"""
Main orchestrator that ties all modules together.

Workflow:
1. Fetch leads from Airtable
2. Split into A/B test groups of 10
3. For each group, generate + send emails using the assigned variation
4. Immediately log every AI message to Airtable 'ai-messages'
5. Track responses and update metrics

Supports daily batch mode: 12 emails max, 4 per A/B group, spread throughout the day.
"""
import logging
import time
import json
import os
from typing import Any

from config.settings import EmailConfig

from modules.ab_testing import ABGroup, ABTestEngine
from modules.airtable_client import AirtableClient
from modules.email_sender import EmailSender
from modules.llm_client import LLMClient, clean_email_content, check_similarity
from modules.response_tracker import ResponseTracker

logger = logging.getLogger(__name__)

# Path to custom email templates (Lisa's edited AI emails)
CUSTOM_TEMPLATES_FILE = os.path.join(
    os.path.dirname(__file__), '..', 'config', 'custom_email_templates.json'
)
# Path to placeholder configuration
PLACEHOLDERS_FILE = os.path.join(
    os.path.dirname(__file__), '..', 'config', 'placeholders.json'
)

# Store reference emails for similarity checking (first email per variant)
REFERENCE_EMAILS = {}


class Orchestrator:
    """Coordinates the full A/B testing lead follow-up pipeline."""

    def __init__(self):
        self.airtable = AirtableClient()
        self.ab_engine = ABTestEngine()
        self.llm = LLMClient()
        self.email_sender = EmailSender()
        self.tracker = ResponseTracker(self.airtable)
        self.custom_templates = self._load_custom_templates()
        self.placeholders = self._load_placeholders()

    def _load_custom_templates(self) -> dict:
        """Load custom email templates from JSON file."""
        if os.path.exists(CUSTOM_TEMPLATES_FILE):
            try:
                with open(CUSTOM_TEMPLATES_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load custom templates: %s", e)
        return {}

    def _load_placeholders(self) -> dict:
        """Load placeholder configuration from JSON file."""
        if os.path.exists(PLACEHOLDERS_FILE):
            try:
                with open(PLACEHOLDERS_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("placeholders", {})
            except Exception as e:
                logger.warning("Failed to load placeholders: %s", e)
        return {
            "name": "Lisa",
            "company": "My Address Number",
            "email": "lisa@egetmyaddressnumber.com",
            "phone": "",
            "website": "www.myaddressnumber.com",
            "product": "Our Solution",
            "service": "Our Services",
            "industry": "Home Decoration"
        }

    def _generate_with_similarity_check(
        self,
        system_prompt: str,
        user_prompt: str,
        variation_id: str,
        max_retries: int = 3,
    ) -> tuple[str, int]:
        """
        Generate email with similarity check against reference email for the variant.

        Regenerates if similarity score is below 0.9.
        """
        global REFERENCE_EMAILS
        total_tokens = 0

        for attempt in range(max_retries):
            body, tokens_used = self.llm.generate_email(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            total_tokens += tokens_used

            # First email for this variant becomes the reference
            if variation_id not in REFERENCE_EMAILS:
                REFERENCE_EMAILS[variation_id] = body
                logger.info("Set reference email for variant %s", variation_id)
                return body, total_tokens

            # Check similarity against reference
            reference = REFERENCE_EMAILS[variation_id]
            similarity = check_similarity(reference, body, self.llm.client, model=self.llm.model)

            if similarity >= 0.9:
                logger.info("Email similarity %.2f >= 0.9, using generated email", similarity)
                return body, total_tokens
            else:
                logger.warning("Email similarity %.2f < 0.9, regenerating (attempt %d/%d)",
                             similarity, attempt + 1, max_retries)

        # If all retries failed, return the last generated email
        logger.warning("Max retries reached for similarity check, using last generated email")
        return body, total_tokens

    # ─── Public entry points ──────────────────────────────────────────

    def run_welcome_campaign(self, status_filter: str = "Intro-email") -> list[ABGroup]:
        """
        Run the initial welcome email campaign with A/B testing.

        1. Fetch leads with the given status
        2. Split into groups of 10
        3. Generate + send welcome emails per variation
        4. Log every message to Airtable immediately
        """
        logger.info("=" * 60)
        logger.info("STARTING WELCOME EMAIL CAMPAIGN (A/B Test)")
        logger.info("=" * 60)

        leads = self.airtable.get_leads_by_status(status_filter)
        if not leads:
            logger.warning("No leads found with status '%s'", status_filter)
            return []

        groups = self.ab_engine.create_groups(leads)
        for group in groups:
            self._process_group_welcome(group)

        self._log_campaign_summary(groups, "Welcome Campaign")
        return groups

    def run_followup_campaign(self, status_filter: str = "Pending-1-week") -> list[ABGroup]:
        """
        Run the 1-week follow-up email campaign with A/B testing.

        1. Fetch leads that haven't responded after 1 week
        2. Split into groups of 10
        3. Generate + send follow-up emails per variation
        4. Log every message to Airtable immediately
        """
        logger.info("=" * 60)
        logger.info("STARTING FOLLOW-UP EMAIL CAMPAIGN (A/B Test)")
        logger.info("=" * 60)

        leads = self.airtable.get_leads_by_status(status_filter)
        if not leads:
            logger.warning("No leads found with status '%s'", status_filter)
            return []

        groups = self.ab_engine.create_groups(leads)
        for group in groups:
            self._process_group_followup(group)

        self._log_campaign_summary(groups, "Follow-Up Campaign")
        return groups

    def check_responses(self) -> list[dict]:
        """
        Check all tracked leads for responses and update metrics.
        Returns updated metrics for all groups.
        """
        logger.info("Checking for responses across all groups...")
        leads_to_check = {
            email: data
            for email, data in self.tracker.state.get("sent_emails", {}).items()
            if not data.get("responded")
        }

        for email, data in leads_to_check.items():
            # Check if lead status was updated to "Responded" in Airtable
            responded_leads = self.airtable.get_leads_by_status("Responded")
            responded_emails = {
                r["fields"].get("Email", "") for r in responded_leads
            }

            if email in responded_emails:
                # Record the response
                self.tracker.record_response(email)
                logger.info("Recorded response from %s (via Airtable status check)", email)

        # Return updated metrics
        return self.tracker.get_all_metrics()

    def check_7day_leads(self) -> int:
        """
        Check for leads that are Intro-email-sent for 7+ days and move to Pending-1-week.
        Returns count of leads moved.
        """
        logger.info("Checking for leads 7+ days in Intro-email-sent status...")
        from datetime import datetime, timedelta, timezone

        leads = self.airtable.get_leads_by_status("Intro-email-sent")
        moved_count = 0
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

        for lead in leads:
            created_time = lead.get("createdTime", "")
            if created_time:
                try:
                    lead_time = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                    if lead_time < seven_days_ago:
                        # Move to Pending-1-week
                        self.airtable.update_lead_status(lead["id"], "Pending-1-week")
                        logger.info("Moved lead %s to Pending-1-week (7+ days since Intro-email-sent)", lead.get("id"))
                        moved_count += 1
                except Exception as e:
                    logger.warning("Failed to parse lead time: %s", e)

        logger.info("Moved %d leads from Intro-email-sent to Pending-1-week", moved_count)
        return moved_count

    def run_daily_batch(self, status_filter: str = "Intro-email", 
                        batch_size: int = 3) -> list[ABGroup]:
        """
        Run a single batch: send N emails (1 per A/B group) at scheduled times.
        
        Designed for 4 daily batches at 9am, 12pm, 3pm, 6pm:
        - Each batch sends 3 emails (1 lead from each A/B group)
        - Total: 12 emails/day, evenly distributed for valid A/B testing
        
        Args:
            status_filter: Airtable status to filter leads
            batch_size: Emails per batch (default 3 = 1 per group)
        
        Returns:
            list[ABGroup]: Groups that had leads processed in this batch
        """
        logger.info("=" * 60)
        logger.info("STARTING BATCH SEND (1 per A/B group)")
        logger.info("Batch size: %d emails (1 per group)", batch_size)
        logger.info("=" * 60)

        leads = self.airtable.get_leads_by_status(status_filter)
        if not leads:
            logger.warning("No leads found with status '%s'", status_filter)
            return []

        # Create A/B groups
        groups = self.ab_engine.create_groups(leads)
        if not groups:
            logger.warning("No groups created from %d leads", len(leads))
            return []
        
        # Track next lead index for each group (for progressive batching)
        if not hasattr(self, '_batch_indexes'):
            self._batch_indexes = {}
        
        # Build batch: take 1 lead from each group (round-robin from current position)
        batch_queue = []
        groups_with_leads = []
        
        for group in groups:
            group_key = f"{group.group_number}_{status_filter}"
            current_idx = self._batch_indexes.get(group_key, 0)
            
            # Find next unsent lead in this group (skip if already processed)
            while current_idx < len(group.leads):
                lead = group.leads[current_idx]
                # Check if this lead was already sent (via status change)
                lead_status = lead.get("fields", {}).get("Status", status_filter)
                if lead_status == status_filter:
                    # This lead is ready to send
                    batch_queue.append((group, lead))
                    groups_with_leads.append(group)
                    current_idx += 1
                    self._batch_indexes[group_key] = current_idx
                    break
                else:
                    # Already processed, move to next
                    current_idx += 1
                    self._batch_indexes[group_key] = current_idx
            
            if len(batch_queue) >= batch_size:
                break
        
        if not batch_queue:
            logger.info("No leads ready to send in this batch (all groups may be exhausted)")
            return []
        
        logger.info("Sending batch of %d emails (1 per %d groups)", 
                    len(batch_queue), len(set(g.group_number for g, _ in batch_queue)))

        # Send each email in the batch
        processed_groups = set()
        
        for idx, (group, lead) in enumerate(batch_queue):
            variation = group.welcome_variation if "Intro" in status_filter else group.followup_variation
            email_type = "welcome" if "Intro" in status_filter else "followup"
            next_status = "Intro-email-sent" if email_type == "welcome" else "Reminder-sent"
            msg_type = "welcome-email" if email_type == "welcome" else "followup-week1"
            
            logger.info(
                "[Batch %d/%d] Group %d → %s variation: %s",
                idx + 1, len(batch_queue), group.group_number, email_type, variation["id"]
            )
            
            success = self._send_single_email(
                lead=lead,
                group=group,
                variation=variation,
                email_type=email_type,
                msg_type=msg_type,
                next_status=next_status,
            )
            
            if success:
                processed_groups.add(group.group_number)
            
            # Small delay between emails in same batch (to avoid rate limits)
            if idx < len(batch_queue) - 1:
                time.sleep(EmailConfig.MIN_DELAY_SECONDS)
        
        # Return groups that were processed
        result_groups = [g for g in groups if g.group_number in processed_groups]
        logger.info("Batch complete: %d emails sent to %d groups", 
                    sum(g.emails_sent for g in result_groups), len(result_groups))
        return result_groups

    def _send_single_email(self, lead: dict, group: ABGroup, variation: dict,
                           email_type: str, msg_type: str, next_status: str) -> bool:
        """Send a single email and update tracking."""
        fields = lead.get("fields", {})
        name = fields.get("Name", "there")
        email = fields.get("Email", "")
        
        if not email:
            logger.warning("Lead %s has no email, skipping", lead.get("id"))
            return False

        # Fetch Company field
        company = lead.get("fields", {}).get("Company", "")

        # Build placeholder values (use lead data if available, otherwise use configured placeholders)
        placeholder_values = {
            "name": name if name else self.placeholders.get("name", "Lisa"),
            "company": company if company else self.placeholders.get("company", "Your Company"),
            "email": self.placeholders.get("email", "lisa@example.com"),
            "phone": self.placeholders.get("phone", "+1 (555) 123-4567"),
            "website": self.placeholders.get("website", "https://example.com"),
            "product": self.placeholders.get("product", "Our Solution"),
            "service": self.placeholders.get("service", "Our Service"),
            "industry": self.placeholders.get("industry", "Technology"),
        }

        # Check for custom template first (Lisa's edited email)
        template_key = f"{msg_type}_template"
        if template_key in self.custom_templates:
            # Use Lisa's custom template
            custom_template = self.custom_templates[template_key]
            body = custom_template["content"]
            # Replace placeholders in custom template using configured values
            for key, value in placeholder_values.items():
                body = body.replace(f"{{{key}}}", value)
            # Clean up markdown and placeholders
            body = clean_email_content(body)
            subject = custom_template.get("subject", variation["subject"])
            for key, value in placeholder_values.items():
                subject = subject.replace(f"{{{key}}}", value)
            tokens_used = 0  # No AI generation for custom templates
            logger.info("Using custom template for %s (message_id: %s)", msg_type, custom_template.get("original_message_id"))
        else:
            # Generate personalized email (with company if available)
            try:
                user_prompt = variation["user_prompt_template"].format(name=name, company=company)
                subject = variation["subject"].format(name=name, company=company)
            except KeyError:
                # Fallback if prompt doesn't use company placeholder
                user_prompt = variation["user_prompt_template"].format(name=name)
                subject = variation["subject"].format(name=name)

            # Generate email with similarity check (regenerate if < 0.9)
            body, tokens_used = self._generate_with_similarity_check(
                system_prompt=variation["system_prompt"],
                user_prompt=user_prompt,
                variation_id=variation["id"],
                max_retries=3,
            )

        # Send email
        success = self.email_sender.send(email, subject, body)
        
        if success:
            group.emails_sent += 1
            
            # Log agent action (after successful send)
            self.airtable.log_agent_action(
                tools=msg_type,  # e.g., "welcome-email", "followup-week1"
                user_query=user_prompt,
                ai_message=body,
                total_tokens=tokens_used,
            )
            
            # Log to Airtable
            current_rate = self.tracker.get_response_rate_for_group(group.group_number)
            record = self.airtable.log_ai_message(
                msg_type=msg_type,
                notes=(
                    f"Daily batch | Variation: {variation['id']} ({variation['label']}). "
                    f"Sent to: {name} <{email}>. Group {group.group_number}."
                ),
                ai_message=body,
                response_rate=current_rate,
                group=group.group_number,
            )
            
            # Track in local state
            self.tracker.record_email_sent(
                lead_email=email,
                group_number=group.group_number,
                email_type=email_type,
                airtable_msg_record_id=record["id"],
            )
            
            # Update lead status
            self.airtable.update_lead_status(lead["id"], next_status)
            return True
        
        return False

    # ─── Internal processing ──────────────────────────────────────────

    def _process_group_welcome(self, group: ABGroup) -> None:
        """Generate and send welcome emails for one A/B group."""
        variation = group.welcome_variation
        logger.info(
            "Processing welcome group %d (%d leads) — variation: %s",
            group.group_number, len(group.leads), variation["id"],
        )

        for lead in group.leads:
            fields = lead.get("fields", {})
            name = fields.get("Name", "there")
            email = fields.get("Email", "")
            if not email:
                logger.warning("Lead %s has no email, skipping", lead.get("id"))
                continue

            # Generate personalized email
            user_prompt = variation["user_prompt_template"].format(name=name)
            body, tokens_used = self.llm.generate_email(
                system_prompt=variation["system_prompt"],
                user_prompt=user_prompt,
            )

            # Send email
            subject = variation["subject"].format(name=name)
            success = self.email_sender.send(email, subject, body)

            if success:
                group.emails_sent += 1

                # Log agent action (for runs table)
                self.airtable.log_agent_action(
                    tools="welcome-email",
                    user_query=f"Welcome email to {name} from {fields.get('Company', '')}",
                    ai_message=body,
                    total_tokens=tokens_used,
                )

                # IMMEDIATELY log to Airtable ai-messages
                current_rate = self.tracker.get_response_rate_for_group(
                    group.group_number
                )
                record = self.airtable.log_ai_message(
                    msg_type="welcome-email",
                    notes=(
                        f"Variation: {variation['id']} ({variation['label']}). "
                        f"Sent to: {name} <{email}>. "
                        f"Group {group.group_number}."
                    ),
                    ai_message=body,
                    response_rate=current_rate,
                    group=group.group_number,
                )

                # Track in local state
                self.tracker.record_email_sent(
                    lead_email=email,
                    group_number=group.group_number,
                    email_type="welcome",
                    airtable_msg_record_id=record["id"],
                )

                # Update lead status
                self.airtable.update_lead_status(lead["id"], "Intro-email-sent")

            # Small delay to avoid rate limits
            time.sleep(1)

    def _process_group_followup(self, group: ABGroup) -> None:
        """Generate and send follow-up emails for one A/B group."""
        variation = group.followup_variation
        logger.info(
            "Processing follow-up group %d (%d leads) — variation: %s",
            group.group_number, len(group.leads), variation["id"],
        )

        for lead in group.leads:
            fields = lead.get("fields", {})
            name = fields.get("Name", "there")
            email = fields.get("Email", "")
            if not email:
                logger.warning("Lead %s has no email, skipping", lead.get("id"))
                continue

            # Generate personalized follow-up
            user_prompt = variation["user_prompt_template"].format(name=name)
            body, tokens_used = self.llm.generate_email(
                system_prompt=variation["system_prompt"],
                user_prompt=user_prompt,
            )

            # Send email
            subject = variation["subject"].format(name=name)
            success = self.email_sender.send(email, subject, body)

            if success:
                group.emails_sent += 1

                # Log agent action (for runs table)
                self.airtable.log_agent_action(
                    tools="followup-week1",
                    user_query=f"Follow-up email to {name} from {fields.get('Company', '')}",
                    ai_message=body,
                    total_tokens=tokens_used,
                )

                # IMMEDIATELY log to Airtable ai-messages
                current_rate = self.tracker.get_response_rate_for_group(
                    group.group_number
                )
                record = self.airtable.log_ai_message(
                    msg_type="followup-week1",
                    notes=(
                        f"Variation: {variation['id']} ({variation['label']}). "
                        f"Sent to: {name} <{email}>. "
                        f"Group {group.group_number}. "
                        f"Follow-up after 1 week of no response."
                    ),
                    ai_message=body,
                    response_rate=current_rate,
                    group=group.group_number,
                )

                # Track in local state
                self.tracker.record_email_sent(
                    lead_email=email,
                    group_number=group.group_number,
                    email_type="followup",
                    airtable_msg_record_id=record["id"],
                )

                # Update lead status
                self.airtable.update_lead_status(lead["id"], "Reminder-sent")

            time.sleep(1)

    def _log_campaign_summary(self, groups: list[ABGroup], campaign_name: str) -> None:
        """Log a summary of the campaign results."""
        logger.info("-" * 60)
        logger.info("%s SUMMARY", campaign_name.upper())
        logger.info("-" * 60)
        total_sent = 0
        for g in groups:
            logger.info(
                "  Group %d: %d emails sent | variation: %s + %s",
                g.group_number,
                g.emails_sent,
                g.welcome_variation["id"],
                g.followup_variation["id"],
            )
            total_sent += g.emails_sent
        logger.info("  TOTAL emails sent: %d", total_sent)
        logger.info("-" * 60)

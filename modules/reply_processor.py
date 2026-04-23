"""
Reply processing module.

Analyzes lead reply emails using LLM to:
1. Classify intent (question vs interest) with {{contact-intent}} detail
2. Generate brand-aware draft replies using customized prompt templates
3. Log drafts to Airtable
4. Notify Lisa via SMS
"""
import logging
import os
from typing import Literal

from modules.llm_client import LLMClient, get_relevant_brand_context
from modules.twilio_client import TwilioClient
from modules.airtable_client import AirtableClient

logger = logging.getLogger(__name__)

# ── Prompt Templates ────────────────────────────────────────────────────────

INTENT_CLASSIFICATION_PROMPT = """You are analyzing an email reply from a potential customer.

Classify the intent and provide a specific detail that fills the variable {{contact-intent}}.

Reply to analyze:
---
{reply_content}
---

Return your response in this exact format:
TYPE: <question|interest>
INTENT: <specific 3-5 word description>

Examples:
TYPE: question
INTENT: pricing for address plaques

TYPE: interest
INTENT: ready to order mailbox

TYPE: question
INTENT: installation process and tools

TYPE: interest
INTENT: interested in bulk order
"""

QUESTION_REPLY_TEMPLATE = """You are Lisa, a contractor of My Address Number (myaddressnumber.com). 
A potential customer has sent you an email with a question.
As far as the potential customer is concerned, you are a cofounder of My Address Number.

BRAND GUIDELINES:
{brand_guidelines}

CUSTOMER INTENT: {{contact-intent}}

The customer's specific question is:
---
{reply_content}
---

Draft a warm, helpful, and concise email reply (under 150 words) that:
1. Directly answers their question using the brand guidelines and product knowledge
2. Sounds natural and personal — like a real person, not AI
3. Includes a subtle product recommendation or next step when relevant
4. Ends with an open question or clear next step
5. Uses "we" and "you" to build connection

Do NOT use markdown formatting (**bold**, *italic*).
Do NOT include placeholder text like [Your Name].
Avoid using "*" to make differnt points. Number them instead.
Sign off as "Lisa" or "Lisa from My Address Number".
"""

INTEREST_REPLY_TEMPLATE = """You are Lisa, the founder of My Address Number (myaddressnumber.com).
A potential customer has sent you an email showing interest!

BRAND GUIDELINES:
{brand_guidelines}

CUSTOMER INTENT: {{contact-intent}}

The customer's message:
---
{reply_content}
---

Draft a human-centric (warm, personalized) but professional follow-up email (under 150 words) that:
1. Acknowledge and thank them for their interest
2. Provides a clear next step (schedule call, view specific products, place order)
3. Creates gentle urgency without being pushy
4. Sounds natural and personal — like a real person, not AI
5. Includes a relevant product recommendation based on their interest

Do NOT use markdown formatting (**bold**, *italic*).
Do NOT use subheaders like "#", "##", or "###".
Do NOT include placeholder text like [Your Name].
Sign off as "Best, Lisa" or "Lisa from My Address Number".
"""


class ReplyProcessor:
    """Processes lead reply emails with AI intent classification and draft generation."""

    def __init__(self, airtable: AirtableClient):
        self.llm = LLMClient()
        self.twilio = TwilioClient()
        self.airtable = airtable

    def process_reply(
        self,
        lead_email: str,
        lead_name: str,
        reply_subject: str,
        reply_content: str,
        lead_record_id: str = "",
    ) -> dict:
        """Process a single lead reply end-to-end.

        Args:
            lead_email: Email of the lead
            lead_name: Name of the lead
            reply_subject: Subject of the reply email
            reply_content: Body of the reply email
            lead_record_id: Airtable record ID for the lead

        Returns:
            dict with keys: intent_type, intent_detail, draft_reply, sms_sent, airtable_logged
        """
        logger.info("Processing reply from %s (%s): %s", lead_name, lead_email, reply_subject)

        # Step 1: Classify intent (fills {{contact-intent}})
        intent_type, intent_detail = self._classify_intent(reply_content)
        logger.info("Intent classified: %s - %s", intent_type, intent_detail)

        # Step 2: Generate draft reply using appropriate template
        draft_reply = self._generate_draft(intent_type, intent_detail, reply_content)
        logger.info("Draft generated (%d chars)", len(draft_reply))

        # Step 3: Log draft to Airtable
        airtable_logged = self._log_draft(
            lead_email=lead_email,
            lead_name=lead_name,
            reply_subject=reply_subject,
            reply_content=reply_content,
            intent_type=intent_type,
            intent_detail=intent_detail,
            draft_reply=draft_reply,
            lead_record_id=lead_record_id,
        )

        # Step 4: Send SMS notification to Lisa
        sms_sent = self.twilio.send_reply_notification(
            lead_name=lead_name,
            lead_email=lead_email,
            intent_type=intent_type,
            intent_detail=intent_detail,
            draft_preview=draft_reply[:100],
        )

        return {
            "intent_type": intent_type,
            "intent_detail": intent_detail,
            "draft_reply": draft_reply,
            "sms_sent": sms_sent,
            "airtable_logged": airtable_logged,
        }

    def _classify_intent(self, reply_content: str) -> tuple[Literal["question", "interest"], str]:
        """Classify reply intent using LLM. Returns (type, detail)."""
        prompt = INTENT_CLASSIFICATION_PROMPT.format(reply_content=reply_content)

        try:
            content, _ = self.llm.generate_email(
                system_prompt="You are an expert at analyzing customer email replies.",
                user_prompt=prompt,
                max_tokens=100,
            )

            # Parse the response
            intent_type = "question"  # default
            intent_detail = "general inquiry"

            for line in content.strip().split("\n"):
                line = line.strip()
                if line.upper().startswith("TYPE:"):
                    type_val = line.split(":", 1)[1].strip().lower()
                    if type_val in ("question", "interest"):
                        intent_type = type_val  # type: ignore[assignment]
                elif line.upper().startswith("INTENT:"):
                    intent_detail = line.split(":", 1)[1].strip()

            return intent_type, intent_detail  # type: ignore[return-value]
        except Exception as e:
            logger.warning("Intent classification failed: %s. Defaulting to question.", e)
            return "question", "general inquiry"  # type: ignore[return-value]

    def _generate_draft(
        self,
        intent_type: Literal["question", "interest"],
        intent_detail: str,
        reply_content: str,
    ) -> str:
        """Generate a draft reply using the appropriate template with brand context."""
        # Inject {{contact-intent}} into template
        # Use selective section retrieval — "manual RAG" based on intent keywords
        brand = get_relevant_brand_context(intent_detail)
        if not brand:
            brand = "My Address Number - Premium address numbers and plaques."

        if intent_type == "question":
            template = QUESTION_REPLY_TEMPLATE
        else:
            template = INTEREST_REPLY_TEMPLATE

        prompt = template.replace("{{contact-intent}}", intent_detail).format(
            brand_guidelines=brand,
            reply_content=reply_content,
        )

        try:
            draft, _ = self.llm.generate_email(
                system_prompt="You are Lisa from My Address Number. Write natural, personal emails.",
                user_prompt=prompt,
                max_tokens=600,
            )
            return draft
        except Exception as e:
            logger.error("Draft generation failed: %s", e)
            return f"Hi there,\n\nThanks for your message about {intent_detail}! Let me get back to you with more details.\n\nBest,\nLisa"

    def _log_draft(
        self,
        lead_email: str,
        lead_name: str,
        reply_subject: str,
        reply_content: str,
        intent_type: str,
        intent_detail: str,
        draft_reply: str,
        lead_record_id: str = "",
    ) -> bool:
        """Log the reply and draft to Airtable for Lisa's review."""
        try:
            notes = (
                f"Lead: {lead_name} <{lead_email}>. "
                f"Subject: {reply_subject}. "
                f"Intent: {intent_type} - {intent_detail}. "
                f"Auto-draft generated."
            )

            record = self.airtable.log_ai_message(
                msg_type=f"reply-{intent_type}",
                notes=notes,
                ai_message=draft_reply,
                response_rate=0.0,
                group=0,
            )

            # Update lead status to Responded if we have the record ID
            if lead_record_id:
                self.airtable.update_lead_status(lead_record_id, "Responded")

            logger.info("Draft reply logged to Airtable: %s", record.get("id", "unknown"))
            return True
        except Exception as e:
            logger.error("Failed to log draft to Airtable: %s", e)
            return False

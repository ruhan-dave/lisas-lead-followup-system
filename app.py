"""
Web dashboard for Lisa — monitor runs, view emails, edit prompts
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import subprocess
import os
import json
import threading
import time
import logging
from datetime import datetime, timedelta
from modules.airtable_client import AirtableClient
from modules.imap_monitor import IMAPMonitor
from modules.reply_processor import ReplyProcessor
from config.settings import AirtableConfig
from modules.ab_testing import WELCOME_VARIATIONS, FOLLOWUP_VARIATIONS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

airtable = AirtableClient()
from modules.response_tracker import ResponseTracker
_tracker = ResponseTracker(airtable)
reply_processor = ReplyProcessor(airtable, tracker=_tracker)

# ── Background IMAP Reply Monitor ─────────────────────────────────────────

def _background_imap_monitor(interval_minutes: int = 10):
    """Background thread: check IMAP inbox every N minutes for replies."""
    logger = logging.getLogger(__name__)
    logger.info("Starting background IMAP monitor (every %d min)", interval_minutes)

    imap = IMAPMonitor()
    if not imap.enabled:
        logger.warning("IMAP not configured. Background monitor will not run.")
        return

    # Track processed message IDs to avoid duplicates
    processed_ids: set[str] = set()

    while True:
        try:
            time.sleep(interval_minutes * 60)

            # Fetch leads that might have replied (Intro-email-sent or Pending-1-week)
            leads = (
                airtable.get_leads_by_status("Intro-email-sent")
                + airtable.get_leads_by_status("Pending-1-week")
                + airtable.get_leads_by_status("Reminder-sent")
            )

            if not leads:
                logger.debug("No active leads to check for replies")
                continue

            # Build sent_emails list for IMAP matching
            sent_emails = []
            lead_map: dict[str, dict] = {}
            for lead in leads:
                fields = lead.get("fields", {})
                email = fields.get("Email", "")
                if email:
                    sent_emails.append({
                        "email": email,
                        "sent_at": lead.get("createdTime", ""),
                        "lead_id": lead.get("id", ""),
                    })
                    lead_map[email] = lead

            # Check IMAP for replies
            replies = imap.check_for_replies(sent_emails)

            for reply in replies:
                msg_id = reply.get("message_id", "")
                if msg_id in processed_ids:
                    continue
                processed_ids.add(msg_id)

                sender_email = reply.get("sender_email", "")
                lead = lead_map.get(sender_email)
                if not lead:
                    continue

                lead_fields = lead.get("fields", {})
                lead_name = lead_fields.get("Name", "there")
                lead_record_id = lead.get("id", "")

                logger.info(
                    "New reply detected from %s (%s): %s",
                    lead_name, sender_email, reply.get("subject", "")
                )

                # Process the reply (classify intent, generate draft, SMS, Airtable)
                try:
                    result = reply_processor.process_reply(
                        lead_email=sender_email,
                        lead_name=lead_name,
                        reply_subject=reply.get("subject", ""),
                        reply_content=reply.get("body", reply.get("subject", "")),
                        lead_record_id=lead_record_id,
                    )
                    logger.info(
                        "Reply processed: intent=%s, sms_sent=%s, airtable=%s",
                        result["intent_detail"],
                        result["sms_sent"],
                        result["airtable_logged"],
                    )
                except Exception as e:
                    logger.error("Failed to process reply from %s: %s", sender_email, e)

        except Exception as e:
            logger.error("Background IMAP monitor error: %s", e)
            time.sleep(60)  # Retry in 1 minute on error


# Start background thread on app startup (only once, not on reloads)
_background_thread_started = False


@app.before_request
def _start_background_monitor():
    global _background_thread_started
    if not _background_thread_started and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        thread = threading.Thread(
            target=_background_imap_monitor,
            args=(10,),  # Check every 10 minutes
            daemon=True,
            name="IMAP-Monitor",
        )
        thread.start()
        _background_thread_started = True

# Path to custom prompts file (persists Lisa's edits)
PROMPTS_FILE = os.path.join(os.path.dirname(__file__), 'config', 'custom_prompts.json')
# Path to custom email templates (Lisa's edited AI emails)
CUSTOM_TEMPLATES_FILE = os.path.join(os.path.dirname(__file__), 'config', 'custom_email_templates.json')
# Path to placeholder configuration
PLACEHOLDERS_FILE = os.path.join(os.path.dirname(__file__), 'config', 'placeholders.json')


def _load_prompts():
    """Load prompts: custom if they exist, otherwise defaults from ab_testing.py"""
    if os.path.exists(PROMPTS_FILE):
        with open(PROMPTS_FILE, 'r') as f:
            return json.load(f)
    return {
        "welcome": WELCOME_VARIATIONS,
        "followup": FOLLOWUP_VARIATIONS,
    }


def _save_prompts(prompts_data):
    """Save prompts to file"""
    with open(PROMPTS_FILE, 'w') as f:
        json.dump(prompts_data, f, indent=2)


def _load_placeholders():
    """Load placeholder configuration"""
    if os.path.exists(PLACEHOLDERS_FILE):
        with open(PLACEHOLDERS_FILE, 'r') as f:
            data = json.load(f)
            return data.get("placeholders", {})
    return {
        "name": "Lisa",
        "company": "Your Company",
        "email": "lisa@example.com",
        "phone": "+1 (555) 123-4567",
        "website": "https://example.com",
        "product": "Our Solution",
        "service": "Our Service",
        "industry": "Technology"
    }


def _save_placeholders(placeholders_data):
    """Save placeholder configuration to file"""
    data = {
        "created_at": datetime.now().isoformat(),
        "placeholders": placeholders_data,
        "notes": "Configure default placeholder values for email templates. These will be used when lead data is not available."
    }
    with open(PLACEHOLDERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _load_custom_templates():
    """Load custom email templates edited by Lisa"""
    if os.path.exists(CUSTOM_TEMPLATES_FILE):
        with open(CUSTOM_TEMPLATES_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_custom_templates(templates):
    """Save Lisa's custom email templates"""
    os.makedirs(os.path.dirname(CUSTOM_TEMPLATES_FILE), exist_ok=True)
    with open(CUSTOM_TEMPLATES_FILE, 'w') as f:
        json.dump(templates, f, indent=2)


# ── Routes ────────────────────────────────────────────────────────────────


@app.route('/')
def dashboard():
    """Main dashboard: recent runs"""
    try:
        runs = airtable.get_recent_runs(limit=15)
        # Get group metrics for 30-email alert
        from modules.response_tracker import ResponseTracker
        tracker = ResponseTracker(airtable)
        group_metrics = tracker.get_all_metrics()
        # Check if any group has reached 30 emails
        groups_at_30 = [m for m in group_metrics if m["emails_sent"] >= 30]
    except Exception:
        runs = []
        group_metrics = []
        groups_at_30 = []

    airtable_urls = {
        "base": AirtableConfig.BASE_URL,
        "leads": AirtableConfig.LEADS_URL,
        "messages": AirtableConfig.MESSAGES_URL,
        "actions": AirtableConfig.AGENT_ACTIONS_URL,
    }
    return render_template('dashboard.html', runs=runs, airtable_urls=airtable_urls,
                          group_metrics=group_metrics, groups_at_30=groups_at_30)


@app.route('/emails')
def emails():
    """View all AI-generated email content"""
    try:
        messages = airtable.get_recent_messages(limit=30)
        templates = _load_custom_templates()
    except Exception:
        messages = []
        templates = {}

    airtable_urls = {
        "base": AirtableConfig.BASE_URL,
        "messages": AirtableConfig.MESSAGES_URL,
    }

    return render_template('emails.html', messages=messages, airtable_urls=airtable_urls, templates=templates)


@app.route('/emails/<message_id>/edit', methods=['GET', 'POST'])
def edit_email(message_id):
    """Edit an AI-generated email and save as custom template"""
    try:
        message = airtable.get_message_by_id(message_id)
        templates = _load_custom_templates()

        if request.method == 'POST':
            # Save as custom template
            template_key = f"{message['type']}_template"
            templates[template_key] = {
                "content": request.form['content'],
                "subject": message.get('subject', ''),
                "original_message_id": message_id,
                "created_at": datetime.now().isoformat(),
            }
            _save_custom_templates(templates)
            flash("Email saved as custom template — will override AI generation.", "success")
            return redirect(url_for('emails'))

        return render_template('edit_email.html', message=message, templates=templates)
    except Exception as e:
        flash(f"Error loading email: {str(e)}", "error")
        return redirect(url_for('emails'))


@app.route('/prompts')
def prompts():
    """View and edit AI prompts"""
    prompts_data = _load_prompts()

    # Calculate days remaining for custom prompts
    days_remaining = None
    expires_at = prompts_data.get("expires_at")
    if expires_at:
        expiration_date = datetime.fromisoformat(expires_at)
        if datetime.now() < expiration_date:
            days_remaining = (expiration_date - datetime.now()).days + 1  # +1 to count current day
        else:
            days_remaining = 0

    airtable_urls = {
        "base": AirtableConfig.BASE_URL,
    }
    return render_template('prompts.html', prompts=prompts_data, airtable_urls=airtable_urls, days_remaining=days_remaining)


@app.route('/prompts/save', methods=['POST'])
def save_prompts():
    """Save edited prompts (all or individual variant)"""
    try:
        prompts_data = _load_prompts()
        save_variant = request.form.get("save_variant")

        if save_variant:
            # Save only the specific variant
            if save_variant.startswith("welcome_"):
                idx = int(save_variant.split("_")[1])
                prefix = f"welcome_{idx}"
                if f"{prefix}_system_prompt" in request.form:
                    prompts_data["welcome"][idx]["system_prompt"] = request.form[f"{prefix}_system_prompt"]
                    prompts_data["welcome"][idx]["user_prompt_template"] = request.form[f"{prefix}_user_prompt"]
                    prompts_data["welcome"][idx]["subject"] = request.form[f"{prefix}_subject"]
                    flash(f"Welcome Variant {idx + 1} saved — changes apply for the next 3 days.", "success")
            elif save_variant.startswith("followup_"):
                idx = int(save_variant.split("_")[1])
                prefix = f"followup_{idx}"
                if f"{prefix}_system_prompt" in request.form:
                    prompts_data["followup"][idx]["system_prompt"] = request.form[f"{prefix}_system_prompt"]
                    prompts_data["followup"][idx]["user_prompt_template"] = request.form[f"{prefix}_user_prompt"]
                    prompts_data["followup"][idx]["subject"] = request.form[f"{prefix}_subject"]
                    flash(f"Follow-Up Variant {idx + 1} saved — changes apply for the next 3 days.", "success")
        else:
            # Save all variants
            for i, var in enumerate(prompts_data.get("welcome", [])):
                prefix = f"welcome_{i}"
                if f"{prefix}_system_prompt" in request.form:
                    var["system_prompt"] = request.form[f"{prefix}_system_prompt"]
                    var["user_prompt_template"] = request.form[f"{prefix}_user_prompt"]
                    var["subject"] = request.form[f"{prefix}_subject"]

            for i, var in enumerate(prompts_data.get("followup", [])):
                prefix = f"followup_{i}"
                if f"{prefix}_system_prompt" in request.form:
                    var["system_prompt"] = request.form[f"{prefix}_system_prompt"]
                    var["user_prompt_template"] = request.form[f"{prefix}_user_prompt"]
                    var["subject"] = request.form[f"{prefix}_subject"]
            flash("All prompts saved — changes apply for the next 3 days.", "success")

        # Add timestamp for 3-day expiration
        prompts_data["created_at"] = datetime.now().isoformat()
        prompts_data["expires_at"] = (datetime.now() + datetime.timedelta(days=3)).isoformat()

        _save_prompts(prompts_data)
    except Exception as e:
        flash(f"Error saving prompts: {str(e)}", "error")

    return redirect(url_for('prompts'))


@app.route('/placeholders', methods=['GET'])
def placeholders():
    """Placeholder configuration page"""
    placeholders = _load_placeholders()
    return render_template('placeholders.html', placeholders=placeholders)


@app.route('/placeholders/save', methods=['POST'])
def save_placeholders():
    """Save placeholder configuration"""
    try:
        placeholders_data = {
            "name": request.form.get('name', ''),
            "company": request.form.get('company', ''),
            "email": request.form.get('email', ''),
            "phone": request.form.get('phone', ''),
            "website": request.form.get('website', ''),
            "industry": request.form.get('industry', ''),
            "product": request.form.get('product', ''),
            "service": request.form.get('service', ''),
        }
        _save_placeholders(placeholders_data)
        flash("Placeholder configuration saved successfully.", "success")
    except Exception as e:
        flash(f"Error saving placeholders: {str(e)}", "error")

    return redirect(url_for('placeholders'))


@app.route('/trigger/<action>', methods=['POST'])
def trigger_action(action):
    """Trigger a manual action"""
    valid_actions = ['daily-batch', 'check', 'metrics', 'welcome', 'followup', 'full_run']

    if action not in valid_actions:
        flash(f"Invalid action: {action}", "error")
        return redirect(url_for('dashboard'))

    try:
        airtable.log_run(
            action=action,
            status='STARTED',
            triggered_by='MANUAL',
            metadata={'source': 'web_dashboard'}
        )

        cmd = ['python', 'main.py', action]
        if action == 'daily-batch':
            cmd.extend(['--size', '3'])

        subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
        flash(f"Triggered: {action}", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=(os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'))

"""
Web dashboard for Lisa — monitor runs, view emails, edit prompts
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import subprocess
import os
import json
from datetime import datetime, timedelta
from modules.airtable_client import AirtableClient
from config.settings import AirtableConfig
from modules.ab_testing import WELCOME_VARIATIONS, FOLLOWUP_VARIATIONS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

airtable = AirtableClient()

# Path to custom prompts file (persists Lisa's edits)
PROMPTS_FILE = os.path.join(os.path.dirname(__file__), 'config', 'custom_prompts.json')
# Path to custom email templates (Lisa's edited AI emails)
CUSTOM_TEMPLATES_FILE = os.path.join(os.path.dirname(__file__), 'config', 'custom_email_templates.json')


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
    """Save Lisa's custom prompts to disk"""
    os.makedirs(os.path.dirname(PROMPTS_FILE), exist_ok=True)
    with open(PROMPTS_FILE, 'w') as f:
        json.dump(prompts_data, f, indent=2)


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
    app.run(debug=True, port=5000)

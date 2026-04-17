# Lisa Lead Follow-Up System — Enhanced with A/B Testing

An enhanced lead follow-up system that replaces the original n8n workflow with a Python-based A/B testing engine. It reads leads from Airtable, splits them into groups of 10, tests different message variations for both welcome and follow-up emails, sends them via SMTP, and immediately logs every AI-generated message back to Airtable.

---

## Architecture Overview

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Airtable   │────▶│  A/B Test Engine  │────▶│  LLM Client  │
│  (leads tbl) │     │  (groups of 10)   │     │ (OpenRouter)  │
└──────────────┘     └──────────────────┘     └──────┬───────┘
                              │                       │
                              ▼                       ▼
                     ┌──────────────────┐     ┌──────────────┐
                     │ Response Tracker  │     │ Email Sender │
                     │  (metrics/state)  │     │   (SMTP)     │
                     └──────────────────┘     └──────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │    Airtable      │
                     │ (ai-messages tbl)│◀── Logged IMMEDIATELY
                     └──────────────────┘     after each send
```

## What's Different from the Original n8n Workflow

| Feature | Original (n8n) | Enhanced (This System) |
|---|---|---|
| A/B Testing | ❌ None | ✅ Groups of 10, round-robin variations |
| Message Variations | 1 prompt per stage | 3 variations per stage (welcome + follow-up) |
| Metrics Tracking | Basic logging | Response rate %, avg response time per group |
| Immediate Logging | Partial | ✅ Every AI message logged to Airtable instantly |
| Scalability | Limited by n8n | Full Python — schedule via cron, run in Docker, etc. |

---

## Setup Guide

### 1. Prerequisites

- **Python 3.10+**
- **Airtable account** with a Personal Access Token
- **OpenRouter API key** (for LLM email generation)
- **Gmail App Password** (or any SMTP provider)

### 2. Install Dependencies

```bash
cd lead_followup_system
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

### 4. Airtable Configuration

You need **two tables** in your Airtable base:

#### Table 1: `leads`

| Field Name | Field Type | Description |
|---|---|---|
| Name | Single line text | Lead's full name |
| Email | Email | Lead's email address |
| Company | Single line text | Lead's company name (used in email templates) |
| Phone | Phone number | Lead's phone (optional) |
| Address | Single line text | Lead's address (optional) |
| Status | Single select | One of: `Intro-email`, `Pending-1-week`, `Pending-2-week`, `Responded`, `Contract signed`, `Contract Lost` |

#### Table 2: `ai-messages`

This is the logging table. **Create it with these exact field names:**

| Field Name | Field Type | Notes |
|---|---|---|
| type | Long text | **Primary field**. Values: `welcome-email`, `followup-week1` |
| Notes | Long text | Context about the message (variation used, recipient, group) |
| ai-message | **Long text** | **Plain text only** — the AI-generated email content (no JSON, no prompts) |
| response-rate | Number (percent, 0-1) | Current response rate for the group at time of send |
| group | Number (integer) | The A/B test group number (1, 2, 3, ...) |

> **⚠️ Critical:** The `ai-message` field must be **"Long text"** type, not "User". 
> If you currently have it as "User" type:
> 1. Go to Airtable → ai-messages table
> 2. Click the dropdown next to "ai-message" field
> 3. "Customize field type" → Change to "Long text"
> 4. The code will then work correctly
>
> **What gets stored:** Only the AI-generated email text (e.g., "Hi John, I'm Lisa..."). 
> The system prompts and user prompts are NOT stored — they're only used to generate the content.

#### Table 3: `ai-agent-actions`

Logs every AI action for debugging and monitoring. **Create this table:**

| Field Name | Field Type | Notes |
|---|---|---|
| Timestamp | **Date** (primary) | ISO format UTC timestamp of the action |
| Tools | Long text | Action type: `welcome-email`, `reminder-email`, `reply` |
| User Query | Long text | The prompt/query sent to the AI (includes lead name) |
| AI Message | Long text | The AI-generated response (email content) |
| Total Tokens | Number (decimal) | Total tokens used in the LLM call |

**Example record:**
- Timestamp: `2024-01-15T09:00:00Z`
- Tools: `welcome-email`
- User Query: `Write a welcome email to John who is a restaurant owner...`
- AI Message: `Hi John,

I'm Lisa from...`
- Total Tokens: `342`

### 5. Airtable Base ID

Find your Base ID:
1. Go to [airtable.com/api](https://airtable.com/api)
2. Select your base
3. The Base ID starts with `app...` (e.g., `app6a4vGO6ufDSvyb`)

### 6. Email Provider Setup (Custom Domain)

Lisa uses custom domain emails (`lisa@myaddressnumber.com`, `sales@myaddressnumber.com`).

**Common Email Provider Settings:**

| Provider | SMTP_HOST | Port | Password Type |
|----------|-----------|------|---------------|
| **Google Workspace** | smtp.gmail.com | 587 | [App Password](https://myaccount.google.com/apppasswords) |
| **Microsoft 365** | smtp.office365.com | 587 | App Password |
| **Zoho Mail** | smtp.zoho.com | 587 | Account Password |
| **Namecheap** | mail.privateemail.com | 587 | Email Password |
| **GoDaddy** | smtpout.secureserver.net | 465 | Email Password |
| **cPanel/Hosting** | mail.myaddressnumber.com | 587 | Email Password |

**Setup Steps:**
1. Find your email provider in the table above
2. Generate an App Password (Google/Microsoft) or use your email password (others)
3. Update `.env` with your provider's settings:
   ```
   SMTP_HOST=smtp.gmail.com      # Replace with your provider
   SMTP_PORT=587
   SMTP_USER=lisa@myaddressnumber.com
   SMTP_PASSWORD=your-app-password
   EMAIL_FROM_NAME=Lisa
   EMAIL_FROM_ADDRESS=lisa@myaddressnumber.com
   ```

---

## Usage

### Daily Batch Campaign (Recommended for Warming)

```bash
python main.py daily-batch
```

Sends **3 emails per batch** (1 per A/B group) at scheduled times (EST):
- **9:00 AM EST** (morning) - 3 emails
- **12:00 PM EST** (noon) - 3 emails
- **3:00 PM EST** (afternoon) - 3 emails
- **6:00 PM EST** (evening) - 3 emails
- **Total: 12 emails/day**, evenly distributed for valid A/B testing

**Customize batch size:**
```bash
# Send 6 emails per batch (2 per group)
python main.py daily-batch --size 6

# Send welcome emails to leads with different status
python main.py daily-batch --size 3 --status "New Lead"
```

### Send Welcome Emails (A/B Tested)

```bash
python main.py welcome
```

Fetches leads with status `Intro-email`, splits into groups, and sends welcome email variations. **Use after warming period.**

### Send Follow-Up Emails (A/B Tested)

```bash
python main.py followup
```

Fetches leads with status `Pending-1-week`, splits into groups, and sends follow-up variations. **Use after warming period.**

### Check for Responses

```bash
python main.py check
```

Scans for leads whose status changed to `Responded` and updates per-group metrics.

### View Metrics

```bash
python main.py metrics
```

Displays a formatted table of response rates and average response times per A/B group.

### Full Run (Welcome + Follow-Up)

```bash
python main.py full_run
```

Runs both campaigns sequentially.

### Dry Run Mode

Set `DRY_RUN=true` in `.env` to test without actually sending emails. All other steps (Airtable reads, LLM generation, logging) still execute.

### Custom Status Filters

```bash
python main.py welcome --status "New Lead"
python main.py followup --status "Pending-2-week"
```

---

## A/B Testing Details

### How Groups Are Formed

Leads are fetched from Airtable and split into sequential groups. For daily batches, each batch sends 1 email per group to maintain even A/B distribution.

### Message Variations

**Welcome Emails (3 variations, round-robin per group):**

| Variation | Strategy | Subject Line Style |
|---|---|---|
| `welcome_A` | Friendly & Benefits-Focused | "Welcome from Lisa — Let's save you time & money" |
| `welcome_B` | Urgency & Social Proof | "Join 200+ businesses already seeing results..." |
| `welcome_C` | Question-Led & Curiosity | "Quick question for you, {name}" |

**Follow-Up Emails (3 variations, round-robin per group):**

| Variation | Strategy | Subject Line Style |
|---|---|---|
| `followup_A` | Gentle Reminder + Value | "Just checking in, {name} — any questions?" |
| `followup_B` | FOMO & Case Study | "Here's what {name} could be saving..." |
| `followup_C` | Direct & Time-Limited Offer | "Last chance for your exclusive offer, {name}" |

### Daily Batch Assignment (Recommended)

Each batch (9am, 12pm, 3pm, 6pm) sends:
- **1 lead from Group 1** → welcome_A
- **1 lead from Group 2** → welcome_B
- **1 lead from Group 3** → welcome_C

This ensures even A/B distribution throughout the day for valid statistical comparison.

### Tracked Metrics Per Group

- **Response rate** (%) — updated in real-time on Airtable `ai-messages` records
- **Average response time** (hours) — how fast leads respond after receiving emails

---

## Scheduling (Production)

### Recommended: GitHub Actions (Cloud-Based)

**Benefits:**
- Automatic deployments on push to GitHub
- Cloud-based (no local server needed)
- Version-controlled schedules
- Built-in logs and history
- Manual trigger option

**Setup:**
1. Push code to GitHub repository
2. Add secrets to GitHub (Settings → Secrets → Actions):
   - `AIRTABLE_API_KEY`
   - `AIRTABLE_BASE_ID`
   - `AIRTABLE_LEADS_TABLE`
   - `AIRTABLE_MESSAGES_TABLE`
   - `AIRTABLE_AGENT_ACTIONS_TABLE`
   - `OPENROUTER_API_KEY`
   - `OPENROUTER_MODEL`
   - `SMTP_USER`
   - `SMTP_PASSWORD`
   - `SMTP_SERVER`
   - `SMTP_PORT`
   - `EMAIL_DAILY_LIMIT`
   - `EMAIL_MIN_DELAY_SECONDS`
   - `AB_GROUP_SIZE`
   - `LOG_LEVEL`
   - `DRY_RUN`
3. Workflows run automatically on schedule:
   - Daily batch: 9am, 12pm, 3pm, 6pm EST (14, 17, 20, 23 UTC)
   - Check replies: Midnight EST (5:00 UTC)
   - Metrics report: Mondays 8am EST (13:00 UTC)

**Alternative: Local Cron**

```bash
# 4 batches per day at business hours
# Each batch sends 3 emails (1 per A/B group)

# Morning batch: 9:00 AM EST (14:00 UTC)
0 14 * * * cd /path/to/lead_followup_system && source venv/bin/activate && python main.py daily-batch

# Noon batch: 12:00 PM EST (17:00 UTC)
0 17 * * * cd /path/to/lead_followup_system && source venv/bin/activate && python main.py daily-batch

# Afternoon batch: 3:00 PM EST (20:00 UTC)
0 20 * * * cd /path/to/lead_followup_system && source venv/bin/activate && python main.py daily-batch

# Evening batch: 6:00 PM EST (23:00 UTC)
0 23 * * * cd /path/to/lead_followup_system && source venv/bin/activate && python main.py daily-batch

# Check for responses at midnight EST (5:00 UTC)
0 5 * * * cd /path/to/lead_followup_system && source venv/bin/activate && python main.py check-replies
0 * * * * cd /path/to/lead_followup_system && source venv/bin/activate && python main.py check
```

### Bulk Campaigns (Post-Warming)

After 4+ weeks of warming, switch to bulk sends:

```bash
# Run welcome emails every morning at 9 AM
0 9 * * * cd /path/to/lead_followup_system && python main.py welcome

# Run follow-up emails every afternoon at 2 PM
0 14 * * * cd /path/to/lead_followup_system && python main.py followup
```

---

## Web Dashboard (For Lisa)

A clean, minimal web dashboard for non-developers to monitor runs, view AI-generated emails, and edit prompts.

**Start the dashboard:**
```bash
source venv/bin/activate
python app.py
```

Then open http://localhost:5000 in your browser.

**Dashboard tabs:**

### 1. Runs Tab
- View recent campaign runs with status (STARTED, COMPLETED, FAILED, RUNNING)
- Trigger manual runs (Daily Batch, Check Responses, Metrics, Welcome Campaign, Follow-Up Campaign, Full Run)
- See who triggered each run (MANUAL, GITHUB_ACTIONS, SYSTEM)
- Color-coded status: Green (running/completed), Red (failed), Blue (started)

### 2. Emails Tab
- View all AI-generated email content with timestamps
- See response rates (yellow highlight)
- Click "Edit" on any email to modify it
- Edited emails are saved as custom templates that override AI generation
- Link to Airtable messages table

### 3. Prompts Tab (A/B Test Variants)
- View and edit the 3 variants for each email type:
  - **Welcome Emails — 3 Variants**
    - Variant A (Group 1): Friendly & Benefits-Focused
    - Variant B (Group 2): Urgency & Social Proof
    - Variant C (Group 3): Question-Led & Curiosity
  - **Follow-Up Emails — 3 Variants**
    - Variant A (Group 1): Gentle Reminder + Value
    - Variant B (Group 2): FOMO & Case Study
    - Variant C (Group 3): Direct & Time-Limited Offer
- Edit subject lines, system prompts, and user prompt templates
- **Custom edits apply for 3 days** — after 3 days, they expire and default prompts are used
- Dashboard shows days remaining for custom edits
- Orange highlighting for edit fields

**Color scheme:**
- **Blue** — Lisa's input (accent color, links)
- **Green** — Running runs, completed status
- **Yellow** — Response rates
- **Orange** — Edit fields, save buttons
- **Red** — Failed runs, attention needed

**For Lisa:**
1. Bookmark the dashboard URL
2. Use Runs tab to trigger manual campaigns and monitor scheduled runs
3. Use Emails tab to review AI-generated emails and edit them
4. Use Prompts tab to customize A/B test variants
5. View all results in Airtable as before

---

## Project Structure

```
lead_followup_system/
├── main.py                    # CLI entry point
├── app.py                     # Flask web dashboard for Lisa
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
├── .gitignore
├── README.md
├── .github/
│   └── workflows/
│       ├── daily-batch.yml    # GitHub Actions: Daily email batches
│       ├── check-responses.yml # GitHub Actions: Check for responses
│       └── metrics-report.yml # GitHub Actions: Weekly metrics
├── config/
│   ├── __init__.py
│   └── settings.py            # Centralized configuration
├── modules/
│   ├── __init__.py
│   ├── ab_testing.py          # A/B test engine + message variations
│   ├── airtable_client.py     # Airtable read/write integration + run tracking
│   ├── email_sender.py        # SMTP email delivery
│   ├── llm_client.py          # OpenRouter LLM client
│   ├── orchestrator.py        # Main pipeline coordinator
│   └── response_tracker.py    # Response metrics + persistence
├── templates/
│   └── dashboard.html         # Web dashboard template
├── tests/
│   ├── __init__.py
│   └── test_ab_testing.py     # Unit tests
└── logs/
    ├── system.log             # Application logs (auto-created)
    └── tracking_state.json    # Persisted tracking state (auto-created)
```

---

## Customizing Message Variations

Edit `modules/ab_testing.py` to add or modify variations. Each variation needs:

```python
{
    "id": "welcome_D",                    # Unique identifier
    "label": "Descriptive Label",         # Human-readable name
    "system_prompt": "...",               # LLM system instruction
    "user_prompt_template": "... {name}", # Template with {name} placeholder
    "subject": "Subject line for {name}", # Email subject with {name} placeholder
}
```

Add it to `WELCOME_VARIATIONS` or `FOLLOWUP_VARIATIONS` and the round-robin assignment will automatically include it.

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `AIRTABLE_API_KEY is not set` | Copy `.env.example` to `.env` and fill in credentials |
| `Gmail authentication failed` | Use an App Password, not your regular password |
| `No leads found` | Check the `--status` filter matches your Airtable Status values |
| `LLM generation failed` | Verify your OpenRouter API key and model name |
| Emails not arriving | Check spam folder; verify SMTP settings; try `DRY_RUN=true` first |

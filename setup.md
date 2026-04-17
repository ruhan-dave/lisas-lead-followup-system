# Complete Setup Guide

This document provides a comprehensive guide to setting up and deploying the Lisa Lead Follow-Up System, including frontend usage, backend operations, and production deployment via GitHub Actions.

## Table of Contents
1. [System Overview](#system-overview)
2. [Prerequisites](#prerequisites)
3. [Initial Setup](#initial-setup)
4. [Frontend Usage](#frontend-usage)
5. [Backend Usage](#backend-usage)
6. [Production Deployment (GitHub Actions)](#production-deployment-github-actions)
7. [Email Reply Detection Alternatives](#email-reply-detection-alternatives)

---

## System Overview

The Lisa Lead Follow-Up System is an A/B testing email campaign system with:
- **Frontend**: Flask dashboard for monitoring, manual triggers, and prompt editing
- **Backend**: Python CLI for email campaigns, response tracking, and metrics
- **Automation**: GitHub Actions workflows for scheduled email sending and reply checking
- **Data Storage**: Airtable for leads, messages, and campaign tracking

**Key Features:**
- A/B testing with 5 welcome and 25 follow-up email variants
- Automatic email generation via LLM
- Semantic similarity checking for email diversity
- Response rate tracking and metrics
- IMAP-based reply detection (with fallback options)

---

## Prerequisites

### Required Accounts
1. **Airtable Account** (free tier available)
   - Base with tables: `leads`, `ai-messages`, `agent-actions`
2. **GitHub Account** (for GitHub Actions deployment)
3. **Email Provider** with SMTP access
   - Options: Gmail, Outlook, Google Workspace, Microsoft 365, Zoho, etc.
4. **OpenRouter API Key** (for LLM email generation)
   - Get at https://openrouter.ai/keys

### Required Software
- Python 3.11+
- pip (Python package manager)
- Git

---

## Initial Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd lead_followup_system
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Airtable Configuration
AIRTABLE_API_KEY=your_airtable_api_key
AIRTABLE_BASE_ID=your_base_id
AIRTABLE_LEADS_TABLE=leads
AIRTABLE_MESSAGES_TABLE=ai-messages
AIRTABLE_AGENT_ACTIONS_TABLE=agent-actions

# Airtable URLs (for dashboard links)
AIRTABLE_BASE_URL=https://airtable.com/your_base_url
AIRTABLE_LEADS_URL=https://airtable.com/your_leads_url
AIRTABLE_MESSAGES_URL=https://airtable.com/your_messages_url
AIRTABLE_AGENT_ACTIONS_URL=https://airtable.com/your_actions_url

# LLM Configuration (OpenRouter)
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=openai/gpt-4o-mini

# Email Configuration (SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=lisa@yourdomain.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=lisa@yourdomain.com

# IMAP Configuration (for reply detection)
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993

# Email Limits
EMAIL_DAILY_LIMIT=100
EMAIL_MIN_DELAY_SECONDS=5

# A/B Testing
AB_GROUP_SIZE=10

# Reply Detection Method
REPLY_DETECTION_METHOD=imap  # Options: imap, airtable, webhook
```

### 4. Verify Setup

Test the backend:
```bash
python main.py --help
```

Test the frontend:
```bash
python app.py
```

Visit http://localhost:5000 to access the dashboard.

---

## Frontend Usage

The Flask dashboard provides a web interface for monitoring and controlling the email campaigns.

### Starting the Dashboard

```bash
python app.py
```

The dashboard will be available at `http://localhost:5000`

### Dashboard Sections

#### 1. Runs Tab
- **Purpose**: View scheduled and manual campaign runs
- **Features**:
  - See recent runs with status (STARTED, COMPLETED, FAILED)
  - View action type (welcome-email, follow-up-email, daily-batch)
  - See who triggered the run (MANUAL, GITHUB_ACTIONS)
  - View notes and metadata
- **Trigger Buttons**:
  - **Daily Batch**: Send 3 emails (1 per A/B group)
  - **Check Responses**: Manually check for email replies
  - **Metrics**: View current A/B test metrics
- **Notice**: Response rates update daily at midnight EST via IMAP

#### 2. Emails Tab
- **Purpose**: View AI-generated email messages
- **Features**:
  - See all sent emails with content
  - View email type (welcome, follow-up)
  - See response rate per email
  - View which A/B group the email belongs to
  - Click to view in Airtable

#### 3. Prompts Tab
- **Purpose**: Edit A/B testing prompt variants
- **Features**:
  - View all 5 welcome email variants
  - View all 25 follow-up email variants
  - Edit subject line, system prompt, and user prompt for each variant
  - **Individual Save buttons**: Save each variant independently
  - **Global Save**: Save all variants at once
  - **Last saved timestamp**: See when custom edits were last saved
  - **Days remaining**: Custom edits expire after 3 days
- **Variants**:
  - Welcome A: Friendly & Benefits-Focused
  - Welcome B: Urgency & Social Proof
  - Welcome C: Question-Led & Curiosity
  - Welcome D: Educational & Resource-Heavy
  - Welcome E: Personal Story & Connection
  - Follow-up A-W: 25 different approaches (social proof, ROI, objection handling, etc.)

#### 4. Leads Tab
- **Purpose**: View leads from Airtable
- **Features**:
  - Search and filter leads
  - View lead status, email, company
  - See which leads have been contacted

### Manual Triggers via Dashboard

You can manually trigger campaigns from the dashboard:
1. Click "Daily Batch" to send 3 emails immediately
2. Click "Check Responses" to manually check for replies
3. Click "Metrics" to view current A/B test metrics

---

## Backend Usage

The backend provides CLI commands for email campaigns and response tracking.

### Available Commands

#### 1. Welcome Campaign
Send initial welcome emails with A/B testing:

```bash
python main.py welcome --status "Intro-email"
```

**Options:**
- `--status`: Airtable status to filter leads (default: "Intro-email")

**What it does:**
- Fetches leads with specified status
- Assigns leads to A/B test groups (10 leads per group)
- Sends welcome emails using different variants per group
- Records emails sent and tracks responses

#### 2. Follow-Up Campaign
Send 1-week follow-up emails:

```bash
python main.py followup --status "Pending-1-week"
```

**Options:**
- `--status`: Airtable status to filter leads (default: "Pending-1-week")

**What it does:**
- Fetches leads who received welcome emails 1 week ago
- Sends follow-up emails using the same A/B group assignments
- Records responses and updates metrics

#### 3. Daily Batch
Send a small batch of emails (for sender reputation warming):

```bash
python main.py daily-batch --size 3 --status "Intro-email"
```

**Options:**
- `--size`: Emails per batch (default: 3 = 1 per A/B group)
- `--status`: Airtable status to filter leads

**What it does:**
- Sends specified number of emails (1 per A/B group)
- Designed for daily scheduled runs (9am, 12pm, 3pm, 6pm EST)
- Logs run to Airtable for tracking

#### 4. Check Replies
Check IMAP inbox for email replies:

```bash
python main.py check-replies
```

**What it does:**
- Connects to IMAP server
- Scans inbox for replies to sent emails
- Automatically records responses
- Updates response rates
- Displays new replies found

#### 5. Check Responses
Check for responses and update metrics:

```bash
python main.py check
```

**What it does:**
- Updates response tracking from Airtable
- Calculates response rates per group
- Displays current metrics

#### 6. Metrics
Display current A/B test metrics:

```bash
python main.py metrics
```

**What it does:**
- Shows emails sent, responses, response rate per group
- Shows average response time per group
- Highlights best performing group

#### 7. Full Run
Run both welcome and follow-up campaigns sequentially:

```bash
python main.py full-run
```

**What it does:**
- Runs welcome campaign
- Runs follow-up campaign
- Displays results for both

### A/B Testing Logic

**Group Assignment:**
- Leads are assigned to groups (Group 1, Group 2, Group 3, etc.)
- Each group uses a different email variant
- Group size is configurable (default: 10 leads per group)

**Email Variants:**
- **Welcome**: 5 variants (A-E) assigned to different groups
- **Follow-up**: 25 variants (A-W) assigned to different groups

**Response Tracking:**
- Each group tracks:
  - Emails sent
  - Responses received
  - Response rate (responses / sent × 100)
  - Average response time

**Similarity Checking:**
- First email per variant becomes reference
- Subsequent emails are checked for semantic similarity
- If similarity < 0.9, email is regenerated (max 3 retries)
- Ensures email diversity within A/B variants

---

## Production Deployment (GitHub Actions)

The system uses GitHub Actions for automated email sending and reply checking.

### GitHub Actions Workflows

#### 1. Daily Email Batch (`.github/workflows/daily-batch.yml`)
**Schedule:** 9am, 12pm, 3pm, 6pm EST (14, 17, 20, 23 UTC)
**Purpose:** Send 3 emails per batch (1 per A/B group)
**Total:** 12 emails/day

**What it does:**
- Runs `python main.py daily-batch --size 3`
- Logs run to Airtable
- Can be triggered manually via workflow_dispatch

#### 2. Check Email Replies (`.github/workflows/check-replies.yml`)
**Schedule:** Midnight EST (5:00 UTC)
**Purpose:** Check IMAP inbox for replies and update response rates
**Total:** 1 check/day

**What it does:**
- Runs `python main.py check-replies`
- Scans IMAP inbox for replies
- Records responses automatically
- Updates response rates in dashboard

### Setting Up GitHub Actions

#### Step 1: Push Code to GitHub

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

#### Step 2: Configure GitHub Secrets

Go to your GitHub repository:
1. Navigate to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add the following secrets:

| Secret Name | Description |
|-------------|-------------|
| `AIRTABLE_API_KEY` | Your Airtable API key |
| `AIRTABLE_BASE_ID` | Your Airtable base ID |
| `AIRTABLE_LEADS_TABLE` | Airtable leads table name |
| `AIRTABLE_MESSAGES_TABLE` | Airtable messages table name |
| `AIRTABLE_AGENT_ACTIONS_TABLE` | Airtable actions table name |
| `AIRTABLE_BASE_URL` | Airtable base URL |
| `AIRTABLE_LEADS_URL` | Airtable leads URL |
| `AIRTABLE_MESSAGES_URL` | Airtable messages URL |
| `AIRTABLE_AGENT_ACTIONS_URL` | Airtable actions URL |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `OPENROUTER_MODEL` | OpenRouter model name |
| `SMTP_SERVER` | SMTP server address |
| `SMTP_PORT` | SMTP port (587 or 465) |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |
| `EMAIL_FROM` | From email address |
| `IMAP_SERVER` | IMAP server address |
| `IMAP_PORT` | IMAP port (993) |
| `AB_GROUP_SIZE` | A/B group size (default: 10) |
| `LOG_LEVEL` | Logging level (INFO, DEBUG) |
| `DRY_RUN` | Set to "true" for testing without sending emails |

#### Step 3: Enable Workflows

The workflows are already configured in `.github/workflows/`. They will automatically:
- Run on the scheduled times
- Show up in the "Actions" tab of your GitHub repository
- Can be triggered manually via the "Run workflow" button

#### Step 4: Monitor Workflows

1. Go to the **Actions** tab in your GitHub repository
2. View workflow runs and their status
3. Click on a run to see logs and details
4. Workflows will show:
   - **Success**: Green checkmark
   - **Failure**: Red X
   - **In progress**: Yellow dot

### Testing Before Production

**Dry Run Mode:**
Set `DRY_RUN=true` in GitHub secrets to test without sending emails:
- System will simulate email sending
- No actual emails will be sent
- Useful for testing workflow configuration

**Manual Trigger:**
Use the "Run workflow" button in GitHub Actions to manually trigger workflows for testing.

### Production Deployment Checklist

- [ ] All environment variables configured in GitHub secrets
- [ ] Airtable tables set up correctly
- [ ] Email provider SMTP credentials verified
- [ ] IMAP credentials verified (if using IMAP reply detection)
- [ ] OpenRouter API key configured
- [ ] Workflows tested in dry-run mode
- [ ] Time zones verified (all times in EST)
- [ ] Dashboard deployed (optional, for monitoring)

### Optional: Deploy Dashboard

If you want to access the dashboard in production:

#### Option 1: Render (Free)
1. Connect GitHub repository to Render
2. Create a new web service
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python app.py`
5. Add environment variables
6. Deploy

#### Option 2: Heroku (Free tier available)
1. Install Heroku CLI
2. Create app: `heroku create`
3. Set config vars: `heroku config:set KEY=value`
4. Push code: `git push heroku main`

#### Option 3: Local Only
- Run dashboard locally: `python app.py`
- Access at `http://localhost:5000`
- Use for manual triggers and monitoring
- GitHub Actions handles automated sending

---

## Email Reply Detection Alternatives

## Problem Statement

The system requires tracking email responses to calculate A/B test response rates. The primary method uses IMAP to scan the inbox for replies. However, this may fail if:
- IMAP credentials are not available
- Email provider doesn't support IMAP
- IMAP access is blocked by security policies
- Authentication issues arise

## Alternative Solutions

### Alternative 1: Manual Marking in Airtable (Current Fallback)

**How it works:**
- Lisa manually checks her email inbox for replies
- Updates lead status in Airtable to "Responded" or similar
- System calculates response rates from Airtable status changes

**Pros:**
- No technical setup required
- Works with any email provider
- Zero additional cost
- Lisa has full control

**Cons:**
- Manual effort required
- Not real-time
- Prone to human error
- Doesn't scale well

**Implementation:**
```python
# In response_tracker.py
def check_airtable_status_changes(self) -> int:
    """Check Airtable for leads whose status changed to 'Responded'."""
    leads = self.airtable.get_leads_by_status("Responded")
    new_responses = 0
    for lead in leads:
        if lead["id"] not in self.state["sent_emails"]:
            continue
        entry = self.state["sent_emails"][lead["id"]]
        if not entry.get("responded"):
            self.record_response(lead["email"])
            new_responses += 1
    return new_responses
```

---

### Alternative 2: Email API with Webhooks (Recommended)

**How it works:**
- Use an email API service (SendGrid, Mailgun, Postmark, AWS SES)
- These services provide webhook notifications for replies
- Set up a webhook endpoint in the system to receive reply notifications
- Automatically record responses when webhooks are received

**Pros:**
- Automatic and real-time
- Reliable and scalable
- Better email deliverability
- Built-in analytics
- No IMAP setup needed

**Cons:**
- Requires API setup
- May have costs (though free tiers available)
- Need to configure webhooks

**Services:**

| Service | Free Tier | Pricing After Free | Webhook Support |
|---------|-----------|-------------------|-----------------|
| **SendGrid** | 100 emails/day | $15/month for 40k/day | ✅ |
| **Mailgun** | 5,000 emails/month | $35/month for 50k/month | ✅ |
| **Postmark** | 100 emails/month (trial) | $1.50/1,000 emails | ✅ |
| **AWS SES** | 200 emails/day (sandbox) | Pay-as-you-go ($0.10/1,000) | ✅ (via SNS) |

**Implementation Steps:**

1. **Choose an email API service** (SendGrid recommended for ease of use)

2. **Update .env with API credentials:**
```bash
SENDGRID_API_KEY=your_sendgrid_api_key
SENDGRID_FROM_EMAIL=lisa@yourdomain.com
```

3. **Add webhook endpoint to Flask app:**
```python
# In app.py
@app.route('/webhooks/sendgrid', methods=['POST'])
def sendgrid_webhook():
    events = request.json
    for event in events:
        if event.get('event') == 'reply':
            sender_email = event.get('email')
            tracker.record_response(sender_email)
    return '', 200
```

4. **Configure webhook in email service dashboard:**
- Set webhook URL to: `https://your-domain.com/webhooks/sendgrid`
- Select events: "reply", "delivered", "opened"

---

### Alternative 3: Reply-To Tracking with Unique Addresses

**How it works:**
- Generate unique reply-to address for each sent email
- Example: `reply+lead123@company.com`
- Set up catch-all forwarding to a monitored inbox
- Parse incoming emails to identify original recipient
- Match reply to original sent email

**Pros:**
- Works with any email provider
- Reliable tracking
- No API dependencies
- Can track individual email interactions

**Cons:**
- Requires domain setup
- Email routing configuration needed
- Still requires some inbox monitoring

**Implementation:**

1. **Set up domain with catch-all forwarding:**
- Buy domain (e.g., company.com)
- Configure email provider to forward all emails to a monitored inbox
- Example: Forward `reply+*@company.com` to `lisa@company.com`

2. **Generate unique reply-to addresses:**
```python
# In orchestrator.py
def generate_reply_to_address(lead_id: str) -> str:
    """Generate unique reply-to address for tracking."""
    return f"reply+{lead_id}@company.com"
```

3. **Parse incoming emails:**
```python
# In imap_monitor.py
def parse_recipient(email_address: str) -> str:
    """Extract lead ID from reply-to address."""
    if email_address.startswith("reply+"):
        lead_id = email_address.split("+")[1].split("@")[0]
        return lead_id
    return None
```

---

### Alternative 4: Email Forwarding to Monitored Inbox

**How it works:**
- Set up automatic forwarding from Lisa's email to a dedicated monitoring inbox
- Use IMAP on the monitoring inbox only
- The monitoring inbox has known credentials
- Lisa's main email doesn't need IMAP access

**Pros:**
- Minimal setup
- Works with most email providers
- Lisa's main email remains secure
- Still uses IMAP (just on different inbox)

**Cons:**
- Requires setting up email forwarding
- Still requires IMAP on monitoring inbox
- May need additional email account

**Implementation:**

1. **Create dedicated monitoring inbox:**
- Example: `monitoring+company@gmail.com`
- Enable IMAP on this account

2. **Set up forwarding from Lisa's email:**
- Forward all emails to monitoring inbox
- Or forward only replies (using email filters)

3. **Update IMAP credentials:**
```bash
# In .env
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
SMTP_USER=monitoring+company@gmail.com  # Use monitoring inbox
SMTP_PASSWORD=monitoring_app_password
```

---

## Proactive Setup Recommendations

### Option A: Buy Domain + Email API Service (Recommended)

**Steps:**
1. Buy a domain (e.g., via Namecheap, GoDaddy, Google Domains)
2. Set up email with Google Workspace or Microsoft 365
3. Use SendGrid or Mailgun for email sending with webhooks
4. Configure webhook endpoint in the system
5. Emails sent via API, replies tracked via webhooks

**Benefits:**
- Professional email address
- Best deliverability
- Automatic reply tracking
- Scalable
- Real-time metrics

**Estimated cost:**
- Domain: $10-15/year
- Google Workspace: $6/user/month
- SendGrid: Free tier (100 emails/day) or $15/month

### Option B: Buy Domain + SMTP + IMAP (Current Approach)

**Steps:**
1. Buy a domain
2. Set up email with provider that supports SMTP and IMAP
3. Configure IMAP credentials in the system
4. Use current IMAP monitoring implementation

**Benefits:**
- Professional email address
- No additional API service needed
- Direct control over email sending

**Risks:**
- IMAP may not work with all providers
- Requires IMAP access
- May need additional setup

### Option C: Use Free Email Provider + Manual Marking

**Steps:**
1. Use existing free email (Gmail, Outlook, etc.)
2. Lisa manually marks responses in Airtable
3. System calculates response rates from Airtable

**Benefits:**
- No cost
- No technical setup
- Works immediately

**Risks:**
- Manual effort
- Lower deliverability
- Not professional
- Prone to errors

---

## Fallback Implementation in Code

Update `response_tracker.py` to support multiple reply detection methods:

```python
class ResponseTracker:
    def __init__(self, airtable: AirtableClient):
        self.airtable = airtable
        self.state: dict[str, Any] = self._load_state()
        self.imap_monitor = IMAPMonitor()
        self.reply_detection_method = os.getenv(
            "REPLY_DETECTION_METHOD", "imap"
        )  # Options: imap, airtable, webhook

    def check_replies(self) -> int:
        """Check for replies using configured method."""
        if self.reply_detection_method == "imap":
            return self._check_imap_replies()
        elif self.reply_detection_method == "airtable":
            return self._check_airtable_status_changes()
        elif self.reply_detection_method == "webhook":
            # Webhooks handle replies automatically
            return 0  # No polling needed
        else:
            logger.warning(f"Unknown reply detection method: {self.reply_detection_method}")
            return 0

    def _check_imap_replies(self) -> int:
        """Check IMAP inbox for replies (current implementation)."""
        if not self.imap_monitor.enabled:
            logger.info("IMAP not configured, skipping reply check")
            return 0
        # ... existing IMAP logic ...

    def _check_airtable_status_changes(self) -> int:
        """Check Airtable for status changes (manual fallback)."""
        leads = self.airtable.get_leads_by_status("Responded")
        new_responses = 0
        for lead in leads:
            lead_email = lead.get("email")
            if lead_email in self.state["sent_emails"]:
                entry = self.state["sent_emails"][lead_email]
                if not entry.get("responded"):
                    self.record_response(lead_email)
                    new_responses += 1
        return new_responses
```

Add to `.env`:
```bash
REPLY_DETECTION_METHOD=imap  # Options: imap, airtable, webhook
```

---

## Decision Matrix

| Factor | IMAP | Airtable Manual | Email API Webhooks | Reply-To Tracking |
|--------|------|-----------------|-------------------|------------------|
| **Setup difficulty** | Medium | Easy | Medium | Hard |
| **Reliability** | Medium | Low | High | High |
| **Real-time** | Yes | No | Yes | Yes |
| **Cost** | Free | Free | Free tier available | Domain cost |
| **Scalability** | Medium | Low | High | High |
| **Professional** | Medium | Low | High | High |
| **Deliverability** | Medium | N/A | High | High |

---

## Recommended Path Forward

**Phase 1: Immediate (Current)**
- Use IMAP if credentials available
- Fall back to manual Airtable marking
- Document this in setup guide

**Phase 2: Short-term (1-2 weeks)**
- Buy domain and set up professional email
- Configure IMAP with new email provider
- Test IMAP monitoring

**Phase 3: Long-term (1-2 months)**
- If IMAP still problematic, migrate to email API
- Implement webhook endpoint
- Configure email service (SendGrid/Mailgun)
- Remove IMAP dependency

---

## Quick Start: Which Should You Choose?

**Choose IMAP if:**
- Email provider supports IMAP
- You have IMAP credentials
- Want to avoid additional services

**Choose Airtable Manual if:**
- IMAP not available
- Low volume of emails
- Willing to manually track responses

**Choose Email API Webhooks if:**
- Want automatic, real-time tracking
- Need best deliverability
- Willing to set up additional service

**Choose Reply-To Tracking if:**
- Have domain and email routing control
- Need per-email tracking
- Want to avoid IMAP on main email

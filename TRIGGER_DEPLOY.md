# Trigger.dev Deployment Guide

This guide walks you through deploying the Lisa Lead Follow-Up System to Trigger.dev for reliable, observable A/B testing automation.

---

## Why Trigger.dev?

| Feature | Local/Cron | Trigger.dev |
|---------|-----------|-------------|
| **Observability** | Log files | Real-time dashboard with step-by-step execution |
| **Retries** | Manual | Automatic with exponential backoff |
| **Scheduling** | Cron (server-dependent) | Cloud-native, timezone-aware |
| **Debugging** | SSH/log diving | Full trace, replay, and replay |
| **Scalability** | Single machine | Distributed workers |
| **Alerting** | Manual setup | Built-in failure notifications |

---

## Prerequisites

1. **Node.js 18+** and **npm**
2. **Python 3.10+**
3. **Trigger.dev account** (free tier available at [trigger.dev](https://trigger.dev))
4. **Trigger.dev CLI** installed: `npm install -g @trigger.dev/cli`

### Pricing (as of 2024)

| Plan | Cost | What You Get |
|------|------|--------------|
| **Free** | **$0** | **10,000 task runs/month** — plenty for your use case |
| Hobby | $10/mo | 50,000 task runs/month |
| Pro | $29/mo | 200,000 task runs/month |

**Your usage**: 4 batches/day × 30 days = 120 runs/month (well under free limit)

The free tier includes:
- All scheduling features
- Full observability dashboard
- Retries and timeouts
- Python runtime support
- Email notifications on failure

---

## Quick Start

### 1. Install Dependencies

```bash
# Install Node dependencies
npm install

# Install Python dependencies (including Trigger.dev SDK)
pip install -r requirements.txt
```

### 2. Authenticate with Trigger.dev

```bash
trigger login
```

This opens a browser to authenticate your CLI with your Trigger.dev account.

### 3. Initialize the Project

```bash
trigger init
```

Select:
- **Project name**: `lead-followup-system`
- **Runtime**: Python 3.10
- **Region**: Choose closest to your Airtable data

### 4. Configure Environment Variables

In the Trigger.dev dashboard:

1. Go to your project **Environment Variables**
2. Add all variables from your `.env` file:

```
AIRTABLE_API_KEY=path4eORLwfP2stok...
AIRTABLE_BASE_ID=app6a4vGO6ufDSvyb
AIRTABLE_LEADS_TABLE=leads
AIRTABLE_MESSAGES_TABLE=ai-messages

OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-oss-120b:free

# Custom domain email (lisa@myaddressnumber.com)
# Replace with your email provider's SMTP settings:
SMTP_HOST=smtp.gmail.com        # Google Workspace: smtp.gmail.com
                                # Microsoft 365: smtp.office365.com
                                # cPanel: mail.myaddressnumber.com
SMTP_PORT=587
SMTP_USER=lisa@myaddressnumber.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM_NAME=Lisa
EMAIL_FROM_ADDRESS=lisa@myaddressnumber.com

AB_GROUP_SIZE=15
LOG_LEVEL=INFO
DRY_RUN=false
```

**Note:** Lisa uses custom domain emails (`lisa@myaddressnumber.com`, `sales@myaddressnumber.com`). 
- If using **Google Workspace**: Generate an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- If using **Microsoft 365**: Same process, App Password required
- If using **web hosting email**: Use your host's SMTP server (usually mail.yourdomain.com)

### 5. Deploy

```bash
trigger deploy
```

This uploads your code and activates all scheduled tasks.

---

## Available Tasks

After deployment, you'll see these tasks in the Trigger.dev dashboard:

| Task ID | Schedule | Description |
|---------|----------|-------------|
| **`daily-batch`** | **4× daily (9am, 12pm, 3pm, 6pm ET)** | **3 emails/batch (1 per A/B group) = 12/day** |
| `check-responses` | Every hour | Updates response metrics |
| `metrics-report` | Mondays 8:00 AM ET | Weekly performance report |
| `welcome-campaign` | Manual only | Bulk welcome emails (use after warming) |
| `followup-campaign` | Manual only | Bulk follow-up emails (use after warming) |
| `full-run` | Manual only | Welcome + follow-up combined |

### 🌡️ Warming Schedule (Recommended)

**Phase 1: Daily Batches (Weeks 1-4)**
- 4 batches/day at business hours: 9am, 12pm, 3pm, 6pm
- 3 emails per batch = 1 from each A/B group
- Total: 12 emails/day with even A/B distribution
- Natural sending pattern during active hours

**Phase 2: Increase Volume (Weeks 5-8)**
- Option A: Increase batch size (e.g., 6 emails = 2 per group)
- Option B: Add more batch times (e.g., 8am, 11am, 2pm, 5pm, 8pm)

**Phase 3: Full Volume (Week 9+)**
- Switch to bulk campaigns or increase batch size to 50-100 emails/day

---

## Local Development

### Test Tasks Locally

```bash
# Test batch send (3 emails = 1 per A/B group)
python main.py daily-batch

# Test with larger batch size (6 emails = 2 per group)
python main.py daily-batch --size 6

# Or use Trigger.dev local dev server
trigger dev
```

### Run Individual Tasks

```python
from trigger import welcome_campaign, TriggerContext

# Run a task locally
context = TriggerContext()
result = welcome_campaign(context, status_filter="Intro-email")
print(result)
```

---

## Monitoring & Debugging

### Dashboard Views

Once deployed, the Trigger.dev dashboard shows:

1. **Run History**: Every execution with logs, duration, and status
2. **Task List**: All 5 tasks with their schedules
3. **Run Details**: 
   - Step-by-step execution
   - Rich logs with `trigger_logger.info()` / `trigger_logger.error()`
   - Input/output payloads
   - Retry attempts

### Example Run View

```
🚀 Starting Welcome Campaign
  status_filter: Intro-email
  
✅ Welcome Campaign Complete
  total_groups: 3
  total_emails_sent: 45
  
Groups:
  - Group 1: 15 leads, variation welcome_A, 15 emails sent
  - Group 2: 15 leads, variation welcome_B, 15 emails sent
  - Group 3: 15 leads, variation welcome_C, 15 emails sent
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Task fails with "Airtable API error" | Check `AIRTABLE_API_KEY` env var |
| Emails not sending | Verify `SMTP_PASSWORD` is an App Password, not regular password |
| No leads found | Check Airtable status values match filters |
| LLM generation fails | Verify `OPENROUTER_API_KEY` is valid |

---

## Modifying Schedules

Edit `trigger.config.ts` to change when tasks run:

```typescript
schedules: [
  {
    task: "welcome-campaign",
    cron: "0 9 * * *",        // Change to your preferred time
    timezone: "America/New_York", // Change timezone
  },
]
```

**Cron Format**: `min hour day month day_of_week`

**Common Patterns**:
- `"0 14 * * *"` — 9:00 AM EST daily
- `"0 */6 * * *"` — Every 6 hours
- `"0 9 * * 1"` — Mondays at 9 AM
- `"0 9 1 * *"` — 1st of each month at 9 AM

After editing, redeploy:
```bash
trigger deploy
```

---

## Manual Task Triggers

From the dashboard, you can manually trigger any task:

1. Go to **Tasks** → Select a task
2. Click **Trigger** button
3. Provide payload (optional):
   ```json
   {"status_filter": "Intro-email"}
   ```

---

## A/B Test Workflow on Trigger.dev

```
Day 1, 9:00 AM EST
  └── welcome-campaign runs
      ├── Group 1: 15 leads → welcome_A
      ├── Group 2: 15 leads → welcome_B
      └── Group 3: 15 leads → welcome_C

Day 1, 2:00 PM
  └── followup-campaign (if any pending)

Every Hour
  └── check-responses updates metrics
      └── Tracks which groups are responding

Day 8, 9:00 AM EST
  └── welcome-campaign (new leads)
  └── followup-campaign (1-week follow-ups for Day 1 leads)

Monday 8:00 AM
  └── metrics-report generates winner analysis
```

---

## Switching Back to Local/Cron

If needed, you can disable Trigger.dev and return to local cron:

```bash
# In Trigger.dev dashboard, disable the project
# Or locally:
python main.py welcome    # CLI version still works
```

---

## Support

- **Trigger.dev Docs**: [trigger.dev/docs](https://trigger.dev/docs)
- **Trigger.dev Discord**: Community support
- **Task Logs**: Check the dashboard Run details for full execution logs

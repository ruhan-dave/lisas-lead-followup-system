# GitHub Actions Setup Guide

This guide walks you through setting up GitHub Actions for the Lisa Lead Follow-Up System.

## Prerequisites

- GitHub repository with code pushed
- Airtable API credentials
- SMTP email credentials
- OpenRouter API key

## Step 1: Push Code to GitHub

```bash
# Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## Step 2: Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

### Required Secrets

**Airtable Configuration:**
- `AIRTABLE_API_KEY` - Your Airtable API key
- `AIRTABLE_BASE_ID` - Your Airtable base ID
- `AIRTABLE_LEADS_TABLE` - Table name for leads (default: "leads")
- `AIRTABLE_MESSAGES_TABLE` - Table name for AI messages (default: "ai-messages")
- `AIRTABLE_AGENT_ACTIONS_TABLE` - Table name for agent actions/runs (default: "ai-agent-actions")

**OpenRouter Configuration:**
- `OPENROUTER_API_KEY` - Your OpenRouter API key
- `OPENROUTER_MODEL` - Model to use (default: "openai/gpt-4o-mini")

**Email Configuration:**
- `SMTP_USER` - SMTP username (email address)
- `SMTP_PASSWORD` - SMTP password
- `SMTP_SERVER` - SMTP server (e.g., "smtp.gmail.com")
- `SMTP_PORT` - SMTP port (default: 587)

**Email Limits:**
- `EMAIL_DAILY_LIMIT` - Max emails per day (default: 100)
- `EMAIL_MIN_DELAY_SECONDS` - Min delay between emails (default: 5.0)
- `AB_GROUP_SIZE` - Group size for A/B testing (default: 10)

**System Configuration:**
- `LOG_LEVEL` - Logging level (default: "INFO")
- `DRY_RUN` - Set to "true" for testing (no emails sent), "false" for production

## Step 3: Verify Workflows

Your repository has three workflow files:

### 1. Daily Email Batch (`.github/workflows/daily-batch.yml`)
- **Schedule:** 9am, 12pm, 3pm, 6pm EST (14, 17, 20, 23 UTC)
- **Purpose:** Sends 3 emails per batch (1 per A/B group)
- **Total:** 12 emails/day
- **Command:** `python main.py daily-batch --size 3`

### 2. Check Replies (`.github/workflows/check-replies.yml`)
- **Schedule:** Midnight EST (5:00 UTC)
- **Purpose:** Checks IMAP for email replies
- **Command:** `python main.py check-replies`

### 3. Check Responses (`.github/workflows/check-responses.yml`)
- **Schedule:** Hourly (every hour UTC)
- **Purpose:** Checks Airtable for status changes
- **Command:** `python main.py check`

**Note:** If using IMAP for reply detection, you can disable `check-responses.yml` as it's redundant.

## Step 4: Enable Workflows

1. Go to your GitHub repository → Actions tab
2. Click on "Daily Email Batch" workflow
3. Click "Enable workflow" (if not already enabled)
4. Repeat for "Check Replies" and "Check Responses" workflows

## Step 5: Test Workflows

### Test Daily Batch Manually

1. Go to Actions tab → "Daily Email Batch" → "Run workflow"
2. Select branch: `main`
3. Click "Run workflow"
4. Monitor the run logs

### Test Check Replies Manually

1. Go to Actions tab → "Check Replies" → "Run workflow"
2. Select branch: `main`
3. Click "Run workflow"
4. Monitor the run logs

## Step 6: Configure IMAP (Optional but Recommended)

For automatic reply detection, add IMAP secrets:

- `IMAP_SERVER` - IMAP server (e.g., "imap.gmail.com")
- `IMAP_PORT` - IMAP port (default: 993)
- `IMAP_USER` - IMAP username (email address)
- `IMAP_PASSWORD` - IMAP password (use app-specific password for Gmail)

## Step 7: Add Test Leads

Before production runs, add test leads to Airtable:

1. Open your Airtable base
2. Go to the leads table
3. Add leads with:
   - **Name:** Test name
   - **Email:** Your test email
   - **Company:** Test company
   - **Status:** "Intro-email" (for daily batch)

## Step 8: Set DRY_RUN to False for Production

When ready for production:

1. Go to Settings → Secrets and variables → Actions
2. Find `DRY_RUN` secret
3. Change value from "true" to "false"
4. Save

## Step 9: Monitor Workflow Runs

1. Go to Actions tab
2. Check recent workflow runs
3. View logs for any errors
4. Monitor email sending and response tracking

## Troubleshooting

### Workflow Not Running
- Check if workflow is enabled
- Verify secrets are configured
- Check workflow schedule (UTC vs EST)

### Emails Not Sending
- Verify SMTP credentials
- Check `DRY_RUN` is set to "false"
- Check Airtable has leads with correct status
- Check workflow logs for errors

### IMAP Not Working
- Verify IMAP credentials
- Check IMAP server and port
- Use app-specific password for Gmail
- Check workflow logs for connection errors

### Airtable Errors
- Verify API key and base ID
- Check table names match secrets
- Verify lead status values

## Workflow Schedule Reference

| Workflow | EST Time | UTC Time | Command |
|----------|----------|----------|---------|
| Daily Batch 1 | 9:00 AM | 14:00 | `daily-batch --size 3` |
| Daily Batch 2 | 12:00 PM | 17:00 | `daily-batch --size 3` |
| Daily Batch 3 | 3:00 PM | 20:00 | `daily-batch --size 3` |
| Daily Batch 4 | 6:00 PM | 23:00 | `daily-batch --size 3` |
| Check Replies | 12:00 AM | 5:00 | `check-replies` |
| Check Responses | Hourly | Hourly | `check` |

## Dashboard Integration

The dashboard shows recent runs from the agent-actions table:
- Go to http://localhost:5000 (or your deployed URL)
- Click "Runs" tab to see recent workflow runs
- Click "Emails" tab to see sent emails
- Click "Prompts" tab to edit email templates

## Production Checklist

- [ ] All secrets configured
- [ ] Workflows enabled
- [ ] Test leads added to Airtable
- [ ] Daily batch tested manually
- [ ] Check replies tested manually
- [ ] DRY_RUN set to "false"
- [ ] IMAP configured (if using)
- [ ] Email limits reviewed
- [ ] Dashboard accessible
- [ ] Monitoring set up

## Support

For issues:
- Check workflow logs in Actions tab
- Check Airtable for lead status updates
- Check dashboard for recent runs
- Review this guide for common issues

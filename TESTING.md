# Testing Checklist

This system was built based on your requirements but **has not been executed**. Here's how to verify it works:

---

## Phase 1: Configuration Verification (5 min)

### 1. Environment Variables
```bash
# Test .env loads correctly
python -c "from config.settings import AirtableConfig, EmailConfig; print('Airtable:', AirtableConfig.BASE_ID); print('Email:', EmailConfig.SMTP_USER)"
```

**Check:** No errors, values match your actual credentials.

### 2. Airtable Connection
```bash
# Test Airtable read
python -c "from modules.airtable_client import AirtableClient; c = AirtableClient(); leads = c.get_leads_by_status('Intro-email'); print(f'Found {len(leads)} leads')"
```

**Check:** Returns lead count (0 is OK if no leads have that status).

### 3. SMTP Connection (Dry Run)
```bash
# Set DRY_RUN=true in .env first, then:
python -c "from modules.email_sender import EmailSender; s = EmailSender(); print('Email sender initialized:', s.dry_run)"
```

**Check:** No connection errors, dry_run=True shown.

---

## Phase 2: Dry Run Test (10 min)

### Full System Test (No Emails Sent)
```bash
# 1. Set in .env:
DRY_RUN=true
EMAIL_DAILY_LIMIT=20

# 2. Run batch
python main.py daily-batch
```

**Expected Output:**
```
📅 Batch Send
Sending 3 emails (1 per A/B group)
...
[DRY RUN] Would send email to=... 
Batch Results: 3 emails shown in table
```

**What to Check:**
- [ ] No Python errors
- [ ] Airtable shows 3 new records in `ai-messages` table
- [ ] Lead statuses updated to "Pending-1-week"
- [ ] 3 different variations used (A, B, C)

---

## Phase 3: Single Real Email Test (5 min)

### Send One Real Email
```bash
# 1. Add your own email to Airtable with status "Intro-email"
# 2. Set in .env:
DRY_RUN=false
EMAIL_DAILY_LIMIT=1  # Safety: only 1 email

# 3. Run single batch
python main.py daily-batch --size 1
```

**Check:**
- [ ] Email arrives in your inbox (check spam!)
- [ ] Personalization works (your name in email)
- [ ] From address shows "Lisa <lisa@myaddressnumber.com>"
- [ ] Airtable logged the AI-generated message

---

## Phase 4: Full Daily Batch (20 min)

### Run Real 12-Email Day
```bash
# Make sure you have 12+ leads in Airtable with status "Intro-email"
# Set DRY_RUN=false
# Run:
python main.py daily-batch
```

**Check:**
- [ ] 3 emails sent (one per group) - stops at daily limit
- [ ] 2-hour gaps between sends (if watching live)
- [ ] All 3 variations used
- [ ] No SMTP errors

---

## Phase 5: Trigger.dev Deployment (15 min)

### Deploy and Verify
```bash
# 1. Login
trigger login

# 2. Test locally first
trigger dev

# 3. Check daily-batch task appears in dashboard

# 4. Deploy
trigger deploy

# 5. Manually trigger once from dashboard
# 6. Check logs show success
```

---

## Common Issues & Fixes

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| `Airtable API error` | Wrong API key or Base ID | Check `.env` values |
| `Cannot convert string to User` | `ai-message` field is "User" type | Change field type to "Long text" in Airtable |
| `No leads found` | Status doesn't match | Check Airtable Status field values |
| `SMTP auth failed` | Wrong password or App Password needed | Use App Password, not regular password |
| `Gmail security error` | Less secure apps blocked | Enable 2FA, use App Password |
| `LLM generation failed` | Wrong OpenRouter key | Verify API key at openrouter.ai |
| `Module not found` | Dependencies not installed | Run `pip install -r requirements.txt` |
| `Email in spam` | New sender reputation | Mark as "Not spam", warm up gradually |

---

## What I (the AI) Cannot Verify

1. **Your actual credentials** — I don't know if Airtable API key, SMTP password, etc. are correct
2. **Airtable table structure** — I assumed field names, but yours might differ
3. **Email deliverability** — Gmail/Microsoft might block your domain initially
4. **Rate limits** — Your email provider might have different limits than expected
5. **Python environment** — Your local Python setup might have conflicts

---

## Confidence Level

| Component | Confidence | Why |
|-----------|------------|-----|
| Airtable integration | 85% | Uses standard pyairtable library |
| SMTP sending | 80% | Standard Python smtplib, but provider-specific issues possible |
| A/B group logic | 90% | Straightforward round-robin |
| Rate limiting | 85% | Simple time.sleep and counter logic |
| Trigger.dev integration | 70% | Mock wrapper provided, but real SDK behavior untested |
| LLM generation | 80% | Uses OpenAI-compatible API, but model availability varies |

**Overall: The code structure is sound, but you WILL find bugs during testing. That's normal.**

---

## Recommended First Step

```bash
# Right now, test this:
cd lead_followup_system
pip install -r requirements.txt
python -c "from modules.orchestrator import Orchestrator; o = Orchestrator(); print('Import successful')"
```

If that works without errors, you're 50% there.

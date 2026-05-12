"""Warmup sender — keeps 3 spacemail accounts active before June.

Sends 12 generic welcome emails/day to breakintoai@yahoo.com,
rotating through SMTP_USERS (info, lisa, sales) in 4 batches:
  9am   — 3 emails
  12pm  — 3 emails
  3pm   — 3 emails
  6pm   — 3 emails

No LLMs. Static, non-spammy content. Designed for cron or manual run.
Usage: python scripts/warmup_sender.py
"""
import json
import logging
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import EmailConfig, SMTPConfig
from modules.email_sender import EmailSender

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# ─── Config ────────────────────────────────────────────────────────────────

TARGET_EMAIL = "breakintoai@yahoo.com"
SENDERS = SMTPConfig.SMTP_USERS or [SMTPConfig.SMTP_USER]
BATCH_SCHEDULE = [9, 12, 15, 18]  # 9am, 12pm, 3pm, 6pm
EMAILS_PER_BATCH = 3
DAILY_TARGET = len(BATCH_SCHEDULE) * EMAILS_PER_BATCH  # 12

STATE_FILE = Path(__file__).resolve().parent.parent / "logs" / "warmup_state.json"

WELCOME_SUBJECT = "A warm hello from My Address Number"

WELCOME_BODY = """Hi there,

My name is Lisa, and I wanted to personally reach out from My Address Number.

We help homeowners make a lasting first impression with premium address numbers and plaques that are built to last. Everything comes in the box — no extra trips to the hardware store needed.

If you are curious about modern styles or classic designs, I would love to point you in the right direction.

Feel free to reply if anything catches your eye.

Warmly,
Lisa
My Address Number
www.myaddressnumber.com
"""

# ─── State persistence ─────────────────────────────────────────────────────

class WarmupState:
    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"sent_today": 0, "last_date": "", "total_sent": 0, "history": []}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    def reset_if_new_day(self) -> None:
        today = date.today().isoformat()
        if self.data.get("last_date") != today:
            self.data["sent_today"] = 0
            self.data["last_date"] = today
            self.save()
            logger.info("New day — daily counter reset to 0")

    def record_send(self, sender: str, ts: str) -> None:
        self.data["sent_today"] += 1
        self.data["total_sent"] += 1
        self.data.setdefault("history", []).append({
            "to": TARGET_EMAIL,
            "from": sender,
            "ts": ts,
        })
        # Trim history to last 200 entries
        self.data["history"] = self.data["history"][-200:]
        self.save()

    @property
    def sent_today(self) -> int:
        return self.data.get("sent_today", 0)

# ─── Batch logic ───────────────────────────────────────────────────────────

def get_current_batch_index(now: datetime) -> int | None:
    """Return which batch window we are in, or None if outside schedule."""
    for idx, hour in enumerate(BATCH_SCHEDULE):
        if now.hour == hour:
            return idx
    return None


def get_sender_for_slot(batch_idx: int, slot: int) -> str:
    """Rotate through senders deterministically across all daily slots."""
    slot_index = batch_idx * EMAILS_PER_BATCH + slot
    return SENDERS[slot_index % len(SENDERS)]


# ─── Main ──────────────────────────────────────────────────────────────────

def run_warmup() -> int:
    state = WarmupState(STATE_FILE)
    state.reset_if_new_day()

    now = datetime.now(timezone.utc)
    batch_idx = get_current_batch_index(now)

    if batch_idx is None:
        next_hr = next((h for h in BATCH_SCHEDULE if h > now.hour), BATCH_SCHEDULE[0])
        logger.info("Outside send window. Next batch at %02d:00 UTC", next_hr)
        return 0

    if state.sent_today >= DAILY_TARGET:
        logger.info("Daily target of %d already reached. Nothing to send.", DAILY_TARGET)
        return 0

    # Calculate how many emails this batch should send
    target_for_batch = (batch_idx + 1) * EMAILS_PER_BATCH
    to_send = target_for_batch - state.sent_today
    if to_send <= 0:
        logger.info("Batch %d already complete (%d/%d sent).", batch_idx + 1, state.sent_today, DAILY_TARGET)
        return 0

    logger.info(
        "Starting warmup batch %d/%d at %02d:00 UTC — sending %d email(s)",
        batch_idx + 1, len(BATCH_SCHEDULE), BATCH_SCHEDULE[batch_idx], to_send,
    )

    sender = EmailSender(min_delay_seconds=2.0, daily_limit=50)
    sent_count = 0

    for slot in range(to_send):
        from_email = get_sender_for_slot(batch_idx, slot)
        success = sender.send(
            to_email=TARGET_EMAIL,
            subject=WELCOME_SUBJECT,
            body_text=WELCOME_BODY,
            from_address=from_email,
        )
        if success:
            ts = datetime.now(timezone.utc).isoformat()
            state.record_send(from_email, ts)
            sent_count += 1
            logger.info("Warmup email %d/%d sent from %s", state.sent_today, DAILY_TARGET, from_email)
        else:
            logger.warning("Failed to send warmup email from %s", from_email)

        if slot < to_send - 1:
            time.sleep(2)

    logger.info("Warmup batch complete: %d sent today (%d/%d)", sent_count, state.sent_today, DAILY_TARGET)
    return sent_count


if __name__ == "__main__":
    run_warmup()

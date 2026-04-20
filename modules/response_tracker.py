"""
Response tracking module.

Checks for replies from leads and calculates per-group metrics.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.airtable_client import AirtableClient
from modules.imap_monitor import IMAPMonitor

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent / "logs" / "tracking_state.json"


class ResponseTracker:
    """Tracks responses per A/B test group and persists state to disk."""

    def __init__(self, airtable: AirtableClient):
        self.airtable = airtable
        self.state: dict[str, Any] = self._load_state()
        self.imap_monitor = IMAPMonitor()

    # ─── Persistence ──────────────────────────────────────────────────

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
        return {"groups": {}, "sent_emails": {}}

    def _save_state(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2, default=str)

    # ─── Recording ────────────────────────────────────────────────────

    def record_email_sent(
        self,
        lead_email: str,
        group_number: int,
        email_type: str,
        airtable_msg_record_id: str,
    ) -> None:
        """Record that an email was sent to a lead."""
        key = str(group_number)
        if key not in self.state["groups"]:
            self.state["groups"][key] = {
                "emails_sent": 0,
                "responses": 0,
                "response_times_sec": [],
            }
        self.state["groups"][key]["emails_sent"] += 1

        self.state["sent_emails"][lead_email] = {
            "group": group_number,
            "type": email_type,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "airtable_record_id": airtable_msg_record_id,
            "responded": False,
        }
        self._save_state()

    def record_response(self, lead_email: str) -> None:
        """Record that a lead has responded."""
        entry = self.state["sent_emails"].get(lead_email)
        if not entry or entry.get("responded"):
            return

        entry["responded"] = True
        entry["responded_at"] = datetime.now(timezone.utc).isoformat()

        sent_at = datetime.fromisoformat(entry["sent_at"])
        responded_at = datetime.fromisoformat(entry["responded_at"])
        response_time = (responded_at - sent_at).total_seconds()
        entry["response_time_sec"] = response_time

        key = str(entry["group"])
        self.state["groups"][key]["responses"] += 1
        self.state["groups"][key]["response_times_sec"].append(response_time)

        # Update response rate on the Airtable message record
        grp = self.state["groups"][key]
        rate = (grp["responses"] / grp["emails_sent"]) * 100 if grp["emails_sent"] else 0
        self.airtable.update_message_response_rate(entry["airtable_record_id"], rate)

        # CRITICAL: Update lead status to "Responded" in Airtable
        lead_id = entry.get("lead_id")
        if lead_id:
            self.airtable.update_lead_status(lead_id, "Responded")
            logger.info("Updated lead %s status to 'Responded'", lead_id)

        self._save_state()
        logger.info(
            "Recorded response from %s (group %s, time=%.0fs)",
            lead_email, key, response_time,
        )

    # ─── Reporting ────────────────────────────────────────────────────

    def get_group_metrics(self, group_number: int) -> dict:
        """Get metrics for a specific group."""
        key = str(group_number)
        grp = self.state["groups"].get(key, {
            "emails_sent": 0, "responses": 0, "response_times_sec": []
        })
        sent = grp["emails_sent"]
        resp = grp["responses"]
        times = grp["response_times_sec"]
        return {
            "group": group_number,
            "emails_sent": sent,
            "responses": resp,
            "response_rate": round((resp / sent) * 100, 2) if sent else 0.0,
            "avg_response_time_hours": (
                round(sum(times) / len(times) / 3600, 2) if times else 0.0
            ),
        }

    def get_all_metrics(self) -> list[dict]:
        """Get metrics for all groups."""
        return [
            self.get_group_metrics(int(k))
            for k in sorted(self.state["groups"].keys(), key=int)
        ]

    def get_response_rate_for_group(self, group_number: int) -> float:
        """Return current response rate (0-100) for a group."""
        m = self.get_group_metrics(group_number)
        return m["response_rate"]

    def check_replies(self) -> int:
        """
        Check IMAP inbox for replies to sent emails and record them.

        Returns:
            Number of new replies detected.
        """
        if not self.imap_monitor.enabled:
            logger.info("IMAP not configured, skipping reply check")
            return 0

        # Build list of sent emails
        sent_emails = []
        for lead_email, entry in self.state["sent_emails"].items():
            if not entry.get("responded"):
                sent_emails.append({
                    "email": lead_email,
                    "sent_at": entry["sent_at"],
                    "group": entry["group"],
                    "airtable_record_id": entry["airtable_record_id"],
                })

        if not sent_emails:
            logger.info("No pending emails to check for replies")
            return 0

        # Check IMAP for replies
        replies = self.imap_monitor.check_for_replies(sent_emails)
        new_replies_count = 0

        for reply in replies:
            lead_email = reply["sender_email"]
            if lead_email in self.state["sent_emails"]:
                entry = self.state["sent_emails"][lead_email]
                if not entry.get("responded"):
                    self.record_response(lead_email)
                    new_replies_count += 1
                    logger.info("Auto-recorded reply from %s via IMAP", lead_email)

        return new_replies_count

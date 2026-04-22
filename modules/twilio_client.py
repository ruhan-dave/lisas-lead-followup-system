"""Twilio SMS notification module for alerting Lisa about lead replies."""
import logging

from twilio.rest import Client

from config.settings import TwilioConfig

logger = logging.getLogger(__name__)


class TwilioClient:
    """Sends SMS notifications to Lisa when leads reply."""

    def __init__(self):
        self.enabled = all([
            TwilioConfig.ACCOUNT_SID,
            TwilioConfig.AUTH_TOKEN,
            TwilioConfig.FROM_NUMBER,
            TwilioConfig.TO_NUMBER,
        ])
        if not self.enabled:
            logger.warning("Twilio not configured. SMS notifications disabled.")
            return

        self.client = Client(TwilioConfig.ACCOUNT_SID, TwilioConfig.AUTH_TOKEN)
        self.from_number = TwilioConfig.FROM_NUMBER
        self.to_number = TwilioConfig.TO_NUMBER

    def send_reply_notification(
        self,
        lead_name: str,
        lead_email: str,
        intent_type: str,
        intent_detail: str,
        draft_preview: str = "",
    ) -> bool:
        """Send SMS to Lisa when a lead replies.

        Args:
            lead_name: Name of the lead who replied
            lead_email: Email of the lead
            intent_type: 'question' or 'interest'
            intent_detail: Specific intent (e.g., 'pricing inquiry')
            draft_preview: Short preview of the AI draft reply

        Returns:
            bool: True if SMS sent successfully
        """
        if not self.enabled:
            return False

        emoji = "❓" if intent_type == "question" else "🔥"
        action = "Draft reply ready" if intent_type == "question" else "Hot lead - auto-followup sent"

        body = (
            f"{emoji} Lead Reply: {lead_name} <{lead_email}>\n"
            f"Intent: {intent_detail}\n"
            f"{action}\n"
        )
        if draft_preview:
            preview = draft_preview[:80] + "..." if len(draft_preview) > 80 else draft_preview
            body += f"Preview: {preview}\n"
        body += "Check dashboard for full details."

        try:
            message = self.client.messages.create(
                body=body,
                from_=self.from_number,
                to=self.to_number,
            )
            logger.info("SMS sent to %s: %s", self.to_number, message.sid)
            return True
        except Exception as e:
            logger.error("Failed to send SMS: %s", e)
            return False

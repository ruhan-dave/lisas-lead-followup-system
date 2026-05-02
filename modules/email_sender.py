"""
Email sending module via SMTP with rate limiting and warming support.

Supports both real sending and dry-run mode for testing.
Includes rate limiting to prevent blacklisting and maintain sender reputation.
"""
import logging
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import EmailConfig, SMTPConfig, SystemConfig

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends emails via SMTP with rate limiting to protect sender reputation."""

    def __init__(self, min_delay_seconds: float = None, daily_limit: int = None):
        """
        Initialize email sender with rate limiting.
        
        Args:
            min_delay_seconds: Minimum seconds between emails (uses EMAIL_MIN_DELAY_SECONDS env var or 5s)
            daily_limit: Maximum emails per day (uses EMAIL_DAILY_LIMIT env var or 100)
        """
        self.host = SMTPConfig.SMTP_HOST
        self.port = SMTPConfig.SMTP_PORT
        self.user = SMTPConfig.SMTP_USER
        self.password = SMTPConfig.SMTP_PASSWORD
        self.from_name = EmailConfig.FROM_NAME
        self.from_address = EmailConfig.FROM_ADDRESS
        self.dry_run = SystemConfig.DRY_RUN
        
        # Rate limiting settings from config or defaults
        self.min_delay = min_delay_seconds or EmailConfig.MIN_DELAY_SECONDS
        self.daily_limit = daily_limit or EmailConfig.DAILY_LIMIT
        self._last_send_time: datetime | None = None
        self._emails_today = 0
        self._today = datetime.now().date()

    def _check_rate_limit(self) -> bool:
        """Check if sending is allowed based on rate limits."""
        now = datetime.now()
        
        # Reset daily counter if it's a new day
        if now.date() != self._today:
            self._today = now.date()
            self._emails_today = 0
            logger.info("Daily email counter reset for %s", self._today)
        
        # Check daily limit
        if self._emails_today >= self.daily_limit:
            logger.warning(
                "Daily email limit reached (%d/%d). Skipping send to protect reputation.",
                self._emails_today, self.daily_limit
            )
            return False
        
        # Enforce minimum delay between emails
        if self._last_send_time:
            elapsed = (now - self._last_send_time).total_seconds()
            if elapsed < self.min_delay:
                sleep_time = self.min_delay - elapsed
                logger.info("Rate limiting: sleeping %.1fs between emails", sleep_time)
                time.sleep(sleep_time)
        
        return True

    def _record_send(self):
        """Record that an email was sent."""
        self._last_send_time = datetime.now()
        self._emails_today += 1
        logger.debug("Email count today: %d/%d", self._emails_today, self.daily_limit)

    def send(self, to_email: str, subject: str, body_text: str, from_address: str = None) -> bool:
        """
        Send a single email with rate limiting.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_text: Plain text body
            from_address: Optional override for sender email (defaults to config)

        Returns True on success, False on failure.
        In dry-run mode, logs the email but does not actually send.
        Respects daily limits and inter-email delays to protect sender reputation.
        """
        # Check rate limits first
        if not self._check_rate_limit():
            return False
        
        sender = from_address or self.from_address
        
        if self.dry_run:
            self._record_send()
            logger.info(
                "[DRY RUN] Would send email from=%s to=%s subject='%s' body_len=%d",
                sender, to_email, subject, len(body_text),
            )
            return True

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.from_name} <{sender}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Plain text part
        msg.attach(MIMEText(body_text, "plain"))

        # HTML part — wrap plain text in styled HTML
        html_body = (
            '<html><body style="font-family: Arial, sans-serif; '
            'line-height: 1.6; color: #333;">'
            + body_text.replace("\n", "<br>")
            + "</body></html>"
        )
        msg.attach(MIMEText(html_body, "html"))

        try:
            # Port 465 uses SSL, port 587 uses STARTTLS
            if self.port == 465:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=10)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=10)
                server.ehlo()
                server.starttls()
                server.ehlo()

            server.login(self.user, self.password)
            server.send_message(msg)
            server.quit()
            self._record_send()
            logger.info(
                "Email sent successfully to %s (count: %d/%d)",
                to_email, self._emails_today, self.daily_limit
            )
            return True
        except Exception as e:
            logger.error("Failed to send email to %s: %s", to_email, e)
            return False

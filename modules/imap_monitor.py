"""
IMAP email reply detection module.

Monitors an IMAP inbox for replies to sent emails and updates response tracking.
"""
import email
import imaplib
import logging
import re
from datetime import datetime, timedelta
from email.header import decode_header
from typing import Optional

from config.settings import SMTPConfig

logger = logging.getLogger(__name__)


def decode_email_header(header: str) -> str:
    """Decode email header from encoded format."""
    if not header:
        return ""
    decoded_list = decode_header(header)
    decoded_str = ""
    for content, encoding in decoded_list:
        if isinstance(content, bytes):
            decoded_str += content.decode(encoding or "utf-8", errors="ignore")
        else:
            decoded_str += content
    return decoded_str


def get_email_body(email_message) -> str:
    """Extract plain text body from an email message."""
    body = ""
    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="ignore")
                        break
                except Exception:
                    continue
    else:
        try:
            payload = email_message.get_payload(decode=True)
            if payload:
                charset = email_message.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="ignore")
        except Exception:
            pass
    return body.strip()


class IMAPMonitor:
    """Monitors IMAP inbox for email replies."""

    def __init__(self):
        self.imap_server = getattr(SMTPConfig, "IMAP_SERVER", None)
        self.imap_port = getattr(SMTPConfig, "IMAP_PORT", 993)
        self.imap_user = getattr(SMTPConfig, "SMTP_USER", None)
        self.imap_password = getattr(SMTPConfig, "SMTP_PASSWORD", None)

        if not all([self.imap_server, self.imap_user, self.imap_password]):
            logger.warning("IMAP credentials not configured. Reply detection disabled.")
            self.enabled = False
        else:
            self.enabled = True

    def connect(self) -> Optional[imaplib.IMAP4_SSL]:
        """Connect to IMAP server."""
        if not self.enabled:
            return None

        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.imap_user, self.imap_password)
            mail.select("INBOX")
            logger.info("Connected to IMAP server")
            return mail
        except Exception as e:
            logger.error("Failed to connect to IMAP server: %s", e)
            return None

    def check_for_replies(self, sent_emails: list[dict]) -> list[dict]:
        """
        Check inbox for replies to sent emails.

        Args:
            sent_emails: List of sent email dicts with 'email' and 'sent_at' keys

        Returns:
            List of reply dicts with 'sender_email', 'original_recipient', 'reply_time', 'message_id'
        """
        if not self.enabled:
            logger.warning("IMAP not configured, skipping reply detection")
            return []

        mail = self.connect()
        if not mail:
            return []

        replies = []

        try:
            # Search for recent emails (last 7 days)
            since_date = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
            mail.search(None, f'(SINCE "{since_date}")')
            _, message_ids = mail.search(None, f'(SINCE "{since_date}")')

            if not message_ids[0]:
                logger.info("No recent emails found in inbox")
                return []

            for msg_id in message_ids[0].split():
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)

                # Get sender email
                from_header = decode_email_header(email_message.get("From", ""))
                sender_match = re.search(r'<([^>]+)>', from_header)
                sender_email = sender_match.group(1) if sender_match else from_header

                # Check if this is a reply to any sent email
                in_reply_to = email_message.get("In-Reply-To", "")
                references = email_message.get("References", "")
                subject = decode_email_header(email_message.get("Subject", ""))

                # Extract email body for AI processing
                body = get_email_body(email_message)

                # Check if sender matches any of our sent email recipients
                for sent in sent_emails:
                    if sender_email == sent.get("email"):
                        reply_time = email_message.get("Date", "")
                        replies.append({
                            "sender_email": sender_email,
                            "original_recipient": sent.get("email"),
                            "reply_time": reply_time,
                            "message_id": email_message.get("Message-ID", ""),
                            "subject": subject,
                            "body": body,
                        })
                        logger.info("Found reply from %s (original: %s)", sender_email, sent.get("email"))
                        break

        except Exception as e:
            logger.error("Error checking for replies: %s", e)
        finally:
            try:
                mail.close()
                mail.logout()
            except:
                pass

        return replies

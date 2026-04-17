"""
Centralized configuration loaded from environment variables.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class AirtableConfig:
    API_KEY: str = os.getenv("AIRTABLE_API_KEY", "")
    BASE_ID: str = os.getenv("AIRTABLE_BASE_ID", "")
    LEADS_TABLE: str = os.getenv("AIRTABLE_LEADS_TABLE", "leads")
    MESSAGES_TABLE: str = os.getenv("AIRTABLE_MESSAGES_TABLE", "ai-messages")
    AGENT_ACTIONS_TABLE: str = os.getenv("AIRTABLE_AGENT_ACTIONS_TABLE", "ai-agent-actions")
    BASE_URL: str = os.getenv("AIRTABLE_BASE_URL", f"https://airtable.com/{os.getenv('AIRTABLE_BASE_ID', '')}")
    LEADS_URL: str = os.getenv("AIRTABLE_LEADS_URL", "")
    MESSAGES_URL: str = os.getenv("AIRTABLE_MESSAGES_URL", "")
    AGENT_ACTIONS_URL: str = os.getenv("AIRTABLE_AGENT_ACTIONS_URL", "")


class LLMConfig:
    API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    BASE_URL: str = "https://openrouter.ai/api/v1"


class SMTPConfig:
    SMTP_SERVER = os.getenv("SMTP_SERVER")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    EMAIL_FROM = os.getenv("EMAIL_FROM")
    # IMAP configuration for reply detection
    IMAP_SERVER = os.getenv("IMAP_SERVER")
    IMAP_PORT = int(os.getenv("IMAP_PORT", 993))


class EmailConfig:
    FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "Lisa")
    FROM_ADDRESS: str = os.getenv("EMAIL_FROM_ADDRESS", "")
    # Rate limiting for sender reputation protection
    MIN_DELAY_SECONDS: float = float(os.getenv("EMAIL_MIN_DELAY_SECONDS", "5.0"))
    DAILY_LIMIT: int = int(os.getenv("EMAIL_DAILY_LIMIT", "100"))


class ABTestConfig:
    GROUP_SIZE: int = int(os.getenv("AB_GROUP_SIZE", "10"))


class SystemConfig:
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"
    LOG_DIR: Path = Path(__file__).resolve().parent.parent / "logs"

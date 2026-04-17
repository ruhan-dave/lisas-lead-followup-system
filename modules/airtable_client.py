"""
Airtable integration module.

Handles:
- Reading leads from the 'leads' table
- Logging AI-generated messages to the 'ai-messages' table
- Updating lead statuses
"""
import logging
from datetime import datetime, timezone
from typing import Any

from pyairtable import Api, Table

from config.settings import AirtableConfig

logger = logging.getLogger(__name__)


class AirtableClient:
    """Wrapper around pyairtable for the lead follow-up system."""

    def __init__(self):
        if not AirtableConfig.API_KEY:
            raise ValueError("AIRTABLE_API_KEY is not set. Check your .env file.")
        self.api = Api(AirtableConfig.API_KEY)
        self._leads_table: Table = self.api.table(
            AirtableConfig.BASE_ID, AirtableConfig.LEADS_TABLE
        )
        self._messages_table: Table = self.api.table(
            AirtableConfig.BASE_ID, AirtableConfig.MESSAGES_TABLE
        )
        self._agent_actions_table: Table = self.api.table(
            AirtableConfig.BASE_ID, AirtableConfig.AGENT_ACTIONS_TABLE
        )
        # Try to use ai-agent-actions table for run tracking
        self._runs_table = self._agent_actions_table

    # ------------------------------------------------------------------ reads
    def get_all_leads(self) -> list[dict[str, Any]]:
        """Fetch every record from the leads table."""
        records = self._leads_table.all()
        logger.info("Fetched %d leads from Airtable", len(records))
        return records

    def get_leads_by_status(self, status: str) -> list[dict[str, Any]]:
        """Fetch leads filtered by a specific Status value."""
        formula = f"{{Status}} = '{status}'"
        records = self._leads_table.all(formula=formula)
        logger.info(
            "Fetched %d leads with status '%s'", len(records), status
        )
        return records

    # --------------------------------------------------------------- updates
    def update_lead_status(self, record_id: str, new_status: str) -> None:
        """Update the Status field of a lead record."""
        self._leads_table.update(record_id, {"Status": new_status})
        logger.info("Updated lead %s → status '%s'", record_id, new_status)

    def update_lead_fields(self, record_id: str, fields: dict) -> None:
        """Update arbitrary fields on a lead record."""
        self._leads_table.update(record_id, fields)
        logger.info("Updated lead %s with fields %s", record_id, list(fields.keys()))

    # ---------------------------------------- ai-messages logging (immediate)
    def log_ai_message(
        self,
        msg_type: str,
        notes: str,
        ai_message: str,
        response_rate: float,
        group: int,
    ) -> dict:
        """
        Immediately log an AI-generated message to the 'ai-messages' table.

        IMPORTANT: The 'ai-message' field must be "Long text" type in Airtable.
        If your field is "User" type, either:
        1. Change field type to "Long text" in Airtable, OR
        2. Change field name below to one that accepts text (e.g., "Notes")

        Parameters
        ----------
        msg_type : str
            e.g. "welcome-email", "followup-week1"  (primary field)
        notes : str
            Free-text notes about this message / context
        ai_message : str
            The full AI-generated message content
        response_rate : float
            Current response rate for the group (0-100 percentage)
        group : int
            The A/B test group number this message belongs to
        """
        # NOTE: If your 'ai-message' field is type "User", change this to "Notes"
        # or create a new "Long text" field named "ai-message" in Airtable
        ai_message_field = "ai-message"
        
        # ai_message should be PLAIN TEXT ONLY - the generated email content
        # NOT a JSON object with system/user prompts
        fields = {
            "type": msg_type,
            "Notes": notes,
            ai_message_field: ai_message,  # Plain text email body only
            "response-rate": response_rate / 100,  # Convert 0-100 to 0-1 for Airtable percent
            "group": group,
        }
        
        try:
            record = self._messages_table.create(fields)
            logger.info(
                "Logged AI message to Airtable: type=%s, group=%d, record=%s",
                msg_type,
                group,
                record["id"],
            )
            return record
        except Exception as e:
            # If 'ai-message' field fails (e.g., wrong type), try storing in Notes instead
            if "ai-message" in str(e) or "Unknown field" in str(e):
                logger.warning("Failed to write to 'ai-message' field, storing in Notes instead")
                fields["Notes"] = f"{notes}\n\n--- AI MESSAGE ---\n{ai_message}"
                del fields[ai_message_field]
                record = self._messages_table.create(fields)
                logger.info("Logged AI message to Notes field instead: record=%s", record["id"])
                return record
            raise

    # ------------------------------------------------ response-rate helpers
    def update_message_response_rate(
        self, record_id: str, response_rate: float
    ) -> None:
        """Update the response-rate on an existing ai-messages record."""
        # Convert 0-100 percentage to 0-1 decimal for Airtable percent field
        self._messages_table.update(record_id, {"response-rate": response_rate / 100})
        logger.debug(
            "Updated response-rate for message %s → %.1f%%", record_id, response_rate
        )

    def get_messages_by_group(self, group: int) -> list[dict[str, Any]]:
        """Fetch all logged messages for a given A/B test group."""
        formula = f"{{group}} = {group}"
        return self._messages_table.all(formula=formula)

    # ------------------------------------------------ agent actions logging
    def log_agent_action(
        self,
        tools: str,
        user_query: str,
        ai_message: str,
        total_tokens: int,
    ) -> dict:
        """
        Log an AI agent action to the 'ai-agent-actions' table.

        Parameters
        ----------
        tools : str
            Description of tools used (e.g., "welcome-email", "reminder-email", "reply")
        user_query : str
            The user query/prompt sent to the AI (including lead name, context)
        ai_message : str
            The AI-generated response (email content)
        total_tokens : int
            Total tokens used in the LLM call
        """
        from datetime import datetime, timezone
        
        record = self._agent_actions_table.create(
            {
                "Timestamp": datetime.now(timezone.utc).isoformat(),
                "Tools": tools,
                "User Query": user_query,
                "AI Message": ai_message,
                "Total Tokens": total_tokens,
            }
        )
        logger.info(
            "Logged agent action: tools=%s, tokens=%d, record=%s",
            tools,
            total_tokens,
            record["id"],
        )
        return record

    # ------------------------------------------------ run tracking for dashboard
    def log_run(
        self,
        action: str,
        status: str = "STARTED",
        triggered_by: str = "SYSTEM",
        metadata: dict = None,
    ) -> dict:
        """
        Log a run to the runs table for dashboard visibility.

        Parameters
        ----------
        action : str
            The action being run (e.g., "daily-batch", "check", "metrics")
        status : str
            Status of the run (STARTED, RUNNING, COMPLETED, FAILED)
        triggered_by : str
            Who triggered the run (SYSTEM, MANUAL, GITHUB_ACTIONS)
        metadata : dict
            Additional metadata about the run
        """
        fields = {
            "Timestamp": datetime.now(timezone.utc).isoformat(),
            "Tools": action,
            "User Query": f"Triggered by: {triggered_by}",
            "AI Message": f"Status: {status}",
            "Total Tokens": 0,
        }
        if metadata:
            fields["User Query"] += f" | Metadata: {metadata}"

        try:
            record = self._runs_table.create(fields)
            logger.info(
                "Logged run: action=%s, status=%s, triggered_by=%s, record=%s",
                action,
                status,
                triggered_by,
                record["id"],
            )
            return record
        except Exception as e:
            logger.warning(f"Failed to log run: {e}")
            return {"id": ""}

    def get_recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent runs for the dashboard."""
        try:
            records = self._runs_table.all()[:limit]
            runs = []
            for record in records:
                runs.append({
                    "id": record["id"],
                    "action": record.get("fields", {}).get("Tools", ""),
                    "timestamp": record.get("fields", {}).get("Timestamp", ""),
                    "status": record.get("fields", {}).get("AI Message", "").replace("Status: ", ""),
                    "triggered_by": record.get("fields", {}).get("User Query", "").split("Triggered by: ")[-1] if "Triggered by:" in record.get("fields", {}).get("User Query", "") else "SYSTEM",
                })
            return runs
        except Exception as e:
            logger.error(f"Failed to get recent runs: {e}")
            return []

    def update_run_status(self, record_id: str, status: str) -> None:
        """Update the status of a run."""
        try:
            self._runs_table.update(record_id, {"AI Message": f"Status: {status}"})
            logger.info("Updated run %s → status '%s'", record_id, status)
        except Exception as e:
            logger.warning(f"Failed to update run status: {e}")

    def get_run_details(self, run_id: str) -> dict[str, Any]:
        """Get details of a specific run."""
        try:
            record = self._runs_table.get(run_id)
            return {
                "id": record["id"],
                "action": record.get("fields", {}).get("Tools", ""),
                "timestamp": record.get("fields", {}).get("Timestamp", ""),
                "status": record.get("fields", {}).get("AI Message", "").replace("Status: ", ""),
                "triggered_by": record.get("fields", {}).get("User Query", "").split("Triggered by: ")[-1] if "Triggered by:" in record.get("fields", {}).get("User Query", "") else "SYSTEM",
            }
        except Exception as e:
            logger.error(f"Failed to get run details: {e}")
            return {}

    def get_run_messages(self, run_id: str) -> list[dict[str, Any]]:
        """Get messages associated with a run (using timestamp matching)."""
        try:
            run = self._runs_table.get(run_id)
            run_timestamp = run.get("fields", {}).get("Timestamp", "")
            # Get messages from around the same time
            all_messages = self._messages_table.all()
            related_messages = []
            for msg in all_messages:
                msg_time = msg.get("createdTime", "")
                if run_timestamp in msg_time or msg_time in run_timestamp:
                    related_messages.append(msg)
            return related_messages
        except Exception as e:
            logger.error(f"Failed to get run messages: {e}")
            return []

    def get_recent_messages(self, limit: int = 30) -> list[dict[str, Any]]:
        """Get recent AI-generated messages for the emails page."""
        try:
            records = self._messages_table.all()[:limit]
            messages = []
            for record in records:
                fields = record.get("fields", {})
                messages.append({
                    "id": record["id"],
                    "type": fields.get("type", ""),
                    "notes": fields.get("Notes", ""),
                    "content": fields.get("ai-message", fields.get("Notes", "")),
                    "response_rate": fields.get("response-rate", 0),
                    "group": fields.get("group", ""),
                    "created_time": record.get("createdTime", ""),
                })
            return messages
        except Exception as e:
            logger.error(f"Failed to get recent messages: {e}")
            return []

    def get_message_by_id(self, message_id: str) -> dict[str, Any]:
        """Get a specific message by ID."""
        try:
            record = self._messages_table.get(message_id)
            fields = record.get("fields", {})
            return {
                "id": record["id"],
                "type": fields.get("type", ""),
                "notes": fields.get("Notes", ""),
                "content": fields.get("ai-message", fields.get("Notes", "")),
                "response_rate": fields.get("response-rate", 0),
                "group": fields.get("group", ""),
                "created_time": record.get("createdTime", ""),
            }
        except Exception as e:
            logger.error(f"Failed to get message by ID: {e}")
            return {}

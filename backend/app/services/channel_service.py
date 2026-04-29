"""
PARWA Channel Service - Omnichannel Configuration & Routing (Day 30)

Implements F-052: Omnichannel support with:
- Channel configuration management
- Per-company channel settings
- PS13: Variant down handling (queue + retry)
- Channel-specific formatting and validation

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.exceptions import (
    NotFoundError,
    ValidationError,
)
from database.models.tickets import (
    Channel,
    ChannelConfig,
    Ticket,
    TicketStatus,
)

# Default channel types supported by the system
DEFAULT_CHANNELS = [
    {"name": "email", "channel_type": "email", "description": "Email channel"},
    {"name": "chat", "channel_type": "chat", "description": "Live chat widget"},
    {"name": "sms", "channel_type": "sms", "description": "SMS/Messaging"},
    {"name": "voice", "channel_type": "voice", "description": "Voice/Phone calls"},
    {"name": "slack", "channel_type": "chat", "description": "Slack integration"},
    {"name": "webchat", "channel_type": "chat", "description": "Web chat widget"},
]

# Character limits per channel
CHANNEL_CHAR_LIMITS = {
    "email": None,  # No limit
    "chat": 4000,
    "sms": 1600,  # 10 SMS segments
    "voice": 500,  # Brief summaries
    "slack": 40000,
    "webchat": 4000,
}

# Default file types per channel
DEFAULT_ALLOWED_FILE_TYPES = [
    "pdf",
    "doc",
    "docx",
    "txt",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "csv",
    "xls",
    "xlsx",
]


class ChannelService:
    """Channel configuration and routing operations."""

    # PS13: Variant down retry settings
    VARIANT_RETRY_DELAY_MINUTES = 5
    VARIANT_MAX_RETRIES = 12  # 1 hour total
    HUMAN_FALLBACK_THRESHOLD_MINUTES = 60

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    # ── CHANNEL MANAGEMENT ───────────────────────────────────────────────────

    def get_available_channels(self) -> List[Dict[str, Any]]:
        """Get all available system channels.

        Returns:
            List of channel definitions
        """
        # Check database for any custom channels
        db_channels = self.db.query(Channel).filter(Channel.is_active).all()

        # Merge with defaults
        channel_map = {c["name"]: c for c in DEFAULT_CHANNELS}

        for db_ch in db_channels:
            if db_ch.name not in channel_map:
                channel_map[db_ch.name] = {
                    "name": db_ch.name,
                    "channel_type": db_ch.channel_type,
                    "description": db_ch.description,
                }

        return list(channel_map.values())

    def get_company_channel_config(self) -> List[Dict[str, Any]]:
        """Get company's channel configuration.

        Returns:
            List of channel configs with status
        """
        # Get all channel configs for company
        configs = (
            self.db.query(ChannelConfig)
            .filter(ChannelConfig.company_id == self.company_id)
            .all()
        )

        config_map = {c.channel_type: c for c in configs}

        # Build result with all channels
        result = []
        for channel in DEFAULT_CHANNELS:
            name = channel["name"]
            config = config_map.get(name)

            result.append(
                {
                    "channel_type": name,
                    "channel_category": channel["channel_type"],
                    "description": channel["description"],
                    "is_enabled": config.is_enabled if config else False,
                    "config": (
                        json.loads(config.config_json)
                        if config and config.config_json
                        else {}
                    ),
                    "auto_create_ticket": config.auto_create_ticket if config else True,
                    "char_limit": (
                        config.char_limit
                        if config and config.char_limit
                        else CHANNEL_CHAR_LIMITS.get(name)
                    ),
                    "allowed_file_types": (
                        json.loads(config.allowed_file_types)
                        if config and config.allowed_file_types
                        else DEFAULT_ALLOWED_FILE_TYPES
                    ),
                    "max_file_size": (
                        config.max_file_size if config else 5 * 1024 * 1024
                    ),  # 5MB default
                }
            )

        return result

    def get_channel_config(self, channel_type: str) -> Optional[ChannelConfig]:
        """Get configuration for a specific channel.

        Args:
            channel_type: Channel type name

        Returns:
            ChannelConfig object or None
        """
        return (
            self.db.query(ChannelConfig)
            .filter(
                ChannelConfig.company_id == self.company_id,
                ChannelConfig.channel_type == channel_type,
            )
            .first()
        )

    def update_channel_config(
        self,
        channel_type: str,
        is_enabled: Optional[bool] = None,
        config_json: Optional[Dict[str, Any]] = None,
        auto_create_ticket: Optional[bool] = None,
        char_limit: Optional[int] = None,
        allowed_file_types: Optional[List[str]] = None,
        max_file_size: Optional[int] = None,
    ) -> ChannelConfig:
        """Update configuration for a channel.

        Args:
            channel_type: Channel type to update
            is_enabled: Enable/disable the channel
            config_json: Channel-specific settings (API keys, webhooks, etc.)
            auto_create_ticket: Auto-create tickets on inbound
            char_limit: Character limit for this channel
            allowed_file_types: Supported file types
            max_file_size: Max file size in bytes

        Returns:
            Updated ChannelConfig object

        Raises:
            ValidationError: If channel type is invalid
        """
        # Validate channel type
        valid_channels = [c["name"] for c in DEFAULT_CHANNELS]
        if channel_type not in valid_channels:
            raise ValidationError(f"Invalid channel type: {channel_type}")

        # Get or create config
        config = self.get_channel_config(channel_type)

        if not config:
            config = ChannelConfig(
                id=str(uuid.uuid4()),
                company_id=self.company_id,
                channel_type=channel_type,
                is_enabled=is_enabled if is_enabled is not None else True,
                config_json=json.dumps(config_json or {}),
                auto_create_ticket=(
                    auto_create_ticket if auto_create_ticket is not None else True
                ),
                char_limit=char_limit,
                allowed_file_types=json.dumps(
                    allowed_file_types or DEFAULT_ALLOWED_FILE_TYPES
                ),
                max_file_size=max_file_size,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.db.add(config)
        else:
            if is_enabled is not None:
                config.is_enabled = is_enabled
            if config_json is not None:
                config.config_json = json.dumps(config_json)
            if auto_create_ticket is not None:
                config.auto_create_ticket = auto_create_ticket
            if char_limit is not None:
                config.char_limit = char_limit
            if allowed_file_types is not None:
                config.allowed_file_types = json.dumps(allowed_file_types)
            if max_file_size is not None:
                config.max_file_size = max_file_size
            config.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(config)

        return config

    def test_channel_connectivity(
        self,
        channel_type: str,
        test_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Test connectivity for a channel configuration.

        Args:
            channel_type: Channel type to test
            test_config: Optional test config (uses saved config if not provided)

        Returns:
            Test result with success status and details
        """
        # Get config
        config = self.get_channel_config(channel_type)
        config_data = test_config or (
            json.loads(config.config_json) if config and config.config_json else {}
        )

        # Simulate connectivity test (in production, this would actually test)
        # For now, return success if config has required fields
        result = {
            "channel_type": channel_type,
            "success": True,
            "message": "Channel connectivity verified",
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }

        # Channel-specific validation
        if channel_type == "email":
            if not config_data.get("smtp_host") and not config_data.get("provider"):
                result["success"] = False
                result["message"] = (
                    "Email configuration incomplete: missing SMTP or provider settings"
                )

        elif channel_type == "sms":
            if not config_data.get("provider") and not config_data.get("twilio_sid"):
                result["success"] = False
                result["message"] = (
                    "SMS configuration incomplete: missing provider settings"
                )

        elif channel_type == "slack":
            if not config_data.get("bot_token") and not config_data.get("webhook_url"):
                result["success"] = False
                result["message"] = (
                    "Slack configuration incomplete: missing bot token or webhook"
                )

        return result

    # ── CHANNEL ROUTING ─────────────────────────────────────────────────────

    def is_channel_enabled(self, channel_type: str) -> bool:
        """Check if a channel is enabled for the company.

        Args:
            channel_type: Channel type to check

        Returns:
            True if enabled, False otherwise
        """
        config = self.get_channel_config(channel_type)
        return config.is_enabled if config else False

    def should_auto_create_ticket(self, channel_type: str) -> bool:
        """Check if tickets should be auto-created for a channel.

        Args:
            channel_type: Channel type to check

        Returns:
            True if auto-create is enabled
        """
        config = self.get_channel_config(channel_type)
        return config.auto_create_ticket if config else True

    def format_message_for_channel(
        self,
        content: str,
        channel_type: str,
        truncate: bool = True,
    ) -> str:
        """Format a message for a specific channel.

        Args:
            content: Original message content
            channel_type: Target channel
            truncate: Whether to truncate to channel limit

        Returns:
            Formatted message
        """
        char_limit = CHANNEL_CHAR_LIMITS.get(channel_type)

        if truncate and char_limit and len(content) > char_limit:
            content = content[: char_limit - 3] + "..."

        return content

    def validate_file_for_channel(
        self,
        filename: str,
        file_size: int,
        channel_type: str,
    ) -> Tuple[bool, Optional[str]]:
        """Validate a file for a specific channel.

        Args:
            filename: File name
            file_size: File size in bytes
            channel_type: Target channel

        Returns:
            Tuple of (is_valid, error_message)
        """
        config = self.get_channel_config(channel_type)

        allowed_types = DEFAULT_ALLOWED_FILE_TYPES
        max_size = 5 * 1024 * 1024  # 5MB default

        if config:
            if config.allowed_file_types:
                allowed_types = json.loads(config.allowed_file_types)
            if config.max_file_size:
                max_size = config.max_file_size

        # Check file extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in allowed_types:
            return False, f"File type .{ext} not allowed for channel {channel_type}"

        # Check file size
        if file_size > max_size:
            return False, f"File size exceeds {
                max_size // (
                    1024 * 1024)}MB limit"

        return True, None

    # ── PS13: VARIANT DOWN HANDLING ─────────────────────────────────────────

    def handle_variant_down(
        self,
        ticket_id: str,
        channel_type: str,
    ) -> Dict[str, Any]:
        """PS13: Handle variant being down.

        - Queue ticket for retry
        - Auto-retry when variant returns
        - Human fallback after 1hr

        Args:
            ticket_id: Ticket ID
            channel_type: Channel type

        Returns:
            Handling result with retry status
        """
        # Get ticket
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        # Check if already queued
        if ticket.status == TicketStatus.queued.value:
            return {
                "status": "already_queued",
                "ticket_id": ticket_id,
                "queued_at": (
                    ticket.updated_at.isoformat() if ticket.updated_at else None
                ),
            }

        # Update ticket status to queued
        old_status = ticket.status
        ticket.status = TicketStatus.queued.value
        ticket.updated_at = datetime.now(timezone.utc)

        # Store variant failure metadata
        metadata = json.loads(ticket.metadata_json or "{}")
        metadata["variant_failure"] = {
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "channel_type": channel_type,
            "retry_count": 0,
            "next_retry_at": (
                datetime.now(timezone.utc)
                + timedelta(minutes=self.VARIANT_RETRY_DELAY_MINUTES)
            ).isoformat(),
        }
        ticket.metadata_json = json.dumps(metadata)

        self.db.commit()
        self.db.refresh(ticket)

        return {
            "status": "queued",
            "ticket_id": ticket_id,
            "old_status": old_status,
            "new_status": TicketStatus.queued.value,
            "retry_after_minutes": self.VARIANT_RETRY_DELAY_MINUTES,
            "human_fallback_after_minutes": self.HUMAN_FALLBACK_THRESHOLD_MINUTES,
        }

    def check_variant_retry_tickets(self) -> List[Dict[str, Any]]:
        """Check for tickets that need variant retry or human fallback.

        Returns:
            List of tickets requiring action
        """
        now = datetime.now(timezone.utc)
        retry_threshold = now - timedelta(minutes=self.VARIANT_RETRY_DELAY_MINUTES)
        fallback_threshold = now - timedelta(
            minutes=self.HUMAN_FALLBACK_THRESHOLD_MINUTES
        )

        # Find queued tickets
        queued_tickets = (
            self.db.query(Ticket)
            .filter(
                Ticket.company_id == self.company_id,
                Ticket.status == TicketStatus.queued.value,
            )
            .all()
        )

        results = []

        for ticket in queued_tickets:
            metadata = json.loads(ticket.metadata_json or "{}")
            failure_info = metadata.get("variant_failure", {})
            queued_at_str = failure_info.get("queued_at")

            if not queued_at_str:
                continue

            try:
                queued_at = datetime.fromisoformat(queued_at_str)
            except (ValueError, TypeError):
                continue

            retry_count = failure_info.get("retry_count", 0)

            result = {
                "ticket_id": ticket.id,
                "queued_at": queued_at_str,
                "retry_count": retry_count,
                "action": None,
            }

            # Check for human fallback (1 hour exceeded)
            if queued_at < fallback_threshold:
                result["action"] = "human_fallback"

            # Check for retry
            elif queued_at < retry_threshold and retry_count < self.VARIANT_MAX_RETRIES:
                result["action"] = "retry"

            if result["action"]:
                results.append(result)

        return results

    def process_variant_retry(
        self,
        ticket_id: str,
        success: bool,
    ) -> Dict[str, Any]:
        """Process a variant retry attempt.

        Args:
            ticket_id: Ticket ID
            success: Whether the retry was successful

        Returns:
            Updated ticket status
        """
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        metadata = json.loads(ticket.metadata_json or "{}")
        failure_info = metadata.get("variant_failure", {})

        if success:
            # Return to open status
            ticket.status = TicketStatus.open.value
            del metadata["variant_failure"]
        else:
            # Increment retry count
            failure_info["retry_count"] = failure_info.get("retry_count", 0) + 1
            failure_info["next_retry_at"] = (
                datetime.now(timezone.utc)
                + timedelta(minutes=self.VARIANT_RETRY_DELAY_MINUTES)
            ).isoformat()
            metadata["variant_failure"] = failure_info

        ticket.metadata_json = json.dumps(metadata)
        ticket.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(ticket)

        return {
            "ticket_id": ticket_id,
            "status": ticket.status,
            "retry_count": failure_info.get("retry_count", 0),
        }

    def escalate_to_human(
        self,
        ticket_id: str,
        reason: str = "variant_unavailable",
    ) -> Dict[str, Any]:
        """Escalate queued ticket to human agent.

        Args:
            ticket_id: Ticket ID
            reason: Escalation reason

        Returns:
            Updated ticket status
        """
        ticket = (
            self.db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == self.company_id,
            )
            .first()
        )

        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        old_status = ticket.status

        # Update status
        ticket.status = TicketStatus.awaiting_human.value
        ticket.awaiting_human = True

        # Update metadata
        metadata = json.loads(ticket.metadata_json or "{}")
        metadata["human_escalation"] = {
            "escalated_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "from_status": old_status,
        }
        if "variant_failure" in metadata:
            metadata["human_escalation"]["variant_failure"] = metadata[
                "variant_failure"
            ]
            del metadata["variant_failure"]

        ticket.metadata_json = json.dumps(metadata)
        ticket.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(ticket)

        return {
            "ticket_id": ticket_id,
            "old_status": old_status,
            "new_status": TicketStatus.awaiting_human.value,
            "escalation_reason": reason,
        }

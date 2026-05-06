"""
PARWA MCP Notification Server.

Provides notification operations via MCP including:
- Single user notifications
- Bulk notifications
- User preference management

All operations are tool-based and inherit from BaseMCPServer.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import asyncio

from mcp_servers.base_server import BaseMCPServer
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class NotificationChannel:
    """Supported notification channels."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationServer(BaseMCPServer):
    """
    MCP Server for notification operations.

    Provides tools for sending notifications and managing
    user notification preferences across multiple channels.

    Tools:
        - send_notification: Send notification to a single user
        - send_bulk_notifications: Send notifications to multiple users
        - get_notification_preferences: Get user notification settings
        - update_preferences: Update user notification preferences
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize Notification Server.

        Args:
            config: Optional server configuration
        """
        super().__init__(name="notification_server", config=config)
        self._notification_store: Dict[str, Dict[str, Any]] = {}
        self._preferences_store: Dict[str, Dict[str, Any]] = {}

    def _register_tools(self) -> None:
        """Register all notification tools."""
        self.register_tool(
            name="send_notification",
            description="Send a notification to a specific user",
            parameters_schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "message": {"type": "string", "description": "Notification message"},
                    "channel": {
                        "type": "string",
                        "description": "Notification channel",
                        "enum": ["email", "sms", "push", "in_app", "webhook"]
                    },
                    "title": {"type": "string", "description": "Notification title"},
                    "priority": {
                        "type": "string",
                        "description": "Priority level",
                        "enum": ["low", "normal", "high", "urgent"],
                        "default": "normal"
                    },
                    "metadata": {"type": "object", "description": "Additional metadata"}
                },
                "required": ["user_id", "message", "channel"]
            },
            handler=self._handle_send_notification
        )

        self.register_tool(
            name="send_bulk_notifications",
            description="Send notifications to multiple users",
            parameters_schema={
                "type": "object",
                "properties": {
                    "user_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of user IDs"
                    },
                    "message": {"type": "string", "description": "Notification message"},
                    "channel": {
                        "type": "string",
                        "description": "Notification channel",
                        "enum": ["email", "sms", "push", "in_app", "webhook"]
                    },
                    "title": {"type": "string", "description": "Notification title"}
                },
                "required": ["user_ids", "message", "channel"]
            },
            handler=self._handle_send_bulk_notifications
        )

        self.register_tool(
            name="get_notification_preferences",
            description="Get notification preferences for a user",
            parameters_schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"}
                },
                "required": ["user_id"]
            },
            handler=self._handle_get_preferences
        )

        self.register_tool(
            name="update_preferences",
            description="Update notification preferences for a user",
            parameters_schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "preferences": {
                        "type": "object",
                        "description": "Preference settings"
                    }
                },
                "required": ["user_id", "preferences"]
            },
            handler=self._handle_update_preferences
        )

    async def _on_start(self) -> None:
        """Initialize notification server resources."""
        logger.info({
            "event": "notification_server_starting",
            "server": self._name,
        })
        # Simulate async initialization
        await asyncio.sleep(0.01)

    async def _handle_send_notification(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle send_notification tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with notification_id and status
        """
        user_id = params["user_id"]
        message = params["message"]
        channel = params["channel"]
        title = params.get("title", "Notification")
        priority = params.get("priority", "normal")
        metadata = params.get("metadata", {})

        # Check user preferences
        prefs = self._preferences_store.get(user_id, self._default_preferences())
        if not prefs.get("channels", {}).get(channel, True):
            return {
                "status": "skipped",
                "reason": f"User has disabled {channel} notifications",
                "user_id": user_id
            }

        # Generate notification ID
        notification_id = f"notif_{uuid.uuid4().hex[:12]}"

        # Store notification
        notification = {
            "notification_id": notification_id,
            "user_id": user_id,
            "message": message,
            "title": title,
            "channel": channel,
            "priority": priority,
            "status": "sent",
            "sent_at": datetime.now().isoformat(),
            "metadata": metadata
        }
        self._notification_store[notification_id] = notification

        logger.info({
            "event": "notification_sent",
            "notification_id": notification_id,
            "user_id": user_id,
            "channel": channel,
            "priority": priority
        })

        return {
            "status": "success",
            "notification_id": notification_id,
            "channel": channel,
            "sent_at": notification["sent_at"]
        }

    async def _handle_send_bulk_notifications(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle send_bulk_notifications tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with summary of sent notifications
        """
        user_ids = params["user_ids"]
        message = params["message"]
        channel = params["channel"]
        title = params.get("title", "Notification")

        results = {
            "sent": 0,
            "skipped": 0,
            "failed": 0,
            "notification_ids": []
        }

        for user_id in user_ids:
            try:
                result = await self._handle_send_notification({
                    "user_id": user_id,
                    "message": message,
                    "channel": channel,
                    "title": title
                })

                if result.get("status") == "success":
                    results["sent"] += 1
                    results["notification_ids"].append(result["notification_id"])
                elif result.get("status") == "skipped":
                    results["skipped"] += 1
                else:
                    results["failed"] += 1

            except Exception as e:
                results["failed"] += 1
                logger.error({
                    "event": "bulk_notification_failed",
                    "user_id": user_id,
                    "error": str(e)
                })

        logger.info({
            "event": "bulk_notifications_sent",
            "total_users": len(user_ids),
            "sent": results["sent"],
            "skipped": results["skipped"],
            "failed": results["failed"]
        })

        return {
            "status": "success",
            "summary": results
        }

    async def _handle_get_preferences(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle get_notification_preferences tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with user preferences
        """
        user_id = params["user_id"]

        prefs = self._preferences_store.get(
            user_id, self._default_preferences()
        )

        return {
            "status": "success",
            "user_id": user_id,
            "preferences": prefs
        }

    async def _handle_update_preferences(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle update_preferences tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with updated preferences
        """
        user_id = params["user_id"]
        new_prefs = params["preferences"]

        # Get existing preferences or defaults
        current_prefs = self._preferences_store.get(
            user_id, self._default_preferences()
        )

        # Merge preferences
        current_prefs.update(new_prefs)
        current_prefs["updated_at"] = datetime.now().isoformat()

        self._preferences_store[user_id] = current_prefs

        logger.info({
            "event": "preferences_updated",
            "user_id": user_id
        })

        return {
            "status": "success",
            "user_id": user_id,
            "preferences": current_prefs
        }

    def _default_preferences(self) -> Dict[str, Any]:
        """Get default notification preferences."""
        return {
            "channels": {
                "email": True,
                "sms": True,
                "push": True,
                "in_app": True,
                "webhook": False
            },
            "quiet_hours": {
                "enabled": False,
                "start": "22:00",
                "end": "08:00"
            },
            "frequency": {
                "digest": False,
                "digest_interval_hours": 24
            },
            "created_at": datetime.now().isoformat()
        }


def get_notification_server() -> NotificationServer:
    """
    Get a NotificationServer instance.

    Returns:
        NotificationServer instance
    """
    return NotificationServer()

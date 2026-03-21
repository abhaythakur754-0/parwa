"""
PARWA Chat MCP Server.

MCP server for chat/messaging operations.
Provides conversation management and message handling.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import hashlib
import uuid

from mcp_servers.base_server import BaseMCPServer
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ChatServer(BaseMCPServer):
    """
    MCP Server for chat operations.

    Tools provided:
    - send_message: Send a message to a conversation
    - create_conversation: Create a new conversation
    - get_conversation_history: Get message history
    - mark_read: Mark messages as read

    This server manages chat conversations for customer support interactions.
    """

    def __init__(self, config: Dict[str, Any] = None) -> None:
        """
        Initialize Chat MCP Server.

        Args:
            config: Server configuration
        """
        # In-memory storage for conversations (in production, use database)
        self._conversations: Dict[str, Dict[str, Any]] = {}
        self._messages: Dict[str, List[Dict[str, Any]]] = {}
        super().__init__(name="chat_server", config=config)

    def _register_tools(self) -> None:
        """Register all chat tools."""
        # Tool: send_message
        self.register_tool(
            name="send_message",
            description=(
                "Send a message to an existing conversation. "
                "Messages are timestamped and assigned a unique ID."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "ID of the conversation",
                    },
                    "message": {
                        "type": "string",
                        "description": "Message content to send",
                    },
                    "sender": {
                        "type": "string",
                        "description": "Sender identifier (user_id or 'agent')",
                    },
                },
                "required": ["conversation_id", "message"],
            },
            handler=self._handle_send_message,
        )

        # Tool: create_conversation
        self.register_tool(
            name="create_conversation",
            description=(
                "Create a new conversation with participants. "
                "Returns conversation ID for subsequent messaging."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "participants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of participant user IDs",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Optional conversation metadata",
                    },
                },
                "required": ["participants"],
            },
            handler=self._handle_create_conversation,
        )

        # Tool: get_conversation_history
        self.register_tool(
            name="get_conversation_history",
            description=(
                "Get message history for a conversation. "
                "Returns messages in chronological order."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "ID of the conversation",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of messages to return",
                        "default": 50,
                    },
                    "before": {
                        "type": "string",
                        "description": "Return messages before this message ID (pagination)",
                    },
                },
                "required": ["conversation_id"],
            },
            handler=self._handle_get_conversation_history,
        )

        # Tool: mark_read
        self.register_tool(
            name="mark_read",
            description=(
                "Mark messages as read for a participant. "
                "Updates read receipts in the conversation."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "conversation_id": {
                        "type": "string",
                        "description": "ID of the conversation",
                    },
                    "message_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of message IDs to mark as read",
                    },
                    "participant": {
                        "type": "string",
                        "description": "Participant marking messages as read",
                    },
                },
                "required": ["conversation_id", "message_ids"],
            },
            handler=self._handle_mark_read,
        )

    async def _handle_send_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle send_message tool call.

        Args:
            params: Tool parameters with conversation_id, message, sender

        Returns:
            Message send result with message_id and timestamp
        """
        conversation_id = params.get("conversation_id")
        message = params.get("message")
        sender = params.get("sender", "agent")

        # Validate conversation exists
        if conversation_id not in self._conversations:
            return {
                "status": "error",
                "message": f"Conversation {conversation_id} not found",
            }

        # Validate message content
        if not message or not message.strip():
            return {"status": "error", "message": "Message content cannot be empty"}

        try:
            # Generate message ID
            message_id = hashlib.md5(
                f"{conversation_id}{message}{datetime.now(timezone.utc).isoformat()}".encode()
            ).hexdigest()[:16]

            # Create message record
            message_record = {
                "id": message_id,
                "conversation_id": conversation_id,
                "content": message,
                "sender": sender,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "read_by": [],
                "status": "sent",
            }

            # Store message
            if conversation_id not in self._messages:
                self._messages[conversation_id] = []
            self._messages[conversation_id].append(message_record)

            # Update conversation last activity
            self._conversations[conversation_id]["last_message_at"] = message_record["timestamp"]
            self._conversations[conversation_id]["message_count"] = (
                self._conversations[conversation_id].get("message_count", 0) + 1
            )

            logger.info({
                "event": "chat_message_sent",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "sender": sender,
            })

            return {
                "message_id": message_id,
                "conversation_id": conversation_id,
                "status": "sent",
                "timestamp": message_record["timestamp"],
            }

        except Exception as e:
            logger.error({
                "event": "chat_message_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to send message"}

    async def _handle_create_conversation(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle create_conversation tool call.

        Args:
            params: Tool parameters with participants, metadata (optional)

        Returns:
            Created conversation details with conversation_id
        """
        participants = params.get("participants", [])
        metadata = params.get("metadata", {})

        # Validate participants
        if not participants or len(participants) < 1:
            return {"status": "error", "message": "At least one participant required"}

        if len(participants) > 50:
            return {"status": "error", "message": "Maximum 50 participants per conversation"}

        try:
            # Generate conversation ID
            conversation_id = str(uuid.uuid4())

            # Create conversation record
            now = datetime.now(timezone.utc)
            conversation_record = {
                "id": conversation_id,
                "participants": participants,
                "created_at": now.isoformat(),
                "last_message_at": None,
                "message_count": 0,
                "metadata": metadata,
                "status": "active",
            }

            # Store conversation
            self._conversations[conversation_id] = conversation_record
            self._messages[conversation_id] = []

            logger.info({
                "event": "conversation_created",
                "conversation_id": conversation_id,
                "participants": participants,
            })

            return {
                "conversation_id": conversation_id,
                "participants": participants,
                "created_at": conversation_record["created_at"],
                "status": "active",
            }

        except Exception as e:
            logger.error({
                "event": "conversation_create_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to create conversation"}

    async def _handle_get_conversation_history(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle get_conversation_history tool call.

        Args:
            params: Tool parameters with conversation_id, limit, before (optional)

        Returns:
            List of messages in chronological order
        """
        conversation_id = params.get("conversation_id")
        limit = params.get("limit", 50)
        before = params.get("before")

        # Validate conversation exists
        if conversation_id not in self._conversations:
            return {
                "status": "error",
                "message": f"Conversation {conversation_id} not found",
            }

        # Validate limit
        if limit < 1 or limit > 200:
            limit = 50

        try:
            messages = self._messages.get(conversation_id, [])

            # Filter by before cursor (pagination)
            if before:
                before_index = next(
                    (i for i, m in enumerate(messages) if m["id"] == before),
                    len(messages)
                )
                messages = messages[:before_index]

            # Apply limit
            messages = messages[-limit:] if len(messages) > limit else messages

            # Format response
            formatted_messages = [
                {
                    "id": msg["id"],
                    "content": msg["content"],
                    "sender": msg["sender"],
                    "timestamp": msg["timestamp"],
                    "status": msg["status"],
                }
                for msg in messages
            ]

            return {
                "conversation_id": conversation_id,
                "messages": formatted_messages,
                "count": len(formatted_messages),
                "has_more": len(self._messages.get(conversation_id, [])) > limit,
            }

        except Exception as e:
            logger.error({
                "event": "conversation_history_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to get conversation history"}

    async def _handle_mark_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle mark_read tool call.

        Args:
            params: Tool parameters with conversation_id, message_ids, participant

        Returns:
            Updated read status
        """
        conversation_id = params.get("conversation_id")
        message_ids = params.get("message_ids", [])
        participant = params.get("participant", "unknown")

        # Validate conversation exists
        if conversation_id not in self._conversations:
            return {
                "status": "error",
                "message": f"Conversation {conversation_id} not found",
            }

        try:
            messages = self._messages.get(conversation_id, [])
            updated_count = 0

            for msg in messages:
                if msg["id"] in message_ids:
                    if participant not in msg["read_by"]:
                        msg["read_by"].append(participant)
                        updated_count += 1

            logger.info({
                "event": "messages_marked_read",
                "conversation_id": conversation_id,
                "message_count": updated_count,
                "participant": participant,
            })

            return {
                "conversation_id": conversation_id,
                "marked_count": updated_count,
                "participant": participant,
                "status": "success",
            }

        except Exception as e:
            logger.error({
                "event": "mark_read_error",
                "error": str(e),
            })
            return {"status": "error", "message": "Failed to mark messages as read"}

"""
Chat Widget Service — Week 13 Day 4 (F-122: Live Chat Widget)

Handles the complete chat widget lifecycle:
1. Session creation with HMAC-signed visitor tokens
2. Message sending/receiving with Socket.io events (BC-005)
3. Typing indicators and read receipts
4. Session assignment and closing
5. CSAT rating collection
6. Widget configuration management
7. Canned response CRUD
8. Integration with ticket system

Building Codes:
- BC-001: Multi-tenant isolation (all queries scoped to company_id)
- BC-005: Real-time events via Socket.io for new messages
- BC-006: Rate limiting (max messages per session/hour)
- BC-011: Visitor sessions use HMAC-signed tokens, not JWT
- BC-012: Structured error responses
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from database.models.chat_widget import (
    CannedResponse,
    ChatWidgetConfig,
    ChatWidgetMessage,
    ChatWidgetSession,
)

logger = logging.getLogger("parwa.chat_widget")

# ── Constants ─────────────────────────────────────────────────

# BC-006: Max visitor messages per session per hour
MAX_VISITOR_MESSAGES_PER_HOUR = 60

# BC-006: Max total messages per session
MAX_MESSAGES_PER_SESSION = 500

# Session expiry (closed if no activity for 24 hours)
SESSION_EXPIRY_MINUTES = 1440

# Default widget colors
DEFAULT_PRIMARY_COLOR = "#4F46E5"

# Pre-chat form required fields check
REQUIRED_FIELD_MAP = {
    "name": "require_visitor_name",
    "email": "require_visitor_email",
}


class ChatWidgetService:
    """Service for managing chat widget sessions and messages.

    All methods are scoped to company_id (BC-001) and emit
    Socket.io events for real-time updates (BC-005).
    """

    def __init__(self, db: Session, company_id: Optional[str] = None):
        self.db = db
        self.company_id = company_id

    # ═══════════════════════════════════════════════════════════
    # Session Management
    # ═══════════════════════════════════════════════════════════

    def create_session(
        self,
        company_id: str,
        visitor_data: dict,
    ) -> dict:
        """Create a new chat widget session.

        Generates an HMAC-signed visitor token for authentication
        without requiring user login (BC-011).

        Args:
            company_id: Tenant company ID.
            visitor_data: Dict with visitor metadata (name, email,
                phone, ip, user_agent, page_url, referrer, department).

        Returns:
            Dict with session data and visitor_token.
        """
        # Check if widget is enabled for this company
        config = self._get_widget_config(company_id)
        if config and not config.is_enabled:
            return {
                "status": "error",
                "error": "Chat widget is currently disabled",
            }

        # Validate required fields from widget config
        if config:
            missing = self._check_required_visitor_fields(config, visitor_data)
            if missing:
                return {
                    "status": "error",
                    "error": f"Missing required visitor fields: {', '.join(missing)}",
                }

        session = ChatWidgetSession(
            company_id=company_id,
            visitor_name=visitor_data.get("visitor_name"),
            visitor_email=visitor_data.get("visitor_email"),
            visitor_phone=visitor_data.get("visitor_phone"),
            visitor_ip=visitor_data.get("visitor_ip"),
            visitor_user_agent=visitor_data.get("visitor_user_agent"),
            visitor_page_url=visitor_data.get("visitor_page_url"),
            visitor_referrer=visitor_data.get("visitor_referrer"),
            department=visitor_data.get("department"),
            status="active",
            message_count=0,
            visitor_message_count=0,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # Generate HMAC-signed visitor token (BC-011)
        visitor_token = self._generate_visitor_token(session.id, company_id)

        logger.info(
            "chat_session_created",
            extra={
                "company_id": company_id,
                "session_id": session.id,
            },
        )

        return {
            "status": "created",
            "session": session.to_dict(),
            "visitor_token": visitor_token,
        }

    def get_session(
        self,
        session_id: str,
        company_id: str,
    ) -> Optional[ChatWidgetSession]:
        """Get a chat session with company_id isolation (BC-001).

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.

        Returns:
            ChatWidgetSession if found, None otherwise.
        """
        return (
            self.db.query(ChatWidgetSession)
            .filter(
                ChatWidgetSession.id == session_id,
                ChatWidgetSession.company_id == company_id,
            )
            .first()
        )

    def list_sessions(
        self,
        company_id: str,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        assigned_agent_id: Optional[str] = None,
    ) -> dict:
        """List chat sessions with pagination and filters.

        Args:
            company_id: Tenant company ID.
            page: Page number (1-based).
            page_size: Items per page.
            status: Filter by session status.
            assigned_agent_id: Filter by assigned agent.

        Returns:
            Dict with items, total, page, page_size, total_pages.
        """
        query = self.db.query(ChatWidgetSession).filter(
            ChatWidgetSession.company_id == company_id,
        )

        if status:
            query = query.filter(ChatWidgetSession.status == status)
        if assigned_agent_id:
            query = query.filter(
                ChatWidgetSession.assigned_agent_id == assigned_agent_id,
            )

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size

        items = (
            query.order_by(ChatWidgetSession.updated_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return {
            "items": [item.to_dict() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def assign_session(
        self,
        session_id: str,
        company_id: str,
        agent_id: str,
    ) -> dict:
        """Assign an agent to a chat session.

        Emits a Socket.io event for real-time notification (BC-005).

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.
            agent_id: Agent user ID to assign.

        Returns:
            Dict with updated session data.
        """
        session = self.get_session(session_id, company_id)
        if not session:
            return {"status": "error", "error": "Session not found"}

        session.assigned_agent_id = agent_id
        session.status = "assigned"
        self.db.commit()
        self.db.refresh(session)

        # Emit assignment event via Socket.io (BC-005)
        self._emit_chat_event(
            company_id=company_id,
            session_id=session_id,
            event_type="chat:session_assigned",
            payload={
                "session_id": session_id,
                "agent_id": agent_id,
            },
        )

        # Create system message about assignment
        self._create_system_message(
            session_id=session_id,
            company_id=company_id,
            event_name="session_assigned",
            event_data={"agent_id": agent_id},
        )

        logger.info(
            "chat_session_assigned",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "agent_id": agent_id,
            },
        )

        return {"status": "assigned", "session": session.to_dict()}

    def close_session(
        self,
        session_id: str,
        company_id: str,
        closer_id: Optional[str] = None,
    ) -> dict:
        """Close a chat session.

        Sets status to 'closed' and records the close timestamp.

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.
            closer_id: ID of the user who closed the session.

        Returns:
            Dict with updated session data.
        """
        session = self.get_session(session_id, company_id)
        if not session:
            return {"status": "error", "error": "Session not found"}

        session.status = "closed"
        session.closed_at = datetime.utcnow()

        # Create system message
        self._create_system_message(
            session_id=session_id,
            company_id=company_id,
            event_name="session_closed",
            event_data={"closed_by": closer_id},
        )

        self.db.commit()
        self.db.refresh(session)

        # Emit close event via Socket.io (BC-005)
        self._emit_chat_event(
            company_id=company_id,
            session_id=session_id,
            event_type="chat:session_closed",
            payload={"session_id": session_id},
        )

        logger.info(
            "chat_session_closed",
            extra={
                "company_id": company_id,
                "session_id": session_id,
            },
        )

        return {"status": "closed", "session": session.to_dict()}

    def expire_stale_sessions(self, company_id: str) -> int:
        """Expire sessions that have been inactive beyond the threshold.

        Sessions with no messages for SESSION_EXPIRY_MINUTES are
        automatically closed.

        Args:
            company_id: Tenant company ID.

        Returns:
            Number of sessions expired.
        """
        threshold = datetime.utcnow() - timedelta(minutes=SESSION_EXPIRY_MINUTES)

        stale = (
            self.db.query(ChatWidgetSession)
            .filter(
                ChatWidgetSession.company_id == company_id,
                ChatWidgetSession.status == "active",
                ChatWidgetSession.last_message_at < threshold,
            )
            .all()
        )

        count = 0
        for session in stale:
            session.status = "expired"
            session.closed_at = datetime.utcnow()
            count += 1

        if count > 0:
            self.db.commit()

        logger.info(
            "chat_sessions_expired",
            extra={"company_id": company_id, "count": count},
        )

        return count

    # ═══════════════════════════════════════════════════════════
    # Message Management
    # ═══════════════════════════════════════════════════════════

    def send_message(
        self,
        session_id: str,
        company_id: str,
        content: str,
        role: str = "visitor",
        sender_id: Optional[str] = None,
        sender_name: Optional[str] = None,
        message_type: str = "text",
        attachments_json: str = "[]",
        quick_replies_json: str = "[]",
        event_name: Optional[str] = None,
        event_data_json: str = "{}",
        is_ai_generated: bool = False,
        ai_confidence: Optional[int] = None,
    ) -> dict:
        """Send a message in a chat session.

        Validates rate limits (BC-006), creates the message,
        updates session metrics, and emits Socket.io event (BC-005).

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.
            content: Message text content.
            role: Sender role (visitor, agent, system, bot).
            sender_id: Sender user ID.
            sender_name: Display name.
            message_type: Message type (text, image, file, etc.).
            attachments_json: JSON array of attachments.
            quick_replies_json: JSON array of quick reply options.
            event_name: For system_event type messages.
            event_data_json: JSON data for system events.
            is_ai_generated: Whether message was AI-generated.
            ai_confidence: AI confidence score (0-100).

        Returns:
            Dict with message data and status.
        """
        session = self.get_session(session_id, company_id)
        if not session:
            return {"status": "error", "error": "Session not found"}

        if session.status == "closed":
            return {"status": "error", "error": "Session is closed"}

        # BC-006: Rate limit check for visitor messages
        if role == "visitor":
            rate_error = self._check_visitor_rate_limit(session)
            if rate_error:
                return {"status": "error", "error": rate_error}

        # Create message
        message = ChatWidgetMessage(
            session_id=session_id,
            company_id=company_id,
            sender_id=sender_id,
            sender_name=sender_name,
            role=role,
            content=content,
            message_type=message_type,
            attachments_json=attachments_json,
            quick_replies_json=quick_replies_json,
            event_name=event_name,
            event_data_json=event_data_json,
            is_ai_generated=is_ai_generated,
            ai_confidence=ai_confidence,
            is_read=False,
        )
        self.db.add(message)

        # Update session metrics
        now = datetime.utcnow()
        session.message_count = (session.message_count or 0) + 1
        session.last_message_at = now

        if role == "visitor":
            session.visitor_message_count = (
                session.visitor_message_count or 0
            ) + 1
            if not session.first_message_at:
                session.first_message_at = now

        # Auto-assign if unassigned and first visitor message
        if (
            role == "visitor"
            and not session.assigned_agent_id
            and session.visitor_message_count == 1
        ):
            self._auto_assign_session(session)

        self.db.commit()
        self.db.refresh(message)

        # Emit message event via Socket.io (BC-005)
        self._emit_chat_event(
            company_id=company_id,
            session_id=session_id,
            event_type="chat:message_new",
            payload=message.to_dict(),
        )

        logger.info(
            "chat_message_sent",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "role": role,
                "message_id": message.id,
            },
        )

        return {"status": "sent", "message": message.to_dict()}

    def send_typing_indicator(
        self,
        session_id: str,
        company_id: str,
        user_id: Optional[str],
        role: str,
        is_typing: bool,
    ) -> dict:
        """Emit a typing indicator via Socket.io (BC-005).

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.
            user_id: User ID of the person typing.
            role: Role (visitor or agent).
            is_typing: True if typing started, False if stopped.

        Returns:
            Dict with status.
        """
        session = self.get_session(session_id, company_id)
        if not session:
            return {"status": "error", "error": "Session not found"}

        self._emit_chat_event(
            company_id=company_id,
            session_id=session_id,
            event_type="chat:typing",
            payload={
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "is_typing": is_typing,
            },
        )

        return {"status": "emitted"}

    def mark_messages_read(
        self,
        session_id: str,
        company_id: str,
        reader_id: Optional[str] = None,
    ) -> int:
        """Mark all unread messages in a session as read.

        Emits read receipt via Socket.io (BC-005).

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.
            reader_id: ID of the user reading messages.

        Returns:
            Number of messages marked as read.
        """
        session = self.get_session(session_id, company_id)
        if not session:
            return 0

        unread = (
            self.db.query(ChatWidgetMessage)
            .filter(
                ChatWidgetMessage.session_id == session_id,
                ChatWidgetMessage.company_id == company_id,
                ChatWidgetMessage.is_read == False,  # noqa: E712
                ChatWidgetMessage.role != "system",
            )
            .all()
        )

        now = datetime.utcnow()
        count = 0
        for msg in unread:
            msg.is_read = True
            msg.read_at = now
            count += 1

        if count > 0:
            self.db.commit()

            # Emit read receipt via Socket.io (BC-005)
            self._emit_chat_event(
                company_id=company_id,
                session_id=session_id,
                event_type="chat:messages_read",
                payload={
                    "session_id": session_id,
                    "reader_id": reader_id,
                    "count": count,
                },
            )

        return count

    def get_messages(
        self,
        session_id: str,
        company_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Get messages for a chat session with pagination.

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.
            page: Page number (1-based).
            page_size: Items per page.

        Returns:
            Dict with items, total, page, page_size, total_pages.
        """
        query = self.db.query(ChatWidgetMessage).filter(
            ChatWidgetMessage.session_id == session_id,
            ChatWidgetMessage.company_id == company_id,
        )

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size

        items = (
            query.order_by(ChatWidgetMessage.created_at.asc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return {
            "items": [item.to_dict() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # ═══════════════════════════════════════════════════════════
    # CSAT Rating
    # ═══════════════════════════════════════════════════════════

    def submit_csat_rating(
        self,
        session_id: str,
        company_id: str,
        rating: int,
        comment: Optional[str] = None,
    ) -> dict:
        """Submit a CSAT rating for a closed chat session.

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.
            rating: Rating 1-5.
            comment: Optional feedback comment.

        Returns:
            Dict with status and session data.
        """
        if not 1 <= rating <= 5:
            return {"status": "error", "error": "Rating must be 1-5"}

        session = self.get_session(session_id, company_id)
        if not session:
            return {"status": "error", "error": "Session not found"}

        session.csat_rating = rating
        session.csat_comment = comment
        self.db.commit()
        self.db.refresh(session)

        logger.info(
            "chat_csat_submitted",
            extra={
                "company_id": company_id,
                "session_id": session_id,
                "rating": rating,
            },
        )

        return {"status": "rated", "session": session.to_dict()}

    # ═══════════════════════════════════════════════════════════
    # Widget Configuration
    # ═══════════════════════════════════════════════════════════

    def get_widget_config(
        self,
        company_id: str,
    ) -> Optional[ChatWidgetConfig]:
        """Get widget configuration for a company.

        Args:
            company_id: Tenant company ID.

        Returns:
            ChatWidgetConfig if found, None otherwise.
        """
        return (
            self.db.query(ChatWidgetConfig)
            .filter(ChatWidgetConfig.company_id == company_id)
            .first()
        )

    def get_or_create_widget_config(
        self,
        company_id: str,
    ) -> ChatWidgetConfig:
        """Get existing config or create default.

        Args:
            company_id: Tenant company ID.

        Returns:
            ChatWidgetConfig (existing or newly created).
        """
        config = self.get_widget_config(company_id)
        if config:
            return config

        config = ChatWidgetConfig(
            company_id=company_id,
            widget_title="Chat with us",
            welcome_message="Hi! How can we help you today?",
            placeholder_text="Type your message...",
            primary_color=DEFAULT_PRIMARY_COLOR,
            widget_position="bottom_right",
            is_enabled=True,
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)

        logger.info(
            "widget_config_created",
            extra={"company_id": company_id},
        )

        return config

    def update_widget_config(
        self,
        company_id: str,
        updates: dict,
    ) -> dict:
        """Update widget configuration.

        Args:
            company_id: Tenant company ID.
            updates: Dict of fields to update.

        Returns:
            Dict with status and updated config.
        """
        config = self.get_or_create_widget_config(company_id)

        allowed_fields = [
            "widget_title", "welcome_message", "placeholder_text",
            "primary_color", "widget_position", "is_enabled",
            "auto_greeting_enabled", "auto_greeting_delay_seconds",
            "bot_enabled", "max_file_size_mb", "allowed_file_types",
            "max_queue_size", "queue_message", "business_hours_json",
            "offline_message", "require_visitor_name",
            "require_visitor_email",
        ]

        for field in allowed_fields:
            if field in updates and updates[field] is not None:
                setattr(config, field, updates[field])

        self.db.commit()
        self.db.refresh(config)

        logger.info(
            "widget_config_updated",
            extra={"company_id": company_id},
        )

        return {"status": "updated", "config": config.to_dict()}

    def get_widget_embed_info(
        self,
        company_id: str,
    ) -> dict:
        """Get widget embed information for a company.

        Returns the widget config and embed URL/script tag
        that the company can use to add the chat widget to
        their website.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dict with embed info.
        """
        config = self.get_or_create_widget_config(company_id)
        frontend_url = "https://app.parwa.ai"

        return {
            "company_id": company_id,
            "widget_id": config.id,
            "embed_url": f"{frontend_url}/widget/{company_id}",
            "script_tag": (
                f'<script src="{frontend_url}/widget.js" '
                f'data-company-id="{company_id}" '
                f'data-widget-id="{config.id}"></script>'
            ),
            "config": config.to_dict(),
        }

    # ═══════════════════════════════════════════════════════════
    # Canned Responses
    # ═══════════════════════════════════════════════════════════

    def create_canned_response(
        self,
        company_id: str,
        data: dict,
        created_by: Optional[str] = None,
    ) -> dict:
        """Create a new canned response.

        Args:
            company_id: Tenant company ID.
            data: Dict with title, content, category, shortcut, sort_order.
            created_by: User ID of the creator.

        Returns:
            Dict with status and canned response.
        """
        response = CannedResponse(
            company_id=company_id,
            title=data["title"],
            content=data["content"],
            category=data.get("category", "general"),
            shortcut=data.get("shortcut"),
            sort_order=data.get("sort_order", 0),
            is_active=True,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(response)
        self.db.commit()
        self.db.refresh(response)

        return {"status": "created", "response": response.to_dict()}

    def list_canned_responses(
        self,
        company_id: str,
        category: Optional[str] = None,
        is_active: Optional[bool] = True,
    ) -> list:
        """List canned responses for a company.

        Args:
            company_id: Tenant company ID.
            category: Optional category filter.
            is_active: Filter by active status.

        Returns:
            List of canned response dicts.
        """
        query = self.db.query(CannedResponse).filter(
            CannedResponse.company_id == company_id,
        )

        if category:
            query = query.filter(CannedResponse.category == category)
        if is_active is not None:
            query = query.filter(CannedResponse.is_active == is_active)

        items = (
            query.order_by(CannedResponse.sort_order, CannedResponse.title)
            .all()
        )

        return [item.to_dict() for item in items]

    def update_canned_response(
        self,
        response_id: str,
        company_id: str,
        updates: dict,
        updated_by: Optional[str] = None,
    ) -> dict:
        """Update a canned response.

        Args:
            response_id: Canned response UUID.
            company_id: Tenant company ID.
            updates: Dict of fields to update.
            updated_by: User ID of the updater.

        Returns:
            Dict with status and updated response.
        """
        response = (
            self.db.query(CannedResponse)
            .filter(
                CannedResponse.id == response_id,
                CannedResponse.company_id == company_id,
            )
            .first()
        )
        if not response:
            return {"status": "error", "error": "Canned response not found"}

        allowed_fields = [
            "title", "content", "category", "shortcut",
            "sort_order", "is_active",
        ]
        for field in allowed_fields:
            if field in updates and updates[field] is not None:
                setattr(response, field, updates[field])

        response.updated_by = updated_by
        self.db.commit()
        self.db.refresh(response)

        return {"status": "updated", "response": response.to_dict()}

    def delete_canned_response(
        self,
        response_id: str,
        company_id: str,
    ) -> dict:
        """Delete a canned response.

        Args:
            response_id: Canned response UUID.
            company_id: Tenant company ID.

        Returns:
            Dict with status.
        """
        response = (
            self.db.query(CannedResponse)
            .filter(
                CannedResponse.id == response_id,
                CannedResponse.company_id == company_id,
            )
            .first()
        )
        if not response:
            return {"status": "error", "error": "Canned response not found"}

        self.db.delete(response)
        self.db.commit()

        return {"status": "deleted"}

    # ═══════════════════════════════════════════════════════════
    # Visitor Token (BC-011)
    # ═══════════════════════════════════════════════════════════

    def verify_visitor_token(
        self,
        session_id: str,
        company_id: str,
        token: str,
    ) -> bool:
        """Verify an HMAC-signed visitor token.

        BC-011: Visitor sessions use HMAC-signed tokens, not JWT.

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.
            token: HMAC token to verify.

        Returns:
            True if token is valid, False otherwise.
        """
        expected = self._generate_visitor_token(session_id, company_id)
        return hmac.compare_digest(expected, token)

    def generate_visitor_token(
        self,
        session_id: str,
        company_id: str,
    ) -> str:
        """Generate an HMAC-signed visitor token.

        BC-011: Visitor sessions use HMAC-signed tokens, not JWT.

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.

        Returns:
            HMAC token string.
        """
        return self._generate_visitor_token(session_id, company_id)

    # ═══════════════════════════════════════════════════════════
    # Private Methods
    # ═══════════════════════════════════════════════════════════

    def _generate_visitor_token(
        self,
        session_id: str,
        company_id: str,
    ) -> str:
        """Generate HMAC-SHA256 token for visitor authentication.

        BC-011: Uses HMAC instead of JWT for unauthenticated visitors.
        The token is company-scoped and session-specific.

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.

        Returns:
            Hex-encoded HMAC token.
        """
        secret = self._get_hmac_secret()
        message = f"{session_id}:{company_id}".encode("utf-8")
        return hmac.new(
            secret.encode("utf-8"), message, hashlib.sha256,
        ).hexdigest()

    def _get_hmac_secret(self) -> str:
        """Get the HMAC secret key for visitor token signing.

        Falls back to SECRET_KEY environment variable.

        Returns:
            Secret key string.
        """
        try:
            from app.config import get_settings
            settings = get_settings()
            return settings.SECRET_KEY
        except Exception:
            return "parwa-widget-secret-fallback"

    def _check_visitor_rate_limit(
        self,
        session: ChatWidgetSession,
    ) -> Optional[str]:
        """Check BC-006 rate limit for visitor messages.

        Args:
            session: ChatWidgetSession instance.

        Returns:
            Error message if rate limit exceeded, None otherwise.
        """
        # Check total message limit
        if session.message_count >= MAX_MESSAGES_PER_SESSION:
            return (
                f"BC-006: Session message limit exceeded "
                f"({MAX_MESSAGES_PER_SESSION})"
            )

        # Check hourly rate limit
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_count = (
            self.db.query(func.count(ChatWidgetMessage.id))
            .filter(
                ChatWidgetMessage.session_id == session.id,
                ChatWidgetMessage.role == "visitor",
                ChatWidgetMessage.created_at >= one_hour_ago,
            )
            .scalar()
        ) or 0

        if recent_count >= MAX_VISITOR_MESSAGES_PER_HOUR:
            return (
                f"BC-006: Visitor rate limit exceeded "
                f"({MAX_VISITOR_MESSAGES_PER_HOUR} messages/hour)"
            )

        return None

    def _auto_assign_session(self, session: ChatWidgetSession) -> None:
        """Auto-assign a session to an available agent.

        Uses simple round-robin or load-based assignment.
        Falls back to queuing if no agents are available.

        Args:
            session: ChatWidgetSession to assign.
        """
        try:
            from database.models.core import Agent

            # Find available agents for this company
            available = (
                self.db.query(Agent)
                .filter(
                    Agent.company_id == session.company_id,
                    Agent.is_active == True,  # noqa: E712
                )
                .limit(10)
                .all()
            )

            if available:
                # Simple assignment: pick the agent with fewest active sessions
                agent = self._pick_least_loaded_agent(
                    session.company_id, available,
                )
                if agent:
                    session.assigned_agent_id = agent.id
                    session.status = "assigned"
            else:
                session.status = "queued"
        except Exception as exc:
            logger.warning(
                "chat_auto_assign_failed error=%s",
                str(exc)[:200],
                extra={"session_id": session.id},
            )
            session.status = "queued"

    def _pick_least_loaded_agent(
        self,
        company_id: str,
        agents: list,
    ) -> Optional[Any]:
        """Pick the agent with the fewest active chat sessions.

        Args:
            company_id: Tenant company ID.
            agents: List of Agent model instances.

        Returns:
            Agent with least load, or None.
        """
        best_agent = None
        min_load = float("inf")

        for agent in agents:
            load = (
                self.db.query(func.count(ChatWidgetSession.id))
                .filter(
                    ChatWidgetSession.company_id == company_id,
                    ChatWidgetSession.assigned_agent_id == agent.id,
                    ChatWidgetSession.status.in_(["active", "assigned"]),
                )
                .scalar()
            ) or 0

            if load < min_load:
                min_load = load
                best_agent = agent

        return best_agent

    def _check_required_visitor_fields(
        self,
        config: ChatWidgetConfig,
        visitor_data: dict,
    ) -> list:
        """Check if widget requires visitor fields that are missing.

        Args:
            config: ChatWidgetConfig instance.
            visitor_data: Visitor data dict.

        Returns:
            List of missing field names.
        """
        missing = []
        for field_name, config_key in REQUIRED_FIELD_MAP.items():
            if getattr(config, config_key, False):
                value = visitor_data.get(f"visitor_{field_name}")
                if not value or not value.strip():
                    missing.append(field_name)
        return missing

    def _create_system_message(
        self,
        session_id: str,
        company_id: str,
        event_name: str,
        event_data: dict,
    ) -> ChatWidgetMessage:
        """Create a system event message in a session.

        Args:
            session_id: Session UUID.
            company_id: Tenant company ID.
            event_name: Event name (e.g., session_assigned).
            event_data: Event data dict.

        Returns:
            Created ChatWidgetMessage.
        """
        message = ChatWidgetMessage(
            session_id=session_id,
            company_id=company_id,
            role="system",
            message_type="system_event",
            event_name=event_name,
            event_data_json=json.dumps(event_data),
        )
        self.db.add(message)
        self.db.flush()
        return message

    def _emit_chat_event(
        self,
        company_id: str,
        session_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        """Emit a Socket.io event for real-time updates (BC-005).

        Gracefully handles Socket.io unavailability.

        Args:
            company_id: Tenant company ID.
            session_id: Session UUID.
            event_type: Socket.io event type.
            payload: Event data dict.
        """
        try:
            import asyncio

            from app.core.socketio import emit_to_tenant

            # Schedule async emit in existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    emit_to_tenant(
                        company_id=company_id,
                        event_type=event_type,
                        payload=payload,
                    )
                )
            else:
                loop.run_until_complete(
                    emit_to_tenant(
                        company_id=company_id,
                        event_type=event_type,
                        payload=payload,
                    )
                )
        except Exception as exc:
            # BC-005: Socket.io failure must not break the service
            logger.warning(
                "chat_socketio_emit_failed error=%s",
                str(exc)[:200],
                extra={
                    "company_id": company_id,
                    "session_id": session_id,
                    "event_type": event_type,
                },
            )

    def _get_widget_config(self, company_id: str) -> Optional[ChatWidgetConfig]:
        """Get widget config (private helper)."""
        return (
            self.db.query(ChatWidgetConfig)
            .filter(ChatWidgetConfig.company_id == company_id)
            .first()
        )

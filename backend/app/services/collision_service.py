"""
PARWA Collision Service - Concurrent Editing Detection (Day 33: MF11)

Implements MF11: Collision detection with:
- Real-time viewer tracking via Redis
- TTL-based session expiration
- Socket.io collision notifications
- Soft collision warning (no hard lock)

BC-001: All queries are tenant-isolated via company_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from app.core.redis import get_redis
from app.exceptions import NotFoundError
from sqlalchemy.orm import Session

from database.models.core import User
from database.models.tickets import Ticket, TicketCollision


class CollisionService:
    """Concurrent editing detection operations."""

    # Viewer session TTL in seconds (5 minutes)
    VIEWER_TTL = 300

    # Redis key prefix
    REDIS_KEY_PREFIX = "parwa"

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
        self._redis = None

    @property
    def redis(self):
        """Lazy load Redis client."""
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    def _get_redis_key(self, ticket_id: str) -> str:
        """Get Redis key for ticket viewers."""
        return f"{
            self.REDIS_KEY_PREFIX}:{
            self.company_id}:ticket_viewing:{ticket_id}"

    # ── VIEWER TRACKING ──────────────────────────────────────────────────────

    def start_viewing(
        self,
        ticket_id: str,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark a user as viewing a ticket.

        Args:
            ticket_id: Ticket ID
            user_id: User ID
            session_id: Browser session ID

        Returns:
            Dict with current viewers and collision status
        """
        # Verify ticket exists and belongs to company
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

        redis_key = self._get_redis_key(ticket_id)

        # Get current viewers
        current_viewers = self._get_viewers_from_redis(redis_key)

        # Check for collision
        has_collision = len(current_viewers) > 0 and user_id not in current_viewers

        # Add user to viewers
        current_viewers.add(user_id)

        # Store in Redis with TTL
        self.redis.setex(
            redis_key,
            self.VIEWER_TTL,
            json.dumps(list(current_viewers)),
        )

        # Also store user's session info
        user_session_key = f"{redis_key}:user:{user_id}"
        session_data = {
            "session_id": session_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
        }
        self.redis.setex(
            user_session_key,
            self.VIEWER_TTL,
            json.dumps(session_data),
        )

        # Log collision to database
        if has_collision:
            self._log_collision(ticket_id, user_id, current_viewers)

        # Get viewer details
        viewer_details = self._get_viewer_details(current_viewers)

        return {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "is_viewing": True,
            "has_collision": has_collision,
            "current_viewers": viewer_details,
            "viewer_count": len(current_viewers),
        }

    def stop_viewing(
        self,
        ticket_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Remove a user from ticket viewers.

        Args:
            ticket_id: Ticket ID
            user_id: User ID

        Returns:
            Dict with remaining viewers
        """
        redis_key = self._get_redis_key(ticket_id)

        # Get current viewers
        current_viewers = self._get_viewers_from_redis(redis_key)

        # Remove user
        current_viewers.discard(user_id)

        # Update Redis
        if current_viewers:
            self.redis.setex(
                redis_key,
                self.VIEWER_TTL,
                json.dumps(list(current_viewers)),
            )
        else:
            # Remove key if no viewers
            self.redis.delete(redis_key)

        # Remove user session
        user_session_key = f"{redis_key}:user:{user_id}"
        self.redis.delete(user_session_key)

        # Update database collision record
        self._update_collision_end(ticket_id, user_id)

        viewer_details = self._get_viewer_details(current_viewers)

        return {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "is_viewing": False,
            "current_viewers": viewer_details,
            "viewer_count": len(current_viewers),
        }

    def get_viewers(
        self,
        ticket_id: str,
    ) -> Dict[str, Any]:
        """Get current viewers of a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            Dict with viewer details
        """
        redis_key = self._get_redis_key(ticket_id)
        current_viewers = self._get_viewers_from_redis(redis_key)
        viewer_details = self._get_viewer_details(current_viewers)

        return {
            "ticket_id": ticket_id,
            "current_viewers": viewer_details,
            "viewer_count": len(current_viewers),
        }

    def _get_viewers_from_redis(self, redis_key: str) -> Set[str]:
        """Get current viewers from Redis."""
        viewers_data = self.redis.get(redis_key)

        if viewers_data:
            try:
                return set(json.loads(viewers_data))
            except (json.JSONDecodeError, TypeError):
                return set()

        return set()

    def _get_viewer_details(self, user_ids: Set[str]) -> List[Dict[str, Any]]:
        """Get user details for viewer list."""
        if not user_ids:
            return []

        users = (
            self.db.query(User)
            .filter(
                User.id.in_(user_ids),
            )
            .all()
        )

        user_map = {u.id: u for u in users}

        result = []
        for user_id in user_ids:
            user = user_map.get(user_id)
            if user:
                result.append(
                    {
                        "user_id": user_id,
                        "name": user.name,
                        "email": user.email,
                    }
                )
            else:
                result.append(
                    {
                        "user_id": user_id,
                        "name": "Unknown",
                        "email": None,
                    }
                )

        return result

    # ── COLLISION LOGGING ────────────────────────────────────────────────────

    def _log_collision(
        self,
        ticket_id: str,
        user_id: str,
        all_viewers: Set[str],
    ) -> TicketCollision:
        """Log a collision event to the database."""
        # Check if there's an active collision record for this user
        existing = (
            self.db.query(TicketCollision)
            .filter(
                TicketCollision.company_id == self.company_id,
                TicketCollision.ticket_id == ticket_id,
                TicketCollision.user_id == user_id,
                TicketCollision.is_active,
            )
            .first()
        )

        if existing:
            # Update existing record
            existing.last_activity_at = datetime.now(timezone.utc)
            self.db.commit()
            return existing

        # Create new collision record
        collision = TicketCollision(
            id=str(uuid.uuid4()),
            company_id=self.company_id,
            ticket_id=ticket_id,
            user_id=user_id,
            started_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(collision)
        self.db.commit()

        return collision

    def _update_collision_end(
        self,
        ticket_id: str,
        user_id: str,
    ) -> None:
        """Mark collision record as ended."""
        self.db.query(TicketCollision).filter(
            TicketCollision.company_id == self.company_id,
            TicketCollision.ticket_id == ticket_id,
            TicketCollision.user_id == user_id,
            TicketCollision.is_active,
        ).update(
            {
                "is_active": False,
            }
        )

        self.db.commit()

    # ── COLLISION HISTORY ────────────────────────────────────────────────────

    def get_collision_history(
        self,
        ticket_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get collision history for a ticket.

        Args:
            ticket_id: Ticket ID
            page: Page number
            page_size: Items per page

        Returns:
            Dict with collision history
        """
        query = self.db.query(TicketCollision).filter(
            TicketCollision.company_id == self.company_id,
            TicketCollision.ticket_id == ticket_id,
        )

        total = query.count()

        collisions = (
            query.order_by(TicketCollision.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # Get user details
        user_ids = {c.user_id for c in collisions}
        users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u for u in users}

        results = []
        for c in collisions:
            user = user_map.get(c.user_id)
            results.append(
                {
                    "id": c.id,
                    "user_id": c.user_id,
                    "user_name": user.name if user else "Unknown",
                    "started_at": c.started_at.isoformat() if c.started_at else None,
                    "last_activity_at": (
                        c.last_activity_at.isoformat() if c.last_activity_at else None
                    ),
                    "is_active": c.is_active,
                }
            )

        return {
            "ticket_id": ticket_id,
            "collisions": results,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ── HEARTBEAT ───────────────────────────────────────────────────────────

    def heartbeat(
        self,
        ticket_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Refresh viewer session (extend TTL).

        Args:
            ticket_id: Ticket ID
            user_id: User ID

        Returns:
            Dict with current status
        """
        redis_key = self._get_redis_key(ticket_id)

        # Get current viewers
        current_viewers = self._get_viewers_from_redis(redis_key)

        # Check if user is in viewers
        if user_id not in current_viewers:
            # User session expired, re-add
            current_viewers.add(user_id)

        # Refresh TTL
        self.redis.setex(
            redis_key,
            self.VIEWER_TTL,
            json.dumps(list(current_viewers)),
        )

        # Refresh user session
        user_session_key = f"{redis_key}:user:{user_id}"
        session_data = self.redis.get(user_session_key)

        if session_data:
            try:
                data = json.loads(session_data)
                data["last_activity_at"] = datetime.now(timezone.utc).isoformat()
                self.redis.setex(user_session_key, self.VIEWER_TTL, json.dumps(data))
            except (json.JSONDecodeError, TypeError):
                pass

        # Update database
        self.db.query(TicketCollision).filter(
            TicketCollision.company_id == self.company_id,
            TicketCollision.ticket_id == ticket_id,
            TicketCollision.user_id == user_id,
            TicketCollision.is_active,
        ).update(
            {
                "last_activity_at": datetime.now(timezone.utc),
            }
        )
        self.db.commit()

        viewer_details = self._get_viewer_details(current_viewers)

        return {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "is_viewing": True,
            "ttl_seconds": self.VIEWER_TTL,
            "current_viewers": viewer_details,
            "viewer_count": len(current_viewers),
        }

    # ── CLEANUP ─────────────────────────────────────────────────────────────

    def cleanup_expired_sessions(self) -> int:
        """Clean up expired collision sessions in database.

        Returns:
            Number of sessions cleaned up
        """
        # Mark all active sessions as inactive
        # Redis handles the actual viewer tracking, DB is for history
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.VIEWER_TTL * 2)

        result = (
            self.db.query(TicketCollision)
            .filter(
                TicketCollision.company_id == self.company_id,
                TicketCollision.is_active,
                TicketCollision.last_activity_at < cutoff,
            )
            .update(
                {
                    "is_active": False,
                }
            )
        )

        self.db.commit()

        return result

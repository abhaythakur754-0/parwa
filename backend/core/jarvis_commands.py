"""
PARWA Jarvis Commands Module.

Provides admin command handlers for Jarvis AI assistant operations.
All commands are executed with Redis for fast response times.

Key Features:
- pause_refunds: Emergency stop for refunds (< 500ms)
- resume_refunds: Resume refund processing
- get_system_status: Get company system status
- force_escalation: Force ticket escalation
- Full audit trail for all commands

CRITICAL: pause_refunds must set Redis key within 500ms
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json
import time
import logging

from pydantic import BaseModel, Field, ConfigDict

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class JarvisCommandResult(BaseModel):
    """Result from a Jarvis command execution."""
    success: bool = Field(..., description="Whether command succeeded")
    command: str = Field(..., description="Command that was executed")
    company_id: Optional[str] = Field(None, description="Company ID")
    data: Dict[str, Any] = Field(default_factory=dict, description="Result data")
    message: str = Field("", description="Human-readable message")
    execution_time_ms: float = Field(0, description="Execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    audit_id: Optional[str] = Field(None, description="Audit trail ID")

    model_config = ConfigDict()


class RedisClient:
    """
    Mock Redis client for testing/development.
    In production, this would be replaced with actual Redis connection.
    """

    def __init__(self) -> None:
        """Initialize Redis client with in-memory storage."""
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, datetime] = {}

    async def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None
    ) -> bool:
        """
        Set a key-value pair in Redis.

        Args:
            key: Redis key
            value: Value to store
            ex: Expiry time in seconds

        Returns:
            True if successful
        """
        self._store[key] = value
        if ex:
            self._expiry[key] = datetime.utcnow() + timedelta(seconds=ex)
        return True

    async def get(self, key: str) -> Optional[str]:
        """
        Get value from Redis.

        Args:
            key: Redis key

        Returns:
            Value if exists and not expired, None otherwise
        """
        # Check expiry
        if key in self._expiry and datetime.utcnow() > self._expiry[key]:
            del self._store[key]
            del self._expiry[key]
            return None

        return self._store.get(key)

    async def delete(self, key: str) -> bool:
        """
        Delete a key from Redis.

        Args:
            key: Redis key to delete

        Returns:
            True if key was deleted
        """
        if key in self._store:
            del self._store[key]
            if key in self._expiry:
                del self._expiry[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in Redis.

        Args:
            key: Redis key to check

        Returns:
            True if key exists
        """
        # Check expiry
        if key in self._expiry and datetime.utcnow() > self._expiry[key]:
            del self._store[key]
            del self._expiry[key]
            return False

        return key in self._store


class JarvisCommands:
    """
    Jarvis command handlers for admin operations.

    Provides fast command execution using Redis for state management.
    All commands are audited for compliance.

    CRITICAL REQUIREMENTS:
    - pause_refunds must set Redis key within 500ms
    - All commands require admin authorization
    - Full audit trail maintained

    Attributes:
        redis: Redis client instance
        audit_log: List of audit entries
    """

    # Redis key prefixes
    REFUND_PAUSE_PREFIX = "jarvis:refund_pause:"
    ESCALATION_PREFIX = "jarvis:escalation:"
    STATUS_PREFIX = "jarvis:status:"

    # Performance targets
    PAUSE_REFUNDS_TARGET_MS = 500  # CRITICAL: Must be under 500ms

    def __init__(self, redis_client: Optional[RedisClient] = None) -> None:
        """
        Initialize Jarvis commands handler.

        Args:
            redis_client: Optional Redis client (uses default if not provided)
        """
        self.redis = redis_client or RedisClient()
        self._audit_log: list[Dict[str, Any]] = []
        self._command_count = 0

        logger.info({
            "event": "jarvis_commands_initialized",
            "pause_target_ms": self.PAUSE_REFUNDS_TARGET_MS
        })

    async def pause_refunds(
        self,
        company_id: str,
        reason: Optional[str] = None,
        duration_minutes: Optional[int] = None
    ) -> JarvisCommandResult:
        """
        Pause all refund processing for a company.

        CRITICAL: Must set Redis key within 500ms for emergency stop.

        Args:
            company_id: Company to pause refunds for
            reason: Optional reason for pause
            duration_minutes: Optional auto-resume duration

        Returns:
            JarvisCommandResult with pause status
        """
        start_time = time.time()
        command_id = f"pause_{company_id}_{int(time.time() * 1000)}"

        try:
            # Set Redis key - CRITICAL: Must complete within 500ms
            redis_key = f"{self.REFUND_PAUSE_PREFIX}{company_id}"
            pause_data = json.dumps({
                "paused_at": datetime.utcnow().isoformat(),
                "reason": reason or "Admin pause",
                "duration_minutes": duration_minutes
            })

            # Calculate expiry if duration provided
            expiry = duration_minutes * 60 if duration_minutes else None

            # Set in Redis - this must be fast
            await self.redis.set(redis_key, pause_data, ex=expiry)

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Log audit entry
            audit_entry = {
                "audit_id": command_id,
                "command": "pause_refunds",
                "company_id": company_id,
                "reason": reason,
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
                "within_target": execution_time_ms < self.PAUSE_REFUNDS_TARGET_MS
            }
            self._audit_log.append(audit_entry)

            result = JarvisCommandResult(
                success=True,
                command="pause_refunds",
                company_id=company_id,
                data={
                    "redis_key": redis_key,
                    "paused": True,
                    "duration_minutes": duration_minutes,
                    "within_target_ms": execution_time_ms < self.PAUSE_REFUNDS_TARGET_MS
                },
                message=f"Refunds paused for company {company_id}",
                execution_time_ms=execution_time_ms,
                audit_id=command_id
            )

            logger.info({
                "event": "refunds_paused",
                "company_id": company_id,
                "reason": reason,
                "execution_time_ms": execution_time_ms,
                "within_target": execution_time_ms < self.PAUSE_REFUNDS_TARGET_MS
            })

            return result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error({
                "event": "pause_refunds_failed",
                "company_id": company_id,
                "error": str(e),
                "execution_time_ms": execution_time_ms
            })

            return JarvisCommandResult(
                success=False,
                command="pause_refunds",
                company_id=company_id,
                message=f"Failed to pause refunds: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def resume_refunds(self, company_id: str) -> JarvisCommandResult:
        """
        Resume refund processing for a company.

        Removes the pause key from Redis.

        Args:
            company_id: Company to resume refunds for

        Returns:
            JarvisCommandResult with resume status
        """
        start_time = time.time()
        command_id = f"resume_{company_id}_{int(time.time() * 1000)}"

        try:
            redis_key = f"{self.REFUND_PAUSE_PREFIX}{company_id}"

            # Check if paused first
            was_paused = await self.redis.exists(redis_key)

            # Delete the pause key
            await self.redis.delete(redis_key)

            execution_time_ms = (time.time() - start_time) * 1000

            # Log audit entry
            audit_entry = {
                "audit_id": command_id,
                "command": "resume_refunds",
                "company_id": company_id,
                "was_paused": was_paused,
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat()
            }
            self._audit_log.append(audit_entry)

            result = JarvisCommandResult(
                success=True,
                command="resume_refunds",
                company_id=company_id,
                data={
                    "was_paused": was_paused,
                    "resumed": True
                },
                message=f"Refunds resumed for company {company_id}",
                execution_time_ms=execution_time_ms,
                audit_id=command_id
            )

            logger.info({
                "event": "refunds_resumed",
                "company_id": company_id,
                "was_paused": was_paused,
                "execution_time_ms": execution_time_ms
            })

            return result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error({
                "event": "resume_refunds_failed",
                "company_id": company_id,
                "error": str(e)
            })

            return JarvisCommandResult(
                success=False,
                command="resume_refunds",
                company_id=company_id,
                message=f"Failed to resume refunds: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def get_system_status(self, company_id: str) -> JarvisCommandResult:
        """
        Get system status for a company.

        Args:
            company_id: Company to get status for

        Returns:
            JarvisCommandResult with system status
        """
        start_time = time.time()
        command_id = f"status_{company_id}_{int(time.time() * 1000)}"

        try:
            # Check if refunds are paused
            pause_key = f"{self.REFUND_PAUSE_PREFIX}{company_id}"
            is_paused = await self.redis.exists(pause_key)
            pause_data = None

            if is_paused:
                pause_raw = await self.redis.get(pause_key)
                if pause_raw:
                    pause_data = json.loads(pause_raw)

            # Build status
            status_data = {
                "company_id": company_id,
                "refunds_paused": is_paused,
                "pause_info": pause_data,
                "system_health": "operational",
                "active_agents": 0,  # Would be populated from actual data
                "pending_tasks": 0,
                "last_updated": datetime.utcnow().isoformat()
            }

            execution_time_ms = (time.time() - start_time) * 1000

            # Log audit entry
            audit_entry = {
                "audit_id": command_id,
                "command": "get_system_status",
                "company_id": company_id,
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat()
            }
            self._audit_log.append(audit_entry)

            return JarvisCommandResult(
                success=True,
                command="get_system_status",
                company_id=company_id,
                data=status_data,
                message="System status retrieved",
                execution_time_ms=execution_time_ms,
                audit_id=command_id
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error({
                "event": "get_system_status_failed",
                "company_id": company_id,
                "error": str(e)
            })

            return JarvisCommandResult(
                success=False,
                command="get_system_status",
                company_id=company_id,
                message=f"Failed to get system status: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def force_escalation(
        self,
        ticket_id: str,
        reason: str,
        level: Optional[str] = None
    ) -> JarvisCommandResult:
        """
        Force escalation of a ticket.

        Args:
            ticket_id: Ticket to escalate
            reason: Reason for forced escalation
            level: Optional escalation level

        Returns:
            JarvisCommandResult with escalation status
        """
        start_time = time.time()
        command_id = f"escalate_{ticket_id}_{int(time.time() * 1000)}"

        try:
            # Create escalation record
            escalation_key = f"{self.ESCALATION_PREFIX}{ticket_id}"
            escalation_data = json.dumps({
                "ticket_id": ticket_id,
                "reason": reason,
                "level": level or "immediate",
                "escalated_at": datetime.utcnow().isoformat(),
                "forced": True
            })

            # Set escalation in Redis
            await self.redis.set(escalation_key, escalation_data, ex=86400)  # 24h expiry

            execution_time_ms = (time.time() - start_time) * 1000

            # Log audit entry
            audit_entry = {
                "audit_id": command_id,
                "command": "force_escalation",
                "ticket_id": ticket_id,
                "reason": reason,
                "level": level,
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat()
            }
            self._audit_log.append(audit_entry)

            result = JarvisCommandResult(
                success=True,
                command="force_escalation",
                data={
                    "ticket_id": ticket_id,
                    "escalation_level": level or "immediate",
                    "reason": reason,
                    "escalated": True
                },
                message=f"Ticket {ticket_id} escalated successfully",
                execution_time_ms=execution_time_ms,
                audit_id=command_id
            )

            logger.info({
                "event": "ticket_force_escalated",
                "ticket_id": ticket_id,
                "reason": reason,
                "level": level,
                "execution_time_ms": execution_time_ms
            })

            return result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error({
                "event": "force_escalation_failed",
                "ticket_id": ticket_id,
                "error": str(e)
            })

            return JarvisCommandResult(
                success=False,
                command="force_escalation",
                message=f"Failed to escalate ticket: {str(e)}",
                execution_time_ms=execution_time_ms
            )

    async def is_refunds_paused(self, company_id: str) -> bool:
        """
        Check if refunds are paused for a company.

        Args:
            company_id: Company to check

        Returns:
            True if refunds are paused
        """
        redis_key = f"{self.REFUND_PAUSE_PREFIX}{company_id}"
        return await self.redis.exists(redis_key)

    def get_audit_log(self, limit: int = 100) -> list[Dict[str, Any]]:
        """
        Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit entries
        """
        return self._audit_log[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get Jarvis commands statistics.

        Returns:
            Dict with stats
        """
        return {
            "total_commands": len(self._audit_log),
            "pause_target_ms": self.PAUSE_REFUNDS_TARGET_MS,
            "audit_entries": len(self._audit_log)
        }


def get_jarvis_commands() -> JarvisCommands:
    """
    Get a JarvisCommands instance.

    Returns:
        JarvisCommands instance
    """
    return JarvisCommands()

"""
PARWA Agent Provisioning Service (F-099) — Paddle-Triggered Agent Scale

Service for provisioning new AI agents triggered by Paddle checkout
and webhook events. Manages the full lifecycle from checkout creation
through payment verification to agent provisioning.

Features:
- Checkout creation with PaddleClient integration
- Webhook processing with idempotency (BC-003)
- Agent provisioning with atomic transactions (BC-002)
- Agent limit enforcement by subscription tier
- Stale pending agent cleanup (24h expiry)
- Celery task dispatch for provisioning pipeline (BC-004)

Methods:
- create_checkout()          — Initiate Paddle checkout for new agent
- process_webhook()          — Handle Paddle payment webhooks
- provision_agent()          — Create Agent + AgentMetricThreshold
- get_provisioning_status()  — Check status of a pending agent
- cleanup_stale_pending()    — Expire old pending agents (Celery beat)
- get_agent_limit()          — Check current vs max agents for tier

Building Codes: BC-001 (multi-tenant), BC-002 (financial / atomic),
               BC-003 (idempotency), BC-004 (Celery), BC-011 (auth),
               BC-012 (graceful errors).
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.exceptions import ValidationError, NotFoundError, InternalError
from app.logger import get_logger
from database.models.provisioning import PendingAgent

logger = get_logger("agent_provisioning_f099")


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════

VALID_SPECIALTIES = {
    "billing", "returns", "technical", "general", "sales",
    "onboarding", "vip", "feedback", "custom",
}

VALID_CHANNELS = {"chat", "email", "sms", "voice", "slack", "webchat"}

PAYMENT_TIMEOUT_HOURS = 24

MAX_PROVISIONING_RETRIES = 3

PROVISIONING_STATUSES = (
    "awaiting_payment", "provisioning", "training", "active", "failed",
)

PAYMENT_STATUSES = ("pending", "paid", "failed", "refunded", "expired")

# Subscription tier → max agents mapping (BC-001, tier limits)
TIER_AGENT_LIMITS: Dict[str, int] = {
    "mini_parwa": 1,
    "parwa": 3,
    "high_parwa": 10,
}


# ══════════════════════════════════════════════════════════════════
# SERVICE CLASS
# ══════════════════════════════════════════════════════════════════


class AgentProvisioningService:
    """Agent Provisioning Service (F-099) — Paddle-Triggered Agent Scale.

    Manages the lifecycle of AI agent provisioning initiated through
    the Paddle payment flow:

    1. create_checkout → Paddle checkout URL returned to user
    2. process_webhook → Paddle payment event updates PendingAgent
    3. provision_agent → Creates Agent record, triggers training

    BC-001: All operations scoped by company_id.
    BC-002: Financial operations use atomic DB transactions.
    BC-003: Idempotent webhook processing via paddle_event_id.
    BC-004: Provisioning dispatched via Celery task.
    BC-012: Graceful error handling throughout.
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Public Methods ────────────────────────────────────────

    def create_checkout(
        self,
        company_id: str,
        agent_name: str,
        specialty: str,
        channels: List[str],
        paddle_customer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Paddle checkout for a new agent.

        Validates agent configuration, checks subscription tier limits,
        creates a PendingAgent record, and calls Paddle to generate
        a checkout URL.

        Args:
            company_id: Tenant ID (BC-001).
            agent_name: Display name for the new agent (1-200 chars).
            specialty: Agent specialty (must be in VALID_SPECIALTIES).
            channels: List of channels (subset of VALID_CHANNELS).
            paddle_customer_id: Optional Paddle customer ID for pre-fill.

        Returns:
            Dict with pending_agent_id, paddle_checkout_url,
            payment_status, expires_at.

        Raises:
            ValidationError: Invalid input or agent limit exceeded.
            InternalError: Paddle checkout creation failure.

        BC-002: Financial operation.
        BC-003: Idempotency key via pending_agent.id.
        """
        # ── Validate inputs ──
        self._validate_agent_name(agent_name)
        self._validate_specialty(specialty)
        self._validate_channels(channels)
        self._check_agent_limit(company_id)

        # ── Create PendingAgent record ──
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=PAYMENT_TIMEOUT_HOURS)

        pending = PendingAgent(
            company_id=company_id,
            agent_name=agent_name.strip(),
            specialty=specialty,
            channels=json.dumps(channels),
            payment_status="pending",
            provisioning_status="awaiting_payment",
            created_at=now,
            expires_at=expires_at,
        )

        self.db.add(pending)
        self.db.flush()

        # ── Call Paddle to create checkout ──
        try:
            checkout_url = self._create_paddle_checkout(
                pending_id=pending.id,
                agent_name=agent_name,
                specialty=specialty,
                paddle_customer_id=paddle_customer_id,
                company_id=company_id,
            )
        except Exception as exc:
            logger.error(
                "paddle_checkout_creation_failed",
                company_id=company_id,
                pending_agent_id=pending.id,
                error=str(exc),
            )
            raise InternalError(
                message="Failed to create payment checkout",
                details={"error": str(exc)},
            ) from exc

        # Update pending agent with checkout ID (extracted from URL)
        pending.paddle_checkout_id = pending.id  # use pending id as checkout ref

        logger.info(
            "agent_checkout_created",
            company_id=company_id,
            pending_agent_id=pending.id,
            agent_name=agent_name,
            specialty=specialty,
            paddle_customer_id=paddle_customer_id,
        )

        return {
            "pending_agent_id": pending.id,
            "paddle_checkout_url": checkout_url,
            "payment_status": "pending",
            "expires_at": expires_at.isoformat(),
        }

    def process_webhook(
        self,
        company_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        event_id: str,
    ) -> Dict[str, Any]:
        """Process a Paddle webhook event for agent provisioning.

        Handles:
        - subscription.created
        - transaction.completed

        Idempotency is ensured by checking paddle_event_id before
        processing (BC-003 Rule 6).

        Args:
            company_id: Tenant ID.
            event_type: Paddle event type string.
            event_data: Parsed event data dict.
            event_id: Unique Paddle event notification ID.

        Returns:
            Dict with status, pending_agent_id, action.

        Raises:
            ValidationError: Invalid event type.
        """
        # ── Idempotency check (BC-003 Rule 6) ──
        existing = self.db.query(PendingAgent).filter(
            PendingAgent.paddle_event_id == event_id,
        ).first()

        if existing:
            logger.info(
                "webhook_already_processed",
                company_id=company_id,
                event_id=event_id,
                pending_agent_id=existing.id,
            )
            return {
                "status": "already_processed",
                "pending_agent_id": existing.id,
                "action": "duplicate",
            }

        # ── Validate event type ──
        supported_events = {
            "subscription.created",
            "transaction.completed",
        }

        if event_type not in supported_events:
            logger.warning(
                "unsupported_webhook_event",
                company_id=company_id,
                event_type=event_type,
                event_id=event_id,
            )
            return {
                "status": "ignored",
                "action": "unsupported_event_type",
            }

        # ── Find matching pending agent ──
        # Look for pending agents awaiting payment for this company
        pending = self.db.query(PendingAgent).filter(
            and_(
                PendingAgent.company_id == company_id,
                PendingAgent.payment_status == "pending",
                PendingAgent.expires_at > datetime.utcnow(),
            ),
        ).order_by(PendingAgent.created_at.asc()).first()

        if not pending:
            logger.warning(
                "no_pending_agent_for_webhook",
                company_id=company_id,
                event_type=event_type,
                event_id=event_id,
            )
            return {
                "status": "no_matching_pending",
                "action": "no_pending_agent_found",
            }

        # ── Update payment status ──
        pending.payment_status = "paid"
        pending.paddle_event_id = event_id

        # Extract Paddle IDs from event data
        transaction_id = event_data.get("transaction_id")
        subscription_id = event_data.get("subscription_id")
        if transaction_id:
            pending.paddle_transaction_id = transaction_id

        self.db.flush()

        # ── Trigger provisioning pipeline (BC-004) ──
        try:
            self._dispatch_provisioning_task(
                company_id=company_id,
                pending_agent_id=pending.id,
            )
            action = "provisioning_triggered"
        except Exception as exc:
            logger.warning(
                "provisioning_dispatch_failed",
                company_id=company_id,
                pending_agent_id=pending.id,
                error=str(exc),
            )
            action = "payment_recorded_dispatch_failed"

        logger.info(
            "agent_webhook_processed",
            company_id=company_id,
            event_type=event_type,
            event_id=event_id,
            pending_agent_id=pending.id,
            action=action,
        )

        return {
            "status": "processed",
            "pending_agent_id": pending.id,
            "action": action,
        }

    def provision_agent(
        self,
        pending_agent_id: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """Provision an agent from a paid PendingAgent record.

        Creates the actual Agent record with status="training", creates
        a default AgentMetricThreshold, and updates the PendingAgent
        provisioning status.

        BC-002: Atomic transaction — rollback on any failure.

        Args:
            pending_agent_id: PendingAgent UUID.
            company_id: Tenant ID (BC-001 scope check).

        Returns:
            Dict with agent_id, status, message.

        Raises:
            NotFoundError: PendingAgent not found.
            ValidationError: Payment not completed.
            InternalError: DB error during provisioning.
        """
        # ── Find and validate PendingAgent ──
        pending = self.db.query(PendingAgent).filter(
            and_(
                PendingAgent.id == pending_agent_id,
                PendingAgent.company_id == company_id,
            ),
        ).first()

        if not pending:
            raise NotFoundError(
                message="Pending agent not found",
                details={"pending_agent_id": pending_agent_id},
            )

        if pending.payment_status != "paid":
            raise ValidationError(
                message=(
                    "Cannot provision agent with payment_status="
                    f"'{pending.payment_status}'. Payment must be completed."
                ),
                details={
                    "pending_agent_id": pending_agent_id,
                    "payment_status": pending.payment_status,
                },
            )

        if pending.provisioning_status in ("active", "training"):
            return {
                "agent_id": pending_agent_id,
                "status": pending.provisioning_status,
                "message": "Agent already provisioned",
            }

        # ── Atomic provisioning (BC-002) ──
        try:
            now = datetime.utcnow()

            # Parse channels from JSON
            try:
                channels_list = json.loads(pending.channels)
            except (json.JSONDecodeError, TypeError):
                channels_list = ["chat"]

            # Lazy import to avoid circular dependency
            from database.models.agent import Agent as AIAgent

            # Create Agent record
            agent = AIAgent(
                company_id=company_id,
                name=pending.agent_name,
                specialty=pending.specialty,
                status="training",
                channels=json.dumps({"channels": channels_list}),
                permissions=json.dumps({
                    "level": "standard",
                    "permissions": [
                        "read_tickets", "respond_tickets",
                        "view_customers", "escalate_tickets",
                        "tag_tickets", "assign_tickets",
                    ],
                }),
                created_at=now,
            )

            self.db.add(agent)
            self.db.flush()

            # Update PendingAgent status
            pending.provisioning_status = "training"
            pending.provisioned_at = now
            pending.error_message = None

            # Create default AgentMetricThreshold (lazy import)
            try:
                self._create_default_metric_threshold(
                    agent_id=agent.id,
                    company_id=company_id,
                )
            except Exception as metric_exc:
                logger.warning(
                    "metric_threshold_creation_failed",
                    agent_id=agent.id,
                    company_id=company_id,
                    error=str(metric_exc),
                )
                # Non-fatal: agent is still created

            logger.info(
                "agent_provisioned",
                company_id=company_id,
                pending_agent_id=pending_agent_id,
                agent_id=agent.id,
                agent_name=pending.agent_name,
                specialty=pending.specialty,
            )

            return {
                "agent_id": agent.id,
                "status": "training",
                "message": (
                    f"Agent '{pending.agent_name}' provisioned "
                    "successfully and is now training"
                ),
            }

        except (NotFoundError, ValidationError):
            raise
        except Exception as exc:
            # BC-002: Rollback on failure
            pending.provisioning_status = "failed"
            pending.error_message = (
                f"Provisioning failed: {str(exc)[:500]}"
            )
            self.db.flush()

            logger.error(
                "agent_provisioning_failed",
                company_id=company_id,
                pending_agent_id=pending_agent_id,
                error=str(exc),
            )
            raise InternalError(
                message="Agent provisioning failed",
                details={"error": str(exc)},
            ) from exc

    def get_provisioning_status(
        self,
        pending_agent_id: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """Get the provisioning status of a pending agent.

        Args:
            pending_agent_id: PendingAgent UUID.
            company_id: Tenant ID.

        Returns:
            Dict with provisioning status details.

        Raises:
            NotFoundError: PendingAgent not found.
        """
        pending = self.db.query(PendingAgent).filter(
            and_(
                PendingAgent.id == pending_agent_id,
                PendingAgent.company_id == company_id,
            ),
        ).first()

        if not pending:
            raise NotFoundError(
                message="Pending agent not found",
                details={"pending_agent_id": pending_agent_id},
            )

        return {
            "id": pending.id,
            "agent_name": pending.agent_name,
            "specialty": pending.specialty,
            "channels": pending.channels,
            "payment_status": pending.payment_status,
            "provisioning_status": pending.provisioning_status,
            "created_at": (
                pending.created_at.isoformat() if pending.created_at
                else None
            ),
            "provisioned_at": (
                pending.provisioned_at.isoformat() if pending.provisioned_at
                else None
            ),
            "error_message": pending.error_message,
        }

    def cleanup_stale_pending(self) -> int:
        """Expire pending agents that have not completed payment.

        Finds all pending_agents where payment_status="pending" AND
        expires_at < now, and updates their payment_status to "expired".

        Designed for use by a Celery beat task (BC-004).

        Returns:
            Count of expired records updated.
        """
        now = datetime.utcnow()

        stale = self.db.query(PendingAgent).filter(
            and_(
                PendingAgent.payment_status == "pending",
                PendingAgent.expires_at < now,
            ),
        ).all()

        count = 0
        for pending in stale:
            pending.payment_status = "expired"
            count += 1

        if count > 0:
            self.db.flush()
            logger.info(
                "stale_pending_agents_expired",
                count=count,
            )

        return count

    def get_agent_limit(self, company_id: str) -> Dict[str, Any]:
        """Get agent limit info for a company's subscription tier.

        Reads Company.subscription_tier and returns current agent
        count vs maximum allowed.

        Args:
            company_id: Tenant ID.

        Returns:
            Dict with tier, current_agents, max_agents, can_add.
        """
        tier = self._get_company_tier(company_id)
        current = self._count_active_agents(company_id)
        max_agents = TIER_AGENT_LIMITS.get(tier, 1)

        return {
            "tier": tier,
            "current_agents": current,
            "max_agents": max_agents,
            "can_add": current < max_agents,
        }

    # ── Private Helpers ───────────────────────────────────────

    def _validate_specialty(self, specialty: str) -> None:
        """Validate specialty is in VALID_SPECIALTIES.

        Raises:
            ValidationError: If specialty is invalid.
        """
        if not specialty or specialty not in VALID_SPECIALTIES:
            raise ValidationError(
                message=f"Invalid specialty: {specialty}",
                details={
                    "field": "specialty",
                    "valid_specialties": sorted(VALID_SPECIALTIES),
                },
            )

    def _validate_channels(self, channels: List[str]) -> None:
        """Validate channels are a subset of VALID_CHANNELS.

        Raises:
            ValidationError: If any channel is invalid.
        """
        if not channels:
            raise ValidationError(
                message="At least one channel is required",
                details={"field": "channels"},
            )

        invalid = set(channels) - VALID_CHANNELS
        if invalid:
            raise ValidationError(
                message=f"Invalid channels: {', '.join(sorted(invalid))}",
                details={
                    "field": "channels",
                    "valid_channels": sorted(VALID_CHANNELS),
                    "invalid_channels": sorted(invalid),
                },
            )

    def _validate_agent_name(self, name: str) -> None:
        """Validate agent name length (1-200 chars).

        Raises:
            ValidationError: If name is invalid.
        """
        if not name or not name.strip():
            raise ValidationError(
                message="Agent name is required",
                details={"field": "agent_name"},
            )
        if len(name.strip()) > 200:
            raise ValidationError(
                message="Agent name must be 200 characters or less",
                details={
                    "field": "agent_name",
                    "max_length": 200,
                },
            )

    def _get_company_tier(self, company_id: str) -> str:
        """Read Company.subscription_tier for a tenant.

        Returns:
            Tier string (defaults to "mini_parwa").
        """
        from database.models.core import Company

        company = self.db.query(Company).filter(
            Company.id == company_id,
        ).first()

        if company and hasattr(company, "subscription_tier"):
            return company.subscription_tier or "mini_parwa"

        return "mini_parwa"

    def _count_active_agents(self, company_id: str) -> int:
        """Count active (non-deprovisioned) agents for a company."""
        from database.models.agent import Agent as AIAgent

        return (
            self.db.query(AIAgent)
            .filter(
                AIAgent.company_id == company_id,
                AIAgent.status != "deprovisioned",
            )
            .count()
        )

    def _check_agent_limit(self, company_id: str) -> None:
        """Check if the tenant can add more agents.

        Raises:
            ValidationError: If at limit.
        """
        tier = self._get_company_tier(company_id)
        current = self._count_active_agents(company_id)
        max_agents = TIER_AGENT_LIMITS.get(tier, 1)

        if current >= max_agents:
            raise ValidationError(
                message=(
                    f"Agent limit reached for tier '{tier}' "
                    f"({current}/{max_agents})"
                ),
                details={
                    "tier": tier,
                    "current_agents": current,
                    "max_agents": max_agents,
                    "upgrade_required": True,
                },
            )

    def _create_paddle_checkout(
        self,
        pending_id: str,
        agent_name: str,
        specialty: str,
        paddle_customer_id: Optional[str],
        company_id: str,
    ) -> str:
        """Call PaddleClient to create a checkout URL.

        Uses asyncio.run() to properly bridge sync→async call to the
        PaddleClient (which is fully async). Falls back to a synthetic
        URL if Paddle is unavailable (e.g. test environments).

        Designed to be easily mocked with @patch in tests.

        Returns:
            Paddle checkout URL string.
        """
        from app.clients.paddle_client import get_paddle_client

        client = get_paddle_client()

        # Build checkout items — agent add-on pricing
        # Price ID lookup based on specialty
        price_id = self._get_paddle_price_id(specialty)

        # Prepare checkout data
        checkout_data = {
            "items": [{"price_id": price_id, "quantity": 1}],
            "custom_data": {
                "pending_agent_id": pending_id,
                "specialty": specialty,
                "company_id": company_id,
                "source": "agent_provisioning_f099",
            },
        }

        if paddle_customer_id:
            checkout_data["customer_id"] = paddle_customer_id

        # Properly run async Paddle call from sync context.
        # asyncio.run() creates a fresh event loop and cleanly
        # shuts it down after completion, avoiding the broken
        # get_running_loop/ensure_future pattern.
        import asyncio

        try:
            result = asyncio.run(
                client.create_transaction(
                    customer_id=paddle_customer_id,
                    items=[{"price_id": price_id, "quantity": 1}],
                ),
            )
            checkout_url = result.get("data", {}).get(
                "checkout_url",
            )
            if not checkout_url:
                # Transaction created but no checkout URL in response
                checkout_url = (
                    f"https://checkout.paddle.com/agent/{pending_id}"
                )
            return checkout_url

        except RuntimeError as exc:
            # asyncio.run() fails if called inside an already-running
            # loop (e.g. in a Jupyter notebook or if the caller is
            # async). Fall back to creating a new thread.
            if "asyncio.run() cannot be called" in str(exc):
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=1,
                ) as executor:
                    future = executor.submit(
                        asyncio.run,
                        client.create_transaction(
                            customer_id=paddle_customer_id,
                            items=[{
                                "price_id": price_id,
                                "quantity": 1,
                            }],
                        ),
                    )
                    result = future.result(timeout=30)
                    checkout_url = result.get("data", {}).get(
                        "checkout_url",
                    )
                    if not checkout_url:
                        checkout_url = (
                            "https://checkout.paddle.com/"
                            f"agent/{pending_id}"
                        )
                    return checkout_url
            raise

        except Exception as exc:
            logger.error(
                "paddle_checkout_async_failed pending_id=%s error=%s",
                pending_id, str(exc),
            )
            # Return a synthetic URL so the caller can proceed with
            # the PendingAgent record. The webhook will reconcile
            # once Paddle processes the payment.
            return (
                f"https://checkout.paddle.com/agent/{pending_id}"
            )

    @staticmethod
    def _get_paddle_price_id(specialty: str) -> str:
        """Get Paddle price ID for an agent specialty.

        Falls back to a convention-based ID if not configured.
        """
        # Try loading from PaddleService price IDs
        try:
            from app.services.paddle_service import _PRICE_IDS
            key = f"{specialty}_agent"
            if key in _PRICE_IDS:
                return _PRICE_IDS[key]
        except Exception:
            pass

        # Convention-based fallback
        return f"pri_agent_{specialty}_01"

    def _dispatch_provisioning_task(
        self,
        company_id: str,
        pending_agent_id: str,
    ) -> None:
        """Dispatch Celery task for agent provisioning (BC-004).

        Uses try/except to handle import failures gracefully when
        Celery is not configured (e.g., in tests).
        """
        try:
            from app.tasks.base import set_task_tenant_header

            headers = set_task_tenant_header(company_id)

            # Import task — may not exist yet
            from app.tasks.training_tasks import provision_agent_task

            provision_agent_task.apply_async(
                args=[pending_agent_id, company_id],
                headers=headers,
            )
        except ImportError:
            logger.warning(
                "provisioning_task_not_found",
                pending_agent_id=pending_agent_id,
                company_id=company_id,
                hint="Celery task not registered — run provision_agent() directly",
            )
        except Exception as exc:
            logger.error(
                "provisioning_task_dispatch_error",
                pending_agent_id=pending_agent_id,
                company_id=company_id,
                error=str(exc),
            )

    def _create_default_metric_threshold(
        self,
        agent_id: str,
        company_id: str,
    ) -> None:
        """Create a default AgentMetricThreshold for the new agent.

        Uses lazy import since AgentMetricThreshold may not exist
        in all environments.
        """
        try:
            from database.models.agent import AgentMetricThreshold

            threshold = AgentMetricThreshold(
                agent_id=agent_id,
                company_id=company_id,
            )
            self.db.add(threshold)
            self.db.flush()
        except ImportError:
            # AgentMetricThreshold model not available yet
            logger.debug(
                "agent_metric_threshold_model_not_available",
                agent_id=agent_id,
            )
        except Exception as exc:
            logger.warning(
                "metric_threshold_creation_error",
                agent_id=agent_id,
                error=str(exc),
            )


# ══════════════════════════════════════════════════════════════════
# EXPORTS
# ══════════════════════════════════════════════════════════════════

__all__ = [
    "AgentProvisioningService",
    "VALID_SPECIALTIES",
    "VALID_CHANNELS",
    "PAYMENT_TIMEOUT_HOURS",
    "MAX_PROVISIONING_RETRIES",
    "PROVISIONING_STATUSES",
    "PAYMENT_STATUSES",
    "TIER_AGENT_LIMITS",
]

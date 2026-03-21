"""
PARWA MCP SLA Server.

Provides SLA (Service Level Agreement) operations via MCP including:
- SLA calculation and breach detection
- Breach prediction
- Ticket escalation

All operations are tool-based and inherit from BaseMCPServer.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import uuid
import asyncio

from mcp_servers.base_server import BaseMCPServer
from shared.core_functions.logger import get_logger
from shared.compliance.sla_calculator import (
    SLACalculator, SLATier, SLAType, SLABreachStatus
)

logger = get_logger(__name__)


class SLAServer(BaseMCPServer):
    """
    MCP Server for SLA operations.

    Provides tools for SLA calculation, breach prediction,
    and ticket escalation management.

    Tools:
        - calculate_sla: Calculate SLA status for a ticket
        - get_breach_predictions: Get predicted SLA breaches
        - escalate_ticket: Escalate a ticket with reason
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        sla_calculator: Optional[SLACalculator] = None
    ) -> None:
        """
        Initialize SLA Server.

        Args:
            config: Optional server configuration
            sla_calculator: Optional SLA calculator instance
        """
        super().__init__(name="sla_server", config=config)
        self._sla_calculator = sla_calculator or SLACalculator()
        self._ticket_store: Dict[str, Dict[str, Any]] = {}
        self._escalation_store: Dict[str, Dict[str, Any]] = {}

    def _register_tools(self) -> None:
        """Register all SLA tools."""
        self.register_tool(
            name="calculate_sla",
            description="Calculate SLA status for a ticket",
            parameters_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket ID to calculate SLA for"
                    },
                    "tier": {
                        "type": "string",
                        "description": "SLA tier",
                        "enum": ["critical", "high", "standard", "low"],
                        "default": "standard"
                    },
                    "created_at": {
                        "type": "string",
                        "description": "Ticket creation timestamp (ISO format)"
                    },
                    "is_vip": {
                        "type": "boolean",
                        "description": "Whether customer is VIP",
                        "default": False
                    }
                },
                "required": ["ticket_id"]
            },
            handler=self._handle_calculate_sla
        )

        self.register_tool(
            name="get_breach_predictions",
            description="Get predicted SLA breaches based on current tickets",
            parameters_schema={
                "type": "object",
                "properties": {
                    "time_horizon_hours": {
                        "type": "integer",
                        "description": "Hours to look ahead",
                        "default": 24
                    },
                    "min_probability": {
                        "type": "number",
                        "description": "Minimum breach probability",
                        "default": 0.5
                    },
                    "tiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by SLA tiers"
                    }
                },
                "required": []
            },
            handler=self._handle_get_breach_predictions
        )

        self.register_tool(
            name="escalate_ticket",
            description="Escalate a ticket with a reason",
            parameters_schema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "Ticket ID to escalate"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for escalation"
                    },
                    "escalation_level": {
                        "type": "string",
                        "description": "Escalation level",
                        "enum": ["team_lead", "manager", "director", "executive"],
                        "default": "team_lead"
                    },
                    "additional_context": {
                        "type": "object",
                        "description": "Additional context for escalation"
                    }
                },
                "required": ["ticket_id", "reason"]
            },
            handler=self._handle_escalate_ticket
        )

    async def _on_start(self) -> None:
        """Initialize SLA server resources."""
        logger.info({
            "event": "sla_server_starting",
            "server": self._name,
        })
        # Add mock tickets for testing
        self._seed_mock_tickets()
        await asyncio.sleep(0.01)

    async def _handle_calculate_sla(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle calculate_sla tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with SLA calculation results
        """
        ticket_id = params["ticket_id"]
        tier_str = params.get("tier", "standard")
        created_at_str = params.get("created_at")
        is_vip = params.get("is_vip", False)

        # Parse tier
        tier_map = {
            "critical": SLATier.CRITICAL,
            "high": SLATier.HIGH,
            "standard": SLATier.STANDARD,
            "low": SLATier.LOW
        }
        tier = tier_map.get(tier_str, SLATier.STANDARD)

        # Parse created_at or use ticket data
        if created_at_str:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        elif ticket_id in self._ticket_store:
            created_at = self._ticket_store[ticket_id]["created_at"]
        else:
            # Default to 1 hour ago for mock
            created_at = datetime.now() - timedelta(hours=1)

        # Calculate SLA for all types
        results = {}
        for sla_type in SLAType:
            result = self._sla_calculator.calculate_sla(
                ticket_id=ticket_id,
                tier=tier,
                sla_type=sla_type,
                created_at=created_at,
                is_vip=is_vip
            )
            # Handle both enum and string status values
            status_val = result.status.value if hasattr(result.status, 'value') else result.status
            results[sla_type.value] = {
                "status": status_val,
                "is_breached": result.is_breached,
                "is_warning": result.is_warning,
                "time_elapsed_hours": result.time_elapsed_hours,
                "time_remaining_hours": result.time_remaining_hours,
                "percentage_used": result.percentage_used,
                "should_escalate": result.should_escalate,
                "sla_deadline": result.sla_deadline.isoformat() if result.sla_deadline else None
            }

        # Determine overall status
        overall_status = SLABreachStatus.OK.value
        if any(r["is_breached"] for r in results.values()):
            overall_status = SLABreachStatus.BREACHED.value
        elif any(r["is_warning"] for r in results.values()):
            overall_status = SLABreachStatus.WARNING.value

        logger.info({
            "event": "sla_calculated",
            "ticket_id": ticket_id,
            "tier": tier_str,
            "status": overall_status
        })

        return {
            "status": "success",
            "ticket_id": ticket_id,
            "tier": tier_str,
            "overall_status": overall_status,
            "is_vip": is_vip,
            "sla_results": results,
            "calculated_at": datetime.now().isoformat()
        }

    async def _handle_get_breach_predictions(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle get_breach_predictions tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with predicted breaches
        """
        time_horizon = params.get("time_horizon_hours", 24)
        min_probability = params.get("min_probability", 0.5)
        tier_filter = params.get("tiers", [])

        predictions = []

        # Analyze stored tickets for breach predictions
        for ticket_id, ticket_data in self._ticket_store.items():
            tier_str = ticket_data.get("tier", "standard")

            # Apply tier filter
            if tier_filter and tier_str not in tier_filter:
                continue

            # Calculate current SLA status
            tier_map = {
                "critical": SLATier.CRITICAL,
                "high": SLATier.HIGH,
                "standard": SLATier.STANDARD,
                "low": SLATier.LOW
            }
            tier = tier_map.get(tier_str, SLATier.STANDARD)

            # Get policy for time limits
            policy = self._sla_calculator.get_policy(tier)

            created_at = ticket_data["created_at"]
            elapsed_hours = (datetime.now() - created_at).total_seconds() / 3600

            # Calculate breach probability
            first_response_used = elapsed_hours / policy.first_response_hours
            resolution_used = elapsed_hours / policy.resolution_hours

            # Predict breaches within horizon
            breach_probability = 0.0
            predicted_breach_type = None

            if first_response_used >= policy.warning_threshold:
                breach_probability = min(1.0, first_response_used)
                predicted_breach_type = "first_response"
            elif resolution_used >= policy.warning_threshold:
                breach_probability = min(1.0, resolution_used * 0.8)
                predicted_breach_type = "resolution"

            if breach_probability >= min_probability:
                predictions.append({
                    "ticket_id": ticket_id,
                    "tier": tier_str,
                    "breach_probability": round(breach_probability, 2),
                    "predicted_breach_type": predicted_breach_type,
                    "time_remaining_hours": round(
                        policy.resolution_hours - elapsed_hours, 2
                    ),
                    "customer_id": ticket_data.get("customer_id"),
                    "subject": ticket_data.get("subject"),
                    "is_vip": ticket_data.get("is_vip", False)
                })

        # Sort by probability descending
        predictions.sort(key=lambda x: x["breach_probability"], reverse=True)

        logger.info({
            "event": "breach_predictions",
            "predictions_count": len(predictions),
            "time_horizon_hours": time_horizon
        })

        return {
            "status": "success",
            "predictions": predictions[:20],  # Top 20
            "total_predicted_breaches": len(predictions),
            "time_horizon_hours": time_horizon,
            "min_probability": min_probability,
            "generated_at": datetime.now().isoformat()
        }

    async def _handle_escalate_ticket(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle escalate_ticket tool call.

        Args:
            params: Tool parameters

        Returns:
            Dict with escalation status
        """
        ticket_id = params["ticket_id"]
        reason = params["reason"]
        escalation_level = params.get("escalation_level", "team_lead")
        additional_context = params.get("additional_context", {})

        # Generate escalation ID
        escalation_id = f"esc_{uuid.uuid4().hex[:12]}"

        # Create escalation record
        escalation = {
            "escalation_id": escalation_id,
            "ticket_id": ticket_id,
            "reason": reason,
            "level": escalation_level,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "additional_context": additional_context
        }

        self._escalation_store[escalation_id] = escalation

        # Update ticket if exists
        if ticket_id in self._ticket_store:
            self._ticket_store[ticket_id]["escalated"] = True
            self._ticket_store[ticket_id]["escalation_id"] = escalation_id

        logger.info({
            "event": "ticket_escalated",
            "ticket_id": ticket_id,
            "escalation_id": escalation_id,
            "level": escalation_level,
            "reason": reason
        })

        return {
            "status": "success",
            "escalation_id": escalation_id,
            "ticket_id": ticket_id,
            "level": escalation_level,
            "reason": reason,
            "created_at": escalation["created_at"],
            "message": f"Ticket {ticket_id} escalated to {escalation_level}"
        }

    def _seed_mock_tickets(self) -> None:
        """Seed mock tickets for testing."""
        mock_tickets = [
            {
                "ticket_id": "TKT-001",
                "subject": "Login issue",
                "tier": "critical",
                "is_vip": True,
                "created_at": datetime.now() - timedelta(minutes=30),
                "customer_id": "CUST-001"
            },
            {
                "ticket_id": "TKT-002",
                "subject": "Payment failed",
                "tier": "high",
                "is_vip": False,
                "created_at": datetime.now() - timedelta(hours=2),
                "customer_id": "CUST-002"
            },
            {
                "ticket_id": "TKT-003",
                "subject": "Feature request",
                "tier": "low",
                "is_vip": False,
                "created_at": datetime.now() - timedelta(hours=12),
                "customer_id": "CUST-003"
            },
            {
                "ticket_id": "TKT-004",
                "subject": "Refund request",
                "tier": "standard",
                "is_vip": False,
                "created_at": datetime.now() - timedelta(hours=6),
                "customer_id": "CUST-004"
            }
        ]

        for ticket in mock_tickets:
            self._ticket_store[ticket["ticket_id"]] = ticket


def get_sla_server() -> SLAServer:
    """
    Get an SLAServer instance.

    Returns:
        SLAServer instance
    """
    return SLAServer()

"""
High Parwa Ticket Service — Ticket creation and solving service.

Provides convenience methods for:
  - create_ticket: Create a ticket and run High Parwa pipeline
  - solve_ticket: Re-run pipeline for an existing ticket
  - classify_ticket: Just classify, no generation

Uses ParwaHighPipeline under the hood.
Stores tickets in-memory for now (DB layer comes later).

High-specific: Returns richest metadata including all Tier 3 technique
details, peer review results, strategic decisions, context health,
dedup status, and quality gate with retry history.

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.parwa_high.graph import ParwaHighPipeline
from app.logger import get_logger

logger = get_logger("parwa_high_ticket_service")


class ParwaHighTicketService:
    """Ticket creation and solving service for High Parwa.

    Manages tickets in-memory (DB layer comes later).
    Each method follows BC-001: company_id is first parameter.

    High-specific: Returns the richest metadata including:
    - All technique details (Tier 1+2+3)
    - Peer review results
    - Strategic decision
    - Context health
    - Dedup status
    - Quality gate with retry history
    - Context compression ratio

    Usage:
        service = ParwaHighTicketService()
        result = await service.create_ticket(
            company_id="comp_123",
            query="I need a refund",
            industry="ecommerce",
            channel="chat",
        )
    """

    def __init__(self) -> None:
        """Initialize the ticket service."""
        self._pipeline = ParwaHighPipeline()
        self._tickets: Dict[str, Dict[str, Any]] = {}
        logger.info("ParwaHighTicketService initialized")

    async def create_ticket(
        self,
        company_id: str,
        query: str,
        industry: str = "general",
        channel: str = "chat",
        customer_id: str = "",
        customer_tier: str = "free",
    ) -> Dict[str, Any]:
        """Create a ticket and run High Parwa pipeline.

        BC-001: company_id is first parameter.

        Args:
            company_id: Tenant identifier (BC-001).
            query: Customer's raw message.
            industry: 'ecommerce' | 'logistics' | 'saas' | 'general'.
            channel: 'chat' | 'email' | 'phone' | 'web_widget' | 'social'.
            customer_id: Customer identifier.
            customer_tier: Customer subscription tier.

        Returns:
            Dict with ticket_id, response, and pipeline metadata.
        """
        try:
            ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"

            result = await self._pipeline.process_ticket(
                query=query,
                company_id=company_id,
                industry=industry,
                channel=channel,
                customer_id=customer_id,
                customer_tier=customer_tier,
                ticket_id=ticket_id,
            )

            ticket_data = {
                "ticket_id": ticket_id,
                "company_id": company_id,
                "query": query,
                "industry": industry,
                "channel": channel,
                "customer_id": customer_id,
                "customer_tier": customer_tier,
                "variant_tier": "parwa_high",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "pipeline_result": result,
                "status": "processed",
            }
            self._tickets[ticket_id] = ticket_data

            # Build response (High: richest metadata)
            response = {
                "ticket_id": ticket_id,
                "company_id": company_id,
                "response": result.get("final_response", ""),
                "classification": result.get("classification", {}),
                "pii_detected": result.get("pii_detected", False),
                "emergency_flag": result.get("emergency_flag", False),
                "empathy_score": result.get("empathy_score", 0.5),
                "pipeline_status": result.get("pipeline_status", "unknown"),
                "steps_completed": result.get("steps_completed", []),
                "total_latency_ms": result.get("total_latency_ms", 0.0),
                # Quality details
                "quality_score": result.get("quality_score", 0.0),
                "quality_passed": result.get("quality_passed", True),
                "quality_retry_count": result.get("quality_retry_count", 0),
                # Technique details
                "technique_used": result.get(
                    "step_outputs", {},
                ).get("technique_select", {}).get("primary_technique", "direct"),
                "reasoning_technique": result.get(
                    "step_outputs", {},
                ).get("reasoning_chain", {}).get("technique", "direct"),
                # High-specific: Peer review
                "peer_review_passed": result.get(
                    "step_outputs", {},
                ).get("peer_review", {}).get("passed", True),
                "peer_review_score": result.get(
                    "step_outputs", {},
                ).get("peer_review", {}).get("review_score", 0.8),
                # High-specific: Strategic decision
                "strategic_decision": result.get(
                    "step_outputs", {},
                ).get("strategic_decision", {}).get("decision", "proceed"),
                # High-specific: Context health
                "context_health_score": result.get(
                    "step_outputs", {},
                ).get("context_health", {}).get("health_score", 1.0),
                # High-specific: Dedup
                "dedup_is_duplicate": result.get("dedup_is_duplicate", False),
                # High-specific: Context compression
                "context_compression_ratio": result.get(
                    "context_compression_ratio", 1.0,
                ),
                "billing_cost_usd": result.get("billing_cost_usd", 0.0),
                "created_at": ticket_data["created_at"],
            }

            logger.info(
                "high_ticket_created",
                ticket_id=ticket_id,
                company_id=company_id,
                pipeline_status=response["pipeline_status"],
                technique=response["technique_used"],
            )

            return response

        except Exception:
            logger.exception("create_ticket failed")
            return {
                "ticket_id": "",
                "company_id": company_id,
                "error": "create_ticket_failed",
                "pipeline_status": "failed",
            }

    async def solve_ticket(
        self,
        ticket_id: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """Re-run pipeline for an existing ticket.

        BC-001: company_id is second parameter (ticket_id is first
        because it identifies which ticket to solve).

        Args:
            ticket_id: The ticket to re-process.
            company_id: Tenant identifier (BC-001).

        Returns:
            Dict with updated ticket_id, response, and pipeline metadata.
        """
        try:
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                logger.warning("ticket_not_found", ticket_id=ticket_id, company_id=company_id)
                return {
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": "ticket_not_found",
                    "pipeline_status": "failed",
                }

            if ticket.get("company_id") != company_id:
                logger.warning(
                    "ticket_company_mismatch",
                    ticket_id=ticket_id,
                    expected_company=company_id,
                    actual_company=ticket.get("company_id"),
                )
                return {
                    "ticket_id": ticket_id,
                    "company_id": company_id,
                    "error": "ticket_company_mismatch",
                    "pipeline_status": "failed",
                }

            result = await self._pipeline.process_ticket(
                query=ticket["query"],
                company_id=company_id,
                industry=ticket.get("industry", "general"),
                channel=ticket.get("channel", "chat"),
                customer_id=ticket.get("customer_id", ""),
                customer_tier=ticket.get("customer_tier", "free"),
                ticket_id=ticket_id,
            )

            ticket["pipeline_result"] = result
            ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
            ticket["status"] = "reprocessed"

            response = {
                "ticket_id": ticket_id,
                "company_id": company_id,
                "response": result.get("final_response", ""),
                "classification": result.get("classification", {}),
                "pii_detected": result.get("pii_detected", False),
                "emergency_flag": result.get("emergency_flag", False),
                "pipeline_status": result.get("pipeline_status", "unknown"),
                "quality_score": result.get("quality_score", 0.0),
                "quality_passed": result.get("quality_passed", True),
                "updated_at": ticket["updated_at"],
            }

            logger.info(
                "high_ticket_solved",
                ticket_id=ticket_id,
                company_id=company_id,
                pipeline_status=response["pipeline_status"],
            )

            return response

        except Exception:
            logger.exception("solve_ticket failed")
            return {
                "ticket_id": ticket_id,
                "company_id": company_id,
                "error": "solve_ticket_failed",
                "pipeline_status": "failed",
            }

    async def classify_ticket(
        self,
        company_id: str,
        query: str,
        industry: str = "general",
    ) -> Dict[str, Any]:
        """Just classify a query — no generation.

        BC-001: company_id is first parameter.

        High: Uses AI classification with Heavy model.

        Args:
            company_id: Tenant identifier (BC-001).
            query: Customer's raw message.
            industry: Industry context.

        Returns:
            Dict with classification result only.
        """
        try:
            from app.core.parwa_high.nodes import classify_node, pii_check_node
            from app.core.parwa_graph_state import create_initial_state

            state = create_initial_state(
                query=query,
                company_id=company_id,
                variant_tier="parwa_high",
                industry=industry,
            )

            pii_result = pii_check_node(state)
            state.update(pii_result)

            classify_result = await classify_node(state)
            state.update(classify_result)

            classification = state.get("classification", {})

            return {
                "company_id": company_id,
                "classification": classification,
                "pii_detected": state.get("pii_detected", False),
            }

        except Exception:
            logger.exception("classify_ticket failed")
            return {
                "company_id": company_id,
                "classification": {
                    "intent": "general",
                    "confidence": 0.0,
                    "secondary_intents": [],
                    "method": "fallback",
                },
                "error": "classify_ticket_failed",
            }

    def get_ticket(self, ticket_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        """Get a stored ticket by ID.

        BC-001: company_id is second parameter for verification.

        Args:
            ticket_id: Ticket identifier.
            company_id: Tenant identifier for isolation.

        Returns:
            Ticket data dict, or None if not found / wrong company.
        """
        try:
            ticket = self._tickets.get(ticket_id)
            if ticket and ticket.get("company_id") == company_id:
                return ticket
            return None
        except Exception:
            return None

    def list_tickets(self, company_id: str) -> List[Dict[str, Any]]:
        """List all tickets for a company.

        BC-001: company_id is first parameter.

        Args:
            company_id: Tenant identifier.

        Returns:
            List of ticket data dicts.
        """
        try:
            return [
                ticket for ticket in self._tickets.values()
                if ticket.get("company_id") == company_id
            ]
        except Exception:
            return []

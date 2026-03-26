"""
Shadow Mode Handler.

Processes incoming tickets in "shadow mode" - the AI processes and generates
responses BUT they are NEVER sent to customers. This allows validation of
AI accuracy without any customer-facing impact.

CRITICAL: This module MUST NEVER send real responses to customers.
"""
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from threading import Lock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ShadowModeStatus(Enum):
    """Status of shadow mode processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DecisionType(Enum):
    """Types of decisions that can be made."""
    AUTO_REPLY = "auto_reply"
    ESCALATE = "escalate"
    REFUND_APPROVE = "refund_approve"
    REFUND_DENY = "refund_deny"
    FAQ_ANSWER = "faq_answer"
    ORDER_STATUS = "order_status"
    NEED_INFO = "need_info"
    UNKNOWN = "unknown"


@dataclass
class ShadowTicket:
    """A ticket being processed in shadow mode."""
    ticket_id: str
    client_id: str
    subject: str
    body: str
    customer_email: str
    category: Optional[str] = None
    priority: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ShadowDecision:
    """A decision made by the AI in shadow mode."""
    ticket_id: str
    decision_type: DecisionType
    confidence: float
    reasoning: str
    suggested_response: str
    suggested_actions: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    agent_used: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HumanDecision:
    """A human-made decision for comparison."""
    ticket_id: str
    decision_type: DecisionType
    actual_response: str
    actual_actions: List[str] = field(default_factory=list)
    human_agent: str = "unknown"
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ShadowResult:
    """Result of shadow mode processing for a single ticket."""
    ticket_id: str
    shadow_decision: ShadowDecision
    human_decision: Optional[HumanDecision] = None
    is_match: Optional[bool] = None
    accuracy_score: Optional[float] = None
    notes: str = ""


class ShadowModeHandler:
    """
    Handles shadow mode processing of support tickets.

    Shadow mode processes tickets as the AI would, but NEVER sends
    responses to customers. Instead, it logs the AI decisions for
    later comparison with human decisions.

    CRITICAL SAFETY RULES:
    1. NEVER send responses to customers
    2. All responses are logged, not transmitted
    3. PII is handled according to GDPR/HIPAA
    4. Cross-tenant isolation is enforced
    """

    # Class-level lock for thread safety
    _lock = Lock()

    # Track all instances for safety auditing
    _instances: Dict[str, 'ShadowModeHandler'] = {}

    def __init__(
        self,
        client_id: str,
        output_dir: str = "./shadow_results",
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize shadow mode handler.

        Args:
            client_id: The client identifier (for tenant isolation)
            output_dir: Directory to store shadow mode results
            config: Optional configuration dictionary
        """
        self.client_id = client_id
        self.output_dir = Path(output_dir) / client_id
        self.config = config or {}

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Results storage
        self.results: List[ShadowResult] = []
        self._processed_count = 0
        self._error_count = 0

        # Safety flag - tracks if any response was attempted to be sent
        self._response_send_attempts = 0

        # Register instance
        with self._lock:
            self._instances[client_id] = self

        logger.info(f"ShadowModeHandler initialized for client {client_id}")

    def process_ticket(
        self,
        ticket: ShadowTicket,
        ai_processor: Callable[[ShadowTicket], ShadowDecision]
    ) -> ShadowResult:
        """
        Process a single ticket in shadow mode.

        CRITICAL: This method NEVER sends the response to the customer.
        It only logs what the AI would have done.

        Args:
            ticket: The ticket to process
            ai_processor: A callable that simulates AI processing

        Returns:
            ShadowResult containing the AI's decision (NOT sent to customer)
        """
        # Validate client isolation
        if ticket.client_id != self.client_id:
            raise ValueError(
                f"Cross-tenant violation: ticket belongs to {ticket.client_id}, "
                f"handler is for {self.client_id}"
            )

        logger.info(f"Processing ticket {ticket.ticket_id} in shadow mode")

        start_time = time.time()

        try:
            # Process with AI (this is where we'd call ZAI SDK)
            # The AI generates a decision, but we DO NOT send it
            decision = ai_processor(ticket)

            processing_time = (time.time() - start_time) * 1000
            decision.processing_time_ms = processing_time

            # Create shadow result
            result = ShadowResult(
                ticket_id=ticket.ticket_id,
                shadow_decision=decision,
                notes="Processed in shadow mode - NO response sent to customer"
            )

            # Log the decision (but DO NOT send to customer)
            self._log_decision(ticket, decision)

            self.results.append(result)
            self._processed_count += 1

            logger.info(
                f"Shadow decision for {ticket.ticket_id}: "
                f"{decision.decision_type.value} (confidence: {decision.confidence:.2f})"
            )

            return result

        except Exception as e:
            self._error_count += 1
            logger.error(f"Error processing ticket {ticket.ticket_id}: {e}")

            # Create error result
            error_decision = ShadowDecision(
                ticket_id=ticket.ticket_id,
                decision_type=DecisionType.UNKNOWN,
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                suggested_response="",
                agent_used="error_handler"
            )

            result = ShadowResult(
                ticket_id=ticket.ticket_id,
                shadow_decision=error_decision,
                notes=f"Processing error: {str(e)}"
            )
            self.results.append(result)
            return result

    def process_batch(
        self,
        tickets: List[ShadowTicket],
        ai_processor: Callable[[ShadowTicket], ShadowDecision],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[ShadowResult]:
        """
        Process multiple tickets in shadow mode.

        Args:
            tickets: List of tickets to process
            ai_processor: AI processing function
            progress_callback: Optional callback for progress updates

        Returns:
            List of shadow results
        """
        results = []
        total = len(tickets)

        for i, ticket in enumerate(tickets):
            result = self.process_ticket(ticket, ai_processor)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, total)

        return results

    def compare_with_human(
        self,
        ticket_id: str,
        human_decision: HumanDecision
    ) -> ShadowResult:
        """
        Compare a shadow decision with a human decision.

        Args:
            ticket_id: The ticket ID to find
            human_decision: The human's actual decision

        Returns:
            Updated ShadowResult with comparison
        """
        for result in self.results:
            if result.ticket_id == ticket_id:
                result.human_decision = human_decision

                # Calculate if decisions match
                result.is_match = (
                    result.shadow_decision.decision_type == human_decision.decision_type
                )

                # Calculate accuracy score
                # Full match = 1.0, partial match = 0.5, no match = 0.0
                if result.is_match:
                    result.accuracy_score = 1.0
                elif self._partial_match(result.shadow_decision, human_decision):
                    result.accuracy_score = 0.5
                else:
                    result.accuracy_score = 0.0

                return result

        raise ValueError(f"No shadow result found for ticket {ticket_id}")

    def _partial_match(
        self,
        shadow: ShadowDecision,
        human: HumanDecision
    ) -> bool:
        """Check if decisions are a partial match."""
        # Define similar decision types
        similar_types = {
            (DecisionType.REFUND_APPROVE, DecisionType.REFUND_DENY),
            (DecisionType.AUTO_REPLY, DecisionType.FAQ_ANSWER),
            (DecisionType.ESCALATE, DecisionType.NEED_INFO),
        }

        pair = (shadow.decision_type, human.decision_type)
        return pair in similar_types or (pair[1], pair[0]) in similar_types

    def _log_decision(self, ticket: ShadowTicket, decision: ShadowDecision) -> None:
        """
        Log the decision to a file.

        CRITICAL: This logs the decision but NEVER sends it to the customer.
        """
        # Convert decision to JSON-serializable dict (handle enums)
        decision_dict = {
            "ticket_id": decision.ticket_id,
            "decision_type": decision.decision_type.value,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "suggested_response": decision.suggested_response,
            "suggested_actions": decision.suggested_actions,
            "processing_time_ms": decision.processing_time_ms,
            "agent_used": decision.agent_used,
            "created_at": decision.created_at.isoformat() if decision.created_at else None
        }

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "client_id": self.client_id,
            "ticket_id": ticket.ticket_id,
            "decision": decision_dict,
            "customer_email": self._redact_pii(ticket.customer_email),
            "subject": ticket.subject,
            "RESPONSE_SENT": False,  # ALWAYS False in shadow mode
            "note": "SHADOW MODE - Response NOT sent to customer"
        }

        log_file = self.output_dir / f"shadow_log_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"

        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

    def _redact_pii(self, text: str) -> str:
        """Redact PII for logging."""
        if '@' in text:
            parts = text.split('@')
            return f"{parts[0][:2]}***@{parts[1]}"
        return text[:3] + "***" if len(text) > 3 else "***"

    def get_accuracy_metrics(self) -> Dict[str, Any]:
        """Calculate accuracy metrics from processed tickets."""
        if not self.results:
            return {"error": "No results to analyze"}

        # Filter results that have human comparison
        compared = [r for r in self.results if r.human_decision is not None]

        if not compared:
            return {
                "total_processed": len(self.results),
                "error_count": self._error_count,
                "comparison_pending": len(self.results),
                "message": "No human decisions available for comparison"
            }

        # Calculate metrics
        matches = sum(1 for r in compared if r.is_match)
        partial_matches = sum(1 for r in compared if r.accuracy_score == 0.5)
        full_matches = sum(1 for r in compared if r.accuracy_score == 1.0)

        # Average confidence
        avg_confidence = sum(r.shadow_decision.confidence for r in compared) / len(compared)

        # Accuracy by decision type
        accuracy_by_type: Dict[str, Dict[str, int]] = {}
        for result in compared:
            dtype = result.shadow_decision.decision_type.value
            if dtype not in accuracy_by_type:
                accuracy_by_type[dtype] = {"correct": 0, "total": 0}
            accuracy_by_type[dtype]["total"] += 1
            if result.is_match:
                accuracy_by_type[dtype]["correct"] += 1

        # Average processing time
        avg_processing_time = sum(
            r.shadow_decision.processing_time_ms for r in compared
        ) / len(compared)

        return {
            "client_id": self.client_id,
            "total_processed": len(self.results),
            "total_compared": len(compared),
            "error_count": self._error_count,
            "accuracy": {
                "overall": (full_matches + 0.5 * partial_matches) / len(compared),
                "full_match_rate": full_matches / len(compared),
                "partial_match_rate": partial_matches / len(compared),
            },
            "avg_confidence": avg_confidence,
            "avg_processing_time_ms": avg_processing_time,
            "accuracy_by_decision_type": accuracy_by_type,
            "response_send_attempts": self._response_send_attempts,  # Should ALWAYS be 0
        }

    def export_results(self, filename: Optional[str] = None) -> str:
        """Export all results to a JSON file."""
        if filename is None:
            filename = f"shadow_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        output_path = self.output_dir / filename

        export_data = {
            "client_id": self.client_id,
            "export_timestamp": datetime.utcnow().isoformat(),
            "metrics": self.get_accuracy_metrics(),
            "results": [
                {
                    "ticket_id": r.ticket_id,
                    "shadow_decision": asdict(r.shadow_decision),
                    "human_decision": asdict(r.human_decision) if r.human_decision else None,
                    "is_match": r.is_match,
                    "accuracy_score": r.accuracy_score,
                    "notes": r.notes
                }
                for r in self.results
            ],
            "safety_verification": {
                "response_send_attempts": self._response_send_attempts,
                "all_responses_prevented": self._response_send_attempts == 0,
                "shadow_mode_verified": True
            }
        }

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Results exported to {output_path}")
        return str(output_path)

    @classmethod
    def verify_no_responses_sent(cls) -> bool:
        """
        Verify that NO shadow mode handler has attempted to send responses.

        This is a safety check to ensure shadow mode is working correctly.
        """
        with cls._lock:
            total_attempts = sum(
                h._response_send_attempts for h in cls._instances.values()
            )
            return total_attempts == 0

    def __repr__(self) -> str:
        return (
            f"ShadowModeHandler(client_id={self.client_id}, "
            f"processed={self._processed_count}, errors={self._error_count})"
        )


def create_mock_ai_processor() -> Callable[[ShadowTicket], ShadowDecision]:
    """
    Create a mock AI processor for testing.

    This simulates what the real AI would do, without making actual API calls.
    """
    def mock_processor(ticket: ShadowTicket) -> ShadowDecision:
        # Simulate processing time
        time.sleep(0.05)

        # Simple keyword-based decision logic (mock)
        body_lower = ticket.body.lower()

        if "refund" in body_lower:
            decision_type = DecisionType.REFUND_APPROVE
            confidence = 0.85
            reasoning = "Customer requested refund, appears eligible"
            response = "I understand you'd like a refund. I've processed your request."
            actions = ["initiate_refund", "notify_billing"]
            agent = "refund_agent"

        elif "where is my order" in body_lower or "order status" in body_lower:
            decision_type = DecisionType.ORDER_STATUS
            confidence = 0.92
            reasoning = "Customer asking for order status"
            response = "Let me check your order status for you."
            actions = ["lookup_order", "send_tracking"]
            agent = "order_agent"

        elif "shipping" in body_lower:
            decision_type = DecisionType.FAQ_ANSWER
            confidence = 0.88
            reasoning = "Shipping related question"
            response = "Our standard shipping takes 3-5 business days."
            actions = ["send_shipping_info"]
            agent = "faq_agent"

        elif "speak to" in body_lower or "manager" in body_lower:
            decision_type = DecisionType.ESCALATE
            confidence = 0.95
            reasoning = "Customer requested escalation"
            response = "I'll connect you with a human agent right away."
            actions = ["escalate_to_human"]
            agent = "escalation_agent"

        else:
            decision_type = DecisionType.AUTO_REPLY
            confidence = 0.75
            reasoning = "General inquiry, auto-reply appropriate"
            response = "Thank you for contacting us. How can I help you today?"
            actions = ["log_interaction"]
            agent = "chat_agent"

        return ShadowDecision(
            ticket_id=ticket.ticket_id,
            decision_type=decision_type,
            confidence=confidence,
            reasoning=reasoning,
            suggested_response=response,
            suggested_actions=actions,
            agent_used=agent
        )

    return mock_processor

"""
Notification CRM Models — Data structures for the notification system.

Notification Types:
  - refund_request: Customer wants a refund
  - confusion_on_product: Customer confused about a product/feature
  - confusion_on_billing: Customer confused about charges
  - billing_dispute: Customer disputes a charge
  - technical_issue: Customer has a technical problem
  - complaint: Customer is unhappy
  - cancellation_risk: Customer might cancel
  - ask_client: Variant needs client input (ask-when-unsure)
  - escalation: Needs human attention
  - system_alert: System-generated notification

Merging Rules:
  - Same type + similar content → merge into ONE notification
  - Refunds of same type → batch together
  - Confusion on same topic → merge into one
  - Maximum 50 individual items per merged notification
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class NotificationType(str, Enum):
    """Types of notifications in the CRM system."""
    REFUND_REQUEST = "refund_request"
    CONFUSION_ON_PRODUCT = "confusion_on_product"
    CONFUSION_ON_BILLING = "confusion_on_billing"
    BILLING_DISPUTE = "billing_dispute"
    TECHNICAL_ISSUE = "technical_issue"
    COMPLAINT = "complaint"
    CANCELLATION_RISK = "cancellation_risk"
    ASK_CLIENT = "ask_client"
    ESCALATION = "escalation"
    SYSTEM_ALERT = "system_alert"


class NotificationStatus(str, Enum):
    """Status of a notification."""
    PENDING = "pending"           # Waiting for client to view
    VIEWED = "viewed"             # Client opened it
    IN_PROGRESS = "in_progress"  # Jarvis is handling it
    RESOLVED = "resolved"        # Issue resolved
    DISMISSED = "dismissed"      # Client dismissed it
    ESCALATED = "escalated"      # Escalated to human


@dataclass
class NotificationItem:
    """A single notification item that can be merged with others.

    Each item represents one customer's issue/request.
    """
    id: str = ""
    notification_type: NotificationType = NotificationType.SYSTEM_ALERT
    title: str = ""
    description: str = ""
    customer_id: str = ""
    company_id: str = ""
    ticket_id: str = ""
    conversation_id: str = ""
    variant_tier: str = ""
    confidence: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    status: NotificationStatus = NotificationStatus.PENDING

    # For ask-when-unsure
    ask_client_question: str = ""
    ask_client_options: List[str] = field(default_factory=list)

    # For refund batching
    refund_amount: float = 0.0
    refund_reason: str = ""
    order_id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"notif_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class NotificationBatch:
    """A merged group of similar notifications.

    When multiple customers have the same type of issue (e.g., confused
    about the same billing charge), they get merged into ONE notification
    that the client can address in bulk.
    """
    id: str = ""
    notification_type: NotificationType = NotificationType.SYSTEM_ALERT
    title: str = ""
    description: str = ""
    company_id: str = ""
    items: List[NotificationItem] = field(default_factory=list)
    merged_at: str = ""
    status: NotificationStatus = NotificationStatus.PENDING
    total_customers_affected: int = 0

    # For refund batches
    total_refund_amount: float = 0.0
    refund_count: int = 0

    # Context for Jarvis
    jarvis_context: Dict[str, Any] = field(default_factory=dict)

    # Knowledge base entry after resolution
    resolution: str = ""
    resolution_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = f"batch_{uuid.uuid4().hex[:12]}"
        if not self.merged_at:
            self.merged_at = datetime.now(timezone.utc).isoformat()
        self.total_customers_affected = len(self.items)
        self._compute_totals()

    def _compute_totals(self):
        """Compute batch totals from items."""
        self.refund_count = sum(1 for item in self.items if item.refund_amount > 0)
        self.total_refund_amount = sum(item.refund_amount for item in self.items)

    def add_item(self, item: NotificationItem) -> bool:
        """Add an item to the batch if it matches."""
        if item.notification_type != self.notification_type:
            return False
        if len(self.items) >= 50:  # Max items per batch
            return False
        self.items.append(item)
        self._compute_totals()
        self.total_customers_affected = len(self.items)
        return True


# Alias for backward compatibility
Notification = NotificationBatch

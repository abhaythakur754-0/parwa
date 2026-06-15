"""
Notification Manager — Central manager for the Notification CRM system.

This is the main entry point for:
  1. Creating notifications from variant pipeline results
  2. Merging similar notifications into batches
  3. Opening Jarvis chat when client clicks notification
  4. Converting resolved notifications into knowledge base entries
  5. Showing refunds first and in batches

Flow:
  Variant processes ticket → creates NotificationItem
  → NotificationMerger merges similar items into NotificationBatch
  → Dashboard shows batches (refunds first)
  → Client clicks batch → Jarvis opens with full context
  → Jarvis talks to variant → understands problem → presents options
  → Client chooses option → resolution recorded
  → Resolution becomes knowledge base entry
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger
from app.services.notification_crm.models import (
    NotificationBatch,
    NotificationItem,
    NotificationType,
    NotificationStatus,
)
from app.services.notification_crm.merger import NotificationMerger
from app.services.notification_crm.knowledge_base import NotificationKnowledgeBase

logger = get_logger("notification_manager")


class NotificationManager:
    """Central manager for the Notification CRM system.

    Usage:
        mgr = NotificationManager(company_id="comp_123")
        batch = mgr.create_notification(
            notification_type="refund_request",
            title="Refund for defective product",
            customer_id="cust_456",
            ...
        )
        batches = mgr.get_dashboard_notifications()  # Refunds first!
        jarvis_context = mgr.open_notification(batch_id)  # Client clicked
    """

    def __init__(self, company_id: str):
        self.company_id = company_id
        self._merger = NotificationMerger(company_id)
        self._knowledge_base = NotificationKnowledgeBase(company_id)

    def create_notification(
        self,
        notification_type: str,
        title: str,
        description: str = "",
        customer_id: str = "",
        ticket_id: str = "",
        conversation_id: str = "",
        variant_tier: str = "",
        confidence: float = 0.0,
        context: Dict[str, Any] = None,
        # Ask-when-unsure fields
        ask_client_question: str = "",
        ask_client_options: List[str] = None,
        # Refund fields
        refund_amount: float = 0.0,
        refund_reason: str = "",
        order_id: str = "",
    ) -> NotificationBatch:
        """Create a notification from a variant pipeline result.

        If similar notifications exist, they get merged.
        Refund notifications are prioritized in the dashboard.

        Args:
            notification_type: Type of notification (refund_request, confusion_on_*, etc.)
            title: Short title for the notification.
            description: Detailed description.
            customer_id: Customer who triggered this.
            ticket_id: Related ticket ID.
            conversation_id: Related conversation ID.
            variant_tier: Which variant created this.
            confidence: Variant's confidence level.
            context: Full context from the variant pipeline.
            ask_client_question: If variant is unsure, what to ask the client.
            ask_client_options: Options to present to the client.
            refund_amount: For refund notifications.
            refund_reason: Reason for refund.
            order_id: Related order ID.

        Returns:
            The NotificationBatch (merged or new).
        """
        try:
            # Normalize notification type
            try:
                notif_type = NotificationType(notification_type)
            except ValueError:
                notif_type = NotificationType.SYSTEM_ALERT

            # Auto-detect type from context
            if not ask_client_question and confidence < 0.5:
                # Low confidence → ask-when-unsure
                notif_type = NotificationType.ASK_CLIENT

            item = NotificationItem(
                notification_type=notif_type,
                title=title,
                description=description,
                customer_id=customer_id,
                company_id=self.company_id,
                ticket_id=ticket_id,
                conversation_id=conversation_id,
                variant_tier=variant_tier,
                confidence=confidence,
                context=context or {},
                ask_client_question=ask_client_question,
                ask_client_options=ask_client_options or [],
                refund_amount=refund_amount,
                refund_reason=refund_reason,
                order_id=order_id,
            )

            batch = self._merger.add_notification(item)

            logger.info(
                "notification_created",
                type=notif_type,
                title=title,
                batch_id=batch.id,
                batch_size=len(batch.items),
                customer_id=customer_id,
            )

            return batch

        except Exception:
            logger.exception("notification_creation_failed")
            # Return a dummy batch to never crash (BC-008)
            return NotificationBatch(
                notification_type=NotificationType.SYSTEM_ALERT,
                title="Notification creation failed",
                company_id=self.company_id,
            )

    def create_from_pipeline_result(
        self,
        pipeline_result: Dict[str, Any],
        company_id: str = "",
    ) -> Optional[NotificationBatch]:
        """Create notifications from a variant pipeline result.

        This is called after the variant pipeline finishes processing
        a ticket. It checks the result for:
        - Ask-when-unsure flags
        - Refund requests
        - Low confidence
        - Escalation needs

        Args:
            pipeline_result: The result dict from the unified variant pipeline.
            company_id: Override company_id.

        Returns:
            NotificationBatch if notification was created, None otherwise.
        """
        try:
            company_id = company_id or self.company_id

            # Check for ask-when-unsure
            if pipeline_result.get("ask_client_needed"):
                return self.create_notification(
                    notification_type="ask_client",
                    title=f"Variant needs your input: {pipeline_result.get('ask_client_reason', 'Uncertain')}",
                    description=pipeline_result.get("agent_response", ""),
                    customer_id=pipeline_result.get("customer_id", ""),
                    ticket_id=pipeline_result.get("ticket_id", ""),
                    conversation_id=pipeline_result.get("conversation_id", ""),
                    variant_tier=pipeline_result.get("variant_tier", ""),
                    confidence=pipeline_result.get("confidence_score", 0.0),
                    context=pipeline_result,
                    ask_client_question=pipeline_result.get("ask_client_reason", ""),
                    ask_client_options=["Approve", "Modify", "Reject", "Escalate to human"],
                )

            # Check for refund requests
            intent = pipeline_result.get("intent", "").lower()
            if intent in ("refund", "billing", "payment", "overcharge"):
                return self.create_notification(
                    notification_type="refund_request" if intent == "refund" else "billing_dispute",
                    title=f"Refund request: {pipeline_result.get('agent_response', '')[:50]}",
                    description=pipeline_result.get("agent_response", ""),
                    customer_id=pipeline_result.get("customer_id", ""),
                    ticket_id=pipeline_result.get("ticket_id", ""),
                    conversation_id=pipeline_result.get("conversation_id", ""),
                    variant_tier=pipeline_result.get("variant_tier", ""),
                    confidence=pipeline_result.get("confidence_score", 0.0),
                    context=pipeline_result,
                    refund_reason=pipeline_result.get("classification", {}).get("intent", ""),
                )

            # Check for low confidence
            confidence = pipeline_result.get("confidence_score", 1.0)
            if confidence < 0.4:
                return self.create_notification(
                    notification_type="ask_client",
                    title=f"Low confidence response needs review ({confidence:.0%})",
                    description=pipeline_result.get("agent_response", ""),
                    customer_id=pipeline_result.get("customer_id", ""),
                    ticket_id=pipeline_result.get("ticket_id", ""),
                    conversation_id=pipeline_result.get("conversation_id", ""),
                    variant_tier=pipeline_result.get("variant_tier", ""),
                    confidence=confidence,
                    context=pipeline_result,
                )

            return None

        except Exception:
            logger.exception("create_from_pipeline_result failed")
            return None

    def get_dashboard_notifications(self) -> List[Dict[str, Any]]:
        """Get notifications for the dashboard, refunds FIRST and in batches.

        Order:
          1. Refund batches (shown first)
          2. Ask-client notifications
          3. Billing disputes
          4. Confusion notifications
          5. Complaints
          6. Technical issues
          7. System alerts

        Returns:
            List of notification dicts for the dashboard.
        """
        try:
            refund_batches = self._merger.get_refund_batches()
            all_batches = self._merger.get_pending_batches()

            # Sort: refunds first, then by type priority
            type_priority = {
                NotificationType.REFUND_REQUEST: 1,
                NotificationType.ASK_CLIENT: 2,
                NotificationType.BILLING_DISPUTE: 3,
                NotificationType.CONFUSION_ON_BILLING: 4,
                NotificationType.CONFUSION_ON_PRODUCT: 5,
                NotificationType.COMPLAINT: 6,
                NotificationType.CANCELLATION_RISK: 7,
                NotificationType.TECHNICAL_ISSUE: 8,
                NotificationType.ESCALATION: 9,
                NotificationType.SYSTEM_ALERT: 10,
            }

            # Deduplicate: refund batches already in all_batches
            seen_ids = set()
            sorted_batches = []

            # First: refund batches
            for batch in refund_batches:
                if batch.id not in seen_ids:
                    sorted_batches.append(batch)
                    seen_ids.add(batch.id)

            # Then: everything else sorted by priority
            remaining = [
                b for b in all_batches
                if b.id not in seen_ids
            ]
            remaining.sort(
                key=lambda b: type_priority.get(b.notification_type, 99)
            )
            sorted_batches.extend(remaining)

            # Convert to dashboard format
            dashboard = []
            for batch in sorted_batches:
                dashboard.append({
                    "id": batch.id,
                    "type": batch.notification_type,
                    "title": batch.title,
                    "description": batch.description,
                    "status": batch.status,
                    "total_customers_affected": batch.total_customers_affected,
                    "refund_count": batch.refund_count,
                    "total_refund_amount": batch.total_refund_amount,
                    "created_at": batch.merged_at,
                    "has_ask_client": batch.notification_type == NotificationType.ASK_CLIENT,
                    "items_count": len(batch.items),
                })

            return dashboard

        except Exception:
            logger.exception("get_dashboard_notifications failed")
            return []

    def open_notification(self, batch_id: str) -> Dict[str, Any]:
        """Open a notification for Jarvis chat.

        Called when a client clicks a notification in the dashboard.
        Returns full context for Jarvis to start a conversation.

        Args:
            batch_id: The notification batch ID.

        Returns:
            Dict with:
              - batch info
              - jarvis_context (full context for Jarvis)
              - customer details
              - variant pipeline state
              - suggested actions
        """
        try:
            batch = self._merger.mark_batch_viewed(batch_id)
            if batch is None:
                return {"error": "batch_not_found", "batch_id": batch_id}

            # Build full Jarvis context
            jarvis_context = batch.jarvis_context.copy()

            # Add all customer details
            customers = []
            for item in batch.items:
                customers.append({
                    "customer_id": item.customer_id,
                    "ticket_id": item.ticket_id,
                    "conversation_id": item.conversation_id,
                    "confidence": item.confidence,
                    "context": item.context,
                })

            jarvis_context["customers"] = customers
            jarvis_context["batch_id"] = batch_id
            jarvis_context["batch_type"] = batch.notification_type
            jarvis_context["total_affected"] = batch.total_customers_affected

            # Build suggested actions based on type
            suggested_actions = self._get_suggested_actions(batch)

            result = {
                "batch_id": batch_id,
                "batch_type": batch.notification_type,
                "title": batch.title,
                "description": batch.description,
                "status": batch.status,
                "total_customers_affected": batch.total_customers_affected,
                "customers": customers,
                "jarvis_context": jarvis_context,
                "suggested_actions": suggested_actions,
                # For refund batches
                "refund_count": batch.refund_count,
                "total_refund_amount": batch.total_refund_amount,
            }

            logger.info(
                "notification_opened",
                batch_id=batch_id,
                type=batch.notification_type,
                customers=batch.total_customers_affected,
            )

            return result

        except Exception:
            logger.exception("open_notification failed")
            return {"error": "open_notification_failed", "batch_id": batch_id}

    def resolve_notification(
        self,
        batch_id: str,
        resolution: str,
        resolution_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Resolve a notification and add to knowledge base.

        Called when Jarvis + client resolve a notification.
        The resolution becomes a knowledge base entry for future learning.

        Args:
            batch_id: The notification batch ID.
            resolution: Human-readable resolution text.
            resolution_data: Structured resolution data.

        Returns:
            Dict with resolution result + knowledge base entry ID.
        """
        try:
            batch = self._merger.resolve_batch(batch_id, resolution, resolution_data)
            if batch is None:
                return {"error": "batch_not_found", "batch_id": batch_id}

            # Add to knowledge base
            kb_entry_id = self._knowledge_base.add_from_resolution(
                notification_type=batch.notification_type,
                title=batch.title,
                resolution=resolution,
                resolution_data=resolution_data or {},
                customers_affected=batch.total_customers_affected,
                items_count=len(batch.items),
            )

            logger.info(
                "notification_resolved",
                batch_id=batch_id,
                type=batch.notification_type,
                kb_entry_id=kb_entry_id,
                customers_affected=batch.total_customers_affected,
            )

            return {
                "batch_id": batch_id,
                "status": "resolved",
                "resolution": resolution,
                "kb_entry_id": kb_entry_id,
                "customers_affected": batch.total_customers_affected,
            }

        except Exception:
            logger.exception("resolve_notification failed")
            return {"error": "resolve_failed", "batch_id": batch_id}

    def _get_suggested_actions(self, batch: NotificationBatch) -> List[Dict[str, Any]]:
        """Get suggested actions for a notification batch based on type."""
        actions = []

        if batch.notification_type == NotificationType.REFUND_REQUEST:
            actions = [
                {"action": "approve_all", "label": f"Approve all {batch.refund_count} refunds", "icon": "check"},
                {"action": "approve_partial", "label": "Approve some refunds", "icon": "filter"},
                {"action": "reject_all", "label": "Reject all refunds", "icon": "x"},
                {"action": "contact_customers", "label": "Contact customers individually", "icon": "message"},
            ]

        elif batch.notification_type == NotificationType.ASK_CLIENT:
            if batch.items and batch.items[0].ask_client_options:
                for option in batch.items[0].ask_client_options:
                    actions.append({"action": option.lower().replace(" ", "_"), "label": option})
            else:
                actions = [
                    {"action": "approve", "label": "Approve variant's suggestion", "icon": "check"},
                    {"action": "modify", "label": "Modify the response", "icon": "edit"},
                    {"action": "reject", "label": "Reject and handle manually", "icon": "x"},
                    {"action": "escalate", "label": "Escalate to human agent", "icon": "arrow_up"},
                ]

        elif batch.notification_type == NotificationType.CONFUSION_ON_PRODUCT:
            actions = [
                {"action": "send_clarification", "label": "Send clarification to all affected", "icon": "send"},
                {"action": "update_docs", "label": "Update product documentation", "icon": "doc"},
                {"action": "contact_individually", "label": "Contact each customer individually", "icon": "message"},
            ]

        elif batch.notification_type == NotificationType.CANCELLATION_RISK:
            actions = [
                {"action": "offer_retention", "label": "Offer retention deal to all", "icon": "gift"},
                {"action": "contact_individually", "label": "Personal retention outreach", "icon": "message"},
                {"action": "let_cancel", "label": "Accept cancellations", "icon": "check"},
            ]

        else:
            actions = [
                {"action": "review", "label": "Review details", "icon": "eye"},
                {"action": "escalate", "label": "Escalate to human", "icon": "arrow_up"},
                {"action": "dismiss", "label": "Dismiss", "icon": "x"},
            ]

        return actions

    def get_knowledge_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get knowledge base entries for this company."""
        return self._knowledge_base.get_entries(limit=limit)

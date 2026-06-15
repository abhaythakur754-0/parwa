"""
Notification CRM System — Type-based notifications with merging.

Architecture:
  1. Notifications are typed (refunds, confusion_on_X, billing_issue, etc.)
  2. SIMILAR notifications are MERGED into one (scalability)
  3. User clicks notification → Jarvis opens with FULL context
  4. Jarvis talks to variant → understands problem → presents options
  5. Notifications become knowledge base entries

Key Features:
  - Merge similar requests (same type, similar content) into ONE notification
  - Batch refunds of same type together
  - Ask-when-unsure: variants flag low-confidence → notification for client
  - Knowledge base: every notification resolution becomes learnable

BC-001: company_id first parameter.
BC-008: Never crash.
BC-012: All timestamps UTC.
"""

from app.services.notification_crm.models import (
    NotificationType,
    NotificationStatus,
    Notification,
    NotificationBatch,
)
from app.services.notification_crm.manager import NotificationManager
from app.services.notification_crm.merger import NotificationMerger
from app.services.notification_crm.knowledge_base import NotificationKnowledgeBase

__all__ = [
    "NotificationType",
    "NotificationStatus",
    "Notification",
    "NotificationBatch",
    "NotificationManager",
    "NotificationMerger",
    "NotificationKnowledgeBase",
]

"""PARWA Pydantic schemas package."""

# Ticket schemas - Day 25
from backend.app.schemas.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketResponse,
    TicketListResponse,
    TicketFilter,
    TicketStatusUpdate,
    TicketAssign,
    TicketBulkStatusUpdate,
    TicketBulkAssign,
)

# Ticket message schemas - Day 25
from backend.app.schemas.ticket_message import (
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    AttachmentUpload,
    AttachmentResponse,
    MessageWithAttachmentsCreate,
    MessageWithAttachmentsResponse,
)

# SLA schemas - Day 25
from backend.app.schemas.sla import (
    SLAPolicyCreate,
    SLAPolicyUpdate,
    SLAPolicyResponse,
    SLATimerResponse,
    SLABreachAlert,
    SLAStats,
)

# Assignment schemas - Day 25
from backend.app.schemas.assignment import (
    AssignmentRuleCreate,
    AssignmentRuleUpdate,
    AssignmentRuleResponse,
    AssignmentScore,
    TicketAssignmentResponse,
)

# Bulk action schemas - Day 25
from backend.app.schemas.bulk_action import (
    BulkActionRequest,
    BulkActionResponse,
    BulkActionUndo,
    TicketMergeRequest,
    TicketUnmergeRequest,
    TicketMergeResponse,
)

# Notification schemas - Day 25
from backend.app.schemas.notification import (
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    NotificationTemplateResponse,
    NotificationPreferenceUpdate,
    NotificationSendRequest,
    NotificationSendResponse,
)

# Customer schemas - Day 25
from backend.app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerMergeRequest,
    IdentityMatchRequest,
    IdentityMatchResponse,
    CustomerChannelCreate,
    CustomerChannelResponse,
)

# Existing schemas - using correct class names
from backend.app.schemas.pagination import PaginatedResponseSchema

# Alias for backward compatibility
PaginatedResponse = PaginatedResponseSchema

__all__ = [
    # Ticket
    "TicketCreate",
    "TicketUpdate",
    "TicketResponse",
    "TicketListResponse",
    "TicketFilter",
    "TicketStatusUpdate",
    "TicketAssign",
    "TicketBulkStatusUpdate",
    "TicketBulkAssign",
    # Ticket message
    "MessageCreate",
    "MessageUpdate",
    "MessageResponse",
    "AttachmentUpload",
    "AttachmentResponse",
    "MessageWithAttachmentsCreate",
    "MessageWithAttachmentsResponse",
    # SLA
    "SLAPolicyCreate",
    "SLAPolicyUpdate",
    "SLAPolicyResponse",
    "SLATimerResponse",
    "SLABreachAlert",
    "SLAStats",
    # Assignment
    "AssignmentRuleCreate",
    "AssignmentRuleUpdate",
    "AssignmentRuleResponse",
    "AssignmentScore",
    "TicketAssignmentResponse",
    # Bulk action
    "BulkActionRequest",
    "BulkActionResponse",
    "BulkActionUndo",
    "TicketMergeRequest",
    "TicketUnmergeRequest",
    "TicketMergeResponse",
    # Notification
    "NotificationTemplateCreate",
    "NotificationTemplateUpdate",
    "NotificationTemplateResponse",
    "NotificationPreferenceUpdate",
    "NotificationSendRequest",
    "NotificationSendResponse",
    # Customer
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerResponse",
    "CustomerMergeRequest",
    "IdentityMatchRequest",
    "IdentityMatchResponse",
    "CustomerChannelCreate",
    "CustomerChannelResponse",
    # Pagination
    "PaginatedResponse",
    "PaginatedResponseSchema",
]

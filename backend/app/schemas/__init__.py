"""PARWA Pydantic schemas package."""

# Ticket schemas - Day 25
# Assignment schemas - Day 25
from app.schemas.assignment import (
    AssignmentRuleCreate,
    AssignmentRuleResponse,
    AssignmentRuleUpdate,
    AssignmentScore,
    TicketAssignmentResponse,
)

# Bulk action schemas - Day 25
from app.schemas.bulk_action import (
    BulkActionRequest,
    BulkActionResponse,
    BulkActionUndo,
    TicketMergeRequest,
    TicketMergeResponse,
    TicketUnmergeRequest,
)

# Customer schemas - Day 25
from app.schemas.customer import (
    CustomerChannelCreate,
    CustomerChannelResponse,
    CustomerCreate,
    CustomerMergeRequest,
    CustomerResponse,
    CustomerUpdate,
    IdentityMatchRequest,
    IdentityMatchResponse,
)

# Notification schemas - Day 25
from app.schemas.notification import (
    NotificationPreferenceUpdate,
    NotificationSendRequest,
    NotificationSendResponse,
    NotificationTemplateCreate,
    NotificationTemplateResponse,
    NotificationTemplateUpdate,
)

# Existing schemas - using correct class names
from app.schemas.pagination import PaginatedResponseSchema

# SLA schemas - Day 25
from app.schemas.sla import (
    SLABreachAlert,
    SLAPolicyCreate,
    SLAPolicyResponse,
    SLAPolicyUpdate,
    SLAStats,
    SLATimerResponse,
)
from app.schemas.ticket import (
    TicketAssign,
    TicketBulkAssign,
    TicketBulkStatusUpdate,
    TicketCreate,
    TicketFilter,
    TicketListResponse,
    TicketResponse,
    TicketStatusUpdate,
    TicketUpdate,
)

# Ticket message schemas - Day 25
from app.schemas.ticket_message import (
    AttachmentResponse,
    AttachmentUpload,
    MessageCreate,
    MessageResponse,
    MessageUpdate,
    MessageWithAttachmentsCreate,
    MessageWithAttachmentsResponse,
)

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

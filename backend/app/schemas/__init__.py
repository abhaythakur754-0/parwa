"""PARWA Pydantic schemas package."""

# Ticket schemas - Day 25
from app.schemas.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketResponse,
    TicketListResponse,
    TicketFilter,
    TicketStatusUpdate,
    TicketAssign,
    TicketBulkStatusUpdate,
    TicketBulkAssign,
    PriorityDetectionResponse,
    CategoryDetectionResponse,
    PIIScanResponse,
    TicketDeleteResponse,
    TicketAttachmentResponse,
)

# Ticket message schemas - Day 25
from app.schemas.ticket_message import (
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    AttachmentUpload,
    AttachmentResponse,
    MessageWithAttachmentsCreate,
    MessageWithAttachmentsResponse,
)

# SLA schemas - Day 25
from app.schemas.sla import (
    SLAPolicyCreate,
    SLAPolicyUpdate,
    SLAPolicyResponse,
    SLATimerResponse,
    SLABreachAlert,
    SLAStats,
    SLADeleteResponse,
    SLASeedResponse,
    SLABreachedTicketsResponse,
    SLAApproachingTicketsResponse,
)

# Assignment schemas - Day 25
from app.schemas.assignment import (
    AssignmentRuleCreate,
    AssignmentRuleUpdate,
    AssignmentRuleResponse,
    AssignmentScore,
    TicketAssignmentResponse,
)

# Bulk action schemas - Day 25
from app.schemas.bulk_action import (
    BulkActionRequest,
    BulkActionResponse,
    BulkActionUndo,
    TicketMergeRequest,
    TicketUnmergeRequest,
    TicketMergeResponse,
    TicketUnmergeResponse,
    MergeHistoryResponse,
    MergeCheckResponse,
    MergeDetailResponse,
)

# Ticket lifecycle schemas - R-06
from app.schemas.ticket_lifecycle import (
    TicketEscalateResponse,
    TicketReopenResponse,
    TicketFreezeResponse,
    TicketThawResponse,
    TicketSpamMarkResponse,
    TicketSpamUnmarkResponse,
    TicketTransitionsResponse,
    StaleTicketsResponse,
    IncidentResponse,
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentNotifyResponse,
    SpamQueueResponse,
    SpamAnalyzeResponse,
)

# Notification schemas - Day 25
from app.schemas.notification import (
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    NotificationTemplateResponse,
    NotificationPreferenceUpdate,
    NotificationSendRequest,
    NotificationSendResponse,
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
    TemplateListResponse,
    TemplateCreateResponse,
    TemplateGetResponse,
    TemplateUpdateResponse,
    TemplateDeleteResponse,
    TemplateVariablesResponse,
    PreferenceUpdateResponse,
    ResetPreferencesResponse,
    DisableAllResponse,
    EnableAllResponse,
)

# Customer schemas - Day 25
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerMergeRequest,
    IdentityMatchRequest,
    IdentityMatchResponse,
    CustomerChannelCreate,
    CustomerChannelResponse,
    CustomerListResponse,
    CustomerDeleteResponse,
    CustomerTicketListResponse,
    CustomerChannelLinkResponse,
    CustomerUnlinkResponse,
    CustomerMergeResponse,
    IdentityDuplicatesResponse,
    IdentityMatchLogResponse,
    IdentityGrandfatheredResponse,
    IdentityBatchResolveResponse,
)

# Integration schemas - R-08
from app.schemas.integration import (
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    RESTConnectorCreate,
    RESTConnectorUpdate,
    RESTConnectorResponse,
    WebhookIntegrationCreate,
    WebhookIntegrationUpdate,
    WebhookIntegrationResponse,
    MCPConnectionCreate,
    MCPConnectionUpdate,
    MCPConnectionResponse,
    DBConnectionCreate,
    DBConnectionUpdate,
    DBConnectionResponse,
    EventBufferCreate,
    EventBufferUpdate,
    EventBufferResponse,
    ErrorLogCreate,
    ErrorLogUpdate,
    ErrorLogResponse,
    AuditTrailCreate,
    AuditTrailUpdate,
    AuditTrailResponse,
    OutgoingWebhookCreate,
    OutgoingWebhookUpdate,
    OutgoingWebhookResponse,
)

# Approval schemas - R-08
from app.schemas.approval import (
    ApprovalQueueCreate,
    ApprovalQueueUpdate,
    ApprovalQueueResponse,
    AutoApproveRuleCreate,
    AutoApproveRuleUpdate,
    AutoApproveRuleResponse,
    ExecutedActionCreate,
    ExecutedActionUpdate,
    ExecutedActionResponse,
    UndoLogCreate,
    UndoLogUpdate,
    UndoLogResponse,
)

# Technique schemas - R-08
from app.schemas.technique import (
    TechniqueConfigurationCreate,
    TechniqueConfigurationUpdate,
    TechniqueConfigurationResponse,
    TechniqueExecutionCreate,
    TechniqueExecutionUpdate,
    TechniqueExecutionResponse,
    TechniqueVersionCreate,
    TechniqueVersionUpdate,
    TechniqueVersionResponse,
)

# Channel schemas - R-06
from app.schemas.channel import (
    ChannelConfigUpdateResponse,
    ChannelTestResponse,
    ChannelFormatMessageResponse,
    ChannelFileValidationResponse,
)

# Public schemas - R-06
from app.schemas.public import (
    FeatureItem,
    PublicStatsResponse,
    IndustryItem,
)

# SMS Channel schemas - R-06
from app.schemas.sms_channel import (
    SMSConsentStatusResponse,
    SMSWebhookStatusResponse,
)

# Chat Widget schemas - R-06
from app.schemas.chat_widget import (
    ChatSessionCreateResponse,
    ChatAssignResponse,
    ChatCloseResponse,
    ChatMessageSendResponse,
    ChatTypingResponse,
    ChatMarkReadResponse,
    ChatCSATResponse,
    CannedResponseListResponse,
)

# API Key schemas
from app.schemas.api_key import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyCreatedResponse,
    APIKeyRotatedResponse,
    APIKeyRevokedResponse,
)

# Existing schemas - using correct class names
from app.schemas.pagination import PaginatedResponseSchema

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
    "PriorityDetectionResponse",
    "CategoryDetectionResponse",
    "PIIScanResponse",
    "TicketDeleteResponse",
    "TicketAttachmentResponse",
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
    "TicketUnmergeResponse",
    "MergeHistoryResponse",
    "MergeCheckResponse",
    "MergeDetailResponse",
    # Ticket lifecycle (R-06)
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
    # Integration (R-08)
    "IntegrationCreate",
    "IntegrationUpdate",
    "IntegrationResponse",
    "RESTConnectorCreate",
    "RESTConnectorUpdate",
    "RESTConnectorResponse",
    "WebhookIntegrationCreate",
    "WebhookIntegrationUpdate",
    "WebhookIntegrationResponse",
    "MCPConnectionCreate",
    "MCPConnectionUpdate",
    "MCPConnectionResponse",
    "DBConnectionCreate",
    "DBConnectionUpdate",
    "DBConnectionResponse",
    "EventBufferCreate",
    "EventBufferUpdate",
    "EventBufferResponse",
    "ErrorLogCreate",
    "ErrorLogUpdate",
    "ErrorLogResponse",
    "AuditTrailCreate",
    "AuditTrailUpdate",
    "AuditTrailResponse",
    "OutgoingWebhookCreate",
    "OutgoingWebhookUpdate",
    "OutgoingWebhookResponse",
    # Approval (R-08)
    "ApprovalQueueCreate",
    "ApprovalQueueUpdate",
    "ApprovalQueueResponse",
    "AutoApproveRuleCreate",
    "AutoApproveRuleUpdate",
    "AutoApproveRuleResponse",
    "ExecutedActionCreate",
    "ExecutedActionUpdate",
    "ExecutedActionResponse",
    "UndoLogCreate",
    "UndoLogUpdate",
    "UndoLogResponse",
    # Technique (R-08)
    "TechniqueConfigurationCreate",
    "TechniqueConfigurationUpdate",
    "TechniqueConfigurationResponse",
    "TechniqueExecutionCreate",
    "TechniqueExecutionUpdate",
    "TechniqueExecutionResponse",
    "TechniqueVersionCreate",
    "TechniqueVersionUpdate",
    "TechniqueVersionResponse",
    # Customer (R-06 additions)
    "CustomerListResponse",
    "CustomerDeleteResponse",
    "CustomerTicketListResponse",
    "CustomerChannelLinkResponse",
    "CustomerUnlinkResponse",
    "CustomerMergeResponse",
    "IdentityDuplicatesResponse",
    "IdentityMatchLogResponse",
    "IdentityGrandfatheredResponse",
    "IdentityBatchResolveResponse",
    # SLA (R-06 additions)
    "SLADeleteResponse",
    "SLASeedResponse",
    "SLABreachedTicketsResponse",
    "SLAApproachingTicketsResponse",
    # Notification (R-06 additions)
    "NotificationListResponse",
    "UnreadCountResponse",
    "MarkReadResponse",
    "TemplateListResponse",
    "TemplateCreateResponse",
    "TemplateGetResponse",
    "TemplateUpdateResponse",
    "TemplateDeleteResponse",
    "TemplateVariablesResponse",
    "PreferenceUpdateResponse",
    "ResetPreferencesResponse",
    "DisableAllResponse",
    "EnableAllResponse",
    # Channel (R-06)
    "ChannelConfigUpdateResponse",
    "ChannelTestResponse",
    "ChannelFormatMessageResponse",
    "ChannelFileValidationResponse",
    # Public (R-06)
    "FeatureItem",
    "PublicStatsResponse",
    "IndustryItem",
    # SMS Channel (R-06)
    "SMSConsentStatusResponse",
    "SMSWebhookStatusResponse",
    # Chat Widget (R-06)
    "ChatSessionCreateResponse",
    "ChatAssignResponse",
    "ChatCloseResponse",
    "ChatMessageSendResponse",
    "ChatTypingResponse",
    "ChatMarkReadResponse",
    "ChatCSATResponse",
    "CannedResponseListResponse",
    # API Key
    "APIKeyCreate",
    "APIKeyResponse",
    "APIKeyCreatedResponse",
    "APIKeyRotatedResponse",
    "APIKeyRevokedResponse",
]

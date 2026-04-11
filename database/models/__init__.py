"""Database models registry."""

from database.models.core import (  # noqa: F401
    APIKey,
    Agent,
    BackupCode,
    Company,
    CompanySetting,
    EmergencyState,
    MFASecret,
    OAuthAccount,
    PasswordResetToken,
    RefreshToken,
    User,
    UserNotificationPreference,
    VerificationToken,
)
from database.models.core_rate_limit import (  # noqa: F401
    RateLimitEvent,
)
from database.models.phone_otp import (  # noqa: F401
    PhoneOTP,
)
from database.models.api_key_audit import (  # noqa: F401
    APIKeyAuditLog,
)
from database.models.webhook_event import (  # noqa: F401
    WebhookEvent,
)
from database.models.tickets import *  # noqa: F401, F403
from database.models.ai_pipeline import *  # noqa: F401, F403
from database.models.integration import *  # noqa: F401, F403
from database.models.billing import *  # noqa: F401, F403
from database.models.billing_extended import (  # noqa: F401
    ClientRefund,
    PaymentMethod,
    UsageRecord,
    VariantLimit,
    IdempotencyKey,
    WebhookSequence,
    ProrationAudit,
    PaymentFailure,
    get_variant_limits,
    calculate_overage,
)
from database.models.onboarding import *  # noqa: F401, F403
from database.models.user_details import UserDetails  # noqa: F401
from database.models.analytics import *  # noqa: F401, F403
from database.models.training import *  # noqa: F401, F403
from database.models.approval import *  # noqa: F401, F403
from database.models.remaining import *  # noqa: F401, F403
from database.models.technique import *  # noqa: F401, F403
from database.models.jarvis import (  # noqa: F401
    JarvisSession,
    JarvisMessage,
    JarvisKnowledgeUsed,
    JarvisActionTicket,
)

"""
Auth services — organized domain folder.

Contains 10 service modules.
Re-exports from the flat services/ directory for backward compatibility.
"""

from app.services.auth_service import *  # noqa: F401,F403
from app.services.mfa_service import *  # noqa: F401,F403
from app.services.password_reset_service import *  # noqa: F401,F403
from app.services.session_service import *  # noqa: F401,F403
from app.services.api_key_service import *  # noqa: F401,F403
from app.services.verification_service import *  # noqa: F401,F403
from app.services.business_email_otp_service import *  # noqa: F401,F403
from app.services.phone_otp_service import *  # noqa: F401,F403
from app.services.identity_resolution_service import *  # noqa: F401,F403
from app.services.entitlement_middleware import *  # noqa: F401,F403


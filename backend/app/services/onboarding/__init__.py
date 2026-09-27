"""
Onboarding services — organized domain folder.

Contains 2 service modules.
Re-exports from the flat services/ directory for backward compatibility.
"""

from app.services.onboarding_service import *  # noqa: F401,F403
from app.services.user_details_service import *  # noqa: F401,F403


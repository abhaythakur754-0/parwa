"""
Week 4 test conftest — Additional mocks for security fix tests.

The root conftest.py mocks 'shared' and 'shared.knowledge_base.*' but
does NOT mock 'shared.utils.*' submodules which are needed by
app.schemas.pagination and other modules imported transitively by
app.api.* modules.

This conftest fills that gap by:
1. Mocking all shared.utils.* submodules
2. Pre-importing app.api.deps and app.exceptions to trigger the full
   import chain while the mocks are in place, so test files don't hit
   ModuleNotFoundError.
"""

import sys
import types
import os
from unittest.mock import MagicMock

# ═══ Ensure test environment ═══
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32c")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-32c")
os.environ.setdefault("DATA_ENCRYPTION_KEY", "test-encryption-key-for-testing-32")
os.environ.setdefault("ENVIRONMENT", "test")

# ════════════════════════════════════════════════════════════
# Phase 1: Mock all shared.utils.* submodules
# ════════════════════════════════════════════════════════════

_FAKE_SHARED_UTILS = types.ModuleType("shared.utils")
_FAKE_SHARED_UTILS_PAGINATION = types.ModuleType("shared.utils.pagination")
_FAKE_SHARED_UTILS_VALIDATORS = types.ModuleType("shared.utils.validators")
_FAKE_SHARED_UTILS_DATETIME = types.ModuleType("shared.utils.datetime")
_FAKE_SHARED_UTILS_SECURITY = types.ModuleType("shared.utils.security")
_FAKE_SHARED_UTILS_TOKEN_ENCRYPTION = types.ModuleType("shared.utils.token_encryption")
_FAKE_SHARED_UTILS_TOKEN = types.ModuleType("shared.utils.token")

# Populate pagination attributes
_FAKE_SHARED_UTILS_PAGINATION.DEFAULT_PAGE_SIZE = 25
_FAKE_SHARED_UTILS_PAGINATION.MAX_PAGE_SIZE = 100
_FAKE_SHARED_UTILS_PAGINATION.MAX_OFFSET = 10000
_FAKE_SHARED_UTILS_PAGINATION.paginate = MagicMock()
_FAKE_SHARED_UTILS_PAGINATION.PaginatedResponse = MagicMock

# Populate validators attributes
_FAKE_SHARED_UTILS_VALIDATORS.validate_email = lambda x: x
_FAKE_SHARED_UTILS_VALIDATORS.validate_phone = lambda x: x

# Populate datetime attributes
_FAKE_SHARED_UTILS_DATETIME.format_duration = lambda x: x
_FAKE_SHARED_UTILS_DATETIME.format_datetime = lambda x: x
_FAKE_SHARED_UTILS_DATETIME.utcnow = MagicMock()

# Populate security attributes
_FAKE_SHARED_UTILS_SECURITY.hash_password = MagicMock()
_FAKE_SHARED_UTILS_SECURITY.verify_password = MagicMock()
_FAKE_SHARED_UTILS_SECURITY.mask_sensitive = lambda x: x

# Populate token_encryption attributes
_FAKE_SHARED_UTILS_TOKEN_ENCRYPTION.encrypt = MagicMock()
_FAKE_SHARED_UTILS_TOKEN_ENCRYPTION.decrypt = MagicMock()
_FAKE_SHARED_UTILS_TOKEN_ENCRYPTION.encrypt_token = MagicMock()
_FAKE_SHARED_UTILS_TOKEN_ENCRYPTION.decrypt_token = MagicMock()

# Populate token attributes
_FAKE_SHARED_UTILS_TOKEN.create_token = MagicMock()
_FAKE_SHARED_UTILS_TOKEN.verify_token = MagicMock()

# Register all shared.utils.* mocks
for mod_name, mod in [
    ("shared.utils", _FAKE_SHARED_UTILS),
    ("shared.utils.pagination", _FAKE_SHARED_UTILS_PAGINATION),
    ("shared.utils.validators", _FAKE_SHARED_UTILS_VALIDATORS),
    ("shared.utils.datetime", _FAKE_SHARED_UTILS_DATETIME),
    ("shared.utils.security", _FAKE_SHARED_UTILS_SECURITY),
    ("shared.utils.token_encryption", _FAKE_SHARED_UTILS_TOKEN_ENCRYPTION),
    ("shared.utils.token", _FAKE_SHARED_UTILS_TOKEN),
]:
    sys.modules.setdefault(mod_name, mod)

# ════════════════════════════════════════════════════════════
# Phase 2: Pre-import app modules that have deep import chains
# ════════════════════════════════════════════════════════════
# This triggers the full import chain while all mocks are in place.
# The root conftest.py has already mocked database.*, app.logger,
# app.core.sentiment_engine, app.core.graceful_escalation, etc.
try:
    import app.exceptions  # noqa: F401
    import app.api.deps  # noqa: F401
except ImportError:
    # If there are still missing modules, log but don't fail
    # (individual tests will handle their own imports)
    pass

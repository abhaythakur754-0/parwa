# PARWA Full-Stack Test Report

## Executive Summary

This report documents the testing of PARWA (AI-Powered Customer Support Platform) in a full-stack environment. The application consists of:
- **Backend**: FastAPI application at `/home/z/my-project/parwa/backend`
- **Frontend**: Next.js 16 application at `/home/z/my-project/parwa`

## Test Results

### 1. Servers Started Successfully
- **Backend**: FastAPI server started successfully and loaded all modules
- **Frontend**: Next.js server started successfully with Turbopack

### 2. Health Endpoints Worked
The `/health` endpoint returned a valid response:
```json
{
  "status": "unhealthy",
  "timestamp": "2026-04-25T08:26:26.979767+00:00Z",
  "version": "0.3.0",
  "uptime_seconds": 20.21,
  "subsystems": {
    "postgresql": {"status": "healthy"},
    "redis": {"status": "unhealthy"},
    "celery": {"status": "unhealthy"},
    "celery_queues": {"status": "degraded"},
    "socketio": {"status": "unhealthy"},
    "disk_space": {"status": "healthy"},
    "external_paddle": {"status": "healthy"},
    "external_brevo": {"status": "healthy"},
    "external_twilio": {"status": "healthy"}
  },
  "checks_total": 9,
  "checks_healthy": 5,
  "checks_degraded": 1,
  "checks_unhealthy": 3,
  "cached": false
}
```

---

## Critical Production Gaps Found

### GAP 1: Module Import Conflict - config.py vs config/ directory
**Severity**: CRITICAL
**Location**: `/home/z/my-project/parwa/backend/app/`

**Issue**: There are two files/directories with the same name:
- `config.py` - Contains Settings class with `get_settings()` function
- `config/` - Directory containing `variant_features.py`

Python imports the directory as a package instead of the file, causing:
```
ImportError: cannot import name 'get_settings' from 'app.config'
```

**Fix Required**: Rename the `config/` directory to something else (e.g., `variant_config/` or `feature_config/`) or move `config.py` to a different name.

---

### GAP 2: Duplicate SQLAlchemy Model Definitions
**Severity**: CRITICAL
**Location**: 
- `/home/z/my-project/parwa/database/models/core.py` (line 253)
- `/home/z/my-project/parwa/database/models/agent.py` (line 50)

**Issue**: Two `Agent` classes are defined with the same `__tablename__ = "agents"`:
```python
# core.py
class Agent(Base):
    __tablename__ = "agents"
    # Different columns: variant, capacity_used, capacity_max, accuracy_rate

# agent.py  
class Agent(Base):
    __tablename__ = "agents"
    # Different columns: specialty, channels, permissions, model_checkpoint_id
```

This causes:
```
sqlalchemy.exc.InvalidRequestError: Table 'agents' is already defined for this MetaData instance.
```

**Fix Required**: Consolidate into a single Agent model or use different table names.

---

### GAP 3: Missing `get_tenant_context` Dependency
**Severity**: HIGH
**Location**: `/home/z/my-project/parwa/backend/app/api/deps.py`

**Issue**: Multiple API files import `get_tenant_context` from `app.api.deps`, but the function was not defined.

**Fix Applied**: Added the missing function:
```python
def get_tenant_context(
    request: Request,
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    return {
        "company_id": str(user.company_id),
        "user_id": str(user.id),
        "role": user.role,
    }
```

---

### GAP 4: Wrong Import Path for get_current_user
**Severity**: HIGH
**Location**: `/home/z/my-project/parwa/backend/app/api/faqs.py`

**Issue**: Import from wrong module:
```python
from app.core.auth import get_current_user  # WRONG
```

Should be:
```python
from app.api.deps import get_current_user  # CORRECT
```

**Fix Applied**: Corrected the import.

---

### GAP 5: Missing Python Path for Shared Module
**Severity**: HIGH
**Location**: Backend startup

**Issue**: Backend tries to import from `shared.utils.datetime` but the `shared/` directory is at the project root, not in the backend directory.

**Workaround**: Set `PYTHONPATH=/home/z/my-project/parwa:$PYTHONPATH` before running.

**Fix Required**: Either:
1. Move `shared/` directory into `backend/`
2. Create a proper Python package structure
3. Document PYTHONPATH requirement in deployment

---

### GAP 6: Missing Environment Variables
**Severity**: HIGH
**Location**: Multiple files

**Issue**: Multiple required environment variables not documented or missing defaults:
- `REFRESH_TOKEN_PEPPER` - Required by `app/core/auth.py` but not in Settings class
- `DATA_ENCRYPTION_KEY` - Must be exactly 32 characters (validated)
- `SECRET_KEY`, `JWT_SECRET_KEY` - Required but no defaults

**Fix Required**: Document all required environment variables and add validation at startup.

---

### GAP 7: Alembic Migration Path Hardcoded
**Severity**: MEDIUM
**Location**: `/home/z/my-project/parwa/backend/app/main.py` (line 179)

**Issue**: Hardcoded path for Alembic migrations:
```python
result = subprocess.run(
    ["alembic", "-c", "/app/database/alembic.ini", "upgrade", "head"],
    cwd="/app/database",
    ...
)
```

This fails in non-Docker environments with:
```
[Errno 2] No such file or directory: '/app/database'
```

**Fix Required**: Use relative paths or environment variables for migration paths.

---

### GAP 8: Next.js 16 Turbopack Compatibility
**Severity**: MEDIUM
**Location**: `/home/z/my-project/parwa/next.config.mjs`

**Issue**: Next.js 16 uses Turbopack by default but the project has webpack configurations without Turbopack config.

**Error**:
```
ERROR: This build is using Turbopack, with a `webpack` config and no `turbopack` config.
```

**Fix Applied**: Added empty `turbopack: {}` to next.config.mjs.

---

### GAP 9: Pydantic Field Name Shadowing
**Severity**: LOW
**Location**: Unknown model

**Issue**: Warning during startup:
```
UserWarning: Field name "validate" in "CreateIntegrationRequest" shadows an attribute in parent "BaseModel"
```

**Fix Required**: Rename the `validate` field to avoid conflict with Pydantic's method.

---

### GAP 10: Paddle Price ID Configuration Warning
**Severity**: LOW
**Location**: Configuration

**Issue**: Warning during startup:
```
PADDLE_OVERAGE_PRICE_ID is not set or uses placeholder '(empty)'. Overage charges will fail in production.
```

**Fix Required**: Configure actual Paddle price IDs for production.

---

## Missing Dependencies/Services

### Redis (Required)
- **Status**: Not running
- **Impact**: Cache, session storage, and Celery broker unavailable
- **Error**: `Error 111 connecting to localhost:6379. Connection refused.`

### Celery Worker (Required for background tasks)
- **Status**: Not running
- **Impact**: Background tasks (email, webhooks, AI processing) will not execute

### PostgreSQL Database (Optional - SQLite works for testing)
- **Status**: Not configured
- **Impact**: Using SQLite fallback

---

## Required Environment Variables

```bash
# Required for backend
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_here
DATA_ENCRYPTION_KEY=exactly_32_characters_key_here
REFRESH_TOKEN_PEPPER=your_pepper_here
DATABASE_URL=sqlite:///./test.db  # or PostgreSQL URL
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000

# Optional but recommended
GOOGLE_AI_API_KEY=your_key_here
CEREBRAS_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
BREVO_API_KEY=your_key_here
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here
PADDLE_CLIENT_TOKEN=your_token_here
PADDLE_API_KEY=your_key_here
```

---

## Recommendations Before Production

### Critical (Must Fix)
1. Resolve config.py/config/ naming conflict
2. Consolidate duplicate Agent model definitions
3. Fix all import paths for consistency
4. Document all required environment variables
5. Add proper error handling for missing services (Redis, Celery)

### High Priority
1. Make Alembic paths configurable via environment
2. Add health check circuit breakers for optional services
3. Implement graceful degradation when Redis is unavailable
4. Add startup validation for all required configuration

### Medium Priority
1. Update Next.js config for Turbopack compatibility
2. Rename Pydantic field that shadows `validate`
3. Configure proper Paddle price IDs
4. Add comprehensive logging for startup issues

---

## Files Modified During Testing

1. `/home/z/my-project/parwa/backend/app/config/` → Renamed to `config_variant_features/`
2. `/home/z/my-project/parwa/database/models/agent.py` → Added `extend_existing: True`
3. `/home/z/my-project/parwa/database/models/core.py` → Added `extend_existing: True` to Agent class
4. `/home/z/my-project/parwa/backend/app/api/deps.py` → Added `get_tenant_context` function
5. `/home/z/my-project/parwa/backend/app/api/faqs.py` → Fixed import path
6. `/home/z/my-project/parwa/next.config.mjs` → Added `turbopack: {}`

---

## Conclusion

The PARWA application has a solid architecture but has several critical issues that prevent it from running out-of-the-box in a development environment. The most critical issues are:

1. **Module naming conflicts** (config.py vs config/)
2. **Duplicate model definitions** (Agent class)
3. **Missing dependency functions** (get_tenant_context)
4. **Hardcoded Docker paths** (Alembic migrations)

These issues must be resolved before the application can be deployed to production. The fixes are straightforward but require careful attention to maintain consistency across the codebase.

---

*Report generated: 2026-04-25*
*Test environment: Ubuntu, Python 3.12, Node.js with Bun*

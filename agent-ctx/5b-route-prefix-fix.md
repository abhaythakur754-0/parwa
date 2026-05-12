---
Task ID: 5b
Agent: Route Prefix Fix Agent
Task: Fix BUG-3 Route Prefix Mismatch — tickets and technique_config routers are dead code

Summary:
The `api_router` in `backend/app/api/__init__.py` aggregates 12 routers but is NEVER mounted in `backend/app/main.py`. Two routers were only registered in the dead `api_router` and had no individual mount in `main.py`, making their endpoints completely unreachable.

Changes Made:
- **File**: `backend/app/main.py`
  - Added import: `from app.api.tickets import router as tickets_router` (line 74)
  - Added import: `from app.api.technique_config import router as technique_config_router` (line 75)
  - Added mount: `app.include_router(tickets_router, prefix="/api/v1", tags=["tickets"])` (line 356)
  - Added mount: `app.include_router(technique_config_router, tags=["technique-config"])` (line 357)

Route Path Verification:
- tickets.router (own prefix `/tickets`) + mount prefix `/api/v1` → `/api/v1/tickets` ✓ (matches variant_check.py ROUTE_LIMITS)
- technique_config.router (own prefix `/api/techniques/config`) + no mount prefix → `/api/techniques/config` ✓ (avoids double /api bug in api/__init__.py)

Design Decision:
- Did NOT mount api_router as a whole (would double-mount 8 already-mounted routers: health, auth, admin, api_keys, mfa, client, webhooks, public, jarvis, jarvis_cc)
- Instead individually mounted only the 2 missing routers with correct prefixes

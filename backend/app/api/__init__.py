"""
PARWA API Routes

All FastAPI routers are registered in backend/app/main.py directly.
This module no longer maintains a combined api_router — that approach
caused 80+ dead endpoints because routers added here were not
automatically included in the app.

If you add a new router:
  1. Create the router file in backend/app/api/
  2. Import it in backend/app/main.py
  3. Register it with app.include_router()

DO NOT add routers to this file — they will not be active.
"""

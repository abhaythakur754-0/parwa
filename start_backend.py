"""
Start PARWA backend for manual testing with SQLite.
Patches JSONB→JSON for SQLite compatibility before importing models.
"""
import os
import sys

# Set environment before ANY imports
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = "sqlite:////home/z/my-project/db/parwa_manual_test.db"
os.environ["SECRET_KEY"] = "dev-manual-testing-key-change-in-prod"
os.environ["JWT_SECRET_KEY"] = "dev-jwt-manual-testing-key"
os.environ["DEBUG"] = "true"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["PRICING_SIGNING_KEY"] = "dev-pricing-key-change-in-prod-32c"
os.environ["DATA_ENCRYPTION_KEY"] = "devkey_devkey_devkey_devkey_abcd"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

# ── Patch JSONB→JSON for SQLite compatibility ──
import sqlalchemy
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy.types import JSON

# Create a JSONB type that compiles as JSON on SQLite
class SQLiteJSONB(JSON):
    """JSONB that falls back to JSON on SQLite."""
    pass

# Override the PostgreSQL JSONB compiler for SQLite
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
_original_visit = SQLiteTypeCompiler.visit_JSON

def _visit_json_or_jsonb(self, type_, **kw):
    if isinstance(type_, (_JSONB, SQLiteJSONB)):
        return _original_visit(self, JSON(), **kw)
    return _original_visit(self, type_, **kw)

SQLiteTypeCompiler.visit_JSON = _visit_json_or_jsonb
# Also add visit_JSONB that redirects
SQLiteTypeCompiler.visit_JSONB = _visit_json_or_jsonb

sys.path.insert(0, "/home/z/my-project/parwa")

# Now import and run uvicorn
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  Starting PARWA Backend for Manual Testing")
    print("  Database: SQLite at /home/z/my-project/db/parwa_manual_test.db")
    print("  Login: owner@technova.com / TestPass123!")
    print("=" * 60)

    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )

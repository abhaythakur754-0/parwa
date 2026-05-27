"""
Start PARWA backend for manual testing with SQLite.
Patches JSONB→JSON for SQLite compatibility before importing models.

Works on Windows, macOS, and Linux — no Docker needed.
Usage:  python start_backend.py [port]
"""
import os
import sys
from pathlib import Path

# ── Auto-detect project root (directory where this script lives) ──
PROJECT_ROOT = str(Path(__file__).resolve().parent)

# ── SQLite database path (cross-platform) ──
DB_DIR = Path(PROJECT_ROOT) / "db"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = str(DB_DIR / "parwa_manual_test.db")

# Convert Windows backslashes to forward slashes for SQLite URL
# sqlite:///C:/Users/... works; sqlite:///C:\Users\... does NOT
DB_PATH_FWD = DB_PATH.replace("\\", "/")
# Ensure 3 slashes for absolute path: sqlite:////absolute/path (4 slashes on Unix)
if DB_PATH_FWD.startswith("/"):
    SQLITE_URL = f"sqlite:///{DB_PATH_FWD}"
else:
    # Windows: C:/Users/... → sqlite:///C:/Users/...
    SQLITE_URL = f"sqlite:///{DB_PATH_FWD}"

# Set environment before ANY imports
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = SQLITE_URL
os.environ["SECRET_KEY"] = "dev-manual-testing-key-change-in-prod"
os.environ["JWT_SECRET_KEY"] = "dev-jwt-manual-testing-key"
os.environ["DEBUG"] = "true"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["REDIS_URL"] = ""  # No Redis needed for dev
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

# ── Add BOTH paths to sys.path ──
# 1. Project root  → so 'backend' package is importable
# 2. backend/ dir  → so 'app' package is importable (app.config, app.services, etc.)
BACKEND_DIR = str(Path(PROJECT_ROOT) / "backend")
for _p in [PROJECT_ROOT, BACKEND_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Now import and run uvicorn
import uvicorn

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    print("=" * 60)
    print("  Starting PARWA Backend for Manual Testing")
    print(f"  Project:  {PROJECT_ROOT}")
    print(f"  Backend:  {BACKEND_DIR}")
    print(f"  Database: SQLite at {DB_PATH}")
    print(f"  URL:      http://localhost:{port}")
    print(f"  API Docs: http://localhost:{port}/docs")
    print("  Redis:    DISABLED (in-memory fallback)")
    print("=" * 60)

    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=port,
        reload=False,
        log_level="info",
    )

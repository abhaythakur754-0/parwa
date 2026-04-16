"""
PARWA Week 15 test conftest — ensures DB env vars are set before imports.
"""

import os
import sys
from pathlib import Path

# MUST be set before any database module imports
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Add project roots to sys.path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_backend_dir = str(_project_root / "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

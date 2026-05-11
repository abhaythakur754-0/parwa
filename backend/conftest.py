"""
Root conftest.py for PARWA backend tests.

Ensures that 'shared' and 'database' packages are importable by adding
the parwa project root to sys.path. This is needed because:
  - 'shared' lives at parwa/backend/../ (project root level)
  - 'database' lives at parwa/backend/../ (project root level)
  - Tests import from 'shared.knowledge_base.vector_search' etc.
"""

import sys
from pathlib import Path

# Add the parwa project root (parent of 'backend/') to sys.path
# so that 'shared' and 'database' packages are importable.
_project_root = Path(__file__).resolve().parent.parent
_root_str = str(_project_root)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

# Also ensure the backend/ dir is on the path for 'app' imports
_backend_dir = str(Path(__file__).resolve().parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

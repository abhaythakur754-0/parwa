"""Response envelope: {"ok": true, "data": {...}, "ms": <latency>}."""
from __future__ import annotations

import time
from typing import Any, Dict


def ms_since(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def ok(data: Dict[str, Any], t0: float) -> Dict[str, Any]:
    return {"ok": True, "data": data, "ms": ms_since(t0)}

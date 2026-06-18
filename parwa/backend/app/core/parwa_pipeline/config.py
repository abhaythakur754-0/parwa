"""
PARWA Pipeline V2 — Configuration

NVIDIA API (Llama 3.1 8B) + pipeline thresholds + quality settings.
All values from the architecture roadmap.
"""

from __future__ import annotations

import os


# ── LLM Provider ───────────────────────────────────────────────────

NVIDIA_API_KEY = os.environ.get(
    "NVIDIA_API_KEY",
    "nvapi-mYdaofMi6jRs_7xUD9ZhKtMm8I7exL04LaisFl3Vd5EXbxP8OXacPV1i",
)
NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.1-8b-instruct"

# LiteLLM: use openai/ prefix with NVIDIA base URL for compatible endpoints
LLM_MODEL = "meta/llama-3.1-8b-instruct"
LLM_API_BASE = NVIDIA_API_BASE
LLM_API_KEY = NVIDIA_API_KEY

# Rate limit: 40 requests per minute on NVIDIA free tier
LLM_RPM_LIMIT = 40


# ── Quality Thresholds (from roadmap Section 15) ──────────────────

QUALITY_PASS_THRESHOLD = 0.90       # Node 6: pass quality gate
QUALITY_LOOP_THRESHOLD = 0.70       # Node 6: loop if 0.70-0.90
QUALITY_SUPER_THRESHOLD = 0.85      # Node 8: pass after super node
QUALITY_SIMPLE_SAFETY_NET = 0.80    # Node 7: auto-upgrade to Node 4

# Quality scoring weights (from roadmap Section 15)
QUALITY_WEIGHTS = {
    "reflexion": 0.30,
    "crp": 0.25,
    "zero_shot": 0.20,
    "thot_coherence": 0.15,
    "gsd_part_scores": 0.10,
}

# Max quality loops before Super Node
MAX_QUALITY_LOOPS = 2


# ── Pipeline Paths ─────────────────────────────────────────────────

PATH_SIMPLE = "simple_path"
PATH_COMPLEX = "complex_path"


# ── Notification Keys ──────────────────────────────────────────────

NOTIFICATION_KEY_PREFIX = "PARWA-NFY"
NOTIFICATION_BATCH_WINDOW_SECONDS = 300  # 5 minutes


# ── Priority Scoring (Jarvis — from roadmap Section 5) ─────────────

PRIORITY_WEIGHTS = {
    "impact": 0.30,
    "urgency": 0.25,
    "trend": 0.20,
    "admin_preference": 0.15,
    "frequency": 0.10,
}

PRIORITY_CRITICAL = 0.85
PRIORITY_HIGH = 0.65
PRIORITY_MEDIUM = 0.40
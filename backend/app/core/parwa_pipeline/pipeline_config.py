"""
PARWA Pipeline V2 — Configuration

LLM Provider: LiteLLM Smart Router (11 models across 4 tiers via 3 API keys).
- LIGHT (ALL tasks): Cerebras Llama 3.1 8B → Groq Llama 3.1 8B → Google Gemma 3 27B
- MEDIUM (reserved): Google Gemini Flash-Lite → Google Gemini Flash → Groq Llama 3.3 70B → Groq Qwen3 32B
- HEAVY (reserved): Groq GPT-OSS 120B → Cerebras GPT-OSS 120B → Groq Llama 4 Scout
- GUARDRAIL: Groq GPT-OSS 120B (user-tested best for safety checks)

User-validated: llama-3.1-8b gives best results for ALL pipeline tasks.
All variants get ALL model tiers; only restrictions differ.
"""

from __future__ import annotations

import os


# ── LLM Provider (LiteLLM Smart Router) ────────────────────────────
# The Smart Router in app.core.smart_router handles all model selection.
# LiteLLM auto-routes cerebras/, groq/, gemini/ prefixes to correct API keys.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "litellm")

# Ensure GEMINI_API_KEY is set for LiteLLM (it expects this env var name)
if not os.environ.get("GEMINI_API_KEY") and os.environ.get("GOOGLE_AI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_AI_API_KEY"]

# API Keys (read from env, set by Render)
GOOGLE_AI_API_KEY = os.environ.get("GOOGLE_AI_API_KEY", "")
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Model IDs (LiteLLM format: provider/model-id)
# Note: Cerebras uses "llama3.1-8b" (no dot), Groq uses "llama-3.1-8b-instant"
AI_LIGHT_MODEL = os.environ.get("AI_LIGHT_MODEL", "groq/llama-3.1-8b-instant")
AI_MEDIUM_MODEL = os.environ.get("AI_MEDIUM_MODEL", "groq/llama-3.1-8b-instant")
AI_HEAVY_MODEL = os.environ.get("AI_HEAVY_MODEL", "groq/gpt-oss-120b")
AI_FAILOVER_MODEL = os.environ.get("AI_FAILOVER_MODEL", "groq/llama-3.1-8b-instant")

# Legacy NVIDIA config kept for emergency fallback only
# 2026-09 (revalidated with a real nvapi-* key, live-fire tested):
#   - meta/llama-3.1-8b-instruct EOL (410), llama-3.1-nemotron-70b/51b/ultra
#     all 404 "Not found for account" on NEW build.nvidia.com accounts.
#   - VERIFIED LIVE on-account: z-ai/glm-5.3-flash (~2.4s, clean),
#     nvidia/nemotron-3-super-120b-a12b (~8.3s, strongest),
#     openai/gpt-oss-20b (~3.9s), nemotron-3-nano-omni (reasoning kept in
#     separate reasoning_content field — content stays clean).
#   - AVOID nvidia/nemotron-3.5-lightning-30b-a3b: leaks CoT prose into content.
# NOTE: GLM/nemotron models may emit <think> — call sites strip it (kept).
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "z-ai/glm-5.3-flash")
# Heavy tier gets the strongest verified model (also spreads load across two
# per-model rate-limit buckets on the free 40 RPM account).
NVIDIA_HEAVY_MODEL = os.environ.get("NVIDIA_HEAVY_MODEL", "nvidia/nemotron-3-super-120b-a12b")

# Rate limit: Conservative default for free tiers
LLM_RPM_LIMIT = 30


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

"""POST /browse — act in admin panels with no API (browser-use + Playwright).

DISABLED — Phase 3 decision pending: browser-use needs an LLM "brain".
Options: point it at Parwa's existing LLM (Groq key) or run a local small
model (breaks the "no local text-gen LLMs" rule). 501 until decided.
"""
from __future__ import annotations

NOT_ENABLED = (
    "browse is not enabled yet — Phase 3 pending your decision: "
    "which LLM brain should browser-use use (Parwa Groq key vs local model)?"
)

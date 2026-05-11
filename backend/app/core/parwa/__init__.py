"""
Pro Parwa — Growth tier of the Parwa Variant Engine (17-node pipeline).

Pipeline: pii_check -> empathy_check -> emergency_check -> gsd_state
        -> classify -> extract_signals -> technique_select
        -> reasoning_chain -> context_enrich -> generate
        -> crp_compress -> clara_quality_gate -> quality_retry
        -> confidence_assess -> format -> END

Connected Frameworks (Tier 1 + Tier 2):
  Tier 1 (Always Active):
    - CLARA (Quality Gate) — Structure/Logic/Brand/Tone/Delivery validation
    - CRP (Token Compression) — 30-40% token reduction
    - GSD (State Engine) — Conversation state machine tracking
    - Smart Router (F-054) — Model tier selection (Medium for Pro)
    - Technique Router (BC-013) — Technique selection (Tier 1+2)
    - Confidence Scoring (F-059) — Response confidence assessment

  Tier 2 (Conditional — activated by signal-based trigger rules):
    - CoT (Chain of Thought) — Step-by-step reasoning
    - ReAct — Reasoning + acting with tool calls
    - Reverse Thinking — Inversion-based reasoning
    - Step-Back — Broader context seeking
    - ThoT (Thread of Thought) — Multi-turn continuity

Pro vs Mini differences:
  - 17 nodes vs Mini's 10 (adds technique_select, reasoning_chain,
    context_enrich, quality_retry, confidence_assess)
  - Tier 1+2 techniques vs Mini's Tier 1 only
  - Quality gate threshold: 85 (vs Mini's 60) with 1 retry
  - AI classification (not just keyword)
  - Medium model tier (vs Mini's Light) — gpt-4o-mini or gpt-4o for SaaS
  - Reasoning chain execution before generation
  - Cost target: ~$0.008/query (vs Mini's ~$0.003)
  - Latency target: <8s (vs Mini's <3s)

Design:
  - Code-orchestrated routing = FREE (Python if/else, no LLM for routing)
  - Pro uses AI classification + technique-guided generation
  - Quality gate with retry loop (max 1 retry)
  - BC-008: Every function wrapped in try/except — never crash
  - BC-001: company_id is always first parameter on public methods
  - BC-012: All timestamps UTC
"""

from app.core.parwa.graph import ParwaPipeline
from app.core.parwa.ticket_service import ParwaTicketService

__all__ = [
    "ParwaPipeline",
    "ParwaTicketService",
]

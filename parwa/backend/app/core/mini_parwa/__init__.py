"""
Mini Parwa — Cheapest tier of the Parwa Variant Engine.

Pipeline: pii_check -> empathy_check -> emergency_check -> gsd_state
        -> extract_signals -> classify -> generate -> crp_compress
        -> clara_quality_gate -> format -> END

Connected Frameworks (Tier 1 — Always Active, Even in Mini):
  - CLARA (Quality Gate) — Structure/Logic/Brand/Tone/Delivery validation
  - CRP (Token Compression) — 30-40% token reduction
  - GSD (State Engine) — Conversation state machine tracking
  - Smart Router (F-054) — Model tier selection
  - Technique Router (BC-013) — Technique selection
  - Confidence Scoring (F-059) — Response confidence assessment

Design:
  - Code-orchestrated routing = FREE (Python if/else, no LLM for routing)
  - Mini is the cheapest tier: keyword classification (no AI), gpt-4o-mini for generation only
  - Tier 1 techniques (CLARA, CRP, GSD) are ALWAYS ACTIVE even in Mini
  - Tier 2/3 techniques (CoT, ReAct, ToT, etc.) are Pro/High only
  - BC-008: Every function wrapped in try/except — never crash
  - BC-001: company_id is always first parameter on public methods

BC-001: company_id first parameter on public methods.
BC-008: Every public method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from app.core.mini_parwa.llm_client import MiniLLMClient
from app.core.mini_parwa.graph import MiniParwaPipeline
from app.core.mini_parwa.ticket_service import MiniParwaTicketService

__all__ = [
    "MiniLLMClient",
    "MiniParwaPipeline",
    "MiniParwaTicketService",
]

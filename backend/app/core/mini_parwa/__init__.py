"""
Mini Parwa — Cheapest tier of the Parwa Variant Engine.

Pipeline: pii_check -> empathy_check -> emergency_check -> classify -> generate -> format -> END

Design:
  - Code-orchestrated routing = FREE (Python if/else, no LLM for routing)
  - Mini is the cheapest tier: keyword classification (no AI), gpt-4o-mini for generation only
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

"""
High Parwa -- Highest tier of the Parwa Variant Engine (20-node pipeline).

Pipeline: pii_check -> empathy_check -> emergency_check -> gsd_state
        -> classify -> extract_signals -> technique_select
        -> reasoning_chain -> context_enrich -> context_compress
        -> generate -> crp_compress -> clara_quality_gate
        -> quality_retry (max 2) -> confidence_assess
        -> context_health -> dedup -> strategic_decision
        -> peer_review -> format -> END

Connected Frameworks (Tier 1 + Tier 2 + Tier 3):
  Tier 1 (Always Active):
    - CLARA (Quality Gate) -- Enhanced: threshold 95, 8-check (strictest)
    - CRP (Token Compression) -- 30-40% token reduction
    - GSD (State Engine) -- Conversation state machine tracking
    - Smart Router (F-054) -- Model tier selection (Heavy for High)
    - Technique Router (BC-013) -- Technique selection (Tier 1+2+3)
    - Confidence Scoring (F-059) -- Response confidence assessment

  Tier 2 (Conditional -- activated by signal-based trigger rules):
    - CoT (Chain of Thought) -- Step-by-step reasoning
    - ReAct -- Reasoning + acting with tool calls
    - Reverse Thinking -- Inversion-based reasoning
    - Step-Back -- Broader context seeking
    - ThoT (Thread of Thought) -- Multi-turn continuity

  Tier 3 (Conditional -- High-exclusive advanced reasoning):
    - GST (General Systematic Thinking) -- Systematic problem decomposition
    - UoT (Universe of Thoughts) -- Multi-perspective exploration
    - ToT (Tree of Thoughts) -- Branching exploration of solutions
    - Self-Consistency -- Multi-sample voting for reliability
    - Reflexion -- Self-critique and improvement loop
    - Least-to-Most -- Progressive complexity decomposition

High vs Pro differences:
  - 20 nodes vs Pro's 15 (adds context_compress, context_health, dedup,
    strategic_decision, peer_review)
  - Tier 1+2+3 techniques vs Pro's Tier 1+2
  - Quality gate threshold: 95 (vs Pro's 85) with max 2 retries
  - AI classification + advanced reasoning + self-critique
  - Heavy model tier (gpt-4o) for all industries
  - Context compression before generation
  - Strategic decision node for complex routing
  - Peer review for response validation
  - Cost target: ~$0.015/query (vs Pro's ~$0.008)
  - Latency target: <15s (vs Pro's <8s)

Design:
  - Code-orchestrated routing = FREE (Python if/else, no LLM for routing)
  - High uses AI classification + Tier 3 technique-guided generation
  - Quality gate with retry loop (max 2 retries)
  - Context compression before generation for efficiency
  - Strategic decision for complex multi-path routing
  - Peer review for final response validation
  - BC-008: Every function wrapped in try/except -- never crash
  - BC-001: company_id is always first parameter on public methods
  - BC-012: All timestamps UTC
"""

from app.core.parwa_high.graph import ParwaHighPipeline
from app.core.parwa_high.ticket_service import ParwaHighTicketService

__all__ = [
    "ParwaHighPipeline",
    "ParwaHighTicketService",
]

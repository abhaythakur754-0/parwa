"""
PARWA Builder Agent — AI-powered agent creation pipeline.

Connects Node 1 (Ingest + Classify) to the Builder so that when a
capability gap is detected (no agent claims a capability), the Builder
creates a properly designed agent using a 4-stage pipeline:

  EXPLORE → DESIGN → VERIFY → REFINE

The Builder also gives Node 1 control over agents — it can create,
lookup, and manage agents dynamically based on incoming tickets.

See TIER_2_AGENT_BUILDER_ROADMAP.md for full specification.
"""

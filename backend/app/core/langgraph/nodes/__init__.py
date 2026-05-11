"""
PARWA LangGraph Agent Nodes

This package contains the individual agent node implementations.
Each node is a function: (state: ParwaGraphState) -> dict
that reads from state, processes, and returns a partial state update.

Nodes (Phase 2):
  01_pii_redaction    — PII entity detection and redaction
  02_empathy_engine   — Sentiment analysis and urgency detection
  03_router_agent     — Intent classification and agent routing
  04_faq_agent        — FAQ domain agent
  05_refund_agent     — Refund domain agent
  06_technical_agent  — Technical support domain agent
  07_billing_agent    — Billing domain agent
  08_complaint_agent  — Complaint handling domain agent
  09_escalation_agent — Escalation domain agent
  10_maker_validator  — K-solution validator (ALL tiers)
  11_control_system   — Approval/interrupt decision system
  12_dspy_optimizer   — DSPy prompt optimization
  13_guardrails       — Safety and compliance checks
  14_channel_delivery — Channel dispatch routing
  15_state_update     — Persistence, audit, metrics
  16_email_agent      — Email channel delivery
  17_sms_agent        — SMS channel delivery
  18_voice_agent      — Voice channel delivery (Pro + High only)
  19_video_agent      — Video channel delivery (High only)
"""

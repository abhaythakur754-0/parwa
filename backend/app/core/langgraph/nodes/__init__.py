"""
PARWA LangGraph Agent Nodes

This package contains the individual agent node implementations.
Each node is a function: (state: ParwaGraphState) -> dict
that reads from state, processes, and returns a partial state update.

Nodes (Phase 2):
  01_pii_redaction    — PII entity detection and redaction
  02_empathy_engine   — Sentiment analysis and urgency detection
  03_router_agent     — Intent classification and agent routing
  04_base_domain_agent — Base class for domain agents
  05_faq_agent        — FAQ domain agent
  06_refund_agent     — Refund domain agent
  07_technical_agent  — Technical support domain agent
  08_billing_agent    — Billing domain agent
  09_complaint_agent  — Complaint handling domain agent
  10_escalation_agent — Escalation domain agent
  11_maker_validator  — K-solution validator (ALL tiers)
  12_control_system   — Approval/interrupt decision system
  13_dspy_optimizer   — DSPy prompt optimization
  14_guardrails       — Safety and compliance checks
  15_channel_delivery — Channel dispatch routing
  16_state_update     — Persistence, audit, metrics
  17_email_agent      — Email channel delivery
  18_sms_agent        — SMS channel delivery
  19_voice_agent      — Voice channel delivery (Pro + High only)
"""

# Explicit re-exports for static analysis visibility.
# These modules are loaded lazily by graph.py's _get_node_function(),
# but re-exporting here helps tools (Graphify, IDEs, mypy) see the edges.
#
# NOTE: Module filenames start with digits (e.g. 01_pii_redaction),
# which makes standard `from ... import` a SyntaxError.
# We use importlib.import_module() instead — same approach as graph.py.

import importlib

_NODE_MODULES = {
    "pii_redaction_node": ("01_pii_redaction", "pii_redaction_node"),
    "empathy_engine_node": ("02_empathy_engine", "empathy_engine_node"),
    "router_agent_node": ("03_router_agent", "router_agent_node"),
    "BaseDomainAgent": ("04_base_domain_agent", "BaseDomainAgent"),
    "faq_agent_node": ("05_faq_agent", "faq_agent_node"),
    "refund_agent_node": ("06_refund_agent", "refund_agent_node"),
    "technical_agent_node": ("07_technical_agent", "technical_agent_node"),
    "billing_agent_node": ("08_billing_agent", "billing_agent_node"),
    "complaint_agent_node": ("09_complaint_agent", "complaint_agent_node"),
    "escalation_agent_node": ("10_escalation_agent", "escalation_agent_node"),
    "maker_validator_node": ("11_maker_validator", "maker_validator_node"),
    "control_system_node": ("12_control_system", "control_system_node"),
    "dspy_optimizer_node": ("13_dspy_optimizer", "dspy_optimizer_node"),
    "guardrails_node": ("14_guardrails", "guardrails_node"),
    "channel_delivery_node": ("15_channel_delivery", "channel_delivery_node"),
    "state_update_node": ("16_state_update", "state_update_node"),
    "email_agent_node": ("17_email_agent", "email_agent_node"),
    "sms_agent_node": ("18_sms_agent", "sms_agent_node"),
    "voice_agent_node": ("19_voice_agent", "voice_agent_node"),
}

_BASE = "app.core.langgraph.nodes"

for _attr, (_mod_name, _symbol) in _NODE_MODULES.items():
    _mod = importlib.import_module(f"{_BASE}.{_mod_name}")
    globals()[_attr] = getattr(_mod, _symbol)

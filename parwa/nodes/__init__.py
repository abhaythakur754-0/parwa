"""PARWA LangGraph pipeline nodes.

Each node is a pure function: dict -> dict.
Nodes are organized by agent:
  - Router Agent: Nodes 1, 2, 18, 20
  - Knowledge Agent: Nodes 3, 4, 19, 5
  - Reasoning Agent: Nodes 6, 10, 12, 11
  - Action Agent: Nodes 7, 8, 9
  - Proactive Agent: Nodes 13, 14, 22
  - Compliance Agent: Nodes 15, 16, 21, 17
"""

from parwa.nodes.ingest import ingest
from parwa.nodes.intent_classifier import intent_classifier
from parwa.nodes.sentiment_analyzer import sentiment_analyzer
from parwa.nodes.escalation_decision import escalation_decision
from parwa.nodes.faq_matcher import faq_matcher
from parwa.nodes.kb_retriever import kb_retriever
from parwa.nodes.context_manager import context_manager
from parwa.nodes.integration_lookup import integration_lookup
from parwa.nodes.reasoning_engine import reasoning_engine
from parwa.nodes.reverse_thinker import reverse_thinker
from parwa.nodes.tree_of_thoughts import tree_of_thoughts
from parwa.nodes.strategy_planner import strategy_planner
from parwa.nodes.action_planner import action_planner
from parwa.nodes.action_executor import action_executor
from parwa.nodes.action_verifier import action_verifier
from parwa.nodes.proactive_checker import proactive_checker
from parwa.nodes.prediction_engine import prediction_engine
from parwa.nodes.feedback_loop import feedback_loop
from parwa.nodes.pii_compliance_guard import pii_compliance_guard
from parwa.nodes.audit_logger import audit_logger
from parwa.nodes.quality_scorer import quality_scorer
from parwa.nodes.response_formatter import response_formatter

__all__ = [
    "ingest",
    "intent_classifier",
    "sentiment_analyzer",
    "escalation_decision",
    "faq_matcher",
    "kb_retriever",
    "context_manager",
    "integration_lookup",
    "reasoning_engine",
    "reverse_thinker",
    "tree_of_thoughts",
    "strategy_planner",
    "action_planner",
    "action_executor",
    "action_verifier",
    "proactive_checker",
    "prediction_engine",
    "feedback_loop",
    "pii_compliance_guard",
    "audit_logger",
    "quality_scorer",
    "response_formatter",
]

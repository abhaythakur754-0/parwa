"""DSPy Signatures — Input/output contracts for all PARWA pipeline nodes.

Each signature defines:
  - inputs:  What the node receives
  - outputs: What the node produces
  - quality_metric: How to measure the quality of the node's output
  - description: Human-readable description of what the node does

These signatures are used by:
  - Agent Lightning: To inject few-shot examples into the right prompt sections
  - DSPy Optimizer: To evaluate prompt variants against the quality metric
  - Pattern Rules: To map corrections back to the node that generated them

Phase 6: These signatures enable DSPy-style prompt optimization by defining
clear input/output contracts that can be measured and improved.
"""

from __future__ import annotations

from typing import Any


# ─── Signature Definition ────────────────────────────────────────────────────────

class NodeSignature:
    """DSPy-style signature for a single pipeline node.

    Defines the input/output contract and quality metric for a node,
    enabling automated prompt optimization and few-shot injection.
    """

    def __init__(
        self,
        name: str,
        inputs: list[str],
        outputs: list[str],
        quality_metric: str,
        description: str,
        *,
        optimization_hints: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.inputs = inputs
        self.outputs = outputs
        self.quality_metric = quality_metric
        self.description = description
        self.optimization_hints = optimization_hints or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert signature to a serializable dict."""
        return {
            "name": self.name,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "quality_metric": self.quality_metric,
            "description": self.description,
            "optimization_hints": self.optimization_hints,
        }

    def __repr__(self) -> str:
        return (
            f"NodeSignature(name={self.name!r}, "
            f"inputs={self.inputs}, outputs={self.outputs}, "
            f"metric={self.quality_metric!r})"
        )


# ─── All Node Signatures ─────────────────────────────────────────────────────────

SIGNATURES: dict[str, NodeSignature] = {
    # ─── Router Agent ────────────────────────────────────────────────────────
    "INGEST": NodeSignature(
        name="INGEST",
        inputs=["raw_message", "channel", "customer_id", "timestamp"],
        outputs=["ticket_id", "sanitized_message", "metadata", "complexity_hint"],
        quality_metric="sanitation_completeness",
        description="Ingest and sanitize incoming customer message, assign ticket ID",
        optimization_hints={"max_response_tokens": 200},
    ),
    "INTENT_CLASSIFIER": NodeSignature(
        name="INTENT_CLASSIFIER",
        inputs=["raw_message", "customer_context", "conversation_history"],
        outputs=["intent", "confidence", "sub_intents", "intent_metadata"],
        quality_metric="intent_accuracy",
        description="Classify the customer's intent from their message and context",
        optimization_hints={
            "max_response_tokens": 150,
            "critical_for_few_shot": True,
        },
    ),
    "SENTIMENT_ANALYZER": NodeSignature(
        name="SENTIMENT_ANALYZER",
        inputs=["raw_message", "conversation_history", "customer_context"],
        outputs=["sentiment", "sentiment_score", "emotion_indicators", "urgency_level"],
        quality_metric="sentiment_f1",
        description="Analyze customer sentiment, emotion, and urgency level",
        optimization_hints={"max_response_tokens": 150},
    ),
    "ESCALATION_DECISION": NodeSignature(
        name="ESCALATION_DECISION",
        inputs=["intent", "sentiment", "confidence", "customer_tier", "complexity"],
        outputs=["should_escalate", "escalation_reason", "escalation_target", "escalation_urgency"],
        quality_metric="escalation_precision",
        description="Decide whether to escalate the ticket to a human agent",
        optimization_hints={
            "max_response_tokens": 200,
            "critical_for_few_shot": True,
        },
    ),
    "FAQ_MATCHER": NodeSignature(
        name="FAQ_MATCHER",
        inputs=["sanitized_message", "intent", "knowledge_base"],
        outputs=["faq_match", "faq_answer", "match_confidence", "alternative_faqs"],
        quality_metric="faq_relevance",
        description="Match the query against FAQ knowledge base",
        optimization_hints={"max_response_tokens": 300},
    ),

    # ─── Knowledge Agent ─────────────────────────────────────────────────────
    "KB_RETRIEVER": NodeSignature(
        name="KB_RETRIEVER",
        inputs=["sanitized_message", "intent", "knowledge_base", "context_window"],
        outputs=["retrieved_docs", "relevance_scores", "source_chain", "coverage_assessment"],
        quality_metric="retrieval_relevance",
        description="Retrieve relevant documents from the knowledge base",
        optimization_hints={"max_response_tokens": 500},
    ),
    "CONTEXT_MANAGER": NodeSignature(
        name="CONTEXT_MANAGER",
        inputs=["retrieved_docs", "conversation_history", "customer_context", "intent"],
        outputs=["assembled_context", "context_priority", "context_summary", "gaps_identified"],
        quality_metric="context_completeness",
        description="Assemble and prioritize context from all sources",
        optimization_hints={"max_response_tokens": 400},
    ),
    "INTEGRATION_LOOKUP": NodeSignature(
        name="INTEGRATION_LOOKUP",
        inputs=["intent", "customer_id", "assembled_context", "required_data"],
        outputs=["crm_data", "order_data", "account_data", "integration_status"],
        quality_metric="data_freshness",
        description="Look up customer data from CRM and external integrations",
        optimization_hints={"max_response_tokens": 400},
    ),
    "SITUATION_MODEL": NodeSignature(
        name="SITUATION_MODEL",
        inputs=["assembled_context", "crm_data", "sentiment", "intent", "conversation_history"],
        outputs=["situation_summary", "risks", "opportunities", "customer_state", "key_factors"],
        quality_metric="situational_accuracy",
        description="Build a holistic model of the customer's situation",
        optimization_hints={"max_response_tokens": 500},
    ),
    "POLICY_GUARD": NodeSignature(
        name="POLICY_GUARD",
        inputs=["intent", "situation_summary", "proposed_actions", "customer_tier"],
        outputs=["policy_compliance", "blocked_actions", "policy_constraints", "allowed_scope"],
        quality_metric="policy_compliance_rate",
        description="Enforce policy constraints on reasoning and actions",
        optimization_hints={"max_response_tokens": 300},
    ),

    # ─── Reasoning Agent ────────────────────────────────────────────────────
    "REASONING_ENGINE": NodeSignature(
        name="REASONING_ENGINE",
        inputs=["assembled_context", "intent", "situation_summary", "policy_constraints"],
        outputs=["reasoning_chain", "conclusion", "confidence", "alternatives"],
        quality_metric="reasoning_quality",
        description="Core reasoning engine that produces the reasoning chain and conclusion",
        optimization_hints={
            "max_response_tokens": 800,
            "critical_for_few_shot": True,
        },
    ),
    "REVERSE_THINKER": NodeSignature(
        name="REVERSE_THINKER",
        inputs=["conclusion", "reasoning_chain", "situation_summary"],
        outputs=["challenge_result", "weak_points", "refined_conclusion", "challenge_confidence"],
        quality_metric="challenge_effectiveness",
        description="Challenge the reasoning from the opposite perspective",
        optimization_hints={"max_response_tokens": 600},
    ),
    "RED_TEAM": NodeSignature(
        name="RED_TEAM",
        inputs=["conclusion", "reasoning_chain", "challenge_result", "policy_constraints"],
        outputs=["adversarial_findings", "vulnerabilities", "mitigation_suggestions", "risk_assessment"],
        quality_metric="vulnerability_detection_rate",
        description="Adversarial validation of the reasoning and conclusion",
        optimization_hints={"max_response_tokens": 500},
    ),
    "TREE_OF_THOUGHTS": NodeSignature(
        name="TREE_OF_THOUGHTS",
        inputs=["conclusion", "challenge_result", "situation_summary", "alternatives"],
        outputs=["thought_tree", "best_path", "path_scores", "pruned_alternatives"],
        quality_metric="thought_diversity",
        description="Explore multiple reasoning paths and select the best one",
        optimization_hints={"max_response_tokens": 700},
    ),
    "AGENT_DEBATE": NodeSignature(
        name="AGENT_DEBATE",
        inputs=["best_path", "thought_tree", "situation_summary", "adversarial_findings"],
        outputs=["debate_result", "advocate_position", "skeptic_position", "consensus"],
        quality_metric="debate_quality",
        description="Advocate vs Skeptic debate to validate the chosen path",
        optimization_hints={"max_response_tokens": 600},
    ),
    "STRATEGY_PLANNER": NodeSignature(
        name="STRATEGY_PLANNER",
        inputs=["consensus", "best_path", "policy_constraints", "customer_tier"],
        outputs=["strategy", "action_sequence", "contingency_plans", "strategy_rationale"],
        quality_metric="strategy_feasibility",
        description="Plan the execution strategy based on debate results",
        optimization_hints={"max_response_tokens": 500},
    ),
    "META_REASONER": NodeSignature(
        name="META_REASONER",
        inputs=["reasoning_chain", "quality_score", "feedback_signal", "conversation_history"],
        outputs=["meta_assessment", "reasoning_gaps", "improvement_suggestions", "re_reason_flag"],
        quality_metric="meta_accuracy",
        description="Evaluate the pipeline's own reasoning quality and suggest improvements",
        optimization_hints={"max_response_tokens": 400},
    ),

    # ─── Action Agent ────────────────────────────────────────────────────────
    "ACTION_PLANNER": NodeSignature(
        name="ACTION_PLANNER",
        inputs=["strategy", "reasoning_conclusion", "policy_constraints", "crm_data"],
        outputs=["action_plan", "action_steps", "required_permissions", "rollback_plan"],
        quality_metric="action_completeness",
        description="Plan concrete actions based on the reasoning conclusion",
        optimization_hints={
            "max_response_tokens": 500,
            "critical_for_few_shot": True,
        },
    ),
    "ACTION_EXECUTOR": NodeSignature(
        name="ACTION_EXECUTOR",
        inputs=["action_plan", "action_steps", "required_permissions", "crm_data"],
        outputs=["execution_results", "execution_status", "side_effects", "execution_log"],
        quality_metric="execution_success_rate",
        description="Execute the planned actions against CRM and integrations",
        optimization_hints={"max_response_tokens": 500},
    ),
    "ACTION_VERIFIER": NodeSignature(
        name="ACTION_VERIFIER",
        inputs=["execution_results", "action_plan", "expected_outcomes"],
        outputs=["verification_result", "discrepancies", "verification_confidence", "remediation_needed"],
        quality_metric="verification_accuracy",
        description="Verify that executed actions achieved the expected outcomes",
        optimization_hints={"max_response_tokens": 300},
    ),

    # ─── Proactive Agent ─────────────────────────────────────────────────────
    "PROACTIVE_CHECKER": NodeSignature(
        name="PROACTIVE_CHECKER",
        inputs=["intent", "situation_summary", "execution_results", "customer_context"],
        outputs=["proactive_suggestions", "follow_up_actions", "prevention_tips", "upsell_opportunities"],
        quality_metric="suggestion_relevance",
        description="Proactively suggest follow-up actions and prevention tips",
        optimization_hints={"max_response_tokens": 400},
    ),
    "PREDICTION_ENGINE": NodeSignature(
        name="PREDICTION_ENGINE",
        inputs=["intent", "customer_context", "situation_summary", "conversation_history"],
        outputs=["predictions", "likelihood_scores", "next_best_actions", "risk_forecast"],
        quality_metric="prediction_accuracy",
        description="Predict future customer needs and likely next interactions",
        optimization_hints={"max_response_tokens": 400},
    ),
    "FEEDBACK_LOOP": NodeSignature(
        name="FEEDBACK_LOOP",
        inputs=["intent", "quality_score", "verification_passed", "sentiment", "recommendation"],
        outputs=["feedback_signal", "improvement_areas", "corrective_signals", "satisfaction_level"],
        quality_metric="feedback_signal_quality",
        description="Capture feedback signal for continuous improvement (Node 22)",
        optimization_hints={"max_response_tokens": 300},
    ),

    # ─── Compliance Agent ────────────────────────────────────────────────────
    "PII_COMPLIANCE_GUARD": NodeSignature(
        name="PII_COMPLIANCE_GUARD",
        inputs=["draft_response", "execution_results", "customer_data"],
        outputs=["pii_scan_result", "redacted_response", "compliance_flags", "safe_to_send"],
        quality_metric="pii_detection_rate",
        description="Scan response for PII and compliance violations",
        optimization_hints={"max_response_tokens": 300},
    ),
    "AUDIT_LOGGER": NodeSignature(
        name="AUDIT_LOGGER",
        inputs=["ticket_id", "all_node_outputs", "action_log", "compliance_result"],
        outputs=["audit_record", "audit_hash", "compliance_attestation", "audit_summary"],
        quality_metric="audit_completeness",
        description="Create an immutable audit trail for the ticket",
        optimization_hints={"max_response_tokens": 300},
    ),
    "QUALITY_SCORER": NodeSignature(
        name="QUALITY_SCORER",
        inputs=["draft_response", "intent", "sentiment", "verification_result", "feedback_signal"],
        outputs=["quality_score", "quality_breakdown", "improvement_suggestions", "pass_fail"],
        quality_metric="scoring_accuracy",
        description="Score the quality of the response on multiple dimensions",
        optimization_hints={
            "max_response_tokens": 300,
            "critical_for_few_shot": True,
        },
    ),
    "RESPONSE_FORMATTER": NodeSignature(
        name="RESPONSE_FORMATTER",
        inputs=["reasoning_conclusion", "action_results", "quality_score", "sentiment", "variant"],
        outputs=["formatted_response", "response_metadata", "channel_adaptations", "tone_adjustments"],
        quality_metric="response_naturalness",
        description="Format the final response with appropriate tone and channel adaptations",
        optimization_hints={
            "max_response_tokens": 600,
            "critical_for_few_shot": True,
        },
    ),
    "CONVERSATIONAL_REPAIR": NodeSignature(
        name="CONVERSATIONAL_REPAIR",
        inputs=["draft_response", "quality_breakdown", "improvement_suggestions", "corrective_signals"],
        outputs=["repaired_response", "repairs_made", "repair_confidence", "remaining_issues"],
        quality_metric="repair_effectiveness",
        description="Detect and fix broken or suboptimal responses",
        optimization_hints={"max_response_tokens": 500},
    ),
}

# ─── Convenience Lookups ──────────────────────────────────────────────────────────

# All node names in pipeline order
PIPELINE_ORDER: list[str] = [
    "INGEST",
    "INTENT_CLASSIFIER",
    "SENTIMENT_ANALYZER",
    "ESCALATION_DECISION",
    "FAQ_MATCHER",
    "KB_RETRIEVER",
    "CONTEXT_MANAGER",
    "INTEGRATION_LOOKUP",
    "SITUATION_MODEL",
    "POLICY_GUARD",
    "REASONING_ENGINE",
    "REVERSE_THINKER",
    "RED_TEAM",
    "TREE_OF_THOUGHTS",
    "AGENT_DEBATE",
    "STRATEGY_PLANNER",
    "ACTION_PLANNER",
    "ACTION_EXECUTOR",
    "ACTION_VERIFIER",
    "PROACTIVE_CHECKER",
    "PREDICTION_ENGINE",
    "FEEDBACK_LOOP",
    "PII_COMPLIANCE_GUARD",
    "AUDIT_LOGGER",
    "QUALITY_SCORER",
    "META_REASONER",
    "CONVERSATIONAL_REPAIR",
    "RESPONSE_FORMATTER",
]

# Nodes where few-shot injection is most impactful (high error rate, critical path)
CRITICAL_NODES: list[str] = [
    "INTENT_CLASSIFIER",
    "ESCALATION_DECISION",
    "REASONING_ENGINE",
    "ACTION_PLANNER",
    "QUALITY_SCORER",
    "RESPONSE_FORMATTER",
]

# Agent groupings
AGENT_GROUPS: dict[str, list[str]] = {
    "router": ["INGEST", "INTENT_CLASSIFIER", "ESCALATION_DECISION", "FAQ_MATCHER", "SENTIMENT_ANALYZER"],
    "knowledge": ["KB_RETRIEVER", "CONTEXT_MANAGER", "INTEGRATION_LOOKUP", "SITUATION_MODEL", "POLICY_GUARD"],
    "reasoning": ["REASONING_ENGINE", "REVERSE_THINKER", "RED_TEAM", "TREE_OF_THOUGHTS",
                   "AGENT_DEBATE", "STRATEGY_PLANNER", "META_REASONER"],
    "action": ["ACTION_PLANNER", "ACTION_EXECUTOR", "ACTION_VERIFIER"],
    "proactive": ["PROACTIVE_CHECKER", "PREDICTION_ENGINE", "FEEDBACK_LOOP"],
    "compliance": ["PII_COMPLIANCE_GUARD", "AUDIT_LOGGER", "QUALITY_SCORER",
                    "CONVERSATIONAL_REPAIR", "RESPONSE_FORMATTER"],
}


def get_signature(node_name: str) -> NodeSignature | None:
    """Get the signature for a node by name.

    Args:
        node_name: The node name (e.g. "INTENT_CLASSIFIER").

    Returns:
        NodeSignature if found, None otherwise.
    """
    return SIGNATURES.get(node_name.upper())


def get_signatures_for_agent(agent_name: str) -> list[NodeSignature]:
    """Get all signatures for nodes belonging to an agent.

    Args:
        agent_name: Agent name (router, knowledge, reasoning, action, proactive, compliance).

    Returns:
        List of NodeSignature objects for that agent's nodes.
    """
    node_names = AGENT_GROUPS.get(agent_name.lower(), [])
    return [SIGNATURES[n] for n in node_names if n in SIGNATURES]


def get_critical_signatures() -> list[NodeSignature]:
    """Get signatures for nodes where few-shot injection is most impactful."""
    return [SIGNATURES[n] for n in CRITICAL_NODES if n in SIGNATURES]


def list_all_metrics() -> dict[str, str]:
    """Return a mapping of node_name -> quality_metric for all nodes."""
    return {name: sig.quality_metric for name, sig in SIGNATURES.items()}

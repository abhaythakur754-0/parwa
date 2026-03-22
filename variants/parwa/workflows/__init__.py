"""
PARWA Junior Workflows Package.

This package contains workflows used by PARWA Junior agents:
- RefundRecommendationWorkflow: Process refund requests with APPROVE/REVIEW/DENY reasoning
- KnowledgeUpdateWorkflow: Update knowledge base after resolution
- SafetyWorkflow: Run safety checks before response

All workflows are designed for PARWA Junior variant with:
- Medium AI tier support
- Up to $500 refund recommendations
- Full reasoning output for decisions
- Learning and safety capabilities

CRITICAL: All refund workflows create pending_approval records
and NEVER call Paddle directly.
"""
from variants.parwa.workflows.refund_recommendation import RefundRecommendationWorkflow
from variants.parwa.workflows.knowledge_update import KnowledgeUpdateWorkflow
from variants.parwa.workflows.safety_workflow import SafetyWorkflow

__all__ = [
    "RefundRecommendationWorkflow",
    "KnowledgeUpdateWorkflow",
    "SafetyWorkflow",
]

"""
PARWA Junior Tasks Package.

This package contains task modules for PARWA Junior variant.
Each task wraps PARWA agents and workflows to perform specific actions.

Available Tasks:
- RecommendRefundTask: Generate refund recommendation with APPROVE/REVIEW/DENY
- UpdateKnowledgeTask: Update knowledge base after resolution
- ComplianceCheckTask: Run compliance checks on actions

All PARWA Junior tasks:
- Route to 'medium' tier for processing
- Support refund recommendations up to $500
- Include full reasoning in outputs
- Escalate when confidence < 60%
- NEVER call Paddle without pending_approval
"""
from variants.parwa.tasks.recommend_refund import RecommendRefundTask
from variants.parwa.tasks.update_knowledge import UpdateKnowledgeTask
from variants.parwa.tasks.compliance_check import ComplianceCheckTask

__all__ = [
    "RecommendRefundTask",
    "UpdateKnowledgeTask",
    "ComplianceCheckTask",
]

"""
PARWA High Agents Module.

This module contains all agent implementations for the PARWA High variant.
Each agent inherits from the corresponding base agent and implements
PARWA High-specific behavior with heavy tier support.

Agents:
- ParwaHighVideoAgent: Video support with screen sharing
- ParwaHighAnalyticsAgent: Analytics and insights generation
- ParwaHighCoordinationAgent: Team coordination for 5 concurrent teams
- ParwaHighCustomerSuccessAgent: Customer success with churn prediction
- ParwaHighSLAAgent: SLA breach detection and escalation
- ParwaHighComplianceAgent: HIPAA compliance and BAA enforcement
- ParwaHighLearningAgent: Learning with negative_reward creation
- ParwaHighSafetyAgent: Safety with PHI sanitization

PARWA High differs from PARWA Junior in:
- Uses 'heavy' tier for most sophisticated AI processing
- Supports 10 concurrent calls (vs 5 for PARWA Junior)
- $2000 refund limit with execution capability (vs $500 for PARWA Junior)
- 50% escalation threshold (vs 60% for PARWA Junior)
- Advanced customer success with churn prediction
- Team coordination for 5 concurrent teams
- Full HIPAA compliance enforcement
- PHI sanitization and protection
"""

# Builder 1 (Day 1) agents
from variants.parwa_high.agents.video_agent import ParwaHighVideoAgent
from variants.parwa_high.agents.analytics_agent import ParwaHighAnalyticsAgent
from variants.parwa_high.agents.coordination_agent import ParwaHighCoordinationAgent

# Builder 2 (Day 2) agents
from variants.parwa_high.agents.customer_success_agent import (
    ParwaHighCustomerSuccessAgent,
    ChurnRiskLevel,
    CustomerHealthStatus,
    ChurnPrediction,
)
from variants.parwa_high.agents.sla_agent import (
    ParwaHighSLAAgent,
    EscalationPhase,
    SLABreachRecord,
)
from variants.parwa_high.agents.compliance_agent import (
    ParwaHighComplianceAgent,
    ComplianceLevel,
    ComplianceStatus,
    ComplianceCheckResult,
)
from variants.parwa_high.agents.learning_agent import (
    ParwaHighLearningAgent,
    FeedbackType,
    TrainingDataType,
    NegativeReward,
    TrainingDataPoint,
)
from variants.parwa_high.agents.safety_agent import (
    ParwaHighSafetyAgent,
    SafetyCheckType,
    SafetyAction,
    SafetyCheckResult,
)

__all__ = [
    # Builder 1 - Day 1
    "ParwaHighVideoAgent",
    "ParwaHighAnalyticsAgent",
    "ParwaHighCoordinationAgent",
    # Builder 2 - Day 2 - Customer Success
    "ParwaHighCustomerSuccessAgent",
    "ChurnRiskLevel",
    "CustomerHealthStatus",
    "ChurnPrediction",
    # Builder 2 - Day 2 - SLA
    "ParwaHighSLAAgent",
    "EscalationPhase",
    "SLABreachRecord",
    # Builder 2 - Day 2 - Compliance
    "ParwaHighComplianceAgent",
    "ComplianceLevel",
    "ComplianceStatus",
    "ComplianceCheckResult",
    # Builder 2 - Day 2 - Learning
    "ParwaHighLearningAgent",
    "FeedbackType",
    "TrainingDataType",
    "NegativeReward",
    "TrainingDataPoint",
    # Builder 2 - Day 2 - Safety
    "ParwaHighSafetyAgent",
    "SafetyCheckType",
    "SafetyAction",
    "SafetyCheckResult",
]

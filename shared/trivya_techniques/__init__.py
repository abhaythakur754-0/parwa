"""
PARWA TRIVYA Techniques.

TRIVYA (Tiered Reasoning with Intelligent Verification and Yielding Analysis)
implements a multi-tier reasoning approach for AI-powered customer support.

Tier 1: Foundation techniques (CLARA, CRP, GSD Integration)
Tier 2: Advanced reasoning techniques (Chain of Thought, ReAct, etc.)
Tier 3: Specialized handling (escalation, complex scenarios)
"""

from shared.trivya_techniques.orchestrator import (
    T1Orchestrator,
    T1OrchestratorResult,
    T1OrchestratorConfig,
    ProcessingStage,
)
from shared.trivya_techniques.tier1.clara import (
    CLARA,
    CLARAResult,
    CLARAConfig,
)
from shared.trivya_techniques.tier1.crp import (
    CRP,
    CRPResult,
    CRPConfig,
)
from shared.trivya_techniques.tier1.gsd_integration import (
    GSDIntegration,
    GSDIntegrationResult,
    GSDIntegrationConfig,
)

__all__ = [
    # Orchestrator
    "T1Orchestrator",
    "T1OrchestratorResult",
    "T1OrchestratorConfig",
    "ProcessingStage",
    # Tier 1
    "CLARA",
    "CLARAResult",
    "CLARAConfig",
    "CRP",
    "CRPResult",
    "CRPConfig",
    "GSDIntegration",
    "GSDIntegrationResult",
    "GSDIntegrationConfig",
]

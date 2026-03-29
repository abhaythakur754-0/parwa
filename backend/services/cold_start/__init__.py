"""
Cold Start Module

Provides industry-specific bootstrapping for new clients.
"""

from backend.services.cold_start.service import (
    ColdStartService,
    ColdStartConfig,
    Industry,
    BootstrapStatus,
    get_cold_start_service,
)
from backend.services.cold_start.analyzer import (
    IndustryAnalyzer,
    AnalysisResult,
    analyze_client,
)
from backend.services.cold_start.bootstrap import (
    KnowledgeBaseBootstrap,
    WorkflowSetup,
    get_kb_bootstrap,
    get_workflow_setup,
)

__all__ = [
    # Main service
    "ColdStartService",
    "ColdStartConfig",
    "Industry",
    "BootstrapStatus",
    "get_cold_start_service",
    # Analyzer
    "IndustryAnalyzer",
    "AnalysisResult",
    "analyze_client",
    # Bootstrap
    "KnowledgeBaseBootstrap",
    "WorkflowSetup",
    "get_kb_bootstrap",
    "get_workflow_setup",
]

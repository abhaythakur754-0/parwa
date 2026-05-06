"""
Parwa Enhancement Modules — 5 improvement areas for higher automation.

Targets: 84.3% → 89.5% overall automation potential.

Modules:
  1. emotional_intelligence — EI Layer + Service Recovery Playbooks (Complaints 65%→82%)
  2. churn_retention — Churn Risk Scoring + Dynamic Retention + Win-Back (Cancellation 70%→85%)
  3. billing_intelligence — Paddle Dispute Auto-Resolution + Anomaly Detection (Billing 80%→88%)
  4. tech_diagnostics — Diagnostic Tools + Known Issue Detection + Severity Scoring (Tech 82%→90%)
  5. shipping_intelligence — Multi-Carrier Integration + Proactive Delay Notifications (Shipping 83%→88%)

Architecture:
  Each module is called from the `smart_enrichment` node (between classify
  and extract_signals) and the `auto_action` node (after confidence_assess).
  The smart_enrichment node enriches context BEFORE generation.
  The auto_action node takes automated actions AFTER response generation.

BC-001: company_id first parameter on public methods.
BC-008: Every method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from app.core.enhancements.emotional_intelligence import EmotionalIntelligenceEngine
from app.core.enhancements.churn_retention import ChurnRetentionEngine
from app.core.enhancements.billing_intelligence import BillingIntelligenceEngine
from app.core.enhancements.tech_diagnostics import TechDiagnosticsEngine
from app.core.enhancements.shipping_intelligence import ShippingIntelligenceEngine

__all__ = [
    "EmotionalIntelligenceEngine",
    "ChurnRetentionEngine",
    "BillingIntelligenceEngine",
    "TechDiagnosticsEngine",
    "ShippingIntelligenceEngine",
]

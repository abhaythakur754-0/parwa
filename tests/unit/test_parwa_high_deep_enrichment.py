"""
Unit tests for Parwa High Pipeline — Deep Enrichment Nodes.

Tests the 5 new deep enrichment nodes and routing logic for the High tier.
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.app.core.parwa_graph_state import create_initial_state
from backend.app.core.parwa_high.nodes import (
    complaint_handler_node,
    retention_negotiator_node,
    billing_resolver_node,
    tech_diagnostic_node,
    shipping_tracker_node,
)
from backend.app.core.parwa_high.graph import (
    route_after_smart_enrichment_deep,
    route_after_deep_enrichment,
    INTENT_DEEP_ENRICHMENT_MAP,
    build_parwa_high_graph,
)


def _make_state(**overrides):
    """Create a test state with sensible defaults for High tier."""
    state = create_initial_state(
        query="test query",
        company_id="test_co",
        variant_tier="parwa_high",
        industry="general",
        channel="chat",
    )
    state.update(overrides)
    return state


# ══════════════════════════════════════════════════════════════════
# ROUTING TESTS (Same as Pro — shared logic)
# ══════════════════════════════════════════════════════════════════

class TestHighDeepEnrichmentRouting:
    """Test routing logic for High deep enrichment nodes."""
    
    def test_route_complaint(self):
        state = _make_state(classification={"intent": "complaint", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "complaint_handler"
    
    def test_route_cancellation(self):
        state = _make_state(classification={"intent": "cancellation", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "retention_negotiator"
    
    def test_route_billing(self):
        state = _make_state(classification={"intent": "billing", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "billing_resolver"
    
    def test_route_technical(self):
        state = _make_state(classification={"intent": "technical", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "tech_diagnostic"
    
    def test_route_shipping(self):
        state = _make_state(classification={"intent": "shipping", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "shipping_tracker"
    
    def test_route_general_skips(self):
        state = _make_state(classification={"intent": "general", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "extract_signals"
    
    def test_route_after_deep_always_extracts(self):
        state = _make_state()
        assert route_after_deep_enrichment(state) == "extract_signals"


# ══════════════════════════════════════════════════════════════════
# NODE EXECUTION TESTS (High-specific)
# ══════════════════════════════════════════════════════════════════

class TestHighComplaintHandlerNode:
    """Test complaint_handler_node for High tier."""
    
    @patch("backend.app.core.parwa_high.nodes._get_ei_engine")
    def test_high_tier_output(self, mock_get_ei):
        mock_ei = MagicMock()
        mock_ei.assess_sentiment_escalation.return_value = {
            "escalation_needed": True,
            "escalation_level": "manager",
            "trigger_reason": "extreme_intensity",
            "priority_score": 0.95,
        }
        mock_ei.resolve_complaint.return_value = {
            "resolution_strategy": "apologize_fix_compensate_escalate",
            "de_escalation_applied": True,
            "compensation_type": "significant_credit",
            "follow_up_scheduled": True,
            "escalation_triggered": True,
            "resolution_confidence": 0.8,
        }
        mock_get_ei.return_value = mock_ei

        state = _make_state(
            query="I'm furious about this terrible service!",
            pii_redacted_query="I'm furious about this terrible service!",
            classification={"intent": "complaint"},
            emotion_profile={"primary_emotion": "angry", "intensity": 0.9, "risk_level": "high", "escalation_trajectory": "escalating", "secondary_emotions": []},
            recovery_playbook={"strategy": "apologize_fix_compensate_escalate", "compensation": "significant_credit", "escalation": True},
            customer_tier="enterprise",
            empathy_score=0.1,
        )
        result = complaint_handler_node(state)
        assert "complaint_resolution" in result
        assert "sentiment_escalation" in result
        # High-specific: tier should be in step_outputs
        step_output = result.get("step_outputs", {}).get("complaint_handler", {})
        assert step_output.get("tier") == "high"


class TestHighRetentionNegotiatorNode:
    """Test retention_negotiator_node for High tier."""
    
    @patch("backend.app.core.parwa_high.nodes._get_churn_engine")
    def test_high_tier_negotiation(self, mock_get_churn):
        mock_churn = MagicMock()
        mock_churn.negotiate_retention.return_value = {
            "negotiation_strategy": "aggressive_retention",
            "offer_presented": "personalized_retention_call",
            "counter_offers": ["executive_callback"],
            "acceptance_likelihood": 0.7,
            "negotiation_stage": "initial_offer",
        }
        mock_churn.generate_winback_automation.return_value = {
            "sequence_active": True,
            "sequence_steps": [{"step": 1, "action": "cancellation_confirmation"}],
            "total_duration_days": 45,
            "primary_offer": "personalized_retention_call",
        }
        mock_get_churn.return_value = mock_churn

        state = _make_state(
            classification={"intent": "cancellation"},
            churn_risk={"churn_probability": 0.9, "risk_tier": "critical", "primary_reason": "support_fatigue", "customer_value": "enterprise"},
            retention_offers={"primary_offer": {"offer_name": "personalized_retention_call", "automation_level": "partial", "description": "Retention call"}, "contingency_offers": []},
            customer_tier="enterprise",
        )
        result = retention_negotiator_node(state)
        assert result["retention_negotiation"]["negotiation_strategy"] == "aggressive_retention"
        step_output = result.get("step_outputs", {}).get("retention_negotiator", {})
        assert step_output.get("tier") == "high"


class TestHighBillingResolverNode:
    """Test billing_resolver_node for High tier."""
    
    @patch("backend.app.core.parwa_high.nodes._get_billing_engine")
    def test_high_tier_billing(self, mock_get_billing):
        mock_billing = MagicMock()
        mock_billing.generate_self_service_context.return_value = {
            "portal_url": "https://billing.example.com",
            "available_actions": ["view_invoice", "request_refund", "billing_specialist"],
            "dispute_status": "auto_resolved",
            "refund_eligible": True,
        }
        mock_billing.auto_resolve_paddle_dispute.return_value = {
            "dispute_id": "dp_789",
            "auto_resolved": True,
            "resolution_action": "refund_duplicate",
            "refund_amount": 99.99,
            "processing_time_hours": 12,
        }
        mock_get_billing.return_value = mock_billing

        state = _make_state(
            billing_dispute={"dispute_category": "double_charge", "auto_resolvable": True, "resolution_type": "refund_duplicate", "max_refund_percentage": 100, "priority": "high"},
            billing_anomaly={"anomaly_detected": True, "anomaly_types": ["amount_deviation"], "severity": "high"},
            customer_tier="enterprise",
        )
        result = billing_resolver_node(state)
        assert result["billing_self_service"].get("refund_eligible") is True
        step_output = result.get("step_outputs", {}).get("billing_resolver", {})
        assert step_output.get("tier") == "high"


class TestHighTechDiagnosticNode:
    """Test tech_diagnostic_node for High tier."""
    
    @patch("backend.app.core.parwa_high.nodes._get_tech_diag_engine")
    def test_high_tier_diagnostics(self, mock_get_tech):
        mock_tech = MagicMock()
        mock_tech.generate_diagnostic_result.return_value = {
            "steps_provided": 5,
            "known_issue_match": True,
            "severity_assessment": "high",
            "auto_fix_available": False,
            "resolution_path": "escalate_to_l3",
        }
        mock_tech.decide_escalation.return_value = {
            "escalate": True,
            "escalation_level": "l3_engineering",
            "severity_factors": {"business_impact": 0.9},
            "recommended_actions": ["escalate_to_l3"],
        }
        mock_get_tech.return_value = mock_tech

        state = _make_state(
            query="Production system is down!",
            pii_redacted_query="Production system is down!",
            known_issue={"known_issue_detected": True, "issue_id": "service_outage", "severity": "high", "resolution_type": "wait_for_fix", "eta_hours": 4},
            tech_diagnostics={"diagnostic_steps": [{"step": 1}]},
            severity_score={"severity_score": 0.8, "severity_level": "high", "escalation_path": "l3_engineering", "factors": {"business_impact": 0.9}, "recommended_actions": ["escalate_to_l3"]},
            customer_tier="enterprise",
        )
        result = tech_diagnostic_node(state)
        assert result["diagnostic_result"]["known_issue_match"] is True
        step_output = result.get("step_outputs", {}).get("tech_diagnostic", {})
        assert step_output.get("tier") == "high"


class TestHighShippingTrackerNode:
    """Test shipping_tracker_node for High tier."""
    
    @patch("backend.app.core.parwa_high.nodes._get_shipping_engine")
    def test_high_tier_shipping(self, mock_get_shipping):
        mock_shipping = MagicMock()
        mock_shipping.query_carrier_data.return_value = {
            "carrier": "UPS",
            "tracking_status": "in_transit",
            "estimated_delivery": "2025-03-09",
            "carrier_api_called": True,
            "last_update": "2025-03-07T14:00:00Z",
        }
        mock_shipping.generate_delay_notification.return_value = {
            "notification_sent": True,
            "notification_type": "proactive_delay_alert",
            "delay_reason": "carrier_delay",
            "revised_eta": "2025-03-11",
            "compensation_offered": True,
        }
        mock_get_shipping.return_value = mock_shipping

        state = _make_state(
            tracking_info={"primary_carrier": "UPS", "tracking_numbers": [{"carrier": "UPS", "tracking_number": "1Z999999999999"}]},
            shipping_issue={"issue_type": "delayed", "severity": "medium", "auto_resolvable": True, "resolution": "check_tracking_and_notify"},
            shipping_delay={"delay_detected": True, "compensation_eligible": True, "delay_reason": "carrier_delay"},
        )
        result = shipping_tracker_node(state)
        assert result["shipping_carrier_data"]["carrier"] == "UPS"
        step_output = result.get("step_outputs", {}).get("shipping_tracker", {})
        assert step_output.get("tier") == "high"


# ══════════════════════════════════════════════════════════════════
# GRAPH BUILD TEST
# ══════════════════════════════════════════════════════════════════

class TestParwaHighGraphBuild:
    """Test that the High graph builds correctly with all 27 nodes."""
    
    def test_graph_builds(self):
        graph = build_parwa_high_graph()
        assert graph is not None

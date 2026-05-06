"""
Unit tests for Parwa (Pro) Pipeline — Deep Enrichment Nodes.

Tests the 5 new deep enrichment nodes and the routing logic:
  - complaint_handler_node
  - retention_negotiator_node
  - billing_resolver_node
  - tech_diagnostic_node
  - shipping_tracker_node
  - route_after_smart_enrichment_deep (routing logic)
  - route_after_deep_enrichment (convergence)
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.app.core.parwa_graph_state import create_initial_state
from backend.app.core.parwa.nodes import (
    complaint_handler_node,
    retention_negotiator_node,
    billing_resolver_node,
    tech_diagnostic_node,
    shipping_tracker_node,
)
from backend.app.core.parwa.graph import (
    route_after_smart_enrichment_deep,
    route_after_deep_enrichment,
    INTENT_DEEP_ENRICHMENT_MAP,
    build_parwa_graph,
)


def _make_state(**overrides):
    """Create a test state with sensible defaults."""
    state = create_initial_state(
        query="test query",
        company_id="test_co",
        variant_tier="parwa",
        industry="general",
        channel="chat",
    )
    state.update(overrides)
    return state


# ══════════════════════════════════════════════════════════════════
# ROUTING TESTS
# ══════════════════════════════════════════════════════════════════

class TestDeepEnrichmentRouting:
    """Test the routing logic for deep enrichment nodes."""
    
    def test_route_complaint(self):
        state = _make_state(classification={"intent": "complaint", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "complaint_handler"
    
    def test_route_feedback(self):
        state = _make_state(classification={"intent": "feedback", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "complaint_handler"
    
    def test_route_cancellation(self):
        state = _make_state(classification={"intent": "cancellation", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "retention_negotiator"
    
    def test_route_cancel(self):
        state = _make_state(classification={"intent": "cancel", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "retention_negotiator"
    
    def test_route_billing(self):
        state = _make_state(classification={"intent": "billing", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "billing_resolver"
    
    def test_route_payment(self):
        state = _make_state(classification={"intent": "payment", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "billing_resolver"
    
    def test_route_refund(self):
        state = _make_state(classification={"intent": "refund", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "billing_resolver"
    
    def test_route_technical(self):
        state = _make_state(classification={"intent": "technical", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "tech_diagnostic"
    
    def test_route_bug(self):
        state = _make_state(classification={"intent": "bug", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "tech_diagnostic"
    
    def test_route_shipping(self):
        state = _make_state(classification={"intent": "shipping", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "shipping_tracker"
    
    def test_route_delivery(self):
        state = _make_state(classification={"intent": "delivery", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "shipping_tracker"
    
    def test_route_general_skips(self):
        state = _make_state(classification={"intent": "general", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "extract_signals"
    
    def test_route_account_skips(self):
        state = _make_state(classification={"intent": "account", "secondary_intents": []})
        assert route_after_smart_enrichment_deep(state) == "extract_signals"
    
    def test_route_secondary_intent(self):
        state = _make_state(classification={"intent": "general", "secondary_intents": ["billing"]})
        assert route_after_smart_enrichment_deep(state) == "billing_resolver"
    
    def test_route_after_deep_enrichment_always_extracts(self):
        state = _make_state()
        assert route_after_deep_enrichment(state) == "extract_signals"
    
    def test_intent_map_has_all_entries(self):
        expected_intents = ["complaint", "feedback", "cancellation", "cancel", "billing", "payment", "refund", "technical", "bug", "shipping", "delivery", "tracking", "order"]
        for intent in expected_intents:
            assert intent in INTENT_DEEP_ENRICHMENT_MAP, f"Missing intent: {intent}"


# ══════════════════════════════════════════════════════════════════
# NODE EXECUTION TESTS
# ══════════════════════════════════════════════════════════════════

class TestComplaintHandlerNode:
    """Test complaint_handler_node execution."""
    
    @patch("backend.app.core.parwa.nodes._get_ei_engine")
    def test_basic_execution(self, mock_get_ei):
        mock_ei = MagicMock()
        mock_ei.assess_sentiment_escalation.return_value = {
            "escalation_needed": True,
            "escalation_level": "supervisor",
            "trigger_reason": "high_intensity_angry",
            "priority_score": 0.85,
        }
        mock_ei.resolve_complaint.return_value = {
            "resolution_strategy": "apologize_fix_compensate",
            "de_escalation_applied": True,
            "compensation_type": "significant_credit",
            "follow_up_scheduled": True,
            "escalation_triggered": True,
            "resolution_confidence": 0.75,
        }
        mock_get_ei.return_value = mock_ei

        state = _make_state(
            query="I'm furious about this terrible service!",
            pii_redacted_query="I'm furious about this terrible service!",
            classification={"intent": "complaint"},
            emotion_profile={"primary_emotion": "angry", "intensity": 0.9, "risk_level": "high", "escalation_trajectory": "escalating", "secondary_emotions": []},
            recovery_playbook={"strategy": "apologize_fix_compensate_escalate", "compensation": "significant_credit", "escalation": True},
            customer_tier="growth",
            empathy_score=0.2,
        )
        result = complaint_handler_node(state)
        assert "complaint_resolution" in result
        assert "sentiment_escalation" in result
        assert result["complaint_resolution"].get("escalation_triggered") is True
        assert result["sentiment_escalation"].get("escalation_needed") is True
    
    @patch("backend.app.core.parwa.nodes._get_ei_engine")
    def test_low_intensity_complaint(self, mock_get_ei):
        mock_ei = MagicMock()
        mock_ei.assess_sentiment_escalation.return_value = {
            "escalation_needed": False,
            "escalation_level": "none",
            "trigger_reason": "",
            "priority_score": 0.1,
        }
        mock_ei.resolve_complaint.return_value = {
            "resolution_strategy": "acknowledge_and_resolve",
            "de_escalation_applied": False,
            "compensation_type": "none",
            "follow_up_scheduled": False,
            "escalation_triggered": False,
            "resolution_confidence": 0.9,
        }
        mock_get_ei.return_value = mock_ei

        state = _make_state(
            query="I'm a bit disappointed",
            pii_redacted_query="I'm a bit disappointed",
            classification={"intent": "complaint"},
            emotion_profile={"primary_emotion": "disappointed", "intensity": 0.3, "risk_level": "low", "escalation_trajectory": "stable", "secondary_emotions": []},
            recovery_playbook={"strategy": "acknowledge_and_resolve", "compensation": None, "escalation": False},
            customer_tier="free",
            empathy_score=0.6,
        )
        result = complaint_handler_node(state)
        assert result["complaint_resolution"].get("de_escalation_applied") is False
        assert result["complaint_resolution"].get("escalation_triggered") is False

    @patch("backend.app.core.parwa.nodes._get_ei_engine")
    def test_empty_state(self, mock_get_ei):
        mock_ei = MagicMock()
        mock_ei.assess_sentiment_escalation.return_value = {}
        mock_ei.resolve_complaint.return_value = {}
        mock_get_ei.return_value = mock_ei

        state = _make_state()
        result = complaint_handler_node(state)
        assert "complaint_resolution" in result
        assert "step_outputs" in result


class TestRetentionNegotiatorNode:
    """Test retention_negotiator_node execution."""
    
    @patch("backend.app.core.parwa.nodes._get_churn_engine")
    def test_high_churn_risk(self, mock_get_churn):
        mock_churn = MagicMock()
        mock_churn.negotiate_retention.return_value = {
            "negotiation_strategy": "aggressive_retention",
            "offer_presented": "temporary_discount",
            "counter_offers": ["account_pause", "plan_downgrade"],
            "acceptance_likelihood": 0.65,
            "negotiation_stage": "initial_offer",
        }
        mock_churn.generate_winback_automation.return_value = {
            "sequence_active": True,
            "sequence_steps": [{"step": 1, "action": "cancellation_confirmation"}],
            "total_duration_days": 30,
            "primary_offer": "temporary_discount",
        }
        mock_get_churn.return_value = mock_churn

        state = _make_state(
            classification={"intent": "cancellation"},
            churn_risk={"churn_probability": 0.8, "risk_tier": "high", "primary_reason": "price_sensitivity", "customer_value": "premium"},
            retention_offers={"primary_offer": {"offer_name": "temporary_discount", "automation_level": "full", "description": "20-30% discount"}, "contingency_offers": [{"offer_name": "account_pause"}]},
            customer_tier="growth",
        )
        result = retention_negotiator_node(state)
        assert "retention_negotiation" in result
        assert "winback_sequence" in result
        assert result["retention_negotiation"]["negotiation_strategy"] == "aggressive_retention"
    
    @patch("backend.app.core.parwa.nodes._get_churn_engine")
    def test_low_churn_risk(self, mock_get_churn):
        mock_churn = MagicMock()
        mock_churn.negotiate_retention.return_value = {
            "negotiation_strategy": "soft_retention",
            "offer_presented": "account_pause",
            "counter_offers": [],
            "acceptance_likelihood": 0.3,
            "negotiation_stage": "soft_offer",
        }
        mock_churn.generate_winback_automation.return_value = {
            "sequence_active": False,
            "sequence_steps": [],
            "total_duration_days": 0,
            "primary_offer": "",
        }
        mock_get_churn.return_value = mock_churn

        state = _make_state(
            classification={"intent": "cancellation"},
            churn_risk={"churn_probability": 0.2, "risk_tier": "low", "primary_reason": "general", "customer_value": "basic"},
            retention_offers={"primary_offer": {"offer_name": "account_pause", "automation_level": "full", "description": "Pause"}, "contingency_offers": []},
            customer_tier="free",
        )
        result = retention_negotiator_node(state)
        assert result["retention_negotiation"]["negotiation_strategy"] == "soft_retention"


class TestBillingResolverNode:
    """Test billing_resolver_node execution."""
    
    @patch("backend.app.core.parwa.nodes._get_billing_engine")
    def test_auto_resolvable_dispute(self, mock_get_billing):
        mock_billing = MagicMock()
        mock_billing.generate_self_service_context.return_value = {
            "portal_url": "https://billing.example.com",
            "available_actions": ["view_invoice", "request_refund"],
            "dispute_status": "auto_resolved",
            "refund_eligible": True,
        }
        mock_billing.auto_resolve_paddle_dispute.return_value = {
            "dispute_id": "dp_123",
            "auto_resolved": True,
            "resolution_action": "refund_duplicate",
            "refund_amount": 49.99,
            "processing_time_hours": 24,
        }
        mock_get_billing.return_value = mock_billing

        state = _make_state(
            billing_dispute={"dispute_category": "double_charge", "auto_resolvable": True, "resolution_type": "refund_duplicate", "max_refund_percentage": 100, "priority": "high"},
            billing_anomaly={"anomaly_detected": True, "anomaly_types": ["amount_deviation"], "severity": "high"},
            customer_tier="growth",
        )
        result = billing_resolver_node(state)
        assert "billing_self_service" in result
        assert "paddle_dispute" in result
        assert result["billing_self_service"].get("refund_eligible") is True
        assert result["paddle_dispute"].get("auto_resolved") is True
    
    @patch("backend.app.core.parwa.nodes._get_billing_engine")
    def test_manual_review_dispute(self, mock_get_billing):
        mock_billing = MagicMock()
        mock_billing.generate_self_service_context.return_value = {
            "portal_url": "https://billing.example.com",
            "available_actions": ["view_invoice"],
            "dispute_status": "manual_review_required",
            "refund_eligible": False,
        }
        mock_billing.auto_resolve_paddle_dispute.return_value = {
            "dispute_id": "dp_456",
            "auto_resolved": False,
            "resolution_action": "dispute_investigation",
            "refund_amount": None,
            "processing_time_hours": 72,
        }
        mock_get_billing.return_value = mock_billing

        state = _make_state(
            billing_dispute={"dispute_category": "unrecognized_charge", "auto_resolvable": False, "resolution_type": "dispute_investigation", "max_refund_percentage": 100, "priority": "high"},
            billing_anomaly={"anomaly_detected": False, "anomaly_types": [], "severity": "none"},
            customer_tier="free",
        )
        result = billing_resolver_node(state)
        assert result["billing_self_service"].get("refund_eligible") is False
        assert result["paddle_dispute"].get("auto_resolved") is False


class TestTechDiagnosticNode:
    """Test tech_diagnostic_node execution."""
    
    @patch("backend.app.core.parwa.nodes._get_tech_diag_engine")
    def test_known_issue(self, mock_get_tech):
        mock_tech = MagicMock()
        mock_tech.generate_diagnostic_result.return_value = {
            "steps_provided": 3,
            "known_issue_match": True,
            "severity_assessment": "high",
            "auto_fix_available": False,
            "resolution_path": "wait_for_fix",
        }
        mock_tech.decide_escalation.return_value = {
            "escalate": True,
            "escalation_level": "l2_specialist",
            "severity_factors": {"business_impact": 0.8},
            "recommended_actions": ["escalate"],
        }
        mock_get_tech.return_value = mock_tech

        state = _make_state(
            query="The site is down, I can't access anything",
            pii_redacted_query="The site is down, I can't access anything",
            known_issue={"known_issue_detected": True, "issue_id": "service_outage", "severity": "high", "resolution_type": "wait_for_fix", "eta_hours": 4},
            tech_diagnostics={"diagnostic_steps": [{"step": 1, "action": "Check connectivity"}]},
            severity_score={"severity_score": 0.7, "severity_level": "high", "escalation_path": "l2_specialist", "factors": {"business_impact": 0.8}, "recommended_actions": ["escalate"]},
            customer_tier="growth",
        )
        result = tech_diagnostic_node(state)
        assert "diagnostic_result" in result
        assert "escalation_decision" in result
        assert result["diagnostic_result"]["known_issue_match"] is True
    
    @patch("backend.app.core.parwa.nodes._get_tech_diag_engine")
    def test_self_service_fix(self, mock_get_tech):
        mock_tech = MagicMock()
        mock_tech.generate_diagnostic_result.return_value = {
            "steps_provided": 3,
            "known_issue_match": False,
            "severity_assessment": "low",
            "auto_fix_available": True,
            "resolution_path": "self_service",
        }
        mock_tech.decide_escalation.return_value = {
            "escalate": False,
            "escalation_level": "l1_self_service",
            "severity_factors": {},
            "recommended_actions": ["self_service"],
        }
        mock_get_tech.return_value = mock_tech

        state = _make_state(
            query="Something is not working",
            pii_redacted_query="Something is not working",
            known_issue={"known_issue_detected": False},
            tech_diagnostics={"diagnostic_steps": [{"step": 1}, {"step": 2}, {"step": 3}]},
            severity_score={"severity_score": 0.2, "severity_level": "low", "escalation_path": "l1_self_service", "factors": {}, "recommended_actions": ["self_service"]},
            customer_tier="free",
        )
        result = tech_diagnostic_node(state)
        assert result["diagnostic_result"]["auto_fix_available"] is True
        assert result["escalation_decision"]["escalate"] is False


class TestShippingTrackerNode:
    """Test shipping_tracker_node execution."""
    
    @patch("backend.app.core.parwa.nodes._get_shipping_engine")
    def test_delayed_shipment(self, mock_get_shipping):
        mock_shipping = MagicMock()
        mock_shipping.query_carrier_data.return_value = {
            "carrier": "FedEx",
            "tracking_status": "in_transit_delayed",
            "estimated_delivery": "2025-03-10",
            "carrier_api_called": True,
            "last_update": "2025-03-07T12:00:00Z",
        }
        mock_shipping.generate_delay_notification.return_value = {
            "notification_sent": True,
            "notification_type": "delay_notification",
            "delay_reason": "carrier_delay",
            "revised_eta": "2025-03-12",
            "compensation_offered": True,
        }
        mock_get_shipping.return_value = mock_shipping

        state = _make_state(
            tracking_info={"primary_carrier": "FedEx", "tracking_numbers": [{"carrier": "FedEx", "tracking_number": "123456789012"}]},
            shipping_issue={"issue_type": "delayed", "severity": "medium", "auto_resolvable": True, "resolution": "check_tracking_and_notify"},
            shipping_delay={"delay_detected": True, "compensation_eligible": True, "delay_reason": "carrier_delay"},
        )
        result = shipping_tracker_node(state)
        assert "shipping_carrier_data" in result
        assert "delay_notification" in result
        assert result["shipping_carrier_data"]["carrier"] == "FedEx"
        assert result["delay_notification"]["notification_sent"] is True
    
    @patch("backend.app.core.parwa.nodes._get_shipping_engine")
    def test_no_tracking(self, mock_get_shipping):
        mock_shipping = MagicMock()
        mock_shipping.query_carrier_data.return_value = {
            "carrier": "",
            "tracking_status": "",
            "estimated_delivery": "",
            "carrier_api_called": False,
            "last_update": "",
        }
        mock_shipping.generate_delay_notification.return_value = {
            "notification_sent": False,
            "notification_type": "",
            "delay_reason": "",
            "revised_eta": "",
            "compensation_offered": False,
        }
        mock_get_shipping.return_value = mock_shipping

        state = _make_state(
            tracking_info={"primary_carrier": "", "tracking_numbers": []},
            shipping_issue={"issue_type": "", "severity": "low", "auto_resolvable": False, "resolution": ""},
            shipping_delay={"delay_detected": False, "compensation_eligible": False, "delay_reason": ""},
        )
        result = shipping_tracker_node(state)
        assert result["shipping_carrier_data"]["carrier_api_called"] is False


# ══════════════════════════════════════════════════════════════════
# GRAPH BUILD TEST
# ══════════════════════════════════════════════════════════════════

class TestParwaGraphBuild:
    """Test that the Pro graph builds correctly with all 22 nodes."""
    
    def test_graph_builds(self):
        graph = build_parwa_graph()
        assert graph is not None

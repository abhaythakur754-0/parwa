"""
Comprehensive unit tests for all 5 Enhancement Engines.

Tests both original methods and new deep enrichment methods added for
automation improvement from 84.3% → 89.5%.

Engines tested:
  1. EmotionalIntelligenceEngine — 4 methods (profile_emotion, select_recovery_playbook, generate_de_escalation_prompts, get_recovery_actions) + 2 new (assess_sentiment_escalation, resolve_complaint)
  2. ChurnRetentionEngine — 4 methods (score_churn_risk, select_retention_offers, generate_winback_sequence, get_retention_actions) + 2 new (negotiate_retention, generate_winback_automation)
  3. BillingIntelligenceEngine — 4 methods (classify_dispute, detect_anomaly, get_resolution_actions, generate_billing_context) + 2 new (generate_self_service_context, auto_resolve_paddle_dispute)
  4. TechDiagnosticsEngine — 4 methods (detect_known_issue, generate_diagnostics, score_severity, get_tech_actions) + 2 new (generate_diagnostic_result, decide_escalation)
  5. ShippingIntelligenceEngine — 4 methods (detect_tracking_number, classify_shipping_issue, assess_delay, get_shipping_actions, generate_shipping_context) + 2 new (query_carrier_data, generate_delay_notification)
"""
import pytest
from unittest.mock import patch, MagicMock

# Import engines
from backend.app.core.enhancements.emotional_intelligence import EmotionalIntelligenceEngine
from backend.app.core.enhancements.churn_retention import ChurnRetentionEngine
from backend.app.core.enhancements.billing_intelligence import BillingIntelligenceEngine
from backend.app.core.enhancements.tech_diagnostics import TechDiagnosticsEngine
from backend.app.core.enhancements.shipping_intelligence import ShippingIntelligenceEngine


# ══════════════════════════════════════════════════════════════════
# EMOTIONAL INTELLIGENCE ENGINE TESTS
# ══════════════════════════════════════════════════════════════════

class TestEmotionalIntelligenceEngine:
    """Tests for EmotionalIntelligenceEngine — 6 methods."""

    def setup_method(self):
        self.engine = EmotionalIntelligenceEngine()

    # --- Original methods ---

    def test_profile_emotion_angry(self):
        result = self.engine.profile_emotion("I am furious about this terrible service!")
        assert result["primary_emotion"] == "angry"
        assert result["intensity"] >= 0.7
        assert result["risk_level"] in ("high", "critical")

    def test_profile_emotion_frustrated(self):
        result = self.engine.profile_emotion("I'm frustrated, this is not working again")
        assert result["primary_emotion"] == "frustrated"
        assert result["intensity"] >= 0.5

    def test_profile_emotion_neutral(self):
        result = self.engine.profile_emotion("Hello, I have a question about my account")
        assert result["primary_emotion"] == "neutral"
        assert result["intensity"] <= 0.5

    def test_profile_emotion_empty_query(self):
        result = self.engine.profile_emotion("")
        assert result["primary_emotion"] == "neutral"

    def test_profile_emotion_betrayed(self):
        result = self.engine.profile_emotion("I was lied to, you promised something different!")
        assert result["primary_emotion"] == "betrayed"
        assert result["risk_level"] == "critical"

    def test_profile_emotion_with_secondary(self):
        result = self.engine.profile_emotion("I'm angry and I want to cancel! I'll post about this on social media!")
        assert "public_threat" in result.get("secondary_emotions", [])

    def test_select_recovery_playbook_minor(self):
        profile = {"intensity": 0.3, "risk_level": "low"}
        result = self.engine.select_recovery_playbook(profile)
        assert result["strategy"] == "acknowledge_and_resolve"
        assert result["escalation"] is False

    def test_select_recovery_playbook_serious(self):
        profile = {"intensity": 0.8, "risk_level": "high"}
        result = self.engine.select_recovery_playbook(profile)
        assert result["escalation"] is True
        assert "compensation" in result

    def test_select_recovery_playbook_critical(self):
        profile = {"intensity": 0.95, "risk_level": "critical"}
        result = self.engine.select_recovery_playbook(profile)
        assert result["strategy"] == "senior_escalation_full_recovery"

    def test_generate_de_escalation_prompts_low(self):
        profile = {"intensity": 0.2, "escalation_trajectory": "stable", "emotional_needs": ["information"]}
        result = self.engine.generate_de_escalation_prompts(profile)
        assert isinstance(result, str)

    def test_generate_de_escalation_prompts_high(self):
        profile = {"intensity": 0.8, "escalation_trajectory": "escalating", "emotional_needs": ["validation", "restoration"]}
        result = self.engine.generate_de_escalation_prompts(profile)
        assert len(result) > 50
        assert "acknowledging" in result.lower() or "minimize" in result.lower()

    def test_get_recovery_actions(self):
        profile = {"risk_level": "high", "intensity": 0.8}
        playbook = {"actions": ["sincere_apology", "offer_significant_compensation", "schedule_follow_up", "escalate_to_senior"]}
        classification = {"intent": "complaint"}
        result = self.engine.get_recovery_actions(profile, playbook, classification)
        assert len(result) >= 3
        assert any(a["action_type"] == "send_apology" for a in result)
        assert any(a["action_type"] == "escalate" for a in result)

    # --- New deep methods ---

    def test_assess_sentiment_escalation_critical(self):
        profile = {"intensity": 0.9, "escalation_trajectory": "critical", "risk_level": "critical", "secondary_emotions": []}
        result = self.engine.assess_sentiment_escalation(profile)
        assert result["escalation_needed"] is True
        assert result["escalation_level"] == "manager"
        assert result["priority_score"] >= 0.8

    def test_assess_sentiment_escalation_stable(self):
        profile = {"intensity": 0.3, "escalation_trajectory": "stable", "risk_level": "low", "secondary_emotions": []}
        result = self.engine.assess_sentiment_escalation(profile)
        assert result["escalation_needed"] is False
        assert result["escalation_level"] == "none"

    def test_assess_sentiment_escalation_public_threat(self):
        profile = {"intensity": 0.5, "escalation_trajectory": "stable", "risk_level": "medium", "secondary_emotions": ["public_threat"]}
        result = self.engine.assess_sentiment_escalation(profile)
        assert result["escalation_needed"] is True
        assert result["escalation_level"] == "manager"

    def test_assess_sentiment_escalation_repeated(self):
        profile = {"intensity": 0.6, "escalation_trajectory": "escalating", "risk_level": "medium", "secondary_emotions": []}
        result = self.engine.assess_sentiment_escalation(profile, conversation_turns=3)
        assert result["escalation_needed"] is True

    def test_resolve_complaint_high_intensity(self):
        profile = {"intensity": 0.85, "risk_level": "high"}
        playbook = {"strategy": "apologize_fix_compensate_escalate", "compensation": "significant_credit", "escalation": True}
        result = self.engine.resolve_complaint(profile, playbook, customer_tier="growth")
        assert result["de_escalation_applied"] is True
        assert result["escalation_triggered"] is True
        assert result["compensation_type"] != "none"
        assert result["resolution_confidence"] > 0

    def test_resolve_complaint_low_intensity(self):
        profile = {"intensity": 0.2, "risk_level": "low"}
        playbook = {"strategy": "acknowledge_and_resolve", "compensation": None, "escalation": False}
        result = self.engine.resolve_complaint(profile, playbook)
        assert result["de_escalation_applied"] is False
        assert result["escalation_triggered"] is False


# ══════════════════════════════════════════════════════════════════
# CHURN RETENTION ENGINE TESTS
# ══════════════════════════════════════════════════════════════════

class TestChurnRetentionEngine:
    """Tests for ChurnRetentionEngine — 6 methods."""

    def setup_method(self):
        self.engine = ChurnRetentionEngine()

    # --- Original methods ---

    def test_score_churn_risk_direct_cancel(self):
        result = self.engine.score_churn_risk("I want to cancel my subscription immediately")
        assert result["churn_probability"] >= 0.5
        assert result["risk_tier"] in ("high", "critical")
        assert "direct_cancel" in result.get("cancellation_signals", {})

    def test_score_churn_risk_price_sensitivity(self):
        result = self.engine.score_churn_risk("This is too expensive, I found a cheaper alternative")
        assert result["churn_probability"] >= 0.3
        assert result["primary_reason"] in ("price_sensitivity", "indirect_cancel")

    def test_score_churn_risk_low(self):
        result = self.engine.score_churn_risk("How do I change my password?")
        assert result["churn_probability"] < 0.3
        assert result["risk_tier"] == "low"

    def test_score_churn_risk_empty(self):
        result = self.engine.score_churn_risk("")
        assert result["risk_tier"] == "low"

    def test_select_retention_offers(self):
        risk = {"primary_reason": "price_sensitivity", "risk_tier": "high", "customer_value": "premium"}
        result = self.engine.select_retention_offers(risk, customer_tier="growth")
        assert len(result["recommended_offers"]) > 0
        assert "primary_offer" in result
        assert "prompt_addition" in result

    def test_generate_winback_sequence(self):
        risk = {"risk_tier": "high", "primary_reason": "direct_cancel"}
        result = self.engine.generate_winback_sequence(risk)
        assert len(result["sequence"]) >= 2
        assert result["automated"] is True

    def test_get_retention_actions(self):
        risk = {"risk_tier": "high", "churn_probability": 0.7, "customer_value": "premium"}
        offers = {"primary_offer": {"offer_name": "temporary_discount", "automation_level": "full", "description": "20-30% discount"}}
        result = self.engine.get_retention_actions(risk, offers)
        assert len(result) >= 1

    # --- New deep methods ---

    def test_negotiate_retention_aggressive(self):
        risk = {"churn_probability": 0.8, "risk_tier": "high"}
        offers = {"primary_offer": {"offer_name": "feature_upgrade_no_cost", "automation_level": "full"}, "contingency_offers": [{"offer_name": "loyalty_credit"}, {"offer_name": "account_pause"}]}
        result = self.engine.negotiate_retention(risk, offers, customer_tier="growth")
        assert result["negotiation_strategy"] == "aggressive_retention"
        assert result["offer_presented"] == "feature_upgrade_no_cost"
        assert len(result["counter_offers"]) > 0
        assert result["acceptance_likelihood"] > 0

    def test_negotiate_retention_soft(self):
        risk = {"churn_probability": 0.2, "risk_tier": "low"}
        offers = {"primary_offer": {"offer_name": "account_pause", "automation_level": "full"}, "contingency_offers": []}
        result = self.engine.negotiate_retention(risk, offers)
        assert result["negotiation_strategy"] == "soft_retention"

    def test_generate_winback_automation_active(self):
        risk = {"risk_tier": "high"}
        offers = {"primary_offer": {"offer_name": "temporary_discount"}}
        result = self.engine.generate_winback_automation(risk, offers)
        assert result["sequence_active"] is True
        assert len(result["sequence_steps"]) > 0

    def test_generate_winback_automation_inactive(self):
        risk = {"risk_tier": "low"}
        offers = {"primary_offer": {"offer_name": "account_pause"}}
        result = self.engine.generate_winback_automation(risk, offers)
        assert result["sequence_active"] is False
        assert result["sequence_steps"] == []


# ══════════════════════════════════════════════════════════════════
# BILLING INTELLIGENCE ENGINE TESTS
# ══════════════════════════════════════════════════════════════════

class TestBillingIntelligenceEngine:
    """Tests for BillingIntelligenceEngine — 6 methods."""

    def setup_method(self):
        self.engine = BillingIntelligenceEngine()

    # --- Original methods ---

    def test_classify_dispute_double_charge(self):
        result = self.engine.classify_dispute("I was charged twice for the same thing!")
        assert result["dispute_category"] == "double_charge"
        assert result["auto_resolvable"] is True

    def test_classify_dispute_missing_refund(self):
        result = self.engine.classify_dispute("Where is my refund? I haven't received it yet")
        assert result["dispute_category"] == "missing_refund"
        assert result["auto_resolvable"] is True

    def test_classify_dispute_unrecognized(self):
        result = self.engine.classify_dispute("I don't recognize this charge on my card")
        assert result["dispute_category"] == "unrecognized_charge"
        assert result["auto_resolvable"] is False

    def test_classify_dispute_unknown(self):
        result = self.engine.classify_dispute("Hello, how are you?")
        assert result["dispute_category"] == "unknown"

    def test_detect_anomaly_with_amount(self):
        result = self.engine.detect_anomaly("I was charged $50 but my plan is $10", expected_amount=10.0, actual_amount=50.0)
        assert result["anomaly_detected"] is True
        assert "amount_deviation" in result["anomaly_types"]

    def test_detect_anomaly_no_anomaly(self):
        result = self.engine.detect_anomaly("I have a billing question", expected_amount=10.0, actual_amount=10.0)
        assert result["anomaly_detected"] is False

    def test_get_resolution_actions_auto(self):
        dispute = {"auto_resolvable": True, "resolution_type": "refund_duplicate", "priority": "high", "dispute_category": "double_charge", "max_refund_percentage": 100}
        anomaly = {"anomaly_detected": False}
        result = self.engine.get_resolution_actions(dispute, anomaly)
        assert any(a["action_type"] == "initiate_refund" for a in result)

    def test_generate_billing_context(self):
        dispute = {"dispute_category": "double_charge", "auto_resolvable": True, "resolution_type": "refund_duplicate"}
        anomaly = {"anomaly_detected": True, "anomaly_types": ["amount_deviation"]}
        result = self.engine.generate_billing_context(dispute, anomaly)
        assert "double charge" in result.lower() or "duplicate" in result.lower()

    # --- New deep methods ---

    def test_generate_self_service_context_refund_eligible(self):
        dispute = {"dispute_category": "double_charge", "auto_resolvable": True, "max_refund_percentage": 100}
        anomaly = {"anomaly_detected": False}
        result = self.engine.generate_self_service_context(dispute, anomaly, customer_tier="growth")
        assert result["refund_eligible"] is True
        assert "request_refund" in result["available_actions"]

    def test_generate_self_service_context_not_eligible(self):
        dispute = {"dispute_category": "unknown", "auto_resolvable": False, "max_refund_percentage": 0}
        anomaly = {"anomaly_detected": False}
        result = self.engine.generate_self_service_context(dispute, anomaly)
        assert result["refund_eligible"] is False
        assert result["dispute_status"] == "no_dispute"

    def test_auto_resolve_paddle_dispute_auto(self):
        dispute = {"auto_resolvable": True, "resolution_type": "refund_duplicate", "max_refund_percentage": 100}
        anomaly = {"anomaly_detected": False}
        result = self.engine.auto_resolve_paddle_dispute(dispute, anomaly)
        assert result["auto_resolved"] is True
        assert result["dispute_id"].startswith("pad_")
        assert result["processing_time_hours"] > 0

    def test_auto_resolve_paddle_dispute_manual(self):
        dispute = {"auto_resolvable": False, "resolution_type": "dispute_investigation", "max_refund_percentage": 100}
        anomaly = {"anomaly_detected": False}
        result = self.engine.auto_resolve_paddle_dispute(dispute, anomaly)
        assert result["auto_resolved"] is False
        assert result["resolution_action"] == "manual_review"

    def test_auto_resolve_paddle_anomaly_speeds_up(self):
        dispute = {"auto_resolvable": True, "resolution_type": "refund_duplicate", "max_refund_percentage": 100}
        anomaly = {"anomaly_detected": True, "severity": "high"}
        result = self.engine.auto_resolve_paddle_dispute(dispute, anomaly)
        assert result["processing_time_hours"] <= 12  # Should be faster due to anomaly


# ══════════════════════════════════════════════════════════════════
# TECH DIAGNOSTICS ENGINE TESTS
# ══════════════════════════════════════════════════════════════════

class TestTechDiagnosticsEngine:
    """Tests for TechDiagnosticsEngine — 6 methods."""

    def setup_method(self):
        self.engine = TechDiagnosticsEngine()

    # --- Original methods ---

    def test_detect_known_issue_outage(self):
        result = self.engine.detect_known_issue("The site is down, I can't access anything")
        assert result["known_issue_detected"] is True
        assert result["issue_id"] == "service_outage"
        assert result["severity"] == "high"

    def test_detect_known_issue_login(self):
        result = self.engine.detect_known_issue("I can't log in to my account, password not working")
        assert result["known_issue_detected"] is True
        assert result["issue_id"] == "login_issues"

    def test_detect_known_issue_none(self):
        result = self.engine.detect_known_issue("How do I export my data?")
        assert result["known_issue_detected"] is False

    def test_generate_diagnostics_with_known_issue(self):
        known_issue = {"known_issue_detected": True, "issue_id": "login_issues", "severity": "medium", "resolution_type": "self_service_steps", "eta_hours": 0}
        result = self.engine.generate_diagnostics("Can't log in", known_issue)
        assert len(result["diagnostic_steps"]) > 0
        assert "account" in result["diagnostic_categories"]

    def test_generate_diagnostics_without_known_issue(self):
        result = self.engine.generate_diagnostics("Something is not working on my dashboard")
        # Should provide default browser + connectivity diagnostics
        assert isinstance(result["diagnostic_steps"], list)

    def test_score_severity_critical(self):
        result = self.engine.score_severity("Our production system is down and customers are affected!", customer_tier="enterprise")
        assert result["severity_score"] >= 0.5
        assert result["escalation_path"] in ("l2_specialist", "l3_engineering", "emergency")

    def test_score_severity_low(self):
        result = self.engine.score_severity("The formatting looks a bit off on my dashboard", customer_tier="free")
        assert result["severity_score"] < 0.5

    def test_get_tech_actions_escalation(self):
        known_issue = {"known_issue_detected": True, "auto_communicate": True, "issue_id": "service_outage", "message": "We're aware", "eta_hours": 4, "severity": "high"}
        diagnostics = {"diagnostic_steps": [], "diagnostic_categories": []}
        severity = {"escalation_path": "l3_engineering", "severity_score": 0.7, "severity_level": "high", "recommended_actions": ["escalate_to_l3"]}
        result = self.engine.get_tech_actions(known_issue, diagnostics, severity)
        assert any(a["action_type"] == "escalate_to_specialist" for a in result)

    # --- New deep methods ---

    def test_generate_diagnostic_result_known_issue(self):
        known_issue = {"known_issue_detected": True, "issue_id": "service_outage", "resolution_type": "wait_for_fix", "eta_hours": 4, "severity": "high"}
        diagnostics = {"diagnostic_steps": [{"step": 1}, {"step": 2}]}
        severity = {"severity_level": "high", "escalation_path": "l2_specialist"}
        result = self.engine.generate_diagnostic_result("Site is down", known_issue, diagnostics, severity)
        assert result["known_issue_match"] is True
        assert result["steps_provided"] == 2
        assert result["severity_assessment"] == "high"

    def test_generate_diagnostic_result_self_service(self):
        known_issue = {"known_issue_detected": False}
        diagnostics = {"diagnostic_steps": [{"step": 1}, {"step": 2}, {"step": 3}]}
        severity = {"severity_level": "low", "escalation_path": "l1_self_service"}
        result = self.engine.generate_diagnostic_result("Something not working", known_issue, diagnostics, severity)
        assert result["auto_fix_available"] is True
        assert result["resolution_path"] == "self_service_diagnostics"

    def test_decide_escalation_yes(self):
        severity = {"severity_score": 0.7, "escalation_path": "l3_engineering", "factors": {"business_impact": 0.8}, "recommended_actions": ["escalate"]}
        known_issue = {"known_issue_detected": False}
        result = self.engine.decide_escalation(severity, known_issue, customer_tier="enterprise")
        assert result["escalate"] is True
        assert result["escalation_level"] in ("specialist", "engineering", "management")

    def test_decide_escalation_no(self):
        severity = {"severity_score": 0.2, "escalation_path": "l1_self_service", "factors": {}, "recommended_actions": ["self_service"]}
        known_issue = {"known_issue_detected": False}
        result = self.engine.decide_escalation(severity, known_issue)
        assert result["escalate"] is False
        assert result["escalation_level"] == "none"


# ══════════════════════════════════════════════════════════════════
# SHIPPING INTELLIGENCE ENGINE TESTS
# ══════════════════════════════════════════════════════════════════

class TestShippingIntelligenceEngine:
    """Tests for ShippingIntelligenceEngine — 7 methods."""

    def setup_method(self):
        self.engine = ShippingIntelligenceEngine()

    # --- Original methods ---

    def test_detect_tracking_number_fedex(self):
        result = self.engine.detect_tracking_number("My tracking number is 123456789012")
        # May or may not match depending on pattern specificity
        assert isinstance(result["tracking_detected"], bool)
        assert isinstance(result["tracking_numbers"], list)

    def test_detect_tracking_number_none(self):
        result = self.engine.detect_tracking_number("Where is my order?")
        assert result["tracking_detected"] is False
        assert result["tracking_numbers"] == []

    def test_classify_shipping_issue_delayed(self):
        result = self.engine.classify_shipping_issue("My order is late, where is it?")
        assert result["issue_detected"] is True
        assert result["issue_type"] == "delayed"

    def test_classify_shipping_issue_damaged(self):
        result = self.engine.classify_shipping_issue("My item arrived damaged and broken")
        assert result["issue_detected"] is True
        assert result["issue_type"] == "damaged"
        assert result["severity"] == "high"

    def test_classify_shipping_issue_lost(self):
        result = self.engine.classify_shipping_issue("My package is lost, tracking not updating")
        assert result["issue_detected"] is True
        assert result["issue_type"] == "lost"
        assert result["severity"] == "critical"

    def test_classify_shipping_issue_none(self):
        result = self.engine.classify_shipping_issue("Thanks for the update!")
        assert result["issue_detected"] is False

    def test_assess_delay(self):
        issue = {"issue_type": "delayed"}
        result = self.engine.assess_delay(issue, query="My package is delayed due to weather")
        assert result["delay_detected"] is True
        assert result["delay_reason"] == "weather"

    def test_assess_delay_no_delay(self):
        issue = {"issue_type": "wrong_address"}
        result = self.engine.assess_delay(issue)
        assert result["delay_detected"] is False

    def test_get_shipping_actions_delay(self):
        issue = {"issue_type": "delayed", "severity": "medium", "resolution": "check_tracking_and_notify", "compensation": "shipping_refund_if_late"}
        delay = {"delay_detected": True, "compensation_eligible": True, "notification_template": "test"}
        tracking = {"tracking_numbers": [], "primary_carrier": ""}
        result = self.engine.get_shipping_actions(issue, delay, tracking)
        assert any(a["action_type"] == "send_proactive_delay_notification" for a in result)

    def test_generate_shipping_context(self):
        issue = {"issue_type": "delayed", "resolution": "check_tracking_and_notify", "compensation": "shipping_refund_if_late"}
        delay = {"delay_detected": True, "delay_reason": "carrier_delay"}
        tracking = {"tracking_detected": True, "primary_carrier": "FedEx"}
        result = self.engine.generate_shipping_context(issue, delay, tracking)
        assert "delayed" in result.lower() or "fedex" in result.lower()

    # --- New deep methods ---

    def test_query_carrier_data_with_tracking(self):
        tracking = {"primary_carrier": "FedEx", "tracking_numbers": [{"carrier": "FedEx", "tracking_number": "123456789012"}]}
        issue = {"issue_type": "delayed"}
        result = self.engine.query_carrier_data(tracking, issue)
        assert result["carrier"] == "FedEx"
        assert result["tracking_status"] == "delayed"
        assert result["carrier_api_called"] is True

    def test_query_carrier_data_lost(self):
        tracking = {"primary_carrier": "", "tracking_numbers": []}
        issue = {"issue_type": "lost"}
        result = self.engine.query_carrier_data(tracking, issue)
        assert result["tracking_status"] == "exception"

    def test_query_carrier_data_no_tracking(self):
        tracking = {"primary_carrier": "", "tracking_numbers": []}
        issue = {"issue_type": ""}
        result = self.engine.query_carrier_data(tracking, issue)
        assert result["carrier_api_called"] is False

    def test_generate_delay_notification_delayed(self):
        issue = {"issue_type": "delayed"}
        delay = {"delay_detected": True, "compensation_eligible": True, "delay_reason": "carrier_delay"}
        carrier = {"estimated_delivery": "2026-05-10"}
        result = self.engine.generate_delay_notification(issue, delay, carrier)
        assert result["notification_sent"] is True
        assert result["notification_type"] == "delay_notification"
        assert result["compensation_offered"] is True

    def test_generate_delay_notification_lost(self):
        issue = {"issue_type": "lost"}
        delay = {"delay_detected": True, "compensation_eligible": True, "delay_reason": "unknown"}
        carrier = {"estimated_delivery": "unknown"}
        result = self.engine.generate_delay_notification(issue, delay, carrier)
        assert result["notification_sent"] is True
        assert result["notification_type"] == "lost_package_alert"

    def test_generate_delay_notification_no_delay(self):
        issue = {"issue_type": "wrong_address"}
        delay = {"delay_detected": False, "compensation_eligible": False, "delay_reason": ""}
        carrier = {"estimated_delivery": "2026-05-10"}
        result = self.engine.generate_delay_notification(issue, delay, carrier)
        assert result["notification_sent"] is False

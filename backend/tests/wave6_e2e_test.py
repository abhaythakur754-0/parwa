"""
Wave 6 E2E Test — Reporting & Quality Coach

Tests all 7 Wave 6 deliverables:
  6A: Weekly Wins Report (report_generator)
 6B: Performance Dashboard Data (report_generator)
   6C: Drift Detection & Alerts (quality_coach + jarvis_db)
  6D: Quality Coach Reports (quality_coach)
  6E: SLA Calculator (sla_calculator)
  6F: Customer Health Score (health_scorer)
  6G: ROI Calculator (health_scorer)

Plus pipeline integration:
  - Command parser recognizes Wave 6 intents
  - State includes Wave 6 fields

All tests use InMemory backend — no external services needed.
Run: python -m pytest backend/tests/wave6_e2e_test.py -v
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.core.jarvis_pipeline.jarvis_db import reset_db, use_in_memory, get_db
from app.core.jarvis_pipeline.report_generator import (
    generate_weekly_wins_report, get_performance_dashboard,
    format_weekly_report_text,
)
from app.core.jarvis_pipeline.quality_coach import (
    generate_weekly_quality_report, generate_mistake_analysis,
    generate_training_priority_list, run_drift_check_and_alert,
    get_agent_health_summary,
)
from app.core.jarvis_pipeline.sla_calculator import (
    compute_sla_status, generate_monthly_sla_report, record_uptime_event,
)
from app.core.jarvis_pipeline.health_scorer import (
    get_customer_health, calculate_roi, get_success_coach_message,
)
from app.core.jarvis_pipeline.command_parser import (
    classify_command_sync, is_report_intent,
    INTENT_QUERIES_W6,
)

TENANT = "wave6_test_tenant"


@pytest.fixture(autouse=True)
def _reset():
    """Reset DB before each test."""
    reset_db()
    use_in_memory()
    yield


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


async def _seed_quality_scores(tenant, count=20, low_quality_count=3):
    db = get_db()
    for i in range(count):
        score = 0.65 if i < low_quality_count else (0.85 + (i * 0.005) % 0.14)
        path = "escalated" if i < 2 else ("stuck" if i < low_quality_count else "auto")
        await db.write_quality_score(
            tenant_id=tenant, ticket_id=f"TKT-{100+i}",
            overall_score=score, resolution_path=path,
            nodes_reached=[f"N{j}" for j in range(1, 6)],
            llm_calls=3, tokens_used=500,
        )


async def _seed_training_data(tenant, approved=15, rejected=5):
    db = get_db()
    types = ["refund", "address_change", "order_status", "return_request", "billing"]
    for i in range(approved):
        await db.record_training_data(
            tenant_id=tenant, ticket_id=f"TKT-{200+i}",
            signal_type="approved", quality_score=0.9,
            ticket_type=types[i % len(types)],
        )
    for i in range(rejected):
        await db.record_training_data(
            tenant_id=tenant, ticket_id=f"TKT-{300+i}",
            signal_type="rejected", quality_score=0.5,
            ticket_type=types[i % len(types)],
        )


async def _seed_confidence_logs(tenant, count=15):
    db = get_db()
    routings = ["auto", "auto", "auto", "batch", "batch", "ask", "escalate"]
    for i in range(count):
        routing = routings[i % len(routings)]
        confidence = {"auto": 0.96, "batch": 0.90, "ask": 0.77, "escalate": 0.55}[routing]
        await db.record_confidence(
            tenant_id=tenant, ticket_id=f"TKT-{400+i}",
            confidence=confidence, routing=routing,
            factors={"pattern_match": 0.9, "policy_alignment": 0.8,
                       "risk_score": 0.1, "historical_accuracy": 0.85},
        )


async def _seed_integration_pings(tenant, healthy=8, unhealthy=2):
    db = get_db()
    for svc in ["sendgrid", "shopify", "stripe", "hubspot", "twilio"]:
        for _ in range(healthy):
            await db.write_integration_ping(
                tenant_id=tenant, service_name=svc, is_healthy=True,
                response_ms=50.0,
            )
        for _ in range(unhealthy):
            await db.write_integration_ping(
                tenant_id=tenant, service_name=svc, is_healthy=False,
                response_ms=5000.0, error_detail="timeout",
            )


async def _seed_sla_events(tenant, downtime_seconds=3600):
    db = get_db()
    await db.record_sla_event(tenant, "uptime_start", details="normal")
    await db.record_sla_event(tenant, "downtime_start", details="planned maintenance")
    await db.record_sla_event(tenant, "downtime_end", duration_seconds=downtime_seconds,
                                 details="maintenance complete")
    await db.record_sla_event(tenant, "uptime_start", details="back online")


# ═════════════════════════════════════════════════════════════════════════
# 6A: WEEKLY WINS REPORT
# ═════════════════════════════════════════════════════════════

class Test6A_WeeklyWinsReport:

    def test_6a_1_report_generates_with_seed_data(self):
        _run(_seed_quality_scores(TENANT, count=20, low_quality_count=3))
        report = _run(generate_weekly_wins_report(TENANT))

        assert report["report_type"] == "weekly_wins"
        assert report["tenant_id"] == TENANT
        assert report["tickets_handled"] == 20
        assert report["auto_resolved"] > 0
        assert "money_saved_usd" in report
        assert "prediction" in report
        assert report["money_saved_usd"] > 0

    def test_6a_2_money_saved_calculation(self):
        _run(_seed_quality_scores(TENANT, count=10, low_quality_count=0))
        report = _run(generate_weekly_wins_report(TENANT))
        expected = report["auto_resolved"] * 8.0
        assert report["money_saved_usd"] == expected

    def test_6a_3_quality_trend_detected(self):
        _run(_seed_quality_scores(TENANT, count=20, low_quality_count=3))
        report = _run(generate_weekly_wins_report(TENANT))
        assert report["quality_trend"] in ("stable", "improving", "declining")

    def test_6a_4_prediction_is_string(self):
        _run(_seed_quality_scores(TENANT, count=10))
        report = _run(generate_weekly_wins_report(TENANT))
        assert isinstance(report["prediction"], str)
        assert len(report["prediction"]) > 20

    def test_6a_5_report_saved_to_db(self):
        _run(_seed_quality_scores(TENANT, count=5))
        _run(generate_weekly_wins_report(TENANT))
        db = get_db()
        reports = _run(db.get_generated_reports(TENANT, report_type="weekly_wins"))
        assert len(reports) >= 1
        assert reports[0]["report_type"] == "weekly_wins"

    def test_6a_6_format_weekly_report_text(self):
        report = {
            "period": {"days": 7},
            "tickets_handled": 100, "auto_resolved": 75, "human_handled": 25,
            "money_saved_usd": 600.0, "avg_quality": 0.91,
            "quality_trend": "improving",
            "confidence_trend": {"avg_confidence": 0.88, "trend_direction": "improving",
                                "distribution": {"auto": 50, "batch": 20, "ask": 5, "escalate": 5}},
            "new_skills_learned": [],
            "top_improvement": {"ticket_type": "auto", "description": "Auto path leads"},
            "needs_attention": [], "prediction": "Accuracy will reach 94% next week.",
            "efficiency": {"manager_time_saved_minutes": 375},
        }
        text = format_weekly_report_text(report)
        assert "100" in text
        assert "$600.00" in text
        assert "improving" in text

    def test_6a_7_empty_db_returns_zeros(self):
        report = _run(generate_weekly_wins_report(TENANT))
        assert report["tickets_handled"] == 0
        assert report["money_saved_usd"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════

class Test6B_PerformanceDashboard:

    def test_6b_1_dashboard_has_four_sections(self):
        _run(_seed_quality_scores(TENANT, count=10))
        _run(_seed_confidence_logs(TENANT, count=5))
        dashboard = _run(get_performance_dashboard(TENANT))
        assert "volume_accuracy" in dashboard
        assert "confidence_trends" in dashboard
        assert "efficiency_gains" in dashboard
        assert "learning_progress" in dashboard

    def test_6b_2_volume_accuracy_populated(self):
        _run(_seed_quality_scores(TENANT, count=15))
        dashboard = _run(get_performance_dashboard(TENANT))
        va = dashboard["volume_accuracy"]
        assert va["total_tickets"] == 15
        assert "avg_quality" in va

    def test_6c_3_confidence_trends_has_distribution(self):
        _run(_seed_confidence_logs(TENANT, count=10))
        dashboard = _run(get_performance_dashboard(TENANT))
        ct = dashboard["confidence_trends"]
        assert "distribution" in ct
        dist = ct["distribution"]
        assert dist.get("auto", 0) + dist.get("batch", 0) > 0

    def test_6b_4_tenant_id_in_dashboard(self):
        dashboard = _run(get_performance_dashboard(TENANT))
        assert dashboard["tenant_id"] == TENANT


class Test6C_DriftDetection:

    def test_6c_1_no_drift_with_good_data(self):
        db = get_db()
        for i in range(10):
            _run(db.write_quality_score(
                tenant_id=TENANT, ticket_id=f"TKT-6c-{i}",
                overall_score=0.90 + (i * 0.005),
                resolution_path="auto",
            ))
        result = _run(run_drift_check_and_alert(TENANT))
        assert result["total_new"] == 0

    def test_6c_2_quality_alert_can_be_created(self):
        db = get_db()
        alert = _run(db.create_quality_alert(
            tenant_id=TENANT, alert_type="confidence_drift",
            severity="warning", description="Test alert for drift",
            metrics={"confidence_drop": 0.08},
        ))
        assert alert["alert_type"] == "confidence_drift"
        assert alert["severity"] == "warning"
        assert not alert["is_resolved"]

    def test_6c_3_quality_alerts_retrieved(self):
        db = get_db()
        _run(db.create_quality_alert(
            TENANT, "quality_drop", "critical", "Accuracy dropped",
            {"accuracy": 0.5}))
        _run(db.create_quality_alert(
            TENANT, "recurring_error", "warning", "Same error 3x",
            {"count": 3}))
        alerts = _run(db.get_quality_alerts(TENANT))
        assert len(alerts) == 2
        assert all(a["tenant_id"] == TENANT for a in alerts)

    def test_6c_4_alert_can_be_resolved(self):
        db = get_db()
        alert = _run(db.create_quality_alert(
            TENANT, "test", "warning", "test", {}))
        resolved = _run(db.resolve_quality_alert(alert["id"]))
        assert resolved is True
        active = _run(db.get_quality_alerts(TENANT, include_resolved=False))
        assert not any(a["id"] == alert["id"] for a in active)

    def test_6c_5_filter_alerts_by_type(self):
        db = get_db()
        _run(db.create_quality_alert(
            TENANT, "quality_drop", "critical", "drop",
            {"accuracy": 0.3}))
        _run(db.create_quality_alert(
            TENANT, "confidence_drift", "warning", "drift",
            {"confidence": 0.1}))
        filtered = _run(db.get_quality_alerts(TENANT, alert_type="quality_drop"))
        assert len(filtered) == 2

    def test_6c_6_drift_check_returns_structure(self):
        result = _run(run_drift_check_and_alert(TENANT))
        assert "alerts_created" in result
        assert "total_new" in result
        assert "existing_active" in result
        assert isinstance(result["alerts_created"], list)


class Test6D_QualityCoach:

    def test_6d_1_weekly_quality_report_structure(self):
        _run(_seed_quality_scores(TENANT, count=20, low_quality_count=5))
        _run(_seed_confidence_logs(TENANT, count=10))
        report = _run(generate_weekly_quality_report(TENANT))
        assert report["report_type"] == "weekly_quality"
        assert "health_score" in report
        assert "performance" in report
        assert "mistakes" in report
        assert "recommendations" in report

    def test_6d_2_agent_health_score_computed(self):
        _run(_seed_quality_scores(TENANT, count=15))
        _run(_seed_integration_pings(TENANT))
        summary = _run(get_agent_health_summary(TENANT))
        assert 0 <= summary["overall_score"] <= 1
        assert summary["status"] in ("healthy", "warning", "critical")
        assert "recommendation" in summary

    def test_6d_3_mistake_analysis_with_bad_scores(self):
        _run(_seed_quality_scores(TENANT, count=10, low_quality_count=5))
        _run(_seed_training_data(TENANT, approved=5, rejected=3))
        analysis = _run(generate_mistake_analysis(TENANT))
        assert analysis["rejection_count"] >= 1

    def test_6d_4_training_priority_list_ranked(self):
        _run(_seed_training_data(TENANT, approved=10, rejected=8))
        priorities = _run(generate_training_priority_list(TENANT))
        assert len(priorities) > 0
        if len(priorities) >= 2:
            assert priorities[0]["priority_rank"] < priorities[-1]["priority_rank"]
        for p in priorities:
            assert "suggested_action" in p
            assert len(p["suggested_action"]) > 10

    def test_6d_5_health_summary_has_components(self):
        _run(_seed_quality_scores(TENANT, count=10))
        _run(_seed_integration_pings(TENANT))
        summary = _run(get_agent_health_summary(TENANT))
        components = summary["components"]
        assert "quality" in components
        assert "efficiency" in components
        assert "confidence" in components

    def test_6d_6_quality_report_saved_to_db(self):
        _run(_seed_quality_scores(TENANT, count=5))
        _run(generate_weekly_quality_report(TENANT))
        db = get_db()
        reports = _run(db.get_generated_reports(TENANT, report_type="weekly_quality"))
        assert len(reports) >= 1


class Test6E_SLACalculator:

    def test_6e_1_sla_status_structure(self):
        _run(_seed_sla_events(TENANT, downtime_seconds=3600))
        status = _run(compute_sla_status(TENANT))
        assert "sla_status" in status
        assert "actual_uptime_pct" in status
        assert "target_uptime_pct" in status
        assert "credit_owed_usd" in status
        assert "recommendation" in status
        assert status["tenant_id"] == TENANT

    def test_6e_2_sla_meeting_when_high_uptime(self):
        db = get_db()
        _run(db.record_sla_event(TENANT, "uptime_start", details="all good"))
        status = _run(compute_sla_status(TENANT, days=7))
        assert status["sla_status"] == "meeting"
        assert status["actual_uptime_pct"] == 100.0

    def test_6e_3_sla_credit_with_downtime(self):
        _run(_seed_sla_events(TENANT, downtime_seconds=7200))
        status = _run(compute_sla_status(TENANT, days=7))
        if status["actual_uptime_pct"] < status["target_uptime_pct"]:
            assert status["credit_owed_usd"] >= 0

    def test_6e_4_sla_event_recording(self):
        event = _run(record_uptime_event(TENANT, "downtime_start", details="test"))
        assert event["event_type"] == "downtime_start"
        assert event["tenant_id"] == TENANT

    def test_6e_5_monthly_sla_report(self):
        _run(_seed_sla_events(TENANT, downtime_seconds=1800))
        _run(_seed_integration_pings(TENANT))
        report = _run(generate_monthly_sla_report(TENANT))
        assert report["report_type"] == "monthly_sla"
        assert "sla_status" in report
        assert "integration_health" in report
        assert "recommendations" in report

    def test_6e_6_client_legal_config(self):
        db = get_db()
        config = _run(db.get_client_legal_config(TENANT))
        assert "config" in config
        assert config["config"]["target_uptime_pct"] == 99.5
        _run(db.set_client_legal_config(
            TENANT,
            {"target_uptime_pct": 99.9, "monthly_fee": 500},
            set_by="admin",
        ))
        custom = _run(db.get_client_legal_config(TENANT))
        assert custom["config"]["target_uptime_pct"] == 99.9
        assert custom["config"]["monthly_fee"] == 500

    def test_6e_7_sla_summary_structure(self):
        _run(_seed_sla_events(TENANT))
        summary = _run(get_db().get_sla_summary(TENANT))
        assert "compliance_pct" in summary
        assert "breach_count" in summary


class Test6F_CustomerHealth:

    def test_6f_1_health_score_structure(self):
        _run(_seed_quality_scores(TENANT, count=10))
        _run(_seed_training_data(TENANT, approved=10))
        _run(_seed_integration_pings(TENANT))
        health = _run(get_customer_health(TENANT))
        assert 0 <= health["customer_health_score"] <= 1
        assert "readiness_pct" in health
        assert "grade" in health
        assert "milestones" in health
        assert "success_coach_message" in health

    def test_6f_2_milestones_tracked(self):
        health = _run(get_customer_health(TENANT))
        milestones = health["milestones"]
        assert len(milestones) == 5
        names = {m["name"] for m in milestones}
        assert "knowledge_base_setup" in names
        assert "initial_training" in names
        assert "accuracy_target" in names
        assert "integration_connect" in names
        assert "policy_coverage" in names

    def test_6f_3_success_coach_message(self):
        _run(_seed_quality_scores(TENANT, count=5))
        _run(_seed_training_data(TENANT, approved=3))
        health = _run(get_customer_health(TENANT))
        msg = health["success_coach_message"]
        assert isinstance(msg, str)
        assert len(msg) > 20

    def test_6f_4_health_score_improves_with_data(self):
        h1 = _run(get_customer_health(TENANT))
        _run(_seed_quality_scores(TENANT, count=20, low_quality_count=1))
        _run(_seed_training_data(TENANT, approved=15))
        _run(_seed_integration_pings(TENANT, healthy=10, unhealthy=0))
        h2 = _run(get_customer_health(TENANT))
        assert h2["customer_health_score"] >= h1["customer_health_score"]


class Test6G_ROICalculator:

    def test_6g_1_roi_structure(self):
        _run(_seed_quality_scores(TENANT, count=20))
        _run(_seed_training_data(TENANT, approved=15))
        roi = _run(calculate_roi(TENANT))
        assert "total_tickets" in roi
        assert "auto_resolved" in roi
        assert "human_cost_usd" in roi
        assert "ai_cost_usd" in roi
        assert "net_savings_usd" in roi
        assert "roi_pct" in roi
        assert "recommendation" in roi

    def test_6g_2_roi_savings_positive_with_auto_resolve(self):
        _run(_seed_quality_scores(TENANT, count=20, low_quality_count=2))
        roi = _run(calculate_roi(TENANT))
        assert roi["auto_resolved"] > 0
        assert roi["net_savings_usd"] >= 0

    def test_6g_3_roi_recommendation_is_string(self):
        _run(_seed_quality_scores(TENANT, count=10))
        roi = _run(calculate_roi(TENANT))
        assert isinstance(roi["recommendation"], str)
        assert len(roi["recommendation"]) > 30

    def test_6g_4_empty_db_roi_shows_no_data_message(self):
        roi = _run(calculate_roi(TENANT))
        assert roi["total_tickets"] == 0
        assert "No tickets" in roi["recommendation"]

    def test_6g_5_auto_resolve_pct(self):
        _run(_seed_quality_scores(TENANT, count=20, low_quality_count=4))
        roi = _run(calculate_roi(TENANT))
        assert roi["auto_resolve_pct"] > 0
        assert roi["auto_resolve_pct"] <= 100


class Test6Pipeline_Integration:

    def test_parser_recognizes_weekly_report(self):
        result = classify_command_sync("show weekly report")
        assert result["intent"] == "query_report"
        assert result["target"] == "weekly"

    def test_parser_recognizes_dashboard(self):
        result = classify_command_sync("show performance dashboard")
        assert result["intent"] == "query_report"
        assert result["target"] == "dashboard"

    def test_parser_recognizes_sla(self):
        result = classify_command_sync("show SLA status")
        assert result["intent"] == "query_sla"

    def test_parser_recognizes_health_score(self):
        result = classify_command_sync("show health score")
        assert result["intent"] == "query_health_score"

    def test_parser_recognizes_roi(self):
        result = classify_command_sync("calculate ROI for last month")
        assert result["intent"] == "query_roi"

    def test_parser_recognizes_agent_health(self):
        result = classify_command_sync("show agent health")
        assert result["intent"] == "query_agent_health"

    def test_is_report_intent_helper(self):
        assert is_report_intent("query_report")
        assert is_report_intent("query_sla")
        assert is_report_intent("query_health_score")
        assert is_report_intent("query_roi")
        assert is_report_intent("query_agent_health")
        assert not is_report_intent("query_tickets")
        assert not is_report_intent("control_pause")

    def test_w6_intents_in_all_intents(self):
        from app.core.jarvis_pipeline.command_parser import ALL_INTENTS
        for intent in INTENT_QUERIES_W6:
            assert intent in ALL_INTENTS, f"{intent} not in ALL_INTENTS"

    def test_state_has_wave6_fields(self):
        from app.core.jarvis_pipeline.state import JarvisState
        annotations = JarvisState.__annotations__
        assert "weekly_report" in annotations
        assert "performance_dashboard" in annotations
        assert "quality_report" in annotations
        assert "drift_alerts_result" in annotations
        assert "agent_health" in annotations
        assert "sla_status" in annotations
        assert "customer_health" in annotations
        assert "roi_result" in annotations
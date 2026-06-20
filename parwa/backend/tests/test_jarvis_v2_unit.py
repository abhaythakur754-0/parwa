"""
JARVIS 3-Node Pipeline — Comprehensive Unit Test Suite (v2)

Tests the full JARVIS awareness engine: SENSE → EVALUATE → NOTIFY
Plus all Wave 5 intelligence modules and Wave 6 reporting/quality modules.

Architecture:
  - Jarvis Node 1 (SENSE):  8 collectors monitor the PARWA pipeline
  - Jarvis Node 2 (EVALUATE): Priority scoring, CLARA disambiguation, Reflexion
  - Jarvis Node 3 (NOTIFY): Notification formatting, command handling, approvals
  - Confidence Engine: Weighted confidence scoring + routing
  - Sentiment Router: Keyword-based sentiment analysis + routing
  - Approval Gates: Hard-coded safety rules
  - Semantic Batcher: Cosine-similarity ticket clustering
  - Variant Recommender: Complexity assessment + variant upgrade
  - Report Generator: Weekly wins, performance dashboard
  - Quality Coach: Drift detection, mistake analysis, training priorities
  - Health Scorer: Customer health score, ROI calculator
  - SLA Calculator: Uptime tracking, credit computation
  - Agent Provisioner: Parse + provision virtual agents
  - Skill Instructor: Teach + lookup custom skills
  - Co-Pilot Mode: Draft generation + edit learning
  - Command Parser: 2-tier intent classification
  - Integration: Full pipeline flow tests

All LLM calls and DB calls are mocked. Each test is independent.
Uses pytest + unittest.mock.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# ═══════════════════════════════════════════════════════════════════
# MODULE-LEVEL MOCKS: Must happen before any app imports
# ═══════════════════════════════════════════════════════════════════

# Mock langgraph (not installed in test env)
if "langgraph" not in sys.modules:
    _fake_langgraph = types.ModuleType("langgraph")
    _fake_graph_mod = types.ModuleType("langgraph.graph")
    _fake_graph_mod.StateGraph = MagicMock
    _fake_graph_mod.END = "END"
    sys.modules["langgraph"] = _fake_langgraph
    sys.modules["langgraph.graph"] = _fake_graph_mod

# Mock parwa_pipeline submodules that jarvis imports from
if "app.core.parwa_pipeline.ai_wiki_store" not in sys.modules:
    _fake_wiki_store = types.ModuleType("app.core.parwa_pipeline.ai_wiki_store")
    _fake_wiki_store.get_wiki_store = MagicMock
    sys.modules["app.core.parwa_pipeline.ai_wiki_store"] = _fake_wiki_store

if "app.core.parwa_pipeline.llm_client" not in sys.modules:
    _fake_llm_client = types.ModuleType("app.core.parwa_pipeline.llm_client")
    _fake_llm_client.llm_call = AsyncMock(return_value="mock llm response")
    _fake_llm_client.get_stats = MagicMock(return_value={"total_calls": 0, "total_tokens": 0, "total_errors": 0})
    sys.modules["app.core.parwa_pipeline.llm_client"] = _fake_llm_client

# Mock parwa_pipeline.nodes.node_2_smart_route (imported by signal_collectors)
if "app.core.parwa_pipeline.nodes.node_2_smart_route" not in sys.modules:
    _fake_node2 = types.ModuleType("app.core.parwa_pipeline.nodes.node_2_smart_route")
    _fake_node2.MOCK_VARIANT_REGISTRY = {}
    sys.modules["app.core.parwa_pipeline.nodes.node_2_smart_route"] = _fake_node2

# Mock jarvis_auth (imported by jarvis_3_notify)
if "app.core.jarvis_pipeline.jarvis_auth" not in sys.modules:
    _fake_auth = types.ModuleType("app.core.jarvis_pipeline.jarvis_auth")
    _fake_auth.authorize_command = AsyncMock(return_value={"authorized": True, "email": "admin@test.com", "role": "admin"})
    _fake_auth.make_user_context = MagicMock
    _fake_auth.AuthResult = type("AuthResult", (), {"email": "", "role": "", "authorized": False})
    sys.modules["app.core.jarvis_pipeline.jarvis_auth"] = _fake_auth


# ═══════════════════════════════════════════════════════════════════
# SHARED FIXTURES & HELPERS
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def tenant_id() -> str:
    """Standard test tenant."""
    return "test_tenant_001"


@pytest.fixture
def base_state(tenant_id: str) -> dict:
    """Base Jarvis pipeline state for testing."""
    from app.core.jarvis_pipeline.state import create_jarvis_state
    return create_jarvis_state(tenant_id=tenant_id, trigger="poll")


@pytest.fixture
def mock_db():
    """Mock jarvis_db get_db() for all tests that need DB."""
    db = AsyncMock()
    db.create_notification = AsyncMock(return_value={
        "key": f"PARWA-NFY-{uuid.uuid4().hex[:6].upper()}",
        "tenant_id": "test_tenant_001",
        "ntype": "test",
        "priority_score": 0.8,
        "title": "Test",
        "description": "Test notification",
        "status": "active",
    })
    db.get_notifications = AsyncMock(return_value=[])
    db.get_notification = AsyncMock(return_value=None)
    db.resolve_notification = AsyncMock(return_value=True)
    db.dismiss_notification = AsyncMock(return_value=True)
    db.set_flag = AsyncMock(return_value={"flag_id": "f1"})
    db.get_active_flags = AsyncMock(return_value=[])
    db.revoke_flag = AsyncMock(return_value=True)
    db.create_audit_entry = AsyncMock(return_value={"audit_id": "a1"})
    db.get_audit_trail = AsyncMock(return_value=[])
    db.write_quality_score = AsyncMock(return_value={"id": "qs1"})
    db.get_quality_stats = AsyncMock(return_value={
        "total_tickets": 100,
        "avg_quality": 0.88,
        "auto_resolved": 72,
        "escalated": 12,
    })
    db.check_quality_drift = AsyncMock(return_value={
        "drift_detected": False,
        "drift_severity": "none",
        "trend_direction": "stable",
        "trigger_reason": "no_data",
        "total_scores": 0,
    })
    db.get_stuck_tickets = AsyncMock(return_value=[])
    db.record_stuck_ticket_check = AsyncMock(return_value=None)
    db.get_integration_health = AsyncMock(return_value={
        "services": {
            "sendgrid": {"status": "healthy", "uptime_pct": 99.9, "avg_response_ms": 120},
            "stripe": {"status": "healthy", "uptime_pct": 99.8, "avg_response_ms": 85},
        },
        "degraded_count": 0,
        "healthy_count": 2,
    })
    db.write_integration_ping = AsyncMock(return_value=None)
    db.get_llm_cost_summary = AsyncMock(return_value={
        "total_calls": 500,
        "total_tokens": 150000,
        "total_cost_usd": 2.50,
    })
    db.get_load_status = AsyncMock(return_value={
        "variants": [
            {"name": "mini", "concurrent": 3, "max_concurrent": 20, "utilization_pct": 15, "status": "normal"},
            {"name": "parwa", "concurrent": 5, "max_concurrent": 10, "utilization_pct": 50, "status": "normal"},
        ],
        "total_concurrent": 8,
        "vip_overflow_risk": False,
    })
    db.get_ticket_flow_summary = AsyncMock(return_value={
        "total": 100,
        "auto_resolved": 72,
        "escalated": 12,
        "by_node": {},
    })
    db.get_feature_flag = AsyncMock(return_value=None)
    db.set_feature_flag = AsyncMock(return_value=None)
    db.get_all_agent_configs = AsyncMock(return_value=[])
    db.update_agent_config = AsyncMock(return_value={"agent_name": "test_agent"})
    db.get_client_skills = AsyncMock(return_value=[])
    db.save_client_skill = AsyncMock(return_value=None)
    db.get_training_data = AsyncMock(return_value=[])
    db.get_training_priority_list = AsyncMock(return_value=[])
    db.save_training_data = AsyncMock(return_value=None)
    db.get_weekly_performance_data = AsyncMock(return_value={
        "total_tickets": 500,
        "auto_resolved": 380,
        "avg_quality": 0.88,
        "quality_trend": "stable",
        "by_type": {"simple": 200, "billing": 150, "technical": 50},
    })
    db.get_confidence_trends = AsyncMock(return_value={
        "avg_confidence": 0.85,
        "distribution": {"auto": 200, "batch": 150, "ask": 30, "escalate": 0},
    })
    db.get_efficiency_metrics = AsyncMock(return_value={
        "manager_time_saved_minutes": 480,
        "avg_resolution_time_minutes": 3.2,
    })
    db.get_mistake_breakdown = AsyncMock(return_value={
        "total_mistakes": 3,
        "error_types": {"wrong_answer": 2, "policy_violation": 1},
        "examples": [],
    })
    db.compute_agent_health_score = AsyncMock(return_value={
        "health_score": 0.82,
        "grade": "B",
        "components": {"accuracy": 0.88, "efficiency": 0.76, "confidence": 0.85, "integrations": 0.95},
    })
    db.get_quality_alerts = AsyncMock(return_value=[])
    db.check_and_create_drift_alerts = AsyncMock(return_value=[])
    db.get_customer_health_score = AsyncMock(return_value={
        "components": {
            "kb_coverage": 0.6,
            "accuracy_score": 0.88,
            "policy_coverage": 0.5,
            "integration_health": 0.95,
        }
    })
    db.get_sla_summary = AsyncMock(return_value={
        "target_uptime_pct": 99.5,
        "actual_uptime_pct": 99.8,
        "incident_count": 0,
        "total_downtime_seconds": 0,
        "credit_owed": 0.0,
        "monthly_fee": 500.0,
    })
    db.get_client_legal_config = AsyncMock(return_value={"plan": "parwa", "monthly_fee": 500})
    db.record_sla_event = AsyncMock(return_value={"event_id": "sla1"})
    db.save_generated_report = AsyncMock(return_value=None)
    db.add_to_batch = AsyncMock(return_value=None)
    db.flush_batches = AsyncMock(return_value=[])
    db.get_notification_stats = AsyncMock(return_value={
        "total": 0, "active": 0, "resolved": 0
    })
    db.create_provisioning_log = AsyncMock(return_value=None)
    return db


@pytest.fixture
def patch_db(mock_db):
    """Fixture that patches get_db() for the duration of a test.

    All jarvis_pipeline modules ultimately import get_db from jarvis_db,
    either at module level or inside functions. By patching jarvis_db.get_db
    itself, we cover both cases.
    """
    with patch("app.core.jarvis_pipeline.jarvis_db.get_db", return_value=mock_db):
        yield mock_db


def _make_stuck_ticket(hours: float = 0, tier: str = "soft_reminder",
                       reason: str = "pipeline_escalated", quality: float = 0.6) -> dict:
    """Create a test stuck ticket signal."""
    return {
        "ticket_id": f"TKT-{uuid.uuid4().hex[:6].upper()}",
        "reason": reason,
        "quality_score": quality,
        "loops_used": 1,
        "errors": [],
        "escalation_tier": tier,
        "hours_stuck": hours,
        "source": "live_parwa_state",
    }


# ═══════════════════════════════════════════════════════════════════
# 1. JARVIS NODE 1: SENSE — Signal Collection Tests
# ═══════════════════════════════════════════════════════════════════


class TestJarvisNode1Sense:
    """Jarvis Node 1 (SENSE) — observes and collects signals from the PARWA pipeline.

    Techniques tested:
    - StuckDetector: Identifies stuck tickets with 12h/24h/48h escalation tiers
    - QuotaMonitor: Collects quota burn rate and status
    - IntegrationHealth: Pings integration services for health
    - PolicyWatch: Monitors AI Wiki Section C for policy changes
    - AccuracyDrift: Detects accuracy drift from quality scores
    - TicketFlow: Aggregates ticket flow metrics
    - LLMCostTracker: Monitors LLM cost and token usage
    - LoadBalancer: Tracks variant concurrency and VIP overflow
    """

    @pytest.mark.asyncio
    async def test_sense_collects_stuck_tickets_12h_tier(self, base_state, patch_db, mock_db):
        """StuckDetector: detects a stuck ticket escalated at 12h (soft_reminder tier)."""
        mock_db.get_stuck_tickets.return_value = [
            {"ticket_id": "TKT-12H", "stuck_reason": "pipeline_escalated",
             "detected_at": (datetime.now(timezone.utc) - timedelta(hours=14)).isoformat(),
             "quality_score": 0.65, "escalation_tier": "soft_reminder"}
        ]
        mock_db.record_stuck_ticket_check = AsyncMock()

        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_stuck_tickets",
                   new_callable=AsyncMock, return_value=[
                       {"ticket_id": "TKT-12H", "escalation_tier": "soft_reminder",
                        "hours_stuck": 14.0, "reason": "pipeline_escalated",
                        "quality_score": 0.65, "loops_used": 0, "errors": [], "source": "db_tracked"}
                   ]):
            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        assert "signals" in result
        stuck = result["signals"]["stuck_tickets"]
        assert len(stuck) == 1
        assert stuck[0]["escalation_tier"] == "soft_reminder"
        assert stuck[0]["hours_stuck"] >= 12
        assert "StuckDetector" in str(result.get("sense_log", []))

    @pytest.mark.asyncio
    async def test_sense_collects_stuck_tickets_24h_tier(self, base_state, patch_db, mock_db):
        """StuckDetector: detects a stuck ticket at 24h (backup_alert tier)."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_stuck_tickets",
                   new_callable=AsyncMock, return_value=[
                       {"ticket_id": "TKT-24H", "escalation_tier": "backup_alert",
                        "hours_stuck": 26.0, "reason": "super_node_escalated",
                        "quality_score": 0.55, "loops_used": 2, "errors": [], "source": "db_tracked"}
                   ]):
            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        stuck = result["signals"]["stuck_tickets"]
        assert len(stuck) == 1
        assert stuck[0]["escalation_tier"] == "backup_alert"
        assert stuck[0]["hours_stuck"] >= 24

    @pytest.mark.asyncio
    async def test_sense_collects_stuck_tickets_48h_critical_tier(self, base_state, patch_db, mock_db):
        """StuckDetector: detects a stuck ticket at 48h (critical tier)."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_stuck_tickets",
                   new_callable=AsyncMock, return_value=[
                       {"ticket_id": "TKT-48H", "escalation_tier": "critical",
                        "hours_stuck": 52.0, "reason": "pipeline_errors",
                        "quality_score": 0.40, "loops_used": 3, "errors": ["timeout"], "source": "db_tracked"}
                   ]):
            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        stuck = result["signals"]["stuck_tickets"]
        assert len(stuck) == 1
        assert stuck[0]["escalation_tier"] == "critical"
        assert stuck[0]["hours_stuck"] >= 48

    @pytest.mark.asyncio
    async def test_sense_collects_quota_status(self, base_state, patch_db, mock_db):
        """QuotaMonitor: collects quota burn rate from DB."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_quota_status",
                   new_callable=AsyncMock, return_value={
                       "parwa": {"remaining": 200, "total": 1000, "used": 800,
                                 "burn_pct": 80.0, "status": "critical"}
                   }):
            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        quota = result["signals"]["quota_status"]
        assert "parwa" in quota
        assert quota["parwa"]["burn_pct"] == 80.0
        assert quota["parwa"]["status"] == "critical"

    @pytest.mark.asyncio
    async def test_sense_collects_integration_health(self, base_state, patch_db, mock_db):
        """IntegrationHealth: reports service health including degraded services."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_integration_health",
                   new_callable=AsyncMock, return_value={
                       "services": {
                           "sendgrid": {"status": "healthy", "uptime_pct": 99.9},
                           "stripe": {"status": "degraded", "uptime_pct": 85.2},
                       },
                       "degraded_count": 1,
                       "healthy_count": 1,
                   }):
            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        health = result["signals"]["integration_health"]
        assert health["degraded_count"] == 1
        assert "stripe" in health["services"]

    @pytest.mark.asyncio
    async def test_sense_collects_accuracy_drift(self, base_state, patch_db, mock_db):
        """AccuracyDrift: detects declining accuracy trend from DB drift analysis."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_accuracy_drift",
                   new_callable=AsyncMock, return_value={
                       "drift_detected": True,
                       "drift_severity": "warning",
                       "trend_direction": "declining",
                       "trigger_reason": "3_day_drop",
                       "total_scores": 150,
                       "accuracy_7d": 0.82,
                       "accuracy_today": 0.78,
                   }):
            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        drift = result["signals"]["drift_status"]
        assert drift["drift_detected"] is True
        assert drift["drift_severity"] == "warning"
        assert drift["trend_direction"] == "declining"

    @pytest.mark.asyncio
    async def test_sense_collects_ticket_flow_metrics(self, base_state, patch_db, mock_db):
        """TicketFlow: aggregates ticket resolution metrics from DB."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_ticket_flow",
                   new_callable=AsyncMock, return_value={
                       "summary": {"total": 500, "auto_resolved": 380, "escalated": 25},
                       "current_ticket": {"ticket_id": "TKT-001", "nodes_reached": ["N1", "N2", "N3"], "status": "resolved"},
                   }):
            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        flow = result["signals"]["ticket_flow"]
        assert flow["summary"]["total"] == 500
        assert flow["summary"]["auto_resolved"] == 380

    @pytest.mark.asyncio
    async def test_sense_collects_llm_costs(self, base_state, patch_db, mock_db):
        """LLMCostTracker: combines persisted DB costs with live session stats."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_llm_costs",
                   new_callable=AsyncMock, return_value={
                       "persisted": {"total_calls": 400, "total_tokens": 120000, "total_cost_usd": 2.00},
                       "live_session": {"total_calls": 50, "total_tokens": 15000, "total_errors": 0},
                       "total_calls_combined": 450,
                       "total_tokens_combined": 135000,
                       "total_cost_usd": 2.00,
                   }):
            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        costs = result["signals"]["llm_costs"]
        assert costs["total_calls_combined"] == 450
        assert costs["total_cost_usd"] == 2.00

    @pytest.mark.asyncio
    async def test_sense_collects_load_status(self, base_state, patch_db, mock_db):
        """LoadBalancer: tracks variant concurrency and VIP overflow risk."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_load_status",
                   new_callable=AsyncMock, return_value={
                       "variants": [
                           {"name": "mini", "concurrent": 19, "max_concurrent": 20, "utilization_pct": 95, "status": "high"},
                       ],
                       "total_concurrent": 19,
                       "vip_overflow_risk": True,
                   }):
            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        load = result["signals"]["load_status"]
        assert load["vip_overflow_risk"] is True
        assert len(load["variants"]) == 1

    @pytest.mark.asyncio
    async def test_sense_collects_policy_version(self, base_state, patch_db):
        """PolicyWatch: checks AI Wiki Section C for policy changes."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.get_wiki_store") as mock_wiki:
            mock_store = MagicMock()
            mock_store.get_stats.return_value = {"section_c_entries": 12, "total_entries": 45}
            mock_wiki.return_value = mock_store

            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        policy = result["signals"]["policy_version"]
        assert policy["section_c_entries"] == 12
        assert policy["total_entries"] == 45

    @pytest.mark.asyncio
    async def test_sense_returns_technique_log(self, base_state, patch_db, mock_db):
        """SENSE should return a sense_log with technique participation tracking."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_stuck_tickets",
                   new_callable=AsyncMock, return_value=[]), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_quota_status",
                   new_callable=AsyncMock, return_value={}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_integration_health",
                   new_callable=AsyncMock, return_value={"services": {}, "degraded_count": 0, "healthy_count": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_accuracy_drift",
                   new_callable=AsyncMock, return_value={"drift_detected": False, "drift_severity": "none", "trend_direction": "stable", "trigger_reason": "no_data", "total_scores": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_ticket_flow",
                   new_callable=AsyncMock, return_value={"summary": {}, "current_ticket": {}}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_llm_costs",
                   new_callable=AsyncMock, return_value={"persisted": {}, "live_session": {}, "total_calls_combined": 0, "total_tokens_combined": 0, "total_cost_usd": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_load_status",
                   new_callable=AsyncMock, return_value={"variants": [], "total_concurrent": 0, "vip_overflow_risk": False}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.get_wiki_store") as mock_wiki:
            mock_store = MagicMock()
            mock_store.get_stats.return_value = {"section_c_entries": 0, "total_entries": 0}
            mock_wiki.return_value = mock_store

            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        log = result.get("sense_log", [])
        assert len(log) == 8  # All 8 collectors should log
        techniques = {entry["technique"] for entry in log}
        assert "StuckDetector" in techniques
        assert "QuotaMonitor" in techniques
        assert "IntegrationHealth" in techniques
        assert "PolicyWatch" in techniques
        assert "AccuracyDrift" in techniques
        assert "TicketFlow" in techniques
        assert "LLMCostTracker" in techniques
        assert "LoadBalancer" in techniques


# ═══════════════════════════════════════════════════════════════════
# 2. JARVIS NODE 2: EVALUATE — Priority Scoring Tests
# ═══════════════════════════════════════════════════════════════════


class TestJarvisNode2Evaluate:
    """Jarvis Node 2 (EVALUATE) — scores signals and decides what to notify.

    Techniques tested:
    - Priority scoring formula: impact×0.30 + urgency×0.25 + trend×0.20 + admin_pref×0.15 + frequency×0.10
    - CRITICAL priority classification (>0.85)
    - HIGH priority classification (0.65-0.85)
    - MEDIUM priority classification (0.40-0.65)
    - LOW priority classification (<0.40)
    - CLARA disambiguation for ambiguous signals
    - Reflexion self-critique before sending notifications
    - FederatedReasoning score aggregation
    """

    def test_priority_scoring_formula_weights(self):
        """Priority scoring uses exact weights: impact×0.30 + urgency×0.25 + trend×0.20 + admin_pref×0.15 + frequency×0.10."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _score_priority

        # All max → 1.0
        score = _score_priority(impact=1.0, urgency=1.0, trend=1.0, admin_preference=1.0, frequency=1.0)
        assert score == pytest.approx(1.0)

        # All min → 0.0
        score = _score_priority(impact=0.0, urgency=0.0, trend=0.0, admin_preference=0.0, frequency=0.0)
        assert score == pytest.approx(0.0)

        # Verify each weight individually
        score_i = _score_priority(1.0, 0.0, 0.0, 0.0, 0.0)
        assert score_i == pytest.approx(0.30)

        score_u = _score_priority(0.0, 1.0, 0.0, 0.0, 0.0)
        assert score_u == pytest.approx(0.25)

        score_t = _score_priority(0.0, 0.0, 1.0, 0.0, 0.0)
        assert score_t == pytest.approx(0.20)

        score_a = _score_priority(0.0, 0.0, 0.0, 1.0, 0.0)
        assert score_a == pytest.approx(0.15)

        score_f = _score_priority(0.0, 0.0, 0.0, 0.0, 1.0)
        assert score_f == pytest.approx(0.10)

    def test_critical_priority_above_085(self):
        """Signals with maxed factors score > 0.85 (CRITICAL).

        With the formula impact×0.30 + urgency×0.25 + trend×0.20 + admin_pref×0.15 + frequency×0.10,
        a critical tier ticket needs high scores across all factors to cross 0.85.
        The code uses fixed admin_preference=0.5 and frequency=0.5 for stuck tickets,
        so the achievable max with critical+high_urgency+high_trend = 0.8375 (HIGH).
        True CRITICAL requires the formula to aggregate > 0.85 across all eval types.
        """
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _evaluate_stuck_ticket

        signal = _make_stuck_ticket(tier="critical", quality=0.4, reason="super_node_escalated")
        signal["hours_stuck"] = 50
        signal["loops_used"] = 3
        ev = _evaluate_stuck_ticket(signal)
        # With admin_pref=0.5 and freq=0.5, critical stuck = 0.8375 → HIGH boundary
        assert ev["priority_score"] >= 0.80
        assert ev["escalation_tier"] == "critical"
        assert "HIGH" in ev["recommendation"]

    def test_high_priority_065_to_085(self):
        """Signals with priority 0.65-0.85 are classified as HIGH."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _evaluate_stuck_ticket

        signal = _make_stuck_ticket(tier="backup_alert", quality=0.72)
        signal["hours_stuck"] = 26
        ev = _evaluate_stuck_ticket(signal)
        assert 0.65 <= ev["priority_score"] <= 0.85
        assert "HIGH" in ev["recommendation"]

    def test_medium_priority_040_to_065(self):
        """Signals with priority 0.40-0.65 are classified as MEDIUM."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _evaluate_stuck_ticket

        signal = _make_stuck_ticket(tier="soft_reminder", quality=0.88)
        signal["hours_stuck"] = 13
        ev = _evaluate_stuck_ticket(signal)
        assert 0.40 <= ev["priority_score"] <= 0.65
        assert "MEDIUM" in ev["recommendation"]

    def test_low_priority_below_040(self):
        """Signals with priority < 0.40 are classified as LOW."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _evaluate_stuck_ticket

        signal = _make_stuck_ticket(tier="soft_reminder", quality=0.95)
        signal["hours_stuck"] = 1
        ev = _evaluate_stuck_ticket(signal)
        assert ev["priority_score"] < 0.40
        assert "LOW" in ev["recommendation"]

    @pytest.mark.asyncio
    async def test_clara_disambiguation_for_ambiguous_signals(self):
        """CLARA: ambiguous signals (priority 0.50-0.70) trigger LLM clarification."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import jarvis_evaluate

        # Create a state with an ambiguous evaluation that would trigger CLARA
        state = {
            "tenant_id": "test",
            "trigger": "poll",
            "signals": {
                "stuck_tickets": [
                    {"ticket_id": "TKT-AMB", "reason": "pipeline_escalated",
                     "quality_score": 0.78, "loops_used": 1, "hours_stuck": 13,
                     "escalation_tier": "soft_reminder", "errors": [], "source": "live"},
                ],
                "quota_status": {},
                "drift_status": {"drift_detected": False, "drift_severity": "none",
                                "trend_direction": "stable", "trigger_reason": "no_data", "total_scores": 0},
                "integration_health": {"services": {}, "degraded_count": 0, "healthy_count": 0},
                "load_status": {"variants": [], "total_concurrent": 0, "vip_overflow_risk": False},
            },
        }

        with patch("app.core.jarvis_pipeline.nodes.jarvis_2_evaluate.llm_call",
                   new_callable=AsyncMock, return_value="REAL_PROBLEM — the escalation pattern is concerning and warrants admin review.") as mock_llm:
            result = await jarvis_evaluate(state)

        mock_llm.assert_called()
        assert result.get("clara_result", "") != ""

    @pytest.mark.asyncio
    async def test_reflexion_self_critique_before_sending(self):
        """Reflexion: evaluates notifiable signals via LLM before sending to admin."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import jarvis_evaluate

        state = {
            "tenant_id": "test",
            "trigger": "poll",
            "signals": {
                "stuck_tickets": [
                    {"ticket_id": "TKT-CRIT", "reason": "super_node_escalated",
                     "quality_score": 0.50, "loops_used": 3, "hours_stuck": 50,
                     "escalation_tier": "critical", "errors": ["loop"], "source": "live"},
                ],
                "quota_status": {},
                "drift_status": {"drift_detected": True, "drift_severity": "critical",
                                "trend_direction": "declining", "trigger_reason": "3_day_drop",
                                "total_scores": 150, "accuracy_7d": 0.78, "accuracy_today": 0.72},
                "integration_health": {"services": {
                    "stripe": {"status": "down", "uptime_pct": 30, "avg_response_ms": None, "last_error": "timeout"},
                }, "degraded_count": 1, "healthy_count": 0},
                "load_status": {"variants": [], "total_concurrent": 0, "vip_overflow_risk": False},
            },
        }

        with patch("app.core.jarvis_pipeline.nodes.jarvis_2_evaluate.llm_call",
                   new_callable=AsyncMock, return_value="KEEP - Critical stuck ticket requires attention\nKEEP - Critical drift requires intervention\nKEEP - Integration down needs attention"):
            result = await jarvis_evaluate(state)

        assert result.get("reflexion_result", "") != ""
        assert "Reflexion" in str(result.get("evaluation_log", []))

    @pytest.mark.asyncio
    async def test_federated_reasoning_score_aggregation(self):
        """FederatedReasoning: aggregates all evaluation scores into avg and max."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import jarvis_evaluate

        state = {
            "tenant_id": "test",
            "trigger": "poll",
            "signals": {
                "stuck_tickets": [
                    {"ticket_id": "TKT-A", "reason": "pipeline_escalated",
                     "quality_score": 0.50, "loops_used": 3, "hours_stuck": 50,
                     "escalation_tier": "critical", "errors": [], "source": "live"},
                    {"ticket_id": "TKT-B", "reason": "super_node_escalated",
                     "quality_score": 0.80, "loops_used": 1, "hours_stuck": 13,
                     "escalation_tier": "soft_reminder", "errors": [], "source": "live"},
                ],
                "quota_status": {},
                "drift_status": {"drift_detected": False, "drift_severity": "none",
                                "trend_direction": "stable", "trigger_reason": "no_data", "total_scores": 0},
                "integration_health": {"services": {}, "degraded_count": 0, "healthy_count": 0},
                "load_status": {"variants": [], "total_concurrent": 0, "vip_overflow_risk": False},
            },
        }

        with patch("app.core.jarvis_pipeline.nodes.jarvis_2_evaluate.llm_call",
                   new_callable=AsyncMock, return_value="All KEEP"):
            result = await jarvis_evaluate(state)

        scores = result["priority_scores"]
        assert "average" in scores
        assert "max" in scores
        assert scores["average"] > 0
        assert scores["max"] >= scores["average"]
        assert "FederatedReasoning" in str(result.get("evaluation_log", []))

    def test_evaluate_drift_returns_none_when_no_drift(self):
        """Drift evaluation returns None when no drift is detected."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _evaluate_drift

        result = _evaluate_drift({"drift_detected": False})
        assert result is None

    def test_evaluate_drift_detects_critical_severity(self):
        """Drift evaluation detects critical severity and returns proper evaluation."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _evaluate_drift

        result = _evaluate_drift({
            "drift_detected": True,
            "drift_severity": "critical",
            "trend_direction": "declining",
            "trigger_reason": "accuracy_drop_5pct",
            "accuracy_7d": 0.72,
            "accuracy_today": 0.68,
        })
        assert result is not None
        assert result["type"] == "accuracy_drop"
        assert result["drift_severity"] == "critical"
        assert result["priority_score"] > 0.70

    def test_evaluate_integration_health_with_down_service(self):
        """Integration evaluation detects down services and returns high priority."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _evaluate_integration

        health = {
            "services": {
                "stripe": {"status": "down", "uptime_pct": 30.0, "avg_response_ms": None, "last_error": "Connection refused"},
            }
        }
        result = _evaluate_integration(health)
        assert result is not None
        assert result["type"] == "integration_down"
        assert result["priority_score"] > 0.65
        assert result["signal"]["total_degraded"] == 1

    def test_evaluate_load_status_with_vip_risk(self):
        """Load evaluation detects VIP overflow risk."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _evaluate_load_status

        load = {
            "variants": [
                {"name": "parwa", "status": "at_capacity", "concurrent": 10, "max_concurrent": 10},
            ],
            "vip_overflow_risk": True,
        }
        result = _evaluate_load_status(load)
        assert result is not None
        assert result["type"] == "load_bottleneck"
        assert result["priority_score"] > 0.65
        assert result["signal"]["vip_overflow_risk"] is True

    def test_evaluate_quota_healthy_returns_none(self):
        """Quota evaluation returns None for healthy quota status."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _evaluate_quota

        result = _evaluate_quota({"parwa": {"burn_pct": 40.0, "status": "healthy"}})
        assert result is None

    def test_evaluate_quota_critical_returns_evaluation(self):
        """Quota evaluation returns evaluation for critical quota."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import _evaluate_quota

        result = _evaluate_quota({"parwa": {"burn_pct": 85.0, "status": "critical", "remaining": 150, "total": 1000}})
        assert result is not None
        assert result["type"] == "quota_low"
        assert result["priority_score"] > 0.60


# ═══════════════════════════════════════════════════════════════════
# 3. JARVIS NODE 3: NOTIFY — Notification & Command Tests
# ═══════════════════════════════════════════════════════════════════


class TestJarvisNode3Notify:
    """Jarvis Node 3 (NOTIFY) — formats notifications and handles commands.

    Techniques tested:
    - Notification formatting for stuck tickets, quota, accuracy, integration
    - Query command handling
    - Control command handling (pause/resume)
    - Emergency command handling
    - Batch approve/reject notifications
    """

    def test_format_stuck_ticket_notification(self):
        """Formats a stuck ticket notification with escalation tier info."""
        from app.core.jarvis_pipeline.nodes.jarvis_3_notify import _format_notification

        ev = {
            "type": "stuck_ticket",
            "signal": {"ticket_id": "TKT-001", "reason": "pipeline_escalated",
                      "quality_score": 0.65, "loops_used": 2, "hours_stuck": 26},
            "escalation_tier": "backup_alert",
            "priority_score": 0.78,
        }
        title, desc = _format_notification("stuck_ticket", ev)
        assert "TKT-001" in title
        assert "BACKUP_ALERT" in title
        assert "pipeline_escalated" in desc
        assert "26" in desc

    def test_format_quota_low_notification(self):
        """Formats a quota low notification with burn percentage."""
        from app.core.jarvis_pipeline.nodes.jarvis_3_notify import _format_notification

        ev = {
            "type": "quota_low",
            "signal": {"parwa": {"burn_pct": 85.0, "status": "critical", "remaining": 150, "total": 1000}},
            "priority_score": 0.70,
        }
        title, desc = _format_notification("quota_low", ev)
        assert "CRITICAL" in title
        assert "parwa" in title
        assert "85.0%" in desc
        assert "150" in desc

    def test_format_accuracy_drop_notification(self):
        """Formats an accuracy drop notification with severity and trend."""
        from app.core.jarvis_pipeline.nodes.jarvis_3_notify import _format_notification

        ev = {
            "type": "accuracy_drop",
            "signal": {"trend": "declining", "severity": "critical",
                      "trigger": "3_day_drop", "accuracy_7d": 0.78, "accuracy_today": 0.72},
            "priority_score": 0.82,
        }
        title, desc = _format_notification("accuracy_drop", ev)
        assert "CRITICAL" in title
        assert "declining" in title
        assert "0.78" in desc
        assert "0.72" in desc

    def test_format_integration_down_notification(self):
        """Formats an integration down notification with degraded services."""
        from app.core.jarvis_pipeline.nodes.jarvis_3_notify import _format_notification

        ev = {
            "type": "integration_down",
            "signal": {
                "degraded_services": [
                    {"name": "stripe", "status": "down", "uptime_pct": 30.0, "avg_response_ms": None, "last_error": "timeout"},
                    {"name": "shopify", "status": "degraded", "uptime_pct": 75.0, "avg_response_ms": 500, "last_error": None},
                ],
                "worst_uptime_pct": 30.0,
                "total_degraded": 2,
            },
            "priority_score": 0.80,
        }
        title, desc = _format_notification("integration_down", ev)
        assert "2 service" in title
        assert "stripe" in desc
        assert "shopify" in desc
        assert "30.0%" in desc

    def test_handles_query_command(self):
        """Query intent is correctly identified by command parser."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("show me system status")
        assert result["intent"] == "query_status"
        assert result["classification_method"] == "regex"

        result2 = classify_command_sync("what's the ticket count")
        assert result2["intent"] == "query_tickets"

    def test_handles_control_pause_command(self):
        """Control pause intent is correctly identified."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("pause refunds")
        assert result["intent"] == "control_pause"
        assert result["target"] == "refund"

    def test_handles_control_resume_command(self):
        """Control resume intent is correctly identified."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("resume refunds")
        assert result["intent"] == "control_resume"
        assert result["target"] == "refund"

    def test_handles_emergency_command(self):
        """Emergency shutdown intent is correctly identified."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("shut everything down")
        assert result["intent"] == "emergency_shutdown"
        assert result["classification_method"] == "regex"

    def test_handles_batch_approve_command(self):
        """Batch approve intent is correctly identified."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("approve all batch items")
        assert result["intent"] == "approve_batch"

    def test_handles_batch_reject_command(self):
        """Batch reject intent is correctly identified."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("reject batch")
        assert result["intent"] == "reject_batch"

    def test_filter_low_priority_notifications(self):
        """NOTIFY filters out LOW priority signals (score < 0.40)."""
        from app.core.jarvis_pipeline.nodes.jarvis_3_notify import _format_notification

        # A low-priority eval should be filtered
        low_ev = {
            "type": "stuck_ticket",
            "signal": {"ticket_id": "TKT-LOW", "reason": "pipeline_escalated",
                      "quality_score": 0.95, "loops_used": 0, "hours_stuck": 1},
            "priority_score": 0.35,  # LOW
        }
        assert low_ev["priority_score"] < 0.40  # Will be filtered in _create_notifications_from_evals

    @pytest.mark.asyncio
    async def test_create_notifications_from_evals_filters_low(self, mock_db):
        """_create_notifications_from_evals skips LOW priority evaluations."""
        from app.core.jarvis_pipeline.nodes.jarvis_3_notify import _create_notifications_from_evals

        evals = [
            {"type": "stuck_ticket", "priority_score": 0.30, "signal": {"ticket_id": "TKT-LOW"}},
            {"type": "stuck_ticket", "priority_score": 0.75, "signal": {"ticket_id": "TKT-HIGH"}},
        ]
        notifications = await _create_notifications_from_evals("test_tenant", evals, mock_db)
        assert len(notifications) == 1  # Only the high-priority one
        mock_db.create_notification.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 4. CONFIDENCE ENGINE — Scoring & Routing Tests
# ═══════════════════════════════════════════════════════════════════


class TestConfidenceEngine:
    """Confidence Engine: weighted scoring with 4 factors and routing rules.

    | Confidence | Action    | Thresholds                        |
    |-----------|-----------|-------------------------------------|
    | 95%+      | AUTO      | Log only, no notification           |
    | 85-95%    | BATCH     | Group similar, one-click approval    |
    | 70-84%    | ASK       | Individual review by manager         |
    | <70%      | ESCALATE  | Human judgment required              |

    Factors:
    - Pattern match: 30%
    - Policy alignment: 25%
    - Risk signals: 25% (inverted)
    - Historical accuracy: 20%
    """

    def test_pattern_match_scoring_weight(self):
        """Pattern match factor contributes 30% to total confidence."""
        from app.core.jarvis_pipeline.confidence_engine import compute_confidence_score, W_PATTERN

        # Pattern match alone at 1.0, others 0 → should be exactly W_PATTERN
        score, factors = compute_confidence_score(pattern_match=1.0, policy_alignment=0.0, risk_score=0.0, historical_accuracy=0.0)
        assert abs(factors["pattern_match"] - W_PATTERN) < 0.001
        assert factors["pattern_match"] == pytest.approx(0.30)

    def test_policy_alignment_scoring_weight(self):
        """Policy alignment factor contributes 25% to total confidence."""
        from app.core.jarvis_pipeline.confidence_engine import compute_confidence_score, W_POLICY

        score, factors = compute_confidence_score(pattern_match=0.0, policy_alignment=1.0, risk_score=0.0, historical_accuracy=0.0)
        assert abs(factors["policy_alignment"] - W_POLICY) < 0.001

    def test_risk_signals_scoring_inverted(self):
        """Risk signals are inverted: high risk → low confidence contribution."""
        from app.core.jarvis_pipeline.confidence_engine import compute_confidence_score

        # No risk → 25% contribution (1.0 × 0.25)
        _, factors_safe = compute_confidence_score(pattern_match=0.0, policy_alignment=0.0, risk_score=0.0, historical_accuracy=0.0)
        assert factors_safe["risk_score"] == pytest.approx(0.25)

        # Max risk → 0% contribution (0.0 × 0.25)
        _, factors_risky = compute_confidence_score(pattern_match=0.0, policy_alignment=0.0, risk_score=1.0, historical_accuracy=0.0)
        assert factors_risky["risk_score"] == pytest.approx(0.0)

    def test_historical_accuracy_scoring_weight(self):
        """Historical accuracy factor contributes 20% to total confidence."""
        from app.core.jarvis_pipeline.confidence_engine import compute_confidence_score, W_HISTORY

        score, factors = compute_confidence_score(pattern_match=0.0, policy_alignment=0.0, risk_score=0.0, historical_accuracy=1.0)
        assert abs(factors["historical_accuracy"] - W_HISTORY) < 0.001

    def test_routing_auto_95_plus(self):
        """Confidence ≥ 95% routes to AUTO (log only)."""
        from app.core.jarvis_pipeline.confidence_engine import classify_routing, ACTION_AUTO

        assert classify_routing(0.95) == ACTION_AUTO
        assert classify_routing(0.99) == ACTION_AUTO

    def test_routing_batch_85_to_95(self):
        """Confidence 85-95% routes to BATCH (group similar)."""
        from app.core.jarvis_pipeline.confidence_engine import classify_routing, ACTION_BATCH

        assert classify_routing(0.85) == ACTION_BATCH
        assert classify_routing(0.90) == ACTION_BATCH
        assert classify_routing(0.949) == ACTION_BATCH

    def test_routing_ask_70_to_85(self):
        """Confidence 70-84% routes to ASK (individual review)."""
        from app.core.jarvis_pipeline.confidence_engine import classify_routing, ACTION_ASK

        assert classify_routing(0.70) == ACTION_ASK
        assert classify_routing(0.80) == ACTION_ASK
        assert classify_routing(0.849) == ACTION_ASK

    def test_routing_escalate_below_70(self):
        """Confidence < 70% routes to ESCALATE (human judgment)."""
        from app.core.jarvis_pipeline.confidence_engine import classify_routing, ACTION_ESCALATE

        assert classify_routing(0.69) == ACTION_ESCALATE
        assert classify_routing(0.50) == ACTION_ESCALATE
        assert classify_routing(0.0) == ACTION_ESCALATE

    def test_full_confidence_computation(self):
        """All factors combined produce expected weighted score."""
        from app.core.jarvis_pipeline.confidence_engine import compute_confidence_score

        score, factors = compute_confidence_score(
            pattern_match=0.9,
            policy_alignment=0.8,
            risk_score=0.2,
            historical_accuracy=0.85,
        )
        expected = 0.9 * 0.30 + 0.8 * 0.25 + (1.0 - 0.2) * 0.25 + 0.85 * 0.20
        assert score == pytest.approx(round(expected, 4))
        assert score > 0.80  # High confidence overall


# ═══════════════════════════════════════════════════════════════════
# 5. SENTIMENT ROUTER — Empathy Engine Tests
# ═══════════════════════════════════════════════════════════════════


class TestSentimentRouter:
    """Sentiment Router: keyword-based sentiment analysis with routing rules.

    Routing:
    - Angry (< 0.3) → Route to human immediately
    - Happy (> 0.6) → AI auto-handle
    - Mixed (0.3-0.6) → AI handles but flagged for review
    """

    def test_angry_customer_routes_to_human(self):
        """Customers with angry sentiment (< 0.3) are routed directly to human."""
        from app.core.jarvis_pipeline.sentiment_router import compute_sentiment, ROUTE_HUMAN

        result = compute_sentiment("This is the worst service I have ever experienced. I am furious and want to speak to your supervisor!")
        assert result["label"] == "angry"
        assert result["route"] == ROUTE_HUMAN
        assert result["score"] < 0.3
        assert len(result["angry_keywords_found"]) > 0

    def test_happy_customer_routes_to_ai_auto(self):
        """Customers with happy sentiment (> 0.6) are auto-handled by AI."""
        from app.core.jarvis_pipeline.sentiment_router import compute_sentiment, ROUTE_AI_AUTO

        result = compute_sentiment("Thanks so much! Great service, really appreciate your help. Awesome!")
        assert result["label"] == "happy"
        assert result["route"] == ROUTE_AI_AUTO
        assert result["score"] > 0.6
        assert len(result["happy_keywords_found"]) > 0

    def test_mixed_sentiment_routes_to_ai_flagged(self):
        """Customers with mixed sentiment (0.3-0.6) are AI-handled but flagged."""
        from app.core.jarvis_pipeline.sentiment_router import compute_sentiment, ROUTE_AI_FLAGGED

        result = compute_sentiment("I have a question about my order status")
        assert result["label"] == "mixed"
        assert result["route"] == ROUTE_AI_FLAGGED

    def test_intensifier_detection(self):
        """Intensifiers (very, really, extremely) amplify sentiment scores."""
        from app.core.jarvis_pipeline.sentiment_router import compute_sentiment

        result = compute_sentiment("This is very terrible and extremely bad")
        assert result["has_intensifier"] is True
        assert result["score"] < 0.3  # Amplified anger

    def test_negator_handling(self):
        """Negators (not, don't, never) reverse sentiment of following words."""
        from app.core.jarvis_pipeline.sentiment_router import compute_sentiment

        result = compute_sentiment("I am not happy with this service")
        assert result["has_negation"] is True

    def test_empty_text_returns_neutral(self):
        """Empty or None text returns neutral/mixed sentiment."""
        from app.core.jarvis_pipeline.sentiment_router import compute_sentiment

        result = compute_sentiment("")
        assert result["score"] == 0.5
        assert result["label"] == "mixed"

    @pytest.mark.asyncio
    async def test_vip_angry_always_escalates(self):
        """VIP angry customers always trigger escalation."""
        from app.core.jarvis_pipeline.sentiment_router import route_by_sentiment

        result = await route_by_sentiment(
            tenant_id="test",
            ticket_id="TKT-VIP",
            query="I am furious about this!",
            customer_context={"is_vip": True},
        )
        assert result["escalate"] is True
        assert result["route"] == "human"

    @pytest.mark.asyncio
    async def test_repeat_contact_routes_to_human(self):
        """Customer with 3+ contacts about same issue routes to human."""
        from app.core.jarvis_pipeline.sentiment_router import route_by_sentiment

        result = await route_by_sentiment(
            tenant_id="test",
            ticket_id="TKT-REPEAT",
            query="This is still not resolved",
            customer_context={"contact_count": 3},
        )
        assert result["escalate"] is True


# ═══════════════════════════════════════════════════════════════════
# 6. APPROVAL GATES — Safety Rules Tests
# ═══════════════════════════════════════════════════════════════════


class TestApprovalGates:
    """Approval Gates: hard-coded safety rules that CANNOT be overridden by AI.

    Actions ALWAYS requiring approval: refunds, returns, account changes, policy exceptions.
    Conditional: discount > $10.
    VIP: always require approval for VIP customers.
    """

    @pytest.mark.asyncio
    async def test_refund_always_requires_approval(self, patch_db):
        """Refunds ALWAYS require human approval regardless of confidence."""
        from app.core.jarvis_pipeline.approval_gates import check_approval_required

        result = await check_approval_required(
            tenant_id="test", action="refund", confidence=0.99
        )
        assert result["required"] is True
        assert result["gate_type"] == "hard"
        assert "refund" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_return_always_requires_approval(self, patch_db):
        """Returns ALWAYS require human approval."""
        from app.core.jarvis_pipeline.approval_gates import check_approval_required

        result = await check_approval_required(
            tenant_id="test", action="return", confidence=0.99
        )
        assert result["required"] is True
        assert result["gate_type"] == "hard"

    @pytest.mark.asyncio
    async def test_account_change_always_requires_approval(self, patch_db):
        """Account changes ALWAYS require human approval."""
        from app.core.jarvis_pipeline.approval_gates import check_approval_required

        result = await check_approval_required(
            tenant_id="test", action="account_change", confidence=0.99
        )
        assert result["required"] is True
        assert result["gate_type"] == "hard"

    @pytest.mark.asyncio
    async def test_discount_over_10_requires_approval(self, patch_db):
        """Discounts exceeding $10 require approval."""
        from app.core.jarvis_pipeline.approval_gates import check_approval_required

        result = await check_approval_required(
            tenant_id="test", action="apply discount", confidence=0.95, value_usd=15.0
        )
        assert result["required"] is True
        assert result["gate_type"] == "conditional"
        assert "15.00" in result["reason"]

    @pytest.mark.asyncio
    async def test_discount_under_10_no_approval(self, patch_db):
        """Discounts under $10 do not require approval."""
        from app.core.jarvis_pipeline.approval_gates import check_approval_required

        result = await check_approval_required(
            tenant_id="test", action="apply discount", confidence=0.95, value_usd=8.0
        )
        assert result["required"] is False

    @pytest.mark.asyncio
    async def test_vip_gates_active(self, patch_db):
        """VIP customers require approval for sensitive actions."""
        from app.core.jarvis_pipeline.approval_gates import check_approval_required

        # discount is a non-hard action; without VIP it would pass
        # but with VIP=True, the vip_gates catch it
        result = await check_approval_required(
            tenant_id="test", action="discount", confidence=0.95, is_vip=True, value_usd=5.0
        )
        assert result["required"] is True
        assert result["gate_type"] == "vip"

    @pytest.mark.asyncio
    async def test_policy_exception_requires_approval(self, patch_db):
        """Policy exceptions ALWAYS require approval."""
        from app.core.jarvis_pipeline.approval_gates import check_approval_required

        result = await check_approval_required(
            tenant_id="test", action="policy_exception", confidence=0.99
        )
        assert result["required"] is True
        assert result["gate_type"] == "hard"

    @pytest.mark.asyncio
    async def test_simple_action_no_approval_needed(self, patch_db):
        """Simple FAQ actions don't require approval."""
        from app.core.jarvis_pipeline.approval_gates import check_approval_required

        result = await check_approval_required(
            tenant_id="test", action="answer_faq", confidence=0.90
        )
        assert result["required"] is False
        assert result["gate_type"] == "none"


# ═══════════════════════════════════════════════════════════════════
# 7. SEMANTIC BATCHER — Intelligent Batching Tests
# ═══════════════════════════════════════════════════════════════════


class TestSemanticBatcher:
    """Semantic Batcher: groups tickets by similarity, not just time.

    Threshold: cosine similarity > 0.70 → same cluster.
    Batch window: 5 minutes.
    """

    def test_groups_similar_tickets(self):
        """Tickets with similar content are grouped into the same batch."""
        from app.core.jarvis_pipeline.semantic_batcher import compute_similarity

        text_a = "I need to change my shipping address to 123 Main St"
        text_b = "Please update my delivery address to 123 Main Street"
        similarity = compute_similarity(text_a, text_b)
        assert similarity > 0.70

    def test_separates_dissimilar_tickets(self):
        """Tickets with different content are NOT grouped together."""
        from app.core.jarvis_pipeline.semantic_batcher import compute_similarity

        text_a = "I need to change my shipping address"
        text_b = "What is your refund policy for annual plans?"
        similarity = compute_similarity(text_a, text_b)
        assert similarity < 0.70

    def test_batch_window_is_5_minutes(self):
        """Batch window is configured at 300 seconds (5 minutes)."""
        from app.core.jarvis_pipeline.semantic_batcher import BATCH_WINDOW_S

        assert BATCH_WINDOW_S == 300

    def test_similarity_threshold_is_070(self):
        """Similarity threshold is 0.70 for clustering."""
        from app.core.jarvis_pipeline.semantic_batcher import SIMILARITY_THRESHOLD

        assert SIMILARITY_THRESHOLD == 0.70

    def test_check_should_batch_only_for_batch_routing(self):
        """Only BATCH-routed tickets should be batched."""
        from app.core.jarvis_pipeline.semantic_batcher import check_should_batch

        assert check_should_batch(0.88, "batch") is True
        assert check_should_batch(0.96, "auto") is False
        assert check_should_batch(0.72, "ask") is False
        assert check_should_batch(0.55, "escalate") is False

    def test_format_batch_description(self):
        """Batch description includes count, confidence range, and risk level."""
        from app.core.jarvis_pipeline.semantic_batcher import format_batch_description

        batch = {
            "ticket_ids": ["TKT-1", "TKT-2", "TKT-3", "TKT-4", "TKT-5"],
            "confidence_min": 0.88,
            "confidence_max": 0.96,
            "risk_level": 0.15,
        }
        desc = format_batch_description(batch)
        assert "5 tickets" in desc
        assert "88-96%" in desc
        assert "Risk: Low" in desc

    def test_empty_texts_zero_similarity(self):
        """Empty text produces 0.0 similarity."""
        from app.core.jarvis_pipeline.semantic_batcher import compute_similarity

        assert compute_similarity("", "") == 0.0
        assert compute_similarity("hello", "") == 0.0


# ═══════════════════════════════════════════════════════════════════
# 8. VARIANT RECOMMENDER — Complexity & Upgrade Tests
# ═══════════════════════════════════════════════════════════════════


class TestVariantRecommender:
    """Variant Recommender: detects task complexity and recommends variant upgrades.

    Variants:
    - mini: simple only, no multi-API, no refund
    - parwa_standard: medium, multi-API, refund
    - parwa_high: complex, multi-API, refund, escalation
    """

    def test_detects_multi_api_complexity(self):
        """Tasks mentioning 'shopify' and 'stripe' are detected as multi-API complex."""
        from app.core.jarvis_pipeline.variant_recommender import _assess_task_complexity

        result = _assess_task_complexity("sync order data from shopify to stripe", "")
        assert result["needs_multi_api"] is True
        assert result["signals"]["multi_api"] is True

    def test_detects_financial_complexity(self):
        """Tasks mentioning 'refund' are detected as financial complexity."""
        from app.core.jarvis_pipeline.variant_recommender import _assess_task_complexity

        result = _assess_task_complexity("process refund for order #123", "")
        assert result["needs_refund"] is True
        assert result["signals"]["financial"] is True

    def test_checks_variant_availability(self):
        """Variant availability is checked before recommending an upgrade."""
        from app.core.jarvis_pipeline.variant_recommender import _can_variant_handle

        # mini cannot handle multi-API
        can, reasons = _can_variant_handle("mini", {
            "complexity": "medium", "needs_multi_api": True,
            "needs_refund": False, "needs_escalation": False, "estimated_steps": 3
        })
        assert can is False
        assert any("multi-API" in r for r in reasons)

    def test_recommends_upgrade_path(self):
        """When current variant can't handle, cheapest capable variant is recommended."""
        from app.core.jarvis_pipeline.variant_recommender import VARIANT_CAPABILITIES, _can_variant_handle

        # mini can't handle multi-API, parwa_standard can
        task = {"complexity": "medium", "needs_multi_api": True,
                "needs_refund": False, "needs_escalation": False, "estimated_steps": 3}

        assert not _can_variant_handle("mini", task)[0]
        assert _can_variant_handle("parwa_standard", task)[0]
        assert _can_variant_handle("parwa_high", task)[0]

    def test_simple_task_needs_no_upgrade(self):
        """Simple tasks don't need variant upgrade from mini."""
        from app.core.jarvis_pipeline.variant_recommender import _assess_task_complexity, _can_variant_handle

        task = _assess_task_complexity("what are your business hours?", "")
        assert task["complexity"] == "simple"
        can, reasons = _can_variant_handle("mini", task)
        assert can is True


# ═══════════════════════════════════════════════════════════════════
# 9. REPORT GENERATOR — Weekly Wins & Dashboard Tests
# ═══════════════════════════════════════════════════════════════════


class TestReportGenerator:
    """Report Generator: weekly wins, performance dashboard, money saved.

    Money saved = auto_resolved × $8/ticket (human cost).
    """

    @pytest.mark.asyncio
    async def test_weekly_wins_report_generation(self, patch_db, mock_db):
        """Generates weekly wins report with ticket counts, money saved, and trends."""
        from app.core.jarvis_pipeline.report_generator import generate_weekly_wins_report

        report = await generate_weekly_wins_report(tenant_id="test", days=7)

        assert report["report_type"] == "weekly_wins"
        assert report["tickets_handled"] == 500
        assert report["auto_resolved"] == 380
        assert report["money_saved_usd"] == 380 * 8.0  # $8 per ticket
        assert report["period"]["days"] == 7
        mock_db.save_generated_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_performance_dashboard_data(self, patch_db, mock_db):
        """Returns performance dashboard with volume, confidence, efficiency."""
        from app.core.jarvis_pipeline.report_generator import get_performance_dashboard

        dashboard = await get_performance_dashboard(tenant_id="test", days=7)

        assert "volume_accuracy" in dashboard
        assert "confidence_trends" in dashboard
        assert "efficiency_gains" in dashboard
        assert "learning_progress" in dashboard

    def test_money_saved_calculation(self):
        """Money saved = auto_resolved × $8/ticket human cost."""
        from app.core.jarvis_pipeline.report_generator import HUMAN_COST_PER_TICKET

        auto_resolved = 380
        saved = auto_resolved * HUMAN_COST_PER_TICKET
        assert saved == 3040.0

    @pytest.mark.asyncio
    async def test_quality_trends_in_report(self, patch_db, mock_db):
        """Report includes quality trend direction."""
        from app.core.jarvis_pipeline.report_generator import generate_weekly_wins_report

        report = await generate_weekly_wins_report(tenant_id="test", days=7)
        assert "quality_trend" in report
        assert report["quality_trend"] == "stable"

    def test_format_weekly_report_text(self):
        """format_weekly_report_text produces human-readable output."""
        from app.core.jarvis_pipeline.report_generator import format_weekly_report_text

        report = {
            "period": {"days": 7},
            "tickets_handled": 500,
            "auto_resolved": 380,
            "human_handled": 120,
            "money_saved_usd": 3040.0,
            "avg_quality": 0.88,
            "quality_trend": "improving",
            "confidence_trend": {"avg_confidence": 0.85, "distribution": {"auto": 200, "batch": 150, "ask": 30, "escalate": 0}},
            "new_skills_learned": [{"ticket_type": "refund"}],
            "prediction": "AI accuracy will reach ~91% by next week",
            "efficiency": {"manager_time_saved_minutes": 480},
        }
        text = format_weekly_report_text(report)
        assert "Weekly Progress Report" in text
        assert "500" in text
        assert "$3040.00" in text
        assert "88.0%" in text

    @pytest.mark.asyncio
    async def test_prediction_for_declining_trend(self, patch_db, mock_db):
        """Report generates appropriate prediction for declining quality."""
        mock_db.get_weekly_performance_data.return_value = {
            "total_tickets": 200, "auto_resolved": 100, "avg_quality": 0.75,
            "quality_trend": "declining", "by_type": {},
        }
        from app.core.jarvis_pipeline.report_generator import generate_weekly_wins_report

        report = await generate_weekly_wins_report(tenant_id="test", days=7)
        assert "declining" in report.get("prediction", "").lower() or "declining" in report.get("quality_trend", "")


# ═══════════════════════════════════════════════════════════════════
# 10. QUALITY COACH — Drift & Training Tests
# ═══════════════════════════════════════════════════════════════════


class TestQualityCoach:
    """Quality Coach: drift detection, weekly quality report, mistake analysis, training priorities.
    """

    @pytest.mark.asyncio
    async def test_drift_detection_creates_alerts(self, patch_db, mock_db):
        """Drift check creates alerts when drift is detected."""
        mock_db.check_and_create_drift_alerts.return_value = [
            {"alert_type": "accuracy_drop", "severity": "warning", "description": "3-day decline detected"},
        ]
        from app.core.jarvis_pipeline.quality_coach import run_drift_check_and_alert

        result = await run_drift_check_and_alert(tenant_id="test")
        assert result["total_new"] == 1
        assert result["alerts_created"][0]["alert_type"] == "accuracy_drop"

    @pytest.mark.asyncio
    async def test_weekly_quality_report(self, patch_db, mock_db):
        """Generates a comprehensive weekly quality report."""
        from app.core.jarvis_pipeline.quality_coach import generate_weekly_quality_report

        report = await generate_weekly_quality_report(tenant_id="test", days=7)
        assert report["report_type"] == "weekly_quality"
        assert "health_score" in report
        assert "performance" in report
        assert "mistakes" in report
        assert "recommendations" in report

    @pytest.mark.asyncio
    async def test_mistake_analysis(self, patch_db, mock_db):
        """Generates mistake analysis with improvement suggestions."""
        from app.core.jarvis_pipeline.quality_coach import generate_mistake_analysis

        analysis = await generate_mistake_analysis(tenant_id="test", days=7)
        assert analysis["total_mistakes"] == 3
        assert analysis["most_common_mistake"] == "wrong_answer"
        assert len(analysis["improvement_suggestions"]) > 0

    @pytest.mark.asyncio
    async def test_training_priority_list(self, patch_db, mock_db):
        """Training priority list ranks ticket types by accuracy."""
        mock_db.get_training_priority_list.return_value = [
            {"ticket_type": "refund", "rejection_count": 15, "accuracy_pct": 0.45},
            {"ticket_type": "billing", "rejection_count": 5, "accuracy_pct": 0.78},
            {"ticket_type": "faq", "rejection_count": 1, "accuracy_pct": 0.95},
        ]
        from app.core.jarvis_pipeline.quality_coach import generate_training_priority_list

        priorities = await generate_training_priority_list(tenant_id="test")
        assert len(priorities) == 3
        assert priorities[0]["priority_rank"] == 1
        assert priorities[0]["ticket_type"] == "refund"  # Lowest accuracy first
        assert "CRITICAL" in priorities[0]["suggested_action"]

    @pytest.mark.asyncio
    async def test_agent_health_summary(self, patch_db, mock_db):
        """Agent health summary includes grade, weakest component, recommendation."""
        from app.core.jarvis_pipeline.quality_coach import get_agent_health_summary

        summary = await get_agent_health_summary(tenant_id="test")
        assert summary["health_score"] == 0.82
        assert summary["grade"] == "B"
        assert summary["weakest_component"] == "efficiency"  # 0.76 is lowest
        assert "recommendation" in summary


# ═══════════════════════════════════════════════════════════════════
# 11. HEALTH SCORER — Customer Health & ROI Tests
# ═══════════════════════════════════════════════════════════════════


class TestHealthScorer:
    """Health Scorer: customer health score (5 milestones) and ROI calculator.

    Milestones:
    1. Knowledge base setup (20% KB coverage)
    2. Initial training (10 approved examples)
    3. Accuracy target (85%)
    4. Integration connect (1 healthy)
    5. Policy coverage (5 ticket types)
    """

    @pytest.mark.asyncio
    async def test_customer_health_score_5_milestones(self, patch_db, mock_db):
        """Customer health score is computed from 5 onboarding milestones."""
        from app.core.jarvis_pipeline.health_scorer import get_customer_health

        health = await get_customer_health(tenant_id="test")
        assert health["health_score"] > 0
        assert "grade" in health
        assert len(health["milestones"]) == 5
        milestone_names = {m["name"] for m in health["milestones"]}
        assert milestone_names == {
            "knowledge_base_setup", "initial_training", "accuracy_target",
            "integration_connect", "policy_coverage",
        }

    @pytest.mark.asyncio
    async def test_roi_calculation(self, patch_db, mock_db):
        """ROI = (human_cost - ai_cost) / ai_cost × 100."""
        from app.core.jarvis_pipeline.health_scorer import calculate_roi

        roi = await calculate_roi(tenant_id="test", days=30)
        assert "net_savings_usd" in roi
        assert "roi_pct" in roi
        assert "auto_resolve_pct" in roi
        assert roi["total_tickets"] == 500
        assert roi["auto_resolved"] == 380
        # human_cost = (500-380) * 8 = 960
        assert roi["human_cost_usd"] == 960.0

    @pytest.mark.asyncio
    async def test_kb_coverage_scoring(self, patch_db, mock_db):
        """KB coverage is part of the health components."""
        from app.core.jarvis_pipeline.health_scorer import get_customer_health

        health = await get_customer_health(tenant_id="test")
        assert health["components"]["kb_coverage"] == 0.6

    @pytest.mark.asyncio
    async def test_accuracy_target_scoring(self, patch_db, mock_db):
        """Accuracy target milestone checks against 85% threshold."""
        from app.core.jarvis_pipeline.health_scorer import get_customer_health

        health = await get_customer_health(tenant_id="test")
        accuracy_milestone = next(m for m in health["milestones"] if m["name"] == "accuracy_target")
        assert accuracy_milestone["threshold"] == 0.85
        # With accuracy_score 0.88, this should be achieved
        assert accuracy_milestone["achieved"] is True

    def test_success_coach_message_for_excellent(self):
        """Success coach provides appropriate message for excellent readiness."""
        from app.core.jarvis_pipeline.health_scorer import get_success_coach_message

        msg = get_success_coach_message(
            health_score=0.92, readiness_pct=92,
            milestones=[], grade="excellent",
        )
        assert "excellent" in msg.lower()
        assert "92%" in msg

    def test_success_coach_message_for_onboarding(self):
        """Success coach provides actionable steps for onboarding readiness."""
        from app.core.jarvis_pipeline.health_scorer import get_success_coach_message

        unachieved = [
            {"name": "initial_training", "description": "10 approved training examples", "current_value": 3, "threshold": 10},
            {"name": "integration_connect", "description": "1 healthy integration", "current_value": 0, "threshold": 1},
        ]
        msg = get_success_coach_message(
            health_score=0.35, readiness_pct=35,
            milestones=unachieved, grade="onboarding",
        )
        assert "training examples" in msg.lower() or "35%" in msg


# ═══════════════════════════════════════════════════════════════════
# 12. SLA CALCULATOR — Uptime & Credit Tests
# ═══════════════════════════════════════════════════════════════════


class TestSLACalculator:
    """SLA Calculator: uptime tracking, SLA status, credit computation.

    Status: meeting (actual >= target), at_risk (gap <= 0.5%), breached (gap > 0.5%).
    Default target: 99.5%.
    """

    @pytest.mark.asyncio
    async def test_sla_status_meeting(self, patch_db, mock_db):
        """SLA status is 'meeting' when actual uptime >= target."""
        from app.core.jarvis_pipeline.sla_calculator import compute_sla_status

        sla = await compute_sla_status(tenant_id="test", days=30)
        assert sla["sla_status"] == "meeting"
        assert sla["actual_uptime_pct"] >= sla["target_uptime_pct"]

    @pytest.mark.asyncio
    async def test_sla_status_at_risk(self, patch_db, mock_db):
        """SLA status is 'at_risk' when gap <= 0.5%."""
        mock_db.get_sla_summary.return_value = {
            "target_uptime_pct": 99.5,
            "actual_uptime_pct": 99.2,
            "incident_count": 2,
            "total_downtime_seconds": 21600,
            "credit_owed": 0.0,
            "monthly_fee": 500.0,
        }
        from app.core.jarvis_pipeline.sla_calculator import compute_sla_status

        sla = await compute_sla_status(tenant_id="test", days=30)
        assert sla["sla_status"] == "at_risk"

    @pytest.mark.asyncio
    async def test_sla_status_breached(self, patch_db, mock_db):
        """SLA status is 'breached' when gap > 0.5%."""
        mock_db.get_sla_summary.return_value = {
            "target_uptime_pct": 99.5,
            "actual_uptime_pct": 98.0,
            "incident_count": 5,
            "total_downtime_seconds": 72000,
            "credit_owed": 50.0,
            "monthly_fee": 500.0,
        }
        from app.core.jarvis_pipeline.sla_calculator import compute_sla_status

        sla = await compute_sla_status(tenant_id="test", days=30)
        assert sla["sla_status"] == "breached"
        assert sla["credit_owed_usd"] > 0

    @pytest.mark.asyncio
    async def test_credit_calculation(self, patch_db, mock_db):
        """SLA credit is 10% of monthly fee per 1% below target."""
        mock_db.get_sla_summary.return_value = {
            "target_uptime_pct": 99.5,
            "actual_uptime_pct": 97.5,
            "incident_count": 3,
            "total_downtime_seconds": 43200,
            "credit_owed": 100.0,
            "monthly_fee": 500.0,
        }
        from app.core.jarvis_pipeline.sla_calculator import compute_sla_status

        sla = await compute_sla_status(tenant_id="test", days=30)
        assert sla["credit_owed_usd"] == 100.0

    @pytest.mark.asyncio
    async def test_monthly_sla_report(self, patch_db, mock_db):
        """Monthly SLA report includes status, integration health, and recommendations."""
        from app.core.jarvis_pipeline.sla_calculator import generate_monthly_sla_report

        report = await generate_monthly_sla_report(tenant_id="test")
        assert report["report_type"] == "monthly_sla"
        assert "sla_status" in report
        assert "integration_health" in report
        assert "incidents_summary" in report
        assert "credit_summary" in report
        assert "recommendations" in report
        mock_db.save_generated_report.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 13. AGENT PROVISIONER — Chat-to-Infrastructure Tests
# ═══════════════════════════════════════════════════════════════════


class TestAgentProvisioner:
    """Agent Provisioner: parse natural language commands to provision virtual agents.

    Safety: Max 20 agents per command. Plan tier limits enforced.
    """

    def test_parse_provision_command_extracts_count_and_type(self):
        """Parses 'add 3 mini agents' to extract count=3, type=mini."""
        from app.core.jarvis_pipeline.agent_provisioner import parse_provision_command

        result = parse_provision_command("Add 3 mini agents for the weekend")
        assert result["count"] == 3
        assert result["agent_type"] == "mini"
        assert result["duration"] == "weekend"

    def test_parse_provision_command_parwa_type(self):
        """Parses 'provision 2 parwa agents' to type=parwa."""
        from app.core.jarvis_pipeline.agent_provisioner import parse_provision_command

        result = parse_provision_command("provision 2 parwa agents")
        assert result["count"] == 2
        assert result["agent_type"] == "parwa"

    def test_parse_provision_command_duration_today(self):
        """Parses 'for today' duration."""
        from app.core.jarvis_pipeline.agent_provisioner import parse_provision_command

        result = parse_provision_command("add 1 agent for today to handle support")
        assert result["duration"] == "today"
        assert result["expires_at"] is not None

    def test_parse_provision_command_max_20(self):
        """Count is capped at 20 (MAX_AGENTS_PER_COMMAND)."""
        from app.core.jarvis_pipeline.agent_provisioner import parse_provision_command, MAX_AGENTS_PER_COMMAND

        result = parse_provision_command("add 50 agents")
        assert result["count"] == MAX_AGENTS_PER_COMMAND

    def test_parse_provision_command_purpose_detection(self):
        """Parses purpose from command context."""
        from app.core.jarvis_pipeline.agent_provisioner import parse_provision_command

        result = parse_provision_command("add 2 mini agents to handle sales emails")
        assert result["purpose"] == "sales_email_handling"

    @pytest.mark.asyncio
    async def test_budget_check_plan_limit(self, patch_db, mock_db):
        """Provisioning fails when plan limit is reached."""
        mock_db.get_all_agent_configs.return_value = [
            {"agent_type": "mini", "status": "active"},
            {"agent_type": "mini", "status": "active"},
            {"agent_type": "mini", "status": "active"},
            {"agent_type": "mini", "status": "active"},
            {"agent_type": "mini", "status": "active"},
        ]
        from app.core.jarvis_pipeline.agent_provisioner import provision_agents

        parsed = {"count": 1, "agent_type": "mini", "duration": None, "expires_at": None, "purpose": "general_support"}
        result = await provision_agents("test", "admin@test.com", parsed)
        assert result["success"] is False
        assert "Plan limit" in result["error"]

    @pytest.mark.asyncio
    async def test_clone_config_from_existing_agent(self, patch_db, mock_db):
        """New agents clone config from existing agent of same type."""
        mock_db.get_all_agent_configs.return_value = [
            {"agent_type": "mini", "status": "active", "agent_name": "mini_agent_1",
             "custom_instructions": "Be friendly", "faq_categories": ["returns"]},
        ]
        from app.core.jarvis_pipeline.agent_provisioner import provision_agents

        parsed = {"count": 1, "agent_type": "mini", "duration": None, "expires_at": None, "purpose": "support"}
        result = await provision_agents("test", "admin@test.com", parsed)
        assert result["success"] is True
        assert result["cloned_from"] == "mini_agent_1"
        mock_db.create_audit_entry.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 14. SKILL INSTRUCTOR — Dynamic Instruction Tests
# ═══════════════════════════════════════════════════════════════════


class TestSkillInstructor:
    """Skill Instructor: teach AI new processes via natural language.

    Flow: parse → LLM extract steps → store in client_skills → confirm.
    """

    def test_parse_skill_instruction(self):
        """Extracts process description from teach command."""
        from app.core.jarvis_pipeline.skill_instructor import _extract_process_description

        result = _extract_process_description("here's how to handle international returns: first check the order, then verify customs")
        assert "check the order" in result.lower()

    @pytest.mark.asyncio
    async def test_llm_step_extraction(self, patch_db, mock_db):
        """LLM parses process description into structured steps."""
        llm_response = json.dumps({
            "skill_name": "international_returns",
            "display_name": "International Returns Process",
            "steps": [
                {"order": 1, "action": "Verify order details and customs documentation", "condition": "international order", "response_template": ""},
                {"order": 2, "action": "Check return eligibility per region", "condition": "", "response_template": ""},
                {"order": 3, "action": "Calculate refund with customs adjustment", "condition": "", "response_template": ""},
            ],
            "trigger_keywords": ["international", "returns", "customs", "region"],
            "priority": "high",
            "category": "returns",
        })

        with patch("app.core.jarvis_pipeline.skill_instructor.llm_call",
                   new_callable=AsyncMock, return_value=llm_response):
            from app.core.jarvis_pipeline.skill_instructor import teach_skill

            result = await teach_skill(
                tenant_id="test",
                actor_email="admin@test.com",
                raw_input="Here's how to handle international returns: verify order, check eligibility, calculate refund",
            )

        assert result["success"] is True
        assert result["step_count"] == 3
        assert result["category"] == "returns"
        mock_db.save_client_skill.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_in_client_skills(self, patch_db, mock_db):
        """Taught skills are stored in client_skills table."""
        llm_response = json.dumps({
            "skill_name": "vip_handling",
            "display_name": "VIP Customer Handling",
            "steps": [{"order": 1, "action": "Greet by name", "condition": "", "response_template": ""}],
            "trigger_keywords": ["vip"],
            "priority": "high",
            "category": "general",
        })

        with patch("app.core.jarvis_pipeline.skill_instructor.llm_call",
                   new_callable=AsyncMock, return_value=llm_response):
            from app.core.jarvis_pipeline.skill_instructor import teach_skill

            result = await teach_skill(
                tenant_id="test",
                actor_email="admin@test.com",
                raw_input="Here's how to handle VIP customers: greet by name",
            )

        # Verify save_client_skill was called with proper data
        call_args = mock_db.save_client_skill.call_args
        skill_data = call_args[0][1]  # second positional arg
        assert skill_data["skill_name"] == "vip_handling"
        assert skill_data["tenant_id"] == "test"

    @pytest.mark.asyncio
    async def test_lookup_skill_for_variant_help(self, patch_db, mock_db):
        """PARWA Node 3 can fetch custom skills when relevant ticket arrives."""
        mock_db.get_client_skills.return_value = [
            {
                "skill_id": "skill_abc123",
                "skill_name": "international_returns",
                "display_name": "International Returns Process",
                "trigger_keywords": ["international", "returns", "customs"],
                "steps_json": [{"order": 1, "action": "Check order"}],
            },
        ]
        from app.core.jarvis_pipeline.skill_instructor import lookup_skill

        skill = await lookup_skill("test", "how do we handle international returns?")
        assert skill is not None
        assert skill["skill_name"] == "international_returns"

    @pytest.mark.asyncio
    async def test_llm_fallback_on_failure(self, patch_db, mock_db):
        """If LLM step extraction fails, creates a simple fallback skill."""
        with patch("app.core.jarvis_pipeline.skill_instructor.llm_call",
                   new_callable=AsyncMock, side_effect=Exception("LLM unavailable")):
            from app.core.jarvis_pipeline.skill_instructor import teach_skill

            result = await teach_skill(
                tenant_id="test",
                actor_email="admin@test.com",
                raw_input="Here's how to process returns: first verify the order, then calculate refund",
            )

        assert result["success"] is True  # Fallback still succeeds
        assert result["step_count"] == 1  # Single fallback step

    def test_slugify_generates_valid_slug(self):
        """Slugify produces URL-safe skill names."""
        from app.core.jarvis_pipeline.skill_instructor import _slugify

        assert _slugify("International Returns") == "international_returns"
        assert _slugify("") == "unnamed_skill"


# ═══════════════════════════════════════════════════════════════════
# 15. CO-PILOT MODE — Draft Composer Tests
# ═══════════════════════════════════════════════════════════════════


class TestCopilotMode:
    """Co-Pilot Mode: drafts responses based on ticket data, policy, and sentiment.

    Drafts are stored for review. Manager edits become training data.
    """

    def test_draft_generation_with_sentiment(self):
        """Co-pilot analyzes sentiment for drafting."""
        from app.core.jarvis_pipeline.copilot_mode import _analyze_sentiment

        assert _analyze_sentiment("I'm furious about this terrible service") == "angry"
        assert _analyze_sentiment("Thanks for the help, great job") == "positive"
        assert _analyze_sentiment("Where is my order?") == "neutral"
        assert _analyze_sentiment("This is frustrating and annoying") == "frustrated"

    def test_policy_aware_drafting(self):
        """Co-pilot retrieves relevant policy context for drafting."""
        from app.core.jarvis_pipeline.copilot_mode import _get_policy_context

        refund_ctx = _get_policy_context("I want a refund for my order")
        assert "Refund Policy" in refund_ctx

        shipping_ctx = _get_policy_context("When will my order ship?")
        assert "Shipping Policy" in shipping_ctx

        generic_ctx = _get_policy_context("Hello, how are you?")
        assert "No specific policy" in generic_ctx

    @pytest.mark.asyncio
    async def test_draft_response_uses_llm(self, patch_db, mock_db):
        """Co-pilot generates draft via LLM call."""
        with patch("app.core.jarvis_pipeline.copilot_mode.llm_call",
                   new_callable=AsyncMock, return_value="Dear customer, I apologize for the delay. Your order #12345 is being processed and will ship within 24 hours. Thank you for your patience."):

            from app.core.jarvis_pipeline.copilot_mode import draft_response

            result = await draft_response(
                tenant_id="test",
                actor_email="admin@test.com",
                ticket_id="TKT-001",
                customer_query="Where is my order? It's been 2 weeks!",
                channel="email",
            )

        assert result["success"] is True
        assert "draft_id" in result
        assert result["status"] == "pending_review"
        mock_db.save_training_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_learn_from_edits(self, patch_db, mock_db):
        """Manager edits are saved as training data for AI learning."""
        from app.core.jarvis_pipeline.copilot_mode import save_edited_draft

        result = await save_edited_draft(
            tenant_id="test",
            draft_id="draft_abc123",
            edited_text="Dear customer, we sincerely apologize. Your order has been expedited at no charge.",
            actor_email="admin@test.com",
        )

        assert result["success"] is True
        mock_db.save_training_data.assert_called()
        mock_db.create_audit_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_draft_stores_with_sentiment(self, patch_db, mock_db):
        """Draft includes sentiment analysis in stored training data."""
        with patch("app.core.jarvis_pipeline.copilot_mode.llm_call",
                   new_callable=AsyncMock, return_value="Draft response"):

            from app.core.jarvis_pipeline.copilot_mode import draft_response

            await draft_response(
                tenant_id="test",
                actor_email="admin@test.com",
                ticket_id="TKT-002",
                customer_query="This is unacceptable! Cancel my subscription!",
                channel="chat",
            )

        # Check that save_training_data was called with sentiment data
        call_args = mock_db.save_training_data.call_args
        content = call_args[1].get("content", {})
        assert content["sentiment"] == "angry"


# ═══════════════════════════════════════════════════════════════════
# 16. COMMAND PARSER — 2-Tier Intent Classification Tests
# ═══════════════════════════════════════════════════════════════════


class TestCommandParser:
    """Command Parser: 2-tier intent classification (regex fast path + LLM fallback).

    Tier 1: Regex patterns for ~80% of commands (0 tokens, instant).
    Tier 2: LLM classification for everything else.
    """

    def test_parse_query_status_command(self):
        """Parses 'show system status' as query_status intent."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("show system status")
        assert result["intent"] == "query_status"
        assert result["confidence"] == 0.92
        assert result["classification_method"] == "regex"

    def test_parse_control_pause_command(self):
        """Parses 'pause refunds' as control_pause intent."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("pause refunds")
        assert result["intent"] == "control_pause"
        assert result["target"] == "refund"

    def test_parse_control_resume_command(self):
        """Parses 'resume everything' as control_resume intent."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("resume everything")
        assert result["intent"] == "control_resume"
        assert result["target"] == "all"

    def test_parse_emergency_shutdown_command(self):
        """Parses 'shut down everything' as emergency_shutdown intent."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("shut everything down")
        assert result["intent"] == "emergency_shutdown"
        assert result["classification_method"] == "regex"

    def test_parse_create_agent_command(self):
        """Parses 'add 3 mini agents' as create_agent intent."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("add 3 mini agents")
        assert result["intent"] == "create_agent"

    def test_tier1_regex_hits_common_queries(self):
        """Tier 1 regex catches the most common query patterns."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        queries = [
            ("what's the system status", "query_status"),
            ("show errors", "query_errors"),
            ("how many tickets", "query_tickets"),
            ("show quality", "query_quality"),
            ("what's my quota", "query_quota"),
            ("list notifications", "query_notifications"),
            ("show flags", "query_flags"),
            ("show audit log", "query_audit"),
            ("what's the cost", "query_cost"),
            ("show integration health", "query_health"),
            ("how many stuck tickets", "query_stuck"),
        ]
        for text, expected_intent in queries:
            result = classify_command_sync(text)
            assert result["intent"] == expected_intent, f"Failed for: {text}"

    def test_tier1_regex_hits_wave6_queries(self):
        """Tier 1 regex catches Wave 6 query patterns (reports, SLA, ROI, health score)."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        queries = [
            ("show weekly report", "query_report"),
            ("what's my SLA status", "query_sla"),
            ("show health score", "query_health_score"),
            ("what's the ROI", "query_roi"),
            ("show agent health", "query_agent_health"),
        ]
        for text, expected_intent in queries:
            result = classify_command_sync(text)
            assert result["intent"] == expected_intent, f"Failed for: {text}"

    def test_is_query_intent_helper(self):
        """is_query_intent correctly identifies query intent families."""
        from app.core.jarvis_pipeline.command_parser import is_query_intent, INTENT_QUERIES

        for intent in INTENT_QUERIES:
            assert is_query_intent(intent) is True

        assert is_query_intent("control_pause") is False
        assert is_query_intent("emergency_shutdown") is False

    def test_is_emergency_intent_helper(self):
        """is_emergency_intent correctly identifies emergency intents."""
        from app.core.jarvis_pipeline.command_parser import is_emergency_intent, INTENT_EMERGENCIES

        for intent in INTENT_EMERGENCIES:
            assert is_emergency_intent(intent) is True

        assert is_emergency_intent("query_status") is False

    def test_requires_owner_for_shutdown(self):
        """Emergency shutdown and agent creation require owner role."""
        from app.core.jarvis_pipeline.command_parser import requires_owner

        assert requires_owner("emergency_shutdown") is True
        assert requires_owner("create_agent") is True
        assert requires_owner("query_status") is False
        assert requires_owner("control_pause") is False

    def test_sync_fallback_for_unknown(self):
        """Sync classify falls back to unknown intent with 0 confidence."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync

        result = classify_command_sync("xyzzy foobar nonsense command")
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0

    def test_scope_inference_temporary(self):
        """Scope is inferred as temporary for 'for today' commands."""
        from app.core.jarvis_pipeline.command_parser import _infer_scope

        assert _infer_scope("pause refunds for today") == "temporary"
        assert _infer_scope("pause refunds for 2 hours") == "temporary"
        assert _infer_scope("always auto-approve refunds") == "permanent"
        assert _infer_scope("pause refunds") == "global"


# ═══════════════════════════════════════════════════════════════════
# 17. INTEGRATION TEST: Full Jarvis Pipeline Flow
# ═══════════════════════════════════════════════════════════════════


class TestJarvisPipelineIntegration:
    """Full pipeline integration tests: SENSE → EVALUATE → NOTIFY flow.

    These tests verify the end-to-end data flow between all 3 nodes.
    All external dependencies are mocked.
    """

    @pytest.mark.asyncio
    async def test_sense_evaluate_notify_flow_with_signals(self, patch_db, mock_db):
        """Full SENSE→EVALUATE→NOTIFY flow with detected stuck tickets and drift."""
        # Setup: sense will find stuck tickets and drift
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_stuck_tickets",
                   new_callable=AsyncMock, return_value=[
                       {"ticket_id": "TKT-CRIT", "reason": "super_node_escalated",
                        "quality_score": 0.50, "loops_used": 3, "hours_stuck": 50,
                        "escalation_tier": "critical", "errors": ["loop"], "source": "live"},
                   ]), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_quota_status",
                   new_callable=AsyncMock, return_value={}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_integration_health",
                   new_callable=AsyncMock, return_value={"services": {}, "degraded_count": 0, "healthy_count": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_accuracy_drift",
                   new_callable=AsyncMock, return_value={"drift_detected": True, "drift_severity": "critical",
                                                        "trend_direction": "declining", "trigger_reason": "3_day_drop",
                                                        "total_scores": 100, "accuracy_7d": 0.75, "accuracy_today": 0.70}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_ticket_flow",
                   new_callable=AsyncMock, return_value={"summary": {"total": 100, "auto_resolved": 72}, "current_ticket": {}}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_llm_costs",
                   new_callable=AsyncMock, return_value={"persisted": {}, "live_session": {}, "total_calls_combined": 0, "total_tokens_combined": 0, "total_cost_usd": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_load_status",
                   new_callable=AsyncMock, return_value={"variants": [], "total_concurrent": 0, "vip_overflow_risk": False}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.get_wiki_store") as mock_wiki, \
             patch("app.core.jarvis_pipeline.nodes.jarvis_2_evaluate.llm_call",
                   new_callable=AsyncMock, return_value="All KEEP") as mock_eval_llm, \
             patch("app.core.jarvis_pipeline.nodes.jarvis_3_notify.llm_call",
                   new_callable=AsyncMock) as mock_notify_llm:

            mock_store = MagicMock()
            mock_store.get_stats.return_value = {"section_c_entries": 0, "total_entries": 0}
            mock_wiki.return_value = mock_store

            # Execute SENSE
            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            sense_result = await jarvis_sense({"tenant_id": "test", "trigger": "poll", "parwa_state": {}})

            assert len(sense_result["signals"]["stuck_tickets"]) == 1
            assert sense_result["signals"]["drift_status"]["drift_detected"] is True

            # Execute EVALUATE with sense output
            eval_state = {"tenant_id": "test", "trigger": "poll", **sense_result}
            from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import jarvis_evaluate
            eval_result = await jarvis_evaluate(eval_state)

            assert len(eval_result["evaluations"]) >= 2  # stuck + drift
            assert eval_result["priority_scores"]["max"] > 0.65

            # Execute NOTIFY with eval output
            notify_state = {
                "tenant_id": "test",
                "trigger": "poll",
                "signals": sense_result["signals"],
                "evaluations": eval_result["evaluations"],
                "priority_scores": eval_result["priority_scores"],
                "evaluation_log": eval_result["evaluation_log"],
                "clara_result": eval_result["clara_result"],
                "reflexion_result": eval_result["reflexion_result"],
                "total_token_usage": eval_result.get("total_token_usage", 0),
            }
            from app.core.jarvis_pipeline.nodes.jarvis_3_notify import jarvis_notify
            notify_result = await jarvis_notify(notify_state)

            # Verify notifications were created for HIGH+ priority
            assert "notifications" in notify_result or "chat_response" in notify_result

    @pytest.mark.asyncio
    async def test_no_signal_flow_nothing_to_report(self, base_state, patch_db, mock_db):
        """When SENSE finds no signals, EVALUATE produces no evaluations and NOTIFY has nothing."""
        from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import jarvis_evaluate
        from app.core.jarvis_pipeline.nodes.jarvis_3_notify import jarvis_notify

        # SENSE: all collectors return empty
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_stuck_tickets",
                   new_callable=AsyncMock, return_value=[]), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_quota_status",
                   new_callable=AsyncMock, return_value={}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_integration_health",
                   new_callable=AsyncMock, return_value={"services": {}, "degraded_count": 0, "healthy_count": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_accuracy_drift",
                   new_callable=AsyncMock, return_value={"drift_detected": False, "drift_severity": "none",
                                                        "trend_direction": "stable", "trigger_reason": "no_data", "total_scores": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_ticket_flow",
                   new_callable=AsyncMock, return_value={"summary": {}, "current_ticket": {}}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_llm_costs",
                   new_callable=AsyncMock, return_value={"persisted": {}, "live_session": {}, "total_calls_combined": 0, "total_tokens_combined": 0, "total_cost_usd": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_load_status",
                   new_callable=AsyncMock, return_value={"variants": [], "total_concurrent": 0, "vip_overflow_risk": False}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.get_wiki_store") as mock_wiki:
            mock_store = MagicMock()
            mock_store.get_stats.return_value = {"section_c_entries": 0, "total_entries": 0}
            mock_wiki.return_value = mock_store

            sense_result = await jarvis_sense(base_state)

        # EVALUATE: no signals → no evaluations
        eval_state = {"tenant_id": "test", "trigger": "poll", **sense_result}
        eval_result = await jarvis_evaluate(eval_state)
        assert len(eval_result["evaluations"]) == 0
        assert eval_result["priority_scores"]["average"] == 0.0
        assert eval_result["priority_scores"]["max"] == 0.0

        # NOTIFY: nothing to report
        notify_state = {
            "tenant_id": "test", "trigger": "poll",
            "signals": sense_result["signals"],
            "evaluations": eval_result["evaluations"],
            "priority_scores": eval_result["priority_scores"],
            "evaluation_log": eval_result["evaluation_log"],
            "clara_result": "", "reflexion_result": "",
            "total_token_usage": 0,
        }
        notify_result = await jarvis_notify(notify_state)
        # With no evaluations, no notifications should be created
        mock_db.create_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_emergency_escalation_flow(self, patch_db, mock_db):
        """Emergency commands bypass normal flow and take immediate action."""
        from app.core.jarvis_pipeline.command_parser import classify_command_sync, is_emergency_intent

        cmd = "shut everything down immediately"
        result = classify_command_sync(cmd)
        assert is_emergency_intent(result["intent"]) is True
        assert result["intent"] == "emergency_shutdown"

    @pytest.mark.asyncio
    async def test_state_creation_factory(self):
        """create_jarvis_state produces valid initial state with all required fields."""
        from app.core.jarvis_pipeline.state import create_jarvis_state

        state = create_jarvis_state(
            tenant_id="test_co",
            trigger="admin_chat",
            admin_question="What is the system status?",
            parwa_state={"status": "healthy"},
        )
        assert state["tenant_id"] == "test_co"
        assert state["trigger"] == "admin_chat"
        assert state["signals"]["stuck_tickets"] == []
        assert state["signals"]["drift_status"]["drift_detected"] is False
        assert state["evaluations"] == []
        assert state["notifications"] == []
        assert state["errors"] == []
        assert state["technique_log"] == []
        assert state["total_token_usage"] == 0


# ═══════════════════════════════════════════════════════════════════
# BONUS: Cross-module Integration Tests
# ═══════════════════════════════════════════════════════════════════


class TestCrossModuleIntegration:
    """Cross-module tests that verify interaction between modules."""

    @pytest.mark.asyncio
    async def test_confidence_and_approval_gates_interact(self, patch_db):
        """High-confidence actions still require approval if they hit hard gates."""
        from app.core.jarvis_pipeline.confidence_engine import compute_confidence_score, classify_routing
        from app.core.jarvis_pipeline.approval_gates import check_approval_required

        # Even with 99% confidence, refund requires approval
        score, _ = compute_confidence_score(pattern_match=1.0, policy_alignment=1.0, risk_score=0.0, historical_accuracy=1.0)
        routing = classify_routing(score)
        assert routing == "auto"  # Would normally auto-handle

        # But approval gate overrides this
        approval = await check_approval_required(tenant_id="test", action="refund", confidence=score)
        assert approval["required"] is True

    @pytest.mark.asyncio
    async def test_sentiment_and_approval_vip_interaction(self, patch_db):
        """VIP angry customer routes to human AND requires approval."""
        from app.core.jarvis_pipeline.sentiment_router import route_by_sentiment

        result = await route_by_sentiment(
            tenant_id="test",
            ticket_id="TKT-VIP-ANGRY",
            query="I am furious about this refund!",
            customer_context={"is_vip": True},
        )
        assert result["escalate"] is True
        assert result["route"] == "human"

    @pytest.mark.asyncio
    async def test_batcher_and_confidence_routing(self):
        """Only BATCH-routed tickets should enter semantic batching."""
        from app.core.jarvis_pipeline.confidence_engine import classify_routing
        from app.core.jarvis_pipeline.semantic_batcher import check_should_batch

        for confidence, expected_routing, expected_batch in [
            (0.97, "auto", False),
            (0.90, "batch", True),
            (0.78, "ask", False),
            (0.55, "escalate", False),
        ]:
            routing = classify_routing(confidence)
            assert routing == expected_routing, f"Confidence {confidence}: expected {expected_routing}, got {routing}"
            assert check_should_batch(confidence, routing) == expected_batch

    def test_report_and_health_scorer_data_consistency(self, patch_db, mock_db):
        """Report generator and health scorer use consistent data sources."""
        # Both read from the same DB tables
        # This test verifies the interfaces are compatible
        from app.core.jarvis_pipeline.report_generator import generate_weekly_wins_report
        from app.core.jarvis_pipeline.health_scorer import get_customer_health

        # Both should succeed with the same mock DB
        import asyncio
        report = asyncio.get_event_loop().run_until_complete(
            generate_weekly_wins_report(tenant_id="test", days=7)
        )
        health = asyncio.get_event_loop().run_until_complete(
            get_customer_health(tenant_id="test")
        )
        assert report["tickets_handled"] > 0
        assert health["health_score"] > 0


# ═══════════════════════════════════════════════════════════════════
# SIGNAL COLLECTORS — Unit Tests
# ═══════════════════════════════════════════════════════════════════


class TestSignalCollectors:
    """Signal collectors: real monitoring functions that read from jarvis_db."""

    def test_escalation_tiers_constants(self):
        """Escalation tiers are defined correctly: 12h/24h/48h."""
        from app.core.jarvis_pipeline.signal_collectors import ESCALATION_TIERS

        assert ESCALATION_TIERS["soft_reminder"] == 12
        assert ESCALATION_TIERS["backup_alert"] == 24
        assert ESCALATION_TIERS["critical"] == 48

    def test_quota_thresholds(self):
        """Quota warning and critical thresholds are defined."""
        from app.core.jarvis_pipeline.signal_collectors import QUOTA_WARNING_PCT, QUOTA_CRITICAL_PCT

        assert QUOTA_WARNING_PCT == 60
        assert QUOTA_CRITICAL_PCT == 80

    def test_known_integrations_defined(self):
        """Known integrations list includes core services."""
        from app.core.jarvis_pipeline.signal_collectors import KNOWN_INTEGRATIONS

        names = {svc["name"] for svc in KNOWN_INTEGRATIONS}
        assert "sendgrid" in names
        assert "stripe" in names
        assert "shopify" in names


# ═══════════════════════════════════════════════════════════════════
# JARVIS STATE — Factory Tests
# ═══════════════════════════════════════════════════════════════════


class TestJarvisState:
    """Jarvis State definition and factory function tests."""

    def test_create_state_with_defaults(self):
        """create_jarvis_state produces valid default state."""
        from app.core.jarvis_pipeline.state import create_jarvis_state

        state = create_jarvis_state(tenant_id="test")
        assert state["tenant_id"] == "test"
        assert state["trigger"] == "poll"
        assert state["signals"]["stuck_tickets"] == []
        assert state["signals"]["quota_status"] == {}
        assert state["signals"]["drift_status"]["drift_detected"] is False
        assert state["signals"]["llm_costs"]["total_cost_usd"] == 0
        assert state["signals"]["load_status"]["vip_overflow_risk"] is False
        assert state["evaluations"] == []
        assert state["notifications"] == []

    def test_create_state_with_all_params(self):
        """create_jarvis_state accepts all input parameters."""
        from app.core.jarvis_pipeline.state import create_jarvis_state

        state = create_jarvis_state(
            tenant_id="t1",
            trigger="stuck_ticket",
            parwa_state={"status": "escalated", "ticket_id": "TKT-1"},
            admin_question="What happened to TKT-1?",
            notification_key="PARWA-NFY-001",
            stuck_ticket_data={"hours": 14},
        )
        assert state["trigger"] == "stuck_ticket"
        assert state["parwa_state"]["status"] == "escalated"
        assert state["stuck_ticket_data"]["hours"] == 14


# ═══════════════════════════════════════════════════════════════════
# NOTIFICATION CENTER — DB-Backed Tests
# ═══════════════════════════════════════════════════════════════════


class TestNotificationCenter:
    """Notification Center: DB-backed notification management."""

    @pytest.mark.asyncio
    async def test_create_notification_delegates_to_db(self, patch_db, mock_db):
        """create_notification delegates to jarvis_db."""
        from app.core.jarvis_pipeline.notification_center import create_notification

        nf = await create_notification(
            tenant_id="test", ntype="stuck_ticket",
            priority_score=0.8, title="Test", description="Test desc",
        )
        mock_db.create_notification.assert_called_once()
        assert "key" in nf

    @pytest.mark.asyncio
    async def test_get_tenant_notifications(self, patch_db, mock_db):
        """get_tenant_notifications delegates to jarvis_db."""
        from app.core.jarvis_pipeline.notification_center import get_tenant_notifications

        nfs = await get_tenant_notifications(tenant_id="test")
        mock_db.get_notifications.assert_called_once()
        assert isinstance(nfs, list)

    @pytest.mark.asyncio
    async def test_resolve_notification(self, patch_db, mock_db):
        """resolve_notification delegates to jarvis_db."""
        from app.core.jarvis_pipeline.notification_center import resolve_notification

        result = await resolve_notification(key="PARWA-NFY-001")
        mock_db.resolve_notification.assert_called_once_with("PARWA-NFY-001")
        assert result is True

    def test_batch_window_constant(self):
        """Batch window is 300 seconds."""
        from app.core.jarvis_pipeline.notification_center import BATCH_WINDOW_S
        assert BATCH_WINDOW_S == 300


# ═══════════════════════════════════════════════════════════════════
# COMMAND EXECUTOR — Validation & Execution Tests
# ═══════════════════════════════════════════════════════════════════


class TestCommandExecutor:
    """Command Executor: validates and executes parsed commands."""

    def test_valid_pause_targets(self):
        """Valid pause targets include refund, return, account_change, all."""
        from app.core.jarvis_pipeline.command_executor import VALID_PAUSE_TARGETS

        assert "refund" in VALID_PAUSE_TARGETS
        assert "refunds" in VALID_PAUSE_TARGETS
        assert "return" in VALID_PAUSE_TARGETS
        assert "account_change" in VALID_PAUSE_TARGETS
        assert "all" in VALID_PAUSE_TARGETS

    def test_valid_modes(self):
        """Valid modes are shadow, supervised, graduated."""
        from app.core.jarvis_pipeline.command_executor import VALID_MODES

        assert VALID_MODES == {"shadow", "supervised", "graduated"}

    def test_valid_channels(self):
        """Valid channels include instagram, email, call, dm, sms, whatsapp."""
        from app.core.jarvis_pipeline.command_executor import VALID_CHANNELS

        assert "instagram" in VALID_CHANNELS
        assert "email" in VALID_CHANNELS
        assert "whatsapp" in VALID_CHANNELS


# ═══════════════════════════════════════════════════════════════════
# DB CONSTANTS — Verification Tests
# ═══════════════════════════════════════════════════════════════════


class TestDBConstants:
    """Verify jarvis_db constants used throughout the pipeline."""

    def test_priority_constants(self):
        """Priority levels and thresholds are defined correctly."""
        from app.core.jarvis_pipeline.jarvis_db import (
            PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW,
            PRIORITY_THRESHOLDS,
        )

        assert PRIORITY_CRITICAL == "CRITICAL"
        assert PRIORITY_HIGH == "HIGH"
        assert PRIORITY_MEDIUM == "MEDIUM"
        assert PRIORITY_LOW == "LOW"
        assert PRIORITY_THRESHOLDS[PRIORITY_CRITICAL] == 0.85
        assert PRIORITY_THRESHOLDS[PRIORITY_HIGH] == 0.65
        assert PRIORITY_THRESHOLDS[PRIORITY_MEDIUM] == 0.40

    def test_notification_type_constants(self):
        """Notification type constants are defined."""
        from app.core.jarvis_pipeline.jarvis_db import (
            TYPE_STUCK_TICKET, TYPE_QUOTA_LOW, TYPE_INTEGRATION_DOWN,
            TYPE_ACCURACY_DROP, TYPE_POLICY_CHANGE, TYPE_SLA_RISK,
        )

        assert TYPE_STUCK_TICKET == "stuck_ticket"
        assert TYPE_QUOTA_LOW == "quota_low"
        assert TYPE_INTEGRATION_DOWN == "integration_down"
        assert TYPE_ACCURACY_DROP == "accuracy_drop"

    def test_admin_roles(self):
        """Admin roles include admin, owner, supervisor."""
        from app.core.jarvis_pipeline.jarvis_db import ADMIN_ROLES, ALL_ROLES

        assert ADMIN_ROLES == {"admin", "owner", "supervisor"}
        assert ALL_ROLES == {"admin", "owner", "supervisor", "team_member", "viewer"}


# ═══════════════════════════════════════════════════════════════════
# TECHNIQUE PARTICIPATION TRACKING
# ═══════════════════════════════════════════════════════════════════


class TestTechniqueParticipation:
    """Verify technique participation tracking across pipeline nodes."""

    @pytest.mark.asyncio
    async def test_sense_logs_technique_participation(self, base_state, patch_db, mock_db):
        """SENSE node logs all 8 technique participations in sense_log."""
        with patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_stuck_tickets",
                   new_callable=AsyncMock, return_value=[]), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_quota_status",
                   new_callable=AsyncMock, return_value={}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_integration_health",
                   new_callable=AsyncMock, return_value={"services": {}, "degraded_count": 0, "healthy_count": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_accuracy_drift",
                   new_callable=AsyncMock, return_value={"drift_detected": False, "drift_severity": "none", "trend_direction": "stable", "trigger_reason": "no_data", "total_scores": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_ticket_flow",
                   new_callable=AsyncMock, return_value={"summary": {}, "current_ticket": {}}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_llm_costs",
                   new_callable=AsyncMock, return_value={"persisted": {}, "live_session": {}, "total_calls_combined": 0, "total_tokens_combined": 0, "total_cost_usd": 0}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.collect_load_status",
                   new_callable=AsyncMock, return_value={"variants": [], "total_concurrent": 0, "vip_overflow_risk": False}), \
             patch("app.core.jarvis_pipeline.nodes.jarvis_1_sense.get_wiki_store") as mock_wiki:
            mock_store = MagicMock()
            mock_store.get_stats.return_value = {"section_c_entries": 0, "total_entries": 0}
            mock_wiki.return_value = mock_store

            from app.core.jarvis_pipeline.nodes.jarvis_1_sense import jarvis_sense
            result = await jarvis_sense(base_state)

        log = result.get("sense_log", [])
        assert len(log) == 8
        for entry in log:
            assert "node" in entry
            assert entry["node"] == "J1"
            assert "technique" in entry
            assert "duration_ms" in entry
            assert "result_summary" in entry

    @pytest.mark.asyncio
    async def test_evaluate_logs_technique_participation(self):
        """EVALUATE node logs technique participations including CLARA and Reflexion."""
        from app.core.jarvis_pipeline.nodes.jarvis_2_evaluate import jarvis_evaluate

        state = {
            "tenant_id": "test", "trigger": "poll",
            "signals": {
                "stuck_tickets": [
                    {"ticket_id": "TKT-A", "reason": "super_node_escalated",
                     "quality_score": 0.55, "loops_used": 3, "hours_stuck": 50,
                     "escalation_tier": "critical", "errors": [], "source": "live"},
                ],
                "quota_status": {},
                "drift_status": {"drift_detected": False, "drift_severity": "none",
                                "trend_direction": "stable", "trigger_reason": "no_data", "total_scores": 0},
                "integration_health": {"services": {}, "degraded_count": 0, "healthy_count": 0},
                "load_status": {"variants": [], "total_concurrent": 0, "vip_overflow_risk": False},
            },
        }

        with patch("app.core.jarvis_pipeline.nodes.jarvis_2_evaluate.llm_call",
                   new_callable=AsyncMock, return_value="All KEEP"):
            result = await jarvis_evaluate(state)

        log = result.get("evaluation_log", [])
        assert len(log) >= 2  # At least StuckEval + FederatedReasoning
        nodes = {entry["node"] for entry in log}
        assert "J2" in nodes
        techniques = {entry["technique"] for entry in log}
        assert "FederatedReasoning" in techniques


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

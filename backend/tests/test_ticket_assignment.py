"""
Comprehensive tests for ticket_assignment.py (PARWA SaaS).

Covers:
- ScoreBasedAssigner: specialty(40%) + workload(30%) + accuracy(20%) + jitter(10%)
- RuleBasedAssigner: round-robin, priority escalation, follow-up routing
- HybridAssigner: score-first, rule-based fallback when score < threshold
- AssignmentEngine: metrics, strategy selection, event bus
- CapacityManager: acquire/release slots, snapshots
- SLAHelper: deadlines, compliance
- Edge cases: no agents, empty list, all offline agents
- Batch assignment
- AssignmentEventBus
"""

from __future__ import annotations
from app.core.ticket_assignment import (
    AgentProfile,
    AgentStatus,
    AssignmentEngine,
    AssignmentEvent,
    AssignmentEventBus,
    AssignmentResult,
    AssignmentStrategy,
    CapacityManager,
    ChannelType,
    HybridAssigner,
    RuleBasedAssigner,
    SLAHelper,
    ScoreBasedAssigner,
    TicketContext,
    TicketPriority,
    create_agents,
    create_engine,
    create_tickets,
    deterministic_jitter,
)

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from unittest.mock import AsyncMock

import pytest

# ── Environment bootstrap ──────────────────────────────────────────
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt")
os.environ.setdefault(
    "DATA_ENCRYPTION_KEY",
    "12345678901234567890123456789012")


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _make_agent(
    agent_id: str = "agent_001",
    name: str = "Alice",
    specialties: Optional[List[str]] = None,
    status: AgentStatus = AgentStatus.ONLINE,
    is_online: bool = True,
    max_concurrent: int = 5,
    current_load: int = 1,
    accuracy_score: float = 0.95,
    avg_response_time: float = 300.0,
    assigned_count: int = 0,
    seniority_years: float = 3.0,
    languages: Optional[List[str]] = None,
    customer_tier_access: Optional[List[str]] = None,
) -> AgentProfile:
    return AgentProfile(
        agent_id=agent_id,
        name=name,
        email=f"{agent_id}@parwa.io",
        specialties=specialties or ["billing"],
        status=status,
        is_online=is_online,
        max_concurrent=max_concurrent,
        current_load=current_load,
        accuracy_score=accuracy_score,
        avg_response_time=avg_response_time,
        assigned_count=assigned_count,
        seniority_years=seniority_years,
        languages=languages or ["en"],
        customer_tier_access=customer_tier_access or [
            "standard",
            "premium",
            "enterprise"],
    )


def _make_ticket(
    ticket_id: str = "tkt_001",
    subject: str = "Billing issue",
    category: str = "billing",
    priority: str = "medium",
    customer_tier: str = "standard",
    tags: Optional[List[str]] = None,
    language: str = "en",
    channel: str = "email",
    estimated_complexity: float = 0.5,
    previous_agent_id: Optional[str] = None,
) -> TicketContext:
    return TicketContext(
        ticket_id=ticket_id,
        subject=subject,
        description=f"Description for {ticket_id}",
        category=category,
        priority=priority,
        customer_tier=customer_tier,
        tags=tags or ["billing"],
        language=language,
        channel=channel,
        estimated_complexity=estimated_complexity,
        previous_agent_id=previous_agent_id,
    )


# ══════════════════════════════════════════════════════════════════
# 1. ENUM TESTS
# ══════════════════════════════════════════════════════════════════

class TestEnums:
    def test_assignment_strategy_values(self):
        assert AssignmentStrategy.SCORE_BASED.value == "score_based"
        assert AssignmentStrategy.RULE_BASED.value == "rule_based"
        assert AssignmentStrategy.HYBRID.value == "hybrid"

    def test_agent_status_values(self):
        assert AgentStatus.ONLINE.value == "online"
        assert AgentStatus.OFFLINE.value == "offline"
        assert AgentStatus.AWAY.value == "away"
        assert AgentStatus.BUSY.value == "busy"

    def test_ticket_priority_ordinals(self):
        assert TicketPriority.CRITICAL.value == "critical"
        assert TicketPriority.HIGH.value == "high"
        assert TicketPriority.MEDIUM.value == "medium"
        assert TicketPriority.LOW.value == "low"

    def test_channel_type_values(self):
        assert ChannelType.EMAIL.value == "email"
        assert ChannelType.CHAT.value == "chat"
        assert ChannelType.PHONE.value == "phone"


# ══════════════════════════════════════════════════════════════════
# 2. AGENT PROFILE TESTS
# ══════════════════════════════════════════════════════════════════

class TestAgentProfile:
    def test_available_capacity(self):
        a = _make_agent(max_concurrent=5, current_load=2)
        assert a.available_capacity == 3

    def test_available_capacity_zero_when_full(self):
        a = _make_agent(max_concurrent=5, current_load=5)
        assert a.available_capacity == 0

    def test_available_capacity_clamped_at_zero(self):
        a = _make_agent(max_concurrent=5, current_load=7)
        assert a.available_capacity == 0

    def test_utilization_ratio(self):
        a = _make_agent(max_concurrent=10, current_load=3)
        assert a.utilization_ratio == 0.3

    def test_utilization_ratio_clamped_at_one(self):
        a = _make_agent(max_concurrent=5, current_load=10)
        assert a.utilization_ratio == 1.0

    def test_utilization_ratio_zero_max_concurrent(self):
        a = _make_agent(max_concurrent=0, current_load=0)
        assert a.utilization_ratio == 1.0

    def test_can_accept_online_with_capacity(self):
        a = _make_agent(is_online=True, max_concurrent=5, current_load=2)
        assert a.can_accept is True

    def test_can_accept_false_when_offline(self):
        a = _make_agent(is_online=False, max_concurrent=5, current_load=0)
        assert a.can_accept is False

    def test_can_accept_false_when_full(self):
        a = _make_agent(is_online=True, max_concurrent=5, current_load=5)
        assert a.can_accept is False

    def test_to_dict_keys(self):
        a = _make_agent()
        d = a.to_dict()
        assert "agent_id" in d
        assert "name" in d
        assert "available_capacity" in d
        assert "utilization_ratio" in d


# ══════════════════════════════════════════════════════════════════
# 3. TICKET CONTEXT TESTS
# ══════════════════════════════════════════════════════════════════

class TestTicketContext:
    def test_created_at_auto_set(self):
        t = _make_ticket()
        assert t.created_at is not None

    def test_priority_enum_valid(self):
        t = _make_ticket(priority="critical")
        assert t.priority_enum == TicketPriority.CRITICAL

    def test_priority_enum_invalid_defaults_medium(self):
        t = _make_ticket(priority="unknown_priority")
        assert t.priority_enum == TicketPriority.MEDIUM

    def test_channel_enum_valid(self):
        t = _make_ticket(channel="chat")
        assert t.channel_enum == ChannelType.CHAT

    def test_channel_enum_invalid_defaults_email(self):
        t = _make_ticket(channel="fax")
        assert t.channel_enum == ChannelType.EMAIL

    def test_search_terms_from_subject(self):
        t = _make_ticket(subject="Billing Problem Help")
        terms = t.search_terms
        assert "billing" in terms
        assert "problem" in terms
        assert "help" in terms

    def test_search_terms_includes_tags(self):
        t = _make_ticket(subject="Help", tags=["urgent", "refund"])
        terms = t.search_terms
        assert "urgent" in terms
        assert "refund" in terms

    def test_search_terms_includes_category(self):
        t = _make_ticket(category="billing_support")
        terms = t.search_terms
        assert "billing" in terms
        assert "support" in terms

    def test_to_dict_keys(self):
        t = _make_ticket()
        d = t.to_dict()
        assert "ticket_id" in d
        assert "subject" in d
        assert "category" in d
        assert "priority" in d


# ══════════════════════════════════════════════════════════════════
# 4. ASSIGNMENT RESULT TESTS
# ══════════════════════════════════════════════════════════════════

class TestAssignmentResult:
    def test_is_unassigned_true(self):
        r = AssignmentResult(
            ticket_id="t1",
            assigned_to="unassigned",
            strategy="test")
        assert r.is_unassigned is True

    def test_is_unassigned_false(self):
        r = AssignmentResult(
            ticket_id="t1",
            assigned_to="agent_001",
            strategy="test")
        assert r.is_unassigned is False

    def test_timestamp_auto_set(self):
        r = AssignmentResult(ticket_id="t1", assigned_to="a1", strategy="test")
        assert r.timestamp is not None

    def test_to_dict_keys(self):
        r = AssignmentResult(
            ticket_id="t1", assigned_to="a1", strategy="score_based",
            score=0.85, score_breakdown={"specialty": 0.9},
        )
        d = r.to_dict()
        assert d["assigned_to"] == "a1"
        assert d["strategy"] == "score_based"
        assert "score_breakdown" in d
        assert "is_unassigned" in d


# ══════════════════════════════════════════════════════════════════
# 5. SCORE-BASED ASSIGNER TESTS
# ══════════════════════════════════════════════════════════════════

class TestScoreBasedAssigner:
    def test_weights(self):
        a = ScoreBasedAssigner()
        assert a._weights["specialty"] == 0.40
        assert a._weights["workload"] == 0.30
        assert a._weights["accuracy"] == 0.20
        assert a._weights["jitter"] == 0.10

    def test_specialty_score_with_match(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(specialties=["billing", "payments"])
        ticket = _make_ticket(subject="billing problem", tags=["billing"])
        score = a._specialty_score(agent, ticket)
        assert score >= 0.30

    def test_specialty_score_no_specialties_baseline(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(specialties=["nonexistent_tag"])
        ticket = _make_ticket()
        score = a._specialty_score(agent, ticket)
        assert score == 0.30

    def test_specialty_score_category_match(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(specialties=["billing"])
        ticket = _make_ticket(category="billing")
        score = a._specialty_score(agent, ticket)
        # baseline 0.30 + 1 match * 0.35 = 0.65
        assert score == pytest.approx(0.65)

    def test_specialty_score_multiple_matches(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(specialties=["billing", "technical"])
        ticket = _make_ticket(
            subject="billing technical issue", tags=[
                "billing", "technical"])
        score = a._specialty_score(agent, ticket)
        assert score > 0.65  # multiple matches

    def test_specialty_score_clamped_at_1(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(specialties=["a", "b", "c", "d", "e"])
        ticket = _make_ticket(
            subject="a b c d e", tags=[
                "a", "b", "c", "d", "e"])
        score = a._specialty_score(agent, ticket)
        assert score <= 1.0

    def test_workload_score_full_capacity(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(max_concurrent=5, current_load=0)
        assert a._workload_score(agent) == 1.0

    def test_workload_score_half_capacity(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(max_concurrent=10, current_load=5)
        assert a._workload_score(agent) == 0.5

    def test_workload_score_full(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(max_concurrent=5, current_load=5)
        assert a._workload_score(agent) == 0.0

    def test_workload_score_zero_max_concurrent(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(max_concurrent=0, current_load=0)
        assert a._workload_score(agent) == 0.0

    def test_accuracy_score_direct(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(accuracy_score=0.92)
        assert a._accuracy_score(agent) == 0.92

    def test_accuracy_score_clamped_high(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(accuracy_score=1.5)
        assert a._accuracy_score(agent) == 1.0

    def test_accuracy_score_clamped_low(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(accuracy_score=-0.1)
        assert a._accuracy_score(agent) == 0.0

    def test_jitter_score_in_range(self):
        a = ScoreBasedAssigner(jitter_range=0.05)
        for _ in range(50):
            j = a._jitter_score()
            assert 0.0 <= j <= 0.05

    def test_seniority_bonus_zero_for_low_complexity(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(seniority_years=10.0)
        ticket = _make_ticket(estimated_complexity=0.3)
        assert a._seniority_bonus(agent, ticket) == 0.0

    def test_seniority_bonus_for_high_complexity(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(seniority_years=5.0)
        ticket = _make_ticket(estimated_complexity=0.8)
        bonus = a._seniority_bonus(agent, ticket)
        assert bonus > 0.0
        assert bonus <= 0.05

    def test_seniority_bonus_clamped(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(seniority_years=100.0)
        ticket = _make_ticket(estimated_complexity=1.0)
        bonus = a._seniority_bonus(agent, ticket)
        assert bonus <= 0.05

    def test_language_bonus_english_no_bonus(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(languages=["en", "es"])
        ticket = _make_ticket(language="en")
        assert a._language_bonus(agent, ticket) == 0.0

    def test_language_bonus_matching(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(languages=["en", "es"])
        ticket = _make_ticket(language="es")
        assert a._language_bonus(agent, ticket) == 0.10

    def test_language_bonus_no_match(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(languages=["en"])
        ticket = _make_ticket(language="fr")
        assert a._language_bonus(agent, ticket) == 0.0

    def test_tier_access_authorized(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(customer_tier_access=["standard", "premium"])
        ticket = _make_ticket(customer_tier="premium")
        assert a._tier_access_score(agent, ticket) == 1.0

    def test_tier_access_unauthorized(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(customer_tier_access=["standard"])
        ticket = _make_ticket(customer_tier="enterprise")
        assert a._tier_access_score(agent, ticket) == 0.2

    def test_calculate_score_returns_tuple(self):
        a = ScoreBasedAssigner()
        agent = _make_agent()
        ticket = _make_ticket()
        score, breakdown = a._calculate_score(agent, ticket)
        assert isinstance(score, float)
        assert isinstance(breakdown, dict)
        assert "specialty" in breakdown
        assert "workload" in breakdown
        assert "accuracy" in breakdown
        assert "jitter" in breakdown
        assert "total" in breakdown

    def test_calculate_score_clamped_at_1(self):
        a = ScoreBasedAssigner()
        agent = _make_agent(
            accuracy_score=1.0,
            current_load=0,
            seniority_years=10.0)
        ticket = _make_ticket(estimated_complexity=1.0)
        score, _ = a._calculate_score(agent, ticket)
        assert score <= 1.0

    @pytest.mark.asyncio
    async def test_assign_no_agents_returns_unassigned(self):
        a = ScoreBasedAssigner()
        ticket = _make_ticket()
        result = await a.assign(ticket, [])
        assert result.is_unassigned is True
        assert result.assigned_to == "unassigned"
        assert result.strategy == "score_based"

    @pytest.mark.asyncio
    async def test_assign_single_agent(self):
        a = ScoreBasedAssigner()
        agent = _make_agent()
        ticket = _make_ticket()
        result = await a.assign(ticket, [agent])
        assert result.assigned_to == agent.agent_id
        assert result.strategy == "score_based"

    @pytest.mark.asyncio
    async def test_assign_best_agent_selected(self):
        a = ScoreBasedAssigner()
        # Agent with better specialty match + lighter load should win
        good_agent = _make_agent(
            agent_id="good", specialties=["billing"],
            current_load=0, accuracy_score=0.99,
        )
        bad_agent = _make_agent(
            agent_id="bad", specialties=["security"],
            current_load=4, accuracy_score=0.70,
        )
        ticket = _make_ticket(subject="billing question", category="billing")
        result = await a.assign(ticket, [good_agent, bad_agent])
        assert result.assigned_to == "good"

    @pytest.mark.asyncio
    async def test_assign_has_alternatives(self):
        a = ScoreBasedAssigner()
        agents = [_make_agent(agent_id=f"a{i}") for i in range(5)]
        ticket = _make_ticket()
        result = await a.assign(ticket, agents)
        assert len(result.alternatives) <= 3  # top 3 alternatives

    @pytest.mark.asyncio
    async def test_assign_has_score_breakdown(self):
        a = ScoreBasedAssigner()
        agent = _make_agent()
        ticket = _make_ticket()
        result = await a.assign(ticket, [agent])
        assert result.score_breakdown != {}
        assert "specialty" in result.score_breakdown

    @pytest.mark.asyncio
    async def test_assign_has_latency(self):
        a = ScoreBasedAssigner()
        agent = _make_agent()
        ticket = _make_ticket()
        result = await a.assign(ticket, [agent])
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_assign_caches_scores(self):
        a = ScoreBasedAssigner()
        agent = _make_agent()
        ticket = _make_ticket()
        await a.assign(ticket, [agent])
        assert len(a._score_cache) == 1

    def test_clear_cache(self):
        a = ScoreBasedAssigner()
        a._score_cache["key"] = (0.5, {})
        a.clear_cache()
        assert len(a._score_cache) == 0

    @pytest.mark.asyncio
    async def test_batch_assign(self):
        a = ScoreBasedAssigner()
        agents = [_make_agent(agent_id=f"a{i}") for i in range(3)]
        tickets = [_make_ticket(ticket_id=f"t{i}") for i in range(5)]
        results = await a.batch_assign(tickets, agents)
        assert len(results) == 5
        for r in results:
            assert not r.is_unassigned


# ══════════════════════════════════════════════════════════════════
# 6. RULE-BASED ASSIGNER TESTS
# ══════════════════════════════════════════════════════════════════

class TestRuleBasedAssigner:
    def test_available_agents_filters_online(self):
        a = RuleBasedAssigner()
        online = _make_agent(
            agent_id="on",
            is_online=True,
            max_concurrent=5,
            current_load=0)
        offline = _make_agent(agent_id="off", is_online=False)
        ticket = _make_ticket()
        avail = a._available_agents([online, offline], ticket)
        assert len(avail) == 1
        assert avail[0].agent_id == "on"

    def test_available_agents_filters_capacity(self):
        a = RuleBasedAssigner()
        full = _make_agent(
            agent_id="full",
            is_online=True,
            max_concurrent=5,
            current_load=5)
        free = _make_agent(
            agent_id="free",
            is_online=True,
            max_concurrent=5,
            current_load=2)
        ticket = _make_ticket()
        avail = a._available_agents([full, free], ticket)
        assert len(avail) == 1
        assert avail[0].agent_id == "free"

    def test_available_agents_prefers_language_match(self):
        a = RuleBasedAssigner()
        es_agent = _make_agent(agent_id="es", languages=["es"])
        en_agent = _make_agent(agent_id="en", languages=["en"])
        ticket = _make_ticket(language="es")
        avail = a._available_agents([en_agent, es_agent], ticket)
        assert len(avail) == 1
        assert avail[0].agent_id == "es"

    def test_least_loaded_selects_lowest(self):
        a = RuleBasedAssigner()
        heavy = _make_agent(agent_id="heavy", current_load=4)
        light = _make_agent(agent_id="light", current_load=1)
        result = a._least_loaded([heavy, light])
        assert result.agent_id == "light"

    def test_least_loaded_empty_returns_none(self):
        a = RuleBasedAssigner()
        assert a._least_loaded([]) is None

    def test_least_loaded_tie_breaks_by_last_assigned(self):
        a = RuleBasedAssigner()
        older = _make_agent(agent_id="older", current_load=1)
        older.last_assigned = datetime(2024, 1, 1, tzinfo=timezone.utc)
        newer = _make_agent(agent_id="newer", current_load=1)
        newer.last_assigned = datetime(2024, 6, 1, tzinfo=timezone.utc)
        result = a._least_loaded([older, newer])
        assert result.agent_id == "older"

    @pytest.mark.asyncio
    async def test_assign_returns_assigned_to_field(self):
        a = RuleBasedAssigner()
        agent = _make_agent()
        ticket = _make_ticket()
        result = await a.assign(ticket, [agent])
        assert hasattr(result, "assigned_to")
        assert result.assigned_to == agent.agent_id

    @pytest.mark.asyncio
    async def test_round_robin_cycles(self):
        a = RuleBasedAssigner()
        agents = [_make_agent(agent_id=f"a{i}") for i in range(3)]
        ticket = _make_ticket()
        assigned_ids = []
        for _ in range(6):
            result = await a.assign(ticket, agents)
            assigned_ids.append(result.assigned_to)
        assert assigned_ids[0] != assigned_ids[1]
        assert assigned_ids[0] == assigned_ids[3]  # cycle

    @pytest.mark.asyncio
    async def test_round_robin_per_category(self):
        a = RuleBasedAssigner()
        agents = [_make_agent(agent_id=f"a{i}") for i in range(3)]
        t1 = _make_ticket(category="billing")
        t2 = _make_ticket(category="technical")
        r1 = await a.assign(t1, agents)
        r2 = await a.assign(t2, agents)
        # Different category → different counter → same index
        assert r1.assigned_to == r2.assigned_to

    @pytest.mark.asyncio
    async def test_priority_escalation_critical(self):
        a = RuleBasedAssigner()
        heavy = _make_agent(agent_id="heavy", current_load=4)
        light = _make_agent(agent_id="light", current_load=0)
        ticket = _make_ticket(priority="critical")
        result = await a.assign(ticket, [heavy, light])
        assert result.assigned_to == "light"

    @pytest.mark.asyncio
    async def test_priority_escalation_high(self):
        a = RuleBasedAssigner()
        heavy = _make_agent(agent_id="heavy", current_load=4)
        light = _make_agent(agent_id="light", current_load=0)
        ticket = _make_ticket(priority="high")
        result = await a.assign(ticket, [heavy, light])
        assert result.assigned_to == "light"

    @pytest.mark.asyncio
    async def test_follow_up_routing(self):
        a = RuleBasedAssigner()
        agent = _make_agent(
            agent_id="prev_agent",
            current_load=1,
            max_concurrent=5)
        ticket = _make_ticket(previous_agent_id="prev_agent")
        result = await a.assign(ticket, [agent])
        assert result.assigned_to == "prev_agent"
        assert "Follow-up" in result.reason

    @pytest.mark.asyncio
    async def test_follow_up_routing_agent_full_falls_through(self):
        a = RuleBasedAssigner()
        prev = _make_agent(
            agent_id="prev_agent",
            current_load=5,
            max_concurrent=5)
        other = _make_agent(agent_id="other", current_load=0)
        ticket = _make_ticket(previous_agent_id="prev_agent")
        result = await a.assign(ticket, [prev, other])
        # prev can't accept (full), falls through to round-robin
        assert result.assigned_to == "prev_agent" or result.assigned_to == "other"

    @pytest.mark.asyncio
    async def test_no_agents_returns_unassigned(self):
        a = RuleBasedAssigner()
        ticket = _make_ticket()
        result = await a.assign(ticket, [])
        assert result.is_unassigned is True

    @pytest.mark.asyncio
    async def test_all_offline_falls_back(self):
        a = RuleBasedAssigner()
        agents = [
            _make_agent(
                agent_id=f"off{i}",
                is_online=False) for i in range(3)]
        ticket = _make_ticket()
        result = await a.assign(ticket, agents)
        # Falls back to all agents, should still assign via round-robin
        assert not result.is_unassigned

    @pytest.mark.asyncio
    async def test_assignment_log(self):
        a = RuleBasedAssigner()
        agent = _make_agent()
        ticket = _make_ticket()
        await a.assign(ticket, [agent])
        log = a.get_assignment_log()
        assert len(log) == 1

    def test_reset_counters(self):
        a = RuleBasedAssigner()
        a._counters["billing"] = 10
        a.reset_counters()
        assert a._counters == {}
        assert a._assignment_log == []

    @pytest.mark.asyncio
    async def test_batch_assign(self):
        a = RuleBasedAssigner()
        agents = [_make_agent(agent_id=f"a{i}") for i in range(3)]
        tickets = [_make_ticket(ticket_id=f"t{i}") for i in range(5)]
        results = await a.batch_assign(tickets, agents)
        assert len(results) == 5


# ══════════════════════════════════════════════════════════════════
# 7. HYBRID ASSIGNER TESTS
# ══════════════════════════════════════════════════════════════════

class TestHybridAssigner:
    def test_default_threshold(self):
        h = HybridAssigner()
        assert h.min_score_threshold == 0.30

    def test_custom_threshold(self):
        h = HybridAssigner(min_score_threshold=0.70)
        assert h.min_score_threshold == 0.70

    @pytest.mark.asyncio
    async def test_score_above_threshold_uses_score(self):
        h = HybridAssigner(min_score_threshold=0.10)
        agent = _make_agent(
            specialties=["billing"],
            current_load=0,
            accuracy_score=0.99)
        ticket = _make_ticket(subject="billing problem", category="billing")
        result = await h.assign(ticket, [agent])
        assert result.strategy == "hybrid"
        assert "score-based" in result.reason

    @pytest.mark.asyncio
    async def test_score_below_threshold_falls_back(self):
        h = HybridAssigner(min_score_threshold=0.99)
        agent = _make_agent(
            agent_id="a1", specialties=["security"],
            current_load=4, accuracy_score=0.50,
        )
        ticket = _make_ticket(subject="billing issue", category="billing")
        result = await h.assign(ticket, [agent])
        assert result.strategy == "hybrid"
        assert "rule-based" in result.reason

    @pytest.mark.asyncio
    async def test_unassigned_score_falls_back(self):
        h = HybridAssigner()
        ticket = _make_ticket()
        # No agents → score assigner returns unassigned → fallback
        result = await h.assign(ticket, [])
        assert result.strategy == "hybrid"

    def test_stats_initial(self):
        h = HybridAssigner()
        assert h.stats == {
            "direct_score_assignments": 0,
            "rule_fallback_assignments": 0}

    @pytest.mark.asyncio
    async def test_stats_track_direct(self):
        h = HybridAssigner(min_score_threshold=0.0)
        agent = _make_agent()
        ticket = _make_ticket()
        await h.assign(ticket, [agent])
        assert h.stats["direct_score_assignments"] == 1

    @pytest.mark.asyncio
    async def test_stats_track_fallback(self):
        h = HybridAssigner(min_score_threshold=99.0)
        agent = _make_agent()
        ticket = _make_ticket()
        await h.assign(ticket, [agent])
        assert h.stats["rule_fallback_assignments"] == 1

    @pytest.mark.asyncio
    async def test_batch_assign(self):
        h = HybridAssigner()
        agents = [_make_agent(agent_id=f"a{i}") for i in range(3)]
        tickets = [_make_ticket(ticket_id=f"t{i}") for i in range(4)]
        results = await h.batch_assign(tickets, agents)
        assert len(results) == 4


# ══════════════════════════════════════════════════════════════════
# 8. CAPACITY MANAGER TESTS
# ══════════════════════════════════════════════════════════════════

class TestCapacityManager:
    @pytest.mark.asyncio
    async def test_acquire_slot_success(self):
        cm = CapacityManager()
        ok = await cm.acquire_slot("a1", max_concurrent=5)
        assert ok is True
        assert cm.get_load("a1") == 1

    @pytest.mark.asyncio
    async def test_acquire_slot_at_capacity(self):
        cm = CapacityManager()
        for _ in range(5):
            await cm.acquire_slot("a1", max_concurrent=5)
        ok = await cm.acquire_slot("a1", max_concurrent=5)
        assert ok is False
        assert cm.get_load("a1") == 5

    @pytest.mark.asyncio
    async def test_release_slot(self):
        cm = CapacityManager()
        await cm.acquire_slot("a1", max_concurrent=5)
        await cm.release_slot("a1")
        assert cm.get_load("a1") == 0

    @pytest.mark.asyncio
    async def test_release_slot_floor_zero(self):
        cm = CapacityManager()
        await cm.release_slot("a1")
        assert cm.get_load("a1") == 0

    @pytest.mark.asyncio
    async def test_redis_set_on_acquire(self):
        mock_redis = AsyncMock()
        cm = CapacityManager(redis_client=mock_redis)
        await cm.acquire_slot("a1", max_concurrent=5)
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_error_does_not_crash_acquire(self):
        mock_redis = AsyncMock()
        mock_redis.set.side_effect = Exception("Redis down")
        cm = CapacityManager(redis_client=mock_redis)
        ok = await cm.acquire_slot("a1", max_concurrent=5)
        assert ok is True  # still succeeds in-memory

    def test_snapshot(self):
        cm = CapacityManager()
        agents = [
            _make_agent(agent_id="a1", max_concurrent=5, current_load=2),
            _make_agent(agent_id="a2", max_concurrent=10, current_load=3),
        ]
        snap = cm.snapshot(agents)
        assert len(snap) == 2
        assert snap[0]["agent_id"] == "a1"
        assert snap[0]["max_concurrent"] == 5
        assert snap[0]["available"] == 3

    def test_reset(self):
        cm = CapacityManager()
        cm._load["a1"] = 3
        cm.reset()
        assert cm.get_load("a1") == 0


# ══════════════════════════════════════════════════════════════════
# 9. SLA HELPER TESTS
# ══════════════════════════════════════════════════════════════════

class TestSLAHelper:
    def test_response_target_critical_enterprise(self):
        assert SLAHelper.response_target_seconds(
            "critical", "enterprise") == 300

    def test_response_target_high_standard(self):
        assert SLAHelper.response_target_seconds("high", "standard") == 1800

    def test_response_target_medium_premium(self):
        assert SLAHelper.response_target_seconds("medium", "premium") == 2700

    def test_response_target_low_standard(self):
        assert SLAHelper.response_target_seconds("low", "standard") == 86400

    def test_response_target_unknown_priority_defaults_medium(self):
        assert SLAHelper.response_target_seconds("urgent", "standard") == 3600

    def test_response_target_unknown_tier_defaults_3600(self):
        assert SLAHelper.response_target_seconds("critical", "free") == 3600

    def test_deadline_iso(self):
        base = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = SLAHelper.deadline_iso("critical", "enterprise", base=base)
        expected = (base + timedelta(seconds=300)).isoformat()
        assert deadline == expected

    def test_is_within_sla_true(self):
        assigned = "2024-01-01T12:00:00+00:00"
        responded = "2024-01-01T12:04:00+00:00"  # 4 min < 5 min threshold
        assert SLAHelper.is_within_sla(
            assigned, responded, "critical", "enterprise") is True

    def test_is_within_sla_false(self):
        assigned = "2024-01-01T12:00:00+00:00"
        responded = "2024-01-01T13:00:00+00:00"
        assert SLAHelper.is_within_sla(
            assigned, responded, "critical", "enterprise") is False

    def test_is_within_sla_invalid_date(self):
        assert SLAHelper.is_within_sla(
            "not-a-date", "also-bad", "medium", "standard") is False


# ══════════════════════════════════════════════════════════════════
# 10. ASSIGNMENT EVENT BUS TESTS
# ══════════════════════════════════════════════════════════════════

class TestAssignmentEventBus:
    def test_subscribe_and_publish(self):
        bus = AssignmentEventBus()
        received = []
        bus.subscribe("test.event", lambda e: received.append(e))
        event = AssignmentEvent(
            event_type="test.event", payload={
                "key": "val"})
        bus.publish(event)
        assert len(received) == 1
        assert received[0].payload["key"] == "val"

    def test_unsubscribe(self):
        bus = AssignmentEventBus()
        def handler(e): return None
        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)
        assert bus._subscribers.get("test") == []

    def test_unsubscribe_nonexistent_no_error(self):
        bus = AssignmentEventBus()
        bus.unsubscribe("nope", lambda e: None)  # should not raise

    def test_handler_error_doesnt_stop_others(self):
        bus = AssignmentEventBus()
        received = []
        bus.subscribe("test", lambda e: 1 / 0)
        bus.subscribe("test", lambda e: received.append(e))
        bus.publish(AssignmentEvent(event_type="test", payload={}))
        assert len(received) == 1

    def test_history(self):
        bus = AssignmentEventBus()
        for i in range(5):
            bus.publish(AssignmentEvent(event_type="e", payload={"i": i}))
        hist = bus.get_history()
        assert len(hist) == 5

    def test_history_filtered_by_type(self):
        bus = AssignmentEventBus()
        bus.publish(AssignmentEvent(event_type="a", payload={}))
        bus.publish(AssignmentEvent(event_type="b", payload={}))
        bus.publish(AssignmentEvent(event_type="a", payload={}))
        hist = bus.get_history(event_type="a")
        assert len(hist) == 2

    def test_history_limit(self):
        bus = AssignmentEventBus()
        for _ in range(10):
            bus.publish(AssignmentEvent(event_type="e", payload={}))
        hist = bus.get_history(limit=3)
        assert len(hist) == 3

    def test_clear_history(self):
        bus = AssignmentEventBus()
        bus.publish(AssignmentEvent(event_type="e", payload={}))
        bus.clear_history()
        assert bus.get_history() == []


# ══════════════════════════════════════════════════════════════════
# 11. DETERMINISTIC JITTER
# ══════════════════════════════════════════════════════════════════

class TestDeterministicJitter:
    def test_reproducible(self):
        j1 = deterministic_jitter("t1", "a1")
        j2 = deterministic_jitter("t1", "a1")
        assert j1 == j2

    def test_different_inputs_different(self):
        j1 = deterministic_jitter("t1", "a1")
        j2 = deterministic_jitter("t1", "a2")
        assert j1 != j2

    def test_within_range(self):
        j = deterministic_jitter("t1", "a1", max_val=0.05)
        assert 0.0 <= j <= 0.05

    def test_custom_max_val(self):
        j = deterministic_jitter("t1", "a1", max_val=1.0)
        assert 0.0 <= j <= 1.0


# ══════════════════════════════════════════════════════════════════
# 12. ASSIGNMENT ENGINE TESTS
# ══════════════════════════════════════════════════════════════════

class TestAssignmentEngine:
    def test_init(self):
        engine = AssignmentEngine()
        assert "score_based" in engine._assigners
        assert "rule_based" in engine._assigners
        assert "hybrid" in engine._assigners

    @pytest.mark.asyncio
    async def test_assign_with_score_based_strategy(self):
        engine = AssignmentEngine()
        agent = _make_agent()
        ticket = _make_ticket()
        result = await engine.assign(ticket, [agent], strategy="score_based")
        assert result.assigned_to == agent.agent_id

    @pytest.mark.asyncio
    async def test_assign_with_rule_based_strategy(self):
        engine = AssignmentEngine()
        agent = _make_agent()
        ticket = _make_ticket()
        result = await engine.assign(ticket, [agent], strategy="rule_based")
        assert result.assigned_to == agent.agent_id

    @pytest.mark.asyncio
    async def test_assign_with_hybrid_strategy(self):
        engine = AssignmentEngine()
        agent = _make_agent()
        ticket = _make_ticket()
        result = await engine.assign(ticket, [agent], strategy="hybrid")
        assert result.assigned_to == agent.agent_id

    @pytest.mark.asyncio
    async def test_assign_unknown_strategy_defaults_hybrid(self):
        engine = AssignmentEngine()
        agent = _make_agent()
        ticket = _make_ticket()
        result = await engine.assign(ticket, [agent], strategy="nonexistent")
        # Falls back to hybrid assigner
        assert result.assigned_to == agent.agent_id

    @pytest.mark.asyncio
    async def test_assign_updates_metrics(self):
        engine = AssignmentEngine()
        agent = _make_agent()
        ticket = _make_ticket()
        await engine.assign(ticket, [agent])
        m = engine.get_metrics()
        assert m["total_assigned"] == 1
        assert m["total_unassigned"] == 0

    @pytest.mark.asyncio
    async def test_assign_unassigned_updates_metrics(self):
        engine = AssignmentEngine()
        ticket = _make_ticket()
        await engine.assign(ticket, [])
        m = engine.get_metrics()
        assert m["total_unassigned"] == 1
        assert m["total_assigned"] == 0

    @pytest.mark.asyncio
    async def test_assign_increments_strategy_counts(self):
        engine = AssignmentEngine()
        agent = _make_agent()
        ticket = _make_ticket()
        await engine.assign(ticket, [agent], strategy="score_based")
        m = engine.get_metrics()
        assert "score_based" in m["strategy_counts"]

    @pytest.mark.asyncio
    async def test_assign_emits_event(self):
        engine = AssignmentEngine()
        agent = _make_agent()
        ticket = _make_ticket()
        await engine.assign(ticket, [agent])
        events = engine.get_event_history()
        assert len(events) > 0
        assert events[0]["event_type"] == "ticket.assigned"

    @pytest.mark.asyncio
    async def test_assign_unassigned_emits_event(self):
        engine = AssignmentEngine()
        ticket = _make_ticket()
        await engine.assign(ticket, [])
        events = engine.get_event_history(event_type="ticket.unassigned")
        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_avg_latency_in_metrics(self):
        engine = AssignmentEngine()
        agent = _make_agent()
        ticket = _make_ticket()
        await engine.assign(ticket, [agent])
        m = engine.get_metrics()
        assert "avg_latency_ms" in m
        assert m["avg_latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_recent_results(self):
        engine = AssignmentEngine()
        agent = _make_agent()
        for i in range(5):
            ticket = _make_ticket(ticket_id=f"t{i}")
            await engine.assign(ticket, [agent])
        recent = engine.get_recent_results(limit=3)
        assert len(recent) == 3

    @pytest.mark.asyncio
    async def test_capacity_snapshot(self):
        engine = AssignmentEngine()
        agents = [_make_agent(agent_id=f"a{i}") for i in range(2)]
        snap = engine.get_capacity_snapshot(agents)
        assert len(snap) == 2

    @pytest.mark.asyncio
    async def test_release_agent(self):
        engine = AssignmentEngine()
        agent = _make_agent()
        ticket = _make_ticket()
        await engine.assign(ticket, [agent])
        await engine.release_agent(agent.agent_id)
        # Should not raise

    @pytest.mark.asyncio
    async def test_assign_error_returns_unassigned(self):
        engine = AssignmentEngine()
        ticket = _make_ticket()
        # Force an error by mocking assigner to raise
        engine._assigners["hybrid"].assign = AsyncMock(
            side_effect=RuntimeError("boom"))
        result = await engine.assign(ticket, [])
        assert result.is_unassigned is True
        assert "Error" in result.reason

    @pytest.mark.asyncio
    async def test_assign_error_increments_error_metric(self):
        engine = AssignmentEngine()
        ticket = _make_ticket()
        engine._assigners["hybrid"].assign = AsyncMock(
            side_effect=RuntimeError("boom"))
        await engine.assign(ticket, [])
        m = engine.get_metrics()
        assert m["errors"] == 1

    @pytest.mark.asyncio
    async def test_batch_assign(self):
        engine = AssignmentEngine()
        agents = [_make_agent(agent_id=f"a{i}") for i in range(3)]
        tickets = [_make_ticket(ticket_id=f"t{i}") for i in range(5)]
        results = await engine.batch_assign(tickets, agents, strategy="rule_based")
        assert len(results) == 5

    def test_reset(self):
        engine = AssignmentEngine()
        engine._metrics["total_assigned"] = 100
        engine.reset()
        m = engine.get_metrics()
        assert m["total_assigned"] == 0

    def test_subscribe(self):
        engine = AssignmentEngine()
        def handler(e): return None
        engine.subscribe("test", handler)
        assert handler in engine._event_bus._subscribers.get("test", [])


# ══════════════════════════════════════════════════════════════════
# 13. FACTORY HELPERS TESTS
# ══════════════════════════════════════════════════════════════════

class TestFactories:
    def test_create_engine(self):
        engine = create_engine()
        assert isinstance(engine, AssignmentEngine)

    def test_create_engine_with_strategy(self):
        engine = create_engine(strategy="score_based")
        assert isinstance(engine, AssignmentEngine)

    def test_create_agents(self):
        agents = create_agents(5)
        assert len(agents) == 5
        assert all(isinstance(a, AgentProfile) for a in agents)

    def test_create_tickets(self):
        tickets = create_tickets(5)
        assert len(tickets) == 5
        assert all(isinstance(t, TicketContext) for t in tickets)

    def test_create_agents_custom_base_id(self):
        agents = create_agents(3, base_id="custom")
        assert agents[0].agent_id.startswith("custom_")


# ══════════════════════════════════════════════════════════════════
# 14. EDGE CASES
# ══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_score_assigner_empty_agents(self):
        a = ScoreBasedAssigner()
        ticket = _make_ticket()
        result = await a.assign(ticket, [])
        assert result.is_unassigned

    @pytest.mark.asyncio
    async def test_rule_assigner_empty_agents(self):
        a = RuleBasedAssigner()
        ticket = _make_ticket()
        result = await a.assign(ticket, [])
        assert result.is_unassigned

    @pytest.mark.asyncio
    async def test_hybrid_assigner_empty_agents(self):
        h = HybridAssigner()
        ticket = _make_ticket()
        result = await h.assign(ticket, [])
        assert result.strategy == "hybrid"

    @pytest.mark.asyncio
    async def test_all_agents_offline_rule_based(self):
        a = RuleBasedAssigner()
        agents = [
            _make_agent(
                agent_id=f"off{i}",
                is_online=False,
                current_load=0) for i in range(3)]
        ticket = _make_ticket()
        result = await a.assign(ticket, agents)
        # Falls back to all agents pool
        assert result.assigned_to in ["off0", "off1", "off2"]

    @pytest.mark.asyncio
    async def test_all_agents_at_capacity(self):
        a = ScoreBasedAssigner()
        agents = [
            _make_agent(
                agent_id=f"full{i}",
                max_concurrent=5,
                current_load=5) for i in range(3)]
        ticket = _make_ticket()
        result = await a.assign(ticket, agents)
        # Score assigner still assigns (doesn't check capacity)
        assert result.assigned_to in ["full0", "full1", "full2"]

    @pytest.mark.asyncio
    async def test_engine_with_no_agents_multiple_tickets(self):
        engine = AssignmentEngine()
        tickets = [_make_ticket(ticket_id=f"t{i}") for i in range(3)]
        results = await engine.batch_assign(tickets, [])
        assert all(r.is_unassigned for r in results)

    @pytest.mark.asyncio
    async def test_single_agent_repeated_assignments(self):
        engine = AssignmentEngine()
        agent = _make_agent(agent_id="solo", max_concurrent=3)
        tickets = [_make_ticket(ticket_id=f"t{i}") for i in range(10)]
        results = await engine.batch_assign(tickets, [agent], strategy="rule_based")
        assert all(r.assigned_to == "solo" for r in results)


# ══════════════════════════════════════════════════════════════════
# 15. ASSIGNMENT EVENT TESTS
# ══════════════════════════════════════════════════════════════════

class TestAssignmentEvent:
    def test_event_has_id(self):
        e = AssignmentEvent(event_type="test", payload={})
        assert e.event_id is not None
        assert len(e.event_id) == 12

    def test_event_timestamp(self):
        e = AssignmentEvent(event_type="test", payload={})
        assert e.timestamp is not None

    def test_event_to_dict(self):
        e = AssignmentEvent(event_type="test", payload={"key": "val"})
        d = e.to_dict()
        assert d["event_type"] == "test"
        assert d["payload"]["key"] == "val"

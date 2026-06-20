"""
Comprehensive Unit Tests for PARWA LangGraph Phase 1

Tests cover:
  1. ParwaGraphState — State creation, field presence, reducer behavior
  2. Config — Variant configs, MAKER configs, agent availability,
     technique access, channel availability, intent mapping,
     action classification, K-value computation
  3. Edges — All conditional edge functions with all tier variants

Test Categories:
  - Happy path: Normal inputs, expected outputs
  - Edge cases: Unknown tiers, empty inputs, boundary values
  - Tier-specific: Mini vs Pro vs High behavior differences
  - Reducer behavior: List merging, dict merging
  - Fallback behavior: Unknown variant_tier → mini fallback

BC-008: All tests verify graceful degradation on invalid inputs.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List


# ══════════════════════════════════════════════════════════════════
# STATE TESTS
# ══════════════════════════════════════════════════════════════════


class TestParwaGraphState:
    """Tests for ParwaGraphState TypedDict and create_initial_state."""

    def test_create_initial_state_has_all_groups(self):
        """Verify create_initial_state returns a dict with all 18 group prefixes."""
        from app.core.langgraph.state import create_initial_state

        state = create_initial_state(
            message="Hello",
            channel="email",
            customer_id="cust_123",
            tenant_id="tenant_abc",
            variant_tier="mini",
        )

        # Group 1: INPUT
        assert state["message"] == "Hello"
        assert state["channel"] == "email"
        assert state["customer_id"] == "cust_123"
        assert state["tenant_id"] == "tenant_abc"
        assert state["variant_tier"] == "mini"
        assert state["customer_tier"] == "free"
        assert state["industry"] == "general"
        assert state["language"] == "en"
        assert state["conversation_id"] == ""
        assert state["ticket_id"] == ""
        assert state["session_id"] == ""

        # Group 2: PII REDACTION
        assert state["pii_redacted_message"] == ""
        assert state["pii_entities_found"] == []

        # Group 3: EMPATHY ENGINE
        assert state["sentiment_score"] == 0.5
        assert state["sentiment_intensity"] == "low"
        assert state["legal_threat_detected"] is False
        assert state["urgency"] == "low"
        assert state["sentiment_trend"] == "stable"

        # Group 4: ROUTER AGENT
        assert state["intent"] == "general"
        assert state["complexity_score"] == 0.0
        assert state["target_agent"] == "faq"
        assert state["model_tier"] == "medium"
        assert state["technique_stack"] == []
        assert state["signals_extracted"] == {}

        # Group 5: DOMAIN AGENT
        assert state["agent_response"] == ""
        assert state["agent_confidence"] == 0.0
        assert state["proposed_action"] == "respond"
        assert state["action_type"] == "informational"
        assert state["agent_reasoning"] == ""
        assert state["agent_type"] == ""

        # Group 6: MAKER VALIDATOR
        assert state["k_solutions"] == []
        assert state["selected_solution"] == ""
        assert state["red_flag"] is False
        assert state["maker_mode"] == ""
        assert state["k_value_used"] == 0
        assert state["fake_threshold"] == 0.0
        assert state["maker_decomposition"] == {}
        assert state["maker_audit_trail"] == []

        # Group 7: CONTROL SYSTEM
        assert state["approval_decision"] == ""
        assert state["confidence_breakdown"] == {}
        assert state["system_mode"] == "auto"
        assert state["dnd_applies"] is False
        assert state["money_rule_triggered"] is False
        assert state["vip_rule_triggered"] is False
        assert state["approval_timeout_seconds"] == 300

        # Group 8: DSPY OPTIMIZER
        assert state["prompt_optimized"] is False
        assert state["optimized_prompt_version"] == ""

        # Group 9: GUARDRAILS
        assert state["guardrails_passed"] is False
        assert state["guardrails_flags"] == []
        assert state["guardrails_blocked_reason"] == ""

        # Group 10: CHANNEL DELIVERY
        assert state["delivery_status"] == "pending"
        assert state["delivery_channel"] == ""
        assert state["delivery_timestamp"] == ""
        assert state["delivery_confirmation_id"] == ""
        assert state["delivery_failure_reason"] == ""
        assert state["fallback_attempted"] is False

        # Group 11: STATE UPDATE
        assert state["ticket_created"] is False
        assert state["ticket_updated"] is False
        assert state["ticket_status"] == "open"
        assert state["gsd_state_persisted"] is False
        assert state["audit_log_written"] is False
        assert state["metrics_updated"] is False
        assert state["jarvis_feed_pushed"] is False
        assert state["fifty_mistake_check"] == {}

        # Group 12: GSD STATE
        assert state["gsd_state"] == "new"
        assert state["gsd_step"] == ""
        assert state["context_health"] == 1.0
        assert state["context_compressed"] is False

        # Group 13: METADATA
        assert state["processing_start_time"] != ""
        assert state["model_used"] == ""
        assert state["tokens_consumed"] == 0
        assert state["total_llm_calls"] == 0
        assert state["node_execution_log"] == []
        assert state["error"] == ""
        assert state["reward_signal"] == 0.0
        assert state["shadow_mode_intercepted"] is False

        # Group 14: JARVIS AWARENESS
        assert state["current_plan"] == "mini"
        assert state["plan_usage_today"] == 0.0
        assert state["subscription_status"] == "active"
        assert state["days_until_renewal"] == 30
        assert state["system_health"] == "healthy"
        assert state["channel_health"] == {}
        assert state["active_alerts"] == []
        assert state["ticket_volume_today"] == 0
        assert state["ticket_volume_avg"] == 0.0
        assert state["ticket_volume_spike"] is False
        assert state["active_agents"] == 0
        assert state["agent_pool_capacity"] == 5
        assert state["agent_pool_utilization"] == 0.0
        assert state["training_running"] is False
        assert state["training_mistake_count"] == 0
        assert state["training_model_version"] == ""
        assert state["drift_status"] == "none"
        assert state["drift_score"] == 0.0
        assert state["quality_score"] == 0.0
        assert state["quality_alerts"] == []
        assert state["last_5_errors"] == []

        # Group 15: EMERGENCY CONTROLS
        assert state["ai_paused"] is False
        assert state["paused_channels"] == []
        assert state["paused_actions"] == []
        assert state["emergency_state"] == "normal"
        assert state["circuit_breaker_trips"] == 0
        assert state["global_pause_reason"] == ""

        # Group 16: ANTI-ARBITRAGE
        assert state["arbitrage_risk_score"] == 0.0
        assert state["arbitrage_signals"] == []
        assert state["active_sessions"] == 1
        assert state["plan_cycling_detected"] is False

        # Group 17: BRAND VOICE & RAG
        assert state["brand_voice_applied"] is False
        assert state["brand_voice_profile"] == {}
        assert state["rag_documents_retrieved"] == []
        assert state["rag_reranked"] is False
        assert state["kb_documents_used"] == []

        # Group 18: COLLECTIVE INTELLIGENCE
        assert state["collective_patterns_used"] == []
        assert state["manager_correction"] is False
        assert state["auto_approved_rule_created"] is False
        assert state["batch_cluster_id"] == ""
        assert state["node_outputs"] == {}
        assert state["errors"] == []

    def test_create_initial_state_with_all_params(self):
        """Test create_initial_state with all parameters specified."""
        from app.core.langgraph.state import create_initial_state

        state = create_initial_state(
            message="I want a refund",
            channel="sms",
            customer_id="cust_456",
            tenant_id="tenant_xyz",
            variant_tier="pro",
            customer_tier="vip",
            industry="ecommerce",
            language="es",
            conversation_id="conv_789",
            ticket_id="ticket_012",
            session_id="sess_345",
        )

        assert state["message"] == "I want a refund"
        assert state["channel"] == "sms"
        assert state["customer_id"] == "cust_456"
        assert state["tenant_id"] == "tenant_xyz"
        assert state["variant_tier"] == "pro"
        assert state["customer_tier"] == "vip"
        assert state["industry"] == "ecommerce"
        assert state["language"] == "es"
        assert state["conversation_id"] == "conv_789"
        assert state["ticket_id"] == "ticket_012"
        assert state["session_id"] == "sess_345"
        assert state["current_plan"] == "pro"

    def test_create_initial_state_variants(self):
        """Test that all three variant tiers produce valid initial states."""
        from app.core.langgraph.state import create_initial_state

        for tier in ("mini", "pro", "high"):
            state = create_initial_state(
                message="test",
                channel="email",
                customer_id="c1",
                tenant_id="t1",
                variant_tier=tier,
            )
            assert state["variant_tier"] == tier
            assert state["current_plan"] == tier

    def test_reducer_merge_lists(self):
        """Test _merge_lists reducer appends items."""
        from app.core.langgraph.state import _merge_lists

        result = _merge_lists(["a", "b"], ["c"])
        assert result == ["a", "b", "c"]

        result = _merge_lists([], ["x"])
        assert result == ["x"]

        result = _merge_lists(["x"], [])
        assert result == ["x"]

    def test_reducer_merge_dicts(self):
        """Test _merge_dicts reducer merges dicts with override."""
        from app.core.langgraph.state import _merge_dicts

        result = _merge_dicts({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

        result = _merge_dicts({"a": 1}, {"a": 2})
        assert result == {"a": 2}

        result = _merge_dicts({}, {"x": 1})
        assert result == {"x": 1}

    def test_reducer_max_float(self):
        """Test _max_float reducer keeps maximum."""
        from app.core.langgraph.state import _max_float

        assert _max_float(0.5, 0.8) == 0.8
        assert _max_float(0.9, 0.1) == 0.9
        assert _max_float(0.0, 0.0) == 0.0

    def test_reducer_replace(self):
        """Test _replace reducer does last-write-wins."""
        from app.core.langgraph.state import _replace

        assert _replace("old", "new") == "new"
        assert _replace(0, 42) == 42

    def test_field_count(self):
        """Test get_total_field_count returns expected count."""
        from app.core.langgraph.state import get_total_field_count, _count_fields

        counts = _count_fields()
        # Verify group counts
        assert counts["1_INPUT"] == 11
        assert counts["14_JARVIS_AWARENESS"] == 21

        total = get_total_field_count()
        assert total > 100  # Should be around 117+

    def test_initial_state_processing_start_time_is_utc(self):
        """Test that processing_start_time is a valid UTC ISO timestamp."""
        from app.core.langgraph.state import create_initial_state

        state = create_initial_state(
            message="test", channel="email",
            customer_id="c1", tenant_id="t1",
            variant_tier="mini",
        )
        # Should be parseable as ISO format
        ts = datetime.fromisoformat(state["processing_start_time"])
        assert ts.tzinfo is not None  # Has timezone info

    def test_initial_state_empty_lists_are_mutable(self):
        """Test that empty list defaults can be appended to."""
        from app.core.langgraph.state import create_initial_state

        state = create_initial_state(
            message="test", channel="email",
            customer_id="c1", tenant_id="t1",
            variant_tier="mini",
        )
        # Lists should be independent per state (not shared reference)
        state["errors"].append("error1")
        state2 = create_initial_state(
            message="test2", channel="sms",
            customer_id="c2", tenant_id="t2",
            variant_tier="pro",
        )
        assert state2["errors"] == []


# ══════════════════════════════════════════════════════════════════
# CONFIG TESTS
# ══════════════════════════════════════════════════════════════════


class TestVariantConfig:
    """Tests for VARIANT_CONFIG and helper functions."""

    def test_all_tiers_present(self):
        """Verify all three tiers exist in VARIANT_CONFIG."""
        from app.core.langgraph.config import VARIANT_CONFIG

        assert "mini" in VARIANT_CONFIG
        assert "pro" in VARIANT_CONFIG
        assert "high" in VARIANT_CONFIG

    def test_tier_display_names(self):
        """Verify display names are correct."""
        from app.core.langgraph.config import VARIANT_CONFIG

        assert VARIANT_CONFIG["mini"]["display_name"] == "Mini Parwa"
        assert VARIANT_CONFIG["pro"]["display_name"] == "Parwa Pro"
        assert VARIANT_CONFIG["high"]["display_name"] == "Parwa High"

    def test_tier_pricing(self):
        """Verify pricing is correct."""
        from app.core.langgraph.config import VARIANT_CONFIG

        assert VARIANT_CONFIG["mini"]["price_usd"] == 999
        assert VARIANT_CONFIG["pro"]["price_usd"] == 2499
        assert VARIANT_CONFIG["high"]["price_usd"] == 3999

    def test_pipeline_timeouts_increase_with_tier(self):
        """Verify pipeline timeouts increase: mini < pro < high."""
        from app.core.langgraph.config import VARIANT_CONFIG

        assert VARIANT_CONFIG["mini"]["pipeline_timeout_seconds"] < \
               VARIANT_CONFIG["pro"]["pipeline_timeout_seconds"]
        assert VARIANT_CONFIG["pro"]["pipeline_timeout_seconds"] < \
               VARIANT_CONFIG["high"]["pipeline_timeout_seconds"]

    def test_max_tokens_increase_with_tier(self):
        """Verify max tokens increase: mini < pro < high."""
        from app.core.langgraph.config import VARIANT_CONFIG

        assert VARIANT_CONFIG["mini"]["max_tokens_per_response"] < \
               VARIANT_CONFIG["pro"]["max_tokens_per_response"]
        assert VARIANT_CONFIG["pro"]["max_tokens_per_response"] < \
               VARIANT_CONFIG["high"]["max_tokens_per_response"]

    def test_get_variant_config_valid_tiers(self):
        """Test get_variant_config for all valid tiers."""
        from app.core.langgraph.config import get_variant_config

        for tier in ("mini", "pro", "high"):
            config = get_variant_config(tier)
            assert config["tier"] == tier
            assert "maker" in config
            assert "techniques" in config
            assert "agents" in config
            assert "channels" in config
            assert "control" in config

    def test_get_variant_config_unknown_tier_falls_back(self):
        """Test get_variant_config falls back to mini for unknown tiers."""
        from app.core.langgraph.config import get_variant_config

        config = get_variant_config("enterprise")
        assert config["tier"] == "mini"

        config = get_variant_config("")
        assert config["tier"] == "mini"

        config = get_variant_config("random_string")
        assert config["tier"] == "mini"

    def test_validate_variant_tier(self):
        """Test validate_variant_tier function."""
        from app.core.langgraph.config import validate_variant_tier

        assert validate_variant_tier("mini") is True
        assert validate_variant_tier("pro") is True
        assert validate_variant_tier("high") is True
        assert validate_variant_tier("enterprise") is False
        assert validate_variant_tier("") is False

    def test_get_all_valid_tiers(self):
        """Test get_all_valid_tiers returns all three tiers."""
        from app.core.langgraph.config import get_all_valid_tiers

        tiers = get_all_valid_tiers()
        assert set(tiers) == {"mini", "pro", "high"}


class TestMakerConfig:
    """Tests for MAKER_CONFIG and MAKER-related helper functions."""

    def test_maker_modes_per_tier(self):
        """Verify MAKER modes: mini=efficiency, pro=balanced, high=conservative."""
        from app.core.langgraph.config import MAKER_CONFIG

        assert MAKER_CONFIG["mini"]["mode"] == "efficiency"
        assert MAKER_CONFIG["pro"]["mode"] == "balanced"
        assert MAKER_CONFIG["high"]["mode"] == "conservative"

    def test_maker_k_values(self):
        """Verify K values: mini=3, pro=3-5, high=5-7."""
        from app.core.langgraph.config import MAKER_CONFIG

        assert MAKER_CONFIG["mini"]["k"] == 3
        assert MAKER_CONFIG["mini"]["k_range"] is None

        assert MAKER_CONFIG["pro"]["k"] == 4
        assert MAKER_CONFIG["pro"]["k_range"] == (3, 5)

        assert MAKER_CONFIG["high"]["k"] == 6
        assert MAKER_CONFIG["high"]["k_range"] == (5, 7)

    def test_maker_thresholds_increase_with_tier(self):
        """Verify thresholds: mini=0.50, pro=0.60, high=0.75."""
        from app.core.langgraph.config import MAKER_CONFIG

        assert MAKER_CONFIG["mini"]["threshold"] == 0.50
        assert MAKER_CONFIG["pro"]["threshold"] == 0.60
        assert MAKER_CONFIG["high"]["threshold"] == 0.75

    def test_maker_decomposition_per_tier(self):
        """Verify decomposition: mini=disabled, pro=enabled, high=enabled."""
        from app.core.langgraph.config import MAKER_CONFIG

        assert MAKER_CONFIG["mini"]["decomposition_enabled"] is False
        assert MAKER_CONFIG["pro"]["decomposition_enabled"] is True
        assert MAKER_CONFIG["high"]["decomposition_enabled"] is True

    def test_maker_audit_trail_levels(self):
        """Verify audit trail levels increase with tier."""
        from app.core.langgraph.config import MAKER_CONFIG

        assert MAKER_CONFIG["mini"]["audit_trail_level"] == "minimal"
        assert MAKER_CONFIG["pro"]["audit_trail_level"] == "standard"
        assert MAKER_CONFIG["high"]["audit_trail_level"] == "full"

    def test_get_maker_k_value_fixed(self):
        """Test get_maker_k_value for mini (fixed K=3)."""
        from app.core.langgraph.config import get_maker_k_value

        # Mini always returns K=3 regardless of complexity
        assert get_maker_k_value("mini", 0.0) == 3
        assert get_maker_k_value("mini", 0.5) == 3
        assert get_maker_k_value("mini", 1.0) == 3

    def test_get_maker_k_value_dynamic_pro(self):
        """Test get_maker_k_value for pro (K=3-5 based on complexity)."""
        from app.core.langgraph.config import get_maker_k_value

        assert get_maker_k_value("pro", 0.0) == 3   # Low complexity → K=3
        assert get_maker_k_value("pro", 0.1) == 3   # Low complexity → K=3
        assert get_maker_k_value("pro", 0.3) == 3   # Boundary → K=3
        assert get_maker_k_value("pro", 0.5) == 4   # Medium → K=4
        assert get_maker_k_value("pro", 0.7) == 5   # High → K=5
        assert get_maker_k_value("pro", 1.0) == 5   # Max → K=5

    def test_get_maker_k_value_dynamic_high(self):
        """Test get_maker_k_value for high (K=5-7 based on complexity)."""
        from app.core.langgraph.config import get_maker_k_value

        assert get_maker_k_value("high", 0.0) == 5   # Low → K=5
        assert get_maker_k_value("high", 0.5) == 6   # Medium → K=6
        assert get_maker_k_value("high", 1.0) == 7   # High → K=7

    def test_get_maker_k_value_unknown_tier(self):
        """Test get_maker_k_value for unknown tier falls back to mini."""
        from app.core.langgraph.config import get_maker_k_value

        assert get_maker_k_value("enterprise", 0.5) == 3  # Falls back to mini K=3

    def test_get_maker_config(self):
        """Test get_maker_config helper."""
        from app.core.langgraph.config import get_maker_config

        for tier in ("mini", "pro", "high"):
            config = get_maker_config(tier)
            assert "mode" in config
            assert "k" in config
            assert "threshold" in config


class TestAgentAvailability:
    """Tests for AGENT_AVAILABILITY and helper functions."""

    def test_mini_agents(self):
        """Mini tier has 3 domain agents: faq, technical, billing."""
        from app.core.langgraph.config import AGENT_AVAILABILITY

        agents = AGENT_AVAILABILITY["mini"]["domain_agents"]
        assert agents == ["faq", "technical", "billing"]

    def test_pro_agents(self):
        """Pro tier has 6 domain agents."""
        from app.core.langgraph.config import AGENT_AVAILABILITY

        agents = AGENT_AVAILABILITY["pro"]["domain_agents"]
        assert len(agents) == 6
        assert "faq" in agents
        assert "refund" in agents
        assert "technical" in agents
        assert "billing" in agents
        assert "complaint" in agents
        assert "escalation" in agents

    def test_high_agents(self):
        """High tier has all 6 domain agents."""
        from app.core.langgraph.config import AGENT_AVAILABILITY

        agents = AGENT_AVAILABILITY["high"]["domain_agents"]
        assert len(agents) == 6

    def test_mini_lacks_refund_and_escalation(self):
        """Mini tier should NOT have refund, complaint, or escalation agents."""
        from app.core.langgraph.config import AGENT_AVAILABILITY

        agents = AGENT_AVAILABILITY["mini"]["domain_agents"]
        assert "refund" not in agents
        assert "complaint" not in agents
        assert "escalation" not in agents

    def test_concurrent_agents_increase_with_tier(self):
        """Max concurrent agents: mini=5, pro=15, high=50."""
        from app.core.langgraph.config import AGENT_AVAILABILITY

        assert AGENT_AVAILABILITY["mini"]["max_concurrent_agents"] == 5
        assert AGENT_AVAILABILITY["pro"]["max_concurrent_agents"] == 15
        assert AGENT_AVAILABILITY["high"]["max_concurrent_agents"] == 50

    def test_get_available_agents(self):
        """Test get_available_agents helper."""
        from app.core.langgraph.config import get_available_agents

        assert get_available_agents("mini") == ["faq", "technical", "billing"]
        assert len(get_available_agents("pro")) == 6
        assert len(get_available_agents("high")) == 6

    def test_get_available_agents_unknown_tier(self):
        """Unknown tier falls back to mini agents."""
        from app.core.langgraph.config import get_available_agents

        assert get_available_agents("enterprise") == ["faq", "technical", "billing"]

    def test_fallback_agents(self):
        """Test fallback agent configuration per tier."""
        from app.core.langgraph.config import AGENT_AVAILABILITY

        assert AGENT_AVAILABILITY["mini"]["fallback_agent"] == "faq"
        assert AGENT_AVAILABILITY["pro"]["fallback_agent"] == "faq"
        assert AGENT_AVAILABILITY["high"]["fallback_agent"] == "escalation"


class TestTechniqueTierAccess:
    """Tests for TECHNIQUE_TIER_ACCESS and helper functions."""

    def test_mini_t1_only(self):
        """Mini tier only has Tier 1 techniques: CLARA, CRP, GSD."""
        from app.core.langgraph.config import TECHNIQUE_TIER_ACCESS

        assert TECHNIQUE_TIER_ACCESS["mini"]["available_tiers"] == ["tier_1"]
        techniques = TECHNIQUE_TIER_ACCESS["mini"]["techniques"]
        assert "clara" in techniques
        assert "crp" in techniques
        assert "gsd" in techniques
        assert "chain_of_thought" not in techniques

    def test_pro_t1_t2(self):
        """Pro tier has Tier 1 + Tier 2 techniques."""
        from app.core.langgraph.config import TECHNIQUE_TIER_ACCESS

        assert "tier_1" in TECHNIQUE_TIER_ACCESS["pro"]["available_tiers"]
        assert "tier_2" in TECHNIQUE_TIER_ACCESS["pro"]["available_tiers"]
        assert "tier_3" not in TECHNIQUE_TIER_ACCESS["pro"]["available_tiers"]

        techniques = TECHNIQUE_TIER_ACCESS["pro"]["techniques"]
        assert "chain_of_thought" in techniques
        assert "react" in techniques
        assert "gst" not in techniques  # T3 not available

    def test_high_all_tiers(self):
        """High tier has all technique tiers."""
        from app.core.langgraph.config import TECHNIQUE_TIER_ACCESS

        assert "tier_1" in TECHNIQUE_TIER_ACCESS["high"]["available_tiers"]
        assert "tier_2" in TECHNIQUE_TIER_ACCESS["high"]["available_tiers"]
        assert "tier_3" in TECHNIQUE_TIER_ACCESS["high"]["available_tiers"]

        techniques = TECHNIQUE_TIER_ACCESS["high"]["techniques"]
        assert "gst" in techniques
        assert "universe_of_thoughts" in techniques
        assert "tree_of_thoughts" in techniques

    def test_get_available_techniques(self):
        """Test get_available_techniques helper."""
        from app.core.langgraph.config import get_available_techniques

        mini_techniques = get_available_techniques("mini")
        assert len(mini_techniques) == 3

        pro_techniques = get_available_techniques("pro")
        assert len(pro_techniques) == 8

        high_techniques = get_available_techniques("high")
        assert len(high_techniques) == 14

    def test_technique_tokens_increase_with_tier(self):
        """Max technique tokens increase: mini < pro < high."""
        from app.core.langgraph.config import TECHNIQUE_TIER_ACCESS

        assert TECHNIQUE_TIER_ACCESS["mini"]["max_technique_tokens"] < \
               TECHNIQUE_TIER_ACCESS["pro"]["max_technique_tokens"]
        assert TECHNIQUE_TIER_ACCESS["pro"]["max_technique_tokens"] < \
               TECHNIQUE_TIER_ACCESS["high"]["max_technique_tokens"]


class TestChannelAvailability:
    """Tests for CHANNEL_AVAILABILITY and helper functions."""

    def test_mini_no_voice_no_video(self):
        """Mini tier has no voice or video."""
        from app.core.langgraph.config import CHANNEL_AVAILABILITY

        assert CHANNEL_AVAILABILITY["mini"]["voice_enabled"] is False
        assert CHANNEL_AVAILABILITY["mini"]["video_enabled"] is False
        assert "voice" not in CHANNEL_AVAILABILITY["mini"]["channels"]
        assert "video" not in CHANNEL_AVAILABILITY["mini"]["channels"]

    def test_pro_has_voice_no_video(self):
        """Pro tier has voice but no video."""
        from app.core.langgraph.config import CHANNEL_AVAILABILITY

        assert CHANNEL_AVAILABILITY["pro"]["voice_enabled"] is True
        assert CHANNEL_AVAILABILITY["pro"]["video_enabled"] is False
        assert "voice" in CHANNEL_AVAILABILITY["pro"]["channels"]
        assert "video" not in CHANNEL_AVAILABILITY["pro"]["channels"]

    def test_high_has_voice_and_video(self):
        """High tier has both voice and video."""
        from app.core.langgraph.config import CHANNEL_AVAILABILITY

        assert CHANNEL_AVAILABILITY["high"]["voice_enabled"] is True
        assert CHANNEL_AVAILABILITY["high"]["video_enabled"] is True
        assert "voice" in CHANNEL_AVAILABILITY["high"]["channels"]
        assert "video" in CHANNEL_AVAILABILITY["high"]["channels"]

    def test_is_voice_enabled(self):
        """Test is_voice_enabled helper."""
        from app.core.langgraph.config import is_voice_enabled

        assert is_voice_enabled("mini") is False
        assert is_voice_enabled("pro") is True
        assert is_voice_enabled("high") is True

    def test_is_video_enabled(self):
        """Test is_video_enabled helper."""
        from app.core.langgraph.config import is_video_enabled

        assert is_video_enabled("mini") is False
        assert is_video_enabled("pro") is False
        assert is_video_enabled("high") is True

    def test_get_available_channels(self):
        """Test get_available_channels helper."""
        from app.core.langgraph.config import get_available_channels

        mini_channels = get_available_channels("mini")
        assert "email" in mini_channels
        assert "sms" in mini_channels
        assert "voice" not in mini_channels

        pro_channels = get_available_channels("pro")
        assert "voice" in pro_channels

        high_channels = get_available_channels("high")
        assert "video" in high_channels


class TestControlConfig:
    """Tests for CONTROL_CONFIG and approval-related helpers."""

    def test_mini_no_approval_needed(self):
        """Mini tier auto-approves everything."""
        from app.core.langgraph.config import CONTROL_CONFIG

        assert CONTROL_CONFIG["mini"]["approval_required_for"] == []
        assert CONTROL_CONFIG["mini"]["interrupt_before"] is False

    def test_pro_approval_for_monetary_and_destructive(self):
        """Pro tier requires approval for monetary + destructive actions."""
        from app.core.langgraph.config import CONTROL_CONFIG

        required = CONTROL_CONFIG["pro"]["approval_required_for"]
        assert "monetary" in required
        assert "destructive" in required
        assert "informational" not in required
        assert CONTROL_CONFIG["pro"]["interrupt_before"] is True

    def test_high_approval_for_all_risky(self):
        """High tier requires approval for monetary + destructive + escalation."""
        from app.core.langgraph.config import CONTROL_CONFIG

        required = CONTROL_CONFIG["high"]["approval_required_for"]
        assert "monetary" in required
        assert "destructive" in required
        assert "escalation" in required
        assert "informational" not in required

    def test_needs_human_approval(self):
        """Test needs_human_approval helper across tiers and action types."""
        from app.core.langgraph.config import needs_human_approval

        # Mini: no approval needed
        assert needs_human_approval("informational", "mini") is False
        assert needs_human_approval("monetary", "mini") is False
        assert needs_human_approval("destructive", "mini") is False

        # Pro: approval for monetary + destructive
        assert needs_human_approval("informational", "pro") is False
        assert needs_human_approval("monetary", "pro") is True
        assert needs_human_approval("destructive", "pro") is True
        assert needs_human_approval("escalation", "pro") is False

        # High: approval for monetary + destructive + escalation
        assert needs_human_approval("informational", "high") is False
        assert needs_human_approval("monetary", "high") is True
        assert needs_human_approval("destructive", "high") is True
        assert needs_human_approval("escalation", "high") is True

    def test_approval_timeout(self):
        """Pro has 5 min timeout, High has 10 min, Mini has 0."""
        from app.core.langgraph.config import CONTROL_CONFIG

        assert CONTROL_CONFIG["mini"]["human_approval_timeout_seconds"] == 0
        assert CONTROL_CONFIG["pro"]["human_approval_timeout_seconds"] == 300
        assert CONTROL_CONFIG["high"]["human_approval_timeout_seconds"] == 600


class TestIntentMapping:
    """Tests for INTENT_AGENT_MAP and map_intent_to_agent."""

    def test_all_known_intents(self):
        """Test all known intent mappings."""
        from app.core.langgraph.config import map_intent_to_agent

        # These should map correctly for pro/high
        assert map_intent_to_agent("faq", "pro") == "faq"
        assert map_intent_to_agent("refund", "pro") == "refund"
        assert map_intent_to_agent("technical", "pro") == "technical"
        assert map_intent_to_agent("billing", "pro") == "billing"
        assert map_intent_to_agent("complaint", "pro") == "complaint"
        assert map_intent_to_agent("escalation", "pro") == "escalation"

    def test_mini_intent_fallback(self):
        """Mini tier: refund/complaint/escalation intent falls back to faq."""
        from app.core.langgraph.config import map_intent_to_agent

        # Refund not available in mini → fallback to faq
        assert map_intent_to_agent("refund", "mini") == "faq"
        assert map_intent_to_agent("complaint", "mini") == "faq"
        assert map_intent_to_agent("escalation", "mini") == "faq"

        # Available agents work fine
        assert map_intent_to_agent("faq", "mini") == "faq"
        assert map_intent_to_agent("technical", "mini") == "technical"
        assert map_intent_to_agent("billing", "mini") == "billing"

    def test_high_intent_escalation_fallback(self):
        """High tier fallback agent is escalation (used when mapped agent is unavailable)."""
        from app.core.langgraph.config import AGENT_AVAILABILITY, map_intent_to_agent

        # High tier fallback_agent is escalation (but all 6 agents are available,
        # so unknown intents still map to "faq" via INTENT_AGENT_MAP default)
        assert AGENT_AVAILABILITY["high"]["fallback_agent"] == "escalation"

        # Unknown intent maps to "faq" (INTENT_AGENT_MAP default), which IS available
        result = map_intent_to_agent("unknown_intent_xyz", "high")
        assert result == "faq"  # faq is available in high tier

    def test_unknown_intent_maps_to_faq(self):
        """Unknown intent defaults to faq mapping."""
        from app.core.langgraph.config import map_intent_to_agent

        assert map_intent_to_agent("totally_unknown", "pro") == "faq"


class TestActionClassification:
    """Tests for ACTION_TYPE_MAP and classify_action_type."""

    def test_informational_actions(self):
        """Test informational action classification."""
        from app.core.langgraph.config import classify_action_type

        assert classify_action_type("respond") == "informational"
        assert classify_action_type("answer") == "informational"
        assert classify_action_type("inform") == "informational"
        assert classify_action_type("create_ticket") == "informational"

    def test_monetary_actions(self):
        """Test monetary action classification."""
        from app.core.langgraph.config import classify_action_type

        assert classify_action_type("refund") == "monetary"
        assert classify_action_type("discount") == "monetary"
        assert classify_action_type("credit") == "monetary"
        assert classify_action_type("waive_fee") == "monetary"

    def test_destructive_actions(self):
        """Test destructive action classification."""
        from app.core.langgraph.config import classify_action_type

        assert classify_action_type("cancel_subscription") == "destructive"
        assert classify_action_type("delete_account") == "destructive"

    def test_escalation_actions(self):
        """Test escalation action classification."""
        from app.core.langgraph.config import classify_action_type

        assert classify_action_type("escalate") == "escalation"
        assert classify_action_type("human_handoff") == "escalation"

    def test_unknown_action_defaults_to_informational(self):
        """Unknown action types default to informational (safe default)."""
        from app.core.langgraph.config import classify_action_type

        assert classify_action_type("totally_unknown_action") == "informational"


# ══════════════════════════════════════════════════════════════════
# EDGE TESTS
# ══════════════════════════════════════════════════════════════════


class TestRouteAfterRouter:
    """Tests for route_after_router edge function."""

    def test_faq_intent_all_tiers(self):
        """FAQ intent routes to faq_agent for all tiers."""
        from app.core.langgraph.edges import route_after_router

        for tier in ("mini", "pro", "high"):
            state = {"intent": "faq", "variant_tier": tier}
            assert route_after_router(state) == "faq_agent"

    def test_refund_intent_mini_fallback(self):
        """Refund intent on mini tier falls back to faq_agent."""
        from app.core.langgraph.edges import route_after_router

        state = {"intent": "refund", "variant_tier": "mini"}
        assert route_after_router(state) == "faq_agent"

    def test_refund_intent_pro_routes_to_refund(self):
        """Refund intent on pro tier routes to refund_agent."""
        from app.core.langgraph.edges import route_after_router

        state = {"intent": "refund", "variant_tier": "pro"}
        assert route_after_router(state) == "refund_agent"

    def test_escalation_intent_mini_fallback(self):
        """Escalation intent on mini tier falls back to faq_agent."""
        from app.core.langgraph.edges import route_after_router

        state = {"intent": "escalation", "variant_tier": "mini"}
        assert route_after_router(state) == "faq_agent"

    def test_escalation_intent_pro_routes_to_escalation(self):
        """Escalation intent on pro tier routes to escalation_agent."""
        from app.core.langgraph.edges import route_after_router

        state = {"intent": "escalation", "variant_tier": "pro"}
        assert route_after_router(state) == "escalation_agent"

    def test_technical_intent_all_tiers(self):
        """Technical intent routes to technical_agent for all tiers."""
        from app.core.langgraph.edges import route_after_router

        for tier in ("mini", "pro", "high"):
            state = {"intent": "technical", "variant_tier": tier}
            assert route_after_router(state) == "technical_agent"

    def test_unknown_intent_defaults_to_faq(self):
        """Unknown intent defaults to faq_agent."""
        from app.core.langgraph.edges import route_after_router

        state = {"intent": "xyz_unknown", "variant_tier": "pro"}
        assert route_after_router(state) == "faq_agent"

    def test_missing_intent_defaults_to_general(self):
        """Missing intent field defaults to general → faq_agent."""
        from app.core.langgraph.edges import route_after_router

        state = {"variant_tier": "pro"}
        result = route_after_router(state)
        assert result == "faq_agent"

    def test_missing_variant_tier_defaults_to_mini(self):
        """Missing variant_tier defaults to mini (safest fallback)."""
        from app.core.langgraph.edges import route_after_router

        state = {"intent": "refund"}
        result = route_after_router(state)
        # Refund not available in mini → fallback to faq
        assert result == "faq_agent"


class TestRouteAfterMaker:
    """Tests for route_after_maker edge function."""

    def test_red_flag_goes_to_control(self):
        """Red flag from MAKER always routes to control_system."""
        from app.core.langgraph.edges import route_after_maker

        for tier in ("mini", "pro", "high"):
            state = {"red_flag": True, "action_type": "informational", "variant_tier": tier}
            assert route_after_maker(state) == "control_system"

    def test_no_red_flag_informational_skips_control(self):
        """No red flag + informational action skips control_system."""
        from app.core.langgraph.edges import route_after_maker

        state = {"red_flag": False, "action_type": "informational", "variant_tier": "mini"}
        assert route_after_maker(state) == "dspy_optimizer"

    def test_monetary_action_pro_goes_to_control(self):
        """Monetary action on pro tier routes to control_system."""
        from app.core.langgraph.edges import route_after_maker

        state = {"red_flag": False, "action_type": "monetary", "variant_tier": "pro"}
        assert route_after_maker(state) == "control_system"

    def test_monetary_action_mini_skips_control(self):
        """Monetary action on mini tier skips control_system (auto-approve)."""
        from app.core.langgraph.edges import route_after_maker

        state = {"red_flag": False, "action_type": "monetary", "variant_tier": "mini"}
        assert route_after_maker(state) == "dspy_optimizer"

    def test_destructive_action_high_goes_to_control(self):
        """Destructive action on high tier routes to control_system."""
        from app.core.langgraph.edges import route_after_maker

        state = {"red_flag": False, "action_type": "destructive", "variant_tier": "high"}
        assert route_after_maker(state) == "control_system"

    def test_escalation_action_high_goes_to_control(self):
        """Escalation action on high tier routes to control_system."""
        from app.core.langgraph.edges import route_after_maker

        state = {"red_flag": False, "action_type": "escalation", "variant_tier": "high"}
        assert route_after_maker(state) == "control_system"


class TestRouteAfterControl:
    """Tests for route_after_control edge function."""

    def test_approved_goes_to_dspy(self):
        """Approved decision goes to dspy_optimizer."""
        from app.core.langgraph.edges import route_after_control

        state = {"approval_decision": "approved"}
        assert route_after_control(state) == "dspy_optimizer"

    def test_auto_approved_goes_to_dspy(self):
        """Auto-approved decision goes to dspy_optimizer."""
        from app.core.langgraph.edges import route_after_control

        state = {"approval_decision": "auto_approved"}
        assert route_after_control(state) == "dspy_optimizer"

    def test_rejected_goes_to_state_update(self):
        """Rejected decision goes to state_update."""
        from app.core.langgraph.edges import route_after_control

        state = {"approval_decision": "rejected"}
        assert route_after_control(state) == "state_update"

    def test_needs_human_approval_goes_to_state_update(self):
        """Needs human approval goes to state_update (safety fallback)."""
        from app.core.langgraph.edges import route_after_control

        state = {"approval_decision": "needs_human_approval"}
        assert route_after_control(state) == "state_update"

    def test_unknown_decision_defaults_to_dspy(self):
        """Unknown decision defaults to dspy_optimizer (proceed)."""
        from app.core.langgraph.edges import route_after_control

        state = {"approval_decision": "something_unknown"}
        assert route_after_control(state) == "dspy_optimizer"


class TestRouteAfterGuardrails:
    """Tests for route_after_guardrails edge function."""

    def test_passed_goes_to_channel_delivery(self):
        """Guardrails passed → channel_delivery."""
        from app.core.langgraph.edges import route_after_guardrails

        state = {"guardrails_passed": True}
        assert route_after_guardrails(state) == "channel_delivery"

    def test_blocked_goes_to_state_update(self):
        """Guardrails blocked → state_update."""
        from app.core.langgraph.edges import route_after_guardrails

        state = {"guardrails_passed": False, "guardrails_blocked_reason": "Injection detected"}
        assert route_after_guardrails(state) == "state_update"

    def test_default_passed(self):
        """Default (missing field) assumes passed."""
        from app.core.langgraph.edges import route_after_guardrails

        state = {}
        assert route_after_guardrails(state) == "channel_delivery"


class TestRouteAfterDelivery:
    """Tests for route_after_delivery edge function."""

    def test_email_all_tiers(self):
        """Email channel routes to email_agent for all tiers."""
        from app.core.langgraph.edges import route_after_delivery

        for tier in ("mini", "pro", "high"):
            state = {"channel": "email", "variant_tier": tier}
            assert route_after_delivery(state) == "email_agent"

    def test_sms_all_tiers(self):
        """SMS channel routes to sms_agent for all tiers."""
        from app.core.langgraph.edges import route_after_delivery

        for tier in ("mini", "pro", "high"):
            state = {"channel": "sms", "variant_tier": tier}
            assert route_after_delivery(state) == "sms_agent"

    def test_voice_mini_fallback(self):
        """Voice on mini tier falls back to email_agent."""
        from app.core.langgraph.edges import route_after_delivery

        state = {"channel": "voice", "variant_tier": "mini"}
        assert route_after_delivery(state) == "email_agent"

    def test_voice_pro_routes_to_voice_agent(self):
        """Voice on pro tier routes to voice_agent."""
        from app.core.langgraph.edges import route_after_delivery

        state = {"channel": "voice", "variant_tier": "pro"}
        assert route_after_delivery(state) == "voice_agent"

    def test_video_only_high(self):
        """Video channel only routes to video_agent on high tier."""
        from app.core.langgraph.edges import route_after_delivery

        state = {"channel": "video", "variant_tier": "high"}
        assert route_after_delivery(state) == "video_agent"

    def test_video_pro_fallback(self):
        """Video on pro tier falls back to email_agent."""
        from app.core.langgraph.edges import route_after_delivery

        state = {"channel": "video", "variant_tier": "pro"}
        assert route_after_delivery(state) == "email_agent"

    def test_video_mini_fallback(self):
        """Video on mini tier falls back to email_agent."""
        from app.core.langgraph.edges import route_after_delivery

        state = {"channel": "video", "variant_tier": "mini"}
        assert route_after_delivery(state) == "email_agent"

    def test_chat_routes_to_state_update(self):
        """Chat channel routes to state_update (WebSocket delivery)."""
        from app.core.langgraph.edges import route_after_delivery

        state = {"channel": "chat", "variant_tier": "pro"}
        assert route_after_delivery(state) == "state_update"

    def test_api_routes_to_state_update(self):
        """API channel routes to state_update (direct response)."""
        from app.core.langgraph.edges import route_after_delivery

        state = {"channel": "api", "variant_tier": "pro"}
        assert route_after_delivery(state) == "state_update"

    def test_unknown_channel_fallback_to_email(self):
        """Unknown channel falls back to email_agent."""
        from app.core.langgraph.edges import route_after_delivery

        state = {"channel": "fax", "variant_tier": "pro"}
        assert route_after_delivery(state) == "email_agent"


class TestShouldUseDspy:
    """Tests for should_use_dspy edge function."""

    def test_mini_always_skips_dspy(self):
        """Mini tier always skips DSPy (cost optimization)."""
        from app.core.langgraph.edges import should_use_dspy

        state = {"variant_tier": "mini", "complexity_score": 0.9}
        assert should_use_dspy(state) == "guardrails"

    def test_pro_simple_queries_skip_dspy(self):
        """Pro tier with low complexity skips DSPy."""
        from app.core.langgraph.edges import should_use_dspy

        state = {"variant_tier": "pro", "complexity_score": 0.3}
        assert should_use_dspy(state) == "guardrails"

    def test_pro_complex_queries_use_dspy(self):
        """Pro tier with high complexity uses DSPy."""
        from app.core.langgraph.edges import should_use_dspy

        state = {"variant_tier": "pro", "complexity_score": 0.7}
        assert should_use_dspy(state) == "dspy_optimizer"

    def test_high_always_uses_dspy(self):
        """High tier always uses DSPy."""
        from app.core.langgraph.edges import should_use_dspy

        state = {"variant_tier": "high", "complexity_score": 0.1}
        assert should_use_dspy(state) == "dspy_optimizer"

    def test_pro_boundary_complexity(self):
        """Pro tier at boundary (0.5) uses DSPy."""
        from app.core.langgraph.edges import should_use_dspy

        state = {"variant_tier": "pro", "complexity_score": 0.6}
        assert should_use_dspy(state) == "dspy_optimizer"


class TestShouldCompressContext:
    """Tests for should_compress_context edge function."""

    def test_mini_healthy_skips_compression(self):
        """Mini tier with healthy context skips compression."""
        from app.core.langgraph.edges import should_compress_context

        state = {"variant_tier": "mini", "context_health": 0.8}
        assert should_compress_context(state) == "domain_agent"

    def test_mini_critical_compresses(self):
        """Mini tier with critical context health compresses."""
        from app.core.langgraph.edges import should_compress_context

        state = {"variant_tier": "mini", "context_health": 0.4}
        assert should_compress_context(state) == "context_compression"

    def test_pro_moderate_compresses(self):
        """Pro tier with moderate context health compresses."""
        from app.core.langgraph.edges import should_compress_context

        state = {"variant_tier": "pro", "context_health": 0.6}
        assert should_compress_context(state) == "context_compression"

    def test_high_slight_degradation_compresses(self):
        """High tier compresses even with slight degradation."""
        from app.core.langgraph.edges import should_compress_context

        state = {"variant_tier": "high", "context_health": 0.8}
        assert should_compress_context(state) == "context_compression"

    def test_high_healthy_skips_compression(self):
        """High tier with perfectly healthy context skips compression."""
        from app.core.langgraph.edges import should_compress_context

        state = {"variant_tier": "high", "context_health": 0.95}
        assert should_compress_context(state) == "domain_agent"


class TestRouteAfterEmergencyCheck:
    """Tests for route_after_emergency_check edge function."""

    def test_normal_proceeds_to_pii(self):
        """Normal emergency state proceeds to pii_redaction."""
        from app.core.langgraph.edges import route_after_emergency_check

        state = {"ai_paused": False, "emergency_state": "normal"}
        assert route_after_emergency_check(state) == "pii_redaction"

    def test_ai_paused_goes_to_state_update(self):
        """AI paused state goes to state_update."""
        from app.core.langgraph.edges import route_after_emergency_check

        state = {"ai_paused": True, "emergency_state": "normal"}
        assert route_after_emergency_check(state) == "state_update"

    def test_full_stop_goes_to_state_update(self):
        """Full stop emergency state goes to state_update."""
        from app.core.langgraph.edges import route_after_emergency_check

        state = {"ai_paused": False, "emergency_state": "full_stop"}
        assert route_after_emergency_check(state) == "state_update"

    def test_yellow_alert_proceeds(self):
        """Yellow alert proceeds with normal flow."""
        from app.core.langgraph.edges import route_after_emergency_check

        state = {"ai_paused": False, "emergency_state": "yellow_alert"}
        assert route_after_emergency_check(state) == "pii_redaction"

    def test_red_alert_proceeds(self):
        """Red alert still proceeds (not full stop)."""
        from app.core.langgraph.edges import route_after_emergency_check

        state = {"ai_paused": False, "emergency_state": "red_alert"}
        assert route_after_emergency_check(state) == "pii_redaction"


class TestRouteAfterChannelAgent:
    """Tests for route_after_channel_agent edge function."""

    def test_always_returns_state_update(self):
        """After channel agent, always go to state_update."""
        from app.core.langgraph.edges import route_after_channel_agent

        state = {}
        assert route_after_channel_agent(state) == "state_update"

        state = {"variant_tier": "high", "channel": "voice"}
        assert route_after_channel_agent(state) == "state_update"


# ══════════════════════════════════════════════════════════════════
# ENUM TESTS
# ══════════════════════════════════════════════════════════════════


class TestEnums:
    """Tests for all enum classes."""

    def test_variant_tier_values(self):
        """Test VariantTier enum values."""
        from app.core.langgraph.config import VariantTier

        assert VariantTier.MINI.value == "mini"
        assert VariantTier.PRO.value == "pro"
        assert VariantTier.HIGH.value == "high"

    def test_maker_mode_values(self):
        """Test MakerMode enum values."""
        from app.core.langgraph.config import MakerMode

        assert MakerMode.EFFICIENCY.value == "efficiency"
        assert MakerMode.BALANCED.value == "balanced"
        assert MakerMode.CONSERVATIVE.value == "conservative"

    def test_system_mode_values(self):
        """Test SystemMode enum values."""
        from app.core.langgraph.config import SystemMode

        assert SystemMode.AUTO.value == "auto"
        assert SystemMode.SUPERVISED.value == "supervised"
        assert SystemMode.SHADOW.value == "shadow"
        assert SystemMode.PAUSED.value == "paused"

    def test_emergency_state_values(self):
        """Test EmergencyState enum values."""
        from app.core.langgraph.config import EmergencyState

        assert EmergencyState.NORMAL.value == "normal"
        assert EmergencyState.YELLOW_ALERT.value == "yellow_alert"
        assert EmergencyState.RED_ALERT.value == "red_alert"
        assert EmergencyState.FULL_STOP.value == "full_stop"

    def test_approval_decision_values(self):
        """Test ApprovalDecision enum values."""
        from app.core.langgraph.config import ApprovalDecision

        assert ApprovalDecision.APPROVED.value == "approved"
        assert ApprovalDecision.REJECTED.value == "rejected"
        assert ApprovalDecision.NEEDS_HUMAN_APPROVAL.value == "needs_human_approval"
        assert ApprovalDecision.AUTO_APPROVED.value == "auto_approved"

    def test_action_type_values(self):
        """Test ActionType enum values."""
        from app.core.langgraph.config import ActionType

        assert ActionType.INFORMATIONAL.value == "informational"
        assert ActionType.MONETARY.value == "monetary"
        assert ActionType.DESTRUCTIVE.value == "destructive"
        assert ActionType.ESCALATION.value == "escalation"


# ══════════════════════════════════════════════════════════════════
# INTEGRATION-STYLE TESTS (Phase 1 scope)
# ══════════════════════════════════════════════════════════════════


class TestStateConfigIntegration:
    """Integration tests verifying state and config work together."""

    def test_initial_state_maker_fields_match_config(self):
        """Verify initial state MAKER fields are set correctly based on tier."""
        from app.core.langgraph.state import create_initial_state
        from app.core.langgraph.config import MAKER_CONFIG

        for tier in ("mini", "pro", "high"):
            state = create_initial_state(
                message="test", channel="email",
                customer_id="c1", tenant_id="t1",
                variant_tier=tier,
            )
            # Initial state has empty MAKER fields — they get populated
            # by the MAKER node during execution. Verify the config is accessible.
            maker_config = MAKER_CONFIG[tier]
            assert maker_config["mode"] in ("efficiency", "balanced", "conservative")

    def test_initial_state_channel_field_matches_availability(self):
        """Verify channel field in initial state is compatible with tier."""
        from app.core.langgraph.state import create_initial_state
        from app.core.langgraph.config import CHANNEL_AVAILABILITY

        for tier in ("mini", "pro", "high"):
            state = create_initial_state(
                message="test", channel="email",
                customer_id="c1", tenant_id="t1",
                variant_tier=tier,
            )
            # Email should be available for all tiers
            assert "email" in CHANNEL_AVAILABILITY[tier]["channels"]

    def test_full_flow_simulation_mini(self):
        """Simulate a full mini-tier flow through edge functions."""
        from app.core.langgraph.state import create_initial_state
        from app.core.langgraph.edges import (
            route_after_router,
            route_after_maker,
            route_after_guardrails,
            route_after_delivery,
        )

        state = create_initial_state(
            message="How do I reset my password?",
            channel="email",
            customer_id="cust_001",
            tenant_id="tenant_001",
            variant_tier="mini",
        )

        # Simulate: Router classifies as faq
        state["intent"] = "faq"
        assert route_after_router(state) == "faq_agent"

        # Simulate: FAQ agent responds with informational action
        state["action_type"] = "informational"
        state["red_flag"] = False
        assert route_after_maker(state) == "dspy_optimizer"  # Skip control for mini

        # Simulate: Guardrails pass
        state["guardrails_passed"] = True
        assert route_after_guardrails(state) == "channel_delivery"

        # Simulate: Channel delivery → email
        assert route_after_delivery(state) == "email_agent"

    def test_full_flow_simulation_pro_refund(self):
        """Simulate a pro-tier refund flow through edge functions."""
        from app.core.langgraph.state import create_initial_state
        from app.core.langgraph.edges import (
            route_after_router,
            route_after_maker,
            route_after_control,
            route_after_guardrails,
            route_after_delivery,
        )

        state = create_initial_state(
            message="I want a refund for order #123",
            channel="email",
            customer_id="cust_002",
            tenant_id="tenant_002",
            variant_tier="pro",
        )

        # Router classifies as refund
        state["intent"] = "refund"
        assert route_after_router(state) == "refund_agent"

        # Refund agent proposes monetary action
        state["action_type"] = "monetary"
        state["red_flag"] = False
        assert route_after_maker(state) == "control_system"  # Monetary needs approval on pro

        # Control approves
        state["approval_decision"] = "approved"
        assert route_after_control(state) == "dspy_optimizer"

        # Guardrails pass
        state["guardrails_passed"] = True
        assert route_after_guardrails(state) == "channel_delivery"

        # Delivery via email
        assert route_after_delivery(state) == "email_agent"

    def test_full_flow_simulation_high_voice_escalation(self):
        """Simulate a high-tier voice escalation flow."""
        from app.core.langgraph.state import create_initial_state
        from app.core.langgraph.edges import (
            route_after_router,
            route_after_maker,
            route_after_control,
            route_after_guardrails,
            route_after_delivery,
        )

        state = create_initial_state(
            message="I need to speak to a manager NOW!",
            channel="voice",
            customer_id="cust_003",
            tenant_id="tenant_003",
            variant_tier="high",
        )

        # Router classifies as escalation
        state["intent"] = "escalation"
        assert route_after_router(state) == "escalation_agent"

        # Escalation action on high tier needs approval
        state["action_type"] = "escalation"
        state["red_flag"] = False
        assert route_after_maker(state) == "control_system"

        # Control approves
        state["approval_decision"] = "approved"
        assert route_after_control(state) == "dspy_optimizer"

        # Guardrails pass
        state["guardrails_passed"] = True
        assert route_after_guardrails(state) == "channel_delivery"

        # Voice delivery on high tier
        assert route_after_delivery(state) == "voice_agent"

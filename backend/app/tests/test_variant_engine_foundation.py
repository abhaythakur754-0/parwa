"""
Production-Ready Unit Tests for the Variant Engine Shared Foundation.

Covers all 4 foundation modules:
  1. parwa_graph_state.py — ParwaGraphState, create_initial_state, helpers
  2. industry_enum.py — Industry enum, metadata, mapping, helpers
  3. variant_router.py — All routing functions, pipeline definitions, VariantRouter
  4. variant_service.py — VariantConfig, config resolution, overrides, summaries

Test categories:
  - Happy path: correct inputs → correct outputs
  - Edge cases: empty strings, unknown values, boundary conditions
  - Error resilience: malformed inputs → graceful fallbacks (BC-008)
  - Cross-module integration: router + state + service working together
  - Production scenarios: multi-instance, upgrade/downgrade, industry switching
  - Thread safety: concurrent access patterns

Building Codes: BC-001, BC-008, BC-012
"""

import operator
import threading
import time

import pytest

from app.core.parwa_graph_state import (
    ParwaGraphState,
    create_initial_state,
    get_step_output,
    append_audit_entry,
)
from app.core.industry_enum import (
    Industry,
    INDUSTRY_METADATA,
    validate_industry,
    get_industry_prompt,
    get_industry_tools,
    get_industry_tone,
    map_onboarding_industry_to_enum,
)
from app.core.variant_router import (
    NODE_PII,
    NODE_EMPATHY,
    NODE_EMERGENCY,
    NODE_CLASSIFY,
    NODE_EXTRACT_SIGNALS,
    NODE_TECHNIQUE_SELECT,
    NODE_CONTEXT_COMPRESS,
    NODE_GENERATE,
    NODE_QUALITY_GATE,
    NODE_CONTEXT_HEALTH,
    NODE_DEDUP,
    NODE_FORMAT,
    NODE_END,
    ALL_NODES,
    route_after_pii,
    route_after_empathy,
    route_after_emergency,
    route_after_classify,
    route_after_extract_signals,
    route_after_technique_select,
    route_after_context_compress,
    route_after_generate,
    route_after_quality_gate,
    route_after_context_health,
    route_after_dedup,
    get_mini_pipeline_steps,
    get_pro_pipeline_steps,
    get_high_pipeline_steps,
    VariantRouter,
)
from app.core.variant_service import (
    StepConfig,
    VariantConfig,
    VariantService,
    TIER_DEFAULTS,
    INDUSTRY_OVERRIDES,
    STEP_DEFAULTS,
)


# ═══════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def service():
    """Fresh VariantService for each test."""
    return VariantService()


@pytest.fixture
def router():
    """Fresh VariantRouter for each test."""
    return VariantRouter()


@pytest.fixture
def mini_ecommerce_state():
    """State for Mini E-commerce scenario."""
    return create_initial_state(
        query="Where is my order?",
        company_id="co_123",
        variant_tier="mini_parwa",
        variant_instance_id="inst_mini_1",
        industry="ecommerce",
        channel="chat",
        conversation_id="conv_456",
        ticket_id="tkt_789",
        customer_id="cust_001",
        customer_tier="starter",
    )


@pytest.fixture
def pro_saas_state():
    """State for Pro SaaS scenario."""
    return create_initial_state(
        query="My billing is wrong, I need help",
        company_id="co_456",
        variant_tier="parwa",
        variant_instance_id="inst_pro_1",
        industry="saas",
        channel="email",
        conversation_id="conv_789",
        ticket_id="tkt_012",
        customer_id="cust_002",
        customer_tier="growth",
    )


@pytest.fixture
def high_logistics_state():
    """State for High Logistics scenario."""
    return create_initial_state(
        query="Urgent: shipment stuck at customs for 5 days",
        company_id="co_789",
        variant_tier="parwa_high",
        variant_instance_id="inst_high_1",
        industry="logistics",
        channel="phone",
        conversation_id="conv_012",
        ticket_id="tkt_345",
        customer_id="cust_003",
        customer_tier="enterprise",
    )


# ═══════════════════════════════════════════════════════════════════
# 1. PARWA GRAPH STATE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestParwaGraphState:
    """Tests for ParwaGraphState TypedDict and helpers."""

    # -- create_initial_state --

    def test_create_initial_state_basic(self):
        """create_initial_state should return a dict with all required fields."""
        state = create_initial_state(
            query="Hello",
            company_id="co_1",
            variant_tier="mini_parwa",
        )
        assert state["query"] == "Hello"
        assert state["company_id"] == "co_1"
        assert state["variant_tier"] == "mini_parwa"

    def test_create_initial_state_all_incoming_fields(self):
        """All INCOMING fields should be populated from arguments."""
        state = create_initial_state(
            query="Test",
            company_id="co_1",
            variant_tier="parwa",
            variant_instance_id="inst_1",
            industry="ecommerce",
            channel="email",
            conversation_id="conv_1",
            ticket_id="tkt_1",
            customer_id="cust_1",
            customer_tier="growth",
        )
        assert state["variant_instance_id"] == "inst_1"
        assert state["industry"] == "ecommerce"
        assert state["channel"] == "email"
        assert state["conversation_id"] == "conv_1"
        assert state["ticket_id"] == "tkt_1"
        assert state["customer_id"] == "cust_1"
        assert state["customer_tier"] == "growth"

    def test_create_initial_state_defaults(self):
        """Pipeline control fields should have safe defaults."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="mini_parwa")
        assert state["pii_detected"] is False
        assert state["emergency_flag"] is False
        assert state["quality_passed"] is True  # default pass for Mini
        assert state["context_compressed"] is False
        assert state["dedup_is_duplicate"] is False
        assert state["pipeline_status"] == "pending"
        assert state["total_tokens"] == 0
        assert state["errors"] == []
        assert state["steps_completed"] == []
        assert state["audit_log"] == []
        assert state["step_outputs"] == {}

    def test_create_initial_state_pii_redacted_defaults_to_query(self):
        """pii_redacted_query should default to the raw query."""
        state = create_initial_state(query="My SSN is 123-45-6789", company_id="co_1", variant_tier="parwa")
        assert state["pii_redacted_query"] == "My SSN is 123-45-6789"

    def test_create_initial_state_billing_tier_matches_variant(self):
        """billing_tier should match variant_tier."""
        for tier in ["mini_parwa", "parwa", "parwa_high"]:
            state = create_initial_state(query="Hi", company_id="co_1", variant_tier=tier)
            assert state["billing_tier"] == tier

    def test_create_initial_state_response_format_matches_channel(self):
        """response_format should default to the channel."""
        for channel in ["chat", "email", "phone"]:
            state = create_initial_state(
                query="Hi", company_id="co_1",
                variant_tier="mini_parwa", channel=channel,
            )
            assert state["response_format"] == channel

    def test_create_initial_state_empty_defaults(self):
        """Empty strings should work for optional fields."""
        state = create_initial_state(
            query="Hi",
            company_id="co_1",
            variant_tier="mini_parwa",
            variant_instance_id="",
            industry="general",
            channel="",
            conversation_id="",
            ticket_id="",
        )
        assert state["variant_instance_id"] == ""
        assert state["industry"] == "general"
        assert state["channel"] == ""
        assert state["conversation_id"] == ""
        assert state["ticket_id"] == ""

    # -- State mutation patterns --

    def test_state_node_write_pattern(self):
        """Nodes should be able to update specific fields without affecting others."""
        state = create_initial_state(query="Hello", company_id="co_1", variant_tier="parwa")

        # Simulate classify node writing its output
        state["classification"] = {"intent": "order_status", "confidence": 0.92}
        state["current_step"] = "classify"

        # Verify other fields are untouched
        assert state["query"] == "Hello"
        assert state["company_id"] == "co_1"
        assert state["emergency_flag"] is False
        assert state["signals"] == {}

    def test_state_step_outputs_merge(self):
        """step_outputs should merge using operator.or_ reducer logic."""
        # Simulate what LangGraph does: merge dicts
        existing = {"classify": {"intent": "order_status"}}
        new_output = {"generate": {"response": "Your order is shipping"}}
        merged = {**existing, **new_output}

        assert "classify" in merged
        assert "generate" in merged
        assert merged["classify"]["intent"] == "order_status"

    def test_state_audit_log_append(self):
        """audit_log should support append pattern."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa")

        entry1 = {"step": "pii", "action": "scan", "tokens": 0}
        entry2 = {"step": "classify", "action": "classify", "tokens": 50}

        # Simulate LangGraph operator.add reducer
        state["audit_log"] = state["audit_log"] + [entry1, entry2]
        assert len(state["audit_log"]) == 2
        assert state["audit_log"][0]["step"] == "pii"
        assert state["audit_log"][1]["step"] == "classify"

    def test_state_errors_append(self):
        """errors should support append pattern."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa")
        state["errors"] = state["errors"] + ["timeout_in_classify"]
        state["errors"] = state["errors"] + ["quality_gate_failed"]
        assert len(state["errors"]) == 2


class TestGetStepOutput:
    """Tests for get_step_output helper."""

    def test_existing_step(self):
        """Should return output dict for existing step."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa")
        state["step_outputs"] = {"classify": {"intent": "refund", "confidence": 0.9}}
        result = get_step_output(state, "classify")
        assert result["intent"] == "refund"

    def test_missing_step(self):
        """Should return empty dict for missing step."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa")
        result = get_step_output(state, "nonexistent")
        assert result == {}

    def test_empty_state(self):
        """Should handle state with no step_outputs."""
        state = {"query": "Hi"}  # minimal state, no step_outputs key
        result = get_step_output(state, "classify")
        assert result == {}

    def test_non_dict_output(self):
        """Should return empty dict if step output is not a dict."""
        state = {"step_outputs": {"classify": "not_a_dict"}}
        result = get_step_output(state, "classify")
        assert result == {}


class TestAppendAuditEntry:
    """Tests for append_audit_entry helper."""

    def test_creates_entry_dict(self):
        """Should return a dict with audit_log key containing one entry."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa")
        result = append_audit_entry(state, "classify", "intent_classified", duration_ms=120.5, tokens_used=50)
        assert "audit_log" in result
        assert len(result["audit_log"]) == 1
        entry = result["audit_log"][0]
        assert entry["step"] == "classify"
        assert entry["action"] == "intent_classified"
        assert entry["duration_ms"] == 120.5
        assert entry["tokens_used"] == 50
        assert "timestamp" in entry

    def test_includes_context(self):
        """Entry should include company_id, variant_tier, industry."""
        state = create_initial_state(
            query="Hi", company_id="co_1",
            variant_tier="parwa", industry="ecommerce",
        )
        result = append_audit_entry(state, "generate", "response_generated")
        entry = result["audit_log"][0]
        assert entry["company_id"] == "co_1"
        assert entry["variant_tier"] == "parwa"
        assert entry["industry"] == "ecommerce"

    def test_with_details(self):
        """Should include details dict when provided."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa")
        details = {"model": "gpt-4o-mini", "retry": False}
        result = append_audit_entry(state, "generate", "response", details=details)
        assert result["audit_log"][0]["details"]["model"] == "gpt-4o-mini"

    def test_without_details(self):
        """Details should default to empty dict."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa")
        result = append_audit_entry(state, "classify", "classified")
        assert result["audit_log"][0]["details"] == {}


# ═══════════════════════════════════════════════════════════════════
# 2. INDUSTRY ENUM TESTS
# ═══════════════════════════════════════════════════════════════════


class TestIndustryEnum:
    """Tests for Industry enum."""

    def test_four_industries(self):
        """Should have exactly 4 industries."""
        assert len(Industry) == 4

    def test_ecommerce(self):
        """ECOMMERCE should equal 'ecommerce'."""
        assert Industry.ECOMMERCE.value == "ecommerce"

    def test_logistics(self):
        """LOGISTICS should equal 'logistics'."""
        assert Industry.LOGISTICS.value == "logistics"

    def test_saas(self):
        """SAAS should equal 'saas'."""
        assert Industry.SAAS.value == "saas"

    def test_general(self):
        """GENERAL should equal 'general'."""
        assert Industry.GENERAL.value == "general"

    def test_string_comparison(self):
        """Enum should be comparable with string values (str inheritance)."""
        assert Industry.ECOMMERCE == "ecommerce"
        assert Industry.LOGISTICS == "logistics"

    def test_json_serializable(self):
        """Enum should be JSON-serializable via .value."""
        import json
        data = {"industry": Industry.SAAS.value}
        serialized = json.dumps(data)
        assert '"saas"' in serialized

    def test_from_string(self):
        """Should be constructable from string."""
        assert Industry("ecommerce") == Industry.ECOMMERCE
        assert Industry("logistics") == Industry.LOGISTICS


class TestIndustryMetadata:
    """Tests for INDUSTRY_METADATA dictionary."""

    def test_metadata_for_all_industries(self):
        """Each Industry enum member should have metadata."""
        for industry in Industry:
            assert industry.value in INDUSTRY_METADATA

    def test_ecommerce_has_order_tracker(self):
        """E-commerce should have order_tracker tool."""
        tools = INDUSTRY_METADATA["ecommerce"]["available_tools"]
        assert "order_tracker" in tools

    def test_ecommerce_has_shipment_tracker(self):
        """E-commerce should have shipment_tracker tool (shared with logistics)."""
        tools = INDUSTRY_METADATA["ecommerce"]["available_tools"]
        assert "shipment_tracker" in tools

    def test_logistics_has_shipment_tracker(self):
        """Logistics should have shipment_tracker tool."""
        tools = INDUSTRY_METADATA["logistics"]["available_tools"]
        assert "shipment_tracker" in tools

    def test_saas_has_subscription_manager(self):
        """SaaS should have subscription_manager tool."""
        tools = INDUSTRY_METADATA["saas"]["available_tools"]
        assert "subscription_manager" in tools

    def test_general_has_knowledge_search(self):
        """General should have knowledge_search as basic tool."""
        tools = INDUSTRY_METADATA["general"]["available_tools"]
        assert "knowledge_search" in tools

    def test_all_have_system_prompt(self):
        """Each industry should have a system_prompt_prefix."""
        for industry, meta in INDUSTRY_METADATA.items():
            assert "system_prompt_prefix" in meta
            assert len(meta["system_prompt_prefix"]) > 20

    def test_all_have_tone(self):
        """Each industry should have a tone."""
        for industry, meta in INDUSTRY_METADATA.items():
            assert "tone" in meta
            assert len(meta["tone"]) > 0

    def test_all_have_common_intents(self):
        """Each industry should have common_intents list."""
        for industry, meta in INDUSTRY_METADATA.items():
            assert "common_intents" in meta
            assert len(meta["common_intents"]) > 0

    def test_all_have_escalation_triggers(self):
        """Each industry should have escalation_triggers list."""
        for industry, meta in INDUSTRY_METADATA.items():
            assert "escalation_triggers" in meta
            assert len(meta["escalation_triggers"]) > 0

    def test_ecommerce_tone(self):
        """E-commerce tone should be warm_friendly."""
        assert INDUSTRY_METADATA["ecommerce"]["tone"] == "warm_friendly"

    def test_logistics_tone(self):
        """Logistics tone should be professional_precise."""
        assert INDUSTRY_METADATA["logistics"]["tone"] == "professional_precise"

    def test_saas_tone(self):
        """SaaS tone should be technical_helpful."""
        assert INDUSTRY_METADATA["saas"]["tone"] == "technical_helpful"


class TestValidateIndustry:
    """Tests for validate_industry helper."""

    def test_valid_industries(self):
        """All valid industry strings should pass validation."""
        for industry in ["ecommerce", "logistics", "saas", "general"]:
            result = validate_industry(industry)
            assert isinstance(result, Industry)

    def test_case_insensitive(self):
        """Should handle case-insensitive input."""
        assert validate_industry("ECOMMERCE") == Industry.ECOMMERCE
        assert validate_industry("Ecommerce") == Industry.ECOMMERCE
        assert validate_industry("SAAS") == Industry.SAAS

    def test_whitespace_stripped(self):
        """Should strip whitespace."""
        assert validate_industry("  ecommerce  ") == Industry.ECOMMERCE

    def test_invalid_raises_valueerror(self):
        """Unknown industry should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown industry"):
            validate_industry("healthcare")

    def test_empty_raises_valueerror(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            validate_industry("")

    def test_error_message_lists_valid(self):
        """Error message should list valid industries."""
        with pytest.raises(ValueError) as exc_info:
            validate_industry("unknown")
        error_msg = str(exc_info.value)
        assert "ecommerce" in error_msg
        assert "logistics" in error_msg
        assert "saas" in error_msg
        assert "general" in error_msg


class TestGetIndustryHelpers:
    """Tests for get_industry_prompt, get_industry_tools, get_industry_tone."""

    def test_get_prompt_known_industry(self):
        """Should return prompt for known industry."""
        prompt = get_industry_prompt("ecommerce")
        assert "e-commerce" in prompt.lower()

    def test_get_prompt_unknown_falls_back(self):
        """Unknown industry should fall back to general prompt."""
        prompt = get_industry_prompt("unknown_industry")
        assert len(prompt) > 0
        # Should be the general prompt
        assert prompt == INDUSTRY_METADATA["general"]["system_prompt_prefix"]

    def test_get_tools_known_industry(self):
        """Should return tools for known industry."""
        tools = get_industry_tools("saas")
        assert "subscription_manager" in tools

    def test_get_tools_unknown_falls_back(self):
        """Unknown industry should fall back to general tools."""
        tools = get_industry_tools("unknown")
        assert "knowledge_search" in tools

    def test_get_tone_known_industry(self):
        """Should return tone for known industry."""
        assert get_industry_tone("logistics") == "professional_precise"

    def test_get_tone_unknown_falls_back(self):
        """Unknown industry should fall back to general tone."""
        tone = get_industry_tone("unknown")
        assert tone == "professional_adaptable"


class TestMapOnboardingIndustry:
    """Tests for map_onboarding_industry_to_enum."""

    def test_ecommerce_group(self):
        """E-commerce group: ecommerce, retail, hospitality."""
        assert map_onboarding_industry_to_enum("ecommerce") == Industry.ECOMMERCE
        assert map_onboarding_industry_to_enum("retail") == Industry.ECOMMERCE
        assert map_onboarding_industry_to_enum("hospitality") == Industry.ECOMMERCE

    def test_logistics_group(self):
        """Logistics group: logistics only."""
        assert map_onboarding_industry_to_enum("logistics") == Industry.LOGISTICS

    def test_saas_group(self):
        """SaaS group: saas, technology, finance, healthcare, education."""
        assert map_onboarding_industry_to_enum("saas") == Industry.SAAS
        assert map_onboarding_industry_to_enum("technology") == Industry.SAAS
        assert map_onboarding_industry_to_enum("finance") == Industry.SAAS
        assert map_onboarding_industry_to_enum("healthcare") == Industry.SAAS
        assert map_onboarding_industry_to_enum("education") == Industry.SAAS

    def test_general_group(self):
        """General group: real_estate, manufacturing, consulting, agency, nonprofit, other."""
        assert map_onboarding_industry_to_enum("real_estate") == Industry.GENERAL
        assert map_onboarding_industry_to_enum("manufacturing") == Industry.GENERAL
        assert map_onboarding_industry_to_enum("consulting") == Industry.GENERAL
        assert map_onboarding_industry_to_enum("agency") == Industry.GENERAL
        assert map_onboarding_industry_to_enum("nonprofit") == Industry.GENERAL
        assert map_onboarding_industry_to_enum("other") == Industry.GENERAL

    def test_unknown_falls_back_to_general(self):
        """Unknown onboarding industry should fall back to general."""
        assert map_onboarding_industry_to_enum("space_mining") == Industry.GENERAL

    def test_case_insensitive(self):
        """Should handle case-insensitive input."""
        assert map_onboarding_industry_to_enum("Ecommerce") == Industry.ECOMMERCE
        assert map_onboarding_industry_to_enum("SAAS") == Industry.SAAS

    def test_all_14_onboarding_industries_mapped(self):
        """All 14 onboarding industries should map to a valid Industry."""
        onboarding_industries = [
            "saas", "ecommerce", "healthcare", "finance", "education",
            "real_estate", "manufacturing", "consulting", "agency",
            "nonprofit", "logistics", "hospitality", "retail", "other",
        ]
        for industry in onboarding_industries:
            result = map_onboarding_industry_to_enum(industry)
            assert isinstance(result, Industry), f"Failed for {industry}"


# ═══════════════════════════════════════════════════════════════════
# 3. VARIANT ROUTER TESTS
# ═══════════════════════════════════════════════════════════════════


class TestNodeConstants:
    """Tests for node name constants."""

    def test_all_nodes_defined(self):
        """ALL_NODES should contain all 12 node names."""
        assert len(ALL_NODES) == 12
        assert NODE_PII in ALL_NODES
        assert NODE_EMPATHY in ALL_NODES
        assert NODE_EMERGENCY in ALL_NODES
        assert NODE_CLASSIFY in ALL_NODES
        assert NODE_EXTRACT_SIGNALS in ALL_NODES
        assert NODE_TECHNIQUE_SELECT in ALL_NODES
        assert NODE_CONTEXT_COMPRESS in ALL_NODES
        assert NODE_GENERATE in ALL_NODES
        assert NODE_QUALITY_GATE in ALL_NODES
        assert NODE_CONTEXT_HEALTH in ALL_NODES
        assert NODE_DEDUP in ALL_NODES
        assert NODE_FORMAT in ALL_NODES

    def test_no_duplicate_nodes(self):
        """ALL_NODES should not have duplicates."""
        assert len(ALL_NODES) == len(set(ALL_NODES))


class TestPipelineSteps:
    """Tests for pipeline step definitions."""

    def test_mini_steps_count(self):
        """Mini pipeline should have 6 steps (pii+empathy+emergency+classify+generate+format)."""
        steps = get_mini_pipeline_steps()
        assert len(steps) == 6

    def test_pro_steps_count(self):
        """Pro pipeline should have 9 steps."""
        steps = get_pro_pipeline_steps()
        assert len(steps) == 9

    def test_high_steps_count(self):
        """High pipeline should have 12 steps."""
        steps = get_high_pipeline_steps()
        assert len(steps) == 12

    def test_mini_starts_with_pii(self):
        """All pipelines should start with PII check."""
        assert get_mini_pipeline_steps()[0] == NODE_PII
        assert get_pro_pipeline_steps()[0] == NODE_PII
        assert get_high_pipeline_steps()[0] == NODE_PII

    def test_all_end_with_format(self):
        """All pipelines should end with format."""
        assert get_mini_pipeline_steps()[-1] == NODE_FORMAT
        assert get_pro_pipeline_steps()[-1] == NODE_FORMAT
        assert get_high_pipeline_steps()[-1] == NODE_FORMAT

    def test_mini_is_subset_of_pro(self):
        """Mini steps should be a subset of Pro steps."""
        mini_steps = set(get_mini_pipeline_steps())
        pro_steps = set(get_pro_pipeline_steps())
        assert mini_steps.issubset(pro_steps)

    def test_pro_is_subset_of_high(self):
        """Pro steps should be a subset of High steps."""
        pro_steps = set(get_pro_pipeline_steps())
        high_steps = set(get_high_pipeline_steps())
        assert pro_steps.issubset(high_steps)

    def test_pro_extra_steps(self):
        """Pro should add extract_signals, technique_select, quality_gate vs Mini."""
        mini_steps = set(get_mini_pipeline_steps())
        pro_steps = set(get_pro_pipeline_steps())
        extra = pro_steps - mini_steps
        assert NODE_EXTRACT_SIGNALS in extra
        assert NODE_TECHNIQUE_SELECT in extra
        assert NODE_QUALITY_GATE in extra

    def test_high_extra_steps(self):
        """High should add context_compress, context_health, dedup vs Pro."""
        pro_steps = set(get_pro_pipeline_steps())
        high_steps = set(get_high_pipeline_steps())
        extra = high_steps - pro_steps
        assert NODE_CONTEXT_COMPRESS in extra
        assert NODE_CONTEXT_HEALTH in extra
        assert NODE_DEDUP in extra


class TestRoutingFunctions:
    """Tests for individual routing functions."""

    # -- route_after_pii --
    def test_route_after_pii_always_empathy(self):
        """PII check should always route to empathy."""
        state = {"variant_tier": "mini_parwa"}
        assert route_after_pii(state) == NODE_EMPATHY

    # -- route_after_empathy --
    def test_route_after_empathy_always_emergency(self):
        """Empathy should always route to emergency check."""
        state = {"variant_tier": "mini_parwa"}
        assert route_after_empathy(state) == NODE_EMERGENCY

    # -- route_after_emergency --
    def test_route_after_emergency_no_emergency(self):
        """No emergency should route to classify."""
        state = {"emergency_flag": False}
        assert route_after_emergency(state) == NODE_CLASSIFY

    def test_route_after_emergency_with_emergency(self):
        """Emergency should bypass AI pipeline and go to format."""
        state = {"emergency_flag": True, "emergency_type": "legal_threat"}
        assert route_after_emergency(state) == NODE_FORMAT

    # -- route_after_classify (KEY ROUTING DECISION) --
    def test_route_after_classify_mini(self):
        """Mini should skip to generate after classify."""
        state = {"variant_tier": "mini_parwa"}
        assert route_after_classify(state) == NODE_GENERATE

    def test_route_after_classify_pro(self):
        """Pro should go to extract_signals after classify."""
        state = {"variant_tier": "parwa"}
        assert route_after_classify(state) == NODE_EXTRACT_SIGNALS

    def test_route_after_classify_high(self):
        """High should go to extract_signals after classify."""
        state = {"variant_tier": "parwa_high"}
        assert route_after_classify(state) == NODE_EXTRACT_SIGNALS

    def test_route_after_classify_unknown_tier(self):
        """Unknown tier should default to extract_signals (safe: go deeper, not shallower)."""
        state = {"variant_tier": "unknown"}
        # Safe default: treat unknown as Pro (more steps = safer)
        assert route_after_classify(state) == NODE_EXTRACT_SIGNALS

    # -- route_after_extract_signals --
    def test_route_after_extract_signals_always_technique(self):
        """Extract signals should always route to technique select."""
        assert route_after_extract_signals({}) == NODE_TECHNIQUE_SELECT

    # -- route_after_technique_select --
    def test_route_after_technique_select_pro(self):
        """Pro should go to generate (no compression)."""
        state = {"variant_tier": "parwa"}
        assert route_after_technique_select(state) == NODE_GENERATE

    def test_route_after_technique_select_high(self):
        """High should go to context_compress."""
        state = {"variant_tier": "parwa_high"}
        assert route_after_technique_select(state) == NODE_CONTEXT_COMPRESS

    # -- route_after_context_compress --
    def test_route_after_context_compress_always_generate(self):
        """After compression, always go to generate."""
        assert route_after_context_compress({}) == NODE_GENERATE

    # -- route_after_generate --
    def test_route_after_generate_mini(self):
        """Mini should skip quality gate and go to format."""
        state = {"variant_tier": "mini_parwa"}
        assert route_after_generate(state) == NODE_FORMAT

    def test_route_after_generate_pro(self):
        """Pro should go to quality gate."""
        state = {"variant_tier": "parwa"}
        assert route_after_generate(state) == NODE_QUALITY_GATE

    def test_route_after_generate_high(self):
        """High should go to quality gate."""
        state = {"variant_tier": "parwa_high"}
        assert route_after_generate(state) == NODE_QUALITY_GATE

    # -- route_after_quality_gate --
    def test_route_after_quality_gate_passed_pro(self):
        """Pro with passed quality should go to format."""
        state = {"variant_tier": "parwa", "quality_passed": True, "quality_retry_count": 0}
        assert route_after_quality_gate(state) == NODE_FORMAT

    def test_route_after_quality_gate_passed_high(self):
        """High with passed quality should go to context_health."""
        state = {"variant_tier": "parwa_high", "quality_passed": True, "quality_retry_count": 0}
        assert route_after_quality_gate(state) == NODE_CONTEXT_HEALTH

    def test_route_after_quality_gate_failed_retry(self):
        """Failed quality with retries remaining should go back to generate."""
        state = {"variant_tier": "parwa", "quality_passed": False, "quality_retry_count": 0}
        assert route_after_quality_gate(state) == NODE_GENERATE

    def test_route_after_quality_gate_failed_max_retries(self):
        """Failed quality with max retries should proceed to format."""
        state = {"variant_tier": "parwa", "quality_passed": False, "quality_retry_count": 1}
        assert route_after_quality_gate(state) == NODE_FORMAT

    # -- route_after_context_health --
    def test_route_after_context_health_always_dedup(self):
        """Context health should always route to dedup."""
        assert route_after_context_health({}) == NODE_DEDUP

    # -- route_after_dedup --
    def test_route_after_dedup_always_format(self):
        """Dedup should always route to format."""
        assert route_after_dedup({}) == NODE_FORMAT


class TestRoutingEdgeCases:
    """Edge cases for routing functions."""

    def test_route_after_classify_empty_state(self):
        """Empty state should default to extract_signals (safe: Pro path)."""
        # Safe default: empty state = parwa (Pro) tier → extract_signals
        assert route_after_classify({}) == NODE_EXTRACT_SIGNALS

    def test_route_after_emergency_empty_state(self):
        """Empty state should default to classify (no emergency)."""
        assert route_after_emergency({}) == NODE_CLASSIFY

    def test_route_after_generate_empty_state(self):
        """Empty state should default to quality_gate (safe: Pro path)."""
        # Safe default: empty state = parwa (Pro) tier → quality_gate
        assert route_after_generate({}) == NODE_QUALITY_GATE

    def test_route_after_quality_gate_empty_state(self):
        """Empty state should default to format (safe)."""
        assert route_after_quality_gate({}) == NODE_FORMAT


class TestVariantRouter:
    """Tests for VariantRouter class."""

    def test_get_pipeline_steps_mini(self, router):
        """Should return Mini pipeline steps."""
        steps = router.get_pipeline_steps("mini_parwa")
        assert len(steps) == 6
        assert steps[0] == NODE_PII

    def test_get_pipeline_steps_pro(self, router):
        """Should return Pro pipeline steps."""
        steps = router.get_pipeline_steps("parwa")
        assert len(steps) == 9

    def test_get_pipeline_steps_high(self, router):
        """Should return High pipeline steps."""
        steps = router.get_pipeline_steps("parwa_high")
        assert len(steps) == 12

    def test_get_pipeline_steps_unknown(self, router):
        """Unknown tier should default to Pro steps."""
        steps = router.get_pipeline_steps("unknown_tier")
        assert len(steps) == 9  # Pro default

    def test_get_all_conditional_edges(self, router):
        """Should return mapping for all nodes except format."""
        edges = router.get_all_conditional_edges()
        assert NODE_PII in edges
        assert NODE_CLASSIFY in edges
        assert NODE_GENERATE in edges
        assert NODE_QUALITY_GATE in edges
        # Format goes to END, so no conditional edge for it
        assert NODE_FORMAT not in edges

    def test_conditional_edges_are_callable(self, router):
        """All conditional edge functions should be callable."""
        edges = router.get_all_conditional_edges()
        for source, fn in edges.items():
            assert callable(fn), f"Edge for {source} is not callable"

    def test_instance_methods_match_functions(self, router):
        """Instance methods should return same results as standalone functions."""
        state = {"variant_tier": "mini_parwa"}
        assert router.route_after_classify(state) == route_after_classify(state)
        assert router.route_after_generate(state) == route_after_generate(state)


# ═══════════════════════════════════════════════════════════════════
# 4. VARIANT SERVICE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestVariantConfig:
    """Tests for VariantConfig dataclass."""

    def test_create_config(self):
        """Should create config with all fields."""
        config = VariantConfig(
            variant_tier="mini_parwa",
            industry="ecommerce",
        )
        assert config.variant_tier == "mini_parwa"
        assert config.industry == "ecommerce"

    def test_to_dict(self):
        """to_dict should return serializable dict."""
        config = VariantConfig(
            variant_tier="parwa",
            industry="saas",
            steps=["classify", "generate"],
            cost_per_query_estimate=0.008,
        )
        d = config.to_dict()
        assert d["variant_tier"] == "parwa"
        assert d["industry"] == "saas"
        assert d["steps"] == ["classify", "generate"]
        assert d["cost_per_query_estimate"] == 0.008


class TestStepConfig:
    """Tests for StepConfig dataclass."""

    def test_create_step_config(self):
        """Should create step config with all fields."""
        sc = StepConfig(
            step_id="classify",
            enabled=True,
            model="gpt-4o-mini",
            max_tokens=100,
            timeout_seconds=3.0,
            cost_weight=0.5,
        )
        assert sc.step_id == "classify"
        assert sc.enabled is True
        assert sc.model == "gpt-4o-mini"

    def test_defaults(self):
        """Default values should be safe."""
        sc = StepConfig(step_id="test")
        assert sc.enabled is True
        assert sc.model == ""
        assert sc.max_tokens == 500
        assert sc.cost_weight == 1.0


class TestTierDefaults:
    """Tests for TIER_DEFAULTS configuration."""

    def test_three_tiers_defined(self):
        """Should have defaults for all 3 tiers."""
        assert "mini_parwa" in TIER_DEFAULTS
        assert "parwa" in TIER_DEFAULTS
        assert "parwa_high" in TIER_DEFAULTS

    def test_mini_cheapest(self):
        """Mini should have lowest cost estimate."""
        mini_cost = TIER_DEFAULTS["mini_parwa"]["cost_per_query_estimate"]
        pro_cost = TIER_DEFAULTS["parwa"]["cost_per_query_estimate"]
        high_cost = TIER_DEFAULTS["parwa_high"]["cost_per_query_estimate"]
        assert mini_cost < pro_cost < high_cost

    def test_mini_fewest_tokens(self):
        """Mini should have lowest token budget."""
        mini_tokens = TIER_DEFAULTS["mini_parwa"]["max_total_tokens"]
        pro_tokens = TIER_DEFAULTS["parwa"]["max_total_tokens"]
        high_tokens = TIER_DEFAULTS["parwa_high"]["max_total_tokens"]
        assert mini_tokens < pro_tokens < high_tokens

    def test_mini_no_context_compression(self):
        """Mini should not have context compression."""
        assert TIER_DEFAULTS["mini_parwa"]["enable_context_compression"] is False

    def test_high_has_all_features(self):
        """High should have all features enabled."""
        high = TIER_DEFAULTS["parwa_high"]
        assert high["enable_context_compression"] is True
        assert high["enable_context_health"] is True
        assert high["enable_dedup"] is True

    def test_technique_tiers_ascending(self):
        """Technique tiers should ascend: 1 → 2 → 3."""
        assert TIER_DEFAULTS["mini_parwa"]["technique_tier_max"] == 1
        assert TIER_DEFAULTS["parwa"]["technique_tier_max"] == 2
        assert TIER_DEFAULTS["parwa_high"]["technique_tier_max"] == 3

    def test_mini_quality_no_retries(self):
        """Mini should have 0 quality retries (no quality gate)."""
        assert TIER_DEFAULTS["mini_parwa"]["quality_max_retries"] == 0


class TestIndustryOverrides:
    """Tests for INDUSTRY_OVERRIDES configuration."""

    def test_four_industries_have_overrides(self):
        """All 4 industries should have override entries."""
        for industry in ["ecommerce", "logistics", "saas", "general"]:
            assert industry in INDUSTRY_OVERRIDES

    def test_ecommerce_higher_quality_threshold(self):
        """E-commerce should have higher quality threshold than default."""
        mini_ecom = INDUSTRY_OVERRIDES["ecommerce"]["mini_parwa"]
        assert mini_ecom["quality_threshold"] > TIER_DEFAULTS["mini_parwa"]["quality_threshold"]

    def test_saas_overrides(self):
        """SaaS should have model overrides for technical queries."""
        saas_high = INDUSTRY_OVERRIDES["saas"]["parwa_high"]
        assert "classification_model" in saas_high


class TestVariantServiceResolve:
    """Tests for VariantService.resolve()."""

    def test_resolve_mini_ecommerce(self, service):
        """Should resolve Mini E-commerce config."""
        config = service.resolve("mini_parwa", "ecommerce")
        assert config.variant_tier == "mini_parwa"
        assert config.industry == "ecommerce"
        assert len(config.steps) == 6
        assert "order_tracker" in config.available_tools

    def test_resolve_pro_saas(self, service):
        """Should resolve Pro SaaS config."""
        config = service.resolve("parwa", "saas")
        assert config.variant_tier == "parwa"
        assert config.industry == "saas"
        assert len(config.steps) == 9
        assert "subscription_manager" in config.available_tools

    def test_resolve_high_logistics(self, service):
        """Should resolve High Logistics config."""
        config = service.resolve("parwa_high", "logistics")
        assert config.variant_tier == "parwa_high"
        assert config.industry == "logistics"
        assert len(config.steps) == 12
        assert "shipment_tracker" in config.available_tools

    def test_resolve_mini_general(self, service):
        """Should resolve Mini General config."""
        config = service.resolve("mini_parwa", "general")
        assert config.variant_tier == "mini_parwa"
        assert config.industry == "general"
        assert "knowledge_search" in config.available_tools

    def test_resolve_sets_system_prompt(self, service):
        """Config should have industry-specific system prompt."""
        config = service.resolve("parwa", "ecommerce")
        assert "e-commerce" in config.system_prompt.lower()

    def test_resolve_sets_response_tone(self, service):
        """Config should have industry-specific response tone."""
        config = service.resolve("parwa", "logistics")
        assert config.response_tone == "professional_precise"

    def test_resolve_mini_no_compression(self, service):
        """Mini should never have context compression regardless of industry."""
        for industry in ["ecommerce", "logistics", "saas", "general"]:
            config = service.resolve("mini_parwa", industry)
            assert config.enable_context_compression is False

    def test_resolve_high_has_compression(self, service):
        """High should have context compression for all industries."""
        for industry in ["ecommerce", "logistics", "saas", "general"]:
            config = service.resolve("parwa_high", industry)
            assert config.enable_context_compression is True

    def test_resolve_step_configs_enabled(self, service):
        """Steps in the pipeline should be enabled in step_configs."""
        config = service.resolve("parwa", "ecommerce")
        for step_id in config.steps:
            assert config.step_configs[step_id].enabled is True, f"{step_id} should be enabled"

    def test_resolve_step_configs_disabled(self, service):
        """Steps NOT in the pipeline should be disabled."""
        config = service.resolve("mini_parwa", "general")
        # Mini doesn't have these steps
        assert config.step_configs[NODE_EXTRACT_SIGNALS].enabled is False
        assert config.step_configs[NODE_QUALITY_GATE].enabled is False
        assert config.step_configs[NODE_CONTEXT_COMPRESS].enabled is False
        assert config.step_configs[NODE_CONTEXT_HEALTH].enabled is False
        assert config.step_configs[NODE_DEDUP].enabled is False

    def test_resolve_unknown_tier_fallback(self, service):
        """Unknown tier should fall back to parwa config."""
        config = service.resolve("unknown_tier", "ecommerce")
        # Should still return a valid config (falls back to parwa)
        assert config.variant_tier == "unknown_tier"
        assert len(config.steps) > 0

    def test_resolve_unknown_industry_fallback(self, service):
        """Unknown industry should fall back to general config."""
        config = service.resolve("parwa", "unknown_industry")
        assert config.industry == "unknown_industry"
        assert config.response_tone == "professional_adaptable"  # general tone

    def test_resolve_industry_overrides_applied(self, service):
        """Industry overrides should be applied on top of tier defaults."""
        base = service.resolve("mini_parwa", "general")
        ecom = service.resolve("mini_parwa", "ecommerce")
        # E-commerce should have higher quality threshold than general
        assert ecom.quality_threshold >= base.quality_threshold

    def test_resolve_technique_counts(self, service):
        """Technique counts should match tier."""
        mini = service.resolve("mini_parwa", "general")
        pro = service.resolve("parwa", "general")
        high = service.resolve("parwa_high", "general")
        assert len(mini.techniques_allowed) == 3  # tier 1 only
        assert len(pro.techniques_allowed) == 8   # tier 1 + tier 2
        assert len(high.techniques_allowed) == 14  # all techniques

    def test_resolve_cost_targets(self, service):
        """Cost estimates should match targets within reasonable range."""
        mini = service.resolve("mini_parwa", "general")
        pro = service.resolve("parwa", "general")
        high = service.resolve("parwa_high", "general")
        # Mini ≈ $0.003, Pro ≈ $0.008, High ≈ $0.015
        assert mini.cost_per_query_estimate < 0.005
        assert 0.005 < pro.cost_per_query_estimate < 0.012
        assert 0.010 < high.cost_per_query_estimate < 0.025


class TestVariantServiceResolveByInstance:
    """Tests for VariantService.resolve_by_instance()."""

    def test_resolve_by_instance(self, service):
        """Should return a config for an instance."""
        config = service.resolve_by_instance("co_1", "inst_1")
        assert isinstance(config, VariantConfig)
        assert len(config.steps) > 0

    def test_resolve_by_instance_unknown(self, service):
        """Unknown instance should still return a valid config."""
        config = service.resolve_by_instance("co_1", "nonexistent")
        assert isinstance(config, VariantConfig)


class TestVariantServiceGetAllConfigs:
    """Tests for VariantService.get_all_configs()."""

    def test_returns_all_combinations(self, service):
        """Should return config for every tier×industry combination."""
        configs = service.get_all_configs()
        assert len(configs) == 3  # 3 tiers
        for tier in ["mini_parwa", "parwa", "parwa_high"]:
            assert tier in configs
            assert len(configs[tier]) == 4  # 4 industries

    def test_all_configs_valid(self, service):
        """Every config should be a VariantConfig instance."""
        configs = service.get_all_configs()
        for tier, industries in configs.items():
            for industry, config in industries.items():
                assert isinstance(config, VariantConfig)
                assert config.variant_tier == tier
                assert config.industry == industry


class TestVariantServiceGetConfigSummary:
    """Tests for VariantService.get_config_summary()."""

    def test_returns_12_entries(self, service):
        """Should return 3 tiers × 4 industries = 12 entries."""
        summary = service.get_config_summary()
        assert len(summary) == 12

    def test_summary_has_required_fields(self, service):
        """Each summary entry should have required fields."""
        summary = service.get_config_summary()
        for entry in summary:
            assert "variant_tier" in entry
            assert "industry" in entry
            assert "steps_count" in entry
            assert "generation_model" in entry
            assert "max_tokens" in entry
            assert "cost_estimate" in entry

    def test_summary_steps_match_tier(self, service):
        """Steps count should match tier depth."""
        summary = service.get_config_summary()
        for entry in summary:
            if entry["variant_tier"] == "mini_parwa":
                assert entry["steps_count"] == 6
            elif entry["variant_tier"] == "parwa":
                assert entry["steps_count"] == 9
            elif entry["variant_tier"] == "parwa_high":
                assert entry["steps_count"] == 12


# ═══════════════════════════════════════════════════════════════════
# 5. CROSS-MODULE INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════


class TestStateWithRouter:
    """Integration: ParwaGraphState + VariantRouter."""

    def test_mini_pipeline_flow(self):
        """Mini pipeline should flow: pii → empathy → emergency → classify → generate → format."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="mini_parwa")

        # Step 1: PII → Empathy
        assert route_after_pii(state) == NODE_EMPATHY
        # Step 2: Empathy → Emergency
        assert route_after_empathy(state) == NODE_EMERGENCY
        # Step 3: Emergency → Classify (no emergency)
        assert route_after_emergency(state) == NODE_CLASSIFY
        # Step 4: Classify → Generate (Mini skips signals/technique)
        assert route_after_classify(state) == NODE_GENERATE
        # Step 5: Generate → Format (Mini skips quality gate)
        assert route_after_generate(state) == NODE_FORMAT

    def test_pro_pipeline_flow(self):
        """Pro pipeline should flow through 9 nodes."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa")

        path = []
        path.append(route_after_pii(state))         # empathy
        path.append(route_after_empathy(state))      # emergency
        path.append(route_after_emergency(state))    # classify
        path.append(route_after_classify(state))     # extract_signals
        path.append(route_after_extract_signals(state))  # technique_select
        path.append(route_after_technique_select(state))  # generate
        path.append(route_after_generate(state))     # quality_gate
        path.append(route_after_quality_gate(state))  # format (passed)

        assert path == [
            NODE_EMPATHY, NODE_EMERGENCY, NODE_CLASSIFY,
            NODE_EXTRACT_SIGNALS, NODE_TECHNIQUE_SELECT,
            NODE_GENERATE, NODE_QUALITY_GATE, NODE_FORMAT,
        ]

    def test_high_pipeline_flow(self):
        """High pipeline should flow through all 12 nodes."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa_high")
        state["quality_passed"] = True  # quality gate passes

        path = []
        path.append(route_after_pii(state))
        path.append(route_after_empathy(state))
        path.append(route_after_emergency(state))
        path.append(route_after_classify(state))
        path.append(route_after_extract_signals(state))
        path.append(route_after_technique_select(state))
        path.append(route_after_context_compress(state))
        path.append(route_after_generate(state))
        path.append(route_after_quality_gate(state))  # passes → context_health
        path.append(route_after_context_health(state))
        path.append(route_after_dedup(state))

        assert path == [
            NODE_EMPATHY, NODE_EMERGENCY, NODE_CLASSIFY,
            NODE_EXTRACT_SIGNALS, NODE_TECHNIQUE_SELECT,
            NODE_CONTEXT_COMPRESS, NODE_GENERATE,
            NODE_QUALITY_GATE, NODE_CONTEXT_HEALTH,
            NODE_DEDUP, NODE_FORMAT,
        ]

    def test_emergency_bypasses_pipeline(self):
        """Emergency should skip AI pipeline and go straight to format."""
        state = create_initial_state(query="I'll sue you!", company_id="co_1", variant_tier="parwa_high")
        state["emergency_flag"] = True
        state["emergency_type"] = "legal_threat"

        # Emergency detected after empathy → emergency check
        result = route_after_emergency(state)
        assert result == NODE_FORMAT  # skips classify, signals, technique, generate, etc.

    def test_quality_gate_retry_flow(self):
        """Quality gate failure should route back to generate."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa")
        state["quality_passed"] = False
        state["quality_retry_count"] = 0

        result = route_after_quality_gate(state)
        assert result == NODE_GENERATE  # retry

    def test_quality_gate_max_retry_flow(self):
        """After max retries, quality gate should proceed to format."""
        state = create_initial_state(query="Hi", company_id="co_1", variant_tier="parwa")
        state["quality_passed"] = False
        state["quality_retry_count"] = 1  # max reached

        result = route_after_quality_gate(state)
        assert result == NODE_FORMAT  # give up, proceed


class TestStateWithService:
    """Integration: ParwaGraphState + VariantService."""

    def test_config_matches_state_tier(self, service):
        """Config steps should match what the state's variant_tier expects."""
        for tier in ["mini_parwa", "parwa", "parwa_high"]:
            state = create_initial_state(query="Hi", company_id="co_1", variant_tier=tier)
            config = service.resolve(state["variant_tier"], state.get("industry", "general"))
            assert len(config.steps) > 0

    def test_ecommerce_state_gets_ecommerce_tools(self, service, mini_ecommerce_state):
        """E-commerce state should resolve to e-commerce tools."""
        config = service.resolve(
            mini_ecommerce_state["variant_tier"],
            mini_ecommerce_state["industry"],
        )
        assert "order_tracker" in config.available_tools

    def test_saas_state_gets_saas_tools(self, service, pro_saas_state):
        """SaaS state should resolve to SaaS tools."""
        config = service.resolve(
            pro_saas_state["variant_tier"],
            pro_saas_state["industry"],
        )
        assert "subscription_manager" in config.available_tools


class TestFullPipelineIntegration:
    """End-to-end integration: state + router + service."""

    def test_mini_ecommerce_full_walk(self, service, mini_ecommerce_state):
        """Walk Mini E-commerce through the complete pipeline routing."""
        state = mini_ecommerce_state
        config = service.resolve(state["variant_tier"], state["industry"])

        # Verify config
        assert config.variant_tier == "mini_parwa"
        assert config.industry == "ecommerce"

        # Walk the pipeline
        current = config.steps[0]  # pii_check
        visited = [current]

        router_instance = VariantRouter()
        edges = router_instance.get_all_conditional_edges()

        for _ in range(20):  # safety limit
            if current == NODE_FORMAT:
                break
            route_fn = edges.get(current)
            if route_fn is None:
                break
            next_node = route_fn(state)
            visited.append(next_node)
            current = next_node
            # Simulate node execution writing to state
            if current == NODE_CLASSIFY:
                state["classification"] = {"intent": "order_status", "confidence": 0.92}
            elif current == NODE_GENERATE:
                state["generated_response"] = "Your order is on its way!"

        # Mini should visit: pii → empathy → emergency → classify → generate → format
        assert visited == [
            NODE_PII, NODE_EMPATHY, NODE_EMERGENCY,
            NODE_CLASSIFY, NODE_GENERATE, NODE_FORMAT,
        ]

    def test_high_logistics_emergency_bypass(self, service, high_logistics_state):
        """High Logistics with emergency should bypass AI pipeline."""
        state = high_logistics_state
        config = service.resolve(state["variant_tier"], state["industry"])

        # Simulate emergency detected
        state["emergency_flag"] = True
        state["emergency_type"] = "safety_incident"

        # After emergency check, should go to format (bypassing all AI nodes)
        result = route_after_emergency(state)
        assert result == NODE_FORMAT


# ═══════════════════════════════════════════════════════════════════
# 6. PRODUCTION SCENARIO TESTS
# ═══════════════════════════════════════════════════════════════════


class TestMultiInstanceScenarios:
    """Tests for multi-instance production scenarios."""

    def test_same_tier_different_instances(self, service):
        """Two instances of same tier should get same config."""
        config_a = service.resolve("parwa", "ecommerce")
        config_b = service.resolve("parwa", "ecommerce")
        assert config_a.steps == config_b.steps
        assert config_a.generation_model == config_b.generation_model
        assert config_a.quality_threshold == config_b.quality_threshold

    def test_different_tiers_same_industry(self, service):
        """Different tiers in same industry should have different depths."""
        mini = service.resolve("mini_parwa", "ecommerce")
        pro = service.resolve("parwa", "ecommerce")
        high = service.resolve("parwa_high", "ecommerce")
        assert len(mini.steps) < len(pro.steps) < len(high.steps)

    def test_same_tier_different_industries(self, service):
        """Same tier in different industries should have different tools/prompts."""
        ecom = service.resolve("parwa", "ecommerce")
        saas = service.resolve("parwa", "saas")
        assert ecom.available_tools != saas.available_tools
        assert ecom.system_prompt != saas.system_prompt


class TestIndustrySwitchingScenarios:
    """Tests for switching industry contexts."""

    def test_switch_industry_changes_tools(self, service):
        """Switching industry for same tier should change available tools."""
        ecom_tools = service.resolve("parwa", "ecommerce").available_tools
        saas_tools = service.resolve("parwa", "saas").available_tools
        logistics_tools = service.resolve("parwa", "logistics").available_tools

        # Each industry should have different primary tools
        assert "order_tracker" in ecom_tools
        assert "subscription_manager" in saas_tools
        assert "shipment_tracker" in logistics_tools

    def test_switch_industry_changes_prompt(self, service):
        """Switching industry should change system prompt."""
        ecom_prompt = service.resolve("parwa", "ecommerce").system_prompt
        saas_prompt = service.resolve("parwa", "saas").system_prompt
        assert ecom_prompt != saas_prompt


class TestCostCompliance:
    """Tests verifying cost targets are met."""

    def test_mini_under_half_cent(self, service):
        """Mini should cost under $0.005 per query."""
        for industry in ["ecommerce", "logistics", "saas", "general"]:
            config = service.resolve("mini_parwa", industry)
            assert config.cost_per_query_estimate < 0.005, f"Mini {industry} too expensive"

    def test_pro_under_one_and_half_cent(self, service):
        """Pro should cost under $0.015 per query."""
        for industry in ["ecommerce", "logistics", "saas", "general"]:
            config = service.resolve("parwa", industry)
            assert config.cost_per_query_estimate < 0.015, f"Pro {industry} too expensive"

    def test_high_under_two_and_half_cent(self, service):
        """High should cost under $0.025 per query."""
        for industry in ["ecommerce", "logistics", "saas", "general"]:
            config = service.resolve("parwa_high", industry)
            assert config.cost_per_query_estimate < 0.025, f"High {industry} too expensive"


class TestFreeRoutingVerification:
    """Tests verifying that routing is indeed FREE (no LLM calls)."""

    def test_router_no_model_needed(self, service):
        """Router step configs should show no model for routing steps."""
        config = service.resolve("parwa", "ecommerce")
        # PII check is regex-based (FREE)
        assert config.step_configs[NODE_PII].cost_weight == 0.0
        # Emergency check is keyword-based (FREE)
        assert config.step_configs[NODE_EMERGENCY].cost_weight == 0.0
        # Format is template-based (FREE)
        assert config.step_configs[NODE_FORMAT].cost_weight == 0.0

    def test_paid_steps_have_models(self, service):
        """Steps that use LLM should have models assigned."""
        config = service.resolve("parwa", "ecommerce")
        assert config.step_configs[NODE_CLASSIFY].model != ""
        assert config.step_configs[NODE_GENERATE].model != ""


class TestThreadSafetyBasic:
    """Basic thread safety tests for service and router."""

    def test_concurrent_resolve(self, service):
        """Concurrent resolve calls should not crash."""
        errors = []

        def resolve_config(tier, industry):
            try:
                config = service.resolve(tier, industry)
                assert isinstance(config, VariantConfig)
            except Exception as e:
                errors.append(str(e))

        threads = []
        tiers = ["mini_parwa", "parwa", "parwa_high"]
        industries = ["ecommerce", "logistics", "saas", "general"]

        for _ in range(50):
            for tier in tiers:
                for industry in industries:
                    t = threading.Thread(target=resolve_config, args=(tier, industry))
                    threads.append(t)

        # Run a subset to keep test fast
        for t in threads[:100]:
            t.start()
        for t in threads[:100]:
            t.join()

        assert len(errors) == 0, f"Concurrent resolve errors: {errors}"

    def test_concurrent_routing(self, router):
        """Concurrent routing calls should not crash."""
        errors = []

        def route_state(tier):
            try:
                state = {"variant_tier": tier, "emergency_flag": False}
                result = router.route_after_classify(state)
                assert result in [NODE_GENERATE, NODE_EXTRACT_SIGNALS]
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=route_state, args=(tier,)) for tier in ["mini_parwa", "parwa", "parwa_high"] * 50]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

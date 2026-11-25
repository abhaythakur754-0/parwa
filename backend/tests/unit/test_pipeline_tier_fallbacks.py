"""Ensure removed Mini tiers never become the default for new tenants."""

import pytest
pytest.importorskip("langgraph")

from app.core.parwa_pipeline.nodes.node_2_smart_route import (
    _load_tenant_variants,
    clear_test_registry,
    set_test_variant,
)


def test_legacy_mini_test_variant_is_upgraded_to_parwa():
    clear_test_registry()
    try:
        set_test_variant("company-legacy", "mini", quota_total=100)
        result = _load_tenant_variants("company-legacy")
        assert result["available_tiers"] == ["parwa"]
        assert result["highest_tier_short"] == "parwa"
        assert result["highest_tier_db"] == "parwa"
    finally:
        clear_test_registry()


def test_unknown_tenant_tier_fallback_is_parwa(monkeypatch):
    import database.base

    def unavailable_session():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(database.base, "SessionLocal", unavailable_session)
    result = _load_tenant_variants("company-without-subscription")
    assert result["available_tiers"] == ["parwa"]
    assert result["highest_tier_short"] == "parwa"
    assert result["highest_tier_db"] == "parwa"

# Tenant-specific business facts must never be answered from a global canned template.
from app.core.lane_router import (
    GRATITUDE,
    LANE_FULL,
    LANE_INSTANT,
    SIMPLE_QUESTION,
    classify_message_type,
    generate_instant_response,
    get_lane_for_message_type,
)


def test_gratitude_stays_on_the_instant_lane():
    message_type = classify_message_type("Thanks for your help!")
    assert message_type == GRATITUDE
    assert get_lane_for_message_type(message_type) == LANE_INSTANT
    assert "welcome" in generate_instant_response(message_type, "Thanks!").lower()


@pytest.mark.parametrize(
    "question",
    [
        "What are your hours?",
        "What's your support email?",
        "Where are you located?",
        "How can I contact you?",
    ],
)
def test_business_specific_questions_use_the_tenant_knowledge_path(question):
    message_type = classify_message_type(question)
    assert message_type == SIMPLE_QUESTION
    assert get_lane_for_message_type(message_type) == LANE_FULL


def test_simple_question_cannot_use_a_global_canned_answer():
    with pytest.raises(ValueError, match="tenant knowledge-backed pipeline"):
        generate_instant_response(SIMPLE_QUESTION, "What are your hours?")


@pytest.mark.asyncio
async def test_reasoning_synthesis_receives_selected_tenant_agent_rules(monkeypatch):
    from app.core.parwa_pipeline.nodes import node_4_reasoning_engine as node4

    captured = {}

    async def fake_llm_call(prompt, **kwargs):
        captured["prompt"] = prompt
        return "A grounded customer response with the required next steps."

    monkeypatch.setattr(node4, "llm_call", fake_llm_call)
    await node4._synthesize_final_answer(
        query="How do I return an item?",
        sub_problems=["What is the return window?"],
        solutions=["The tenant policy allows returns within 30 days."],
        knowledge="Returns are accepted within 30 days.",
        context=(
            "Selected tenant agent: Returns Specialist (returns)\\n"
            "TENANT AGENT INSTRUCTIONS: Use a warm, concise tone.\\n"
            "TENANT AGENT RESTRICTIONS: Never promise a refund before inspection."
        ),
        ticket_type="return",
    )

    assert "Returns Specialist" in captured["prompt"]
    assert "Use a warm, concise tone" in captured["prompt"]
    assert "Never promise a refund before inspection" in captured["prompt"]

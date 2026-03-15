"""
Unit tests for the Smart Router pricing optimization logic.
"""
from shared.core_functions.pricing_optimizer import select_llm_tier


def test_select_llm_tier_simple_faq():
    """Test that a simple query routes to the 'light' tier."""
    prompt = "What are your business hours?"
    mock_flags = {}
    
    tier = select_llm_tier(prompt, mock_flags)
    assert tier == "light"


def test_select_llm_tier_long_prompt():
    """Test that a long verbose query routes to the 'heavy' tier."""
    prompt = "Hello there. I was wondering if you could help me. " * 10
    mock_flags = {}
    
    tier = select_llm_tier(prompt, mock_flags)
    assert tier == "heavy"


def test_select_llm_tier_heavy_keywords():
    """Test that high-risk intents trigger the 'heavy' tier regardless of length."""
    risky_prompts = [
        "I need a refund for my last purchase.",
        "Let me speak to a supervisor now.",
        "Your product is completely broken.",
        "Can you apply a 15% discount?"
    ]
    
    mock_flags = {}
    for prompt in risky_prompts:
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"


def test_select_llm_tier_invalid_input():
    """Test that invalid input gracefully defaults to 'light'."""
    assert select_llm_tier("", {}) == "light"
    assert select_llm_tier(None, {}) == "light"
    # Testing with wrong type (should fall back to light without crashing)
    assert select_llm_tier(12345, {}) == "light"

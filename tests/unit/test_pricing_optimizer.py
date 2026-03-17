"""
Unit tests for the Smart Router pricing optimization logic.

Tests cover:
- Basic tier selection (light/heavy)
- Heavy keyword detection
- Length-based routing
- Anti-arbitrage formula verification
- Edge cases and invalid input handling
"""
from shared.core_functions.pricing_optimizer import select_llm_tier


class TestBasicTierSelection:
    """Tests for basic tier selection functionality."""

    def test_select_llm_tier_simple_faq(self):
        """Test that a simple query routes to the 'light' tier."""
        prompt = "What are your business hours?"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "light"

    def test_select_llm_tier_simple_greeting(self):
        """Test that simple greetings route to light tier."""
        prompt = "Hi, how are you?"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "light"

    def test_select_llm_tier_product_inquiry(self):
        """Test that basic product inquiries route to light tier."""
        prompt = "Do you have this item in stock?"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "light"


class TestLongPromptRouting:
    """Tests for length-based routing."""

    def test_select_llm_tier_long_prompt(self):
        """Test that a long verbose query routes to the 'heavy' tier."""
        prompt = "Hello there. I was wondering if you could help me. " * 10
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_select_llm_tier_exactly_250_chars(self):
        """Test boundary case at exactly 250 characters."""
        prompt = "x" * 250
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        # At exactly 250, it should NOT be > 250, so light
        assert tier == "light"

    def test_select_llm_tier_251_chars(self):
        """Test boundary case at 251 characters."""
        prompt = "x" * 251
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"


class TestHeavyKeywordDetection:
    """Tests for heavy keyword detection and routing."""

    def test_select_llm_tier_heavy_keywords(self):
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

    def test_refund_keyword_detection(self):
        """Test that refund keyword triggers heavy tier."""
        prompt = "I want a refund"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_cancel_keyword_detection(self):
        """Test that cancel keyword triggers heavy tier."""
        prompt = "I want to cancel my order"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_supervisor_keyword_detection(self):
        """Test that supervisor keyword triggers heavy tier."""
        prompt = "Get me a supervisor"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_chargeback_keyword_detection(self):
        """Test that chargeback keyword triggers heavy tier."""
        prompt = "I will file a chargeback"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_manager_keyword_detection(self):
        """Test that manager keyword triggers heavy tier."""
        prompt = "I need to speak to a manager"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_broken_keyword_detection(self):
        """Test that broken keyword triggers heavy tier."""
        prompt = "This is broken"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_angry_keyword_detection(self):
        """Test that angry keyword triggers heavy tier."""
        prompt = "I am very angry"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_legal_keyword_detection(self):
        """Test that legal keyword triggers heavy tier."""
        prompt = "I will take legal action"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_discount_keyword_detection(self):
        """Test that discount keyword triggers heavy tier."""
        prompt = "Can I get a discount?"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"


class TestAntiArbitrageFormula:
    """
    Tests for anti-arbitrage formula verification.
    
    Anti-arbitrage ensures that:
    1. High-value customers (with feature flags) get proper routing
    2. Complex queries cannot be "gamed" to use cheaper tiers
    3. Cost optimization doesn't compromise quality for sensitive topics
    """

    def test_anti_arbitrage_short_refund_query(self):
        """
        Test that even short queries with refund intent go to heavy tier.
        
        This prevents users from shortening refund requests to get faster/cheaper
        processing - all refund-related queries must go through heavy tier for
        proper verification and audit trail.
        """
        short_refund = "refund please"
        mock_flags = {}
        
        tier = select_llm_tier(short_refund, mock_flags)
        assert tier == "heavy", "Short refund query should route to heavy tier"

    def test_anti_arbitrage_case_insensitive_keywords(self):
        """
        Test that heavy keywords are detected regardless of case.
        
        This prevents gaming the system by using different capitalization.
        """
        mock_flags = {}
        
        test_cases = [
            "REFUND MY ORDER",
            "Refund My Order",
            "ReFuNd My OrDeR",
            "I Need A SUPERVISOR",
            "LEGAL action required"
        ]
        
        for prompt in test_cases:
            tier = select_llm_tier(prompt, mock_flags)
            assert tier == "heavy", f"Case variation '{prompt}' should route to heavy tier"

    def test_anti_arbitrage_hidden_intent(self):
        """
        Test that heavy keywords embedded in longer text are still detected.
        
        This prevents gaming by hiding intent in verbose text.
        """
        mock_flags = {}
        
        test_cases = [
            "Hello, I was wondering if maybe possibly I could get a refund for my order?",
            "I'm very happy with your service but need to cancel due to circumstances",
            "Great product but I need to speak to a manager about something"
        ]
        
        for prompt in test_cases:
            tier = select_llm_tier(prompt, mock_flags)
            assert tier == "heavy", f"Hidden intent in '{prompt}' should route to heavy tier"

    def test_anti_arbitrage_feature_flags_do_not_override_heavy_intent(self):
        """
        Test that feature flags cannot override heavy intent detection.
        
        This ensures that even if a customer is on Mini PARWA (light tier only),
        heavy intent queries still get flagged for review (even if they must
        use light tier due to subscription limits).
        """
        heavy_intent_prompt = "I demand a refund immediately!"
        
        # Mini PARWA flags (light tier only)
        mini_parwa_flags = {
            "tier": "mini",
            "max_tier": "light",
            "features": ["basic_support"]
        }
        
        tier = select_llm_tier(heavy_intent_prompt, mini_parwa_flags)
        # The routing logic should still flag this as heavy intent
        # (actual tier enforcement is separate from intent detection)
        assert tier == "heavy", "Heavy intent should be detected regardless of feature flags"

    def test_anti_arbitrage_cost_sensitive_routing(self):
        """
        Test the cost optimization formula prioritizes quality for sensitive topics.
        
        Formula: cost_tier = max(intent_tier, length_tier)
        
        A short refund query (light by length) should still be heavy (by intent).
        """
        mock_flags = {}
        
        # Short refund query - light by length (20 chars), heavy by intent
        short_refund = "refund please"
        
        tier = select_llm_tier(short_refund, mock_flags)
        assert tier == "heavy", "Intent should override length in tier selection"

    def test_anti_arbitrage_no_keyword_false_positives(self):
        """
        Test that common words don't trigger false positives.
        
        Words like "cancel" should only trigger heavy tier in customer service context,
        not in phrases like "Can I cancel my subscription?" (which should still be heavy)
        but also shouldn't trigger on unrelated uses.
        """
        mock_flags = {}
        
        # These should be light (no heavy keywords, short length)
        light_queries = [
            "What is your name?",
            "How do I track my order?",
            "Where is my package?",
            "Thanks for your help!"
        ]
        
        for prompt in light_queries:
            tier = select_llm_tier(prompt, mock_flags)
            assert tier == "light", f"Simple query '{prompt}' should route to light tier"


class TestInvalidInputHandling:
    """Tests for edge cases and invalid input handling."""

    def test_select_llm_tier_invalid_input(self):
        """Test that invalid input gracefully defaults to 'light'."""
        assert select_llm_tier("", {}) == "light"
        assert select_llm_tier(None, {}) == "light"
        # Testing with wrong type (should fall back to light without crashing)
        assert select_llm_tier(12345, {}) == "light"

    def test_empty_feature_flags(self):
        """Test that empty feature flags work correctly."""
        prompt = "I need a refund"
        
        tier = select_llm_tier(prompt, {})
        assert tier == "heavy"

    def test_none_feature_flags(self):
        """Test that None feature flags work correctly."""
        prompt = "I need a refund"
        
        tier = select_llm_tier(prompt, None)
        assert tier == "heavy"

    def test_whitespace_only_prompt(self):
        """Test that whitespace-only prompts default to light."""
        tier = select_llm_tier("   ", {})
        assert tier == "light"

    def test_special_characters_prompt(self):
        """Test handling of prompts with special characters."""
        prompt = "I need a refund! @#$%^&*()"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_unicode_prompt(self):
        """Test handling of prompts with unicode characters."""
        prompt = "I need a refund 你好 مرحبا"
        mock_flags = {}
        
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"


class TestTierRoutingIntegration:
    """Integration tests for tier routing scenarios."""

    def test_multi_intent_query(self):
        """Test queries with multiple intents."""
        mock_flags = {}
        
        # Query with both cancel and refund
        prompt = "I want to cancel my order and get a refund"
        tier = select_llm_tier(prompt, mock_flags)
        assert tier == "heavy"

    def test_escalation_language(self):
        """Test escalation language triggers heavy tier."""
        mock_flags = {}
        
        escalation_prompts = [
            "I want to speak to your manager right now",
            "This is unacceptable, supervisor please",
            "Transfer me to someone who can actually help"
        ]
        
        for prompt in escalation_prompts:
            tier = select_llm_tier(prompt, mock_flags)
            # Note: "transfer" doesn't have heavy keyword, but let's check behavior
            if any(kw in prompt.lower() for kw in ["manager", "supervisor"]):
                assert tier == "heavy"

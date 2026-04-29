"""
Tests for SG-28: Edge-Case Handler Registry (~20 handlers)

Covers: 20 edge-case handlers, registry orchestration, variant
customization (GAP-023), timeout handling (GAP-022), handler chain
ordering, action escalation, and graceful degradation (BC-008).
Target: 80+ tests
"""

from unittest.mock import MagicMock, patch

import pytest

# Module-level stubs
CHAIN_TIMEOUT_SECONDS = None  # type: ignore[assignment,misc]
CONFIDENCE_THRESHOLD = None  # type: ignore[assignment,misc]
CONTEXT_EXPIRY_MINUTES = None  # type: ignore[assignment,misc]
DEFAULT_COMPETITORS = None  # type: ignore[assignment,misc]
DUPLICATE_SIMILARITY_THRESHOLD = None  # type: ignore[assignment,misc]
EdgeCaseAction = None  # type: ignore[assignment,misc]
EdgeCaseHandler = None  # type: ignore[assignment,misc]
EdgeCaseProcessingResult = None  # type: ignore[assignment,misc]
EdgeCaseRegistry = None  # type: ignore[assignment,misc]
EdgeCaseResult = None  # type: ignore[assignment,misc]
EdgeCaseSeverity = None  # type: ignore[assignment,misc]
EmptyQueryHandler = None  # type: ignore[assignment,misc]
EmojisOnlyHandler = None  # type: ignore[assignment,misc]
BelowConfidenceHandler = None  # type: ignore[assignment,misc]
BlockedUserHandler = None  # type: ignore[assignment,misc]
CodeBlocksHandler = None  # type: ignore[assignment,misc]
CompetitorMentionHandler = None  # type: ignore[assignment,misc]
DuplicateQueryHandler = None  # type: ignore[assignment,misc]
EmbeddedImagesHandler = None  # type: ignore[assignment,misc]
ExpiredContextHandler = None  # type: ignore[assignment,misc]
FAQMatchHandler = None  # type: ignore[assignment,misc]
LegalTerminologyHandler = None  # type: ignore[assignment,misc]
MaintenanceModeHandler = None  # type: ignore[assignment,misc]
MaliciousHTMLHandler = None  # type: ignore[assignment,misc]
MultiQuestionHandler = None  # type: ignore[assignment,misc]
NonExistentTicketHandler = None  # type: ignore[assignment,misc]
PricingRequestHandler = None  # type: ignore[assignment,misc]
SystemCommandsHandler = None  # type: ignore[assignment,misc]
TimeoutHandler = None  # type: ignore[assignment,misc]
TooLongQueryHandler = None  # type: ignore[assignment,misc]
UnsupportedLanguageHandler = None  # type: ignore[assignment,misc]
VARIANT_HANDLER_WHITELIST = None  # type: ignore[assignment,misc]
_detect_script = None  # type: ignore[assignment,misc]


# ═══════════════════════════════════════════════════════════════════════
# Fixtures — import source modules with mocked logger
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _mock_logger():
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.edge_case_handlers import (  # noqa: F401
            CHAIN_TIMEOUT_SECONDS,
            CONFIDENCE_THRESHOLD,
            CONTEXT_EXPIRY_MINUTES,
            DEFAULT_COMPETITORS,
            DUPLICATE_SIMILARITY_THRESHOLD,
            VARIANT_HANDLER_WHITELIST,
            BelowConfidenceHandler,
            BlockedUserHandler,
            CodeBlocksHandler,
            CompetitorMentionHandler,
            DuplicateQueryHandler,
            EdgeCaseAction,
            EdgeCaseHandler,
            EdgeCaseProcessingResult,
            EdgeCaseRegistry,
            EdgeCaseResult,
            EdgeCaseSeverity,
            EmbeddedImagesHandler,
            EmojisOnlyHandler,
            EmptyQueryHandler,
            ExpiredContextHandler,
            FAQMatchHandler,
            LegalTerminologyHandler,
            MaintenanceModeHandler,
            MaliciousHTMLHandler,
            MultiQuestionHandler,
            NonExistentTicketHandler,
            PricingRequestHandler,
            SystemCommandsHandler,
            TimeoutHandler,
            TooLongQueryHandler,
            UnsupportedLanguageHandler,
            _detect_script,
        )

        globals().update(
            {
                "CHAIN_TIMEOUT_SECONDS": CHAIN_TIMEOUT_SECONDS,
                "CONFIDENCE_THRESHOLD": CONFIDENCE_THRESHOLD,
                "CONTEXT_EXPIRY_MINUTES": CONTEXT_EXPIRY_MINUTES,
                "DEFAULT_COMPETITORS": DEFAULT_COMPETITORS,
                "DUPLICATE_SIMILARITY_THRESHOLD": DUPLICATE_SIMILARITY_THRESHOLD,
                "EdgeCaseAction": EdgeCaseAction,
                "EdgeCaseHandler": EdgeCaseHandler,
                "EdgeCaseProcessingResult": EdgeCaseProcessingResult,
                "EdgeCaseRegistry": EdgeCaseRegistry,
                "EdgeCaseResult": EdgeCaseResult,
                "EdgeCaseSeverity": EdgeCaseSeverity,
                "EmptyQueryHandler": EmptyQueryHandler,
                "EmojisOnlyHandler": EmojisOnlyHandler,
                "BelowConfidenceHandler": BelowConfidenceHandler,
                "BlockedUserHandler": BlockedUserHandler,
                "CodeBlocksHandler": CodeBlocksHandler,
                "CompetitorMentionHandler": CompetitorMentionHandler,
                "DuplicateQueryHandler": DuplicateQueryHandler,
                "EmbeddedImagesHandler": EmbeddedImagesHandler,
                "ExpiredContextHandler": ExpiredContextHandler,
                "FAQMatchHandler": FAQMatchHandler,
                "LegalTerminologyHandler": LegalTerminologyHandler,
                "MaintenanceModeHandler": MaintenanceModeHandler,
                "MaliciousHTMLHandler": MaliciousHTMLHandler,
                "MultiQuestionHandler": MultiQuestionHandler,
                "NonExistentTicketHandler": NonExistentTicketHandler,
                "PricingRequestHandler": PricingRequestHandler,
                "SystemCommandsHandler": SystemCommandsHandler,
                "TimeoutHandler": TimeoutHandler,
                "TooLongQueryHandler": TooLongQueryHandler,
                "UnsupportedLanguageHandler": UnsupportedLanguageHandler,
                "VARIANT_HANDLER_WHITELIST": VARIANT_HANDLER_WHITELIST,
                "_detect_script": _detect_script,
            }
        )


# ═══════════════════════════════════════════════════════════════════════
# 1. EmptyQueryHandler (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEmptyQueryHandler:
    def setup_method(self):
        self.handler = EmptyQueryHandler()

    def test_empty_string_blocks(self):
        assert self.handler.can_handle("", {}) is True
        result = self.handler.handle("", {})
        assert result.action == EdgeCaseAction.BLOCK
        assert result.handler_type == "empty_query"

    def test_whitespace_only_blocks(self):
        assert self.handler.can_handle("   \t\n  ", {}) is True
        result = self.handler.handle("   \t\n  ", {})
        assert result.action == EdgeCaseAction.BLOCK

    def test_none_input_raises(self):
        """None query has no null-guard; expects string input."""
        with pytest.raises(AttributeError):
            self.handler.can_handle(None, {})

    def test_normal_text_not_handled(self):
        assert self.handler.can_handle("Hello world", {}) is False

    def test_unicode_whitespace_blocks(self):
        """Unicode whitespace characters (em space, etc.) are stripped."""
        assert self.handler.can_handle("\u2003\u2009\u200a", {}) is True
        result = self.handler.can_handle("\u2003", {})
        assert result is True


# ═══════════════════════════════════════════════════════════════════════
# 2. TooLongQueryHandler (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestTooLongQueryHandler:
    def setup_method(self):
        self.handler = TooLongQueryHandler()

    def test_normal_query_not_handled(self):
        short = "Hello world, how are you today?"
        assert self.handler.can_handle(short, {}) is False

    def test_exactly_max_length_not_handled(self):
        query = "a" * 10000
        assert self.handler.can_handle(query, {}) is False

    def test_over_max_length_rewrites(self):
        query = "a" * 10001
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REWRITE
        assert result.rewritten_query is not None
        assert len(result.rewritten_query) == 10000

    def test_very_long_query_truncated_properly(self):
        query = "x" * 50000
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REWRITE
        assert len(result.rewritten_query) == 10000
        assert result.rewritten_query == "x" * 10000

    def test_truncated_query_is_meaningful_prefix(self):
        original = "abcdefgh" * 2000  # 16000 chars
        result = self.handler.handle(original, {})
        truncated = result.rewritten_query
        assert original.startswith(truncated)
        assert len(truncated) == 10000


# ═══════════════════════════════════════════════════════════════════════
# 3. UnsupportedLanguageHandler (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestUnsupportedLanguageHandler:
    def setup_method(self):
        self.handler = UnsupportedLanguageHandler()

    def test_english_text_not_handled(self):
        assert self.handler.can_handle("Hello, how are you?", {}) is False

    def test_chinese_characters_redirect(self):
        query = "\u4f60\u597d\u4e16\u754c"  # 你好世界
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REDIRECT
        assert result.redirect_target == "language_support"

    def test_arabic_characters_redirect(self):
        query = "\u0645\u0631\u062d\u0628\u0627"  # مرحبا
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REDIRECT
        assert "Arabic" in (result.metadata.get("detected_script") or "")

    def test_japanese_characters_redirect(self):
        query = "\u3053\u3093\u306b\u3061\u306f"  # こんにちは
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REDIRECT

    def test_mixed_english_cjk_handled(self):
        """Any non-Latin character in the query triggers the handler."""
        query = "Hello \u4f60\u597d world"  # Hello 你好 world
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REDIRECT


# ═══════════════════════════════════════════════════════════════════════
# 4. EmojisOnlyHandler (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEmojisOnlyHandler:
    def setup_method(self):
        self.handler = EmojisOnlyHandler()

    def test_emoji_pair_blocks(self):
        query = "\U0001f600\U0001f389"  # 😀🎉
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK

    def test_text_with_emoji_not_handled(self):
        """Query with text alongside emoji has alphanumeric content."""
        query = "Hello \U0001f600"
        assert self.handler.can_handle(query, {}) is False

    def test_multiple_emojis_blocks(self):
        query = "\U0001f600\U0001f389\U0001f60a\U0001f64c\U0001f4af\U0001f525"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK

    def test_empty_string_handled(self):
        """Empty string has no alphanumeric content → treated as emoji-only."""
        assert self.handler.can_handle("", {}) is True
        result = self.handler.handle("", {})
        assert result.action == EdgeCaseAction.BLOCK

    def test_numbers_with_emojis_not_handled(self):
        """Digits are non-emoji characters, so query is not emoji-only."""
        query = "123\U0001f525456"
        assert self.handler.can_handle(query, {}) is False


# ═══════════════════════════════════════════════════════════════════════
# 5. CodeBlocksHandler (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCodeBlocksHandler:
    def setup_method(self):
        self.handler = CodeBlocksHandler()

    def test_fenced_code_block_proceeds(self):
        query = "```python\nprint('hello')\n```"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.PROCEED
        assert result.metadata["code_block_count"] == 1

    def test_no_code_blocks_not_handled(self):
        query = "How do I fix my code?"
        assert self.handler.can_handle(query, {}) is False

    def test_multiple_code_blocks_proceeds(self):
        query = "```python\nx = 1\n```\nSome text\n```javascript\ny = 2\n```"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.PROCEED
        assert result.metadata["code_block_count"] == 2

    def test_inline_code_only_not_handled(self):
        """Single backtick inline code does NOT match fenced blocks."""
        query = "Use `print()` to debug"
        assert self.handler.can_handle(query, {}) is False


# ═══════════════════════════════════════════════════════════════════════
# 6. DuplicateQueryHandler (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestDuplicateQueryHandler:
    def setup_method(self):
        self.handler = DuplicateQueryHandler()

    def test_no_recent_queries_not_handled(self):
        assert self.handler.can_handle("Hello", {}) is False
        assert self.handler.can_handle("Hello", {"recent_queries": []}) is False

    def test_different_query_not_handled(self):
        ctx = {"recent_queries": ["How do I reset my password?"]}
        assert self.handler.can_handle("What is your pricing?", ctx) is False

    def test_near_duplicate_rewrites(self):
        original = "I want a refund for my order please"
        near_dup = "I want a refund for my order please!"  # 1-char diff
        ctx = {"recent_queries": [original]}
        assert self.handler.can_handle(near_dup, ctx) is True
        result = self.handler.handle(near_dup, ctx)
        assert result.action == EdgeCaseAction.REWRITE
        assert result.metadata["similarity_ratio"] > DUPLICATE_SIMILARITY_THRESHOLD

    def test_exact_duplicate_rewrites(self):
        query = "Reset my password"
        ctx = {"recent_queries": [query]}
        assert self.handler.can_handle(query, ctx) is True
        result = self.handler.handle(query, ctx)
        assert result.action == EdgeCaseAction.REWRITE
        assert result.metadata["similarity_ratio"] == 1.0

    def test_similar_but_different_enough(self):
        """Queries below the 0.9 similarity threshold are not duplicates."""
        ctx = {"recent_queries": ["How do I cancel my subscription plan?"]}
        query = "What is the weather today?"
        assert self.handler.can_handle(query, ctx) is False

    def test_non_string_in_recent_skipped(self):
        """Non-string entries in recent_queries are safely skipped."""
        ctx = {"recent_queries": [123, None, "different query"]}
        assert self.handler.can_handle("Hello world", ctx) is False


# ═══════════════════════════════════════════════════════════════════════
# 7. MultiQuestionHandler (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestMultiQuestionHandler:
    def setup_method(self):
        self.handler = MultiQuestionHandler()

    def test_single_question_not_handled(self):
        """'How are you?' = 1(?) + how + are = 3 signals, not > 3."""
        assert self.handler.can_handle("How are you?", {}) is False

    def test_two_question_marks_no_words_not_handled(self):
        """Two question marks with no question words: 2 signals ≤ 3."""
        assert self.handler.can_handle("Really? Truly?", {}) is False

    def test_many_questions_handled(self):
        """Multiple questions with question words exceed threshold."""
        query = "How are you? What is this? When did it start?"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.PROCEED
        assert result.severity == EdgeCaseSeverity.MEDIUM.value

    def test_question_count_with_words(self):
        """_count_questions aggregates ? marks and question-starting words."""
        query = "How are you? What is this? When did it start?"
        result = self.handler.handle(query, {})
        count = result.metadata["question_count"]
        # 3 question marks + how + are + what + is + when + did = 9
        assert count > 3


# ═══════════════════════════════════════════════════════════════════════
# 8. MaliciousHTMLHandler (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestMaliciousHTMLHandler:
    def setup_method(self):
        self.handler = MaliciousHTMLHandler()

    def test_normal_text_not_handled(self):
        assert self.handler.can_handle("I need help with my account", {}) is False

    def test_script_tag_blocks(self):
        query = "<script>alert(1)</script>"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK
        assert result.severity == EdgeCaseSeverity.CRITICAL.value

    def test_javascript_uri_blocks(self):
        query = "javascript:void(0)"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK

    def test_iframe_tag_blocks(self):
        query = '<iframe src="https://evil.com"></iframe>'
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK

    def test_onerror_attribute_blocks(self):
        query = '<img onerror="alert(1)" src="x">'
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK

    def test_sql_injection_in_script_blocks(self):
        """SQL injection embedded in script tag caught by HTML handler."""
        query = "<script>DELETE FROM users</script>"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK


# ═══════════════════════════════════════════════════════════════════════
# 9. FAQMatchHandler (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestFAQMatchHandler:
    def setup_method(self):
        self.handler = FAQMatchHandler()

    def test_exact_faq_match_redirects(self):
        query = "how do i reset my password"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REDIRECT
        assert result.redirect_target == "faq"
        assert "password" in result.metadata["faq_answer"]

    def test_non_faq_query_not_handled(self):
        query = "what is the meaning of life"
        assert self.handler.can_handle(query, {}) is False

    def test_multiple_faq_keys_first_match(self):
        """When query matches an FAQ key, handle returns that key's answer."""
        query = "how do i cancel my subscription"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REDIRECT
        assert result.metadata["matched_faq"] == query

    def test_case_insensitive_match(self):
        query = "HOW DO I CONTACT SUPPORT"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REDIRECT
        assert result.redirect_target == "faq"

    def test_partial_match_not_handled(self):
        """Partial/incomplete FAQ query does not match."""
        query = "reset my password"
        assert self.handler.can_handle(query, {}) is False

    def test_custom_faq_table_override(self):
        """Context faq_table overrides the default FAQ table."""
        custom_faq = {"custom question": "custom answer"}
        ctx = {"faq_table": custom_faq}
        assert self.handler.can_handle("custom question", ctx) is True
        result = self.handler.handle("custom question", ctx)
        assert result.metadata["faq_answer"] == "custom answer"


# ═══════════════════════════════════════════════════════════════════════
# 10. BlockedUserHandler (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestBlockedUserHandler:
    def setup_method(self):
        self.handler = BlockedUserHandler()

    def test_normal_user_not_handled(self):
        ctx = {"user_status": "active"}
        assert self.handler.can_handle("Hello", ctx) is False

    def test_blocked_user_is_blocked_flag(self):
        ctx = {"is_blocked": True}
        assert self.handler.can_handle("Hello", ctx) is True
        result = self.handler.handle("Hello", ctx)
        assert result.action == EdgeCaseAction.BLOCK
        assert result.severity == EdgeCaseSeverity.CRITICAL.value

    def test_suspended_user_blocks(self):
        ctx = {"user_status": "suspended"}
        assert self.handler.can_handle("Hello", ctx) is True
        result = self.handler.handle("Hello", ctx)
        assert result.action == EdgeCaseAction.BLOCK

    def test_no_user_status_not_handled(self):
        ctx = {}
        assert self.handler.can_handle("Hello", ctx) is False

    def test_banned_user_blocks(self):
        ctx = {"user_status": "banned"}
        assert self.handler.can_handle("Hello", ctx) is True
        result = self.handler.handle("Hello", ctx)
        assert result.action == EdgeCaseAction.BLOCK


# ═══════════════════════════════════════════════════════════════════════
# 11. MaintenanceModeHandler (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestMaintenanceModeHandler:
    def setup_method(self):
        self.handler = MaintenanceModeHandler()

    def test_system_active_not_handled(self):
        ctx = {"maintenance_mode": False}
        assert self.handler.can_handle("Hello", ctx) is False

    def test_maintenance_mode_context_blocks(self):
        ctx = {"maintenance_mode": True}
        assert self.handler.can_handle("Hello", ctx) is True
        result = self.handler.handle("Hello", ctx)
        assert result.action == EdgeCaseAction.BLOCK
        assert result.severity == EdgeCaseSeverity.HIGH.value

    def test_maintenance_via_system_status_blocks(self):
        """system_status.maintenance=True simulates Redis-sourced flag."""
        ctx = {"system_status": {"maintenance": True}}
        assert self.handler.can_handle("Hello", ctx) is True
        result = self.handler.handle("Hello", ctx)
        assert result.action == EdgeCaseAction.BLOCK

    def test_no_maintenance_info_not_handled(self):
        ctx = {}
        assert self.handler.can_handle("Hello", ctx) is False

    def test_custom_maintenance_message(self):
        ctx = {
            "system_status": {
                "maintenance": True,
                "maintenance_message": "Back in 5 minutes",
            },
        }
        result = self.handler.handle("Hello", ctx)
        assert "Back in 5 minutes" in result.reason


# ═══════════════════════════════════════════════════════════════════════
# 12. SystemCommandsHandler (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestSystemCommandsHandler:
    def setup_method(self):
        self.handler = SystemCommandsHandler()

    def test_normal_text_not_handled(self):
        assert self.handler.can_handle("How do I use the dashboard?", {}) is False

    def test_admin_command_blocks(self):
        query = "/admin dashboard"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK
        assert result.severity == EdgeCaseSeverity.CRITICAL.value

    def test_sudo_command_blocks(self):
        query = "sudo rm -rf /"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK

    def test_drop_table_blocks(self):
        query = "DROP TABLE users"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK

    def test_system_command_blocks(self):
        query = "/system restart"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK

    def test_delete_from_blocks(self):
        query = "DELETE FROM orders WHERE 1=1"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.BLOCK


# ═══════════════════════════════════════════════════════════════════════
# 13. PricingRequestHandler (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestPricingRequestHandler:
    def setup_method(self):
        self.handler = PricingRequestHandler()

    def test_pricing_keywords_redirect(self):
        query = "What is the pricing for enterprise plans?"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REDIRECT
        assert result.redirect_target == "billing_support"

    def test_normal_query_not_handled(self):
        query = "How do I reset my password?"
        assert self.handler.can_handle(query, {}) is False

    def test_plan_keyword_redirects(self):
        query = "I want to change my plan"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REDIRECT
        assert "plan" in result.metadata["matched_keywords"]

    def test_upgrade_keyword_redirects(self):
        query = "I'd like to upgrade my account"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.REDIRECT
        assert "upgrade" in result.metadata["matched_keywords"]


# ═══════════════════════════════════════════════════════════════════════
# 14. LegalTerminologyHandler (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestLegalTerminologyHandler:
    def setup_method(self):
        self.handler = LegalTerminologyHandler()

    def test_legal_keywords_escalate(self):
        query = "I am filing a legal action against your company"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.ESCALATE
        assert result.severity == EdgeCaseSeverity.HIGH.value

    def test_normal_query_not_handled(self):
        query = "My order hasn't arrived yet"
        assert self.handler.can_handle(query, {}) is False

    def test_lawsuit_escalates(self):
        query = "I will file a lawsuit"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.ESCALATE
        assert "lawsuit" in result.metadata["matched_keywords"]

    def test_gdpr_escalates(self):
        query = "This is a GDPR compliance question"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.ESCALATE
        assert "gdpr" in result.metadata["matched_keywords"]

    def test_breach_of_contract_escalates(self):
        query = "This is a breach of contract"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.ESCALATE


# ═══════════════════════════════════════════════════════════════════════
# 15. CompetitorMentionHandler (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestCompetitorMentionHandler:
    def setup_method(self):
        self.handler = CompetitorMentionHandler()

    def test_competitor_name_proceeds(self):
        query = "I am switching from Zendesk to your product"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.PROCEED
        assert "zendesk" in result.metadata["competitors_mentioned"]

    def test_normal_query_not_handled(self):
        query = "How do I track my shipment?"
        assert self.handler.can_handle(query, {}) is False

    def test_multiple_competitors_proceeds(self):
        query = "We use Zendesk and Freshdesk, considering Intercom"
        assert self.handler.can_handle(query, {}) is True
        result = self.handler.handle(query, {})
        assert result.action == EdgeCaseAction.PROCEED
        mentioned = result.metadata["competitors_mentioned"]
        assert len(mentioned) >= 3

    def test_custom_competitor_list(self):
        """Context competitors overrides default competitor list."""
        custom = ["acme_tools", "rival_app"]
        ctx = {"competitors": custom}
        query = "We currently use acme_tools"
        assert self.handler.can_handle(query, ctx) is True
        result = self.handler.handle(query, ctx)
        assert "acme_tools" in result.metadata["competitors_mentioned"]

    def test_invalid_competitors_falls_back(self):
        """Non-list/set competitors in context falls back to defaults."""
        ctx = {"competitors": "not a list"}
        query = "We use zendesk"
        assert self.handler.can_handle(query, ctx) is True


# ═══════════════════════════════════════════════════════════════════════
# 16. EdgeCaseRegistry (10 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestEdgeCaseRegistry:
    def test_registry_has_twenty_handlers(self):
        registry = EdgeCaseRegistry(variant="parwa")
        assert len(registry._handlers) == 20

    def test_process_normal_query_proceeds(self):
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("How do I reset my password?")
        assert result.final_action == EdgeCaseAction.PROCEED
        assert result.blocked is False

    def test_process_empty_query_blocks(self):
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("")
        assert result.blocked is True
        assert result.final_action == EdgeCaseAction.BLOCK
        assert "empty_query" in result.handlers_triggered

    def test_handler_chain_stops_on_block(self):
        """When a handler returns BLOCK, subsequent handlers are skipped."""
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("<script>alert(1)</script>")
        assert result.blocked is True
        assert result.final_action == EdgeCaseAction.BLOCK
        # Empty query handler runs first (priority 1) but doesn't match.
        # MaliciousHTML handler (priority 10) matches and BLOCKs.
        assert "malicious_html" in result.handlers_triggered

    def test_multiple_rewrites_collected(self):
        """Registry tracks rewrites; last rewrite wins for final_query."""
        registry = EdgeCaseRegistry(variant="parwa")
        long_query = "a" * 15000
        ctx = {
            "recent_queries": [long_query],
        }
        result = registry.process(long_query, ctx)
        assert result.rewritten is True
        assert len(result.final_query) == 10000

    def test_processing_result_structure(self):
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("Hello")
        assert isinstance(result, EdgeCaseProcessingResult)
        assert hasattr(result, "final_action")
        assert hasattr(result, "final_query")
        assert hasattr(result, "handlers_triggered")
        assert hasattr(result, "blocked")
        assert hasattr(result, "rewritten")
        assert hasattr(result, "processing_time_ms")
        assert hasattr(result, "results")

    def test_processing_time_ms_positive(self):
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("Hello world")
        assert result.processing_time_ms >= 0.0

    def test_handlers_triggered_populated(self):
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("")
        assert isinstance(result.handlers_triggered, list)
        assert len(result.handlers_triggered) >= 1

    def test_blocked_flag_set_correctly(self):
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("Hello world")
        assert result.blocked is False

        result2 = registry.process("")
        assert result2.blocked is True

    def test_rewritten_flag_set_correctly(self):
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("Hello world")
        assert result.rewritten is False

    def test_faq_redirect_in_registry(self):
        """FAQ match produces REDIRECT action through the registry."""
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("how do i upgrade my plan")
        assert result.final_action == EdgeCaseAction.REDIRECT
        assert "faq_match" in result.handlers_triggered

    def test_pricing_redirect_in_registry(self):
        """Pricing keywords produce REDIRECT action."""
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("What is the enterprise pricing?")
        assert result.final_action == EdgeCaseAction.REDIRECT

    def test_legal_escalation_in_registry(self):
        """Legal terminology produces ESCALATE action."""
        registry = EdgeCaseRegistry(variant="parwa")
        result = registry.process("I need to consult an attorney about a lawsuit")
        assert result.final_action == EdgeCaseAction.ESCALATE


# ═══════════════════════════════════════════════════════════════════════
# 17. VariantCustomization (4 tests) — GAP-023
# ═══════════════════════════════════════════════════════════════════════


class TestVariantCustomization:
    def test_mini_parwa_fewer_handlers(self):
        """mini_parwa runs only whitelisted handlers (10)."""
        registry = EdgeCaseRegistry(variant="mini_parwa")
        assert len(registry._handlers) == 10
        handler_types = {h.handler_type for h in registry._handlers}
        assert "empty_query" in handler_types
        assert "malicious_html" in handler_types
        # These should NOT be in mini_parwa
        assert "duplicate_query" not in handler_types
        assert "competitor_mention" not in handler_types

    def test_parwa_all_handlers(self):
        """parwa variant runs all 20 handlers."""
        registry = EdgeCaseRegistry(variant="parwa")
        assert len(registry._handlers) == 20

    def test_parwa_high_all_handlers(self):
        """parwa_high variant runs all 20 handlers."""
        registry = EdgeCaseRegistry(variant="parwa_high")
        assert len(registry._handlers) == 20

    def test_unknown_variant_all_handlers(self):
        """Unknown variant has no whitelist → all handlers."""
        registry = EdgeCaseRegistry(variant="unknown_variant")
        assert len(registry._handlers) == 20

    def test_mini_parwa_whitelist_matches_constant(self):
        """Verify mini_parwa handler set matches VARIANT_HANDLER_WHITELIST."""
        expected = set(VARIANT_HANDLER_WHITELIST["mini_parwa"])
        registry = EdgeCaseRegistry(variant="mini_parwa")
        actual = {h.handler_type for h in registry._handlers}
        assert actual == expected


# ═══════════════════════════════════════════════════════════════════════
# 18. TimeoutHandling (3 tests) — GAP-022 / BC-008
# ═══════════════════════════════════════════════════════════════════════


class TestTimeoutHandling:
    def test_handler_exception_skipped(self):
        """A handler that raises in can_handle is gracefully skipped."""
        registry = EdgeCaseRegistry(variant="parwa")

        class BrokenHandler(EdgeCaseHandler):
            @property
            def handler_type(self):
                return "broken"

            @property
            def priority(self):
                return 0  # Runs first

            def can_handle(self, query, context):
                raise RuntimeError("broken handler")

            def handle(self, query, context):
                return EdgeCaseResult(
                    handler_type="broken",
                    action=EdgeCaseAction.BLOCK,
                )

        registry.register(BrokenHandler())
        result = registry.process("Hello")
        # Process should not crash; broken handler is skipped
        assert isinstance(result, EdgeCaseProcessingResult)
        assert "broken" not in result.handlers_triggered

    def test_handler_exception_in_handle_skipped(self):
        """A handler that raises in handle() is gracefully skipped."""
        registry = EdgeCaseRegistry(variant="parwa")

        class CrashingHandleHandler(EdgeCaseHandler):
            @property
            def handler_type(self):
                return "crashing_handle"

            @property
            def priority(self):
                return 0

            def can_handle(self, query, context):
                return True  # Always claims to handle

            def handle(self, query, context):
                raise RuntimeError("handle() crashed")

        registry.register(CrashingHandleHandler())
        result = registry.process("Hello")
        assert isinstance(result, EdgeCaseProcessingResult)
        assert "crashing_handle" not in result.handlers_triggered

    def test_timeout_does_not_crash_process(self):
        """Registry process() returns valid result even with handler errors."""
        registry = EdgeCaseRegistry(variant="parwa")

        class ErrorHandler(EdgeCaseHandler):
            @property
            def handler_type(self):
                return "always_errors"

            @property
            def priority(self):
                return 0

            def can_handle(self, query, context):
                return True

            def handle(self, query, context):
                raise ValueError("unexpected error")

        registry.register(ErrorHandler())
        result = registry.process("test query")
        assert result.processing_time_ms >= 0.0
        assert isinstance(result.handlers_triggered, list)


# ═══════════════════════════════════════════════════════════════════════
# 19. Helper Utilities (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestHelperUtilities:
    def test_detect_script_latin_none(self):
        assert _detect_script("Hello world") is None

    def test_detect_script_cjk(self):
        result = _detect_script("你好")
        assert result == "CJK"

    def test_detect_script_arabic(self):
        result = _detect_script("مرحبا")
        assert result == "Arabic"

    def test_detect_script_japanese_hiragana(self):
        result = _detect_script("こんにちは")
        assert result == "Japanese"

    def test_detect_script_korean(self):
        result = _detect_script("안녕하세요")
        assert result == "Korean"


# ═══════════════════════════════════════════════════════════════════════
# 20. Data Classes (6 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestDataClasses:
    def test_edge_case_result_defaults(self):
        result = EdgeCaseResult(
            handler_type="test",
            action=EdgeCaseAction.PROCEED,
        )
        assert result.handler_type == "test"
        assert result.action == EdgeCaseAction.PROCEED
        assert result.severity == EdgeCaseSeverity.LOW.value
        assert result.rewritten_query is None
        assert result.redirect_target is None
        assert result.reason == ""
        assert result.metadata == {}

    def test_edge_case_result_full(self):
        result = EdgeCaseResult(
            handler_type="custom",
            action=EdgeCaseAction.BLOCK,
            severity=EdgeCaseSeverity.CRITICAL.value,
            rewritten_query="cleaned",
            redirect_target="somewhere",
            reason="test reason",
            metadata={"key": "value"},
        )
        assert result.rewritten_query == "cleaned"
        assert result.redirect_target == "somewhere"
        assert result.metadata["key"] == "value"

    def test_edge_case_processing_result_defaults(self):
        result = EdgeCaseProcessingResult()
        assert result.final_action == EdgeCaseAction.PROCEED
        assert result.final_query == ""
        assert result.handlers_triggered == []
        assert result.blocked is False
        assert result.rewritten is False
        assert result.processing_time_ms == 0.0
        assert result.results == []

    def test_edge_case_action_enum_values(self):
        assert EdgeCaseAction.PROCEED == "proceed"
        assert EdgeCaseAction.REWRITE == "rewrite"
        assert EdgeCaseAction.REDIRECT == "redirect"
        assert EdgeCaseAction.BLOCK == "block"
        assert EdgeCaseAction.ESCALATE == "escalate"

    def test_edge_case_severity_enum_values(self):
        assert EdgeCaseSeverity.LOW == "low"
        assert EdgeCaseSeverity.MEDIUM == "medium"
        assert EdgeCaseSeverity.HIGH == "high"
        assert EdgeCaseSeverity.CRITICAL == "critical"

    def test_processing_result_mutation(self):
        result = EdgeCaseProcessingResult()
        result.handlers_triggered.append("test_handler")
        result.blocked = True
        assert len(result.handlers_triggered) == 1
        assert result.blocked is True


# ═══════════════════════════════════════════════════════════════════════
# 21. Additional Handler Edge Cases (9 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestAdditionalHandlerEdgeCases:
    def test_embedded_images_handler_proceeds(self):
        handler = EmbeddedImagesHandler()
        query = "See this screenshot [image] attached"
        assert handler.can_handle(query, {}) is True
        result = handler.handle(query, {})
        assert result.action == EdgeCaseAction.PROCEED
        assert "[image]" in result.metadata["markers_found"]

    def test_non_existent_ticket_handler_rewrites(self):
        handler = NonExistentTicketHandler()
        ctx = {
            "referenced_ticket_id": "TKT-999",
            "ticket_exists": False,
        }
        assert handler.can_handle("Check ticket TKT-999", ctx) is True
        result = handler.handle("Check ticket TKT-999", ctx)
        assert result.action == EdgeCaseAction.REWRITE
        assert result.metadata["referenced_ticket_id"] == "TKT-999"

    def test_non_existent_ticket_no_id_not_handled(self):
        handler = NonExistentTicketHandler()
        assert handler.can_handle("Check my ticket", {}) is False

    def test_non_existent_ticket_exists_not_handled(self):
        handler = NonExistentTicketHandler()
        ctx = {
            "referenced_ticket_id": "TKT-123",
            "ticket_exists": True,
        }
        assert handler.can_handle("Check ticket TKT-123", ctx) is False

    def test_below_confidence_handler_escalates(self):
        handler = BelowConfidenceHandler()
        ctx = {"confidence_score": 0.2}
        assert handler.can_handle("Hello", ctx) is True
        result = handler.handle("Hello", ctx)
        assert result.action == EdgeCaseAction.ESCALATE
        assert result.metadata["confidence_score"] == 0.2

    def test_below_confidence_above_threshold_not_handled(self):
        handler = BelowConfidenceHandler()
        ctx = {"confidence_score": 0.9}
        assert handler.can_handle("Hello", ctx) is False

    def test_below_confidence_no_score_not_handled(self):
        handler = BelowConfidenceHandler()
        assert handler.can_handle("Hello", {}) is False

    def test_timeout_handler_not_triggered_normally(self):
        """TimeoutHandler only fires when elapsed exceeds threshold."""
        handler = TimeoutHandler()
        ctx = {"_processing_elapsed_ms": 100}
        assert handler.can_handle("Hello", ctx) is False

    def test_timeout_handler_triggered_when_exceeded(self):
        handler = TimeoutHandler()
        ctx = {"_processing_elapsed_ms": 15000}  # > 10000ms
        assert handler.can_handle("Hello", ctx) is True
        result = handler.handle("Hello", ctx)
        assert result.action == EdgeCaseAction.ESCALATE


# ═══════════════════════════════════════════════════════════════════════
# 22. Registry Advanced Features (5 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestRegistryAdvanced:
    def test_get_handler_returns_registered(self):
        registry = EdgeCaseRegistry(variant="parwa")
        handler = registry.get_handler("empty_query")
        assert handler is not None
        assert handler.handler_type == "empty_query"

    def test_get_handler_unknown_returns_none(self):
        registry = EdgeCaseRegistry(variant="parwa")
        assert registry.get_handler("nonexistent") is None

    def test_extra_handlers_registration(self):
        """Custom handlers can be added via extra_handlers."""

        class CustomHandler(EdgeCaseHandler):
            @property
            def handler_type(self):
                return "custom_handler"

            @property
            def priority(self):
                return 100

            def can_handle(self, query, context):
                return query == "TRIGGER_CUSTOM"

            def handle(self, query, context):
                return EdgeCaseResult(
                    handler_type="custom_handler",
                    action=EdgeCaseAction.ESCALATE,
                )

        registry = EdgeCaseRegistry(
            variant="parwa",
            extra_handlers=[CustomHandler()],
        )
        result = registry.process("TRIGGER_CUSTOM")
        assert "custom_handler" in result.handlers_triggered
        assert result.final_action == EdgeCaseAction.ESCALATE

    def test_handlers_sorted_by_priority(self):
        """Registry handlers are sorted by priority (ascending)."""
        registry = EdgeCaseRegistry(variant="parwa")
        priorities = [h.priority for h in registry._handlers]
        assert priorities == sorted(priorities)

    def test_duplicate_handler_type_replaced(self):
        """Registering a handler with existing type replaces the old one."""
        registry = EdgeCaseRegistry(variant="parwa")

        class CustomCode(EdgeCaseHandler):
            @property
            def handler_type(self):
                return "code_blocks"

            @property
            def priority(self):
                return 5

            def can_handle(self, query, context):
                return query == "TRIGGER_CODE_CUSTOM"

            def handle(self, query, context):
                return EdgeCaseResult(
                    handler_type="code_blocks",
                    action=EdgeCaseAction.ESCALATE,
                    reason="custom code handler",
                )

        registry.register(CustomCode())
        # Standard code blocks no longer handled (custom handler has narrow
        # match)
        result = registry.process("```python\nx=1\n```")
        assert "code_blocks" not in result.handlers_triggered
        # Custom trigger works
        result2 = registry.process("TRIGGER_CODE_CUSTOM")
        assert "code_blocks" in result2.handlers_triggered
        assert result2.final_action == EdgeCaseAction.ESCALATE


# ═══════════════════════════════════════════════════════════════════════
# 23. Constants & Configuration (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_max_query_length(self):
        from app.core.edge_case_handlers import MAX_QUERY_LENGTH

        assert MAX_QUERY_LENGTH == 10000

    def test_handler_timeout(self):
        from app.core.edge_case_handlers import HANDLER_TIMEOUT_SECONDS

        assert HANDLER_TIMEOUT_SECONDS == 2.0

    def test_chain_timeout(self):
        assert CHAIN_TIMEOUT_SECONDS == 10.0

    def test_confidence_threshold(self):
        assert CONFIDENCE_THRESHOLD == 0.5

    def test_duplicate_similarity_threshold(self):
        assert DUPLICATE_SIMILARITY_THRESHOLD == 0.9

    def test_context_expiry_minutes(self):
        assert CONTEXT_EXPIRY_MINUTES == 30

    def test_default_competitors_non_empty(self):
        assert len(DEFAULT_COMPETITORS) > 0
        assert "zendesk" in DEFAULT_COMPETITORS

    def test_variant_whitelist_has_mini_parwa(self):
        assert "mini_parwa" in VARIANT_HANDLER_WHITELIST
        assert VARIANT_HANDLER_WHITELIST["parwa"] is None
        assert VARIANT_HANDLER_WHITELIST["parwa_high"] is None

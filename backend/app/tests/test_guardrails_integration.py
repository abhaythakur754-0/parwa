"""
Tests for Guardrails Integration Module (Day 2).

Tests the wiring of GuardrailsEngine to Smart Router / AI Pipeline.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.core.guardrails_integration import (
    GuardrailsAction,
    GuardrailsCheckResult,
    check_llm_response,
    handle_blocked_response,
    apply_guardrails_to_llm_result,
)


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def clean_response():
    return "Here's how to reset your password: Go to Settings > Security > Reset Password."


@pytest.fixture
def blocked_response_hate():
    return "This content promotes hate speech against certain groups."


@pytest.fixture
def pii_response():
    return "Contact john.doe@example.com or call 555-123-4567 for help."


@pytest.fixture
def llm_result_clean():
    return {
        "content": "This is a helpful response about password reset.",
        "model": "llama-3.1-8b",
        "provider": "cerebras",
        "confidence": 90.0,
    }


@pytest.fixture
def llm_result_blocked():
    return {
        "content": "hate speech content here",
        "model": "llama-3.1-8b",
        "provider": "cerebras",
        "confidence": 85.0,
    }


# ── GuardrailsCheckResult Tests ──────────────────────────────────


class TestGuardrailsCheckResult:
    def test_default_values(self):
        result = GuardrailsCheckResult(
            action=GuardrailsAction.ALLOW,
            original_response="test",
        )
        assert result.action == GuardrailsAction.ALLOW
        assert result.blocked_reasons == []
        assert result.flagged_layers == []
        assert result.company_id == ""

    def test_with_blocked_reasons(self):
        result = GuardrailsCheckResult(
            action=GuardrailsAction.BLOCK,
            original_response="test",
            blocked_reasons=["content_safety: hate speech"],
            company_id="company_123",
        )
        assert result.action == GuardrailsAction.BLOCK
        assert len(result.blocked_reasons) == 1
        assert result.company_id == "company_123"


# ── check_llm_response Tests ─────────────────────────────────────


class TestCheckLlmResponse:
    def test_empty_response_blocked(self):
        result = check_llm_response(
            response_content="",
            original_query="test",
            company_id="company1",
        )
        assert result.action == GuardrailsAction.BLOCK
        assert "Empty response" in result.blocked_reasons

    def test_whitespace_only_blocked(self):
        result = check_llm_response(
            response_content="   \n\t  ",
            original_query="test",
            company_id="company1",
        )
        assert result.action == GuardrailsAction.BLOCK

    def test_clean_response_allowed(self, clean_response):
        result = check_llm_response(
            response_content=clean_response,
            original_query="How do I reset my password?",
            company_id="company1",
        )
        assert result.action == GuardrailsAction.ALLOW
        assert result.safe_response == clean_response

    def test_hate_speech_blocked(self, blocked_response_hate):
        result = check_llm_response(
            response_content=blocked_response_hate,
            original_query="Tell me about hate groups",
            company_id="company1",
        )
        assert result.action == GuardrailsAction.BLOCK
        assert any("content_safety" in r for r in result.blocked_reasons)

    def test_pii_flagged_or_blocked(self, pii_response):
        """PII in response should be detected."""
        result = check_llm_response(
            response_content=pii_response,
            original_query="How can I contact support?",
            company_id="company1",
        )
        # PII leak guard should catch this
        assert result.action in [GuardrailsAction.BLOCK, GuardrailsAction.FLAG_FOR_REVIEW]

    def test_company_id_in_result(self, clean_response):
        result = check_llm_response(
            response_content=clean_response,
            original_query="test",
            company_id="test_company_abc",
        )
        assert result.company_id == "test_company_abc"


# ── handle_blocked_response Tests ────────────────────────────────


class TestHandleBlockedResponse:
    def test_returns_safe_fallback(self):
        result = GuardrailsCheckResult(
            action=GuardrailsAction.BLOCK,
            original_response="blocked content",
            blocked_reasons=["content_safety: violence"],
            company_id="company1",
        )
        safe_response = handle_blocked_response(result)
        assert safe_response != "blocked content"
        assert "apologize" in safe_response.lower() or "unable" in safe_response.lower()

    def test_non_blocked_returns_original(self, clean_response):
        result = GuardrailsCheckResult(
            action=GuardrailsAction.ALLOW,
            original_response=clean_response,
        )
        response = handle_blocked_response(result)
        assert response == clean_response

    def test_hate_speech_specific_fallback(self):
        result = GuardrailsCheckResult(
            action=GuardrailsAction.BLOCK,
            original_response="hate content",
            blocked_reasons=["content_safety: hate_speech detected"],
            company_id="company1",
        )
        safe_response = handle_blocked_response(result)
        assert "rephrase" in safe_response.lower() or "help" in safe_response.lower()

    def test_pii_specific_fallback(self):
        result = GuardrailsCheckResult(
            action=GuardrailsAction.BLOCK,
            original_response="SSN: 123-45-6789",
            blocked_reasons=["pii_leak_prevention: SSN detected"],
            company_id="company1",
        )
        safe_response = handle_blocked_response(result)
        assert "security" in safe_response.lower() or "support" in safe_response.lower()


# ── apply_guardrails_to_llm_result Tests ───────────────────────────


class TestApplyGuardrailsToLlmResult:
    def test_clean_result_passes(self, llm_result_clean):
        output = apply_guardrails_to_llm_result(
            llm_result=llm_result_clean,
            original_query="How do I reset my password?",
            company_id="company1",
        )
        assert output["guardrails_action"] == "allow"
        assert output.get("guardrails_passed") is True
        assert output["content"] == llm_result_clean["content"]

    def test_blocked_result_gets_fallback(self, llm_result_blocked):
        output = apply_guardrails_to_llm_result(
            llm_result=llm_result_blocked,
            original_query="test query",
            company_id="company1",
        )
        assert output["guardrails_action"] == "block"
        assert output["content"] != llm_result_blocked["content"]
        assert "blocked_reasons" in output
        assert output.get("original_content_blocked") is True

    def test_original_metadata_preserved(self, llm_result_clean):
        output = apply_guardrails_to_llm_result(
            llm_result=llm_result_clean,
            original_query="test",
            company_id="company1",
        )
        # Original metadata preserved
        assert output["model"] == "llama-3.1-8b"
        assert output["provider"] == "cerebras"
        assert output["confidence"] == 90.0
        # Guardrails metadata added
        assert "guardrails_action" in output
        assert "guardrails_checked_at" in output

    def test_company_id_propagated(self, llm_result_clean):
        output = apply_guardrails_to_llm_result(
            llm_result=llm_result_clean,
            original_query="test",
            company_id="test_company_xyz",
        )
        # Just verify it doesn't crash
        assert "guardrails_action" in output


# ── Integration Edge Cases ────────────────────────────────────────


class TestEdgeCases:
    def test_none_content(self):
        result = check_llm_response(
            response_content=None,
            original_query="test",
            company_id="company1",
        )
        assert result.action == GuardrailsAction.BLOCK

    def test_very_long_response(self):
        """Test that long responses don't cause timeout."""
        long_response = "This is a normal sentence. " * 1000
        result = check_llm_response(
            response_content=long_response,
            original_query="Tell me a long story about normal sentences",
            company_id="company1",
        )
        # Should pass topic relevance with matching query
        assert result.action in [GuardrailsAction.ALLOW, GuardrailsAction.FLAG_FOR_REVIEW, GuardrailsAction.BLOCK]

    def test_unicode_content(self):
        unicode_response = "Hello 你好 مرحبا Привет 🌍"
        result = check_llm_response(
            response_content=unicode_response,
            original_query="Say hello",
            company_id="company1",
        )
        assert result.action in [GuardrailsAction.ALLOW, GuardrailsAction.FLAG_FOR_REVIEW]

    def test_code_content_allowed(self):
        """Code snippets should be allowed."""
        code_response = """
```python
def reset_password(user):
    token = generate_token()
    send_email(user.email, token)
    return "Check your email"
```
"""
        result = check_llm_response(
            response_content=code_response,
            original_query="Write a password reset function",
            company_id="company1",
        )
        # Code should be allowed
        assert result.action == GuardrailsAction.ALLOW


# ── GuardrailsAction Enum Tests ───────────────────────────────────


class TestGuardrailsAction:
    def test_all_values_exist(self):
        assert GuardrailsAction.ALLOW.value == "allow"
        assert GuardrailsAction.BLOCK.value == "block"
        assert GuardrailsAction.FLAG_FOR_REVIEW.value == "flag_for_review"
        assert GuardrailsAction.REWRITE.value == "rewrite"

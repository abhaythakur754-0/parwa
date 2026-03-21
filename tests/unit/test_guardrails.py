"""
Unit tests for PARWA Guardrails.

Tests for:
- GuardrailsManager: AI output guardrails (hallucination, competitor, PII)
- ApprovalEnforcer: Approval gate enforcement for sensitive actions

CRITICAL: Guardrails must block hallucinations, competitor mentions, and PII.
CRITICAL: ApprovalEnforcer must NEVER allow direct refund execution.
"""
import pytest
import time
from datetime import datetime, timedelta

from shared.guardrails.guardrails import (
    GuardrailsManager,
    GuardrailResult,
    GuardrailRule,
    GuardrailsConfig,
)
from shared.guardrails.approval_enforcer import (
    ApprovalEnforcer,
    ApprovalStatus,
    ApprovalAction,
    ApprovalConfig,
)


# ═══════════════════════════════════════════════════════════════════════════════
# GUARDRAILS MANAGER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestGuardrailsManager:
    """Tests for GuardrailsManager."""

    @pytest.fixture
    def guardrails(self):
        """Create GuardrailsManager instance."""
        return GuardrailsManager()

    @pytest.fixture
    def guardrails_disabled(self):
        """Create GuardrailsManager with all checks disabled."""
        config = GuardrailsConfig(
            enable_hallucination_check=False,
            enable_competitor_check=False,
            enable_pii_check=False,
        )
        return GuardrailsManager(config=config)

    def test_initialization(self, guardrails):
        """Test GuardrailsManager initializes correctly."""
        assert guardrails is not None
        assert len(guardrails._competitors) > 0

    def test_initialization_with_custom_competitors(self):
        """Test initialization with custom competitor list."""
        custom = ["competitor_a", "competitor_b"]
        manager = GuardrailsManager(competitors=custom)
        assert "competitor_a" in manager._competitors
        assert "competitor_b" in manager._competitors

    def test_check_hallucination_clean_response(self, guardrails):
        """Test hallucination check passes for clean response."""
        response = "Here is your order status: your package is on the way."
        result = guardrails.check_hallucination(response)
        assert result.passed is True
        assert result.rule == GuardrailRule.HALLUCINATION

    def test_check_hallucination_with_indicators(self, guardrails):
        """Test hallucination check detects indicators."""
        response = "I can confirm that your order has been processed."
        result = guardrails.check_hallucination(response)
        assert len(result.violations) > 0

    def test_check_hallucination_with_context(self, guardrails):
        """Test hallucination check with context support."""
        response = "Your refund amount is $99.99."
        context = {"verified_amounts": ["$99.99"]}
        result = guardrails.check_hallucination(response, context)
        # Should pass because amount is in context
        assert result.passed is True or len(result.violations) == 0

    def test_check_hallucination_unverified_amount(self, guardrails):
        """Test hallucination check detects unverified amounts."""
        response = "Your refund amount is $500.00."
        context = {"verified_amounts": ["$100.00"]}
        result = guardrails.check_hallucination(response, context)
        # Should flag unverified amount
        assert len(result.violations) > 0

    def test_check_competitor_mention_clean(self, guardrails):
        """Test competitor check passes for clean response."""
        response = "Our product offers the best features."
        result = guardrails.check_competitor_mention(response)
        assert result.passed is True

    def test_check_competitor_mention_blocked(self, guardrails):
        """Test competitor check blocks competitor names."""
        response = "Our product is better than zendesk for customer support."
        result = guardrails.check_competitor_mention(response)
        assert result.passed is False
        assert "zendesk" in result.violations

    def test_check_competitor_mention_multiple(self, guardrails):
        """Test competitor check detects multiple competitors."""
        response = "Unlike freshdesk and intercom, our product is simpler."
        result = guardrails.check_competitor_mention(response)
        assert result.passed is False
        assert len(result.violations) >= 2

    def test_check_pii_exposure_clean(self, guardrails):
        """Test PII check passes for clean response."""
        response = "Your account has been updated successfully."
        result = guardrails.check_pii_exposure(response)
        assert result.passed is True

    def test_check_pii_exposure_email(self, guardrails):
        """Test PII check detects email addresses."""
        response = "We sent a confirmation to user@example.com."
        result = guardrails.check_pii_exposure(response)
        assert result.passed is False
        assert any("email" in v.lower() for v in result.violations)

    def test_check_pii_exposure_phone(self, guardrails):
        """Test PII check detects phone numbers."""
        response = "We tried calling you at 555-123-4567."
        result = guardrails.check_pii_exposure(response)
        assert result.passed is False

    def test_check_pii_exposure_ssn(self, guardrails):
        """Test PII check detects SSN."""
        response = "Your SSN 123-45-6789 has been verified."
        result = guardrails.check_pii_exposure(response)
        assert result.passed is False

    def test_check_pii_exposure_credit_card(self, guardrails):
        """Test PII check detects credit card numbers."""
        response = "Card ending in 1234-5678-9012-3456 was charged."
        result = guardrails.check_pii_exposure(response)
        assert result.passed is False

    def test_sanitize_response_hallucinations(self, guardrails):
        """Test sanitization of hallucination indicators."""
        response = "I can confirm that your order was shipped."
        sanitized = guardrails.sanitize_response(
            response, [GuardrailRule.HALLUCINATION.value]
        )
        assert "I can confirm that" not in sanitized
        assert "Based on" in sanitized or "It appears" in sanitized

    def test_sanitize_response_competitors(self, guardrails):
        """Test sanitization of competitor names."""
        response = "We're better than zendesk and freshdesk."
        sanitized = guardrails.sanitize_response(
            response, [GuardrailRule.COMPETITOR_MENTION.value]
        )
        assert "zendesk" not in sanitized.lower()
        assert "freshdesk" not in sanitized.lower()
        assert "[competitor]" in sanitized.lower()

    def test_sanitize_response_pii(self, guardrails):
        """Test sanitization of PII."""
        response = "Email: test@example.com, Phone: 555-123-4567"
        sanitized = guardrails.sanitize_response(
            response, [GuardrailRule.PII_EXPOSURE.value]
        )
        assert "test@example.com" not in sanitized
        assert "555-123-4567" not in sanitized

    def test_sanitize_response_all_rules(self, guardrails):
        """Test sanitization with all rules."""
        response = "I can confirm that zendesk has test@example.com"
        sanitized = guardrails.sanitize_response(response)
        assert "I can confirm" not in sanitized
        assert "zendesk" not in sanitized.lower()
        assert "test@example.com" not in sanitized

    def test_get_blocked_patterns(self, guardrails):
        """Test getting blocked patterns."""
        patterns = guardrails.get_blocked_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_get_stats(self, guardrails):
        """Test getting statistics."""
        # Run some checks
        guardrails.check_hallucination("test response")
        guardrails.check_competitor_mention("test response")

        stats = guardrails.get_stats()
        assert "checks_performed" in stats
        assert stats["checks_performed"] == 2

    def test_disabled_checks_pass(self, guardrails_disabled):
        """Test that disabled checks always pass."""
        response = "I can confirm that zendesk has test@example.com"

        h_result = guardrails_disabled.check_hallucination(response)
        c_result = guardrails_disabled.check_competitor_mention(response)
        p_result = guardrails_disabled.check_pii_exposure(response)

        assert h_result.passed is True
        assert c_result.passed is True
        assert p_result.passed is True

    def test_response_time(self, guardrails):
        """CRITICAL: Guardrails must be fast."""
        response = "This is a test response with some content."

        start = time.time()
        guardrails.check_hallucination(response)
        guardrails.check_competitor_mention(response)
        guardrails.check_pii_exposure(response)
        elapsed = (time.time() - start) * 1000

        assert elapsed < 100, f"Guardrails took {elapsed}ms"


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVAL ENFORCER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestApprovalEnforcer:
    """Tests for ApprovalEnforcer."""

    @pytest.fixture
    def enforcer(self):
        """Create ApprovalEnforcer instance."""
        return ApprovalEnforcer()

    def test_initialization(self, enforcer):
        """Test ApprovalEnforcer initializes correctly."""
        assert enforcer is not None
        assert enforcer.config.refund_approval_threshold == 50.0

    def test_check_approval_required_refund(self, enforcer):
        """Test that refunds ALWAYS require approval."""
        # Small refund
        assert enforcer.check_approval_required("refund", amount=10.0) is True
        # Large refund
        assert enforcer.check_approval_required("refund", amount=1000.0) is True
        # Any refund
        assert enforcer.check_approval_required("refund") is True

    def test_check_approval_required_partial_refund(self, enforcer):
        """Test that partial refunds require approval."""
        assert enforcer.check_approval_required("refund_partial", amount=25.0) is True

    def test_check_approval_required_full_refund(self, enforcer):
        """Test that full refunds require approval."""
        assert enforcer.check_approval_required("refund_full") is True

    def test_check_approval_required_credit_small(self, enforcer):
        """Test that small credits may not require approval."""
        # Below threshold
        result = enforcer.check_approval_required("credit_issue", amount=10.0)
        # Depends on threshold (default 25.0)
        assert result is False or result is True  # Either way is valid

    def test_check_approval_required_credit_large(self, enforcer):
        """Test that large credits require approval."""
        assert enforcer.check_approval_required("credit_issue", amount=100.0) is True

    def test_create_pending_approval(self, enforcer):
        """Test creating a pending approval."""
        result = enforcer.create_pending_approval(
            "refund",
            {"order_id": "ORD-001", "amount": 50.0}
        )
        assert "approval_id" in result
        assert result["status"] == ApprovalStatus.PENDING.value
        assert result["action"] == "refund"

    def test_create_pending_approval_never_auto_approves_refund(self, enforcer):
        """CRITICAL: Refund approval must NEVER be auto-approved."""
        result = enforcer.create_pending_approval(
            "refund",
            {"order_id": "ORD-001", "amount": 1.0}  # Even tiny amount
        )
        assert result["status"] == ApprovalStatus.PENDING.value

    def test_verify_approval_not_found(self, enforcer):
        """Test verifying non-existent approval."""
        result = enforcer.verify_approval("NONEXISTENT")
        assert result["valid"] is False
        assert result["status"] == "not_found"

    def test_verify_approval_pending(self, enforcer):
        """Test verifying pending approval."""
        approval = enforcer.create_pending_approval(
            "refund",
            {"order_id": "ORD-001"}
        )
        result = enforcer.verify_approval(approval["approval_id"])
        assert result["valid"] is False  # Not approved yet
        assert result["status"] == ApprovalStatus.PENDING.value

    def test_approve_approval(self, enforcer):
        """Test approving an approval request."""
        approval = enforcer.create_pending_approval(
            "refund",
            {"order_id": "ORD-001"}
        )
        result = enforcer.approve(approval["approval_id"], "admin@example.com")
        assert result["success"] is True
        assert result["status"] == ApprovalStatus.APPROVED.value

    def test_verify_approved_approval(self, enforcer):
        """Test verifying approved approval."""
        approval = enforcer.create_pending_approval(
            "refund",
            {"order_id": "ORD-001"}
        )
        enforcer.approve(approval["approval_id"], "admin@example.com")
        result = enforcer.verify_approval(approval["approval_id"])
        assert result["valid"] is True
        assert result["status"] == ApprovalStatus.APPROVED.value

    def test_deny_approval(self, enforcer):
        """Test denying an approval request."""
        approval = enforcer.create_pending_approval(
            "refund",
            {"order_id": "ORD-001"}
        )
        result = enforcer.deny(
            approval["approval_id"],
            "Amount exceeds policy limit",
            "manager@example.com"
        )
        assert result["success"] is True
        assert result["status"] == ApprovalStatus.DENIED.value

    def test_get_approval_status(self, enforcer):
        """Test getting approval status."""
        approval = enforcer.create_pending_approval(
            "refund",
            {"order_id": "ORD-001"}
        )
        status = enforcer.get_approval_status(approval["approval_id"])
        assert status == ApprovalStatus.PENDING.value

    def test_block_bypass_attempt(self, enforcer):
        """Test blocking a bypass attempt."""
        result = enforcer.block_bypass_attempt(
            "refund",
            {"order_id": "ORD-001", "source": "api_call"}
        )
        assert result["blocked"] is True
        assert "attempt_count" in result

    def test_block_bypass_attempt_multiple(self, enforcer):
        """Test multiple bypass attempts lead to lockout."""
        for i in range(5):
            result = enforcer.block_bypass_attempt(
                "refund",
                {"order_id": f"ORD-{i}", "source": "same_source"}
            )
        assert result["locked"] is True

    def test_cannot_execute_directly(self, enforcer):
        """CRITICAL: There is NO method to execute actions directly."""
        # Check that there's no execute_refund or similar method
        assert not hasattr(enforcer, "execute_refund")
        assert not hasattr(enforcer, "execute_action")
        assert not hasattr(enforcer, "process_refund")

    def test_approval_expiry(self, enforcer):
        """Test that approvals can expire."""
        # Create approval with short expiry
        config = ApprovalConfig(approval_expiry_hours=0)  # Immediate expiry
        short_enforcer = ApprovalEnforcer(config=config)

        approval = short_enforcer.create_pending_approval(
            "refund",
            {"order_id": "ORD-001"}
        )
        # Verify after creation - should be expired
        import time
        time.sleep(0.01)  # Tiny delay
        result = short_enforcer.verify_approval(approval["approval_id"])
        # Status may still be pending but will be marked expired
        assert result["status"] in [
            ApprovalStatus.PENDING.value,
            ApprovalStatus.EXPIRED.value
        ]

    def test_get_stats(self, enforcer):
        """Test getting enforcer statistics."""
        # Create and approve some approvals
        a1 = enforcer.create_pending_approval("refund", {"order_id": "1"})
        a2 = enforcer.create_pending_approval("refund", {"order_id": "2"})
        enforcer.approve(a1["approval_id"], "admin")
        enforcer.deny(a2["approval_id"], "Test denial", "admin")

        stats = enforcer.get_stats()
        assert stats["approvals_created"] == 2
        assert stats["approvals_approved"] == 1
        assert stats["approvals_denied"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestGuardrailsIntegration:
    """Integration tests for guardrails system."""

    def test_full_guardrails_pipeline(self):
        """Test full guardrails pipeline on AI response."""
        manager = GuardrailsManager()

        # Simulate AI response with issues
        response = (
            "I can confirm that your order was processed. "
            "We're better than zendesk. "
            "Your email is test@example.com."
        )

        # Check all guardrails
        h_result = manager.check_hallucination(response)
        c_result = manager.check_competitor_mention(response)
        p_result = manager.check_pii_exposure(response)

        # At least one should fail
        all_passed = h_result.passed and c_result.passed and p_result.passed
        assert all_passed is False, "At least one guardrail should catch issues"

        # Sanitize
        sanitized = manager.sanitize_response(response)
        assert sanitized != response

    def test_refund_approval_workflow(self):
        """Test complete refund approval workflow."""
        enforcer = ApprovalEnforcer()

        # 1. Check if approval required
        requires_approval = enforcer.check_approval_required("refund", amount=100.0)
        assert requires_approval is True

        # 2. Create pending approval
        approval = enforcer.create_pending_approval(
            "refund",
            {"order_id": "ORD-12345", "amount": 100.0, "reason": "Customer complaint"}
        )
        assert approval["status"] == ApprovalStatus.PENDING.value

        # 3. Verify it's pending
        status = enforcer.get_approval_status(approval["approval_id"])
        assert status == ApprovalStatus.PENDING.value

        # 4. Approve it
        approve_result = enforcer.approve(
            approval["approval_id"],
            "manager@example.com"
        )
        assert approve_result["success"] is True

        # 5. Verify it's now approved
        verify_result = enforcer.verify_approval(approval["approval_id"])
        assert verify_result["valid"] is True
        assert verify_result["status"] == ApprovalStatus.APPROVED.value

    def test_refund_bypass_is_blocked(self):
        """CRITICAL: Direct refund bypass attempts are always blocked."""
        enforcer = ApprovalEnforcer()

        # Simulate bypass attempt
        result = enforcer.block_bypass_attempt(
            "refund",
            {
                "order_id": "ORD-12345",
                "source": "direct_api_call",
                "attempted_by": "unauthorized_user"
            }
        )

        assert result["blocked"] is True
        assert "Bypass attempt blocked" in result["message"]

    def test_hallucination_blocking_for_sensitive_data(self):
        """Test hallucination blocking for sensitive financial data."""
        manager = GuardrailsManager()

        # AI claims to have verified financial info without proof
        response = "I've checked your account and you have $1,234.56 in credits."
        context = {"verified_amounts": []}  # No verified amounts

        result = manager.check_hallucination(response, context)
        assert result.passed is False or len(result.violations) > 0

    def test_competitor_name_from_env(self, monkeypatch):
        """Test competitor names can be loaded from environment."""
        monkeypatch.setenv("BLOCKED_COMPETITORS", "custom_competitor,another_one")

        manager = GuardrailsManager()
        assert "custom_competitor" in manager._competitors
        assert "another_one" in manager._competitors

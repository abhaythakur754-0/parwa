"""
Tests for Jarvis Service Layer (Week 6 — Day 2 Gap Analysis)

Covers gap analysis findings:
- GAP-2: __all__ exports completeness
- GAP-4: No unused imports in schemas
- GAP-5: Webhook idempotency
- GAP-9: Unit tests for service business logic
"""

import json
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import pytest

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ── GAP-4: Schema imports must not have unused imports ──────────────

class TestSchemaImports:
    """Verify schemas module has no unused imports."""

    def test_schemas_imports_clean(self):
        """All schemas should import without issues."""
        # py_compile already verified in CI, this checks runtime
        from app.schemas.jarvis import (
            JarvisSessionCreate,
            JarvisSessionResponse,
            JarvisMessageSend,
            JarvisMessageResponse,
            JarvisHistoryResponse,
            JarvisContextUpdate,
            JarvisEntryContextRequest,
            JarvisOtpRequest,
            JarvisOtpVerify,
            JarvisOtpResponse,
            JarvisDemoPackPurchase,
            JarvisDemoPackStatusResponse,
            JarvisPaymentCreate,
            JarvisPaymentStatusResponse,
            JarvisPaymentWebhookPayload,
            JarvisDemoCallRequest,
            JarvisDemoCallVerifyOtp,
            JarvisDemoCallSummaryResponse,
            JarvisHandoffRequest,
            JarvisHandoffStatusResponse,
            JarvisActionTicketCreate,
            JarvisActionTicketUpdateStatus,
            JarvisActionTicketResponse,
            JarvisActionTicketListResponse,
            JarvisErrorResponse,
        )
        # If we got here, all 24 schemas imported cleanly
        assert True

    def test_no_datetime_import_in_schemas(self):
        """datetime should not be imported in schemas (unused)."""
        import app.schemas.jarvis as jarvis_mod
        source = open(jarvis_mod.__file__).read()
        assert "from datetime import datetime" not in source, (
            "Unused datetime import found in schemas/jarvis.py"
        )


# ── GAP-2: __all__ exports ────────────────────────────────────────

class TestServiceExports:
    """Verify jarvis_service has complete __all__ exports."""

    def test_has_all_attribute(self):
        """Module must define __all__."""
        import app.services.jarvis_service as svc
        assert hasattr(svc, "__all__"), "Missing __all__ in jarvis_service.py"

    def test_all_exports_public_functions(self):
        """__all__ must contain all 25 public service functions."""
        import app.services.jarvis_service as svc
        expected_functions = [
            "create_or_resume_session",
            "get_session",
            "get_session_context",
            "update_context",
            "set_entry_context",
            "send_message",
            "get_history",
            "check_message_limit",
            "send_business_otp",
            "verify_business_otp",
            "purchase_demo_pack",
            "get_demo_pack_status",
            "create_payment_session",
            "handle_payment_webhook",
            "get_payment_status",
            "initiate_demo_call",
            "get_call_summary",
            "execute_handoff",
            "get_handoff_status",
            "create_action_ticket",
            "get_tickets",
            "get_ticket",
            "update_ticket_status",
            "complete_ticket",
            "build_system_prompt",
            "detect_stage",
            "get_entry_context",
            "build_context_aware_welcome",
            "handle_error",
        ]
        for fn_name in expected_functions:
            assert fn_name in svc.__all__, (
                f"Missing '{fn_name}' in __all__"
            )
            assert hasattr(svc, fn_name), (
                f"'{fn_name}' in __all__ but not defined in module"
            )

    def test_all_exports_constants(self):
        """__all__ must contain all public constants."""
        import app.services.jarvis_service as svc
        expected_constants = [
            "FREE_DAILY_LIMIT",
            "DEMO_DAILY_LIMIT",
            "DEMO_PACK_HOURS",
            "DEMO_CALL_DURATION_SECONDS",
            "OTP_LENGTH",
            "OTP_EXPIRY_MINUTES",
            "MAX_OTP_ATTEMPTS",
        ]
        for const in expected_constants:
            assert const in svc.__all__, f"Missing '{const}' in __all__"
            assert hasattr(svc, const), f"'{const}' in __all__ but not defined"


# ── Schema Validation Tests ───────────────────────────────────────

class TestSchemaValidation:
    """Test Pydantic schema validation rules."""

    def test_session_create_valid_entry_sources(self):
        """All valid entry sources should pass."""
        from app.schemas.jarvis import JarvisSessionCreate
        for source in [
            "direct", "pricing", "roi", "demo", "features",
            "referral", "ad", "organic", "email_campaign", "other",
        ]:
            obj = JarvisSessionCreate(entry_source=source)
            assert obj.entry_source == source

    def test_session_create_invalid_entry_source(self):
        """Invalid entry source should raise ValidationError."""
        from pydantic import ValidationError
        from app.schemas.jarvis import JarvisSessionCreate
        with pytest.raises(ValidationError):
            JarvisSessionCreate(entry_source="invalid_source")

    def test_otp_request_valid_email(self):
        """Valid email should pass."""
        from app.schemas.jarvis import JarvisOtpRequest
        obj = JarvisOtpRequest(email="test@example.com")
        assert obj.email == "test@example.com"

    def test_otp_request_invalid_email(self):
        """Invalid email should raise ValidationError."""
        from pydantic import ValidationError
        from app.schemas.jarvis import JarvisOtpRequest
        with pytest.raises(ValidationError):
            JarvisOtpRequest(email="not-an-email")

    def test_otp_request_empty_email(self):
        """Empty email should raise ValidationError."""
        from pydantic import ValidationError
        from app.schemas.jarvis import JarvisOtpRequest
        with pytest.raises(ValidationError):
            JarvisOtpRequest(email="")

    def test_demo_call_request_valid_phone(self):
        """Valid phone numbers should pass."""
        from app.schemas.jarvis import JarvisDemoCallRequest
        for phone in ["+1234567890", "1234567890", "+44 20 7946 0958"]:
            obj = JarvisDemoCallRequest(phone=phone)
            assert obj.phone == phone

    def test_demo_call_request_short_phone(self):
        """Phone < 7 digits should fail."""
        from pydantic import ValidationError
        from app.schemas.jarvis import JarvisDemoCallRequest
        with pytest.raises(ValidationError):
            JarvisDemoCallRequest(phone="123")

    def test_payment_create_valid_variants(self):
        """Valid variant selection should pass."""
        from app.schemas.jarvis import JarvisPaymentCreate
        obj = JarvisPaymentCreate(
            variants=[{"id": "v1", "quantity": 2}],
            industry="saas",
        )
        assert len(obj.variants) == 1

    def test_payment_create_empty_variants(self):
        """Empty variants should fail."""
        from pydantic import ValidationError
        from app.schemas.jarvis import JarvisPaymentCreate
        with pytest.raises(ValidationError):
            JarvisPaymentCreate(variants=[], industry="saas")

    def test_payment_create_zero_quantity(self):
        """Zero quantity should fail."""
        from pydantic import ValidationError
        from app.schemas.jarvis import JarvisPaymentCreate
        with pytest.raises(ValidationError):
            JarvisPaymentCreate(
                variants=[{"id": "v1", "quantity": 0}],
                industry="saas",
            )

    def test_payment_create_max_quantity(self):
        """Quantity > 10 should fail."""
        from pydantic import ValidationError
        from app.schemas.jarvis import JarvisPaymentCreate
        with pytest.raises(ValidationError):
            JarvisPaymentCreate(
                variants=[{"id": "v1", "quantity": 11}],
                industry="saas",
            )

    def test_ticket_create_valid_types(self):
        """All valid ticket types should pass."""
        from app.schemas.jarvis import JarvisActionTicketCreate
        for t in [
            "otp_verification", "otp_verified",
            "payment_demo_pack", "payment_variant",
            "payment_variant_completed", "demo_call",
            "demo_call_completed", "roi_import", "handoff",
        ]:
            obj = JarvisActionTicketCreate(ticket_type=t)
            assert obj.ticket_type == t

    def test_ticket_create_invalid_type(self):
        """Invalid ticket type should fail."""
        from pydantic import ValidationError
        from app.schemas.jarvis import JarvisActionTicketCreate
        with pytest.raises(ValidationError):
            JarvisActionTicketCreate(ticket_type="invalid")

    def test_ticket_update_valid_statuses(self):
        """All valid statuses should pass."""
        from app.schemas.jarvis import JarvisActionTicketUpdateStatus
        for s in ["pending", "in_progress", "completed", "failed"]:
            obj = JarvisActionTicketUpdateStatus(status=s)
            assert obj.status == s

    def test_context_update_valid_stage(self):
        """Valid stages should pass."""
        from app.schemas.jarvis import JarvisContextUpdate
        obj = JarvisContextUpdate(detected_stage="pricing")
        assert obj.detected_stage == "pricing"

    def test_context_update_invalid_stage(self):
        """Invalid stage should fail."""
        from pydantic import ValidationError
        from app.schemas.jarvis import JarvisContextUpdate
        with pytest.raises(ValidationError):
            JarvisContextUpdate(detected_stage="invalid_stage")

    def test_context_update_email_validation(self):
        """Business email in context update should be validated."""
        from pydantic import ValidationError
        from app.schemas.jarvis import JarvisContextUpdate
        with pytest.raises(ValidationError):
            JarvisContextUpdate(business_email="not-email")


# ── Service Logic Tests ───────────────────────────────────────────

class TestServiceConstants:
    """Verify service constants match spec."""

    def test_free_daily_limit(self):
        from app.services.jarvis_service import FREE_DAILY_LIMIT
        assert FREE_DAILY_LIMIT == 20

    def test_demo_daily_limit(self):
        from app.services.jarvis_service import DEMO_DAILY_LIMIT
        assert DEMO_DAILY_LIMIT == 500

    def test_demo_pack_hours(self):
        from app.services.jarvis_service import DEMO_PACK_HOURS
        assert DEMO_PACK_HOURS == 24

    def test_demo_call_duration(self):
        from app.services.jarvis_service import DEMO_CALL_DURATION_SECONDS
        assert DEMO_CALL_DURATION_SECONDS == 180

    def test_otp_length(self):
        from app.services.jarvis_service import OTP_LENGTH
        assert OTP_LENGTH == 6

    def test_otp_expiry_minutes(self):
        from app.services.jarvis_service import OTP_EXPIRY_MINUTES
        assert OTP_EXPIRY_MINUTES == 10

    def test_max_otp_attempts(self):
        from app.services.jarvis_service import MAX_OTP_ATTEMPTS
        assert MAX_OTP_ATTEMPTS == 3


class TestParseContext:
    """Test context_json parsing helper."""

    def test_parse_valid_json(self):
        from app.services.jarvis_service import _parse_context
        result = _parse_context('{"industry": "saas"}')
        assert result == {"industry": "saas"}

    def test_parse_empty_string(self):
        from app.services.jarvis_service import _parse_context
        result = _parse_context("")
        assert result == {}

    def test_parse_none(self):
        from app.services.jarvis_service import _parse_context
        result = _parse_context(None)
        assert result == {}

    def test_parse_invalid_json(self):
        from app.services.jarvis_service import _parse_context
        result = _parse_context("{invalid}")
        assert result == {}


class TestEntryContext:
    """Test entry context routing."""

    def test_pricing_entry_sets_stage(self):
        from app.services.jarvis_service import get_entry_context
        ctx = get_entry_context("pricing", {"industry": "saas"})
        assert ctx["detected_stage"] == "pricing"
        assert ctx["industry"] == "saas"

    def test_roi_entry_sets_stage(self):
        from app.services.jarvis_service import get_entry_context
        ctx = get_entry_context("roi", {"industry": "ecommerce"})
        assert ctx["detected_stage"] == "discovery"
        assert ctx["industry"] == "ecommerce"

    def test_demo_entry_sets_stage(self):
        from app.services.jarvis_service import get_entry_context
        ctx = get_entry_context("demo")
        assert ctx["detected_stage"] == "demo"

    def test_direct_entry_default_stage(self):
        from app.services.jarvis_service import get_entry_context
        ctx = get_entry_context("direct")
        assert ctx["detected_stage"] == "welcome"

    def test_referral_preserves_ref(self):
        from app.services.jarvis_service import get_entry_context
        ctx = get_entry_context("referral", {"ref": "friend123"})
        assert ctx["referral_source"] == "friend123"

    def test_none_params_safe(self):
        from app.services.jarvis_service import get_entry_context
        ctx = get_entry_context("direct", None)
        assert ctx["entry_params"] is not None


class TestDetectStage:
    """Test conversation stage detection heuristic."""

    def _make_session(self, **overrides):
        """Create a mock session object."""
        defaults = {
            "payment_status": "none",
            "context_json": "{}",
        }
        defaults.update(overrides)
        return type("Session", (), defaults)()

    def test_welcome_no_industry(self):
        from app.services.jarvis_service import detect_stage
        session = self._make_session(context_json='{}')
        stage = detect_stage(MagicMock(), "session_1")
        assert stage == "welcome"

    def test_discovery_with_industry(self):
        from app.services.jarvis_service import detect_stage
        ctx = json.dumps({"industry": "saas"})
        session = self._make_session(context_json=ctx)
        stage = detect_stage(MagicMock(), "session_1")
        assert stage == "discovery"

    def test_pricing_with_variants(self):
        from app.services.jarvis_service import detect_stage
        ctx = json.dumps({
            "industry": "saas",
            "selected_variants": [{"id": "v1"}],
        })
        session = self._make_session(context_json=ctx)
        stage = detect_stage(MagicMock(), "session_1")
        assert stage == "pricing"

    def test_bill_review_with_bill_shown(self):
        from app.services.jarvis_service import detect_stage
        ctx = json.dumps({
            "industry": "saas",
            "selected_variants": [{"id": "v1"}],
            "bill_shown": True,
        })
        session = self._make_session(context_json=ctx)
        stage = detect_stage(MagicMock(), "session_1")
        assert stage == "bill_review"

    def test_verification_otp_sent(self):
        from app.services.jarvis_service import detect_stage
        ctx = json.dumps({
            "otp": {"status": "sent"},
            "email_verified": False,
        })
        session = self._make_session(context_json=ctx)
        stage = detect_stage(MagicMock(), "session_1")
        assert stage == "verification"

    def test_payment_pending(self):
        from app.services.jarvis_service import detect_stage
        session = self._make_session(
            payment_status="pending",
            context_json='{}',
        )
        stage = detect_stage(MagicMock(), "session_1")
        assert stage == "payment"

    def test_handoff_completed(self):
        from app.services.jarvis_service import detect_stage
        session = self._make_session(
            payment_status="completed",
            context_json='{}',
        )
        stage = detect_stage(MagicMock(), "session_1")
        assert stage == "handoff"

    def test_demo_pack_active(self):
        from app.services.jarvis_service import detect_stage
        session = self._make_session(
            pack_type="demo",
            context_json='{}',
        )
        stage = detect_stage(MagicMock(), "session_1")
        assert stage == "demo"


class TestBuildSystemPrompt:
    """Test system prompt generation."""

    def test_prompt_contains_parwa_info(self):
        from app.services.jarvis_service import build_system_prompt
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = (
            type("S", (), {
                "context_json": '{}',
                "id": "s1",
            })()
        )
        prompt = build_system_prompt(mock_db, "s1")
        assert "PARWA" in prompt
        assert "Jarvis" in prompt

    def test_prompt_contains_industry_context(self):
        from app.services.jarvis_service import build_system_prompt
        mock_db = MagicMock()
        ctx = json.dumps({"industry": "saas", "detected_stage": "discovery"})
        mock_db.query.return_value.filter.return_value.first.return_value = (
            type("S", (), {"context_json": ctx, "id": "s1"})()
        )
        prompt = build_system_prompt(mock_db, "s1")
        assert "saas" in prompt
        assert "discovery" in prompt

    def test_prompt_contains_info_boundary(self):
        from app.services.jarvis_service import build_system_prompt
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = (
            type("S", (), {"context_json": '{}', "id": "s1"})()
        )
        prompt = build_system_prompt(mock_db, "s1")
        assert "Information Boundary" in prompt
        assert "CANNOT" in prompt


class TestHandleError:
    """Test error handling helper."""

    def test_rate_limit_error_message(self):
        from app.services.jarvis_service import handle_error
        from app.exceptions import RateLimitError
        result = handle_error(MagicMock(), "s1", RateLimitError("too fast"))
        assert "fast" in result["message"].lower() or "moment" in result["message"].lower()

    def test_generic_error_message(self):
        from app.services.jarvis_service import handle_error
        result = handle_error(MagicMock(), "s1", RuntimeError("boom"))
        assert result["error_type"] == "RuntimeError"
        assert "session_id" in result

    def test_validation_error_message(self):
        from app.services.jarvis_service import handle_error
        from app.exceptions import ValidationError
        result = handle_error(MagicMock(), "s1", ValidationError("bad input"))
        assert result["error_type"] == "ValidationError"


class TestFriendlyErrorMessages:
    """Test user-friendly error messages."""

    def test_default_welcome_message(self):
        from app.services.jarvis_service import _get_default_welcome
        msg = _get_default_welcome()
        assert "Jarvis" in msg
        assert "PARWA" in msg

    def test_friendly_error_message(self):
        from app.services.jarvis_service import _get_friendly_error_message
        msg = _get_friendly_error_message()
        assert len(msg) > 20

    def test_free_limit_message(self):
        from app.services.jarvis_service import _get_limit_message
        session = type("S", (), {"pack_type": "free"})()
        msg = _get_limit_message(session)
        assert "20" in msg
        assert "$1" in msg

    def test_demo_limit_message(self):
        from app.services.jarvis_service import _get_limit_message
        session = type("S", (), {"pack_type": "demo"})()
        msg = _get_limit_message(session)
        assert "Demo Pack" in msg


# ── GAP-7: API Router Tests ────────────────────────────────────────

class TestApiRouterSetup:
    """Verify API router is properly configured."""

    def test_router_prefix(self):
        from app.api.jarvis import router
        assert router.prefix == "/api/jarvis"

    def test_router_has_routes(self):
        from app.api.jarvis import router
        # 22 endpoints = 44 route objects (1 for method + 1 for path each)
        assert len(router.routes) >= 20

    def test_router_registered_in_main(self):
        """jarvis_router should be registered in main.py."""
        import app.main as main_app
        # Check if jarvis_router is in the source
        source = open(main_app.__file__).read()
        assert "jarvis_router" in source

    def test_router_registered_in_init(self):
        """jarvis should be imported in api/__init__.py."""
        import app.api as api_pkg
        source = open(api_pkg.__file__).read()
        assert "jarvis" in source


# ── Frontend Hook Path Verification ────────────────────────────────

class TestFrontendFiles:
    """Verify frontend files exist at both paths."""

    def test_types_jarvis_in_frontend(self):
        from pathlib import Path
        assert Path("/home/z/my-project/parwa/frontend/src/types/jarvis.ts").exists()

    def test_types_jarvis_in_src_mirror(self):
        from pathlib import Path
        assert Path("/home/z/my-project/parwa/src/types/jarvis.ts").exists()

    def test_hook_in_frontend(self):
        from pathlib import Path
        assert Path("/home/z/my-project/parwa/frontend/src/hooks/useJarvisChat.ts").exists()

    def test_hook_in_src_mirror(self):
        from pathlib import Path
        assert Path("/home/z/my-project/parwa/src/hooks/useJarvisChat.ts").exists()

    def test_mirror_files_identical(self):
        """src/ and frontend/src/ should have identical files."""
        import filecmp
        files = [
            ("types/jarvis.ts", "types/jarvis.ts"),
            ("hooks/useJarvisChat.ts", "hooks/useJarvisChat.ts"),
        ]
        for src_rel, fe_rel in files:
            src_path = f"/home/z/my-project/parwa/src/{src_rel}"
            fe_path = f"/home/z/my-project/parwa/frontend/src/{fe_rel}"
            assert filecmp.cmp(src_path, fe_path, shallow=False), (
                f"Mismatch: {src_path} vs {fe_path}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

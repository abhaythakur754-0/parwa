"""
PARWA Router Security Fixes — Unit & Integration Tests (R-01 to R-04)

Covers:
1. R-01: JWT auth required on ooo_detection, bounce_complaint, sms_channel
2. R-02: current_user typed as User (not Dict) across 14 routers
3. R-03: Demo OTP bypass removed — verify_call_otp validates OTP
4. R-04: Error responses do not leak internal exception details

All tests use source-file inspection (no runtime imports that depend on DB/Redis).
"""

import inspect
import json
import os
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_DIR = PROJECT_ROOT / "app" / "api"


# ═══════════════════════════════════════════════════════════════════
# 1. R-01: JWT Auth on Previously Unprotected Routers
# ═══════════════════════════════════════════════════════════════════


class TestR01OOODetectionJWTAuth(unittest.TestCase):
    """Verify ooo_detection.py endpoints require JWT auth."""

    @classmethod
    def setUpClass(cls):
        filepath = API_DIR / "ooo_detection.py"
        with open(filepath) as f:
            cls.source = f.read()

    def test_imports_get_current_user(self):
        """ooo_detection.py must import get_current_user."""
        self.assertIn("from app.api.deps import get_current_user", self.source)

    def test_imports_user_model(self):
        """ooo_detection.py must import User model."""
        self.assertIn("from database.models.core import User", self.source)

    def test_company_id_from_current_user(self):
        """company_id must come from current_user.company_id."""
        self.assertIn("current_user.company_id", self.source)

    def test_no_request_state_company_id(self):
        """Must NOT rely on request.state.company_id (middleware bypass risk)."""
        self.assertNotIn(
            'getattr(request.state, "company_id", None)',
            self.source,
            "ooo_detection.py must use current_user.company_id, not request.state"
        )

    def test_all_endpoints_have_current_user_param(self):
        """Every endpoint function must have current_user: User parameter."""
        # Find all async def functions that are route handlers
        endpoint_funcs = re.findall(
            r'async def (\w+)\([^)]*current_user: User = Depends\(get_current_user\)',
            self.source,
        )
        self.assertGreaterEqual(
            len(endpoint_funcs), 7,
            f"All 7 endpoints must have current_user: User param, found {len(endpoint_funcs)}: {endpoint_funcs}"
        )

    def test_no_dict_type_for_current_user(self):
        """No endpoint should have current_user: Dict type hint."""
        self.assertNotIn(
            'current_user: Dict = Depends(get_current_user)',
            self.source,
            "Must use User type, not Dict"
        )


class TestR01BounceComplaintJWTAuth(unittest.TestCase):
    """Verify bounce_complaint.py endpoints require JWT auth."""

    @classmethod
    def setUpClass(cls):
        filepath = API_DIR / "bounce_complaint.py"
        with open(filepath) as f:
            cls.source = f.read()

    def test_imports_get_current_user(self):
        self.assertIn("from app.api.deps import get_current_user", self.source)

    def test_imports_user_model(self):
        self.assertIn("from database.models.core import User", self.source)

    def test_company_id_from_current_user(self):
        self.assertIn("current_user.company_id", self.source)

    def test_no_request_state_company_id(self):
        self.assertNotIn(
            'getattr(request.state, "company_id", None)',
            self.source,
            "bounce_complaint.py must use current_user.company_id"
        )

    def test_all_endpoints_have_current_user_param(self):
        """All 5 endpoints must have current_user parameter."""
        endpoint_funcs = re.findall(
            r'async def (\w+)\([^)]*current_user: User = Depends\(get_current_user\)',
            self.source,
        )
        self.assertGreaterEqual(
            len(endpoint_funcs), 5,
            f"All 5 endpoints must have current_user: User param, found {len(endpoint_funcs)}"
        )


class TestR01SMSChannelJWTAuth(unittest.TestCase):
    """Verify sms_channel.py endpoints require JWT auth (except webhook)."""

    @classmethod
    def setUpClass(cls):
        filepath = API_DIR / "sms_channel.py"
        with open(filepath) as f:
            cls.source = f.read()

    def test_imports_get_current_user(self):
        self.assertIn("from app.api.deps import get_current_user", self.source)

    def test_imports_user_model(self):
        self.assertIn("from database.models.core import User", self.source)

    def test_company_id_from_current_user(self):
        self.assertIn("current_user.company_id", self.source)

    def test_no_request_state_company_id(self):
        """Non-webhook endpoints must NOT rely on request.state.company_id."""
        self.assertNotIn(
            'getattr(request.state, "company_id", None)',
            self.source,
            "sms_channel.py must use current_user.company_id for non-webhook endpoints"
        )

    def test_webhook_does_not_use_jwt(self):
        """Twilio webhook endpoint must NOT have current_user parameter."""
        # Find the webhook function
        webhook_match = re.search(
            r'async def twilio_status_callback\(([^)]*)\)',
            self.source,
        )
        self.assertIsNotNone(webhook_match, "twilio_status_callback must exist")
        webhook_params = webhook_match.group(1)
        self.assertNotIn(
            "current_user", webhook_params,
            "Webhook endpoint must NOT use JWT auth"
        )

    def test_webhook_has_hmac_verification(self):
        """Twilio webhook must verify HMAC signature."""
        self.assertIn("verify_twilio_signature", self.source)

    def test_non_webhook_endpoints_have_auth(self):
        """All non-webhook endpoints must have current_user parameter."""
        endpoint_funcs = re.findall(
            r'async def (\w+)\([^)]*current_user: User = Depends\(get_current_user\)',
            self.source,
        )
        self.assertGreaterEqual(
            len(endpoint_funcs), 10,
            f"At least 10 non-webhook endpoints must have current_user, found {len(endpoint_funcs)}"
        )


# ═══════════════════════════════════════════════════════════════════
# 2. R-02: current_user Typed as User (Not Dict)
# ═══════════════════════════════════════════════════════════════════


class TestR02CurrentUserTypeHints(unittest.TestCase):
    """Verify all 14 routers use current_user: User instead of Dict."""

    AFFECTED_ROUTERS = [
        "tickets", "identity", "customers", "ticket_messages",
        "ticket_bulk", "channels", "sla", "ticket_notes",
        "ticket_search", "ticket_classification", "ticket_merge",
        "ticket_timeline", "ticket_analytics", "ticket_assignment",
    ]

    def test_no_current_user_dict_type_hints(self):
        """No router should have current_user: Dict = Depends(get_current_user)."""
        for name in self.AFFECTED_ROUTERS:
            filepath = API_DIR / f"{name}.py"
            with open(filepath) as f:
                content = f.read()
            self.assertNotIn(
                'current_user: Dict = Depends(get_current_user)',
                content,
                f"{name}.py must NOT have current_user: Dict type hint"
            )

    def test_all_routers_use_user_type_hint(self):
        """All affected routers must use current_user: User = Depends(get_current_user)."""
        for name in self.AFFECTED_ROUTERS:
            filepath = API_DIR / f"{name}.py"
            with open(filepath) as f:
                content = f.read()
            self.assertIn(
                'current_user: User = Depends(get_current_user)',
                content,
                f"{name}.py must have current_user: User type hint"
            )

    def test_all_routers_import_user_model(self):
        """All affected routers must import User from database.models.core."""
        for name in self.AFFECTED_ROUTERS:
            filepath = API_DIR / f"{name}.py"
            with open(filepath) as f:
                content = f.read()
            self.assertIn(
                'from database.models.core import User',
                content,
                f"{name}.py must import User from database.models.core"
            )

    def test_no_current_user_dot_get_calls(self):
        """No router should use current_user.get() — must use direct attributes."""
        for name in self.AFFECTED_ROUTERS:
            filepath = API_DIR / f"{name}.py"
            with open(filepath) as f:
                content = f.read()
            self.assertNotIn(
                'current_user.get(',
                content,
                f"{name}.py must NOT use current_user.get()"
            )

    def test_company_id_as_attribute(self):
        """company_id must be accessed as current_user.company_id."""
        for name in self.AFFECTED_ROUTERS:
            filepath = API_DIR / f"{name}.py"
            with open(filepath) as f:
                content = f.read()
            # If the file uses current_user, it must use .company_id attribute
            if "current_user" in content and "Depends(get_current_user)" in content:
                self.assertNotIn(
                    'current_user.get("company_id")',
                    content,
                    f"{name}.py must use current_user.company_id, not .get()"
                )

    def test_user_id_as_str_current_user_id(self):
        """user_id must be accessed as str(current_user.id)."""
        for name in self.AFFECTED_ROUTERS:
            filepath = API_DIR / f"{name}.py"
            with open(filepath) as f:
                content = f.read()
            self.assertNotIn(
                'current_user.get("user_id")',
                content,
                f"{name}.py must NOT use current_user.get('user_id')"
            )
            self.assertNotIn(
                'current_user.get("id")',
                content,
                f"{name}.py must NOT use current_user.get('id')"
            )


class TestR02TicketAnalyticsHelperFix(unittest.TestCase):
    """Verify ticket_analytics.py helper function is fixed."""

    @classmethod
    def setUpClass(cls):
        filepath = API_DIR / "ticket_analytics.py"
        with open(filepath) as f:
            cls.source = f.read()

    def test_helper_uses_attribute_not_dict_check(self):
        """Helper must use current_user.company_id directly, not isinstance check."""
        # Find the helper function
        match = re.search(
            r'def get_company_id_from_user\(([^)]*)\)[^:]*:(.*?)(?=\n(?:def |class |$))',
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "get_company_id_from_user must exist")
        func_body = match.group(2)
        self.assertIn("current_user.company_id", func_body)
        self.assertNotIn("isinstance(current_user, dict)", func_body)

    def test_helper_typed_as_user(self):
        """Helper parameter must be typed as User."""
        match = re.search(
            r'def get_company_id_from_user\(([^)]*)\)',
            self.source,
        )
        self.assertIsNotNone(match)
        params = match.group(1)
        self.assertIn("User", params, "Parameter must be typed as User")


# ═══════════════════════════════════════════════════════════════════
# 3. R-03: Demo OTP Bypass Removed
# ═══════════════════════════════════════════════════════════════════


class TestR03DemoOTPBypassRemoved(unittest.TestCase):
    """Verify verify_call_otp no longer always returns 'verified'."""

    @classmethod
    def setUpClass(cls):
        jarvis_api_path = API_DIR / "jarvis.py"
        with open(jarvis_api_path) as f:
            cls.jarvis_api_source = f.read()

        jarvis_svc_path = PROJECT_ROOT / "app" / "services" / "jarvis_service.py"
        with open(jarvis_svc_path) as f:
            cls.jarvis_svc_source = f.read()

    def test_endpoint_delegates_to_service(self):
        """verify_call_otp must delegate to jarvis_service.verify_demo_call_otp."""
        # Find verify_call_otp function in jarvis.py (spans multiple lines)
        match = re.search(
            r'def verify_call_otp\(.*?\):.*?(?=\n@(router|router))',
            self.jarvis_api_source,
            re.DOTALL,
        )
        if match is None:
            # Try alternate: just find the function and its body
            match = re.search(
                r'def verify_call_otp\(.*?\):.*?return result\n\n',
                self.jarvis_api_source,
                re.DOTALL,
            )
        self.assertIsNotNone(match, "verify_call_otp function must exist")
        func_body = match.group(0)
        self.assertIn(
            "jarvis_service.verify_demo_call_otp",
            func_body,
            "verify_call_otp must call jarvis_service.verify_demo_call_otp"
        )

    def test_no_hardcoded_verified_return(self):
        """verify_call_otp must NOT have a hardcoded always-verified return."""
        match = re.search(
            r'def verify_call_otp\(.*?\):.*?return result\n\n',
            self.jarvis_api_source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        func_body = match.group(0)
        self.assertNotIn(
            '# Placeholder',
            func_body,
            "Placeholder comment must be removed"
        )
        # Should not have a direct return with always-verified
        self.assertNotRegex(
            func_body,
            r'return\s*\{\s*"status":\s*"verified"\s*\}',
            "Must not have unconditional verified return"
        )

    def test_service_function_exists(self):
        """jarvis_service.py must define verify_demo_call_otp function."""
        self.assertIn(
            "def verify_demo_call_otp",
            self.jarvis_svc_source,
            "jarvis_service.py must define verify_demo_call_otp"
        )

    def test_service_validates_otp_code(self):
        """verify_demo_call_otp must compare otp_code against stored value."""
        # Use a more flexible regex that handles multi-line function defs
        match = re.search(
            r'def verify_demo_call_otp\(.*?\):.*?(?=\ndef [a-z_])',
            self.jarvis_svc_source,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "verify_demo_call_otp must exist in jarvis_service")
        func_body = match.group(0)
        self.assertIn("stored_otp", func_body,
                       "Must reference stored_otp for comparison")
        self.assertIn("otp_code", func_body,
                       "Must compare against provided otp_code")
        self.assertIn('"rejected"', func_body,
                       "Must reject invalid OTP codes")
        self.assertIn('"verified"', func_body,
                       "Must verify correct OTP codes")

    def test_service_checks_otp_expiry(self):
        """verify_demo_call_otp must check OTP expiry (10 min window)."""
        match = re.search(
            r'def verify_demo_call_otp\(.*?\):.*?(?=\ndef [a-z_])',
            self.jarvis_svc_source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        func_body = match.group(0)
        self.assertIn("expired", func_body,
                       "Must check for expired OTP")
        self.assertIn("600", func_body,
                       "Must enforce 600 second (10 min) expiry")

    def test_service_rejects_no_demo_call(self):
        """verify_demo_call_otp must reject when no demo call was initiated."""
        match = re.search(
            r'def verify_demo_call_otp\(.*?\):.*?(?=\ndef [a-z_])',
            self.jarvis_svc_source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        func_body = match.group(0)
        self.assertIn("demo_call", func_body)
        self.assertIn('"error"', func_body)

    def test_service_rejects_no_stored_otp(self):
        """verify_demo_call_otp must reject when no OTP was stored."""
        match = re.search(
            r'def verify_demo_call_otp\(.*?\):.*?(?=\ndef [a-z_])',
            self.jarvis_svc_source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        func_body = match.group(0)
        self.assertIn("stored_otp", func_body)
        self.assertIn("Twilio Verify", func_body,
                       "Must mention Twilio Verify when no OTP configured")


# ═══════════════════════════════════════════════════════════════════
# 4. R-04: Error Responses Do Not Leak Internal Details
# ═══════════════════════════════════════════════════════════════════


class TestR04NoInternalErrorLeak(unittest.TestCase):
    """Verify jarvis.py payment_webhook does not leak str(exc) in response."""

    @classmethod
    def setUpClass(cls):
        filepath = API_DIR / "jarvis.py"
        with open(filepath) as f:
            cls.source = f.read()

    def test_webhook_error_details_not_str_exc(self):
        """payment_webhook must NOT include str(exc) in error details."""
        self.assertNotIn(
            '"details": str(exc)',
            self.source,
            "payment_webhook must NOT include str(exc) in error details"
        )

    def test_webhook_error_details_is_none(self):
        """Error response details must be None."""
        self.assertIn('"details": None', self.source,
                       "payment_webhook error details must be None")

    def test_webhook_logs_error_server_side(self):
        """Error must be logged server-side."""
        self.assertIn("logger.error", self.source,
                       "payment_webhook must log errors server-side")

    def test_no_str_exc_in_any_error_details(self):
        """No endpoint in jarvis.py should have str(exc) in error details."""
        # Search for the dangerous pattern across the whole file
        self.assertNotRegex(
            self.source,
            r'"details":\s*str\(exc\)',
            "No endpoint should include str(exc) in error details"
        )

    def test_r04_comment_present(self):
        """R-04 fix should have a comment explaining the change."""
        self.assertIn("R-04", self.source,
                       "jarvis.py should document the R-04 fix")


# ═══════════════════════════════════════════════════════════════════
# Integration: R-01 + R-02 Combined Auth Check
# ═══════════════════════════════════════════════════════════════════


class TestR01R02IntegrationAuthEnforcement(unittest.TestCase):
    """Integration test: Verify auth is enforced end-to-end across all routers."""

    def test_no_dict_type_hints_anywhere(self):
        """No router file should have current_user: Dict type hint."""
        py_files = list(API_DIR.glob("*.py"))
        violations = []
        for filepath in py_files:
            with open(filepath) as f:
                content = f.read()
            if 'current_user: Dict = Depends(get_current_user)' in content:
                violations.append(filepath.name)
        self.assertEqual(
            violations, [],
            f"Files still using current_user: Dict: {violations}"
        )

    def test_no_get_calls_on_current_user_anywhere(self):
        """No router file should use current_user.get()."""
        py_files = list(API_DIR.glob("*.py"))
        violations = []
        for filepath in py_files:
            with open(filepath) as f:
                content = f.read()
            if 'current_user.get(' in content:
                violations.append(filepath.name)
        self.assertEqual(
            violations, [],
            f"Files still using current_user.get(): {violations}"
        )

    def test_r01_routers_derive_company_id_from_user(self):
        """R-01 routers must derive company_id from current_user, not request.state."""
        r01_routers = ["ooo_detection", "bounce_complaint", "sms_channel"]
        for name in r01_routers:
            filepath = API_DIR / f"{name}.py"
            with open(filepath) as f:
                content = f.read()
            self.assertNotIn(
                'getattr(request.state, "company_id", None)',
                content,
                f"{name}.py must not rely on request.state.company_id"
            )
            self.assertIn(
                "current_user.company_id",
                content,
                f"{name}.py must derive company_id from current_user"
            )

    def test_deps_get_current_user_returns_user(self):
        """get_current_user in deps.py must have User return type."""
        deps_path = API_DIR / "deps.py"
        with open(deps_path) as f:
            content = f.read()
        # Function should return User (definition spans multiple lines)
        match = re.search(r'async def get_current_user\(.*?\)\s*->\s*(\w+)', content, re.DOTALL)
        self.assertIsNotNone(match, "get_current_user must have return type annotation")
        self.assertEqual(match.group(1), "User",
                         "get_current_user must return User type")


class TestJarvisAuthConsistency(unittest.TestCase):
    """Verify jarvis.py uses User type consistently."""

    @classmethod
    def setUpClass(cls):
        filepath = API_DIR / "jarvis.py"
        with open(filepath) as f:
            cls.source = f.read()

    def test_jarvis_uses_user_not_dict(self):
        """jarvis.py must use User type for auth, not Dict."""
        self.assertNotIn(
            'current_user: Dict = Depends(get_current_user)',
            self.source,
            "jarvis.py should use User type, not Dict"
        )
        self.assertIn("user: User = Depends(get_current_user)", self.source,
                       "jarvis.py should use User type for auth")

    def test_jarvis_imports_user(self):
        """jarvis.py must import User from database.models.core."""
        self.assertIn("from database.models.core import User", self.source)


# ═══════════════════════════════════════════════════════════════════
# Regression: Verify chat_widget.py (already fixed) still correct
# ═══════════════════════════════════════════════════════════════════


class TestChatWidgetAuthRegression(unittest.TestCase):
    """Verify chat_widget.py (previously fixed) hasn't regressed."""

    @classmethod
    def setUpClass(cls):
        filepath = API_DIR / "chat_widget.py"
        with open(filepath) as f:
            cls.source = f.read()

    def test_chat_widget_uses_user_type(self):
        """chat_widget.py must use User type for auth, not Dict."""
        self.assertNotIn(
            'current_user: Dict = Depends(get_current_user)',
            self.source,
        )
        # chat_widget uses _auth: User pattern
        self.assertIn("User = Depends(get_current_user)", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

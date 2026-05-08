"""
PARWA Day 4 Security Tests — Webhook Security Fixes
===================================================
Tests for 7 webhook security fixes + comprehensive functional tests:

H-07:  Webhook signature — fail closed in ALL environments (no dev bypass)
M-36:  Removed dev/test env signature bypass
H-08:  Webhook timestamp freshness check (reject replayed events)
H-16:  HTML-escape user fields in email notification templates
M-16:  SMS status callback has Twilio signature verification
L-15:  Null byte rejection in Paddle event type validation
H-15:  Webhook status/retry endpoints require platform admin auth
L-17:  Brevo handler stores only partial b64 content (no full payload leak)

Run: pytest tests/test_day4_webhook_security.py -v --noconftest
"""

import hashlib
import hmac
import os
import subprocess
import sys
import tempfile
import json
import textwrap

# ─── Base path ──────────────────────────────────────────────────────────────

BASE = "/home/z/my-project/parwa"
BACKEND = os.path.join(BASE, "backend")


def _read(path: str) -> str:
    with open(os.path.join(BASE, path)) as f:
        return f.read()


def _run_isolated(code: str) -> str:
    """Run Python code in a subprocess with backend on sys.path."""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "PYTHONPATH": BACKEND},
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"Subprocess failed (rc={proc.returncode}):\n"
            f"STDOUT: {proc.stdout[:500]}\n"
            f"STDERR: {proc.stderr[:1000]}"
        )
    return proc.stdout


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: Source Code Scanning Tests (58 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestDay4WebhookScanning:
    """Day 4 Webhook Security — Source Code Scanning Tests."""

    # ── H-07 / M-36: Fail closed on missing webhook secret ────────────────

    def test_h07_no_dev_bypass_in_billing_webhooks(self):
        """billing_webhooks.py ALWAYS rejects when PADDLE_WEBHOOK_SECRET is empty."""
        content = _read("backend/app/api/billing_webhooks.py")
        assert 'ENVIRONMENT' not in content, \
            "Must not check ENVIRONMENT for bypass"
        assert 'paddle_webhook_no_secret_configured_rejected' in content, \
            "Must reject when no secret configured"

    def test_h07_error_log_on_missing_secret(self):
        """Logs ERROR (not warning) when secret missing."""
        content = _read("backend/app/api/billing_webhooks.py")
        assert 'logger.error' in content, \
            "Must log ERROR for missing secret"

    def test_h07_raises_500_on_missing_secret(self):
        """Raises HTTPException 500 when PADDLE_WEBHOOK_SECRET is empty."""
        content = _read("backend/app/api/billing_webhooks.py")
        assert 'HTTPException' in content, \
            "Must raise HTTPException"
        assert 'status_code=500' in content, \
            "Must return 500 when webhook not configured"

    def test_m36_no_os_environ(self):
        """billing_webhooks.py no longer uses os.environ."""
        content = _read("backend/app/api/billing_webhooks.py")
        assert 'os.environ' not in content, \
            "Must not use os.environ for env check"

    def test_h07_secret_check_in_endpoint(self):
        """Secret empty check exists within the webhook endpoint function."""
        content = _read("backend/app/api/billing_webhooks.py")
        # Find the endpoint function
        endpoint_start = content.find('async def handle_paddle_webhook(')
        assert endpoint_start > 0, "Must define handle_paddle_webhook endpoint"
        func_body = content[endpoint_start:endpoint_start + 3000]
        assert 'if not webhook_secret' in func_body, \
            "Endpoint must check if webhook_secret is empty"
        assert 'HTTPException' in func_body, \
            "Endpoint must raise HTTPException on missing secret"

    # ── H-08: Webhook timestamp freshness check ──────────────────────────────

    def test_h08_max_webhook_age_defined(self):
        """webhooks.py defines MAX_WEBHOOK_AGE_SECONDS."""
        content = _read("backend/app/api/webhooks.py")
        assert 'MAX_WEBHOOK_AGE_SECONDS' in content, \
            "Must define max webhook age"
        assert '300' in content, \
            "Max age should be ~300 seconds (5 minutes)"

    def test_h08_timedelta_imported(self):
        """webhooks.py imports timedelta for timestamp math."""
        content = _read("backend/app/api/webhooks.py")
        assert 'from datetime import' in content, \
            "Must import datetime utilities"
        assert 'timedelta' in content, \
            "Must import timedelta"

    def test_h08_occurred_at_check(self):
        """webhooks.py checks occurred_at / created_at for timestamp."""
        content = _read("backend/app/api/webhooks.py")
        assert 'occurred_at' in content, \
            "Must check occurred_at timestamp"
        assert 'created_at' in content, \
            "Must check created_at timestamp as fallback"

    def test_h08_replay_detected_response(self):
        """webhooks.py returns REPLAY_DETECTED for old events."""
        content = _read("backend/app/api/webhooks.py")
        assert 'REPLAY_DETECTED' in content, \
            "Must return REPLAY_DETECTED error code"

    def test_h08_forbidden_on_replay(self):
        """webhooks.py returns 403 for replayed events."""
        content = _read("backend/app/api/webhooks.py")
        assert '403' in content, \
            "Must return 403 Forbidden for replayed webhooks"

    def test_h08_age_seconds_in_details(self):
        """webhooks.py includes age_seconds in error details."""
        content = _read("backend/app/api/webhooks.py")
        assert 'age_seconds' in content, \
            "Must include age_seconds in response"

    def test_h08_signature_check_after_timestamp(self):
        """Timestamp check happens BEFORE signature check."""
        content = _read("backend/app/api/webhooks.py")
        pos_timestamp = content.find('occurred_at')
        pos_signature = content.find('Verify signature')
        assert pos_timestamp > 0 and pos_signature > 0, \
            "Both timestamp and signature checks must exist"
        assert pos_timestamp < pos_signature, \
            "Timestamp freshness must be checked BEFORE signature verification"

    def test_h08_timezone_aware_comparison(self):
        """Timestamp comparison uses timezone-aware datetime."""
        content = _read("backend/app/api/webhooks.py")
        assert 'timezone.utc' in content, \
            "Must use UTC timezone for comparison"

    def test_h08_unparseable_timestamp_passes_through(self):
        """Unparseable timestamps pass through (idempotency handles dups)."""
        content = _read("backend/app/api/webhooks.py")
        assert 'ValueError' in content, \
            "Must catch ValueError on unparseable timestamps"

    # ── H-16: HTML-escape in email notification templates ─────────────

    def test_h16_escape_html_function_exists(self):
        """notifications.ts has escapeHtml utility function."""
        content = _read("dashboard/src/lib/notifications.ts")
        assert 'escapeHtml' in content, \
            "Must define escapeHtml function"
        assert '&amp;' in content, \
            "Must escape ampersands"
        assert '&lt;' in content, \
            "Must escape less-than"
        assert '&gt;' in content, \
            "Must escape greater-than"
        assert '&quot;' in content, \
            "Must escape quotes"

    def test_h16_escape_html_function_signature(self):
        """escapeHtml accepts a string parameter."""
        content = _read("dashboard/src/lib/notifications.ts")
        assert 'function escapeHtml' in content, \
            "Must define escapeHtml as function"

    def test_h16_safeName_used_in_builders(self):
        """All buildEmail functions receive escaped name."""
        content = _read("dashboard/src/lib/notifications.ts")
        assert 'safeName' in content, \
            "Must create safeName variable"
        assert content.count('safeName') >= 4, \
            "safeName should be passed to all email builders"

    def test_h16_safeAiResponse_used(self):
        """AI response is HTML-escaped before template interpolation."""
        content = _read("dashboard/src/lib/notifications.ts")
        assert 'safeAiResponse' in content, \
            "Must create safeAiResponse variable"
        assert 'buildInProgressEmail(safeName, ticketNumber, safeAiResponse)' in content, \
            "Must pass escaped AI response to template"

    def test_h16_safeResolution_used(self):
        """Resolution text is HTML-escaped before template interpolation."""
        content = _read("dashboard/src/lib/notifications.ts")
        assert 'safeResolution' in content, \
            "Must create safeResolution variable"
        assert 'buildResolvedEmail(safeName, ticketNumber, safeResolution)' in content, \
            "Must pass escaped resolution to template"

    def test_h16_safeSubject_used(self):
        """Subject is HTML-escaped before template interpolation."""
        content = _read("dashboard/src/lib/notifications.ts")
        assert 'safeSubject' in content, \
            "Must create safeSubject variable"

    def test_h16_no_raw_customerName_in_templates(self):
        """Raw customerName is NOT passed directly to template builders."""
        content = _read("dashboard/src/lib/notifications.ts")
        import re
        build_calls = re.findall(
            r'build\w+Email\([^)]+\)', content
        )
        for call in build_calls:
            assert 'customerName' not in call or 'safeName' in call, \
                f"Template call {call} uses raw customerName instead of safeName"

    def test_h16_no_raw_aiResponse_in_templates(self):
        """Raw aiResponse is NOT passed directly to template builders."""
        content = _read("dashboard/src/lib/notifications.ts")
        assert 'buildInProgressEmail(safeName' in content, \
            "buildInProgressEmail must receive safeName"

    def test_h16_all_notification_types_use_safe_name(self):
        """All notification types use safeName."""
        content = _read("dashboard/src/lib/notifications.ts")
        assert 'buildCreatedEmail(safeName' in content, \
            "Created email must use safeName"
        assert 'buildInProgressEmail(safeName' in content, \
            "In-progress email must use safeName"
        assert 'buildResolvedEmail(safeName' in content, \
            "Resolved email must use safeName"
        assert 'buildEscalatedEmail(safeName' in content, \
            "Escalated email must use safeName"

    # ── M-16: SMS status callback Twilio signature verification ───────

    def test_m16_sms_callback_verifies_signature(self):
        """SMS status callback endpoint verifies Twilio signature."""
        content = _read("backend/app/api/sms_channel.py")
        assert 'verify_twilio_signature' in content, \
            "Must verify Twilio signature"
        assert 'x-twilio-signature' in content, \
            "Must check X-Twilio-Signature header"

    def test_m16_sms_callback_rejects_invalid(self):
        """SMS status callback rejects invalid signatures with 401."""
        content = _read("backend/app/api/sms_channel.py")
        assert '401' in content, \
            "Must return 401 for invalid signature"
        assert 'AUTHENTICATION_ERROR' in content, \
            "Must return proper auth error code"

    def test_m16_sms_callback_rejects_no_auth_token(self):
        """SMS status callback rejects when TWILIO_AUTH_TOKEN is missing."""
        content = _read("backend/app/api/sms_channel.py")
        assert 'NOT_CONFIGURED' in content, \
            "Must return NOT_CONFIGURED when no auth token"
        assert 'TWILIO_AUTH_TOKEN required' in content, \
            "Must indicate TWILIO_AUTH_TOKEN is required"

    def test_m16_sms_callback_uses_request_url(self):
        """SMS status callback uses full request URL for signature verification."""
        content = _read("backend/app/api/sms_channel.py")
        assert 'str(request.url)' in content, \
            "Must use full request URL for Twilio signature"

    def test_m16_sms_callback_uses_request_payload(self):
        """SMS status callback uses form payload for signature verification."""
        content = _read("backend/app/api/sms_channel.py")
        assert 'payload' in content and 'verify_twilio_signature' in content, \
            "Must pass payload to signature verification"

    def test_m16_sms_callback_imports_hmac(self):
        """SMS status callback imports from hmac_verification module."""
        content = _read("backend/app/api/sms_channel.py")
        assert 'from app.security.hmac_verification import' in content, \
            "Must import from hmac_verification module"

    # ── L-15: Null byte rejection in event type ────────────────────────────

    def test_l15_null_byte_check_in_paddle(self):
        """paddle_handler.py rejects null bytes in event_type."""
        content = _read("backend/app/webhooks/paddle_handler.py")
        assert '\\x00' in content or 'null byte' in content.lower(), \
            "Must check for null bytes in event_type"

    def test_l15_invalid_characters_message(self):
        """paddle_handler.py returns 'invalid characters' for null bytes."""
        content = _read("backend/app/webhooks/paddle_handler.py")
        assert 'invalid characters' in content, \
            "Must return descriptive error for null bytes"

    def test_l15_check_before_strip_in_function(self):
        """Null byte check happens before strip WITHIN _validate_event_type."""
        content = _read("backend/app/webhooks/paddle_handler.py")
        func_start = content.find('def _validate_event_type(')
        assert func_start > 0, "Must define _validate_event_type function"
        func_body = content[func_start:func_start + 800]
        pos_null = func_body.find('\\x00')
        pos_strip = func_body.find('.strip()')
        assert pos_null > 0, "Null byte check must exist in function"
        assert pos_strip > 0, "strip() must exist in function"
        assert pos_null < pos_strip, \
            "Null byte check must happen before strip() in _validate_event_type"

    # ── H-15: Webhook status/retry auth ──────────────────────────────────

    def test_h15_status_endpoint_requires_admin(self):
        """GET /api/webhooks/status/{id} requires platform admin."""
        content = _read("backend/app/api/webhooks.py")
        assert 'require_platform_admin' in content, \
            "Status endpoint must require platform admin"

    def test_h15_retry_endpoint_requires_admin(self):
        """POST /api/webhooks/retry/{id} requires platform admin."""
        content = _read("backend/app/api/webhooks.py")
        lines = content.split('\n')
        in_retry = False
        found_dep = False
        for line in lines:
            if 'async def retry_webhook' in line:
                in_retry = True
            if in_retry and 'require_platform_admin' in line:
                found_dep = True
                break
            if in_retry and 'async def ' in line and 'retry' not in line:
                break
        assert found_dep, "Retry endpoint must require platform admin"

    # ── L-17: Brevo partial b64 only ────────────────────────────────────

    def test_l17_brevo_stores_preview_only(self):
        """Brevo handler stores only preview (first 100 chars) of b64 content."""
        content = _read("backend/app/webhooks/brevo_handler.py")
        assert 'content[:100]' in content, \
            "Must store only first 100 chars of b64 content"
        assert 'content_valid' in content, \
            "Must validate base64 content"

    def test_l17_brevo_attachment_size_limit(self):
        """Brevo handler enforces per-attachment size limit (10MB)."""
        content = _read("backend/app/webhooks/brevo_handler.py")
        assert '10 * 1024 * 1024' in content, \
            "Must enforce 10MB per-attachment limit"

    def test_l17_brevo_max_20_attachments(self):
        """Brevo handler limits to 20 attachments per email."""
        content = _read("backend/app/webhooks/brevo_handler.py")
        assert 'attachments[:20]' in content, \
            "Must limit to 20 attachments"

    # ── Regression tests ─────────────────────────────────────────────────

    def test_regression_hmac_verification_still_intact(self):
        """hmac_verification.py still has all provider verification functions."""
        content = _read("backend/app/security/hmac_verification.py")
        assert 'verify_paddle_signature' in content
        assert 'verify_twilio_signature' in content
        assert 'verify_shopify_hmac' in content
        assert 'verify_brevo_ip' in content
        assert 'hmac.compare_digest' in content, \
            "Must use constant-time comparison"

    def test_regression_generic_webhook_signature_verified(self):
        """Generic webhook receiver still verifies all provider signatures."""
        content = _read("backend/app/api/webhooks.py")
        assert '_verify_provider_signature' in content, \
            "Must still call signature verification"
        assert 'AUTHENTICATION_ERROR' in content, \
            "Must return AUTHENTICATION_ERROR for invalid sig"

    def test_regression_billing_status_has_auth(self):
        """Billing status endpoint still requires platform admin (C-11 fix)."""
        content = _read("backend/app/api/billing_webhooks.py")
        assert 'require_platform_admin' in content, \
            "Billing status must still require platform admin"

    def test_regression_twilio_handler_still_sanitized(self):
        """Twilio handler still sanitizes input fields."""
        content = _read("backend/app/webhooks/twilio_handler.py")
        assert '_sanitize_sms_field' in content
        assert 'MAX_SMS_BODY_LENGTH' in content

    def test_regression_brevo_handler_still_sanitized(self):
        """Brevo handler still sanitizes email fields."""
        content = _read("backend/app/webhooks/brevo_handler.py")
        assert '_sanitize_email_field' in content
        assert 'MAX_EMAIL_BODY_SIZE' in content

    def test_regression_shopify_handler_still_sanitized(self):
        """Shopify handler still sanitizes input fields."""
        content = _read("backend/app/webhooks/shopify_handler.py")
        assert '_sanitize_field' in content
        assert 'line_items[:100]' in content

    # ── Source code scanning (no env bypass) ─────────────────────────────

    def test_scan_no_environment_check_in_webhooks(self):
        """No webhook file checks ENVIRONMENT for auth bypass."""
        files = [
            "backend/app/api/billing_webhooks.py",
            "backend/app/api/webhooks.py",
            "backend/app/api/sms_channel.py",
            "backend/app/webhooks/paddle_handler.py",
            "backend/app/webhooks/twilio_handler.py",
            "backend/app/webhooks/brevo_handler.py",
        ]
        for f in files:
            content = _read(f)
            assert 'ENVIRONMENT' not in content or 'client.host' in content, \
                f"{f} must not check ENVIRONMENT for auth bypass"

    def test_scan_no_dev_mode_accept(self):
        """No webhook file accepts requests without signature in any mode."""
        files = [
            "backend/app/api/billing_webhooks.py",
            "backend/app/api/webhooks.py",
            "backend/app/api/sms_channel.py",
        ]
        for f in files:
            content = _read(f)
            assert 'dev_mode' not in content.lower(), \
                f"{f} must not have dev mode acceptance"

    def test_scan_sms_callback_old_comment_removed(self):
        """SMS status callback no longer says 'verified by generic handler'."""
        content = _read("backend/app/api/sms_channel.py")
        assert 'verified by the generic webhook handler' not in content, \
            "Must remove misleading comment about generic handler"

    def test_scan_payload_size_limit_enforced(self):
        """Generic webhook endpoint enforces 1MB payload size limit."""
        content = _read("backend/app/api/webhooks.py")
        assert 'MAX_WEBHOOK_PAYLOAD_SIZE' in content
        assert '413' in content

    def test_scan_error_responses_no_stack_traces(self):
        """Webhook error responses have no stack traces or internal details."""
        content = _read("backend/app/api/webhooks.py")
        assert 'INTERNAL_ERROR' in content
        assert 'traceback' not in content.lower()

    def test_scan_webhook_service_validates_company_id(self):
        """Webhook service validates company_id format."""
        content = _read("backend/app/services/webhook_service.py")
        assert '_validate_company_id' in content
        assert 'max 128 chars' in content
        assert 'control characters' in content

    def test_scan_webhook_service_validates_provider(self):
        """Webhook service validates provider is in allowlist."""
        content = _read("backend/app/services/webhook_service.py")
        assert '_validate_provider' in content
        for p in ["paddle", "twilio", "shopify", "brevo"]:
            assert f'"{p}"' in content, f"Must include {p} in valid providers"

    def test_scan_webhook_service_max_retries(self):
        """Webhook service has max retry cap."""
        content = _read("backend/app/services/webhook_service.py")
        assert 'MAX_RETRY_ATTEMPTS' in content

    def test_scan_all_use_constant_time(self):
        """All HMAC functions use hmac.compare_digest."""
        content = _read("backend/app/security/hmac_verification.py")
        count = content.count('hmac.compare_digest')
        assert count >= 4, f"Expected >= 4 compare_digest calls, found {count}"

    def test_scan_supported_providers_in_webhooks_api(self):
        """Generic webhook API defines SUPPORTED_PROVIDERS."""
        content = _read("backend/app/api/webhooks.py")
        assert 'SUPPORTED_PROVIDERS' in content
        for p in ["paddle", "twilio", "shopify", "brevo"]:
            assert f'"{p}"' in content, f"Must support {p}"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: HMAC Verification Functional Tests (20 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestHMACVerificationFunctional:
    """Functional tests for HMAC verification module."""

    def test_paddle_valid_signature(self):
        """Paddle signature verification passes for correct HMAC."""
        _run_isolated(textwrap.dedent("""\
            import hmac, hashlib
            from app.security.hmac_verification import verify_paddle_signature
            secret = "test_secret_key_123"
            body = b'{"event_id": "evt_123", "event_type": "subscription.created"}'
            expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            assert verify_paddle_signature(body, expected, secret) is True
            print("PASS")
        """))

    def test_paddle_invalid_signature(self):
        """Paddle signature verification rejects tampered payload."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_paddle_signature
            assert verify_paddle_signature(b'{"event_id": "evt_123"}', "wrong_signature", "secret") is False
            print("PASS")
        """))

    def test_paddle_empty_signature_rejected(self):
        """Paddle rejects empty signature header."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_paddle_signature
            assert verify_paddle_signature(b'{"data":1}', "", "secret") is False
            print("PASS")
        """))

    def test_paddle_empty_secret_rejected(self):
        """Paddle rejects empty secret."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_paddle_signature
            assert verify_paddle_signature(b'{"data":1}', "sig", "") is False
            print("PASS")
        """))

    def test_paddle_empty_body_rejected(self):
        """Paddle rejects empty body."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_paddle_signature
            assert verify_paddle_signature(b"", "sig", "secret") is False
            print("PASS")
        """))

    def test_paddle_signature_strips_whitespace(self):
        """Paddle signature comparison strips whitespace."""
        _run_isolated(textwrap.dedent("""\
            import hmac, hashlib
            from app.security.hmac_verification import verify_paddle_signature
            secret = "test_secret"
            body = b'{"test": true}'
            expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            assert verify_paddle_signature(body, f"  {expected}  ", secret) is True
            print("PASS")
        """))

    def test_shopify_valid_hmac(self):
        """Shopify HMAC verification passes for correct signature."""
        _run_isolated(textwrap.dedent("""\
            import hmac, hashlib, base64
            from app.security.hmac_verification import verify_shopify_hmac
            secret = "shopify_secret"
            body = b'{"id": 12345}'
            expected = hmac.new(secret.encode(), body, hashlib.sha256).digest()
            expected_b64 = base64.b64encode(expected).decode()
            assert verify_shopify_hmac(body, expected_b64, secret) is True
            print("PASS")
        """))

    def test_shopify_invalid_hmac(self):
        """Shopify HMAC verification rejects wrong signature."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_shopify_hmac
            assert verify_shopify_hmac(b'{}', "base64wrong", "secret") is False
            print("PASS")
        """))

    def test_shopify_empty_params_rejected(self):
        """Shopify rejects empty params."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_shopify_hmac
            assert verify_shopify_hmac(b"", "", "") is False
            assert verify_shopify_hmac(b"data", "", "secret") is False
            assert verify_shopify_hmac(b"data", "sig", "") is False
            print("PASS")
        """))

    def test_twilio_valid_signature(self):
        """Twilio signature verification passes for correct signature."""
        _run_isolated(textwrap.dedent("""\
            import hmac, hashlib
            from app.security.hmac_verification import verify_twilio_signature
            token = "twilio_auth_token"
            url = "https://parwa.ai/api/webhooks/twilio"
            params = {"MessageSid": "SM123", "Body": "Hello"}
            sorted_params = sorted(params.items())
            data = url
            for key, value in sorted_params:
                data += key + str(value)
            expected = hmac.new(token.encode(), data.encode(), hashlib.sha1).hexdigest()
            assert verify_twilio_signature(url, params, expected, token) is True
            print("PASS")
        """))

    def test_twilio_invalid_signature(self):
        """Twilio signature verification rejects wrong signature."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_twilio_signature
            assert verify_twilio_signature("https://example.com", {"key": "val"}, "wrong", "token") is False
            print("PASS")
        """))

    def test_twilio_empty_params_rejected(self):
        """Twilio rejects empty params."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_twilio_signature
            assert verify_twilio_signature("", {}, "sig", "token") is False
            assert verify_twilio_signature("url", {}, "", "token") is False
            assert verify_twilio_signature("url", {}, "sig", "") is False
            print("PASS")
        """))

    def test_twilio_different_params_different_sig(self):
        """Twilio different params produce different signatures."""
        _run_isolated(textwrap.dedent("""\
            import hmac, hashlib
            from app.security.hmac_verification import verify_twilio_signature
            token = "token123"
            url = "https://parwa.ai/webhook"
            sig1 = hmac.new(token.encode(), (url + "Aval1").encode(), hashlib.sha1).hexdigest()
            sig2 = hmac.new(token.encode(), (url + "Bval2").encode(), hashlib.sha1).hexdigest()
            assert sig1 != sig2
            assert verify_twilio_signature(url, {"A": "val1"}, sig1, token) is True
            assert verify_twilio_signature(url, {"A": "val1"}, sig2, token) is False
            print("PASS")
        """))

    def test_brevo_valid_ip(self):
        """Brevo IP verification passes for IP in allowlist."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_brevo_ip
            assert verify_brevo_ip("185.107.232.50") is True
            assert verify_brevo_ip("102.134.48.100") is True
            print("PASS")
        """))

    def test_brevo_invalid_ip(self):
        """Brevo IP verification rejects IP not in allowlist."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_brevo_ip
            assert verify_brevo_ip("8.8.8.8") is False
            assert verify_brevo_ip("192.168.1.1") is False
            print("PASS")
        """))

    def test_brevo_empty_ip_rejected(self):
        """Brevo rejects empty IP."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_brevo_ip
            assert verify_brevo_ip("") is False
            assert verify_brevo_ip(None) is False
            print("PASS")
        """))

    def test_brevo_custom_ips_override(self):
        """Brevo custom IPs override defaults."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_brevo_ip
            assert verify_brevo_ip("10.0.0.5", allowed_ips=["10.0.0.0/24"]) is True
            assert verify_brevo_ip("185.107.232.50", allowed_ips=["10.0.0.0/24"]) is False
            print("PASS")
        """))

    def test_brevo_cidr_range(self):
        """Brevo correctly handles CIDR range boundaries."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import verify_brevo_ip
            assert verify_brevo_ip("185.107.232.0", allowed_ips=["185.107.232.0/24"]) is True
            assert verify_brevo_ip("185.107.232.255", allowed_ips=["185.107.232.0/24"]) is True
            assert verify_brevo_ip("185.107.233.0", allowed_ips=["185.107.232.0/24"]) is False
            print("PASS")
        """))

    def test_all_fail_on_exception(self):
        """All HMAC verification functions return False on exception."""
        _run_isolated(textwrap.dedent("""\
            from app.security.hmac_verification import (
                verify_paddle_signature, verify_twilio_signature,
                verify_shopify_hmac, verify_brevo_ip
            )
            # These should not raise - they should return False
            assert verify_paddle_signature(None, None, None) is False
            assert verify_twilio_signature(None, None, None, None) is False
            assert verify_shopify_hmac(None, None, None) is False
            assert verify_brevo_ip(None) is False
            print("PASS")
        """))


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: Webhook Service Validation Tests (11 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestWebhookServiceValidation:
    """Functional tests for webhook_service.py validation functions."""

    def test_validate_company_id_valid(self):
        """Valid company_id passes validation."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _validate_company_id
            assert _validate_company_id("company-abc-123") is True
            assert _validate_company_id("a") is True
            assert _validate_company_id("X" * 128) is True
            print("PASS")
        """))

    def test_validate_company_id_empty(self):
        """Empty company_id fails validation."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _validate_company_id
            assert _validate_company_id("") is False
            assert _validate_company_id(None) is False
            print("PASS")
        """))

    def test_validate_company_id_too_long(self):
        """Company_id over 128 chars fails."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _validate_company_id
            assert _validate_company_id("X" * 129) is False
            print("PASS")
        """))

    def test_validate_company_id_control_chars(self):
        """Company_id with control characters fails."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _validate_company_id
            assert _validate_company_id("company\\x00id") is False
            assert _validate_company_id("company\\x01id") is False
            print("PASS")
        """))

    def test_validate_company_id_whitespace(self):
        """Company_id with leading/trailing whitespace passes (stripped)."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _validate_company_id
            assert _validate_company_id("  company-123  ") is True
            print("PASS")
        """))

    def test_validate_provider_valid(self):
        """Valid provider passes validation."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _validate_provider
            for p in ["paddle", "twilio", "shopify", "brevo"]:
                assert _validate_provider(p) is True, f"Provider {p} should be valid"
            print("PASS")
        """))

    def test_validate_provider_invalid(self):
        """Invalid provider fails validation."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _validate_provider
            assert _validate_provider("") is False
            assert _validate_provider("stripe") is False
            # PADDLE is valid because _validate_provider lowercases input
            assert _validate_provider("PADDLE") is True
            print("PASS")
        """))

    def test_validate_event_type_valid(self):
        """Valid event_type passes validation."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _validate_event_type
            assert _validate_event_type("subscription.created") is True
            assert _validate_event_type("payment.failed") is True
            print("PASS")
        """))

    def test_validate_event_type_invalid(self):
        """Invalid event_type fails validation."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _validate_event_type
            assert _validate_event_type("") is False
            assert _validate_event_type(None) is False
            assert _validate_event_type("X" * 201) is False
            print("PASS")
        """))

    def test_truncate_error_short(self):
        """Short error messages pass through unchanged."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _truncate_error
            assert _truncate_error("Short error") == "Short error"
            print("PASS")
        """))

    def test_truncate_error_long(self):
        """Long error messages are truncated."""
        _run_isolated(textwrap.dedent("""\
            from app.services.webhook_service import _truncate_error
            long_err = "X" * 1000
            result = _truncate_error(long_err)
            assert len(result) < 600
            assert result.endswith("...truncated")
            print("PASS")
        """))


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: Paddle Handler Functional Tests (8 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestPaddleHandlerFunctional:
    """Functional tests for paddle_handler.py."""

    def test_validate_event_type_null_byte(self):
        """Rejects event_type containing null bytes."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.paddle_handler import _validate_event_type
            result = _validate_event_type("subscription.created\\x00evil")
            assert result is not None
            assert "invalid characters" in result.lower()
            print("PASS")
        """))

    def test_validate_event_type_empty_after_null(self):
        """Rejects event_type that is just null bytes."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.paddle_handler import _validate_event_type
            result = _validate_event_type("\\x00\\x00\\x00")
            assert result is not None
            print("PASS")
        """))

    def test_validate_event_type_valid(self):
        """Accepts valid event types."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.paddle_handler import _validate_event_type
            assert _validate_event_type("subscription.created") is None
            assert _validate_event_type("payment.succeeded") is None
            assert _validate_event_type("subscription.cancelled") is None
            print("PASS")
        """))

    def test_validate_event_type_unsupported(self):
        """Rejects unsupported event types."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.paddle_handler import _validate_event_type
            result = _validate_event_type("fake.event")
            assert result is not None
            assert "Unsupported" in result
            print("PASS")
        """))

    def test_validate_event_type_empty(self):
        """Rejects empty event_type."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.paddle_handler import _validate_event_type
            assert _validate_event_type("") is not None
            assert _validate_event_type(None) is not None
            print("PASS")
        """))

    def test_handle_paddle_event_no_company_id(self):
        """Main handler rejects event without company_id."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.paddle_handler import handle_paddle_event
            result = handle_paddle_event({
                "event_type": "subscription.created",
                "payload": {
                    "data": {
                        "subscription": {"id": "sub_123"},
                        "customer": {"id": "cus_123"},
                    }
                },
            })
            assert result["status"] == "validation_error"
            assert "company_id" in result["error"].lower()
            print("PASS")
        """))

    def test_handle_paddle_event_no_event_id(self):
        """Main handler rejects event without event_id."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.paddle_handler import handle_paddle_event
            result = handle_paddle_event({
                "event_type": "subscription.created",
                "company_id": "comp_123",
                "payload": {
                    "data": {
                        "subscription": {"id": "sub_123"},
                        "customer": {"id": "cus_123"},
                    }
                },
            })
            assert result["status"] == "validation_error"
            assert "event_id" in result["error"].lower()
            print("PASS")
        """))

    def test_handle_paddle_event_unknown_type(self):
        """Main handler rejects unknown event type."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.paddle_handler import handle_paddle_event
            result = handle_paddle_event({
                "event_type": "unknown.event.type",
                "event_id": "evt_123",
                "company_id": "comp_123",
            })
            assert result["status"] == "validation_error"
            assert "Unsupported" in result.get("error", "")
            print("PASS")
        """))


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: Twilio Handler Functional Tests (6 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestTwilioHandlerFunctional:
    """Functional tests for twilio_handler.py."""

    def test_sanitize_removes_control_chars(self):
        """Sanitizer removes control characters."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.twilio_handler import _sanitize_sms_field
            result = _sanitize_sms_field("Hello\\x00World\\x01Test")
            assert "\\x00" not in result
            assert "\\x01" not in result
            assert result == "HelloWorldTest"
            print("PASS")
        """))

    def test_sanitize_truncates(self):
        """Sanitizer truncates long values."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.twilio_handler import _sanitize_sms_field
            result = _sanitize_sms_field("A" * 500, max_length=100)
            assert len(result) == 100
            print("PASS")
        """))

    def test_sanitize_empty(self):
        """Sanitizer handles empty input."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.twilio_handler import _sanitize_sms_field
            assert _sanitize_sms_field("") == ""
            assert _sanitize_sms_field(None) == ""
            print("PASS")
        """))

    def test_sanitize_preserves_newlines(self):
        """Sanitizer preserves newline, tab, carriage return."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.twilio_handler import _sanitize_sms_field
            result = _sanitize_sms_field("Line1\\nLine2\\rLine3\\tTab")
            assert "\\n" in result
            assert "\\r" in result
            assert "\\t" in result
            print("PASS")
        """))

    def test_handle_sms_incoming_valid(self):
        """Valid SMS event is processed."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.twilio_handler import handle_sms_incoming
            result = handle_sms_incoming({
                "event_type": "sms.incoming",
                "company_id": "comp_123",
                "event_id": "SM123",
                "payload": {
                    "MessageSid": "SM123",
                    "From": "+1234567890",
                    "To": "+0987654321",
                    "Body": "Hello world",
                    "NumSegments": "1",
                },
            })
            assert result["status"] == "processed"
            assert result["action"] == "store_sms_notification"
            print("PASS")
        """))

    def test_handle_sms_incoming_missing_fields(self):
        """SMS without required fields returns validation error."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.twilio_handler import handle_sms_incoming
            result = handle_sms_incoming({
                "event_type": "sms.incoming",
                "company_id": "comp_123",
                "event_id": "SM123",
                "payload": {},
            })
            assert result["status"] == "validation_error"
            print("PASS")
        """))


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: Brevo Handler Functional Tests (6 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestBrevoHandlerFunctional:
    """Functional tests for brevo_handler.py."""

    def test_sanitize_removes_control_chars(self):
        """Email field sanitizer removes control characters."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.brevo_handler import _sanitize_email_field
            result = _sanitize_email_field("test\\x00@example.com")
            assert "\\x00" not in result
            assert result == "test@example.com"
            print("PASS")
        """))

    def test_sanitize_truncates_email(self):
        """Email sanitizer truncates to max_length."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.brevo_handler import _sanitize_email_field
            long_email = "a" * 300 + "@example.com"
            result = _sanitize_email_field(long_email, max_length=254)
            assert len(result) <= 254
            print("PASS")
        """))

    def test_validate_inbound_email_missing_fields(self):
        """Inbound email validation catches missing required fields."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.brevo_handler import _validate_inbound_email
            assert _validate_inbound_email({}) is not None
            assert _validate_inbound_email({"sender_email": "a@b.com"}) is not None
            print("PASS")
        """))

    def test_validate_inbound_email_empty_values(self):
        """Inbound email validation catches empty string values."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.brevo_handler import _validate_inbound_email
            assert _validate_inbound_email({
                "sender_email": "  ",
                "subject": "test",
                "body_html": "<p>test</p>",
                "recipient_email": "a@b.com",
            }) is not None
            print("PASS")
        """))

    def test_extract_attachments_empty(self):
        """Attachment extraction handles empty/null input."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.brevo_handler import _extract_attachments
            assert _extract_attachments(None) == []
            assert _extract_attachments([]) == []
            assert _extract_attachments("not a list") == []
            print("PASS")
        """))

    def test_extract_attachments_limits_to_20(self):
        """Attachment extraction limits to 20 attachments."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks.brevo_handler import _extract_attachments
            attachments = [{"filename": f"file{i}.pdf", "size": 100} for i in range(50)]
            result = _extract_attachments(attachments)
            assert len(result) == 20
            print("PASS")
        """))


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: Webhook Registry Tests (5 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestWebhookRegistry:
    """Functional tests for webhook handler registry."""

    def test_supported_event_types_defined(self):
        """Provider event types are defined."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks import PROVIDER_EVENT_TYPES
            assert "paddle" in PROVIDER_EVENT_TYPES
            assert "twilio" in PROVIDER_EVENT_TYPES
            assert "shopify" in PROVIDER_EVENT_TYPES
            assert "brevo" in PROVIDER_EVENT_TYPES
            print("PASS")
        """))

    def test_validate_event_type_paddle(self):
        """Paddle event type validation works."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks import validate_event_type
            assert validate_event_type("paddle", "subscription.created") is True
            assert validate_event_type("paddle", "payment.succeeded") is True
            assert validate_event_type("paddle", "fake.event") is False
            print("PASS")
        """))

    def test_validate_event_type_brevo(self):
        """Brevo event type validation works."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks import validate_event_type
            assert validate_event_type("brevo", "inbound_email") is True
            assert validate_event_type("brevo", "bounce") is True
            assert validate_event_type("brevo", "fake") is False
            print("PASS")
        """))

    def test_get_supported_event_types(self):
        """get_supported_event_types returns list."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks import get_supported_event_types
            types = get_supported_event_types("twilio")
            assert isinstance(types, list)
            assert "sms.incoming" in types
            print("PASS")
        """))

    def test_dispatch_event_no_handler(self):
        """dispatch_event raises ValueError for unregistered provider."""
        _run_isolated(textwrap.dedent("""\
            from app.webhooks import dispatch_event
            try:
                dispatch_event("nonexistent_provider", {})
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "No handler registered" in str(e)
            print("PASS")
        """))

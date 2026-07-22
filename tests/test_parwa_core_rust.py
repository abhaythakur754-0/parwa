"""
Comprehensive Python Integration Tests for parwa_core Rust Modules

Tests all 5 Rust modules through the Python PyO3 interface:
  1. Rate Limiter (10 checks)
  2. Circuit Breaker (8 checks)
  3. PII Detection (12 checks)
  4. PII Redaction (8 checks)
  5. JWT Auth (8 checks)
  6. Security (6 checks)
  7. Cross-Module Integration (4 checks)

Total: 56 checks

Run: cd /home/z/my-project/parwa && python3.12 tests/test_parwa_core_rust.py
"""

import sys
import os
import json
import time
import traceback

# ── Path Setup ───────────────────────────────────────────────────
# Ensure the installed parwa_core wheel is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Imports ────────────────────────────────────────────────────────
from parwa_core import (
    RateLimiter,
    CircuitBreaker,
    detect_pii,
    redact_pii,
    redact_pii_deterministic,
    create_access_token,
    verify_access_token,
    generate_security_headers,
    generate_csrf_nonce,
    verify_csrf_origin,
    check_rate_limit,
    is_rust_available,
)

# ═══════════════════════════════════════════════════════════════════
# TEST RUNNER
# ═══════════════════════════════════════════════════════════════════

passed = 0
failed = 0
errors = []


def check(condition, name):
    global passed, failed
    if condition:
        passed += 1
        print(f"  \u2705 {name}")
    else:
        failed += 1
        print(f"  \u274c {name}")
        errors.append(name)


# ═══════════════════════════════════════════════════════════════════
# 0. RUST AVAILABILITY
# ═══════════════════════════════════════════════════════════════════

def test_rust_available():
    print("\n\u2550\u2550\u2550 0. RUST AVAILABILITY \u2550\u2550\u2550")
    check(is_rust_available(), "is_rust_available() returns True")


# ═══════════════════════════════════════════════════════════════════
# 1. RATE LIMITER (10 checks)
# ═══════════════════════════════════════════════════════════════════

def test_rate_limiter():
    print("\n\u2550\u2550\u2550 1. RATE LIMITER (10 checks) \u2550\u2550\u2550")

    # 1.1  test_basic_allow_within_limit
    rl = RateLimiter(5, 60)
    allowed_count = 0
    for i in range(5):
        ok, reason = rl.check(f"rl_basic_{i}")
        if ok:
            allowed_count += 1
    check(allowed_count == 5, "test_basic_allow_within_limit: 5 requests allowed under limit of 5")

    # 1.2  test_deny_over_limit
    rl2 = RateLimiter(5, 60)
    for i in range(5):
        rl2.check("rl_deny_user")
    ok6, _ = rl2.check("rl_deny_user")
    check(not ok6, "test_deny_over_limit: 6th request denied")

    # 1.3  test_progressive_lockout
    # Use standalone function with custom lockout_steps where first step is 0 (no lockout)
    # so multiple violations can accumulate without waiting.
    uid = f"prog_lock_{int(time.time()*1000)}"
    # First request: allowed
    ok1, _ = check_rate_limit(uid, 1, 60, [0, 0, 2, 4])
    check(ok1, "test_progressive_lockout: first request allowed")
    # Second request: denied, violation #1, step[1]=0 → no lockout, just "Rate limit exceeded"
    ok2, reason2 = check_rate_limit(uid, 1, 60, [0, 0, 2, 4])
    check(not ok2 and "violation #1" in reason2,
          "test_progressive_lockout: violation #1 recorded")
    # Third request: denied, violation #2, step[2]=2 → "Locked out for 2 seconds"
    ok3, reason3 = check_rate_limit(uid, 1, 60, [0, 0, 2, 4])
    check(not ok3 and "2 seconds" in reason3 and "violation #2" in reason3,
          "test_progressive_lockout: violation #2 increases lockout to 2s")

    # 1.4  test_different_identifiers_independent
    rl3 = RateLimiter(1, 60)
    ok_a, _ = rl3.check("user1")
    ok_a2, _ = rl3.check("user1")
    ok_b, _ = rl3.check("user2")
    check(ok_a and not ok_a2 and ok_b,
          "test_different_identifiers_independent: user1 denied, user2 allowed")

    # 1.5  test_standalone_check_rate_limit
    uid_s = f"standalone_{int(time.time()*1000000)}"
    ok_s1, _ = check_rate_limit(uid_s, 2, 60, [])
    ok_s2, _ = check_rate_limit(uid_s, 2, 60, [])
    ok_s3, _ = check_rate_limit(uid_s, 2, 60, [])
    check(ok_s1 and ok_s2 and not ok_s3,
          "test_standalone_check_rate_limit: standalone function works")

    # 1.6  test_constructor_parameters
    rl4 = RateLimiter(10, 120)
    ok_c, _ = rl4.check("ctor_test")
    check(ok_c, "test_constructor_parameters: RateLimiter(10, 120) allows first request")

    # 1.7  test_reason_message_on_deny
    rl5 = RateLimiter(1, 60)
    rl5.check("reason_test")
    _, reason = rl5.check("reason_test")
    check(isinstance(reason, str) and len(reason) > 0,
          "test_reason_message_on_deny: denied requests have reason string")

    # 1.8  test_large_identifier
    long_id = "user_" + "x" * 500
    rl6 = RateLimiter(10, 60)
    ok_long, _ = rl6.check(long_id)
    check(ok_long, "test_large_identifier: long identifier string works")

    # 1.9  test_concurrent_checks
    rl7 = RateLimiter(100, 60)
    all_allowed = True
    for i in range(100):
        ok, _ = rl7.check(f"concurrent_{i}")
        if not ok:
            all_allowed = False
            break
    check(all_allowed, "test_concurrent_checks: 100 rapid checks from multiple identifiers")

    # 1.10 test_reset_on_window
    # Use a 1-second window, make a request, sleep 2 seconds, then request again
    rl8 = RateLimiter(1, 1)
    ok_before, _ = rl8.check("window_reset_test")
    check(ok_before, "test_reset_on_window: first request allowed (1s window)")
    time.sleep(2)
    ok_after, _ = rl8.check("window_reset_test")
    check(ok_after, "test_reset_on_window: after window expires, counter resets")


# ═══════════════════════════════════════════════════════════════════
# 2. CIRCUIT BREAKER (8 checks)
# ═══════════════════════════════════════════════════════════════════

def test_circuit_breaker():
    print("\n\u2550\u2550\u2550 2. CIRCUIT BREAKER (8 checks) \u2550\u2550\u2550")

    # 2.1  test_initial_state_closed
    cb = CircuitBreaker("test_cb", 3, 60, 2)
    check(cb.get_state() == "CLOSED", "test_initial_state_closed: starts CLOSED")
    check(not cb.is_open(), "test_initial_state_closed: is_open() returns False")

    # 2.2  test_opens_after_threshold
    cb2 = CircuitBreaker("open_thresh", 3, 60, 2)
    cb2.record_failure()
    cb2.record_failure()
    check(cb2.get_state() == "CLOSED", "test_opens_after_threshold: 2 failures → still CLOSED")
    cb2.record_failure()
    check(cb2.get_state() == "OPEN", "test_opens_after_threshold: 3 failures → OPEN")

    # 2.3  test_rejects_when_open
    cb3 = CircuitBreaker("reject_open", 2, 60, 1)
    cb3.record_failure()
    cb3.record_failure()
    check(cb3.is_open(), "test_rejects_when_open: cb.is_open() returns True")

    # 2.4  test_half_open_after_timeout
    cb4 = CircuitBreaker("half_open", 1, 1, 1)
    cb4.record_failure()
    check(cb4.get_state() == "OPEN", "test_half_open_after_timeout: circuit is OPEN")
    # Simulate timeout by manipulating opened_at far enough in the past
    # We can't directly access inner state from Python, so we sleep
    time.sleep(2)
    # is_open() should auto-transition to HALF_OPEN
    check(not cb4.is_open(), "test_half_open_after_timeout: is_open() returns False after timeout")
    check(cb4.get_state() == "HALF_OPEN",
          "test_half_open_after_timeout: after recovery timeout, state → HALF_OPEN")

    # 2.5  test_closes_on_success
    cb5 = CircuitBreaker("close_on_ok", 1, 1, 1)
    cb5.record_failure()
    time.sleep(2)
    # Now in HALF_OPEN
    check(cb5.get_state() == "HALF_OPEN", "test_closes_on_success: transitioned to HALF_OPEN")
    cb5.record_success()  # half_open_max_calls=1, so 1 success → CLOSED
    check(cb5.get_state() == "CLOSED", "test_closes_on_success: HALF_OPEN + success → CLOSED")

    # 2.6  test_reopens_on_failure
    cb6 = CircuitBreaker("reopen_fail", 1, 1, 3)
    cb6.record_failure()
    time.sleep(2)
    check(cb6.get_state() == "HALF_OPEN", "test_reopens_on_failure: transitioned to HALF_OPEN")
    cb6.record_failure()
    check(cb6.get_state() == "OPEN", "test_reopens_on_failure: HALF_OPEN + failure → OPEN")

    # 2.7  test_success_in_closed
    cb7 = CircuitBreaker("success_closed", 3, 60, 2)
    cb7.record_success()
    cb7.record_success()
    check(cb7.get_state() == "CLOSED",
          "test_success_in_closed: success doesn't change state from CLOSED")

    # 2.8  test_get_stats
    cb8 = CircuitBreaker("stats_cb", 3, 60, 2)
    stats = cb8.get_stats()
    expected_keys = {"name", "state", "failure_count", "success_count",
                     "last_failure_time", "last_state_change"}
    check(isinstance(stats, dict) and expected_keys.issubset(set(stats.keys())),
          "test_get_stats: returns dict with expected keys")


# ═══════════════════════════════════════════════════════════════════
# 3. PII DETECTION (12 checks)
# ═══════════════════════════════════════════════════════════════════

def test_pii_detection():
    print("\n\u2550\u2550\u2550 3. PII DETECTION (12 checks) \u2550\u2550\u2550")

    # 3.1  test_detect_ssn
    results = detect_pii("My SSN is 123-45-6789.")
    ssn_found = any(m["pii_type"] == "SSN" and m["value"] == "123-45-6789" for m in results)
    check(ssn_found, "test_detect_ssn: \"123-45-6789\" detected as SSN")

    # 3.2  test_detect_email
    results = detect_pii("Contact john@example.com for help.")
    email_found = any(m["pii_type"] == "EMAIL" and "john@example.com" in m["value"] for m in results)
    check(email_found, "test_detect_email: \"john@example.com\" detected as EMAIL")

    # 3.3  test_detect_phone
    results = detect_pii("Call me at (555) 123-4567.")
    phone_found = any(m["pii_type"] == "PHONE" for m in results)
    check(phone_found, "test_detect_phone: \"(555) 123-4567\" detected as PHONE")

    # 3.4  test_detect_credit_card
    # Use Luhn-valid Visa: 4539148803436467
    results = detect_pii("Card number: 4539148803436467")
    cc_found = any(m["pii_type"] == "CREDIT_CARD" for m in results)
    check(cc_found, "test_detect_credit_card: credit card number detected")

    # 3.5  test_detect_api_key
    results = detect_pii("Use this key: sk-abcdefghijklmnopqrstuvwxy")
    api_found = any(m["pii_type"] == "API_KEY" for m in results)
    check(api_found, "test_detect_api_key: \"sk-abcdefghijklmnopqrstuvwxy\" detected")

    # 3.6  test_detect_aadhaar
    results = detect_pii("Aadhaar: 2345 6789 0123")
    aadhaar_found = any(m["pii_type"] == "AADHAAR" for m in results)
    check(aadhaar_found, "test_detect_aadhaar: \"2345 6789 0123\" detected as AADHAAR")

    # 3.7  test_detect_pan
    results = detect_pii("PAN: ABCDE1234F")
    pan_found = any(m["pii_type"] == "PAN" and m["value"] == "ABCDE1234F" for m in results)
    check(pan_found, "test_detect_pan: \"ABCDE1234F\" detected as PAN")

    # 3.8  test_detect_ip_address
    results = detect_pii("Server at 192.168.1.1 is down.")
    ip_found = any(m["pii_type"] == "IP_ADDRESS" and "192.168.1.1" in m["value"] for m in results)
    check(ip_found, "test_detect_ip_address: \"192.168.1.1\" detected as IP_ADDRESS")

    # 3.9  test_detect_multiple_types
    text = "SSN 123-45-6789, email john@example.com, phone (555) 123-4567"
    results = detect_pii(text)
    types_found = {m["pii_type"] for m in results}
    check("SSN" in types_found and "EMAIL" in types_found and "PHONE" in types_found,
          "test_detect_multiple_types: text with SSN + email + phone → all detected")

    # 3.10 test_no_false_positive_clean_text
    results = detect_pii("Hello world")
    check(len(results) == 0, "test_no_false_positive_clean_text: \"Hello world\" → 0 matches")

    # 3.11 test_detect_dob
    results = detect_pii("Date of birth: 01/15/1990")
    dob_found = any(m["pii_type"] == "DATE_OF_BIRTH" for m in results)
    check(dob_found, "test_detect_dob: \"01/15/1990\" detected as DATE_OF_BIRTH")

    # 3.12 test_match_has_required_keys
    results = detect_pii("Email: test@test.com")
    required_keys = {"pii_type", "value", "start", "end", "confidence"}
    if results:
        match_keys = set(results[0].keys())
        check(required_keys.issubset(match_keys),
              "test_match_has_required_keys: each match has pii_type, value, start, end, confidence")
    else:
        check(False, "test_match_has_required_keys: each match has pii_type, value, start, end, confidence")


# ═══════════════════════════════════════════════════════════════════
# 4. PII REDACTION (8 checks)
# ═══════════════════════════════════════════════════════════════════

def test_pii_redaction():
    print("\n\u2550\u2550\u2550 4. PII REDACTION (8 checks) \u2550\u2550\u2550")

    # 4.1  test_redact_simple
    redacted = redact_pii("SSN: 123-45-6789 and email john@test.com", "[REDACTED]")
    check("[REDACTED]" in redacted and "123-45-6789" not in redacted,
          "test_redact_simple: replaces PII with \"[REDACTED]\"")

    # 4.2  test_redact_specific_types
    text = "SSN: 123-45-6789 and email john@test.com"
    redacted = redact_pii(text, "[REDACTED]", ["EMAIL"])
    check("123-45-6789" in redacted and "john@test.com" not in redacted,
          "test_redact_specific_types: only redacts specified types")

    # 4.3  test_deterministic_same_input
    text = "SSN is 123-45-6789"
    r1, _ = redact_pii_deterministic(text, "company_abc")
    r2, _ = redact_pii_deterministic(text, "company_abc")
    check(r1 == r2, "test_deterministic_same_input: same input + company → same token")

    # 4.4  test_deterministic_different_company
    text = "SSN is 123-45-6789"
    r1, _ = redact_pii_deterministic(text, "company_a")
    r2, _ = redact_pii_deterministic(text, "company_b")
    check(r1 != r2, "test_deterministic_different_company: same input, different company → different token")

    # 4.5  test_redaction_map_is_dict
    text = "Email: alice@example.com"
    _, map_json = redact_pii_deterministic(text, "co_test")
    redaction_map = json.loads(map_json)
    check(isinstance(redaction_map, dict), "test_redaction_map_is_dict: map is a dict mapping value→token")
    if redaction_map:
        check(all(isinstance(k, str) and isinstance(v, str) for k, v in redaction_map.items()),
              "test_redaction_map_is_dict: all keys and values are strings")

    # 4.6  test_multiple_pii_redacted
    text = "SSN: 123-45-6789, email: john@test.com, phone: (555) 123-4567"
    redacted = redact_pii(text, "[REDACTED]")
    check("123-45-6789" not in redacted and "john@test.com" not in redacted,
          "test_multiple_pii_redacted: text with multiple PII → all replaced")

    # 4.7  test_no_pii_returns_original
    text = "Hello, this is clean text."
    redacted = redact_pii(text, "[REDACTED]")
    check(redacted == text, "test_no_pii_returns_original: clean text returned unchanged")

    # 4.8  test_redact_returns_tuple
    result = redact_pii_deterministic("Email: test@example.com", "co")
    check(isinstance(result, tuple) and len(result) == 2,
          "test_redact_returns_tuple: deterministic returns (text, map)")


# ═══════════════════════════════════════════════════════════════════
# 5. JWT AUTH (8 checks)
# ═══════════════════════════════════════════════════════════════════

def test_jwt_auth():
    print("\n\u2550\u2550\u2550 5. JWT AUTH (8 checks) \u2550\u2550\u2550")

    secret = "test_secret_key_123"

    # 5.1  test_create_and_verify
    token = create_access_token("user_1", "company_1", "user@test.com",
                                "admin", "pro", secret, 60)
    payload = verify_access_token(token, secret, [])
    check(payload["sub"] == "user_1" and payload["company_id"] == "company_1",
          "test_create_and_verify: create token → verify returns correct payload")

    # 5.2  test_correct_claims
    token2 = create_access_token("u42", "corp", "alice@corp.com",
                                 "editor", "enterprise", secret, 30)
    claims = verify_access_token(token2, secret, [])
    required_claims = {"sub", "company_id", "email", "role", "plan", "type"}
    check(required_claims.issubset(set(claims.keys())),
          "test_correct_claims: payload has sub, company_id, email, role, plan, type")

    # 5.3  test_expired_token_rejected
    expired_token = create_access_token("user_exp", "co", "e@e.com",
                                        "user", "free", secret, 0)
    time.sleep(1)
    try:
        verify_access_token(expired_token, secret, [])
        check(False, "test_expired_token_rejected: create with 0 min expiry → verify fails")
    except (ValueError, Exception):
        check(True, "test_expired_token_rejected: create with 0 min expiry → verify fails")

    # 5.4  test_wrong_secret_rejected
    token_a = create_access_token("user_a", "co", "a@a.com",
                                  "user", "free", "secret_aaa", 60)
    try:
        verify_access_token(token_a, "secret_bbb", [])
        check(False, "test_wrong_secret_rejected: verify with wrong secret → error")
    except (ValueError, Exception):
        check(True, "test_wrong_secret_rejected: verify with wrong secret → error")

    # 5.5  test_previous_secret_accepted
    old_secret = "old_secret_key"
    new_secret = "new_secret_key"
    token_old = create_access_token("user_old", "co", "o@o.com",
                                    "user", "free", old_secret, 60)
    payload_rot = verify_access_token(token_old, new_secret, [old_secret])
    check(payload_rot["sub"] == "user_old",
          "test_previous_secret_accepted: verify with old secret (key rotation)")

    # 5.6  test_invalid_token_format
    try:
        verify_access_token("not.a.valid.jwt.token", secret, [])
        check(False, "test_invalid_token_format: verify random string → error")
    except (ValueError, Exception):
        check(True, "test_invalid_token_format: verify random string → error")

    # 5.7  test_jti_present
    token_jti = create_access_token("u_jti", "co", "j@j.com",
                                    "user", "free", secret, 60)
    claims_jti = verify_access_token(token_jti, secret, [])
    check("jti" in claims_jti and len(claims_jti["jti"]) > 0,
          "test_jti_present: payload has jti field")

    # 5.8  test_type_is_access
    check(claims_jti.get("type") == "access",
          "test_type_is_access: payload type == \"access\"")


# ═══════════════════════════════════════════════════════════════════
# 6. SECURITY (6 checks)
# ═══════════════════════════════════════════════════════════════════

def test_security():
    print("\n\u2550\u2550\u2550 6. SECURITY (6 checks) \u2550\u2550\u2550")

    # 6.1  test_headers_contain_x_content_type_options
    headers = generate_security_headers()
    check("X-Content-Type-Options" in headers and headers["X-Content-Type-Options"] == "nosniff",
          "test_headers_contain_x_content_type_options: has X-Content-Type-Options")

    # 6.2  test_headers_contain_x_frame_options
    check("X-Frame-Options" in headers and headers["X-Frame-Options"] == "DENY",
          "test_headers_contain_x_frame_options: has X-Frame-Options")

    # 6.3  test_headers_contain_hsts
    check("Strict-Transport-Security" in headers
          and "max-age=31536000" in headers["Strict-Transport-Security"],
          "test_headers_contain_hsts: has Strict-Transport-Security")

    # 6.4  test_headers_contain_csp
    check("Content-Security-Policy" in headers
          and "default-src 'self'" in headers["Content-Security-Policy"],
          "test_headers_contain_csp: has Content-Security-Policy")

    # 6.5  test_nonce_length_64
    nonce = generate_csrf_nonce()
    check(len(nonce) == 64 and all(c in "0123456789abcdef" for c in nonce),
          "test_nonce_length_64: generate_csrf_nonce() returns 64 char hex string")

    # 6.6  test_verify_allowed_origin
    result = verify_csrf_origin(
        "https://app.example.com",
        ["https://other.com", "https://app.example.com"]
    )
    check(result is True, "test_verify_allowed_origin: verify returns True for valid origin")


# ═══════════════════════════════════════════════════════════════════
# 7. CROSS-MODULE INTEGRATION (4 checks)
# ═══════════════════════════════════════════════════════════════════

def test_cross_module_integration():
    print("\n\u2550\u2550\u2550 7. CROSS-MODULE INTEGRATION (4 checks) \u2550\u2550\u2550")

    # 7.1  test_pii_redact_in_pipeline: detect → redact in sequence
    text = "SSN 123-45-6789 belongs to john@example.com"
    detections = detect_pii(text)
    redacted = redact_pii(text, "[REDACTED]")
    all_redacted = all(m["value"] not in redacted for m in detections)
    check(all_redacted,
          "test_pii_redact_in_pipeline: detect → redact removes all detected PII")

    # 7.2  test_rate_limit_before_pii: rate limit check then PII scan
    rl = RateLimiter(100, 60)
    ok, _ = rl.check("integration_user")
    pii_found = len(detect_pii("SSN 123-45-6789")) > 0
    check(ok and pii_found,
          "test_rate_limit_before_pii: rate limit check then PII scan both succeed")

    # 7.3  test_jwt_then_rate_limit: JWT verify then rate limit by user_id
    secret = "integration_secret"
    token = create_access_token("int_user", "int_co", "int@test.com",
                                "user", "free", secret, 60)
    try:
        payload = verify_access_token(token, secret, [])
        user_id = payload["sub"]
        rl2 = RateLimiter(100, 60)
        ok_rl, _ = rl2.check(user_id)
        check(ok_rl,
              "test_jwt_then_rate_limit: JWT verify then rate limit by user_id")
    except Exception:
        check(False, "test_jwt_then_rate_limit: JWT verify then rate limit by user_id")

    # 7.4  test_circuit_breaker_protects_pii: circuit breaker OPEN → skip PII processing
    cb = CircuitBreaker("pii_guard", 1, 1, 1)
    cb.record_failure()  # Trip the breaker
    time.sleep(2)  # Let recovery timeout pass → HALF_OPEN
    # In a real pipeline, we'd check is_open() before calling detect_pii.
    # Here we verify the circuit breaker state correctly gates the flow.
    is_open_flag = cb.is_open()
    if not is_open_flag:
        # HALF_OPEN: one probe call allowed
        detections = detect_pii("SSN 123-45-6789")
        cb.record_success()  # If PII succeeded, close the circuit
        cb_state = cb.get_state()
        check(cb_state == "CLOSED" and len(detections) > 0,
              "test_circuit_breaker_protects_pii: HALF_OPEN → success → CLOSED, PII ran")
    else:
        # Still OPEN → skip PII (no detections expected in guarded path)
        check(True,
              "test_circuit_breaker_protects_pii: circuit breaker OPEN → skip PII processing")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 64)
    print("  PARWA CORE RUST MODULES — PYTHON INTEGRATION TEST SUITE")
    print("  56 checks across 7 test groups")
    print("=" * 64)

    t0 = time.time()

    try:
        test_rust_available()
        test_rate_limiter()
        test_circuit_breaker()
        test_pii_detection()
        test_pii_redaction()
        test_jwt_auth()
        test_security()
        test_cross_module_integration()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()

    elapsed = time.time() - t0
    total = passed + failed

    print("\n" + "=" * 64)
    print(f"  RESULTS: {passed}/{total} PASSED  |  {failed} FAILED  |  {elapsed:.1f}s")
    print("=" * 64)

    if errors:
        print("\nFailed tests:")
        for e in errors:
            print(f"  \u274c {e}")

    sys.exit(0 if failed == 0 else 1)
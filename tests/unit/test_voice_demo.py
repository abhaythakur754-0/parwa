"""
Voice Demo System Tests (F-008)

30+ tests covering:
- Payment: create intent, verify payment, refund
- Session: init, get, end, timeout, activation
- Voice pipeline: transcribe, process, synthesize (placeholders)
- Duration limits: max duration enforcement
- Concurrent sessions: limit enforcement
- BC-002: Decimal used for all money
- BC-008: garbage input, missing params, expired session
- Config: defaults, frozen, validation
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.core.voice_demo import (
    DemoSummary,
    PaymentIntent,
    PaymentStatus,
    RefundResult,
    SessionStatus,
    VoiceDemoConfig,
    VoiceDemoEngine,
    VoiceDemoPayment,
    VoiceDemoResult,
    VoiceDemoSession,
    get_voice_demo_engine,
    reset_voice_demo_engine,
    _generate_session_id,
    _safe_decimal,
    _valid_email,
    _valid_phone,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def reset_engine():
    """Ensure the global engine singleton is reset between tests."""
    reset_voice_demo_engine()
    yield
    reset_voice_demo_engine()


@pytest.fixture
def config():
    return VoiceDemoConfig(
        price_usd=Decimal("1.00"),
        max_duration_seconds=300,
        max_concurrent_sessions=5,
        session_timeout_seconds=1800,
        retry_limit=3,
    )


@pytest.fixture
def payment(config):
    return VoiceDemoPayment(config=config)


@pytest.fixture
def engine(config):
    return VoiceDemoEngine(config=config)


@pytest.fixture
def active_session(engine):
    """Create and activate a session ready for voice interaction."""
    session = engine.init_demo_session("buyer@example.com", "+12345678901")
    intent = engine._payment.create_payment_intent("buyer@example.com", "+12345678901")
    # We need to use the same session id the engine created
    token = engine._payment._make_token(session.session_id, engine._payment.amount)
    engine.activate_session(session.session_id, token)
    return session


# ═══════════════════════════════════════════════════════════════════════════
# Helper Validators
# ═══════════════════════════════════════════════════════════════════════════

class TestHelperValidators:
    """Tests for internal validation helpers."""

    def test_valid_email(self):
        assert _valid_email("user@example.com") is True
        assert _valid_email("a.b+c@d.co") is True

    def test_invalid_email(self):
        assert _valid_email("") is False
        assert _valid_email("not-an-email") is False
        assert _valid_email(None) is False
        assert _valid_email(42) is False
        assert _valid_email("@no.local") is False

    def test_valid_phone(self):
        assert _valid_phone("+12345678901") is True
        assert _valid_phone("12345678901234") is True

    def test_invalid_phone(self):
        assert _valid_phone("") is False
        assert _valid_phone("123") is False
        assert _valid_phone(None) is False
        assert _valid_phone("+0") is False
        assert _valid_phone(555) is False

    def test_safe_decimal_valid(self):
        assert _safe_decimal("1.00") == Decimal("1.00")
        assert _safe_decimal(1.5) == Decimal("1.5")
        assert _safe_decimal(Decimal("3.33")) == Decimal("3.33")

    def test_safe_decimal_none(self):
        assert _safe_decimal(None) is None

    def test_safe_decimal_invalid(self):
        assert _safe_decimal("abc") is None
        assert _safe_decimal(object()) is None


# ═══════════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════════

class TestVoiceDemoConfig:
    """Tests for VoiceDemoConfig defaults, frozen-ness, validation."""

    def test_defaults(self):
        cfg = VoiceDemoConfig()
        assert cfg.price_usd == Decimal("1.00")
        assert cfg.max_duration_seconds == 300
        assert cfg.max_concurrent_sessions == 50
        assert cfg.session_timeout_seconds == 1800
        assert cfg.retry_limit == 3
        assert len(cfg.allowed_countries) > 0

    def test_frozen(self):
        cfg = VoiceDemoConfig()
        with pytest.raises(AttributeError):
            cfg.price_usd = Decimal("2.00")

    def test_custom_values(self):
        cfg = VoiceDemoConfig(
            price_usd=Decimal("2.50"),
            max_duration_seconds=600,
            max_concurrent_sessions=10,
        )
        assert cfg.price_usd == Decimal("2.50")
        assert cfg.max_duration_seconds == 600
        assert cfg.max_concurrent_sessions == 10

    def test_price_coerced_to_decimal(self):
        cfg = VoiceDemoConfig(price_usd=1.5)
        assert isinstance(cfg.price_usd, Decimal)
        assert cfg.price_usd == Decimal("1.5")

    def test_invalid_max_duration(self):
        with pytest.raises(ValueError, match="max_duration_seconds"):
            VoiceDemoConfig(max_duration_seconds=0)

    def test_invalid_max_concurrent(self):
        with pytest.raises(ValueError, match="max_concurrent_sessions"):
            VoiceDemoConfig(max_concurrent_sessions=0)

    def test_invalid_session_timeout(self):
        with pytest.raises(ValueError, match="session_timeout_seconds"):
            VoiceDemoConfig(session_timeout_seconds=-1)

    def test_invalid_retry_limit(self):
        with pytest.raises(ValueError, match="retry_limit"):
            VoiceDemoConfig(retry_limit=0)

    def test_none_price_falls_back(self):
        cfg = VoiceDemoConfig(price_usd=None)
        assert cfg.price_usd == Decimal("1.00")


# ═══════════════════════════════════════════════════════════════════════════
# Payment (BC-002)
# ═══════════════════════════════════════════════════════════════════════════

class TestVoiceDemoPayment:
    """Tests for VoiceDemoPayment: create intent, verify, refund."""

    def test_amount_is_decimal(self, payment):
        assert isinstance(payment.amount, Decimal)
        assert payment.amount == Decimal("1.00")

    def test_create_payment_intent(self, payment):
        intent = payment.create_payment_intent("user@example.com", "+12345678901")
        assert isinstance(intent, PaymentIntent)
        assert isinstance(intent.amount, Decimal)
        assert intent.amount == Decimal("1.00")
        assert intent.currency == "USD"
        assert intent.status == PaymentStatus.PENDING
        assert intent.session_id
        assert "paddle.com" in intent.checkout_url

    def test_verify_payment_valid_token(self, payment):
        intent = payment.create_payment_intent("user@example.com", "+12345678901")
        token = payment._make_token(intent.session_id, intent.amount)
        assert payment.verify_payment(intent.session_id, token) is True

    def test_verify_payment_invalid_token(self, payment):
        intent = payment.create_payment_intent("user@example.com", "+12345678901")
        assert payment.verify_payment(intent.session_id, "garbage_token") is False

    def test_verify_payment_empty_params(self, payment):
        assert payment.verify_payment("", "token") is False
        assert payment.verify_payment("sid", "") is False
        assert payment.verify_payment("", "") is False

    def test_verify_payment_none_params(self, payment):
        assert payment.verify_payment(None, "token") is False
        assert payment.verify_payment("sid", None) is False

    def test_refund_success(self, payment):
        result = payment.refund_if_needed("sess_123", Decimal("1.00"))
        assert result.success is True
        assert isinstance(result.refund_amount, Decimal)
        assert result.refund_amount == Decimal("1.00")
        assert result.status == PaymentStatus.REFUNDED
        assert result.session_id == "sess_123"

    def test_refund_capped_at_price(self, payment):
        result = payment.refund_if_needed("sess_123", Decimal("5.00"))
        assert result.refund_amount == Decimal("1.00")  # capped at config price

    def test_refund_missing_session_id(self, payment):
        result = payment.refund_if_needed("", Decimal("1.00"))
        assert result.success is False
        assert result.status == PaymentStatus.FAILED

    def test_refund_none_session_id(self, payment):
        result = payment.refund_if_needed(None, Decimal("1.00"))
        assert result.success is False

    def test_refund_zero_amount(self, payment):
        result = payment.refund_if_needed("sess_123", Decimal("0.00"))
        assert result.success is True
        assert result.refund_amount == Decimal("0.00")

    def test_refund_amount_is_decimal_bc002(self, payment):
        """BC-002: refund_amount must be Decimal, never float."""
        result = payment.refund_if_needed("sess_123", Decimal("1.00"))
        assert isinstance(result.refund_amount, Decimal)


# ═══════════════════════════════════════════════════════════════════════════
# Session Lifecycle
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionLifecycle:
    """Tests for session init, get, activation, end."""

    def test_init_session(self, engine):
        session = engine.init_demo_session("user@example.com", "+12345678901")
        assert isinstance(session, VoiceDemoSession)
        assert session.status == SessionStatus.CREATED
        assert session.payment_status == PaymentStatus.PENDING
        assert isinstance(session.amount_paid, Decimal)
        assert session.amount_paid == Decimal("0.00")
        assert session.session_id

    def test_init_session_invalid_email(self, engine):
        with pytest.raises(ValueError, match="email"):
            engine.init_demo_session("bad", "+12345678901")

    def test_init_session_invalid_phone(self, engine):
        with pytest.raises(ValueError, match="phone"):
            engine.init_demo_session("user@example.com", "123")

    def test_init_session_none_email(self, engine):
        with pytest.raises(ValueError):
            engine.init_demo_session(None, "+12345678901")

    def test_init_session_none_phone(self, engine):
        with pytest.raises(ValueError):
            engine.init_demo_session("user@example.com", None)

    def test_get_session_exists(self, engine):
        created = engine.init_demo_session("a@b.com", "+12345678901")
        fetched = engine.get_session(created.session_id)
        assert fetched is not None
        assert fetched.session_id == created.session_id

    def test_get_session_missing(self, engine):
        assert engine.get_session("nonexistent") is None

    def test_activate_session(self, engine):
        session = engine.init_demo_session("user@example.com", "+12345678901")
        token = engine._payment._make_token(session.session_id, engine._payment.amount)
        activated = engine.activate_session(session.session_id, token)
        assert activated.status == SessionStatus.ACTIVE
        assert activated.payment_status == PaymentStatus.COMPLETED
        assert isinstance(activated.amount_paid, Decimal)
        assert activated.amount_paid == Decimal("1.00")
        assert activated.started_at is not None

    def test_activate_invalid_token(self, engine):
        session = engine.init_demo_session("user@example.com", "+12345678901")
        with pytest.raises(ValueError, match="Payment verification failed"):
            engine.activate_session(session.session_id, "bad_token")

    def test_activate_missing_session(self, engine):
        with pytest.raises(KeyError):
            engine.activate_session("nonexistent", "some_token")

    def test_activate_already_active(self, active_session, engine):
        """Cannot activate a session that's already active."""
        token = engine._payment._make_token(
            active_session.session_id, engine._payment.amount
        )
        with pytest.raises(ValueError, match="not in CREATED state"):
            engine.activate_session(active_session.session_id, token)

    def test_end_session(self, active_session, engine):
        summary = engine.end_demo_session(active_session.session_id)
        assert isinstance(summary, DemoSummary)
        assert summary.status == SessionStatus.ENDED
        assert summary.duration_seconds > 0
        assert summary.ended_at is not None

    def test_end_session_not_active(self, engine):
        session = engine.init_demo_session("a@b.com", "+12345678901")
        with pytest.raises(ValueError, match="not active"):
            engine.end_demo_session(session.session_id)

    def test_end_session_missing(self, engine):
        with pytest.raises(KeyError):
            engine.end_demo_session("nonexistent")

    def test_get_demo_summary(self, active_session, engine):
        summary = engine.get_demo_summary(active_session.session_id)
        assert isinstance(summary, DemoSummary)
        assert summary.session_id == active_session.session_id
        assert summary.status == SessionStatus.ACTIVE

    def test_get_demo_summary_missing(self, engine):
        with pytest.raises(KeyError):
            engine.get_demo_summary("nonexistent")

    def test_amount_paid_is_decimal_bc002(self, engine):
        """BC-002: amount_paid must always be Decimal."""
        session = engine.init_demo_session("a@b.com", "+12345678901")
        assert isinstance(session.amount_paid, Decimal)


# ═══════════════════════════════════════════════════════════════════════════
# Voice Pipeline (Placeholder)
# ═══════════════════════════════════════════════════════════════════════════

class TestVoicePipeline:
    """Tests for STT, AI processing, TTS placeholders."""

    def test_transcribe_valid_audio(self, engine):
        result = engine._transcribe_audio("aGVsbG8gd29ybGQ=")
        assert result.success is True
        assert result.text
        assert result.confidence > 0

    def test_transcribe_none_audio(self, engine):
        result = engine._transcribe_audio(None)
        assert result.success is False
        assert result.error

    def test_transcribe_empty_audio(self, engine):
        result = engine._transcribe_audio("")
        assert result.success is False

    def test_transcribe_short_audio(self, engine):
        result = engine._transcribe_audio("abc")
        assert result.success is False
        assert "too short" in result.error

    def test_transcribe_garbage_audio(self, engine):
        """BC-008: garbage input should not crash."""
        result = engine._transcribe_audio("%%invalid%%base64%%")
        assert result.success is True  # placeholder accepts anything long enough

    def test_process_ai_valid_text(self, engine):
        result = engine._process_through_ai("Hello PARWA", "Acme Corp")
        assert result.success is True
        assert "Hello PARWA" in result.text
        assert "Acme Corp" in result.text

    def test_process_ai_empty_text(self, engine):
        result = engine._process_through_ai("", "Acme")
        assert result.success is False

    def test_process_ai_none_text(self, engine):
        result = engine._process_through_ai(None, "Acme")
        assert result.success is False

    def test_process_ai_int_text(self, engine):
        """BC-008: non-string text does not crash."""
        result = engine._process_through_ai(42, "Acme")
        assert result.success is False

    def test_synthesize_valid_text(self, engine):
        result = engine._synthesize_speech("Hello")
        assert result.success is True
        assert result.audio_base64
        assert result.text == "Hello"

    def test_synthesize_empty_text(self, engine):
        result = engine._synthesize_speech("")
        assert result.success is False

    def test_synthesize_none_text(self, engine):
        result = engine._synthesize_speech(None)
        assert result.success is False

    def test_process_voice_input_success(self, active_session, engine):
        result = engine.process_voice_input(
            active_session.session_id, "aGVsbG8gd29ybGQ="
        )
        assert result.success is True
        assert result.latency_ms > 0

    def test_process_voice_input_no_session(self, engine):
        result = engine.process_voice_input("nonexistent", "audio")
        assert result.success is False

    def test_generate_voice_response_success(self, active_session, engine):
        result = engine.generate_voice_response(active_session.session_id, "Hi")
        assert result.success is True
        assert result.audio_base64

    def test_generate_voice_response_no_session(self, engine):
        result = engine.generate_voice_response("nonexistent", "Hi")
        assert result.success is False


# ═══════════════════════════════════════════════════════════════════════════
# Duration Limits
# ═══════════════════════════════════════════════════════════════════════════

class TestDurationLimits:
    """Tests for max demo duration enforcement."""

    def test_duration_limit_enforced(self):
        """When elapsed time >= max_duration, session should auto-end."""
        cfg = VoiceDemoConfig(max_duration_seconds=1)
        eng = VoiceDemoEngine(config=cfg)
        session = eng.init_demo_session("user@example.com", "+12345678901")
        token = eng._payment._make_token(session.session_id, eng._payment.amount)
        eng.activate_session(session.session_id, token)

        # Wait for duration to exceed limit
        time.sleep(1.1)

        result = eng.process_voice_input(session.session_id, "aGVsbG8gd29ybGQ=")
        assert result.success is False
        assert "duration limit" in result.error.lower() or result.error

        # Session should now be ended
        s = eng.get_session(session.session_id)
        assert s.status == SessionStatus.ENDED


# ═══════════════════════════════════════════════════════════════════════════
# Concurrent Sessions
# ═══════════════════════════════════════════════════════════════════════════

class TestConcurrentSessions:
    """Tests for max concurrent session enforcement."""

    def test_concurrent_limit_enforced(self):
        cfg = VoiceDemoConfig(max_concurrent_sessions=2)
        eng = VoiceDemoEngine(config=cfg)

        # Fill up to limit
        sessions = []
        for i in range(2):
            s = eng.init_demo_session(f"user{i}@example.com", f"+1234567890{i}")
            token = eng._payment._make_token(s.session_id, eng._payment.amount)
            eng.activate_session(s.session_id, token)
            sessions.append(s)

        assert eng.active_session_count == 2

        # Third should fail
        s3 = eng.init_demo_session("user3@example.com", "+12345678903")
        token3 = eng._payment._make_token(s3.session_id, eng._payment.amount)
        with pytest.raises(ValueError, match="Max concurrent"):
            eng.activate_session(s3.session_id, token3)

    def test_active_count_decrements_on_end(self, config):
        eng = VoiceDemoEngine(config=config)
        s = eng.init_demo_session("u@e.com", "+12345678901")
        token = eng._payment._make_token(s.session_id, eng._payment.amount)
        eng.activate_session(s.session_id, token)
        assert eng.active_session_count == 1

        eng.end_demo_session(s.session_id)
        assert eng.active_session_count == 0

    def test_active_count_decrements_on_timeout(self):
        cfg = VoiceDemoConfig(session_timeout_seconds=1)
        eng = VoiceDemoEngine(config=cfg)
        s = eng.init_demo_session("u@e.com", "+12345678901")
        token = eng._payment._make_token(s.session_id, eng._payment.amount)
        eng.activate_session(s.session_id, token)
        assert eng.active_session_count == 1

        time.sleep(1.1)
        fetched = eng.get_session(s.session_id)
        assert fetched.status == SessionStatus.EXPIRED
        assert eng.active_session_count == 0


# ═══════════════════════════════════════════════════════════════════════════
# BC-008: Garbage Input / Defensive
# ═══════════════════════════════════════════════════════════════════════════

class TestDefensiveInput:
    """BC-008: Ensure garbage input never crashes the system."""

    def test_init_with_empty_strings(self, engine):
        with pytest.raises(ValueError):
            engine.init_demo_session("", "+12345678901")
        with pytest.raises(ValueError):
            engine.init_demo_session("a@b.com", "")

    def test_init_with_special_chars_email(self, engine):
        """Email with whitespace (spaces, newlines) should fail validation."""
        with pytest.raises(ValueError):
            engine.init_demo_session("user name@example.com", "+12345678901")

    def test_init_with_special_chars_phone(self, engine):
        """Phone with letters should fail validation."""
        with pytest.raises(ValueError):
            engine.init_demo_session("user@example.com", "+abc12345678")

    def test_process_voice_input_nonexistent_session(self, engine):
        result = engine.process_voice_input("nope", "data")
        assert result.success is False
        assert result.error

    def test_process_voice_input_non_active_session(self, engine):
        session = engine.init_demo_session("a@b.com", "+12345678901")
        # Session is CREATED, not ACTIVE
        result = engine.process_voice_input(session.session_id, "data")
        assert result.success is False

    def test_generate_response_nonexistent_session(self, engine):
        result = engine.generate_voice_response("nope", "hi")
        assert result.success is False

    def test_get_session_none_id(self, engine):
        assert engine.get_session(None) is None

    def test_end_session_none_id(self, engine):
        with pytest.raises(KeyError):
            engine.end_demo_session(None)

    def test_get_summary_none_id(self, engine):
        with pytest.raises(KeyError):
            engine.get_demo_summary(None)

    def test_process_voice_with_int_audio(self, active_session, engine):
        """BC-008: integer audio does not crash."""
        result = engine.process_voice_input(active_session.session_id, 42)
        # Placeholder transcribe handles this: int has no len() but
        # isinstance check passes — should return error gracefully
        assert isinstance(result, VoiceDemoResult)

    def test_generate_response_empty_text(self, active_session, engine):
        result = engine.generate_voice_response(active_session.session_id, "")
        assert result.success is False

    def test_generate_response_none_text(self, active_session, engine):
        result = engine.generate_voice_response(active_session.session_id, None)
        assert result.success is False


# ═══════════════════════════════════════════════════════════════════════════
# Thread Safety
# ═══════════════════════════════════════════════════════════════════════════

class TestThreadSafety:
    """Ensure engine is safe for concurrent access."""

    def test_concurrent_init_sessions(self, config):
        eng = VoiceDemoEngine(config=config)
        errors = []

        def create(i):
            try:
                eng.init_demo_session(f"user{i}@example.com", f"+1234567890{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert eng.total_session_count == 20

    def test_concurrent_get_sessions(self, config):
        eng = VoiceDemoEngine(config=config)
        session = eng.init_demo_session("a@b.com", "+12345678901")

        results = []
        def get():
            results.append(eng.get_session(session.session_id))

        threads = [threading.Thread(target=get) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r is not None for r in results)
        assert len(results) == 10


# ═══════════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════════

class TestSingleton:
    """Tests for module-level singleton management."""

    def test_get_engine_returns_same_instance(self):
        e1 = get_voice_demo_engine()
        e2 = get_voice_demo_engine()
        assert e1 is e2

    def test_reset_engine(self):
        e1 = get_voice_demo_engine()
        reset_voice_demo_engine()
        e2 = get_voice_demo_engine()
        assert e1 is not e2


# ═══════════════════════════════════════════════════════════════════════════
# Session Timeout / Expiry
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionTimeout:
    """Tests for idle session timeout."""

    def test_session_expires_after_timeout(self):
        cfg = VoiceDemoConfig(session_timeout_seconds=1)
        eng = VoiceDemoEngine(config=cfg)
        s = eng.init_demo_session("u@e.com", "+12345678901")
        token = eng._payment._make_token(s.session_id, eng._payment.amount)
        eng.activate_session(s.session_id, token)

        time.sleep(1.1)
        fetched = eng.get_session(s.session_id)
        assert fetched.status == SessionStatus.EXPIRED
        assert fetched.ended_at is not None

    def test_non_active_session_not_timed_out(self, engine):
        """CREATED session should not be auto-expired."""
        session = engine.init_demo_session("a@b.com", "+12345678901")
        fetched = engine.get_session(session.session_id)
        assert fetched.status == SessionStatus.CREATED

    def test_ended_session_not_timed_out(self, active_session, engine):
        engine.end_demo_session(active_session.session_id)
        time.sleep(0.1)
        fetched = engine.get_session(active_session.session_id)
        assert fetched.status == SessionStatus.ENDED


# ═══════════════════════════════════════════════════════════════════════════
# Session ID Generation
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionIdGeneration:
    """Tests for session ID generation."""

    def test_generates_unique_ids(self):
        ids = {_generate_session_id(f"user{i}@example.com") for i in range(100)}
        # With UUID + timestamp, all should be unique
        assert len(ids) == 100

    def test_id_length(self):
        sid = _generate_session_id("test@example.com")
        assert len(sid) == 32

    def test_id_is_hex(self):
        sid = _generate_session_id("test@example.com")
        assert all(c in "0123456789abcdef" for c in sid)

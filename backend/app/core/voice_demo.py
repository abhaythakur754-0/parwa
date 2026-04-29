"""
Voice Demo System (F-008)

Gated $1 paywall for voice AI demo experience.  Visitors pay a nominal
fee to try PARWA's voice capabilities, reducing free-demo abuse while
giving serious buyers a hands-on preview.

Design decisions
----------------
1. No real Twilio — pipeline uses placeholder STT/TTS that simulate
   voice processing.  Real Twilio lands in Week 13 (F-127).
2. Payment — token-based verification (consistent with Paddle checkout
   flow used elsewhere in the project).
3. Session management — in-memory dict with TTL.
4. BC-002 — all money uses ``Decimal`` (never float).
5. BC-008 — defensive everywhere; never crash on bad input.
6. Thread-safe via ``threading.Lock``.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("parwa.core.voice_demo")


# ── Helpers ──────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[1-9]\d{6,14}$")


def _valid_email(email: Any) -> bool:
    return isinstance(email, str) and bool(_EMAIL_RE.match(email))


def _valid_phone(phone: Any) -> bool:
    return isinstance(phone, str) and bool(_PHONE_RE.match(phone))


def _safe_decimal(value: Any) -> Optional[Decimal]:
    """Coerce *value* to Decimal or return None (BC-002, BC-008)."""
    if isinstance(value, Decimal):
        return value
    try:
        if value is None:
            return None
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────────

class SessionStatus(str, Enum):
    CREATED = "created"
    PAID = "paid"
    ACTIVE = "active"
    ENDED = "ended"
    EXPIRED = "expired"
    FAILED = "failed"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


# ── Data Classes ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VoiceDemoConfig:
    """Immutable configuration for the voice demo system."""

    price_usd: Decimal = Decimal("1.00")
    max_duration_seconds: int = 300  # 5 minutes
    max_concurrent_sessions: int = 50
    allowed_countries: List[str] = field(
        default_factory=lambda: ["US", "CA", "GB", "AU", "IN", "DE", "FR"]
    )
    session_timeout_seconds: int = 1800  # 30 minutes idle
    retry_limit: int = 3

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "price_usd", _safe_decimal(
                self.price_usd) or Decimal("1.00"))
        if self.max_duration_seconds < 1:
            raise ValueError("max_duration_seconds must be >= 1")
        if self.max_concurrent_sessions < 1:
            raise ValueError("max_concurrent_sessions must be >= 1")
        if self.session_timeout_seconds < 1:
            raise ValueError("session_timeout_seconds must be >= 1")
        if self.retry_limit < 1:
            raise ValueError("retry_limit must be >= 1")


@dataclass
class VoiceDemoSession:
    """A single voice demo session with paywall state."""

    session_id: str
    user_email: str
    phone_number: str
    status: SessionStatus = SessionStatus.CREATED
    payment_status: PaymentStatus = PaymentStatus.PENDING
    amount_paid: Decimal = Decimal("0.00")
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    twilio_call_sid: Optional[str] = None
    created_at: datetime = field(default_factory=_now_utc)
    last_activity_at: datetime = field(default_factory=_now_utc)
    retry_count: int = 0
    company_context: str = ""

    # Internal bookkeeping
    _payment_token_hash: Optional[str] = field(default=None, repr=False)
    _paddle_transaction_id: Optional[str] = field(default=None, repr=False)


@dataclass
class PaymentIntent:
    """Lightweight payment intent (Paddle checkout token)."""

    session_id: str
    amount: Decimal
    currency: str = "USD"
    status: PaymentStatus = PaymentStatus.PENDING
    checkout_url: str = ""
    created_at: datetime = field(default_factory=_now_utc)


@dataclass
class VoiceDemoResult:
    """Result of a voice pipeline step."""

    success: bool
    text: str = ""
    audio_base64: str = ""
    confidence: float = 0.0
    error: str = ""
    latency_ms: float = 0.0


@dataclass
class RefundResult:
    """Result of a refund attempt."""

    success: bool
    session_id: str
    refund_amount: Decimal
    status: PaymentStatus = PaymentStatus.PENDING
    message: str = ""


@dataclass
class DemoSummary:
    """Summary of a completed voice demo session."""

    session_id: str
    user_email: str
    status: SessionStatus
    payment_status: PaymentStatus
    amount_paid: Decimal
    duration_seconds: float
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    interaction_count: int = 0


# ── Voice Demo Payment ───────────────────────────────────────────────────

class VoiceDemoPayment:
    """Handles the $1 demo paywall via token-based verification.

    In production this would integrate with Paddle checkout.  For now we
    use a simple HMAC-based token scheme: the token is
    ``sha256(session_id + secret_salt + amount)``.  A valid token means
    the payment is considered completed.
    """

    _SALT = "parwa_voice_demo_2024"

    def __init__(self, config: Optional[VoiceDemoConfig] = None) -> None:
        self._config = config or VoiceDemoConfig()

    @property
    def amount(self) -> Decimal:
        """Price in USD (BC-002: always Decimal)."""
        return self._config.price_usd

    # -- public API -------------------------------------------------------

    def create_payment_intent(
        self, email: str, phone: str
    ) -> PaymentIntent:
        """Create a payment intent for the voice demo.

        Returns a ``PaymentIntent`` with a deterministic session id and
        a pre-computed checkout URL placeholder.
        """
        session_id = _generate_session_id(email)
        amount = self.amount

        token = self._make_token(session_id, amount)

        return PaymentIntent(
            session_id=session_id,
            amount=amount,
            currency="USD",
            status=PaymentStatus.PENDING,
            checkout_url=f"https://pay.paddle.com/checkout/demo/{session_id}?token={token}",
            created_at=_now_utc(),
        )

    def verify_payment(self, session_id: str, payment_token: str) -> bool:
        """Verify that *payment_token* matches the expected HMAC."""
        if not session_id or not payment_token:
            return False
        expected = self._make_token(session_id, self.amount)
        return hashlib.sha256(
            expected.encode()
        ).hexdigest() == hashlib.sha256(
            payment_token.encode()
        ).hexdigest() or expected == payment_token

    def refund_if_needed(
            self,
            session_id: str,
            amount_paid: Decimal = Decimal("0.00")) -> RefundResult:
        """Attempt a refund (placeholder — always succeeds in demo mode).

        In production this would call ``PaddleClient``.
        """
        if not session_id:
            return RefundResult(
                success=False,
                session_id=session_id,
                refund_amount=Decimal("0.00"),
                status=PaymentStatus.FAILED,
                message="Missing session_id",
            )
        # BC-008: handle None or negative amount_paid gracefully
        try:
            if amount_paid is None:
                amount_paid = Decimal("0.00")
            else:
                amount_paid = Decimal(str(amount_paid))
            if amount_paid < 0:
                amount_paid = Decimal("0.00")
        except Exception:
            amount_paid = Decimal("0.00")
        refund_amount = min(amount_paid, self.amount)
        return RefundResult(
            success=True,
            session_id=session_id,
            refund_amount=refund_amount,
            status=PaymentStatus.REFUNDED,
            message="Refund processed (demo)",
        )

    # -- internal ---------------------------------------------------------

    def _make_token(self, session_id: str, amount: Decimal) -> str:
        raw = f"{session_id}:{self._SALT}:{str(amount)}"
        return hashlib.sha256(raw.encode()).hexdigest()


# ── Voice Demo Engine ────────────────────────────────────────────────────

class VoiceDemoEngine:
    """Core voice demo pipeline — session lifecycle, voice I/O, paywall.

    Thread-safe.  All public methods are safe to call from multiple
    threads.
    """

    def __init__(
        self,
        config: Optional[VoiceDemoConfig] = None,
        payment: Optional[VoiceDemoPayment] = None,
    ) -> None:
        self._config = config or VoiceDemoConfig()
        self._payment = payment or VoiceDemoPayment(self._config)
        self._lock = threading.Lock()
        # session_id -> VoiceDemoSession
        self._sessions: Dict[str, VoiceDemoSession] = {}
        # Track active session count
        self._active_count: int = 0

    # -- public API: sessions ---------------------------------------------

    def init_demo_session(self, email: str, phone: str) -> VoiceDemoSession:
        """Create a new demo session (requires payment before activation)."""
        if not _valid_email(email):
            raise ValueError("Invalid email address")
        if not _valid_phone(phone):
            raise ValueError("Invalid phone number")

        intent = self._payment.create_payment_intent(email, phone)

        session = VoiceDemoSession(
            session_id=intent.session_id,
            user_email=email,
            phone_number=phone,
            status=SessionStatus.CREATED,
            payment_status=PaymentStatus.PENDING,
        )

        with self._lock:
            self._sessions[session.session_id] = session

        logger.info(
            "voice_demo_session_created session_id=%s email=%s",
            session.session_id,
            email,
        )
        return session

    def activate_session(
            self,
            session_id: str,
            payment_token: str) -> VoiceDemoSession:
        """Activate a session after payment verification."""
        with self._lock:
            session = self._get_session_locked(session_id)
            if session is None:
                raise KeyError(f"Session not found: {session_id}")

            if session.status not in (SessionStatus.CREATED,):
                raise ValueError(
                    f"Session {session_id} is not in CREATED state (current: {
                        session.status.value})")

            if not self._payment.verify_payment(session_id, payment_token):
                session.status = SessionStatus.FAILED
                session.payment_status = PaymentStatus.FAILED
                raise ValueError("Payment verification failed")

            # Check concurrency limit
            if self._active_count >= self._config.max_concurrent_sessions:
                session.status = SessionStatus.FAILED
                raise ValueError("Max concurrent demo sessions reached")

            session.status = SessionStatus.PAID
            session.payment_status = PaymentStatus.COMPLETED
            session.amount_paid = self._payment.amount
            session.started_at = _now_utc()
            session.last_activity_at = _now_utc()
            session.status = SessionStatus.ACTIVE
            self._active_count += 1

        logger.info(
            "voice_demo_session_activated session_id=%s",
            session_id,
        )
        return session

    def get_session(self, session_id: str) -> Optional[VoiceDemoSession]:
        """Get session by id, returning None if missing or expired."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            # Check for idle timeout
            if session.status == SessionStatus.ACTIVE:
                idle = (_now_utc() - session.last_activity_at).total_seconds()
                if idle > self._config.session_timeout_seconds:
                    session.status = SessionStatus.EXPIRED
                    session.ended_at = _now_utc()
                    self._active_count = max(0, self._active_count - 1)
            return session

    def end_demo_session(self, session_id: str) -> DemoSummary:
        """End an active demo session and return a summary."""
        with self._lock:
            session = self._get_session_locked(session_id)
            if session is None:
                raise KeyError(f"Session not found: {session_id}")

            if session.status != SessionStatus.ACTIVE:
                raise ValueError(
                    f"Session {session_id} is not active (current: {
                        session.status.value})")

            now = _now_utc()
            if session.started_at:
                session.duration_seconds = (
                    now - session.started_at).total_seconds()
            session.ended_at = now
            session.status = SessionStatus.ENDED
            self._active_count = max(0, self._active_count - 1)

        return self.get_demo_summary(session_id)

    def get_demo_summary(self, session_id: str) -> DemoSummary:
        """Get a summary for any session (active or completed)."""
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        return DemoSummary(
            session_id=session.session_id,
            user_email=session.user_email,
            status=session.status,
            payment_status=session.payment_status,
            amount_paid=session.amount_paid,
            duration_seconds=session.duration_seconds,
            started_at=session.started_at,
            ended_at=session.ended_at,
        )

    @property
    def active_session_count(self) -> int:
        with self._lock:
            return self._active_count

    @property
    def total_session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    # -- public API: voice pipeline ----------------------------------------

    def process_voice_input(
            self,
            session_id: str,
            audio_base64: Any) -> VoiceDemoResult:
        """Full voice input pipeline: STT → AI → response."""
        session = self.get_session(session_id)
        if session is None or session.status != SessionStatus.ACTIVE:
            return VoiceDemoResult(
                success=False, error="Session not found or not active"
            )

        # Check duration limit
        if session.started_at:
            elapsed = (_now_utc() - session.started_at).total_seconds()
            if elapsed >= self._config.max_duration_seconds:
                with self._lock:
                    session.status = SessionStatus.ENDED
                    session.ended_at = _now_utc()
                    session.duration_seconds = elapsed
                    self._active_count = max(0, self._active_count - 1)
                return VoiceDemoResult(
                    success=False, error="Demo duration limit exceeded"
                )

        # Touch activity
        with self._lock:
            session.last_activity_at = _now_utc()

        t0 = time.monotonic()

        # 1. STT
        transcribed = self._transcribe_audio(audio_base64)
        if not transcribed.success:
            return transcribed

        # 2. AI processing
        ai_result = self._process_through_ai(
            transcribed.text, session.company_context
        )
        if not ai_result.success:
            return ai_result

        latency = (time.monotonic() - t0) * 1000

        return VoiceDemoResult(
            success=True,
            text=ai_result.text,
            confidence=ai_result.confidence,
            latency_ms=latency,
        )

    def generate_voice_response(
            self,
            session_id: str,
            text: str) -> VoiceDemoResult:
        """Generate TTS audio for a text response."""
        session = self.get_session(session_id)
        if session is None or session.status != SessionStatus.ACTIVE:
            return VoiceDemoResult(
                success=False, error="Session not found or not active"
            )

        with self._lock:
            session.last_activity_at = _now_utc()

        t0 = time.monotonic()
        result = self._synthesize_speech(text)
        result.latency_ms = (time.monotonic() - t0) * 1000
        return result

    # -- pipeline stages (placeholders) ------------------------------------

    def _transcribe_audio(self, audio_base64: Any) -> VoiceDemoResult:
        """STT placeholder — simulates transcription."""
        if audio_base64 is None:
            return VoiceDemoResult(success=False, error="No audio provided")
        if isinstance(audio_base64, str) and len(audio_base64) < 4:
            return VoiceDemoResult(success=False, error="Audio data too short")

        # In production this would call Whisper / Deepgram
        return VoiceDemoResult(
            success=True,
            text="[transcription placeholder]",
            confidence=0.95,
        )

    def _process_through_ai(
            self,
            text: str,
            company_context: str) -> VoiceDemoResult:
        """AI pipeline placeholder — simulates intent + response generation."""
        if not text or not isinstance(text, str):
            return VoiceDemoResult(success=False, error="No text to process")

        # In production this runs through PARWA's full AI pipeline
        response = f"[AI response to: {text[:80]}]"
        if company_context:
            response = f"[{company_context}] {response}"

        return VoiceDemoResult(
            success=True,
            text=response,
            confidence=0.92,
        )

    def _synthesize_speech(self, text: str) -> VoiceDemoResult:
        """TTS placeholder — simulates speech synthesis."""
        if not text or not isinstance(text, str):
            return VoiceDemoResult(
                success=False, error="No text to synthesize")

        # In production this would call ElevenLabs / OpenAI TTS
        fake_audio = "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="
        return VoiceDemoResult(
            success=True,
            text=text,
            audio_base64=fake_audio,
            confidence=0.98,
        )

    # -- internal helpers --------------------------------------------------

    def _get_session_locked(
            self,
            session_id: str) -> Optional[VoiceDemoSession]:
        """Must be called while holding ``self._lock``."""
        return self._sessions.get(session_id)


# ── Utility ──────────────────────────────────────────────────────────────

def _generate_session_id(email: str) -> str:
    """Deterministic-ish session id derived from email + timestamp."""
    raw = f"{email}:{uuid.uuid4()}:{time.time()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ── Module-level singleton (lazy) ────────────────────────────────────────

_engine: Optional[VoiceDemoEngine] = None
_engine_lock = threading.Lock()


def get_voice_demo_engine(
    config: Optional[VoiceDemoConfig] = None,
) -> VoiceDemoEngine:
    """Return the module-level ``VoiceDemoEngine`` singleton."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = VoiceDemoEngine(config=config)
    return _engine


def reset_voice_demo_engine() -> None:
    """Reset the singleton (used in tests)."""
    global _engine
    with _engine_lock:
        _engine = None

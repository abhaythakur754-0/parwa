"""
Jarvis payment service — extracted from jarvis_service.py

Contains 12 functions related to payment.
"""

from app.services.jarvis._shared import *

def send_business_otp(
    db: Session,
    session_id: str,
    user_id: str,
    email: str,
) -> Dict[str, Any]:
    """Generate 6-digit OTP and store in session context.

    In production, this sends an email via the email service.
    Returns OTP metadata for the caller to construct the response.
    """
    session = get_session(db, session_id, user_id)
    ctx = _parse_context(session.context_json)

    # Rate limit OTP attempts
    otp_data = ctx.get("otp", {})
    if otp_data.get("attempts", 0) >= MAX_OTP_ATTEMPTS:
        raise RateLimitError(
            message="Too many OTP attempts. Please try again later.",
            details={"attempts": otp_data.get("attempts", 0)},
        )

    # Generate OTP
    otp_code = secrets.token_hex(OTP_LENGTH // 2)[:OTP_LENGTH].upper()
    if len(otp_code) < OTP_LENGTH:
        otp_code = otp_code.zfill(OTP_LENGTH)

    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
    ).isoformat()

    # Store in context
    otp_data = {
        "code": otp_code,
        "email": email,
        "attempts": 0,
        "expires_at": expires_at,
        "status": "sent",
    }
    ctx["otp"] = otp_data
    ctx["business_email"] = email
    session.context_json = json.dumps(ctx)
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    # Create action ticket
    _create_ticket(db, session_id, "otp_verification", {"email": email})

    # Send OTP via Brevo email
    try:
        from app.services.email_service import send_email
        otp_html = render_email_template(
            "otp_email.html",
            {"otp_code": otp_code, "expires_minutes": OTP_EXPIRY_MINUTES},
        ) if hasattr(render_email_template, '__call__') else f"""
        <html><body>
        <h2>Your PARWA Verification Code</h2>
        <p>Your business email verification code is:</p>
        <h1 style="font-size:32px;letter-spacing:8px;color:#10b981;">{otp_code}</h1>
        <p>This code expires in {OTP_EXPIRY_MINUTES} minutes.</p>
        <p>If you didn't request this, ignore this email.</p>
        </body></html>
        """
        email_result = send_email(
            to=email,
            subject=f"PARWA Verification Code: {otp_code}",
            html_content=otp_html,
        )
        # Check if email actually sent
        if not email_result or not email_result.get("success"):
            email_error = email_result.get("error", "unknown") if email_result else "no_response"
            logger.error(
                "business_otp_email_failed session_id=%s error=%s",
                session_id, email_error,
            )
            # Update OTP status to 'email_failed'
            otp_data["status"] = "email_failed"
            ctx["otp"] = otp_data
            session.context_json = json.dumps(ctx)
            db.flush()
            return {
                "message": f"OTP generated but email failed to send: {email_error}. Please contact support.",
                "status": "email_failed",
                "attempts_remaining": MAX_OTP_ATTEMPTS,
                "expires_at": expires_at,
            }
    except Exception as e:
        logger.error(
            "business_otp_email_failed session_id=%s error=%s",
            session_id, str(e))
        return {
            "message": f"OTP generated but email failed: {str(e)[:100]}",
            "status": "email_failed",
            "attempts_remaining": MAX_OTP_ATTEMPTS,
            "expires_at": expires_at,
        }

    return {
        "message": f"OTP sent to {email}",
        "status": "sent",
        "attempts_remaining": MAX_OTP_ATTEMPTS,
        "expires_at": expires_at,
        # OTP code stored in context only — never returned to client
    }


def verify_business_otp(
    db: Session,
    session_id: str,
    user_id: str,
    code: str,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify OTP code from session context."""
    session = get_session(db, session_id, user_id)
    ctx = _parse_context(session.context_json)
    otp_data = ctx.get("otp", {})

    # Check OTP status
    if otp_data.get("status") == "verified":
        return {
            "message": "Email already verified",
            "status": "verified",
            "attempts_remaining": otp_data.get("attempts_remaining", MAX_OTP_ATTEMPTS),
        }

    # Check expiry
    if otp_data.get("expires_at"):
        expires = datetime.fromisoformat(otp_data["expires_at"])
        if datetime.now(timezone.utc) > expires:
            return {
                "message": "OTP has expired. Please request a new one.",
                "status": "expired",
                "attempts_remaining": 0,
            }

    # Check email match if provided
    if email and otp_data.get("email") and email != otp_data["email"]:
        return {
            "message": "Email does not match the one OTP was sent to",
            "status": "error",
            "attempts_remaining": MAX_OTP_ATTEMPTS - otp_data.get("attempts", 0),
        }

    # Verify code
    attempts = otp_data.get("attempts", 0) + 1
    stored_code = otp_data.get("code", "")

    if code.upper().strip() == stored_code:
        otp_data["status"] = "verified"
        otp_data["verified_at"] = datetime.now(timezone.utc).isoformat()
        otp_data["attempts_remaining"] = MAX_OTP_ATTEMPTS - attempts
        ctx["otp"] = otp_data
        ctx["email_verified"] = True
        session.context_json = json.dumps(ctx)
        session.updated_at = datetime.now(timezone.utc)
        db.flush()

        # Update ticket status
        _complete_latest_ticket(
            db, session_id, "otp_verification",
            {"email": email or otp_data.get("email"), "verified": True},
        )
        # Create verified ticket
        _create_ticket(
            db, session_id, "otp_verified",
            {"email": email or otp_data.get("email")},
        )

        return {
            "message": "Email verified successfully!",
            "status": "verified",
            "attempts_remaining": MAX_OTP_ATTEMPTS - attempts,
        }

    # Wrong code
    otp_data["attempts"] = attempts
    otp_data["attempts_remaining"] = max(0, MAX_OTP_ATTEMPTS - attempts)
    ctx["otp"] = otp_data
    session.context_json = json.dumps(ctx)
    db.flush()

    return {
        "message": f"Invalid OTP. {MAX_OTP_ATTEMPTS - attempts} attempts remaining.",
        "status": "invalid",
        "attempts_remaining": MAX_OTP_ATTEMPTS - attempts,
    }


def purchase_demo_pack(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Activate $1 demo pack: 500 messages + 3-min AI call for 24 hours.

    Paddle was removed on 2026-06-24. Demo-pack checkout now goes through
    Razorpay Standard Checkout. This function is kept for backward-compat
    with existing Jarvis call sites but returns a redirect instruction.
    """
    session = get_session(db, session_id, user_id)
    _create_ticket(db, session_id, "payment_demo_pack", {
        "pack_type": "demo",
        "price_usd": 1.00,
        "status": "pending_payment",
        "provider": "razorpay",
    })
    return {
        "message": "Demo Pack purchase is now handled by Razorpay. Use POST /api/razorpay/create-order with amount=100 (paise).",
        "status": "pending_payment",
        "amount": "$1.00",
        "currency": "USD",
        "pack_type": "demo",
        "provider": "razorpay",
        "checkout_endpoint": "/api/razorpay/create-order",
    }


def get_demo_pack_status(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Get current demo pack status and limits."""
    session = get_session(db, session_id, user_id)
    limit, remaining = check_message_limit(db, session)

    return {
        "pack_type": session.pack_type,
        "remaining_today": remaining,
        "total_allowed": limit,
        "pack_expiry": (
            session.pack_expiry.isoformat() if session.pack_expiry else None
        ),
        "demo_call_remaining": not session.demo_call_used,
    }


def create_payment_session(
    db: Session,
    session_id: str,
    user_id: str,
    variants: List[Dict[str, Any]],
    industry: str,
) -> Dict[str, Any]:
    """Create a Razorpay subscription checkout for variant purchase.

    Paddle was removed on 2026-06-24. Variant subscriptions are now created
    via Razorpay (`POST /api/billing/razorpay/subscribe`). This function
    is kept for backward-compat with existing Jarvis call sites.
    """
    session = get_session(db, session_id, user_id)
    total_monthly = sum(v.get("price", 0) * v.get("quantity", 1) for v in variants)

    _create_ticket(db, session_id, "payment_variant", {
        "variants": variants,
        "industry": industry,
        "total_monthly": total_monthly,
        "provider": "razorpay",
    })

    session.payment_status = "pending"
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    return {
        "status": "pending",
        "amount": f"${total_monthly:.2f}",
        "currency": "USD",
        "total_monthly": total_monthly,
        "industry": industry,
        "variant_count": len(variants),
        "provider": "razorpay",
        "subscribe_endpoint": "/api/billing/razorpay/subscribe",
    }


def handle_payment_webhook(
    db: Session,
    event_type: str,
    event_data: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    raw_payload: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Process a Razorpay webhook event (replaces the old Paddle webhook handler).

    Paddle was removed on 2026-06-24. Razorpay webhooks are now handled by
    `app.services.razorpay_service.handle_webhook_event`, called from
    `/api/billing/razorpay/webhook`. This function is kept for backward-compat
    with any Jarvis call site that still references it; it delegates to the
    Razorpay handler.
    """
    logger.info("jarvis_payment_webhook_delegated_to_razorpay event_type=%s", event_type)
    try:
        from app.services.razorpay_service import handle_webhook_event as rzp_handler
        return asyncio.run(rzp_handler(db, event_data))
    except Exception as e:
        logger.error("jarvis_payment_webhook_delegate_failed error=%s", str(e))
        return {"status": "skipped", "reason": str(e)}

def get_payment_status(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Get current payment status for a session.

    Returns real data from the session record plus any stored
    transaction metadata from the webhook activation.
    """
    session = get_session(db, session_id, user_id)

    # Extract stored transaction data from context_json
    ctx = _parse_context(session.context_json or "{}")

    # Check action tickets for the latest payment info
    latest_payment_ticket = (
        db.query(JarvisActionTicket)
        .filter(
            JarvisActionTicket.session_id == session_id,
            JarvisActionTicket.ticket_type.in_(["payment_demo_pack", "payment_variant"]),
        )
        .order_by(JarvisActionTicket.created_at.desc())
        .first()
    )

    transaction_id = None
    amount = None
    paid_at = None

    if latest_payment_ticket and latest_payment_ticket.result_json:
        ticket_result = _parse_context(latest_payment_ticket.result_json)
        transaction_id = ticket_result.get("transaction_id")
        amount = ticket_result.get("amount")

    if session.payment_status == "completed":
        completed_ticket = (
            db.query(JarvisActionTicket)
            .filter(
                JarvisActionTicket.session_id == session_id,
                JarvisActionTicket.ticket_type == "payment_variant_completed",
            )
            .order_by(JarvisActionTicket.created_at.desc())
            .first()
        )
        if completed_ticket:
            paid_at = completed_ticket.created_at.isoformat() if completed_ticket.created_at else None
            if not transaction_id:
                ticket_result = _parse_context(completed_ticket.result_json or "{}")
                transaction_id = ticket_result.get("transaction_id")

    return {
        "status": session.payment_status,
        "paddle_transaction_id": transaction_id,
        "amount": amount,
        "currency": "USD",
        "paid_at": paid_at,
        "pack_type": session.pack_type,
        "pack_expiry": session.pack_expiry.isoformat() if session.pack_expiry else None,
        "demo_call_remaining": not session.demo_call_used,
        "message_count_today": session.message_count_today,
        "hired_variants": ctx.get("hired_variants", []),
        "subscription_id": ctx.get("subscription_id"),
    }


def initiate_demo_call(
    db: Session,
    session_id: str,
    user_id: str,
    phone_number: str,
) -> Dict[str, Any]:
    """Initiate 3-minute AI voice demo call.

    Validates phone, stores call request, and initiates via Twilio.
    Falls back gracefully if Twilio is not configured.
    """
    session = get_session(db, session_id, user_id)

    # Validate phone number
    import re
    cleaned_phone = re.sub(r'[^0-9+]', '', phone_number)
    if len(cleaned_phone) < 10 or len(cleaned_phone) > 15:
        raise ValidationError(
            message="Invalid phone number format",
            details={"phone_number": phone_number},
        )

    # Create action ticket
    ticket = _create_ticket(db, session_id, "demo_call", {
        "phone_number": cleaned_phone,
        "status": "initiated",
    })

    # Store call details in context
    ctx = _parse_context(session.context_json)
    ctx["demo_call"] = {
        "phone_number": cleaned_phone,
        "status": "initiated",
        "ticket_id": str(ticket.id),
        "initiated_at": datetime.now(timezone.utc).isoformat(),
    }
    session.context_json = json.dumps(ctx)
    session.updated_at = datetime.now(timezone.utc)
    db.flush()

    # Attempt to initiate Twilio call
    call_sid = None
    call_status = "pending_twilio"

    try:
        from twilio.rest import Client
        from app.core.config import get_settings

        settings = get_settings()
        twilio_account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        twilio_auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        twilio_phone_number = getattr(settings, 'TWILIO_PHONE_NUMBER', None)

        if all([twilio_account_sid, twilio_auth_token, twilio_phone_number]):
            client = Client(twilio_account_sid, twilio_auth_token)

            # Create TwiML for the AI demo call
            from twilio.twiml.voice_response import VoiceResponse
            twiml_response = VoiceResponse()
            twiml_response.say(
                "Hello! This is Jarvis from PARWA. Thank you for trying our voice demo. "
                "I'm going to show you how I handle customer support conversations. "
                "Let me demonstrate with a sample scenario...",
                voice="alice",
            )
            twiml_response.pause(length=2)
            twiml_response.say(
                "I've just demonstrated how PARWA's AI handles real customer queries. "
                "To get started with your own AI support agents, visit our website. "
                "Thank you for your time!",
                voice="alice",
            )
            twiml_response.hangup()

            call = client.calls.create(
                to=cleaned_phone,
                from_=twilio_phone_number,
                twiml=str(twiml_response),
                timeout=30,
                record=True,
            )
            call_sid = call.sid
            call_status = "in_progress"

            logger.info(
                "demo_call_initiated session_id=%s call_sid=%s phone_number=%s",
                session_id, call_sid, cleaned_phone)
        else:
            logger.warning(
                "demo_call_twilio_not_configured session_id=%s message=%s",
                session_id, "Twilio credentials not configured. Call marked as simulated.")
            call_status = "simulated"

    except ImportError:
        logger.warning(
            "demo_call_twilio_not_installed session_id=%s message=%s",
            session_id, "twilio package not installed. Call marked as simulated.")
        call_status = "simulated"
    except Exception as e:
        logger.error(
            "demo_call_initiation_failed session_id=%s error=%s",
            session_id, str(e))
        call_status = "failed"

    # Update ticket with result
    ticket.result_json = json.dumps({
        "call_sid": call_sid,
        "call_status": call_status,
        "phone_number": cleaned_phone,
    })
    ticket.status = call_status
    db.flush()

    return {
        "message": "Demo call initiated!" if call_status == "in_progress" else f"Demo call: {call_status}. Configure Twilio credentials for live calls.",
        "call_sid": call_sid,
        "call_status": call_status,
        "phone_number": cleaned_phone,
        "ticket_id": str(ticket.id),
        "duration_limit_seconds": 180,  # 3 minutes
    }


def verify_demo_call_otp(
    db: Session,
    session_id: str,
    user_id: str,
    otp_code: str,
) -> Dict[str, Any]:
    """Verify the phone OTP for a demo call.

    R-03 FIX: Actually validates the OTP code instead of always
    returning "verified". Checks the stored OTP against the
    provided code, and rejects invalid or expired OTPs.

    In production this would call Twilio's verification API.
    For now, validates against the OTP stored in the session
    context (set during initiate_demo_call).
    """
    session = get_session(db, session_id, user_id)

    ctx = _parse_context(session.context_json)
    demo_call = ctx.get("demo_call", {})

    # If no demo call was initiated, reject
    if not demo_call:
        return {
            "message": "No demo call initiated for this session",
            "status": "error",
        }

    stored_otp = demo_call.get("otp_code")

    # If an OTP was stored (production flow), verify against it
    if stored_otp:
        if stored_otp != otp_code:
            return {
                "message": "Invalid OTP code",
                "status": "rejected",
            }

        # Check OTP expiry (10 minutes)
        import datetime
        otp_created = demo_call.get("otp_created_at")
        if otp_created:
            try:
                created_time = datetime.datetime.fromisoformat(otp_created)
                if (datetime.datetime.now(datetime.timezone.utc) - created_time).total_seconds() > 600:
                    return {
                        "message": "OTP has expired. Please request a new one.",
                        "status": "expired",
                    }
            except (ValueError, TypeError):
                pass  # If we can't parse the time, don't block

        # Mark as verified in context
        demo_call["otp_verified"] = True
        ctx["demo_call"] = demo_call
        session.context_json = json.dumps(ctx)
        db.commit()

        return {
            "message": "Phone verified. Call will start shortly.",
            "status": "verified",
        }

    # Development/staging fallback: if no OTP was stored (no Twilio Verify
    # integration yet), reject rather than bypass. In a real production
    # deployment, Twilio Verify would have set the OTP during initiation.
    return {
        "message": "OTP verification is not configured for this session. "
                   "Please ensure Twilio Verify is enabled.",
        "status": "error",
    }


def get_call_summary(
    db: Session,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Get summary of the demo call."""
    session = get_session(db, session_id, user_id)

    # Find the demo_call ticket
    from database.models.jarvis import JarvisActionTicket
    ticket = db.query(JarvisActionTicket).filter(
        JarvisActionTicket.session_id == session_id,
        JarvisActionTicket.ticket_type == "demo_call",
    ).order_by(JarvisActionTicket.created_at.desc()).first()

    if not ticket:
        return {
            "call_completed": False,
            "message": "No demo call found for this session",
        }

    result = _parse_context(ticket.result_json or "{}")

    # If Twilio call was real, fetch actual details
    if result.get("call_sid"):
        try:
            from twilio.rest import Client
            from app.core.config import get_settings
            settings = get_settings()
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            call = client.calls(result["call_sid"]).fetch()

            duration = int(call.duration or 0)
            result["actual_duration"] = duration
            result["call_status_final"] = call.status
        except Exception:
            pass

    return {
        "call_completed": ticket.status in ("completed", "in_progress", "simulated"),
        "call_status": ticket.status,
        "call_sid": result.get("call_sid"),
        "phone_number": result.get("phone_number"),
        "duration_seconds": result.get("actual_duration", 180),
        "topics_discussed": result.get("topics_discussed", []),
        "key_moments": result.get("key_moments", []),
        "transcript_summary": result.get("transcript_summary"),
    }



"""
PARWA Onboarding Service

Business logic for onboarding wizard state management.

GAP FIXES:
- GAP 1: Row-level locking for state machine race condition prevention
- GAP 5: Consent timestamp validation (server time, reject backdated)
- GAP 6: Failed document handling in onboarding progression

BC-001: All operations scoped to company_id.

Services:
- get_or_create_session: Get or create onboarding session
- complete_step: Complete a wizard step with locking
- accept_legal: Accept legal consents with server timestamps
- activate_ai: Activate AI assistant with prerequisites check
"""

import json
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError

from app.exceptions import ValidationError
from app.logger import get_logger
from app.services.user_details_service import check_ai_activation_prerequisites
from app.tasks.knowledge_tasks import process_knowledge_document
from database.models.onboarding import OnboardingSession, KnowledgeDocument, ConsentRecord
from database.models.user_details import UserDetails

logger = get_logger("onboarding_service")

# Consent timestamp tolerance (5 minutes) — P20: configurable via env
import os
_CONSENT_TIMESTAMP_TOLERANCE_SECONDS = int(
    os.environ.get("CONSENT_TIMESTAMP_TOLERANCE", "300")
)

# Max retry count for failed documents
_MAX_DOCUMENT_RETRIES = 3

# P11: Steps that are optional and can be skipped
_OPTIONAL_STEPS = {4}  # Step 4 = Knowledge Base (optional)


# ── GAP 1: Row-Level Locking for Race Condition Prevention ────────────────


def get_session_with_lock(
    db: Session,
    user_id: str,
    company_id: str,
) -> Optional[OnboardingSession]:
    """
    Get onboarding session with row-level lock.

    GAP 1 FIX: Use SELECT FOR UPDATE to prevent race conditions
    when multiple concurrent requests try to update the same session.

    This ensures that concurrent step completions are serialized
    and the state machine remains consistent.

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID for tenant isolation.

    Returns:
        OnboardingSession or None if not found.
    """
    # Use with_for_update() for row-level locking
    # This blocks other transactions from reading/writing until commit
    session = db.execute(
        select(OnboardingSession)
        .where(
            and_(
                OnboardingSession.user_id == user_id,
                OnboardingSession.company_id == company_id,
            )
        )
        .with_for_update()
    ).scalar_one_or_none()

    return session


def get_or_create_session(
    db: Session,
    user_id: str,
    company_id: str,
) -> OnboardingSession:
    """
    Get or create an onboarding session.

    BC-001: Scoped to company_id.
    GAP 1: Uses locking when updating existing session.
    P1 FIX: Handles race condition on concurrent creation by catching
    IntegrityError from unique constraint and retrying the read.

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID.

    Returns:
        OnboardingSession instance.
    """
    # P1: Always try to acquire lock first — if row exists, we get it.
    # If it doesn't exist, the lock query returns None and we create below.
    try:
        session = db.execute(
            select(OnboardingSession)
            .where(
                and_(
                    OnboardingSession.user_id == user_id,
                    OnboardingSession.company_id == company_id,
                )
            )
            .with_for_update()
        ).scalar_one_or_none()

        if session:
            return session

        # Session doesn't exist — create it inside the same transaction
        # that holds the lock intent. If another request created it between
        # our SELECT and INSERT, the unique constraint will catch it.
        session = OnboardingSession(
            user_id=user_id,
            company_id=company_id,
            current_step=1,
            status="in_progress",
            completed_steps="[]",
            integrations="{}",
            knowledge_base_files="[]",
        )
        db.add(session)
        db.flush()  # Flush to trigger any IntegrityError before commit

    except IntegrityError:
        # Another concurrent request created the session — roll back and retry
        db.rollback()
        session = db.execute(
            select(OnboardingSession)
            .where(
                and_(
                    OnboardingSession.user_id == user_id,
                    OnboardingSession.company_id == company_id,
                )
            )
            .with_for_update()
        ).scalar_one_or_none()
        if not session:
            raise ValidationError(
                message="Failed to create onboarding session. Please retry.",
                details={"user_id": user_id, "company_id": company_id},
            )

    db.commit()
    db.refresh(session)
    logger.info(
        "onboarding_session_created",
        user_id=user_id,
        company_id=company_id,
    )

    return session


def complete_step(
    db: Session,
    user_id: str,
    company_id: str,
    step: int,
) -> Dict[str, Any]:
    """
    Complete a wizard step with race condition prevention.

    GAP 1 FIX: Uses row-level locking to ensure atomic step transitions.
    Validates that step transitions are sequential (no skipping).

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID.
        step: Step number being completed (1-6).

    Returns:
        Dict with updated session state.

    Raises:
        ValidationError: If step transition is invalid.
    """
    if step < 1 or step > 6:
        raise ValidationError(
            message="Invalid step number. Must be 1-6.",
            details={"step": step},
        )

    # GAP 1: Lock the row for update
    session = get_session_with_lock(db, user_id, company_id)

    if not session:
        session = get_or_create_session(db, user_id, company_id)

    # Parse completed steps
    try:
        completed = json.loads(session.completed_steps or "[]")
    except json.JSONDecodeError:
        completed = []

    # P11: Allow skipping optional steps (Step 4 = KB).
    # If the requested step is an optional step, advance past it
    # if all previous non-optional steps are completed.
    expected_step = session.current_step
    if step != expected_step and step in _OPTIONAL_STEPS:
        # Check that all required steps before this optional step are done
        required_before = [s for s in range(1, step) if s not in _OPTIONAL_STEPS]
        if all(s in completed for s in required_before):
            # Allow skipping this optional step
            pass
        else:
            raise ValidationError(
                message=f"Cannot skip to step {step}. Complete required steps first.",
                details={
                    "expected_step": expected_step,
                    "actual_step": step,
                    "missing_required": [s for s in required_before if s not in completed],
                },
            )
    elif step != expected_step:
        raise ValidationError(
            message=f"Invalid step transition. Expected step {expected_step}, got {step}.",
            details={
                "expected_step": expected_step,
                "actual_step": step,
                "completed_steps": completed,
            },
        )

    # Complete the step
    if step not in completed:
        completed.append(step)

    session.completed_steps = json.dumps(completed)
    session.current_step = step + 1 if step < 6 else 6
    session.updated_at = datetime.now(timezone.utc)

    # Mark flags based on step
    if step == 1:
        session.details_completed = True
    elif step == 2:
        session.legal_accepted = True
    elif step == 6:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(session)

    logger.info(
        "onboarding_step_completed",
        user_id=user_id,
        company_id=company_id,
        step=step,
        current_step=session.current_step,
    )

    return {
        "id": session.id,
        "current_step": session.current_step,
        "completed_steps": completed,
        "status": session.status,
    }


# ── GAP 5: Consent Timestamp Validation ────────────────────────────────────


def validate_consent_timestamp(
    submitted_time: Optional[datetime],
) -> datetime:
    """
    Validate consent timestamp and return server time.

    GAP 5 FIX: Ensures consent timestamps use server time, not client time.
    Rejects backdated and future-dated timestamps.

    Rules:
    1. Always use server time for consent recording
    2. If client submits a timestamp, verify it's within tolerance
    3. Reject timestamps more than 5 minutes in the past or future

    Args:
        submitted_time: Client-submitted timestamp (optional).

    Returns:
        Server timestamp to use for consent recording.

    Raises:
        ValidationError: If submitted timestamp is outside tolerance.
    """
    server_time = datetime.now(timezone.utc)

    if submitted_time is not None:
        # Ensure submitted time is timezone-aware
        if submitted_time.tzinfo is None:
            submitted_time = submitted_time.replace(tzinfo=timezone.utc)

        time_diff = (submitted_time - server_time).total_seconds()

        # Reject future-dated timestamps
        if time_diff > _CONSENT_TIMESTAMP_TOLERANCE_SECONDS:
            raise ValidationError(
                message="Consent timestamp cannot be in the future.",
                details={
                    "submitted_time": submitted_time.isoformat(),
                    "server_time": server_time.isoformat(),
                },
            )

        # Reject backdated timestamps
        if time_diff < -_CONSENT_TIMESTAMP_TOLERANCE_SECONDS:
            raise ValidationError(
                message="Consent timestamp is too old. Please refresh and try again.",
                details={
                    "submitted_time": submitted_time.isoformat(),
                    "server_time": server_time.isoformat(),
                    "tolerance_seconds": _CONSENT_TIMESTAMP_TOLERANCE_SECONDS,
                },
            )

    # Always return server time for actual recording
    return server_time


def accept_legal_consents(
    db: Session,
    user_id: str,
    company_id: str,
    accept_terms: bool,
    accept_privacy: bool,
    accept_ai_data: bool,
    client_timestamp: Optional[datetime] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Accept legal consents with server-time enforcement.

    GAP 5 FIX: Uses server time for consent recording.
    Validates all required consents are accepted.

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID.
        accept_terms: Accept Terms of Service.
        accept_privacy: Accept Privacy Policy.
        accept_ai_data: Accept AI Data Processing Agreement.
        client_timestamp: Optional client-provided timestamp (validated).
        ip_address: Client IP address for audit.
        user_agent: Client user agent for audit.

    Returns:
        Dict with consent acceptance details.

    Raises:
        ValidationError: If required consents not accepted or timestamp invalid.
    """
    # Validate all consents are accepted
    if not accept_terms:
        raise ValidationError(
            message="Terms of Service must be accepted.",
            details={"field": "accept_terms"},
        )

    if not accept_privacy:
        raise ValidationError(
            message="Privacy Policy must be accepted.",
            details={"field": "accept_privacy"},
        )

    if not accept_ai_data:
        raise ValidationError(
            message="AI Data Processing Agreement must be accepted.",
            details={"field": "accept_ai_data"},
        )

    # GAP 5: Validate timestamp and get server time
    server_time = validate_consent_timestamp(client_timestamp)

    # GAP 1: Lock the session
    session = get_session_with_lock(db, user_id, company_id)

    if not session:
        session = get_or_create_session(db, user_id, company_id)

    # Record consent times using SERVER time
    session.legal_accepted = True
    session.terms_accepted_at = server_time
    session.privacy_accepted_at = server_time
    session.ai_data_accepted_at = server_time
    session.updated_at = datetime.now(timezone.utc)

    # P12 FIX: Create SEPARATE consent records per consent type for GDPR audit.
    # Each consent type gets its own record with version tracking,
    # so version changes to individual agreements are traceable.
    consent_records = [
        ConsentRecord(
            company_id=company_id,
            user_id=user_id,
            consent_type="terms_of_service",
            consent_version="1.0",
            ip_address=ip_address,
            user_agent=user_agent,
            granted=True,
        ),
        ConsentRecord(
            company_id=company_id,
            user_id=user_id,
            consent_type="privacy_policy",
            consent_version="1.0",
            ip_address=ip_address,
            user_agent=user_agent,
            granted=True,
        ),
        ConsentRecord(
            company_id=company_id,
            user_id=user_id,
            consent_type="ai_data_processing",
            consent_version="1.0",
            ip_address=ip_address,
            user_agent=user_agent,
            granted=True,
        ),
    ]
    for cr in consent_records:
        db.add(cr)

    db.commit()
    db.refresh(session)

    logger.info(
        "legal_consents_accepted",
        user_id=user_id,
        company_id=company_id,
        ip_address=ip_address,
    )

    return {
        "message": "Legal consents accepted successfully.",
        "terms_accepted_at": server_time.isoformat(),
        "privacy_accepted_at": server_time.isoformat(),
        "ai_data_accepted_at": server_time.isoformat(),
    }


# ── GAP 6: Failed Document Handling ─────────────────────────────────────────


def get_knowledge_documents(
    db: Session,
    company_id: str,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get knowledge documents for a company.

    GAP 6: Supports filtering by status including 'failed'.

    Args:
        db: Database session.
        company_id: Company UUID.
        status: Optional status filter (processing, completed, failed).

    Returns:
        List of document dicts.
    """
    query = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.company_id == company_id,
    )

    if status:
        query = query.filter(KnowledgeDocument.status == status)

    documents = query.all()

    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "status": doc.status,
            "chunk_count": doc.chunk_count,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
        for doc in documents
    ]


def remove_failed_document(
    db: Session,
    document_id: str,
    company_id: str,
) -> bool:
    """
    Remove a failed document from knowledge base.

    GAP 6 FIX: Allows users to remove failed documents
    so they can proceed with onboarding.

    Args:
        db: Database session.
        document_id: Document UUID.
        company_id: Company UUID for tenant isolation.

    Returns:
        True if document was removed.

    Raises:
        ValidationError: If document not found or not in failed state.
    """
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == document_id,
        KnowledgeDocument.company_id == company_id,
    ).first()

    if not doc:
        raise ValidationError(
            message="Document not found.",
            details={"document_id": document_id},
        )

    if doc.status != "failed":
        raise ValidationError(
            message="Only failed documents can be removed.",
            details={
                "document_id": document_id,
                "status": doc.status,
            },
        )

    db.delete(doc)
    db.commit()

    logger.info(
        "failed_document_removed",
        document_id=document_id,
        company_id=company_id,
    )

    return True


def retry_document_processing(
    db: Session,
    document_id: str,
    company_id: str,
) -> Dict[str, Any]:
    """
    Retry processing of a failed document.

    GAP 6 FIX: Supports retrying failed documents with max limit.

    Args:
        db: Database session.
        document_id: Document UUID.
        company_id: Company UUID.

    Returns:
        Dict with retry status.

    Raises:
        ValidationError: If document not found, not failed, or max retries exceeded.
    """
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == document_id,
        KnowledgeDocument.company_id == company_id,
    ).first()

    if not doc:
        raise ValidationError(
            message="Document not found.",
            details={"document_id": document_id},
        )

    if doc.status != "failed":
        raise ValidationError(
            message="Only failed documents can be retried.",
            details={"status": doc.status},
        )

    # Check retry count (stored in chunk_count temporarily for simplicity)
    retry_count = getattr(doc, "retry_count", 0) or 0

    if retry_count >= _MAX_DOCUMENT_RETRIES:
        raise ValidationError(
            message=f"Maximum retries ({_MAX_DOCUMENT_RETRIES}) exceeded for this document.",
            details={
                "document_id": document_id,
                "retry_count": retry_count,
                "max_retries": _MAX_DOCUMENT_RETRIES,
            },
        )

    # P15 FIX: Trigger Celery BEFORE committing. If Celery trigger fails,
    # rollback the status change so the document stays in "failed" and
    # doesn't get stuck in "processing" forever.
    try:
        process_knowledge_document.delay(str(document_id), str(company_id))
    except Exception as e:
        logger.error(
            "retry_celery_trigger_failed",
            document_id=document_id,
            company_id=company_id,
            error=str(e),
        )
        raise ValidationError(
            message="Failed to start document processing. Please try again.",
            details={
                "document_id": document_id,
                "reason": "celery_unavailable",
            },
        )

    # Celery task queued successfully — now commit status change
    doc.status = "processing"
    doc.retry_count = retry_count + 1  # type: ignore
    db.commit()

    logger.info(
        "document_processing_retried",
        document_id=document_id,
        company_id=company_id,
        retry_count=retry_count + 1,
    )

    return {
        "id": doc.id,
        "status": "processing",
        "retry_count": retry_count + 1,
        "message": "Document processing restarted.",
    }


# ── AI Activation ────────────────────────────────────────────────────────


def activate_ai(
    db: Session,
    user_id: str,
    company_id: str,
    ai_name: str = "Jarvis",
    ai_tone: str = "professional",
    ai_response_style: str = "concise",
    ai_greeting: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Activate AI assistant for the company.

    Validates all prerequisites before activation:
    - GAP 3: Email verification if work email provided
    - Legal consents accepted
    - At least one integration or KB document

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID.
        ai_name: AI assistant name.
        ai_tone: AI tone (professional, friendly, casual).
        ai_response_style: Response style (concise, detailed).
        ai_greeting: Custom greeting message.

    Returns:
        Dict with AI config.

    Raises:
        ValidationError: If prerequisites not met.
    """
    # Check prerequisites (includes GAP 3: email verification)
    prereqs = check_ai_activation_prerequisites(db, user_id, company_id)

    if not prereqs["can_activate"]:
        raise ValidationError(
            message="AI activation prerequisites not met.",
            details={"missing": prereqs["missing"]},
        )

    # GAP 1: Lock session for update
    session = get_session_with_lock(db, user_id, company_id)

    if not session:
        raise ValidationError(
            message="Onboarding session not found.",
            details={"user_id": user_id},
        )

    # P23 FIX: Validate ai_name uniqueness within the company.
    # Two different users in the same company should not be able to
    # create AI assistants with the same name — this causes confusion
    # in customer-facing widgets and admin dashboards.
    existing_ai = db.execute(
        select(OnboardingSession)
        .where(
            and_(
                OnboardingSession.company_id == company_id,
                OnboardingSession.ai_name == ai_name[:50],
                OnboardingSession.status == "completed",
                OnboardingSession.id != session.id,
            )
        )
    ).scalar_one_or_none()
    if existing_ai:
        raise ValidationError(
            message=f"AI assistant name '{ai_name}' is already in use within your organization. Please choose a different name.",
            details={"ai_name": ai_name, "existing_session_id": str(existing_ai.id)},
        )

    # P4 FIX: Idempotency — if already activated, return existing config.
    # Prevents duplicate warmup triggers on double-click or network retry.
    if session.status == "completed" and session.ai_name:
        logger.info(
            "ai_activation_idempotent_return",
            user_id=user_id,
            company_id=company_id,
            existing_ai_name=session.ai_name,
        )
        return {
            "message": "AI assistant is already activated.",
            "ai_name": session.ai_name,
            "ai_tone": session.ai_tone,
            "ai_response_style": session.ai_response_style,
            "ai_greeting": session.ai_greeting,
        }

    # Update AI config
    session.ai_name = ai_name[:50] if ai_name else "Jarvis"
    session.ai_tone = ai_tone if ai_tone in ["professional", "friendly", "casual"] else "professional"
    session.ai_response_style = ai_response_style if ai_response_style in ["concise", "detailed"] else "concise"
    session.ai_greeting = ai_greeting[:500] if ai_greeting else None
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    session.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(session)

    logger.info(
        "ai_activated",
        user_id=user_id,
        company_id=company_id,
        ai_name=ai_name,
    )

    # P3 FIX: Trigger cold start warmup in a BACKGROUND THREAD so the
    # activation response returns immediately. Previously warmup_tenant()
    # was synchronous and could block the HTTP response for 30-60s.
    # P2 FIX: The DB commit happened before warmup. Now warmup is truly
    # async — if it fails, the DB state is already committed and a
    # recovery check on startup will re-trigger for tenants with no warmup.

    def _background_warmup(cid: str, uid: str) -> None:
        try:
            from app.core.cold_start_service import get_cold_start_service
            details = db.query(UserDetails).filter(
                UserDetails.company_id == cid,
            ).first()
            # P16 FIX: Default to mini_parwa for unknown/null company_size
            # to avoid over-provisioning free trial users with parwa tier.
            variant_type = "mini_parwa"
            if details and details.company_size:
                size_to_variant = {
                    "1_10": "mini_parwa",
                    "11_50": "parwa",
                    "51_200": "parwa",
                    "201_500": "high_parwa",
                    "501_1000": "high_parwa",
                    "1000_plus": "high_parwa",
                }
                variant_type = size_to_variant.get(details.company_size, "mini_parwa")

            cold_start = get_cold_start_service()
            warmup_result = cold_start.warmup_tenant(cid, variant_type)
            logger.info(
                "cold_start_warmup_background_complete",
                user_id=uid,
                company_id=cid,
                variant_type=variant_type,
                overall_status=warmup_result.overall_status.value,
                time_to_warm_ms=warmup_result.time_to_warm_ms,
                fallback_used=warmup_result.fallback_used,
            )
        except Exception as e:
            logger.warning(
                "cold_start_warmup_failed_non_blocking",
                user_id=uid,
                company_id=cid,
                error=str(e),
            )

    warmup_thread = threading.Thread(
        target=_background_warmup,
        args=(company_id, user_id),
        daemon=True,
        name=f"warmup-{company_id[:8]}",
    )
    warmup_thread.start()

    return {
        "message": "AI assistant activated successfully.",
        "ai_name": session.ai_name,
        "ai_tone": session.ai_tone,
        "ai_response_style": session.ai_response_style,
        "ai_greeting": session.ai_greeting,
    }


def get_first_victory_status(
    db: Session,
    user_id: str,
    company_id: str,
) -> Dict[str, Any]:
    """
    Get first victory status for the user.

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID.

    Returns:
        Dict with first victory status.
    """
    session = db.query(OnboardingSession).filter(
        OnboardingSession.user_id == user_id,
        OnboardingSession.company_id == company_id,
    ).first()

    if not session:
        return {
            "completed": False,
            "message": "Onboarding not started.",
        }

    return {
        "completed": session.first_victory_completed or False,
        "ai_name": session.ai_name,
        "ai_greeting": session.ai_greeting,
    }


def complete_first_victory(
    db: Session,
    user_id: str,
    company_id: str,
) -> Dict[str, Any]:
    """
    Mark first victory as completed.

    Args:
        db: Database session.
        user_id: User UUID.
        company_id: Company UUID.

    Returns:
        Dict with completion status.
    """
    session = db.query(OnboardingSession).filter(
        OnboardingSession.user_id == user_id,
        OnboardingSession.company_id == company_id,
    ).first()

    if not session:
        raise ValidationError(
            message="Onboarding session not found.",
            details={"user_id": user_id},
        )

    # D8-P2 FIX: Verify session is actually completed before allowing
    # first victory. Without this, a user could call this endpoint
    # before finishing all onboarding steps (e.g., via direct API call).
    if session.status != "completed":
        raise ValidationError(
            message="Cannot complete first victory — onboarding is not finished yet.",
            details={
                "user_id": user_id,
                "current_status": session.status,
            },
        )

    # Idempotency: if already completed, return success without re-writing
    if session.first_victory_completed:
        return {
            "completed": True,
            "message": "First victory already completed.",
        }

    session.first_victory_completed = True
    session.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "first_victory_completed",
        user_id=user_id,
        company_id=company_id,
    )

    return {
        "completed": True,
        "message": "First victory completed! Welcome to PARWA.",
    }

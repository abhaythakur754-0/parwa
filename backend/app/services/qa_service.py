"""
AI QA service — the Report Card engine.

Layer 1 (grading): pure code, $0. CLARA 5-stage checklist + hard
evidence (repeat question, angry words). Runs inline in the pipeline
hook — milliseconds, zero LLM calls.

Layer 2 (officer): ONE cheap LLM review for flagged conversations
only (typically ~10%), capped daily, scheduled in the background so
the customer never waits. Uncertain verdicts are marked, never
silently dropped.

Every row is stamped with company_id (BC-001) — the locked drawer.
The hook in jarvis_cc_service.send_cc_message is fail-open: if
anything here raises, the conversation itself is untouched.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import litellm
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logger import get_logger
from database.models.jarvis import JarvisMessage
from database.models.qa_score import QAReportCard

logger = get_logger("qa_service")

# Held references so fire-and-forget officer tasks are not garbage collected
_officer_tasks: set = set()

ANGRY_WORDS = (
    "angry", "furious", "unacceptable", "ridiculous", "worst",
    "disgusted", "scam", "sue", "lawyer", "trade commission",
)

_OFFICER_START_DELAY_SECONDS = 3.0  # let the request transaction commit first

OFFICER_SYSTEM_PROMPT = (
    "You are a strict but fair customer-support QA officer. You review ONE AI reply "
    "against the customer's question and a code checklist's findings. "
    "Reply with ONLY a JSON object, no other text: "
    '{"verdict": "confirm|correct|fail", "score": <0-100 integer>, '
    '"note": "<one sentence why>"} . '
    'Meaning: "confirm" = the reply served the customer fine. '
    '"correct" = minor issues, name them in the note. '
    '"fail" = the reply would mislead or hurt the customer or the business.'
)


def _json_or(default: Any, raw: Optional[str]) -> Any:
    try:
        return json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default


def _collect_evidence(
    db: Session,
    conversation_id: str,
    user_message: str,
) -> List[str]:
    """Hard evidence, pure code, $0. Never guesses — only records facts."""
    evidence: List[str] = []
    text = (user_message or "").lower()

    if any(word in text for word in ANGRY_WORDS):
        evidence.append("angry_wording")

    # Same question asked again in this conversation = we likely failed once
    try:
        repeat_count = (
            db.query(JarvisMessage)
            .filter(
                JarvisMessage.session_id == conversation_id,
                JarvisMessage.role == "user",
                JarvisMessage.content == user_message,
            )
            .count()
        )
        if repeat_count >= 2:
            evidence.append("repeat_question")
    except Exception as exc:  # evidence is best-effort, never fatal
        logger.warning("qa_evidence_repeat_check_failed: %s", exc)

    return evidence


async def grade_and_schedule_review(
    db: Session,
    company_id: str,
    conversation_id: str,
    channel: str,
    user_message: str,
    ai_response: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[QAReportCard]:
    """Layer 1: grade this conversation now ($0, inline, milliseconds).

    Layer 2: if flagged, schedule ONE background officer review.
    Called from the Step 13 hook — exceptions must be caught THERE
    (fail-open); this function may raise, the hook does not propagate.
    """
    settings = get_settings()
    if not settings.QA_ENABLED:
        return None

    # ── Layer 1: CLARA checklist (pure code) ──
    from app.core.clara_quality_gate import CLARAQualityGate

    clara = CLARAQualityGate()
    result = await clara.evaluate(
        response=ai_response or "",
        query=user_message or "",
        company_id=company_id,
    )

    score = int(round((result.overall_score or 0.0) * 100))
    evidence = _collect_evidence(db, conversation_id, user_message)

    flag_reasons: List[str] = []
    for stage in result.stages:
        # timeout_pass means the stage never finished — that is suspicion,
        # not innocence (the brief: when in doubt, flag)
        if stage.result.value in ("fail", "error", "timeout_pass"):
            flag_reasons.append(stage.stage.value)
    flag_reasons.extend(evidence)
    flagged = bool(flag_reasons)

    row = QAReportCard(
        company_id=company_id,
        conversation_id=conversation_id,
        channel=channel or "chat",
        overall_pass=result.overall_pass,
        score=score,
        checklist_json=json.dumps({
            s.stage.value: {"result": s.result.value, "score": s.score}
            for s in result.stages
        }),
        evidence_json=json.dumps(evidence),
        question_excerpt=(user_message or "")[:500],
        flagged=flagged,
        flag_reasons_json=json.dumps(flag_reasons),
        officer_status="pending" if flagged else "none",
    )
    db.add(row)
    db.flush()

    logger.info(
        "qa_graded company=%s conv=%s score=%d flagged=%s reasons=%s",
        company_id, conversation_id, score, flagged, flag_reasons,
    )

    # ── Layer 2: background officer (customer never waits) ──
    if flagged:
        task = asyncio.create_task(
            _officer_review_task(
                report_id=row.id,
                company_id=company_id,
                user_message=user_message or "",
                ai_response=ai_response or "",
                flag_reasons=flag_reasons,
            )
        )
        _officer_tasks.add(task)
        task.add_done_callback(_officer_tasks.discard)

    return row


def _officer_budget_ok(db: Session) -> tuple[bool, int]:
    """Count today's officer reviews against the daily cap.

    Zero new infrastructure — the QA table counts itself.
    """
    settings = get_settings()
    day_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    used = (
        db.query(QAReportCard)
        .filter(
            QAReportCard.officer_status == "reviewed",
            QAReportCard.created_at >= day_start,
        )
        .count()
    )
    return used < settings.QA_OFFICER_DAILY_CAP, used


async def _officer_review_task(
    report_id: str,
    company_id: str,
    user_message: str,
    ai_response: str,
    flag_reasons: List[str],
) -> None:
    """Layer 2: one LLM double-check on a flagged row. Fail-safe:
    any error leaves the row visibly marked (error/capped), never silent."""
    await asyncio.sleep(_OFFICER_START_DELAY_SECONDS)
    from database.base import get_db_context

    try:
        with get_db_context() as db:
            row = (
                db.query(QAReportCard)
                .filter_by(id=report_id, company_id=company_id)
                .first()
            )
            if row is None or row.officer_status != "pending":
                return

            settings = get_settings()
            budget_ok, used = _officer_budget_ok(db)
            if not budget_ok:
                row.officer_status = "capped"
                row.officer_notes = f"daily cap reached ({used} today)"
                db.commit()
                logger.info("qa_officer_capped report=%s used=%d", report_id, used)
                return

            verdict, o_score, note, model_used = await _ask_officer(
                user_message, ai_response, flag_reasons, settings,
            )
            row.officer_status = "reviewed"
            row.officer_verdict = verdict
            row.officer_score = o_score
            row.officer_notes = note
            row.evidence_json = json.dumps(
                _json_or([], row.evidence_json) + [f"model:{model_used}"]
            )
            db.commit()
            logger.info(
                "qa_officer_reviewed report=%s verdict=%s score=%s",
                report_id, verdict, o_score,
            )
    except Exception as exc:
        logger.warning("qa_officer_failed report=%s: %s", report_id, exc)
        try:
            with get_db_context() as db:
                row = db.query(QAReportCard).filter_by(id=report_id).first()
                if row is not None and row.officer_status == "pending":
                    row.officer_status = "error"
                    row.officer_notes = str(exc)[:200]
                    db.commit()
        except Exception:
            pass


def _parse_officer_json(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        verdict = data.get("verdict")
        if verdict not in ("confirm", "correct", "fail"):
            return None
        return {
            "verdict": verdict,
            "score": max(0, min(100, int(data.get("score", 0)))),
            "note": str(data.get("note", ""))[:300],
        }
    except (ValueError, TypeError):
        return None


async def _ask_officer(
    user_message: str,
    ai_response: str,
    flag_reasons: List[str],
    settings: Any,
    model_override: Optional[str] = None,
) -> tuple[str, int, str, str]:
    """One officer LLM call (escalates to the heavy model on a 'fail')."""
    model = model_override or settings.QA_OFFICER_MODEL or settings.AI_LIGHT_MODEL
    prompt = (
        f"Customer asked:\n{user_message[:1500]}\n\n"
        f"AI replied:\n{ai_response[:1500]}\n\n"
        f"Checklist flags: {', '.join(flag_reasons) or 'none'}\n\n"
        "Give your verdict as the JSON object."
    )
    resp = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": OFFICER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=200,
        temperature=0.0,
        timeout=20,
    )
    text = resp["choices"][0]["message"]["content"] or ""
    parsed = _parse_officer_json(text)
    if parsed is None:
        # Never silently pass — mark it, per the approved design
        raise ValueError(f"officer verdict unparseable: {text[:120]}")

    if parsed["verdict"] == "fail" and model_override is None:
        escalation = (
            settings.QA_OFFICER_ESCALATION_MODEL or settings.AI_HEAVY_MODEL
        )
        try:
            e_verdict, e_score, e_note, _ = await _ask_officer(
                user_message, ai_response, flag_reasons, settings,
                model_override=escalation,
            )
            parsed = {"verdict": e_verdict, "score": e_score, "note": e_note}
        except Exception as exc:
            # escalation failed → the light model's FAIL stands (fail-safe)
            logger.warning("qa_officer_escalation_failed: %s", exc)

    return parsed["verdict"], parsed["score"], parsed["note"], model


# ── Dashboard aggregations (company-locked, read-only) ──────────────


def get_qa_summary(db: Session, company_id: str, days: int = 30) -> Dict[str, Any]:
    """Everything the Report Card screen needs for one tenant."""
    settings = get_settings()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(QAReportCard)
        .filter(
            QAReportCard.company_id == company_id,
            QAReportCard.created_at >= since,
        )
        .all()
    )
    total = len(rows)
    scores = [r.score for r in rows if r.score is not None]
    flagged_rows = [r for r in rows if r.flagged]
    reviewed_rows = [r for r in rows if r.officer_status == "reviewed"]

    volume_by_day: Dict[str, int] = {}
    by_channel: Dict[str, int] = {}
    reason_counts: Dict[str, int] = {}
    for r in rows:
        day = r.created_at.strftime("%Y-%m-%d") if r.created_at else "unknown"
        volume_by_day[day] = volume_by_day.get(day, 0) + 1
        by_channel[r.channel or "unknown"] = by_channel.get(r.channel or "unknown", 0) + 1
        for reason in _json_or([], r.flag_reasons_json):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return {
        "days": days,
        "graded_total": total,
        "average_score": round(sum(scores) / len(scores), 1) if scores else None,
        "flagged_count": len(flagged_rows),
        "flagged_rate": round(100.0 * len(flagged_rows) / total, 1) if total else 0.0,
        "double_checks_ran": len(reviewed_rows),
        "daily_cap": settings.QA_OFFICER_DAILY_CAP,
        "grading_cost_usd": 0.0,  # Layer 1 is pure code — always $0
        "volume_by_day": volume_by_day,
        "by_channel": by_channel,
        "top_flag_reasons": sorted(
            reason_counts.items(), key=lambda kv: kv[1], reverse=True
        )[:10],
    }


def get_flagged_conversations(
    db: Session,
    company_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[Dict[str, Any]], int]:
    """Flagged conversations for the Problems panel — reasons included."""
    query = (
        db.query(QAReportCard)
        .filter(
            QAReportCard.company_id == company_id,
            QAReportCard.flagged.is_(True),
        )
        .order_by(QAReportCard.created_at.desc())
    )
    total = query.count()
    rows = query.offset(offset).limit(min(limit, 200)).all()
    return [
        {
            "id": r.id,
            "conversation_id": r.conversation_id,
            "channel": r.channel,
            "score": r.score,
            "question_excerpt": r.question_excerpt,
            "flag_reasons": _json_or([], r.flag_reasons_json),
            "evidence": _json_or([], r.evidence_json),
            "officer_status": r.officer_status,
            "officer_verdict": r.officer_verdict,
            "officer_notes": r.officer_notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ], total

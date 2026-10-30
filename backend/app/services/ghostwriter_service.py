"""
Ghostwriter service — turns a knowledge gap into a draft article.

Flow (approved design):
1. Client (or the QA Report Card's gaps panel) names a topic.
2. We gather THIS client's own evidence only (BC-001): recent flagged
   conversations matching the topic + their own KB document chunks.
3. ONE cheap LLM call writes the draft (on-demand — no background burn).
4. The draft lands with status "draft". NOTHING goes live by itself —
   approve/reject is an explicit human decision on the API.

Daily cap keeps the cost predictable. Every row is company-stamped.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import litellm
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logger import get_logger
from database.models.ghostwriter import GhostwriterDraft
from database.models.onboarding import DocumentChunk, KnowledgeDocument
from database.models.qa_score import QAReportCard

logger = get_logger("ghostwriter_service")

MAX_SAMPLE_QUESTIONS = 8
MAX_KB_CHUNKS = 8
MAX_CHUNK_CHARS = 600

GHOSTWRITER_SYSTEM_PROMPT = (
    "You are the SHOBH Ghostwriter. You draft ONE help-centre article that "
    "closes a repeated knowledge gap for a business. Rules: use ONLY the "
    "policy facts provided in the source material — never invent policy; if "
    "the sources do not cover something, say what is unknown instead of "
    "guessing. Plain, professional, helpful tone. "
    "Reply with ONLY a JSON object, no other text: "
    '{"title": "<article title>", "article_markdown": "<article in markdown>"}'
)


class GhostwriterDisabled(Exception):
    pass


class DraftCapReached(Exception):
    def __init__(self, used: int, cap: int):
        self.used = used
        self.cap = cap
        super().__init__(f"daily draft cap reached ({used}/{cap})")


def _topic_words(topic: str) -> List[str]:
    return [w for w in re.split(r"\W+", (topic or "").lower()) if len(w) > 3][:6]


def _gather_sample_questions(
    db: Session, company_id: str, topic: str,
) -> Tuple[List[str], int]:
    """Recent flagged questions of THIS company that match the topic."""
    words = _topic_words(topic)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        db.query(QAReportCard)
        .filter(
            QAReportCard.company_id == company_id,
            QAReportCard.flagged.is_(True),
            QAReportCard.created_at >= since,
        )
        .order_by(QAReportCard.created_at.desc())
        .limit(50)
        .all()
    )
    samples: List[str] = []
    for r in rows:
        text = (r.question_excerpt or "").lower()
        if words and not any(w in text for w in words):
            continue
        if r.question_excerpt and r.question_excerpt not in samples:
            samples.append(r.question_excerpt)
        if len(samples) >= MAX_SAMPLE_QUESTIONS:
            break
    return samples, len(rows)


def _gather_kb_sources(
    db: Session, company_id: str, topic: str,
) -> Tuple[List[Dict[str, str]], str]:
    """This company's own KB chunks, keyword-matched to the topic."""
    words = _topic_words(topic)
    chunks = (
        db.query(DocumentChunk, KnowledgeDocument.filename)
        .join(
            KnowledgeDocument,
            DocumentChunk.document_id == KnowledgeDocument.id,
        )
        .filter(
            DocumentChunk.company_id == company_id,
            KnowledgeDocument.status == "completed",
        )
        .order_by(DocumentChunk.created_at.desc())
        .limit(40)
        .all()
    )
    scored: List[Tuple[int, str, str]] = []
    for chunk, filename in chunks:
        content = (chunk.content or "")[:MAX_CHUNK_CHARS]
        hits = sum(1 for w in words if w in content.lower())
        scored.append((hits, content, filename or "unknown"))
    scored.sort(key=lambda t: t[0], reverse=True)

    sources: List[Dict[str, str]] = []
    materials: List[str] = []
    seen_docs: set = set()
    for hits, content, filename in scored[:MAX_KB_CHUNKS]:
        materials.append(f"[source: {filename}]\n{content}")
        if filename not in seen_docs:
            seen_docs.add(filename)
            sources.append({"document": filename})
    return sources, "\n\n".join(materials)


def _parse_draft_json(text: str) -> Optional[Dict[str, str]]:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        title = str(data.get("title", "")).strip()
        article = str(data.get("article_markdown", "")).strip()
        if not title or not article:
            return None
        return {"title": title[:255], "article_markdown": article}
    except (ValueError, TypeError):
        return None


async def create_draft_from_gap(
    db: Session, company_id: str, topic: str,
) -> GhostwriterDraft:
    """Draft an article for `topic` from this company's own material.

    Raises GhostwriterDisabled / DraftCapReached; the API maps them.
    """
    settings = get_settings()
    if not settings.GHOSTWRITER_ENABLED:
        raise GhostwriterDisabled("ghostwriter is disabled by config")

    topic = (topic or "").strip()
    if not topic:
        raise ValueError("topic is required")

    # ── Daily cap (the drafts table counts itself — zero new infra) ──
    day_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    used = (
        db.query(GhostwriterDraft)
        .filter(GhostwriterDraft.created_at >= day_start)
        .count()
    )
    if used >= settings.GHOSTWRITER_DAILY_CAP:
        raise DraftCapReached(used, settings.GHOSTWRITER_DAILY_CAP)

    # ── Evidence: this client's flagged questions + their KB chunks ──
    sample_questions, flagged_seen = _gather_sample_questions(db, company_id, topic)
    sources, kb_material = _gather_kb_sources(db, company_id, topic)

    model = settings.GHOSTWRITER_MODEL or settings.AI_LIGHT_MODEL
    user_prompt = (
        f"Knowledge gap topic: {topic}\n\n"
        f"Real customer questions that failed recently "
        f"({len(sample_questions)} of {flagged_seen} flagged):\n"
        + "\n".join(f"- {q}" for q in sample_questions or [topic])
        + "\n\nSource material from the client's own documents "
        "(the ONLY facts you may use):\n"
        + (kb_material or "(no documents matched — state clearly in the "
                           "article that policy details need confirmation)")
        + "\n\nWrite the JSON object with the title and the article."
    )

    resp = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": GHOSTWRITER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=900,
        temperature=0.2,
        timeout=45,
    )
    text = resp["choices"][0]["message"]["content"] or ""
    parsed = _parse_draft_json(text)
    if parsed is None:
        raise ValueError(f"ghostwriter output unparseable: {text[:120]}")

    draft = GhostwriterDraft(
        company_id=company_id,
        gap_topic=topic[:255],
        status="draft",  # NEVER anything else here — approval is human
        title=parsed["title"],
        content=parsed["article_markdown"],
        sources_json=json.dumps(sources),
        based_on_json=json.dumps({
            "flagged_count": flagged_seen,
            "sample_questions": sample_questions,
        }),
        model_used=model,
    )
    db.add(draft)
    db.flush()
    logger.info(
        "ghostwriter_draft_created company=%s topic=%s sources=%d",
        company_id, topic, len(sources),
    )
    return draft


def list_drafts(
    db: Session, company_id: str, limit: int = 50, offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    query = (
        db.query(GhostwriterDraft)
        .filter(GhostwriterDraft.company_id == company_id)
        .order_by(GhostwriterDraft.created_at.desc())
    )
    total = query.count()
    rows = query.offset(offset).limit(min(limit, 200)).all()
    return [
        {
            "id": r.id,
            "gap_topic": r.gap_topic,
            "status": r.status,
            "title": r.title,
            "content": r.content,
            "sources": json.loads(r.sources_json or "[]"),
            "based_on": json.loads(r.based_on_json or "{}"),
            "model_used": r.model_used,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        }
        for r in rows
    ], total


def set_draft_status(
    db: Session, company_id: str, draft_id: str, status: str,
) -> Optional[GhostwriterDraft]:
    """Approve or reject. The company_id filter IS the security — a client
    can only ever touch its own drafts."""
    if status not in ("approved", "rejected"):
        raise ValueError("status must be approved or rejected")
    draft = (
        db.query(GhostwriterDraft)
        .filter_by(id=draft_id, company_id=company_id)
        .first()
    )
    if draft is None:
        return None
    draft.status = status
    draft.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    logger.info(
        "ghostwriter_draft_%s company=%s draft=%s", status, company_id, draft_id,
    )
    return draft

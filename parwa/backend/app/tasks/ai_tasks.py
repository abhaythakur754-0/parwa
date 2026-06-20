"""
PARWA AI Tasks (Day 22, BC-004)

Celery tasks for AI operations:
- classify_ticket_task: Light classification via LLM gateway (queue: ai_light)
- generate_response_task: Heavy response generation via LLM gateway (queue: ai_heavy)
- score_confidence_task: Confidence scoring via LLM gateway (queue: ai_light)

CL-02 FIX: All three tasks now call the LLM gateway instead of
returning hardcoded stubs. If the LLM call fails, they fall back
to deterministic defaults (graceful degradation, BC-008).
"""

import json
import logging
from typing import List, Optional

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app

logger = logging.getLogger("parwa.tasks.ai")

# ── LLM Prompt Templates ──────────────────────────────────────────────

CLASSIFY_SYSTEM_PROMPT = """You are a support ticket classifier. Analyze the given ticket text and return a JSON object with exactly these fields:
- "priority": one of "low", "normal", "high", "urgent"
- "category": one of "general", "technical", "billing", "account", "feature_request", "bug_report"
- "sentiment": one of "positive", "neutral", "negative", "mixed"
- "confidence": a float between 0.0 and 1.0

Return ONLY the JSON object, no additional text."""

GENERATE_SYSTEM_PROMPT = """You are a customer support agent. Generate a professional, helpful response to the customer's message. Consider the conversation history and any provided context. Be concise but thorough. Return your response as plain text."""

SCORE_SYSTEM_PROMPT = """You are a response quality evaluator. Score the confidence of the given AI-generated response based on:
- Relevance to the original ticket
- Completeness of the answer
- Professional tone
- Accuracy of information

Return a JSON object with:
- "confidence": a float between 0.0 and 1.0
- "should_escalate": boolean, true if the response quality is too low to send

Return ONLY the JSON object, no additional text."""


# ── Helper ────────────────────────────────────────────────────────────

def _run_llm_sync(system_prompt: str, user_message: str, max_tokens: int = 300,
                   temperature: float = 0.3, technique_id: str = "ai_task"):
    """Run LLM gateway call synchronously (for Celery worker context).

    CL-02 FIX: Wraps the async LLM gateway call in an event loop
    so it can be used from synchronous Celery tasks.

    Returns:
        The LLM response text, or None if the call fails.
    """
    try:
        import asyncio
        from app.core.llm_gateway import llm_gateway

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                llm_gateway.generate(
                    technique_id=technique_id,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            )
            return response.text if response and response.text else None
        finally:
            loop.close()
    except Exception as e:
        logger.warning(
            "llm_call_failed",
            extra={
                "technique_id": technique_id,
                "error": str(e)[:200],
            },
        )
        return None


def _parse_json_response(text: str) -> Optional[dict]:
    """Parse a JSON response from LLM output, handling markdown fences."""
    if not text:
        return None
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove ```json and ``` wrappers
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


# ── Task: classify_ticket ─────────────────────────────────────────────

@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="ai_light",
    name="app.tasks.ai.classify_ticket",
    max_retries=3,
    soft_time_limit=30,
    time_limit=60,
    dedup_enabled=True,       # CL-03: Enable dedup for classification
    dedup_ttl_seconds=1800,   # 30 min dedup window
)
@with_company_id
def classify_ticket(self, company_id: str, ticket_id: str,
                    text: str = "") -> dict:
    """Classify a support ticket using AI.

    CL-02 FIX: Calls the LLM gateway to classify the ticket.
    Falls back to safe defaults if the LLM call fails (BC-008).
    """
    # Default fallback (BC-008: graceful degradation)
    fallback_result = {
        "status": "classified",
        "ticket_id": ticket_id,
        "priority": "normal",
        "category": "general",
        "sentiment": "neutral",
        "confidence": 0.5,
        "fallback_used": True,
    }

    try:
        # CL-02: Call LLM gateway instead of returning hardcoded stub
        llm_text = _run_llm_sync(
            system_prompt=CLASSIFY_SYSTEM_PROMPT,
            user_message=f"Classify this support ticket:\n\n{text[:2000]}",
            max_tokens=200,
            temperature=0.2,
            technique_id="classify_ticket",
        )

        if llm_text:
            parsed = _parse_json_response(llm_text)
            if parsed and "priority" in parsed and "category" in parsed:
                result = {
                    "status": "classified",
                    "ticket_id": ticket_id,
                    "priority": parsed.get("priority", "normal"),
                    "category": parsed.get("category", "general"),
                    "sentiment": parsed.get("sentiment", "neutral"),
                    "confidence": float(parsed.get("confidence", 0.7)),
                    "fallback_used": False,
                }
                logger.info(
                    "classify_ticket_success",
                    extra={
                        "task": self.name,
                        "company_id": company_id,
                        "ticket_id": ticket_id,
                        "category": result["category"],
                        "priority": result["priority"],
                        "confidence": result["confidence"],
                        "fallback_used": False,
                    },
                )
                return result

        # LLM call failed or returned invalid JSON — use fallback
        logger.warning(
            "classify_ticket_llm_fallback",
            extra={
                "task": self.name,
                "company_id": company_id,
                "ticket_id": ticket_id,
                "reason": "llm_call_failed_or_invalid_json",
            },
        )
        return fallback_result

    except Exception as exc:
        logger.error(
            "classify_ticket_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "ticket_id": ticket_id,
                "error": str(exc)[:200],
            },
        )
        raise


# ── Task: generate_response ────────────────────────────────────────────

@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="ai_heavy",
    name="app.tasks.ai.generate_response",
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
    dedup_enabled=True,       # CL-03: Enable dedup for response generation
    dedup_ttl_seconds=1800,
)
@with_company_id
def generate_response(self, company_id: str, ticket_id: str,
                      conversation_history: Optional[List[dict]] = None,
                      context: str = "") -> dict:
    """Generate AI response for a support ticket.

    CL-02 FIX: Calls the LLM gateway to generate a response.
    Falls back to an empty response with low confidence if LLM fails (BC-008).
    """
    # Default fallback (BC-008: graceful degradation)
    fallback_result = {
        "status": "generated",
        "ticket_id": ticket_id,
        "response_text": "",
        "confidence": 0.0,
        "fallback_used": True,
    }

    try:
        # Build user message from conversation history + context
        history_text = ""
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                history_text += f"[{role}]: {content}\n"

        user_message = ""
        if history_text:
            user_message += f"Conversation history:\n{history_text}\n"
        if context:
            user_message += f"Context: {context}\n"
        if not user_message:
            user_message = f"Generate a response for ticket {ticket_id}."

        # CL-02: Call LLM gateway instead of returning hardcoded stub
        llm_text = _run_llm_sync(
            system_prompt=GENERATE_SYSTEM_PROMPT,
            user_message=user_message[:4000],  # Limit input size
            max_tokens=500,
            temperature=0.5,
            technique_id="generate_response",
        )

        if llm_text and llm_text.strip():
            result = {
                "status": "generated",
                "ticket_id": ticket_id,
                "response_text": llm_text.strip(),
                "confidence": 0.8,
                "fallback_used": False,
            }
            logger.info(
                "generate_response_success",
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "ticket_id": ticket_id,
                    "response_length": len(llm_text.strip()),
                    "fallback_used": False,
                },
            )
            return result

        # LLM returned empty — use fallback
        logger.warning(
            "generate_response_llm_fallback",
            extra={
                "task": self.name,
                "company_id": company_id,
                "ticket_id": ticket_id,
                "reason": "llm_returned_empty",
            },
        )
        return fallback_result

    except Exception as exc:
        logger.error(
            "generate_response_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "ticket_id": ticket_id,
                "error": str(exc)[:200],
            },
        )
        raise


# ── Task: score_confidence ─────────────────────────────────────────────

@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="ai_light",
    name="app.tasks.ai.score_confidence",
    max_retries=2,
    soft_time_limit=15,
    time_limit=30,
    dedup_enabled=True,       # CL-03: Enable dedup for confidence scoring
    dedup_ttl_seconds=1800,
)
@with_company_id
def score_confidence(self, company_id: str, ticket_id: str,
                     response_text: str = "") -> dict:
    """Score confidence of an AI-generated response.

    CL-02 FIX: Calls the LLM gateway to score the response.
    Falls back to moderate confidence if LLM fails (BC-008).
    """
    # Default fallback (BC-008: graceful degradation)
    fallback_result = {
        "status": "scored",
        "ticket_id": ticket_id,
        "confidence": 0.5,
        "should_escalate": False,
        "fallback_used": True,
    }

    try:
        # CL-02: Call LLM gateway instead of returning hardcoded stub
        llm_text = _run_llm_sync(
            system_prompt=SCORE_SYSTEM_PROMPT,
            user_message=f"Score this AI response (ticket {ticket_id}):\n\n{response_text[:2000]}",
            max_tokens=100,
            temperature=0.1,
            technique_id="score_confidence",
        )

        if llm_text:
            parsed = _parse_json_response(llm_text)
            if parsed and "confidence" in parsed:
                result = {
                    "status": "scored",
                    "ticket_id": ticket_id,
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "should_escalate": bool(parsed.get("should_escalate", False)),
                    "fallback_used": False,
                }
                logger.info(
                    "score_confidence_success",
                    extra={
                        "task": self.name,
                        "company_id": company_id,
                        "ticket_id": ticket_id,
                        "confidence": result["confidence"],
                        "should_escalate": result["should_escalate"],
                        "fallback_used": False,
                    },
                )
                return result

        # LLM call failed — use fallback
        logger.warning(
            "score_confidence_llm_fallback",
            extra={
                "task": self.name,
                "company_id": company_id,
                "ticket_id": ticket_id,
                "reason": "llm_call_failed_or_invalid_json",
            },
        )
        return fallback_result

    except Exception as exc:
        logger.error(
            "score_confidence_failed",
            extra={
                "task": self.name,
                "company_id": company_id,
                "ticket_id": ticket_id,
                "error": str(exc)[:200],
            },
        )
        raise

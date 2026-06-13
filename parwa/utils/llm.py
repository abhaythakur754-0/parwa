"""LLM client utilities for PARWA nodes.

Supports FOUR backends (priority order):
1. ZAI SDK (PRIMARY — highest TPM, best throughput, works globally)
2. Google Gemini (fallback 1) — direct HTTP calls, only works in supported regions (US/EU)
3. NVIDIA API (fallback 2) — DeepSeek-V4-Pro via OpenAI-compatible client, 40 req/min
4. MockLLM (last resort) — deterministic responses for testing without any LLM

Production features:
- ZAI SDK as primary backend (works everywhere, no region restrictions)
- Direct HTTP calls to Google AI as fallback (region-restricted)
- Automatic failover: Light → Medium → Heavy tier chain
- Retry with exponential backoff on LLM failures (sync + async)
- Rate limiting to prevent API overload (sync + async)
- Circuit breaker to fail fast when LLM service is down
- TurboQuant token budget checking before LLM calls
- Prompt injection sanitization
- Async support for concurrent ticket processing
- Structured logging for all LLM calls
- Phase 4: Smart Router — selects the right LLM model based on task complexity
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError

from parwa.utils.rate_limiter import get_llm_rate_limiter
from parwa.utils.retry import retry_with_backoff, async_retry_with_backoff

logger = logging.getLogger("parwa.llm")

# ─── Configuration ─────────────────────────────────────────────────────────────

# Mock mode: when True, returns deterministic responses from MockLLM
# Set PARWA_MOCK_MODE=true to use mock mode (for testing without LLM)
MOCK_MODE = os.getenv("PARWA_MOCK_MODE", "false").lower() == "true"

# NVIDIA API Configuration (PRIMARY — 40 req/min, Llama-3.1-8B + DeepSeek-V4-Pro)
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "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")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
NVIDIA_MODEL_HEAVY = os.getenv("NVIDIA_MODEL_HEAVY", "deepseek-ai/deepseek-v4-pro")
NVIDIA_RATE_LIMIT_SECONDS = float(os.getenv("NVIDIA_RATE_LIMIT_SECONDS", "1.5"))  # 40/min, 1.5s between calls for TPM optimization
_nvidia_disabled = False  # Auto-disabled on repeated failures

# Google AI Configuration (fallback — region-restricted, only works in US/EU)
GOOGLE_AI_KEY = os.getenv("GOOGLE_AI_KEY", "AIzaSyATHbcolmlaNufj6ZHR6tebMmlqqcmCsEs")
GOOGLE_AI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Track if Google AI is available (disabled if region not supported)
_google_ai_disabled = False


def is_real_llm_active() -> bool:
    """Check if real LLM APIs are available (not in mock mode)."""
    return not MOCK_MODE


# ─── TurboQuant Token Tracking Helpers ─────────────────────────────────────────

_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text length (rough approximation)."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _check_token_budget(
    node_name: str, variant: str, estimated_tokens: int,
) -> bool:
    """Check if the node has enough token budget remaining.

    Normalizes UPPERCASE node names to lowercase for budget lookup.
    """
    try:
        from parwa.turboquant.token_budget import get_node_budget
        budget_key = node_name.lower() if node_name else node_name
        budget = get_node_budget(budget_key, variant)
        if not budget.can_spend(estimated_tokens):
            logger.warning(
                "token_budget: node=%s over budget (remaining=%d, need=%d, variant=%s) "
                "— skipping LLM call",
                node_name, budget.remaining, estimated_tokens, variant,
            )
            return False
        return True
    except Exception:
        return True


def _record_token_spend(
    node_name: str, variant: str, tokens_used: int,
) -> None:
    """Record token spend against the node's budget after a successful LLM call."""
    try:
        from parwa.turboquant.token_budget import get_node_budget
        budget = get_node_budget(node_name, variant)
        over = not budget.can_spend(tokens_used)
        budget.spend(tokens_used)
        if over:
            logger.warning(
                "token_budget: node=%s exceeded budget (used=%d, allocated=%d, variant=%s)",
                node_name, budget.used, budget.allocated, variant,
            )
    except Exception:
        pass


def _track_mock_usage(
    ticket_id: str, node_name: str, variant: str,
    prompt: str, response: str, model: str,
) -> None:
    """Track token usage for mock LLM calls (estimated tokens)."""
    try:
        from parwa.turboquant.token_tracker import get_token_tracker
        tracker = get_token_tracker()
        prompt_tokens = _estimate_tokens(prompt)
        completion_tokens = _estimate_tokens(response)
        tracker.record(
            ticket_id=ticket_id or "UNKNOWN",
            node_name=node_name or "unknown",
            variant=variant or "parwa",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
        )
        _record_token_spend(node_name, variant, prompt_tokens + completion_tokens)
    except Exception:
        pass


def _track_response_usage(
    ticket_id: str, node_name: str, variant: str,
    response_text: str, model: str,
    prompt_tokens: int = 0, completion_tokens: int = 0,
) -> None:
    """Track token usage from LLM response. Supports real token counts from ZAI SDK or Google Gemini."""
    try:
        from parwa.turboquant.token_tracker import get_token_tracker
        tracker = get_token_tracker()

        # Use real token counts if available, otherwise estimate
        if prompt_tokens == 0 and completion_tokens == 0:
            prompt_tokens = 50
            completion_tokens = _estimate_tokens(response_text)

        tracker.record(
            ticket_id=ticket_id or "UNKNOWN",
            node_name=node_name or "unknown",
            variant=variant or "parwa",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
        )
        _record_token_spend(node_name, variant, prompt_tokens + completion_tokens)
    except Exception:
        pass


# ─── ZAI SDK Direct Call (subprocess) — PRIMARY BACKEND ────────────────────────

# System prompts per node — tells the AI what structured output format to use
_NODE_SYSTEM_PROMPTS = {
    "INTENT_CLASSIFIER": (
        "Classify this customer message into ONE intent: "
        "account_modification, billing_issue, cancellation, complaint, "
        "escalation, faq_question, general_inquiry, order_status, "
        "refund_request, technical_support. "
        "Reply with ONLY: intent|confidence (e.g. refund_request|0.95). "
        "Examples: 'Charged twice' → refund_request|0.97, 'Where is my order' → order_status|0.95, "
        "'App keeps crashing' → technical_support|0.92, 'Update my email' → account_modification|0.90, "
        "'What is your return policy' → faq_question|0.91, 'Worst service ever' → complaint|0.88, "
        "'Speak to a manager' → escalation|0.94, 'Wrong invoice amount' → billing_issue|0.91, "
        "'I want to cancel' → cancellation|0.93, 'Contact my lawyer' → escalation|0.96"
    ),
    "SENTIMENT_ANALYZER": (
        "Analyze the sentiment of this customer message. "
        "Reply with ONLY: sentiment|urgency where sentiment is one of: "
        "angry, frustrated, happy, neutral and urgency is 0.0-1.0. "
        "Examples: 'I will sue you' → angry|0.95, 'This is ridiculous' → frustrated|0.75, "
        "'Thank you so much' → happy|0.10, 'When will my order arrive' → neutral|0.30, "
        "'I am absolutely disgusted' → angry|0.90, 'Disappointed with delay' → frustrated|0.60"
    ),
    "ESCALATION_DECISION": (
        "Should this ticket be escalated to a human agent? "
        "Reply with ONLY: true|reason or false|. "
        "Reasons: legal_threat, high_urgency, complex_technical, vip_customer, "
        "angry_customer_with_critical_issue, customer_requested_escalation. "
        "Examples: 'I will contact my attorney' → true|legal_threat, "
        "'This is the third time I am reaching out' → true|high_urgency, "
        "'Where is my order' → false|, 'Refund my money now' → false|"
    ),
    "FAQ_MATCHER": "Does this message match any FAQ? Reply with ONLY: faq_id|relevance_score|content or no_match|0.00| where relevance is 0.0-1.0.",
    "KB_RETRIEVER": "Retrieve relevant knowledge base information for this query. Provide a helpful, factual answer based on common customer support policies.",
    "INTEGRATION_LOOKUP": 'Look up CRM data. Reply with JSON: {"order_id":"ORD-XXXX","status":"...","charges":[{"amount":0,"date":"..."}],"customer":{"name":"...","tier":"..."}}',
    "REASONING_ENGINE": "Think step-by-step about this customer issue. Provide a clear reasoning chain ending with: Conclusion: <your conclusion>",
    "REVERSE_THINKER": 'Work backward from the desired outcome. Start with "Goal: <outcome>" then trace back each requirement. End with "Validation: PASSED" or "Validation: FAILED".',
    "TREE_OF_THOUGHTS": "Explore 3 different solution paths. Format: Path N: description (confidence: 0.XX, selected: true/false). Select the best path.",
    "STRATEGY_PLANNER": "Create a step-by-step strategy plan. Number each step. Be specific about actions and evidence needed.",
    "ACTION_PLANNER": "Plan specific actions needed. Format: action_type: description (risk: low/medium/high). Valid action types: send_reply, process_refund, cancel_order, modify_account, escalate_to_human, share_faq, share_policy, create_note",
    "PROACTIVE_CHECKER": "Suggest proactive follow-ups. Format: type: description (confidence: 0.XX)",
    "PREDICTION_ENGINE": "Predict what happens next with this customer. Include churn risk.",
    "QUALITY_SCORER": (
        "Score the quality of this AI customer service response on a scale of 0-100. "
        "Consider: accuracy (does it match the evidence?), completeness (are all issues addressed?), "
        "compliance (is it safe and policy-compliant?), empathy (is it appropriately toned?). "
        "Reply ONLY: score|issues (e.g. 65|incomplete_response,missing_evidence). "
        "Be HONEST — do not give high scores unless the response truly deserves it. "
        "A response that is generic or template-like should score below 70. "
        "A response with missing evidence or wrong data should score below 60. "
        "Only give 80+ if the response is accurate, complete, compliant, and empathetic."
    ),
    "PII_COMPLIANCE_GUARD": "Check for PII (SSN, credit card, email, phone, address). Reply ONLY: true|details or false|No PII detected",
    "RESPONSE_FORMATTER": (
        "Format a professional, empathetic customer service response based on the analysis. "
        "Be specific — include actual data from the evidence (order IDs, amounts, dates). "
        "Be empathetic — match tone to customer sentiment (apologize if frustrated, celebrate if happy). "
        "Be concise but thorough — don't be generic or template-like. "
        "If recommending an action, explain what will happen next and when. "
        "Do NOT output structured data like intent|confidence or JSON. Output natural human language only."
    ),
    "FEEDBACK_LOOP": "Analyze customer satisfaction. Reply: resolved: true/false, satisfaction: high/medium/low, improvement_areas",
}

# Per-node max_tokens for LLM calls
_NODE_MAX_TOKENS: dict[str, int] = {
    "INTENT_CLASSIFIER": 50,
    "SENTIMENT_ANALYZER": 50,
    "ESCALATION_DECISION": 50,
    "FAQ_MATCHER": 100,
    "KB_RETRIEVER": 300,
    "INTEGRATION_LOOKUP": 200,
    "REASONING_ENGINE": 500,
    "REVERSE_THINKER": 400,
    "TREE_OF_THOUGHTS": 400,
    "STRATEGY_PLANNER": 300,
    "ACTION_PLANNER": 200,
    "ACTION_EXECUTOR": 100,
    "ACTION_VERIFIER": 100,
    "PROACTIVE_CHECKER": 150,
    "PREDICTION_ENGINE": 150,
    "QUALITY_SCORER": 50,
    "PII_COMPLIANCE_GUARD": 50,
    "RESPONSE_FORMATTER": 500,
    "FEEDBACK_LOOP": 100,
    "FRAMEWORKBRAIN_COT": 400,
    "FRAMEWORKBRAIN_REACT": 400,
    "FRAMEWORKBRAIN_TOT": 400,
    "FRAMEWORKBRAIN_REFLEXION": 300,
}

# Path to parwa root
_PARWA_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── NVIDIA API Call (PRIMARY — fast, 40 req/min, native Python) ──────────────

def _call_nvidia(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = "",
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call NVIDIA API (DeepSeek-V4-Pro) via OpenAI-compatible client (sync, with rate limit).

    PRIMARY backend — fast native Python, no subprocess, 40 req/min.
    """
    import time as _time
    _time.sleep(NVIDIA_RATE_LIMIT_SECONDS)  # Rate limit: 40 req/min
    return _call_nvidia_no_wait(
        system_prompt, user_prompt,
        model=model, temperature=temperature, max_tokens=max_tokens,
    )


def _call_nvidia_no_wait(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = "",
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """NVIDIA API call without rate limit sleep (used by async wrapper).

    Uses meta/llama-3.1-8b-instruct as primary (fast, 0.2-1.5s/call),
    deepseek-ai/deepseek-v4-pro for heavy reasoning when explicitly requested.
    """
    global _nvidia_disabled
    if _nvidia_disabled:
        raise RuntimeError("NVIDIA API disabled (repeated failures)")

    from openai import OpenAI

    client = OpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=NVIDIA_API_KEY,
        max_retries=1,  # Don't waste time on retries
        timeout=30.0,
    )

    use_model = model or NVIDIA_MODEL
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": str(user_prompt)})

    resp = client.chat.completions.create(
        model=use_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    text = resp.choices[0].message.content or ""
    usage = resp.usage
    return {
        "content": text,
        "model": resp.model or use_model,
        "usage": {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        },
    }


async def _acall_nvidia(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = "",
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call NVIDIA API (DeepSeek-V4-Pro) via OpenAI-compatible client (async).

    PRIMARY backend — fast native Python, no subprocess, 40 req/min.
    Uses asyncio.to_thread to avoid blocking the event loop.
    """
    global _nvidia_disabled
    if _nvidia_disabled:
        raise RuntimeError("NVIDIA API disabled (repeated failures)")

    import asyncio
    await asyncio.sleep(NVIDIA_RATE_LIMIT_SECONDS)  # Rate limit: 40 req/min
    return await asyncio.to_thread(
        _call_nvidia_no_wait, system_prompt, user_prompt,
        model=model, temperature=temperature, max_tokens=max_tokens,
    )


# ─── ZAI SDK Call (FALLBACK — subprocess-based, slow) ─────────────────────────

def _call_zai_sdk(prompt: str, *, node_name: str = "", variant: str = "parwa",
                  complexity: str = "simple", temperature: float = 0.1,
                  max_tokens: int = 0) -> dict[str, Any]:
    """Call the ZAI SDK directly via Node.js subprocess (sync).

    PRIMARY backend — works globally including HK.
    Returns dict with: content, model, usage
    """
    system_prompt = _NODE_SYSTEM_PROMPTS.get(node_name, "Process this and give a clear, structured response.")
    if variant:
        system_prompt += f" [Variant: {variant}]"
    if complexity:
        system_prompt += f" [Complexity: {complexity}]"

    system_escaped = json.dumps(system_prompt)
    user_escaped = json.dumps(str(prompt))
    actual_max_tokens = max_tokens if max_tokens > 0 else _NODE_MAX_TOKENS.get(node_name, 500)

    node_script = f"""const ZAI = require("z-ai-web-dev-sdk").default;
async function main() {{
  const zai = await ZAI.create();
  const c = await zai.chat.completions.create({{
    messages: [
      {{role:"system", content:{system_escaped}}},
      {{role:"user", content:{user_escaped}}}
    ],
    temperature: {temperature},
    max_tokens: {actual_max_tokens},
  }});
  console.log(JSON.stringify({{
    content: c.choices[0].message.content,
    model: c.model || "zai",
    usage: c.usage || {{prompt_tokens:0,completion_tokens:0,total_tokens:0}}
  }}));
}}
main().catch(e => {{ console.error(JSON.stringify({{error:e.message}})); process.exit(1); }});
"""

    result = subprocess.run(
        ["node", "-e", node_script],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=_PARWA_ROOT,
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else f"Node exited with code {result.returncode}"
        raise RuntimeError(f"ZAI SDK call failed: {error_msg}")

    stdout = result.stdout.strip()
    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("{"):
            data = json.loads(line)
            if data.get("error"):
                raise RuntimeError(f"ZAI SDK error: {data['error']}")
            return data

    raise RuntimeError(f"ZAI SDK: no JSON output found in: {stdout[:200]}")


async def _acall_zai_sdk(prompt: str, *, node_name: str = "", variant: str = "parwa",
                         complexity: str = "simple", temperature: float = 0.1,
                         max_tokens: int = 0) -> dict[str, Any]:
    """Call the ZAI SDK via Node.js subprocess (async).

    PRIMARY backend — works globally including HK.
    """
    import asyncio

    system_prompt = _NODE_SYSTEM_PROMPTS.get(node_name, "Process this and give a clear, structured response.")
    if variant:
        system_prompt += f" [Variant: {variant}]"
    if complexity:
        system_prompt += f" [Complexity: {complexity}]"

    system_escaped = json.dumps(system_prompt)
    user_escaped = json.dumps(str(prompt))
    actual_max_tokens = max_tokens if max_tokens > 0 else _NODE_MAX_TOKENS.get(node_name, 500)

    node_script = f"""const ZAI = require("z-ai-web-dev-sdk").default;
async function main() {{
  const zai = await ZAI.create();
  const c = await zai.chat.completions.create({{
    messages: [
      {{role:"system", content:{system_escaped}}},
      {{role:"user", content:{user_escaped}}}
    ],
    temperature: {temperature},
    max_tokens: {actual_max_tokens},
  }});
  console.log(JSON.stringify({{
    content: c.choices[0].message.content,
    model: c.model || "zai",
    usage: c.usage || {{prompt_tokens:0,completion_tokens:0,total_tokens:0}}
  }}));
}}
main().catch(e => {{ console.error(JSON.stringify({{error:e.message}})); process.exit(1); }});
"""

    proc = await asyncio.create_subprocess_exec(
        "node", "-e", node_script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=_PARWA_ROOT,
    )

    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    stdout = stdout.decode().strip()

    if proc.returncode != 0:
        error_msg = stderr.decode().strip()[:200]
        raise RuntimeError(f"ZAI SDK call failed: {error_msg}")

    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("{"):
            data = json.loads(line)
            if data.get("error"):
                raise RuntimeError(f"ZAI SDK error: {data['error']}")
            return data

    raise RuntimeError(f"ZAI SDK: no JSON output in: {stdout[:200]}")


# ─── Google Gemini Direct Call — FALLBACK BACKEND ──────────────────────────────

def _call_google_gemini(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = "gemini-2.0-flash-lite",
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call Google Gemini via native HTTP API (sync).

    FALLBACK backend — only works in supported regions (US/EU etc.).
    Will auto-disable if region not supported (HK etc.).
    """
    global _google_ai_disabled
    if _google_ai_disabled:
        raise RuntimeError("Google AI disabled (region not supported)")

    url = GOOGLE_AI_URL.format(model=model) + f"?key={GOOGLE_AI_KEY}"

    system_instruction = None
    if system_prompt:
        system_instruction = {"parts": [{"text": system_prompt}]}

    contents = [{"role": "user", "parts": [{"text": str(user_prompt)}]}]

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_instruction:
        payload["systemInstruction"] = system_instruction

    data_bytes = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data_bytes, headers={"Content-Type": "application/json"})

    try:
        resp = urlopen(req, timeout=30)
    except URLError as e:
        if hasattr(e, 'code'):
            if e.code == 429:
                raise RuntimeError("Google Gemini rate limited (429)")
            elif e.code == 400:
                _google_ai_disabled = True
                raise RuntimeError("Google AI: region not supported — disabled permanently")
        raise

    resp_data = json.loads(resp.read().decode("utf-8"))

    content = ""
    candidates = resp_data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        content = "".join(p.get("text", "") for p in parts)

    usage_meta = resp_data.get("usageMetadata", {})
    usage = {
        "prompt_tokens": usage_meta.get("promptTokenCount", 0),
        "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
        "total_tokens": usage_meta.get("totalTokenCount", 0),
    }

    return {
        "content": content,
        "model": f"google/{model}",
        "usage": usage,
    }


async def _acall_google_gemini(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = "gemini-2.0-flash-lite",
    temperature: float = 0.1,
    max_tokens: int = 500,
) -> dict[str, Any]:
    """Call Google Gemini via native HTTP API (async).

    FALLBACK backend — only works in supported regions (US/EU etc.).
    """
    import asyncio
    import httpx

    global _google_ai_disabled
    if _google_ai_disabled:
        raise RuntimeError("Google AI disabled (region not supported)")

    url = GOOGLE_AI_URL.format(model=model) + f"?key={GOOGLE_AI_KEY}"

    system_instruction = None
    if system_prompt:
        system_instruction = {"parts": [{"text": system_prompt}]}

    contents = [{"role": "user", "parts": [{"text": str(user_prompt)}]}]

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_instruction:
        payload["systemInstruction"] = system_instruction

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload)

    if resp.status_code == 429:
        raise RuntimeError("Google Gemini rate limited (429)")
    elif resp.status_code == 400:
        error_msg = resp.text[:200]
        if "location" in error_msg.lower() or "region" in error_msg.lower():
            _google_ai_disabled = True
            raise RuntimeError("Google AI: region not supported — disabled permanently")
        raise RuntimeError(f"Google Gemini returned 400: {error_msg}")
    elif resp.status_code != 200:
        raise RuntimeError(f"Google Gemini returned {resp.status_code}: {resp.text[:300]}")

    resp_data = resp.json()

    content = ""
    candidates = resp_data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        content = "".join(p.get("text", "") for p in parts)

    usage_meta = resp_data.get("usageMetadata", {})
    usage = {
        "prompt_tokens": usage_meta.get("promptTokenCount", 0),
        "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
        "total_tokens": usage_meta.get("totalTokenCount", 0),
    }

    return {
        "content": content,
        "model": f"google/{model}",
        "usage": usage,
    }


# ─── Legacy ChatOpenAI (kept for backward compat, not actively used) ────────

try:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_openai import ChatOpenAI
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False

_llm_cache: dict[str, Any] = {}


def get_llm(model: str = "gpt-4o-mini", temperature: float = 0.1) -> Any:
    """Get or create a cached LLM instance (legacy — only used as last resort)."""
    if not _LANGCHAIN_AVAILABLE:
        return None
    cache_key = f"{model}_{temperature}"
    if cache_key not in _llm_cache:
        _llm_cache[cache_key] = ChatOpenAI(
            model=model, temperature=temperature, max_retries=2, timeout=30.0,
        )
    return _llm_cache[cache_key]


def clear_llm_cache() -> None:
    """Clear the LLM instance cache."""
    _llm_cache.clear()


# ─── Smart Router ──────────────────────────────────────────────────────────────

def smart_route_model(
    node_name: str,
    *,
    complexity: str = "simple",
    variant: str = "parwa",
) -> str:
    """Select the right LLM model based on node, complexity, and variant.

    When using ZAI SDK (primary), the model name is logged but the actual
    model selection is done by the zai SDK. The Smart Router still tracks
    which tier SHOULD be used for audit/logging purposes.
    """
    from parwa.config import get_model_for_node

    model = get_model_for_node(node_name, variant)
    logger.debug(
        "smart_router: node=%s variant=%s complexity=%s → %s",
        node_name, variant, complexity, model,
    )
    return model


def smart_route_all_models(
    node_name: str,
    *,
    complexity: str = "simple",
    variant: str = "parwa",
) -> list[str]:
    """Get the full fallback model chain for a node given a variant."""
    from parwa.config import get_all_models_for_node
    return get_all_models_for_node(node_name, variant)


# ─── High-Level LLM Invocation (SYNC) ─────────────────────────────────────────

@retry_with_backoff(max_retries=3, base_delay=1.0, retryable_exceptions=(ConnectionError, TimeoutError, OSError))
def invoke_llm(
    prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.1,
    *,
    node_name: str = "",
    ticket_id: str = "",
    variant: str = "parwa",
    complexity: str = "simple",
) -> str:
    """High-level sync LLM invocation with full production hardening.

    Uses NVIDIA API (PRIMARY — 40 RPM, TPM-optimized) → ZAI SDK (fallback 1) → Google Gemini (fallback 2) → real_llm APIs → MockLLM (last resort).

    Args:
        prompt: The prompt to send.
        model: The model name (overridden by Smart Router if node_name provided).
        temperature: Sampling temperature.
        node_name: Calling node name (for Smart Router + TurboQuant budget tracking).
        ticket_id: Current ticket ID (for TurboQuant tracking).
        variant: Current variant (for Smart Router + TurboQuant budget allocation).
        complexity: Ticket complexity (for Smart Router model selection).

    Returns:
        The LLM response as a string.
    """
    # Smart Router: determine which model/tier should be used
    if node_name:
        routed_model = smart_route_model(node_name, complexity=complexity, variant=variant)
        if routed_model != model:
            logger.debug("invoke_llm: Smart Router — node=%s model=%s→%s", node_name, model, routed_model)
            model = routed_model

    # Check token budget
    estimated = _estimate_tokens(prompt) + 200
    if not _check_token_budget(node_name, variant, estimated):
        return "Token budget exceeded. Using rule-based fallback."

    # ─── Try NVIDIA API (PRIMARY — 40 RPM, TPM-optimized, native Python) ───
    if not MOCK_MODE:
        try:
            system_prompt = _NODE_SYSTEM_PROMPTS.get(node_name, "Process this and give a clear, structured response.")
            if variant:
                system_prompt += f" [Variant: {variant}]"
            if complexity:
                system_prompt += f" [Complexity: {complexity}]"
            actual_max_tokens = _NODE_MAX_TOKENS.get(node_name, 500)
            result = _call_nvidia(
                system_prompt, prompt,
                model="", temperature=temperature,
                max_tokens=actual_max_tokens,
            )
            text = result.get("content", "")
            usage = result.get("usage", {})
            _track_response_usage(
                ticket_id, node_name, variant, text, model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
            logger.debug("invoke_llm [nvidia-primary]: node=%s response_len=%d", node_name, len(text))
            return text
        except Exception as exc:
            logger.warning("invoke_llm: NVIDIA API failed: %s — trying ZAI SDK", exc)

    # ─── Try ZAI SDK (fallback 1 — high TPM, subprocess-based) ───
    if not MOCK_MODE:
        try:
            result = _call_zai_sdk(
                prompt, node_name=node_name, variant=variant,
                complexity=complexity, temperature=temperature,
                max_tokens=0,  # Use node-specific defaults
            )
            text = result.get("content", "")
            usage = result.get("usage", {})
            _track_response_usage(
                ticket_id, node_name, variant, text, model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
            logger.debug("invoke_llm [zai-sdk-fallback]: node=%s response_len=%d", node_name, len(text))
            return text
        except Exception as exc:
            logger.warning("invoke_llm: ZAI SDK failed: %s — trying Google Gemini", exc)

    # ─── Try Google Gemini (fallback 2) ───
    if not MOCK_MODE:
        try:
            system_prompt = _NODE_SYSTEM_PROMPTS.get(node_name, "Process this and give a clear, structured response.")
            if variant:
                system_prompt += f" [Variant: {variant}]"
            if complexity:
                system_prompt += f" [Complexity: {complexity}]"
            actual_max_tokens = _NODE_MAX_TOKENS.get(node_name, 500)
            result = _call_google_gemini(
                system_prompt, prompt,
                model="gemini-2.0-flash-lite", temperature=temperature,
                max_tokens=actual_max_tokens,
            )
            text = result.get("content", "")
            usage = result.get("usage", {})
            _track_response_usage(
                ticket_id, node_name, variant, text, model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
            logger.debug("invoke_llm [google-gemini-fallback]: node=%s response_len=%d", node_name, len(text))
            return text
        except Exception as gemini_exc:
            logger.warning("invoke_llm: Google Gemini failed: %s — trying real LLM APIs", gemini_exc)
            # Try real_llm.py providers as final API fallback
            try:
                from parwa.utils.real_llm import call_llm_sync
                from parwa.config import get_all_models_for_node
                system_prompt = _NODE_SYSTEM_PROMPTS.get(node_name, "Process this and give a clear, structured response.")
                if variant:
                    system_prompt += f" [Variant: {variant}]"
                if complexity:
                    system_prompt += f" [Complexity: {complexity}]"
                actual_max_tokens = _NODE_MAX_TOKENS.get(node_name, 500)
                model_chain = get_all_models_for_node(node_name, variant)
                last_err = None
                for mdl in model_chain:
                    try:
                        result = call_llm_sync(
                            mdl, system_prompt, prompt,
                            temperature=temperature, max_tokens=actual_max_tokens,
                        )
                        break
                    except Exception as inner_exc:
                        logger.debug("invoke_llm failover: %s failed: %s", mdl, inner_exc)
                        last_err = inner_exc
                else:
                    raise RuntimeError(f"All API models failed. Last: {last_err}")
                text = result.get("content", "")
                usage = result.get("usage", {})
                _track_response_usage(
                    ticket_id, node_name, variant, text, model,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                )
                logger.debug("invoke_llm [real-api]: node=%s model=%s response_len=%d", node_name, result.get("model", "?"), len(text))
                return text
            except Exception as exc2:
                logger.warning("invoke_llm: All APIs failed: %s — falling back to MockLLM", exc2)

    # ─── Fallback: MockLLM ───
    mock = get_mock_llm()
    text = mock.invoke(prompt)
    _track_mock_usage(ticket_id, node_name, variant, prompt, text, model)
    return text


# ─── High-Level LLM Invocation (ASYNC) ────────────────────────────────────────

@async_retry_with_backoff(max_retries=3, base_delay=1.0, retryable_exceptions=(ConnectionError, TimeoutError, OSError))
async def ainvoke_llm(
    prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.1,
    *,
    node_name: str = "",
    ticket_id: str = "",
    variant: str = "parwa",
    complexity: str = "simple",
    max_tokens: int = 0,
) -> str:
    """High-level async LLM invocation with full production hardening.

    Uses NVIDIA API (PRIMARY — 40 RPM, TPM-optimized) → ZAI SDK (fallback 1) → Google Gemini (fallback 2) → real_llm APIs → MockLLM (last resort).
    """
    # Smart Router
    if node_name:
        routed_model = smart_route_model(node_name, complexity=complexity, variant=variant)
        if routed_model != model:
            model = routed_model

    # Check token budget
    estimated = _estimate_tokens(prompt) + 200
    if not _check_token_budget(node_name, variant, estimated):
        return "Token budget exceeded. Using rule-based fallback."

    # ─── Try NVIDIA API (PRIMARY — 40 RPM, TPM-optimized, native Python) ───
    if not MOCK_MODE:
        try:
            system_prompt = _NODE_SYSTEM_PROMPTS.get(node_name, "Process this and give a clear, structured response.")
            if variant:
                system_prompt += f" [Variant: {variant}]"
            if complexity:
                system_prompt += f" [Complexity: {complexity}]"
            actual_max_tokens = max_tokens if max_tokens > 0 else _NODE_MAX_TOKENS.get(node_name, 500)
            result = await _acall_nvidia(
                system_prompt, prompt,
                model="", temperature=temperature,
                max_tokens=actual_max_tokens,
            )
            text = result.get("content", "")
            usage = result.get("usage", {})
            _track_response_usage(
                ticket_id, node_name, variant, text, model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
            logger.debug("ainvoke_llm [nvidia-primary]: node=%s response_len=%d", node_name, len(text))
            return text
        except Exception as exc:
            logger.warning("ainvoke_llm: NVIDIA API failed: %s — trying ZAI SDK", exc)

    # ─── Try ZAI SDK (fallback 1 — high TPM, subprocess-based) ───
    if not MOCK_MODE:
        try:
            result = await _acall_zai_sdk(
                prompt, node_name=node_name, variant=variant,
                complexity=complexity, temperature=temperature,
                max_tokens=max_tokens,
            )
            text = result.get("content", "")
            usage = result.get("usage", {})
            _track_response_usage(
                ticket_id, node_name, variant, text, model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
            logger.debug("ainvoke_llm [zai-sdk-fallback]: node=%s response_len=%d", node_name, len(text))
            return text
        except Exception as exc:
            logger.warning("ainvoke_llm: ZAI SDK failed: %s — trying Google Gemini", exc)

    # ─── Try Google Gemini (fallback 2) ───
    if not MOCK_MODE:
        try:
            system_prompt = _NODE_SYSTEM_PROMPTS.get(node_name, "Process this and give a clear, structured response.")
            if variant:
                system_prompt += f" [Variant: {variant}]"
            if complexity:
                system_prompt += f" [Complexity: {complexity}]"
            actual_max_tokens = max_tokens if max_tokens > 0 else _NODE_MAX_TOKENS.get(node_name, 500)
            result = await _acall_google_gemini(
                system_prompt, prompt,
                model="gemini-2.0-flash-lite", temperature=temperature,
                max_tokens=actual_max_tokens,
            )
            text = result.get("content", "")
            usage = result.get("usage", {})
            _track_response_usage(
                ticket_id, node_name, variant, text, model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
            logger.debug("ainvoke_llm [google-gemini-fallback]: node=%s response_len=%d", node_name, len(text))
            return text
        except Exception as gemini_exc:
            logger.warning("ainvoke_llm: Google Gemini failed: %s — trying real LLM APIs", gemini_exc)
            # Try real_llm.py providers as final API fallback
            try:
                from parwa.utils.real_llm import call_llm_with_failover
                from parwa.config import get_all_models_for_node
                system_prompt = _NODE_SYSTEM_PROMPTS.get(node_name, "Process this and give a clear, structured response.")
                if variant:
                    system_prompt += f" [Variant: {variant}]"
                if complexity:
                    system_prompt += f" [Complexity: {complexity}]"
                actual_max_tokens = max_tokens if max_tokens > 0 else _NODE_MAX_TOKENS.get(node_name, 500)
                model_chain = get_all_models_for_node(node_name, variant)
                result = await call_llm_with_failover(
                    model_chain, system_prompt, prompt,
                    temperature=temperature, max_tokens=actual_max_tokens,
                )
                text = result.get("content", "")
                usage = result.get("usage", {})
                _track_response_usage(
                    ticket_id, node_name, variant, text, model,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                )
                logger.debug("ainvoke_llm [real-api]: node=%s model=%s response_len=%d", node_name, result.get("model", "?"), len(text))
                return text
            except Exception as exc2:
                logger.warning("ainvoke_llm: All APIs failed: %s — falling back to MockLLM", exc2)

    # ─── Fallback: MockLLM ───
    mock = get_mock_llm()
    text = mock.invoke(prompt)
    _track_mock_usage(ticket_id, node_name, variant, prompt, text, model)
    return text


# ─── MockLLM ──────────────────────────────────────────────────────────────────

class MockLLM:
    """Mock LLM for testing without API calls.

    Returns deterministic responses based on the input prompt.
    Works in both sync and async contexts.
    """

    @staticmethod
    def _extract_user_message(prompt_str: str) -> str:
        """Extract the user message from a prompt that may contain system instructions."""
        begin_marker = "--- BEGIN CUSTOMER MESSAGE ---"
        end_marker = "--- END CUSTOMER MESSAGE ---"
        begin_idx = prompt_str.find(begin_marker)
        if begin_idx >= 0:
            end_idx = prompt_str.find(end_marker, begin_idx)
            if end_idx >= 0:
                return prompt_str[begin_idx + len(begin_marker):end_idx].strip()
            return prompt_str[begin_idx + len(begin_marker):].strip()

        for marker in ["User: ", "Customer Message: ", "\n\nUser: ", "\n\nCustomer Message: "]:
            idx = prompt_str.rfind(marker)
            if idx >= 0:
                return prompt_str[idx + len(marker):]

        return prompt_str

    def invoke(self, prompt: str | list, **kwargs: Any) -> str:
        """Return a mock response based on keywords in the prompt."""
        if isinstance(prompt, list):
            prompt_str = str(prompt)
        else:
            prompt_str = str(prompt)

        prompt_lower = prompt_str.lower()
        user_msg = self._extract_user_message(prompt_str).lower()

        # Intent classification
        if "intent" in prompt_lower and "classify" in prompt_lower:
            if "cancel" in user_msg or "terminate" in user_msg or "stop order" in user_msg:
                return "cancellation|0.92"
            if "where is my order" in user_msg or "order status" in user_msg or "tracking" in user_msg or "shipped" in user_msg or "delivery" in user_msg:
                return "order_status|0.95"
            if "technical" in user_msg or "broken" in user_msg or "error" in user_msg or "not working" in user_msg or "bug" in user_msg or "crash" in user_msg or "integration" in user_msg:
                return "technical_support|0.90"
            if "charged twice" in user_msg or "double charge" in user_msg or "money back" in user_msg or "reimburse" in user_msg:
                return "refund_request|0.97"
            if "billing" in user_msg or "invoice" in user_msg or "overcharged" in user_msg:
                return "billing_issue|0.90"
            if "account" in user_msg or "update my" in user_msg or "change my" in user_msg or "modify" in user_msg:
                return "account_modification|0.88"
            if "how do i" in user_msg or "what is" in user_msg or "can you tell me" in user_msg or "policy" in user_msg:
                return "faq_question|0.85"
            if "manager" in user_msg or "supervisor" in user_msg or "escalate" in user_msg:
                return "escalation|0.90"
            if "complaint" in user_msg or "unacceptable" in user_msg or "terrible" in user_msg or "worst" in user_msg:
                return "complaint|0.88"
            if "refund" in user_msg:
                return "refund_request|0.95"
            if "charge" in user_msg or "payment" in user_msg:
                return "billing_issue|0.85"
            return "general_inquiry|0.75"

        # Sentiment
        if "sentiment" in prompt_lower or "emotion" in prompt_lower:
            if "furious" in user_msg or "outraged" in user_msg or "lawyer" in user_msg or "lawsuit" in user_msg or "attorney" in user_msg or "disgusted" in user_msg or "legal action" in user_msg:
                return "angry|0.95"
            if "angry" in user_msg or "unacceptable" in user_msg or "ridiculous" in user_msg or "upset" in user_msg or "disappointed" in user_msg or "terrible" in user_msg or "worst" in user_msg or "frustrated" in user_msg:
                return "frustrated|0.75"
            if "great" in user_msg or "awesome" in user_msg or "love" in user_msg or "thank you" in user_msg or "perfect" in user_msg or "wonderful" in user_msg or "excellent" in user_msg or "happy" in user_msg:
                return "happy|0.80"
            return "neutral|0.30"

        # Escalation
        if "escalat" in prompt_lower:
            if "legal" in user_msg or "attorney" in user_msg or "lawyer" in user_msg or "lawsuit" in user_msg or "sue" in user_msg or "court" in user_msg or "fraud" in user_msg:
                return "true|legal_threat"
            if "manager" in user_msg or "supervisor" in user_msg or "human agent" in user_msg:
                return "true|customer_requested_manager"
            if "third email" in user_msg or "nobody has responded" in user_msg or "still not resolved" in user_msg or "no one has helped" in user_msg or "still waiting" in user_msg:
                return "true|multiple_unresolved_tickets"
            if "urgent" in user_msg or "unacceptable" in user_msg:
                return "true|high_urgency"
            return "false|"

        # FAQ
        if "faq" in prompt_lower:
            if "refund" in user_msg or "charged twice" in user_msg or "money back" in user_msg:
                return "refund_policy|0.90|Refunds are available within 30 days of purchase for duplicate charges."
            if "shipping" in user_msg or "delivery" in user_msg:
                return "shipping_faq|0.85|Standard shipping takes 3-5 business days."
            if "cancel" in user_msg or "cancellation" in user_msg:
                return "cancellation_faq|0.85|Orders can be cancelled within 24 hours of placement."
            return "no_match|0.00|"

        # Knowledge base
        if "knowledge" in prompt_lower or "kb" in prompt_lower or "retriev" in prompt_lower:
            if "refund" in user_msg or "charge" in user_msg:
                return "Found relevant document: Refund policy allows full refund for duplicate charges within 30 days."
            if "technical" in user_msg or "integration" in user_msg or "error" in user_msg:
                return "Found relevant document: Technical integration troubleshooting guide — verify API credentials and webhook endpoints."
            return "Found relevant document: General customer support policies and procedures."

        # Integration
        if "crm" in prompt_lower or "integration" in prompt_lower or "lookup" in prompt_lower:
            return '{"order_id": "ORD-12345", "status": "delivered", "charges": [{"amount": 49.99, "date": "2025-01-05"}, {"amount": 49.99, "date": "2025-01-05"}]}'

        # Reasoning
        if "reason" in prompt_lower or "think" in prompt_lower:
            return "Step 1: Customer reports duplicate charge. Step 2: CRM confirms two charges on same date. Step 3: Policy allows refund within 30 days. Conclusion: Customer is eligible for full refund of $49.99."

        # Reverse thinking
        if "reverse" in prompt_lower or "backward" in prompt_lower or "trace" in prompt_lower:
            return "Goal: Refund processed. Trace: Need approval -> Need evidence -> CRM shows duplicate -> Policy allows refund -> Evidence confirmed. Validation: PASSED."

        # Tree of thoughts
        if "tree" in prompt_lower or "paths" in prompt_lower or "explore" in prompt_lower:
            return 'Path 1: Full refund (confidence: 0.95, selected: true). Path 2: Partial refund (confidence: 0.40). Path 3: Store credit (confidence: 0.30).'

        # Strategy
        if "strateg" in prompt_lower or "plan" in prompt_lower:
            return "Step 1: Verify duplicate charge in CRM. Step 2: Calculate refund amount ($49.99). Step 3: Submit for approval or execute refund."

        # Action planning
        if "action" in prompt_lower and "plan" in prompt_lower:
            return "Action: Process refund of $49.99 to original payment method."

        # Quality scoring
        if "quality" in prompt_lower or "score" in prompt_lower:
            return "85|accurate,complete,compliant"

        # PII detection
        if "pii" in prompt_lower or "personal" in prompt_lower or "redact" in prompt_lower:
            return "false|No PII detected in message."

        # Proactive
        if "proactive" in prompt_lower or "predict" in prompt_lower or "next" in prompt_lower:
            return "Customer may ask about shipping status next (confidence: 0.80)."

        return "Analysis complete. No specific pattern matched."

    async def ainvoke(self, prompt: str | list, **kwargs: Any) -> str:
        """Async mock — returns same deterministic response as invoke."""
        return self.invoke(prompt, **kwargs)


# Singleton mock instance
_mock_llm = MockLLM()


def get_mock_llm() -> MockLLM:
    """Get the mock LLM instance for testing."""
    return _mock_llm

"""Tests for the BYO voice system + AI conversation engine (2026-02).

Scope (user-approved plan):
1. BYO ONLY — `parwa_provided` mode is retired. Parwa never provisions
   phone numbers, never pays for telecom. Tenants connect their OWN
   calling platform account (provider field) and pay that provider.
2. Fake demo servers deleted (parwa_voice_server.py, voice_demo.py) —
   they had canned keyword responses, zero AI.
3. NEW VoiceConversationEngine — the agent must CALL and then SOLVE:
   LLM turn loop connected to the tenant's OWN agents (AIAgentAssignment)
   and their SuperGlue tools (whitelist-only execution), honest tool
   outcomes, opt-out, transfer, post-call ticket creation.
4. Gather webhook — customer speech is finally PROCESSED (was ignored).
5. Provider adapter layer — Twilio adapter #1, more providers addable.

Run:  cd backend && ../venv/bin/python -m pytest tests/test_voice_byo_engine.py -q
"""

import ast
import re
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENGINE = BACKEND_DIR / "app/services/voice_conversation_engine.py"
SERVICE = BACKEND_DIR / "app/services/voice_channel_service.py"
API = BACKEND_DIR / "app/api/voice_channel.py"
MODELS = BACKEND_DIR / "database/models/voice_channel.py"
BASE_PROVIDER = BACKEND_DIR / "app/core/providers/voice/base_voice_provider.py"
TWILIO_PROVIDER = BACKEND_DIR / "app/core/providers/voice/twilio_voice_provider.py"
MIGRATION = BACKEND_DIR / "database/alembic/versions/040_voice_provider_turns.py"
MIGRATION_029 = BACKEND_DIR / "database/alembic/versions/029_voice_channel_tables.py"
MAIN = BACKEND_DIR / "app/main.py"
VENV_PY = BACKEND_DIR.parent / "venv" / "bin" / "python"


def _ast_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text())


def _source(path: Path) -> str:
    return path.read_text()


def _run_py(code: str, extra_env: dict | None = None, timeout: int = 180) -> str:
    """Run python in a clean subprocess (house style).

    DATABASE_URL is HARD-SET to a UNIQUE fresh sqlite file per run so the
    test can never read or write a foreign database.
    """
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///./test_voice_{uuid.uuid4().hex[:8]}.db"
    env["TRIAL_LIMIT_DISABLED"] = "false"
    if extra_env:
        env.update(extra_env)
    out = subprocess.run(
        [str(VENV_PY), "-c", code],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if out.returncode != 0:
        raise AssertionError(f"subprocess failed:\n{out.stdout}\n{out.stderr}")
    return out.stdout


# ── 1. BYO: static source checks ───────────────────────────────────────

def test_byo_provision_functions_removed():
    src = _source(SERVICE)
    assert "def provision_parwa_number" not in src, (
        "Parwa must never provision phone numbers"
    )
    assert "def release_parwa_number" not in src, (
        "release function belongs to the retired parwa_provided mode"
    )


def test_byo_create_config_rejects_parwa_provided():
    src = _source(SERVICE)
    assert 'requested_source == "parwa_provided"' in src
    assert "no longer provides phone numbers" in src
    assert 'number_source = "bring_own"' in src


def test_byo_provider_field_on_config_model():
    src = _source(MODELS)
    assert "VoiceCallTurn" in src
    assert 'provider = Column(' in src
    assert "_VOICE_PROVIDERS" in src


def test_demo_files_deleted():
    assert not (BACKEND_DIR / "app/core/parwa_voice_server.py").exists(), (
        "canned-response demo server must be deleted"
    )
    assert not (BACKEND_DIR / "app/core/voice_demo.py").exists(), (
        "fake voice demo engine must be deleted"
    )


def test_migration_040_chains_correctly():
    src = _source(MIGRATION)
    assert 'revision = "040_voice_provider_turns"' in src
    assert 'down_revision = "039_ticket_list_indexes"' in src
    assert "voice_call_turns" in src


def test_every_voice_config_model_column_has_db_home():
    """Regression (live 2026-02, cost us a prod 500): voice_channel_configs
    had model-only columns (number_source, caller_id_name, greeting_style,
    language_preference, parwa_phone_number, parwa_number_sid, provider)
    that NO migration ever created — every config SELECT/INSERT failed on
    production. Guard: every VoiceChannelConfig model column must appear
    in migration 029/040 SQL OR the main.py startup SQL fallback."""
    src = _source(MODELS)
    m = re.search(r"class VoiceChannelConfig\(Base\):(.*?)(?=\nclass |\Z)", src, re.S)
    assert m, "VoiceChannelConfig class not found"
    cols = set(re.findall(r"^\s{4}(\w+)\s*=\s*Column\(", m.group(1), re.M))
    assert cols, "no model columns parsed"
    covered = _source(MIGRATION_029) + _source(MIGRATION) + _source(MAIN)
    missing = [c for c in sorted(cols) if c not in covered]
    assert not missing, (
        f"VoiceChannelConfig columns with no migration/fallback: {missing}"
    )


def test_gather_webhook_route_exists():
    src = _source(API)
    assert '@router.post("/webhook/gather")' in src
    assert "VoiceConversationEngine" in src
    assert "handle_turn" in src


def test_webhook_urls_use_backend_public_url_not_frontend():
    """Regression (live test 2026-02): gather/status webhooks were built from
    FRONTEND_URL (parwa.buzz) — but parwa.buzz has NO /api/v1/voice routes,
    so Twilio's callbacks would 404 and every call would be dead air.
    Provider callbacks MUST land on the Python backend host."""
    src = _source(SERVICE)
    assert "_get_webhook_base_url" in src
    assert "BACKEND_PUBLIC_URL" in src
    assert "RENDER_EXTERNAL_URL" in src
    # FRONTEND_URL may only appear as the LAST-resort fallback inside the
    # base-url helper — never as the direct base for a webhook URL.
    for line in src.splitlines():
        if "webhook/gather" in line or "webhook/status" in line:
            assert "FRONTEND_URL" not in line, (
                f"webhook URL built from FRONTEND_URL: {line.strip()}"
            )


def test_csrf_middleware_skips_provider_webhooks():
    """Regression (live call 2026-02, call died at 14s): the CSRF middleware
    rejected Twilio's speech gather POST (providers send no Origin header).
    Server-to-server provider callbacks are authenticated by X-Twilio-Signature
    inside the handlers — CSRF (a browser attack) must not apply."""
    CSRF = BACKEND_DIR / "app/middleware/csrf.py"
    src = _source(CSRF)
    assert '"/api/v1/voice/webhook/"' in src, (
        "CSRF must skip voice provider webhooks (gather/status/voice)"
    )
    assert '"/api/v1/sms/webhook/"' in src, (
        "CSRF must skip sms provider webhooks"
    )
    # TenantMiddleware must also let provider callbacks through (no JWT on
    # Twilio/Exotel callbacks — the route self-identifies the tenant).
    TENANT = BACKEND_DIR / "app/middleware/tenant.py"
    tsrc = _source(TENANT)
    assert '"/api/v1/voice/webhook/"' in tsrc, (
        "TenantMiddleware must skip voice provider webhooks"
    )
    assert '"/api/v1/sms/webhook/"' in tsrc, (
        "TenantMiddleware must skip sms provider webhooks"
    )


def test_twilio_signature_tolerates_proxy_scheme_mismatch():
    """Regression (live probe 2026-02): behind Render's TLS proxy the ASGI
    server sees http:// but Twilio signed https:// → every real webhook
    rejected with 401. The verifier must retry with the scheme swapped."""
    TP = _source(TWILIO_PROVIDER)
    assert "https://" in TP and "http://" in TP
    assert "swapped" in TP or "scheme" in TP.lower(), (
        "verify_signature must retry with swapped scheme"
    )
    dockerfile = (BACKEND_DIR.parent / "backend" / "Dockerfile")
    df = dockerfile.read_text()
    assert "--proxy-headers" in df, (
        "uvicorn must trust proxy headers (request.url must be https behind Render)"
    )
    assert "--forwarded-allow-ips" in df

def test_twilio_signature_matches_official_sdk():
    """Regression (live probe 2026-02): the old validator compared HEX digest
    instead of Twilio's BASE64 — NO valid Twilio signature could ever pass,
    so every real webhook 401'd. Must byte-match the official SDK."""
    import base64
    import hashlib
    import hmac as hmac_mod
    sys.path.insert(0, str(BACKEND_DIR))
    from app.security.hmac_verification import verify_twilio_signature

    token = "unittesttoken1234567890abcdef12345678"
    url = "https://parwa-backend.onrender.com/api/v1/voice/webhook/gather?company_id=abc"
    params = {
        "CallSid": "CAunittest0000000000000000000000000000",
        "From": "+919652852014",
        "SpeechResult": "I want a refund for order A-1001",
    }
    # Sign exactly like twilio.request_validator.RequestValidator
    data = url + "".join(k + str(v) for k, v in sorted(params.items()))
    sig = base64.b64encode(
        hmac_mod.new(token.encode(), data.encode(), hashlib.sha1).digest()
    ).decode()
    assert verify_twilio_signature(url, params, sig, token) is True
    assert verify_twilio_signature(url, params, sig[:-2] + "xx", token) is False
    assert verify_twilio_signature(url, {}, "", token) is False


def test_engine_uses_superglue_tools():
    """The voice agent MUST use the same SuperGlue tools as the pipeline."""
    tree = _ast_tree(ENGINE)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(f"{node.module}.{alias.name}")
    assert "app.core.superglue_client.execute_tool" in imports
    assert "app.core.parwa_pipeline.llm_client.llm_call" in imports


def test_engine_tool_whitelist_from_tenant_agents():
    """Tools are whitelisted from the tenant's OWN active agents."""
    src = _source(ENGINE)
    assert "AIAgentAssignment" in src
    assert '_active_agents_with_tools' in src
    assert 'superglue_tool_status == "active"' in src
    assert 'AIAgentAssignment.status == "active"' in src
    # Non-whitelisted tool must be refused, never executed
    assert "refused" in src
    assert "not_whitelisted" in src


def test_engine_tool_timeout_within_webhook_budget():
    """Twilio webhook timeout is 15s — tool wait must stay below it."""
    tree = _ast_tree(ENGINE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "TOOL_TIMEOUT_SECONDS"
                ):
                    assert isinstance(node.value, ast.Constant)
                    assert node.value.value <= 15, (
                        "tool timeout would exceed the provider webhook budget"
                    )
                    return
    raise AssertionError("TOOL_TIMEOUT_SECONDS constant not found")


def test_engine_honesty_rules_in_prompt():
    """The agent must never fake success — it replaces humans, honestly."""
    src = _source(ENGINE)
    assert "NEVER say you did something unless" in src
    assert "NEVER invent order numbers" in src
    # Honest tool-failure fallback wording exists
    assert "didn't go through" in src


def test_engine_opt_out_guard():
    src = _source(ENGINE)
    assert "_OPT_OUT_PATTERN" in src
    assert "is_opted_out = True" in src


def test_engine_max_turns_guard():
    src = _source(ENGINE)
    assert "MAX_TURNS_PER_CALL" in src
    assert "max_turns" in src


# ── 3. Provider adapters: static checks ───────────────────────────────

def test_provider_adapters_exist():
    assert BASE_PROVIDER.exists()
    assert TWILIO_PROVIDER.exists()
    src = _source(BASE_PROVIDER)
    assert "class VoiceProviderBase" in src
    assert "def get_voice_provider" in src


# ── 4. Behavioral tests: models + providers (fresh sqlite) ────────────

SETUP_DB = """
import json, os
os.environ.setdefault("TRIAL_LIMIT_DISABLED", "false")
from database.base import Base, engine, SessionLocal
from database import models  # noqa - register all tables
from database.models.voice_channel import (
    VoiceCall, VoiceCallTurn, VoiceConversation, VoiceChannelConfig,
)
from database.models.core import Company
from database.models.tickets import Customer, Ticket, TicketMessage
from database.models.variant_engine import AIAgentAssignment
from sqlalchemy.orm import sessionmaker

# Targeted table creation: the full metadata contains Postgres-only
# JSONB columns elsewhere in the repo, which sqlite cannot render.
for model in (Company, Customer, Ticket, TicketMessage,
              AIAgentAssignment, VoiceCall, VoiceCallTurn,
              VoiceConversation, VoiceChannelConfig):
    model.__table__.create(engine, checkfirst=True)

Session = SessionLocal
db = Session()

company = Company(
    id="comp-voice-1",
    name="Voice Test Co",
    industry="saas",
    subscription_tier="trial",
)
db.add(company)
db.commit()
print("DB_READY")
"""


def test_models_and_config_roundtrip():
    code = SETUP_DB + """
cfg = VoiceChannelConfig(
    company_id="comp-voice-1",
    number_source="bring_own",
    provider="twilio",
    twilio_account_sid="ACtest123456789",
    twilio_auth_token_encrypted="enc",
    twilio_phone_number="+15550001111",
)
db.add(cfg)
db.add(VoiceCall(company_id="comp-voice-1", direction="inbound",
                 from_number="+15550001111", to_number="+15559999999",
                 twilio_call_sid="CA001", status="ringing"))
db.commit()
d = cfg.to_dict()
assert d["provider"] == "twilio", d
assert d["number_source"] == "bring_own", d
assert d["twilio_account_sid"].startswith("****"), "SID must be masked"
turns = db.query(VoiceCallTurn).all()
assert turns == []
print("ROUNDTRIP_OK")
"""
    out = _run_py(code)
    assert "ROUNDTRIP_OK" in out


def test_provider_adapter_twiml_and_parsing():
    code = SETUP_DB + """
from app.core.providers.voice.base_voice_provider import get_voice_provider
from app.core.providers.voice.twilio_voice_provider import TwilioVoiceProvider

p = get_voice_provider("twilio")
assert isinstance(p, TwilioVoiceProvider)
try:
    get_voice_provider("nonexistent_provider")
    raise SystemExit("should have raised")
except ValueError:
    pass

# Parsing: gather event with speech
ev = p.parse_webhook({
    "CallSid": "CA1", "From": "+15550001111", "To": "+15559999999",
    "SpeechResult": "I want a refund", "CallStatus": "in-progress",
})
assert ev.event_kind == "gather", ev
assert ev.speech_text == "I want a refund"

# Parsing: plain status event
ev2 = p.parse_webhook({"CallSid": "CA1", "CallStatus": "completed"})
assert ev2.event_kind == "status"
assert ev2.call_status == "completed"

# TwiML builders
g = p.build_greeting_twiml("Hello there", "https://x/gather", "en-IN", "Polly.Aditi")
assert "<Gather" in g and "https://x/gather" in g and "Hello there" in g
c = p.build_conversation_twiml("Sure <thing> & more", "https://x/gather", "en-IN", "V")
assert "Sure &lt;thing&gt; &amp; more" in c, "XML escaping required"
t = p.build_transfer_twiml("One moment", "+15551112222", "en-IN", "V")
assert "<Dial" in t and "+15551112222" in t
e = p.build_end_twiml("Goodbye", "en-IN", "V")
assert "<Hangup/>" in e

# Signature: no tenant token -> allow (test mode); garbage token + sig -> reject
assert p.verify_signature("https://x", {}, {}, "") is True
assert p.verify_signature("https://x", {}, {"X-Twilio-Signature": "bad"}, "realtoken") is False
print("ADAPTER_OK")
"""
    out = _run_py(code)
    assert "ADAPTER_OK" in out


# ── 5. Behavioral tests: the engine brain (mocked LLM + tools) ─────────

ENGINE_HARNESS = SETUP_DB + """
from unittest.mock import patch
import app.services.voice_conversation_engine as vce
from database.models.voice_channel import (
    VoiceCall, VoiceCallTurn, VoiceConversation, VoiceChannelConfig,
)
from database.models.variant_engine import AIAgentAssignment
from app.services.voice_conversation_engine import VoiceConversationEngine

# ── Tenant fixtures: config + call + conversation + agent with tool ──
cfg = VoiceChannelConfig(
    company_id="comp-voice-1", number_source="bring_own", provider="twilio",
    twilio_account_sid="ACxxx", twilio_auth_token_encrypted="enc",
    twilio_phone_number="+15550001111",
    transfer_number=None, greeting_message="Welcome to Acme support!",
)
db.add(cfg)
conv = VoiceConversation(
    company_id="comp-voice-1", customer_number="+15550001111",
    twilio_number="+15559999999",
)
db.add(conv)
db.commit()
call = VoiceCall(
    company_id="comp-voice-1", conversation_id=conv.id,
    direction="inbound", from_number="+15550001111",
    to_number="+15559999999", twilio_call_sid="CA001", status="ringing",
)
db.add(call)
agent = AIAgentAssignment(
    company_id="comp-voice-1", agent_name="Refund Request",
    capabilities=json.dumps(["refund_processing", "billing_inquiry"]),
    status="active",
    superglue_tool_id="tenant_comp-voice-1__process-refund-request",
    superglue_tool_status="active",
    instructions="Process refunds after confirming the order id.",
)
db.add(agent)
db.commit()

engine = VoiceConversationEngine(db)
"""


def test_engine_start_call_greeting_no_llm():
    code = ENGINE_HARNESS + """
import asyncio

async def _fail_llm(*a, **k):
    raise AssertionError("start_call must not call the LLM")

with patch.object(vce, "_llm_call", _fail_llm):
    result = engine.start_call(
        company_id="comp-voice-1", call_sid="CA001",
        direction="inbound", from_number="+15550001111",
        to_number="+15559999999",
    )
assert result.action == "continue"
assert result.say == "Welcome to Acme support!"
turns = db.query(VoiceCallTurn).filter_by(call_sid="CA001").all()
assert len(turns) == 1 and turns[0].role == "agent"
print("START_CALL_OK")
"""
    out = _run_py(code)
    assert "START_CALL_OK" in out


def test_engine_plain_reply_turn():
    code = ENGINE_HARNESS + """
import asyncio

async def fake_llm(**kw):
    return json.dumps({
        "say": "I can help you track your order.",
        "tool_call": None, "action": "continue",
    })

engine.start_call(company_id="comp-voice-1", call_sid="CA001",
                  direction="inbound", from_number="+15550001111",
                  to_number="+15559999999")

with patch.object(vce, "_llm_call", fake_llm):
    result = asyncio.get_event_loop().run_until_complete(
        engine.handle_turn(
            company_id="comp-voice-1", call_sid="CA001",
            customer_text="Where is my order?",
        )
    )
assert result.action == "continue"
assert "track your order" in result.say
turns = db.query(VoiceCallTurn).filter_by(call_sid="CA001").order_by(
    VoiceCallTurn.created_at.asc(), VoiceCallTurn.id.asc()).all()
roles = [t.role for t in turns]
assert "customer" in roles and roles.count("agent") >= 2
print("PLAIN_TURN_OK")
"""
    out = _run_py(code)
    assert "PLAIN_TURN_OK" in out


def test_engine_tool_success_flow():
    """Tool runs via execute_tool with tenant_id; result is spoken honestly."""
    code = ENGINE_HARNESS + """
import asyncio

calls = {"llm": 0, "tool": None}

async def fake_llm(**kw):
    calls["llm"] += 1
    if calls["llm"] == 1:
        return json.dumps({
            "say": "Let me process that refund.",
            "tool_call": {
                "tool_id": "tenant_comp-voice-1__process-refund-request",
                "input": {"order_id": "A-123"},
            },
            "action": "continue",
        })
    # Second call must contain the REAL tool result in the prompt
    prompt = kw.get("prompt", "")
    assert "REFUND_DONE_123" in prompt, "tool result must reach the LLM"
    return json.dumps({
        "say": "Your refund for order A-123 is processed.",
        "tool_call": None, "action": "continue",
    })

async def fake_tool(tool_id, tool_input, tenant_id=None):
    calls["tool"] = (tool_id, dict(tool_input), tenant_id)
    return {"success": True, "refund_id": "REFUND_DONE_123"}

with patch.object(vce, "_llm_call", fake_llm), \\
     patch.object(vce, "_execute_tool", fake_tool):
    result = asyncio.get_event_loop().run_until_complete(
        engine.handle_turn(
            company_id="comp-voice-1", call_sid="CA001",
            customer_text="I want a refund for order A-123",
        )
    )

assert calls["tool"] is not None
tool_id, tool_input, tenant_id = calls["tool"]
assert tool_id == "tenant_comp-voice-1__process-refund-request"
assert tool_input == {"order_id": "A-123"}
assert tenant_id == "comp-voice-1", "tool must run scoped to the tenant"
assert result.tool_status == "ok"
assert "processed" in result.say
tool_turns = db.query(VoiceCallTurn).filter_by(
    call_sid="CA001", role="system").all()
assert any(t.tool_id and t.tool_status == "ok" for t in tool_turns)
print("TOOL_SUCCESS_OK")
"""
    out = _run_py(code)
    assert "TOOL_SUCCESS_OK" in out


def test_engine_refuses_non_whitelisted_tool():
    """A tool not linked to THIS tenant's active agent can NEVER run."""
    code = ENGINE_HARNESS + """
import asyncio

async def fake_llm(**kw):
    return json.dumps({
        "say": "Trying...",
        "tool_call": {"tool_id": "tenant_OTHER-TENANT__steal-data",
                      "input": {}},
        "action": "continue",
    })

tool_calls = []
async def fake_tool(*a, **k):
    tool_calls.append(a)
    return {"success": True}

with patch.object(vce, "_llm_call", fake_llm), \\
     patch.object(vce, "_execute_tool", fake_tool):
    result = asyncio.get_event_loop().run_until_complete(
        engine.handle_turn(
            company_id="comp-voice-1", call_sid="CA001",
            customer_text="do the thing",
        )
    )
assert tool_calls == [], "non-whitelisted tool must NOT be executed"
assert result.tool_status == "refused"
assert "don't have the ability" in result.say
print("WHITELIST_OK")
"""
    out = _run_py(code)
    assert "WHITELIST_OK" in out


def test_engine_tool_failure_honest():
    code = ENGINE_HARNESS + """
import asyncio

llm_calls = {"n": 0}
async def fake_llm(**kw):
    llm_calls["n"] += 1
    if llm_calls["n"] == 1:
        return json.dumps({
            "say": "One moment.",
            "tool_call": {
                "tool_id": "tenant_comp-voice-1__process-refund-request",
                "input": {},
            },
            "action": "continue",
        })
    return json.dumps({
        "say": "It didn't work, sorry.", "tool_call": None,
        "action": "continue",
    })

async def failing_tool(*a, **k):
    raise RuntimeError("upstream 500")

with patch.object(vce, "_llm_call", fake_llm), \\
     patch.object(vce, "_execute_tool", failing_tool):
    result = asyncio.get_event_loop().run_until_complete(
        engine.handle_turn(
            company_id="comp-voice-1", call_sid="CA001",
            customer_text="refund please",
        )
    )
assert result.tool_status == "failed"
assert "didn't work" in result.say or "sorry" in result.say.lower()
assert "successfully processed" not in result.say.lower(), (
    "must never claim success after a failure"
)
print("TOOL_FAIL_OK")
"""
    out = _run_py(code)
    assert "TOOL_FAIL_OK" in out


def test_engine_tool_timeout_honest():
    code = ENGINE_HARNESS + """
import asyncio

llm_calls = {"n": 0}
async def fake_llm(**kw):
    llm_calls["n"] += 1
    if llm_calls["n"] == 1:
        return json.dumps({
            "say": "One moment.",
            "tool_call": {
                "tool_id": "tenant_comp-voice-1__process-refund-request",
                "input": {},
            },
            "action": "continue",
        })
    # Second call: the engine fed the REAL timeout result to the LLM
    assert "Result status: timeout" in kw.get("prompt", "")
    return json.dumps({
        "say": "I'm sorry, that didn't go through.",
        "tool_call": None, "action": "continue",
    })

async def slow_tool(*a, **k):
    await asyncio.sleep(30)
    return {"success": True}

with patch.object(vce, "_llm_call", fake_llm), \\
     patch.object(vce, "_execute_tool", slow_tool), \\
     patch.object(vce, "TOOL_TIMEOUT_SECONDS", 0.2):
    result = asyncio.get_event_loop().run_until_complete(
        engine.handle_turn(
            company_id="comp-voice-1", call_sid="CA001",
            customer_text="refund please",
        )
    )
assert result.tool_status == "timeout", result
assert "didn't go through" in result.say, (
    "timeout fallback must be honest, not fake success"
)
# The persisted system turn records the timeout
tool_turns = db.query(VoiceCallTurn).filter_by(
    call_sid="CA001", role="system").all()
assert any(t.tool_status == "timeout" for t in tool_turns)
print("TOOL_TIMEOUT_OK")
"""
    out = _run_py(code)
    assert "TOOL_TIMEOUT_OK" in out


def test_engine_malformed_llm_json_fallback():
    code = ENGINE_HARNESS + """
import asyncio

async def bad_llm(**kw):
    return "sorry I am not json, just words"

with patch.object(vce, "_llm_call", bad_llm):
    result = asyncio.get_event_loop().run_until_complete(
        engine.handle_turn(
            company_id="comp-voice-1", call_sid="CA001",
            customer_text="hello?",
        )
    )
assert result.action == "continue"
assert result.say != "", "never leave the caller in silence"
print("MALFORMED_OK")
"""
    out = _run_py(code)
    assert "MALFORMED_OK" in out


def test_engine_spoken_opt_out():
    code = ENGINE_HARNESS + """
import asyncio

async def _fail_llm(*a, **k):
    raise AssertionError("opt-out must not need the LLM")

with patch.object(vce, "_llm_call", _fail_llm):
    result = asyncio.get_event_loop().run_until_complete(
        engine.handle_turn(
            company_id="comp-voice-1", call_sid="CA001",
            customer_text="Stop calling me please",
        )
    )
assert result.action == "end" and result.end_reason == "opt_out"
db.refresh(conv)
assert conv.is_opted_out is True, "TCPA opt-out must be persisted"
print("OPT_OUT_OK")
"""
    out = _run_py(code)
    assert "OPT_OUT_OK" in out


def test_engine_transfer_downgrade_without_number():
    """No transfer number configured → honest downgrade, no fake transfer."""
    code = ENGINE_HARNESS + """
import asyncio

async def fake_llm(**kw):
    return json.dumps({
        "say": "This needs a human specialist.",
        "tool_call": None, "action": "transfer",
    })

with patch.object(vce, "_llm_call", fake_llm):
    result = asyncio.get_event_loop().run_until_complete(
        engine.handle_turn(
            company_id="comp-voice-1", call_sid="CA001",
            customer_text="I want to talk to a human",
        )
    )
assert result.action == "continue", "must not claim a transfer it cannot do"
assert "call you back" in result.say.lower() or "colleague" in result.say.lower()
print("TRANSFER_DOWNGRADE_OK")
"""
    out = _run_py(code)
    assert "TRANSFER_DOWNGRADE_OK" in out


def test_engine_finish_call_creates_ticket():
    code = ENGINE_HARNESS + """
import asyncio
from database.models.voice_channel import VoiceCall

engine.start_call(company_id="comp-voice-1", call_sid="CA001",
                  direction="inbound", from_number="+15550001111",
                  to_number="+15559999999")

async def fake_llm(**kw):
    prompt = kw.get("prompt", "")
    if "CONVERSATION SO FAR" in prompt:
        return json.dumps({"say": "Refund done.", "tool_call": None,
                           "action": "end", "end_reason": "resolved"})
    # post-call summary call
    return "Customer wanted a refund. Refund was processed successfully."

with patch.object(vce, "_llm_call", fake_llm):
    asyncio.get_event_loop().run_until_complete(
        engine.handle_turn(
            company_id="comp-voice-1", call_sid="CA001",
            customer_text="thanks, that is all",
        )
    )
    result = engine.finish_call(
        company_id="comp-voice-1", call_sid="CA001",
        end_reason="resolved", duration_seconds=95,
    )

assert result["status"] == "finished", result
assert result["ticket_id"], "post-call ticket must be created"
assert result["turns"] >= 2
db.refresh(call)
assert call.ticket_id == result["ticket_id"]
assert call.transcript_json and "Customer" in call.transcript_json
assert call.transcript_summary
assert call.status == "completed"
print("FINISH_CALL_OK ticket=%s" % result["ticket_id"])
"""
    out = _run_py(code)
    assert "FINISH_CALL_OK" in out


# ── 6. Integration: HTTP webhooks end-to-end (fresh sqlite + FastAPI) ──

INTEGRATION_HARNESS = SETUP_DB + """
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import app.services.voice_conversation_engine as vce
from database.models.voice_channel import (
    VoiceCall, VoiceCallTurn, VoiceChannelConfig,
)
from database.models.variant_engine import AIAgentAssignment
from app.api.voice_channel import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

cfg = VoiceChannelConfig(
    company_id="comp-voice-1", number_source="bring_own", provider="twilio",
    twilio_account_sid="ACxxx", twilio_auth_token_encrypted="enc",
    twilio_phone_number="+15550001111",
)
db.add(cfg)
agent = AIAgentAssignment(
    company_id="comp-voice-1", agent_name="Refund Request",
    capabilities=json.dumps(["refund_processing"]),
    status="active",
    superglue_tool_id="tenant_comp-voice-1__process-refund-request",
    superglue_tool_status="active",
)
db.add(agent)
db.commit()

async def fake_llm(**kw):
    return json.dumps({
        "say": "I can start that refund for you.",
        "tool_call": None, "action": "continue",
    })

print("HARNESS_READY")
"""


def test_integration_inbound_then_gather_turn():
    code = INTEGRATION_HARNESS + """
# Step 1: inbound call webhook → greeting TwiML with live Gather action
r1 = client.post(
    "/api/v1/voice/webhook/voice",
    data={"CallSid": "CA-INT-1", "From": "+15550001111",
          "To": "+15550001111", "CallStatus": "ringing",
          "AccountSid": "ACxxx", "Direction": "inbound"},
)
assert r1.status_code == 200, r1.text
assert r1.headers["content-type"].startswith("application/xml")
body1 = r1.text
assert "<Gather" in body1, "inbound must start listening for speech"
assert "/api/v1/voice/webhook/gather" in body1, "gather action URL required"
assert "company_id=comp-voice-1" in body1

# Step 2: customer speech arrives at the gather webhook → AI turn
with patch.object(vce, "_llm_call", fake_llm):
    r2 = client.post(
        "/api/v1/voice/webhook/gather?company_id=comp-voice-1",
        data={"CallSid": "CA-INT-1", "From": "+15550001111",
              "To": "+15550001111", "SpeechResult": "I need help",
              "CallStatus": "in-progress"},
    )
assert r2.status_code == 200, r2.text
assert "I can start that refund for you." in r2.text
assert "<Gather" in r2.text, "conversation must keep listening"

# Step 3: transcript persisted
turns = db.query(VoiceCallTurn).filter_by(call_sid="CA-INT-1").all()
roles = sorted(t.role for t in turns)
assert "customer" in roles and "agent" in roles, roles
print("INTEGRATION_OK")
"""
    out = _run_py(code)
    assert "INTEGRATION_OK" in out


def test_integration_gather_unknown_company_rejected():
    code = INTEGRATION_HARNESS + """
r = client.post(
    "/api/v1/voice/webhook/gather?company_id=ghost-company",
    data={"CallSid": "CA-X", "SpeechResult": "hello"},
)
assert r.status_code == 200  # XML response, but it must hang up
assert "<Hangup/>" in r.text
print("UNKNOWN_COMPANY_OK")
"""
    out = _run_py(code)
    assert "UNKNOWN_COMPANY_OK" in out


def test_integration_service_rejects_parwa_provided():
    code = SETUP_DB + """
from app.services.voice_channel_service import VoiceChannelService

service = VoiceChannelService(db)
result = service.create_voice_config("comp-voice-1", {
    "number_source": "parwa_provided",
    "area_code": "555",
})
assert result["status"] == "error"
assert "no longer provides phone numbers" in result["error"]

# BYO with valid data works, provider is stored
result2 = service.create_voice_config("comp-voice-1", {
    "number_source": "bring_own",
    "provider": "twilio",
    "twilio_account_sid": "ACBYO12345678",
    "twilio_auth_token": "tok",
    "twilio_phone_number": "+15557776666",
})
assert result2["status"] == "created", result2
assert result2["config"]["provider"] == "twilio"
assert result2["config"]["number_source"] == "bring_own"

# Unknown provider rejected
result3 = service.create_voice_config("comp-voice-2", {
    "provider": "sky-telecom-9000",
    "twilio_account_sid": "ACX",
    "twilio_auth_token": "t",
    "twilio_phone_number": "+15550000000",
})
assert result3["status"] == "error"
assert "Unknown voice provider" in result3["error"]
print("SERVICE_BYO_OK")
"""
    out = _run_py(code)
    assert "SERVICE_BYO_OK" in out

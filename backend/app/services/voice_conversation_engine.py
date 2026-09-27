"""Voice Conversation Engine — the AI brain for live phone calls.

This is what makes Parwa's agent able to actually SOLVE problems during
a call, not just talk. Parwa replaces humans — so a call must end with
the problem resolved (or an honest transfer/callback), never with fake
promises.

Flow per turn (driven by the provider's Gather webhook):
  1. Customer speech arrives (provider already did speech→text).
  2. Engine loads the tenant's OWN AI agents (AIAgentAssignment) and the
     SuperGlue tools linked to them — the SAME agents/tools the text
     pipeline uses. Tool execution is whitelist-only: a tool not linked
     to one of THIS tenant's active agents can never run.
  3. One fast LLM call decides: reply / call a tool / transfer to a
     human / end the call.
  4. If a tool is called, it executes (timeout-guarded) and its REAL
     result is fed to a second LLM call that speaks the outcome.
  5. Every side of the conversation is persisted (VoiceCallTurn) and
     the full transcript becomes a ticket after the call.

Honesty rules (non-negotiable, enforced via the system prompt):
  - NEVER claim an action was completed unless a tool result says so.
  - On tool failure/timeout: apologize, offer callback or human transfer.
  - Never invent order/account data.

Latency budget: voice callers wait in silence. The turn LLM call uses
the free fast backbone (Groq/Mistral via llm_call); tool execution is
capped at TOOL_TIMEOUT_SECONDS (below the provider webhook timeout) —
on timeout the caller gets an honest fallback, not dead air forever.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models.variant_engine import AIAgentAssignment
from database.models.voice_channel import (
    VoiceCall,
    VoiceCallTurn,
    VoiceChannelConfig,
    VoiceConversation,
)

logger = logging.getLogger("parwa.voice.engine")

# A caller should never wait longer than this for a tool result —
# Twilio's own webhook timeout is 15s; we stay safely below it.
TOOL_TIMEOUT_SECONDS = 12.0

# Hard cap on conversation turns per call (safety + cost guard).
MAX_TURNS_PER_CALL = 30

# The backbone client used by the 11-node pipeline (free fast providers).
# Imported with aliases so tests can monkeypatch cleanly.
from app.core.parwa_pipeline.llm_client import llm_call as _llm_call  # noqa: E402
from app.core.superglue_client import execute_tool as _execute_tool  # noqa: E402

# Spoken opt-out (TCPA BC-010) — handled instantly, no LLM needed.
_OPT_OUT_PATTERN = re.compile(
    r"\b(stop|stop calling|unsubscribe|opt out|opt-out|"
    r"do not call|don't call|do not call me|take me off)\b",
    re.IGNORECASE,
)


@dataclass
class VoiceTurnResult:
    """What the engine decided for one conversation turn."""

    say: str = ""                       # text to speak to the caller
    action: str = "continue"            # continue | transfer | end
    end_reason: str = ""                # resolved | unresolved | opt_out | error | max_turns
    tool_id: Optional[str] = None       # SuperGlue tool executed this turn
    tool_status: Optional[str] = None   # ok | failed | timeout | refused
    llm_turns_used: int = 0             # how many LLM calls this turn took


class VoiceConversationEngine:
    """Runs the live AI conversation for one tenant's voice calls."""

    def __init__(self, db: Session):
        self.db = db

    # ═══════════════════════════════════════════════════════════
    # Call start (no LLM — instant greeting)
    # ═══════════════════════════════════════════════════════════

    def start_call(
        self,
        company_id: str,
        call_sid: str,
        direction: str,
        from_number: str,
        to_number: str,
    ) -> VoiceTurnResult:
        """Open the conversation: greeting turn, no LLM latency."""
        config = self._get_config(company_id)
        greeting = (
            (config.greeting_message if config else None)
            or "Hello! Thanks for calling. I'm Parwa's AI assistant. "
               "How can I help you today?"
        )
        self._persist_turn(
            company_id=company_id,
            call_sid=call_sid,
            role="agent",
            text=greeting,
        )
        return VoiceTurnResult(say=greeting, action="continue")

    # ═══════════════════════════════════════════════════════════
    # One conversation turn
    # ═══════════════════════════════════════════════════════════

    async def handle_turn(
        self,
        company_id: str,
        call_sid: str,
        customer_text: str,
        from_number: str = "",
        to_number: str = "",
    ) -> VoiceTurnResult:
        """Process one customer utterance and decide what to do."""
        customer_text = (customer_text or "").strip()

        # Spoken opt-out (BC-010) — instant, no LLM, no persuasion.
        if customer_text and _OPT_OUT_PATTERN.search(customer_text):
            self._mark_opted_out(company_id, call_sid)
            reply = (
                "Understood. I've removed this number from our call list. "
                "You will not receive calls from us again. Goodbye."
            )
            self._persist_turn(company_id, call_sid, "customer", customer_text)
            self._persist_turn(company_id, call_sid, "agent", reply)
            return VoiceTurnResult(say=reply, action="end", end_reason="opt_out")

        self._persist_turn(company_id, call_sid, "customer", customer_text)

        # Turn guard — never let a call loop forever.
        turn_count = self._count_turns(company_id, call_sid)
        if turn_count >= MAX_TURNS_PER_CALL:
            reply = (
                "I'm sorry, this call is taking longer than expected. "
                "Let me have a colleague follow up with you. Goodbye."
            )
            self._persist_turn(company_id, call_sid, "agent", reply)
            return VoiceTurnResult(say=reply, action="end", end_reason="max_turns")

        # Load the tenant's agents + linked tools (the whitelist).
        agents = self._active_agents_with_tools(company_id)
        tool_catalog = self._build_tool_catalog(agents)

        # ── LLM decision call ────────────────────────────────────
        decision = await self._llm_decide(
            company_id=company_id,
            call_sid=call_sid,
            customer_text=customer_text,
            agents=agents,
            tool_catalog=tool_catalog,
        )

        # Malformed LLM output → safe honest fallback (never silent).
        if decision is None:
            reply = (
                "I'm sorry, I didn't quite catch that. "
                "Could you please say it again in a few words?"
            )
            self._persist_turn(company_id, call_sid, "agent", reply)
            return VoiceTurnResult(say=reply, action="continue", llm_turns_used=1)

        # ── Tool execution branch ────────────────────────────────
        tool_call = decision.get("tool_call") or None
        if tool_call and isinstance(tool_call, dict):
            tool_id = str(tool_call.get("tool_id", "") or "")
            tool_input = tool_call.get("input") or {}

            # Whitelist check — only THIS tenant's active agent tools.
            if tool_id not in {t["tool_id"] for t in tool_catalog}:
                logger.warning(
                    "voice_tool_refused_not_whitelisted tool=%s company=%s",
                    tool_id[:60], company_id,
                )
                self._persist_turn(
                    company_id, call_sid, "agent",
                    "", tool_id=tool_id, tool_status="refused",
                )
                reply = (
                    "I'm sorry, I don't have the ability to do that right now. "
                    "I can take a message and have the right person follow up, "
                    "or transfer you to a human colleague."
                )
                self._persist_turn(company_id, call_sid, "agent", reply)
                return VoiceTurnResult(
                    say=reply,
                    action="continue",
                    tool_id=tool_id,
                    tool_status="refused",
                    llm_turns_used=1,
                )

            ok, result_payload, tool_status = await self._execute_tool_safe(
                tool_id, tool_input, company_id
            )

            # Record the tool attempt, then let the LLM speak the REAL result.
            self._persist_turn(
                company_id, call_sid, "system",
                json.dumps(result_payload)[:2000],
                tool_id=tool_id,
                tool_status=tool_status,
            )

            final = await self._llm_speak_tool_result(
                company_id=company_id,
                call_sid=call_sid,
                agents=agents,
                tool_id=tool_id,
                tool_status=tool_status,
                tool_result=result_payload,
            )
            self._persist_turn(company_id, call_sid, "agent", final.say)
            final.tool_id = tool_id
            final.tool_status = tool_status
            final.llm_turns_used = 2
            return final

        # ── Plain reply / transfer / end branch ──────────────────
        say_text = str(decision.get("say", "") or "").strip()
        action = str(decision.get("action", "continue") or "continue").strip().lower()
        if action not in ("continue", "transfer", "end"):
            action = "continue"
        if not say_text:
            say_text = "I'm sorry, could you please repeat that?"

        # Transfer requested but tenant has no transfer number → honest
        # downgrade: keep helping, never pretend we transferred.
        if action == "transfer":
            config = self._get_config(company_id)
            if not (config and config.transfer_number):
                say_text = (
                    "I'm sorry, human transfer isn't available right now. "
                    "Let me take your details and have a colleague call you back. "
                ) + say_text
                action = "continue"

        self._persist_turn(company_id, call_sid, "agent", say_text)
        end_reason = ""
        if action == "end":
            end_reason = str(decision.get("end_reason", "") or "resolved")
        return VoiceTurnResult(
            say=say_text,
            action=action,
            end_reason=end_reason,
            llm_turns_used=1,
        )

    # ═══════════════════════════════════════════════════════════
    # Call end → summary + ticket
    # ═══════════════════════════════════════════════════════════

    def finish_call(
        self,
        company_id: str,
        call_sid: str,
        end_reason: str = "completed",
        duration_seconds: int = 0,
    ) -> Dict[str, Any]:
        """Sync wrapper for afinish_call — for sync callers (tests, CLI).

        Never call this from inside a running event loop; use
        `await engine.afinish_call(...)` there instead.
        """
        return asyncio.run(
            self.afinish_call(
                company_id=company_id,
                call_sid=call_sid,
                end_reason=end_reason,
                duration_seconds=duration_seconds,
            )
        )

    async def afinish_call(
        self,
        company_id: str,
        call_sid: str,
        end_reason: str = "completed",
        duration_seconds: int = 0,
    ) -> Dict[str, Any]:
        """Wrap up: persist transcript on the call, summarize, create ticket.

        Returns {"status", "ticket_id", "summary"} — best-effort; a
        summary/ticket failure never loses the transcript.
        """
        call = self._get_call(company_id, call_sid)
        turns = self._get_turns(company_id, call_sid)

        transcript_lines = [
            f"{'Customer' if t.role == 'customer' else ('AI Agent' if t.role == 'agent' else 'System')}: {t.text or ('[tool ' + (t.tool_id or '') + ' ' + (t.tool_status or '') + ']')}"
            for t in turns
            if t.role != "system" or t.tool_id
        ]
        transcript_text = "\n".join(transcript_lines)

        if call:
            call.transcript_json = transcript_text
            call.ended_at = datetime.now(timezone.utc)
            if duration_seconds:
                call.duration_seconds = duration_seconds
            call.status = "completed"
            call.resolution = end_reason if end_reason != "completed" else "resolved"
            self.db.commit()

        # LLM summary (short) — best-effort.
        summary = ""
        if transcript_text:
            try:
                summary = await _llm_call(
                    prompt=(
                        "Summarize this customer support phone call in "
                        "2-3 short sentences. State what the customer "
                        "wanted, what was done (be honest if nothing was "
                        "completed), and any follow-up needed.\n\n"
                        f"CALL TRANSCRIPT:\n{transcript_text[:4000]}"
                    ),
                    max_tokens=180,
                    temperature=0.2,
                    step_type="voice_summary",
                    ticket_id=call_sid,
                )
            except Exception as exc:
                logger.warning("voice_summary_llm_failed error=%s", str(exc)[:200])
                summary = transcript_text[:400]

        if call and summary:
            call.transcript_summary = summary
            self.db.commit()

        # Create the ticket — the call becomes a trackable support record.
        ticket_id = None
        if call and transcript_text:
            try:
                from app.services.ticket_service import TicketService

                service = TicketService(self.db, company_id)
                ticket = service.create_ticket(
                    channel="voice",
                    customer_phone=call.from_number,
                    customer_name=f"Voice caller {call.from_number[-4:]}",
                    subject=(
                        f"Voice call ({call.direction}) — "
                        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"
                    ),
                    description=transcript_text[:8000],
                    metadata_json={
                        "source": "voice_call",
                        "call_id": call.id,
                        "call_sid": call_sid,
                        "summary": summary,
                        "end_reason": end_reason,
                    },
                )
                ticket_id = getattr(ticket, "id", None)
                call.ticket_id = ticket_id
                self.db.commit()
            except Exception as exc:
                logger.warning(
                    "voice_ticket_create_failed error=%s", str(exc)[:200]
                )

        return {
            "status": "finished",
            "ticket_id": ticket_id,
            "summary": summary,
            "turns": len(turns),
        }

    # ═══════════════════════════════════════════════════════════
    # LLM calls
    # ═══════════════════════════════════════════════════════════

    def _system_prompt(self, agents: List[dict], tool_catalog: List[dict]) -> str:
        """The voice agent's system prompt — phone-native + honest."""
        agent_lines = []
        for a in agents[:5]:
            agent_lines.append(
                f"- {a['agent_name']} (handles: {', '.join(a['capabilities'])})"
                + (f" — instructions: {a['instructions'][:400]}" if a["instructions"] else "")
            )
        agents_block = "\n".join(agent_lines) if agent_lines else (
            "- General support agent (no specialist agents are configured yet)"
        )

        tool_lines = []
        for t in tool_catalog[:8]:
            tool_lines.append(
                f"- tool_id: {t['tool_id']}\n"
                f"  what it does: {t['description']}\n"
                f"  input: {t['input_hint']}"
            )
        tools_block = "\n".join(tool_lines) if tool_lines else (
            "- (no action tools are linked yet — you can only talk, "
            "not change anything)"
        )

        return (
            "You are Parwa, an AI customer support agent speaking on a LIVE "
            "PHONE CALL. You replace a human support agent.\n"
            "\n"
            "PHONE RULES:\n"
            "- Speak in short, simple sentences (this is spoken out loud).\n"
            "- One idea per response. Ask only ONE question at a time.\n"
            "- Plain words, no jargon, no markdown, no emojis, no lists.\n"
            "- Keep replies under 60 words unless reading back details.\n"
            "\n"
            "YOUR AGENTS:\n"
            f"{agents_block}\n"
            "\n"
            "ACTION TOOLS you may call (ONLY these — they are the only way "
            "to actually DO anything):\n"
            f"{tools_block}\n"
            "\n"
            "HONESTY RULES (most important):\n"
            "- NEVER say you did something unless a tool result in this "
            "conversation confirms it. No tool result = not done.\n"
            "- If a tool failed, say honestly it didn't work and offer a "
            "callback from a colleague or a human transfer.\n"
            "- NEVER invent order numbers, payment statuses, or account "
            "details.\n"
            "- If you cannot verify something, say so plainly.\n"
            "- If the caller asks something you truly cannot help with, "
            "use action \"transfer\" (a human will take over).\n"
            "\n"
            "RESPOND WITH ONLY THIS JSON (no other text):\n"
            '{"say": "<what to speak to the caller>", '
            '"tool_call": {"tool_id": "<id from the list>", "input": {...}} or null, '
            '"action": "continue" | "transfer" | "end", '
            '"end_reason": "resolved" | "unresolved" | "transfer" | "none"}\n'
            "\n"
            "Use tool_call ONLY when the caller wants an action (refund, "
            "booking, account change, lookup) and you have the input values. "
            "Otherwise reply with tool_call: null and action: \"continue\"."
        )

    def _turn_prompt(
        self,
        call_sid: str,
        company_id: str,
        customer_text: str,
    ) -> str:
        history = self._get_turns(company_id, call_sid)
        lines = []
        for t in history[-16:]:
            if t.role == "customer":
                lines.append(f"Caller: {t.text or ''}")
            elif t.role == "agent":
                lines.append(f"You said: {t.text or ''}")
            elif t.role == "system" and t.tool_id:
                lines.append(
                    f"[Tool {t.tool_id} → {t.tool_status}: {t.text or ''}]"
                )
        history_block = "\n".join(lines) if lines else "(call just started)"
        return (
            f"CONVERSATION SO FAR:\n{history_block}\n\n"
            f"The caller just said:\n\"{customer_text}\"\n\n"
            "Respond with the JSON object now."
        )

    async def _llm_decide(
        self,
        company_id: str,
        call_sid: str,
        customer_text: str,
        agents: List[dict],
        tool_catalog: List[dict],
    ) -> Optional[dict]:
        """First LLM call: decide reply / tool / transfer / end."""
        try:
            raw = await _llm_call(
                prompt=self._turn_prompt(call_sid, company_id, customer_text),
                system_prompt=self._system_prompt(agents, tool_catalog),
                max_tokens=400,
                temperature=0.3,
                step_type="voice_turn",
                ticket_id=call_sid,
            )
        except Exception as exc:
            logger.warning("voice_turn_llm_failed error=%s", str(exc)[:200])
            return None
        return self._parse_turn_json(raw)

    async def _llm_speak_tool_result(
        self,
        company_id: str,
        call_sid: str,
        agents: List[dict],
        tool_id: str,
        tool_status: str,
        tool_result: Dict[str, Any],
    ) -> VoiceTurnResult:
        """Second LLM call: tell the caller the REAL tool outcome."""
        try:
            raw = await _llm_call(
                prompt=(
                    f"{self._turn_prompt(call_sid, company_id, '')}\n\n"
                    f"The tool {tool_id} was just executed. Result status: "
                    f"{tool_status}. Raw result: "
                    f"{json.dumps(tool_result)[:1500]}\n\n"
                    "Tell the caller the outcome NOW, honestly:\n"
                    "- ok → say what was done, plainly.\n"
                    "- failed/timeout → apologize, say it didn't go through, "
                    "offer a callback from a colleague or a human transfer "
                    "(action: \"transfer\" if available, else \"continue\").\n"
                    "Respond with the JSON object now."
                ),
                system_prompt=self._system_prompt(agents, []),
                max_tokens=300,
                temperature=0.3,
                step_type="voice_turn_tool",
                ticket_id=call_sid,
            )
            decision = self._parse_turn_json(raw)
            if decision:
                action = str(decision.get("action", "continue") or "continue").lower()
                return VoiceTurnResult(
                    say=str(decision.get("say", "") or "").strip()
                    or "The request went through our system. Is there anything else I can help you with?",
                    action=action if action in ("continue", "transfer", "end") else "continue",
                )
        except Exception as exc:
            logger.warning("voice_tool_speak_failed error=%s", str(exc)[:200])

        # LLM unreachable after tool run → honest canned fallback.
        if tool_status == "ok":
            return VoiceTurnResult(
                say=(
                    "Done — the request went through. "
                    "Is there anything else I can help you with?"
                ),
                action="continue",
            )
        return VoiceTurnResult(
            say=(
                "I'm sorry, that didn't go through on our side. "
                "I'll have a colleague look into it and follow up with you."
            ),
            action="continue",
        )

    # ═══════════════════════════════════════════════════════════
    # Tool execution (timeout-guarded, whitelisted)
    # ═══════════════════════════════════════════════════════════

    async def _execute_tool_safe(
        self,
        tool_id: str,
        tool_input: Dict[str, Any],
        tenant_id: str,
    ) -> tuple:
        """Run a SuperGlue tool with a hard timeout.

        Returns (ok, result_payload, tool_status).
        """
        try:
            result = await asyncio.wait_for(
                _execute_tool(tool_id, tool_input, tenant_id=tenant_id),
                timeout=TOOL_TIMEOUT_SECONDS,
            )
            payload = (
                result if isinstance(result, dict)
                else {"raw": str(result)[:1000]}
            )
            ok = bool(
                payload.get("success")
                or payload.get("status") in ("success", "completed", "ok")
            )
            return ok, payload, ("ok" if ok else "failed")
        except asyncio.TimeoutError:
            logger.warning("voice_tool_timeout tool=%s", tool_id[:60])
            return False, {"error": "tool timeout", "tool_id": tool_id}, "timeout"
        except Exception as exc:
            logger.warning(
                "voice_tool_error tool=%s error=%s", tool_id[:60], str(exc)[:200]
            )
            return False, {"error": str(exc)[:500], "tool_id": tool_id}, "failed"

    # ═══════════════════════════════════════════════════════════
    # Parsing / persistence / tenant context
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _parse_turn_json(raw: str) -> Optional[dict]:
        """Parse the LLM's JSON decision, tolerating fences and prose."""
        if not raw:
            return None
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except Exception:
            pass
        # Find the outermost JSON object in the text.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end + 1])
                return data if isinstance(data, dict) else None
            except Exception:
                return None
        return None

    def _persist_turn(
        self,
        company_id: str,
        call_sid: str,
        role: str,
        text: str,
        tool_id: Optional[str] = None,
        tool_status: Optional[str] = None,
    ) -> None:
        call = self._get_call(company_id, call_sid)
        self.db.add(
            VoiceCallTurn(
                company_id=company_id,
                call_id=call.id if call else None,
                call_sid=call_sid,
                role=role,
                text=text or None,
                tool_id=tool_id,
                tool_status=tool_status,
            )
        )
        if call:
            call.status = "in-progress"
        self.db.commit()

    def _mark_opted_out(self, company_id: str, call_sid: str) -> None:
        call = self._get_call(company_id, call_sid)
        conversation_id = call.conversation_id if call else None
        if conversation_id:
            conv = (
                self.db.query(VoiceConversation)
                .filter(
                    VoiceConversation.id == conversation_id,
                    VoiceConversation.company_id == company_id,
                )
                .first()
            )
            if conv:
                conv.is_opted_out = True
                self.db.commit()
                logger.info(
                    "voice_opt_out_marked company=%s conversation=%s",
                    company_id, conversation_id,
                )

    def _count_turns(self, company_id: str, call_sid: str) -> int:
        return (
            self.db.query(VoiceCallTurn)
            .filter(
                VoiceCallTurn.company_id == company_id,
                VoiceCallTurn.call_sid == call_sid,
            )
            .count()
        )

    def _get_turns(self, company_id: str, call_sid: str) -> List[VoiceCallTurn]:
        return (
            self.db.query(VoiceCallTurn)
            .filter(
                VoiceCallTurn.company_id == company_id,
                VoiceCallTurn.call_sid == call_sid,
            )
            .order_by(VoiceCallTurn.created_at.asc(), VoiceCallTurn.id.asc())
            .all()
        )

    def _get_call(
        self, company_id: str, call_sid: str
    ) -> Optional[VoiceCall]:
        return (
            self.db.query(VoiceCall)
            .filter(
                VoiceCall.company_id == company_id,
                VoiceCall.twilio_call_sid == call_sid,
            )
            .first()
        )

    def _get_config(
        self, company_id: str
    ) -> Optional[VoiceChannelConfig]:
        return (
            self.db.query(VoiceChannelConfig)
            .filter(VoiceChannelConfig.company_id == company_id)
            .first()
        )

    def _active_agents_with_tools(self, company_id: str) -> List[dict]:
        """The tenant's active agents + their active SuperGlue tools.

        Same selection the text pipeline uses (status=active,
        superglue_tool_status=active) — voice and text share ONE brain.
        """
        agents = (
            self.db.query(AIAgentAssignment)
            .filter(
                AIAgentAssignment.company_id == company_id,
                AIAgentAssignment.status == "active",
            )
            .all()
        )
        result = []
        for a in agents:
            try:
                caps = json.loads(a.capabilities) if a.capabilities else []
            except Exception:
                caps = []
            result.append(
                {
                    "agent_name": a.agent_name,
                    "capabilities": caps,
                    "instructions": a.instructions or "",
                    "superglue_tool_id": (
                        a.superglue_tool_id
                        if a.superglue_tool_id
                        and a.superglue_tool_status == "active"
                        else None
                    ),
                }
            )
        return result

    def _build_tool_catalog(self, agents: List[dict]) -> List[dict]:
        """Human-readable catalog of the tenant's whitelisted tools."""
        catalog = []
        seen = set()
        for a in agents:
            tool_id = a.get("superglue_tool_id")
            if not tool_id or tool_id in seen:
                continue
            seen.add(tool_id)
            catalog.append(
                {
                    "tool_id": tool_id,
                    "description": (
                        f"Action tool for the '{a['agent_name']}' agent "
                        f"(handles: {', '.join(a['capabilities'][:4])}). "
                        + a["instructions"][:200]
                    ).strip(),
                    # Input schema unknown at this layer — the tool's own
                    # definition is authoritative; the LLM asks the caller
                    # for missing values and passes what it has.
                    "input_hint": (
                        "pass the values the caller gave you as JSON fields "
                        "(order id, amount, email, phone etc. — only what "
                        "they actually provided)"
                    ),
                }
            )
        return catalog

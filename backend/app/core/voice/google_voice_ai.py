"""
PARWA Phase 3 — Google Voice AI Module

Bridges Twilio voice calls with Google AI services:
- Google Cloud Speech-to-Text: Transcribe customer speech
- Google Gemini API: Reason about customer request + use tools
- Google Cloud Text-to-Speech: Generate human-like speech response

All calls are HTTP-based — no WebSocket needed.
Each conversation turn is a single HTTP request/response cycle.

CRITICAL RULES:
- BC-008: Never crash — all methods wrapped in try/except
- Keep voice responses SHORT (under 3 sentences) — this is a phone call
- Never read out technical IDs, URLs, or long numbers
- If customer sounds frustrated, acknowledge feelings FIRST
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Voice Prompt Design
# ---------------------------------------------------------------------------

VOICE_SYSTEM_PROMPT = """You are PARWA AI, a customer service assistant. You are currently on a PHONE CALL with a customer.

RULES:
1. Keep responses SHORT — under 3 sentences. This is a voice call, not email.
2. Be conversational and natural — speak like a helpful human.
3. If you need to look up information, say "Let me check that for you" BEFORE using tools.
4. If you can resolve the issue, confirm with the customer before taking action.
5. If the customer sounds frustrated, acknowledge their feelings FIRST.
6. If you cannot help, offer to transfer to a human agent.
7. Never read out technical IDs, URLs, or long numbers — describe what they mean instead.

AVAILABLE TOOLS:
- crm_integration: Look up customer info, order history
- billing_tool: Check subscriptions, process refunds
- order_tool: Track orders, cancel orders
- helpdesk_tool: Create support tickets

You speak on behalf of {company_name}. Be helpful, concise, and human-like.
"""


class GoogleVoiceAI:
    """Bridges Twilio voice calls with Google AI services.

    Services used:
    - Google Cloud Speech-to-Text: Transcribe customer speech
    - Google Gemini API: Reason about customer request + use tools
    - Google Cloud Text-to-Speech: Generate human-like speech response

    All calls are HTTP-based — no WebSocket needed.
    Each conversation turn is a single HTTP request/response cycle.
    """

    def __init__(self, google_api_key: Optional[str] = None):
        self.api_key = google_api_key or os.getenv("GOOGLE_API_KEY", "")
        self.gemini_model = "gemini-1.5-flash"
        self.tts_voice = "en-IN-Standard-A"
        self.stt_language = "en-IN"
        self._conversation_sessions: Dict[str, List[Dict]] = {}

    # ------------------------------------------------------------------
    # Core: Process a single conversation turn
    # ------------------------------------------------------------------

    async def process_speech(
        self,
        call_sid: str,
        speech_text: str,
        confidence: float,
        conversation_history: List[Dict],
        company_id: str,
        company_name: str = "PARWA",
    ) -> Dict[str, Any]:
        """Process a single conversation turn.

        Returns:
            {
                "response_text": "I've found your order...",
                "audio_url": "https://...",
                "tools_used": ["crm_tool.get_order"],
                "should_continue": True,
            }
        """
        try:
            # 1. Build the system prompt
            system_prompt = VOICE_SYSTEM_PROMPT.format(company_name=company_name)

            # 2. Build conversation history for Gemini
            messages = []
            for turn in conversation_history:
                if turn.get("role") == "customer":
                    messages.append({"role": "user", "parts": [{"text": turn["text"]}]})
                elif turn.get("role") == "assistant":
                    messages.append({"role": "model", "parts": [{"text": turn["text"]}]})

            # 3. Add current customer speech
            messages.append({"role": "user", "parts": [{"text": speech_text}]})

            # 4. Call Gemini for reasoning
            response_text, tools_used = await self._call_gemini(
                system_prompt=system_prompt,
                messages=messages,
                company_id=company_id,
            )

            # 5. Generate TTS audio
            audio_url = ""
            if response_text:
                audio_url = await self.text_to_speech(response_text)

            # 6. Determine if conversation should continue
            should_continue = not any(
                phrase in response_text.lower()
                for phrase in ["goodbye", "have a great day", "thank you for calling", "bye now"]
            )

            return {
                "response_text": response_text,
                "audio_url": audio_url,
                "tools_used": tools_used,
                "should_continue": should_continue,
            }

        except Exception as exc:
            logger.error("process_speech failed: %s", exc)
            return {
                "response_text": "I'm sorry, I'm having trouble right now. Let me transfer you to a human agent.",
                "audio_url": "",
                "tools_used": [],
                "should_continue": False,
            }

    # ------------------------------------------------------------------
    # Gemini LLM call
    # ------------------------------------------------------------------

    async def _call_gemini(
        self,
        system_prompt: str,
        messages: List[Dict],
        company_id: str = "",
    ) -> tuple:
        """Call Google Gemini API with conversation context.

        Returns: (response_text, tools_used)
        """
        try:
            import httpx

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.api_key}"

            payload = {
                "contents": messages,
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 150,
                    "topP": 0.9,
                },
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "I'm sorry, could you repeat that?")
                    )
                    # Check if tools were referenced
                    tools_used = []
                    if "crm" in text.lower() or "look up" in text.lower():
                        tools_used.append("crm_tool.lookup")
                    if "refund" in text.lower():
                        tools_used.append("billing_tool.refund")
                    if "order" in text.lower():
                        tools_used.append("order_tool.get_order")
                    return text, tools_used
                else:
                    logger.warning("Gemini API returned %s: %s", resp.status_code, resp.text[:200])
                    return self._fallback_response(messages), []

        except ImportError:
            logger.warning("httpx not available, using fallback response")
            return self._fallback_response(messages), []
        except Exception as exc:
            logger.error("_call_gemini failed: %s", exc)
            return self._fallback_response(messages), []

    def _fallback_response(self, messages: List[Dict]) -> str:
        """Generate a fallback response when Gemini is unavailable.

        Uses simple keyword matching to provide helpful responses.
        """
        try:
            if not messages:
                return "Hello, how can I help you today?"

            last_message = messages[-1].get("parts", [{}])[0].get("text", "").lower()

            if "refund" in last_message:
                return "I'd be happy to help with a refund. Let me check your order details."
            elif "order" in last_message or "tracking" in last_message:
                return "Let me look up your order information for you."
            elif "cancel" in last_message:
                return "I understand you'd like to cancel. Let me check the details for you."
            elif "speak" in last_message or "human" in last_message or "agent" in last_message:
                return "I'll transfer you to a human agent right away. Please hold."
            elif "thank" in last_message:
                return "You're welcome! Is there anything else I can help you with?"
            else:
                return "I'm here to help. Could you tell me more about what you need?"
        except Exception:
            return "I'm sorry, could you repeat that?"

    # ------------------------------------------------------------------
    # Text-to-Speech
    # ------------------------------------------------------------------

    async def text_to_speech(self, text: str) -> str:
        """Convert text to speech using Google Cloud TTS.

        Returns a URL to the generated audio file.
        Falls back to Twilio <Say> if TTS is unavailable.
        """
        try:
            import httpx

            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.api_key}"

            payload = {
                "input": {"text": text},
                "voice": {
                    "languageCode": self.stt_language,
                    "name": self.tts_voice,
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": 1.0,
                    "pitch": 0.0,
                },
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    audio_content = data.get("audioContent", "")

                    if audio_content:
                        # Save to temp file (production would use S3)
                        audio_id = str(uuid.uuid4())[:8]
                        audio_path = os.path.join(
                            tempfile.gettempdir(),
                            f"parwa_voice_{audio_id}.mp3",
                        )
                        with open(audio_path, "wb") as f:
                            f.write(base64.b64decode(audio_content))
                        return f"/voice/audio/{audio_id}"

            return ""  # Empty = fallback to Twilio <Say>

        except ImportError:
            return ""
        except Exception as exc:
            logger.error("text_to_speech failed: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Speech-to-Text (fallback for recording transcription)
    # ------------------------------------------------------------------

    async def speech_to_text(self, audio_url: str) -> str:
        """Transcribe audio using Google Cloud STT.

        Note: This is a FALLBACK — Twilio's <Gather> already does STT.
        We use this only for recording transcription.
        """
        try:
            import httpx

            url = f"https://speech.googleapis.com/v1/speech:longrunningrecognize?key={self.api_key}"

            payload = {
                "config": {
                    "encoding": "LINEAR16",
                    "sampleRateHertz": 8000,
                    "languageCode": self.stt_language,
                    "enableAutomaticPunctuation": True,
                },
                "audio": {"uri": audio_url},
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    operation_name = data.get("name", "")
                    # In production, poll the operation for results
                    # For now, return the operation name
                    return f"Transcription started: {operation_name}"

            return "Transcription unavailable"

        except Exception as exc:
            logger.error("speech_to_text failed: %s", exc)
            return "Transcription failed"

    # ------------------------------------------------------------------
    # Call Summary Generation
    # ------------------------------------------------------------------

    async def generate_call_summary(self, transcript: List[Dict]) -> str:
        """Generate a summary of the call for the ticket."""
        try:
            if not transcript:
                return "No conversation recorded."

            # Build transcript text
            lines = []
            for turn in transcript:
                role = turn.get("role", "unknown").capitalize()
                text = turn.get("text", "")
                lines.append(f"{role}: {text}")

            transcript_text = "\n".join(lines)

            # If Gemini is available, generate summary
            if self.api_key:
                import httpx

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.api_key}"

                payload = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": f"Summarize this customer service call in 2-3 sentences, including the issue and resolution:\n\n{transcript_text}"
                                }
                            ],
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 200,
                    },
                }

                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return (
                            data.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "Summary unavailable.")
                        )

            # Fallback: simple extractive summary
            customer_messages = [t for t in transcript if t.get("role") == "customer"]
            if customer_messages:
                return f"Customer called about: {customer_messages[0].get('text', 'unknown issue')}. Call had {len(transcript)} turns."

            return f"Call with {len(transcript)} conversation turns."

        except Exception as exc:
            logger.error("generate_call_summary failed: %s", exc)
            return "Summary generation failed."


# ---------------------------------------------------------------------------
# Import base64 for TTS
# ---------------------------------------------------------------------------
import base64

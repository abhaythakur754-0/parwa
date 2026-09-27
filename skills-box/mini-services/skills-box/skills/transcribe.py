"""POST /transcribe — voice notes → text. faster-whisper base int8 (safe RAM).

Request:  {"audio_base64": "...", "fmt": "webm|mp3|wav|...", "language": null,
           "timeout_s": 30}
Response data: {"text", "language", "language_probability", "duration_s",
                "segments": [{start,end,text}]}

Start on base int8; upgrade to small only if voice quality feels weak
(WHISPER_MODEL=small env — no code change).
"""
from __future__ import annotations

import base64
import logging
import os
import tempfile
import threading
from typing import Optional

from core import config
from core.registry import registry

log = logging.getLogger("skills.transcribe")
_infer_lock = threading.Lock()


def _load():
    from faster_whisper import WhisperModel

    return WhisperModel(
        config.WHISPER_MODEL, device="cpu", compute_type=config.WHISPER_COMPUTE
    )


registry.register("transcribe", _load)


def ensure():
    """Load the model (untimed) — inference below is what the timeout covers."""
    return registry.get("transcribe")


def infer(model, audio_base64: str, fmt: str = "webm",
          language: Optional[str] = None) -> dict:
    raw = base64.b64decode(audio_base64, validate=False)
    if not raw:
        raise ValueError("audio_base64 decoded to zero bytes")
    if len(raw) > 25 * 1024 * 1024:
        raise ValueError("audio too large (>25MB) — trim the clip")

    suffix = "." + (fmt or "bin").lstrip(".").replace("/", "_")[:10]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        path = tmp.name
    try:
        with _infer_lock:
            segments, info = model.transcribe(
                path, language=language, beam_size=1, vad_filter=False
            )
            segs, texts = [], []
            for s in segments:  # generator — consumes model time here
                segs.append({"start": round(s.start, 2),
                             "end": round(s.end, 2),
                             "text": s.text})
                texts.append(s.text.strip())
        return {
            "text": " ".join(t for t in texts if t).strip(),
            "language": getattr(info, "language", None),
            "language_probability": round(float(getattr(info, "language_probability", 0) or 0), 3),
            "duration_s": round(float(getattr(info, "duration", 0) or 0), 2),
            "segments": segs[:50],
        }
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

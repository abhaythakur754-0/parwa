"""POST /speak — text → voice. Piper TTS (binary first, python lib fallback).

Request:  {"text": "...", "voice": null}
Response data: {"audio_base64", "format": "wav", "voice": "en_US-lessac-medium"}

Piper is local, fast, tiny (~60MB voice). No cloud, no LLM.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

from core import config
from core.registry import registry

log = logging.getLogger("skills.speak")
_infer_lock = threading.Lock()

DEFAULT_VOICE = "en_US-lessac-medium"
VOICE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
    "en/en_US/lessac/medium/{name}"
)
MODELS_DIR = config.BASE_DIR / "models" / "piper"
BIN_CANDIDATES = [
    config.BASE_DIR / "bin" / "piper" / "piper",
    Path("/usr/local/bin/piper"),
]


def _find_bin() -> str | None:
    if config.PIPER_BIN and Path(config.PIPER_BIN).is_file():
        return config.PIPER_BIN
    for c in BIN_CANDIDATES:
        if c.is_file():
            return str(c)
    found = shutil.which("piper")
    return found or None


def _voice_path() -> Path:
    if config.PIPER_VOICE and Path(config.PIPER_VOICE).is_file():
        return Path(config.PIPER_VOICE)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{DEFAULT_VOICE}.onnx"
    path = MODELS_DIR / name
    if not path.is_file():
        import requests

        log.info("downloading piper voice %s", DEFAULT_VOICE)
        # name already ends in .onnx — second file is name + ".json"
        for suffix in ("", ".json"):
            url = VOICE_URL.format(name=name + suffix)
            res = requests.get(url, timeout=120)
            res.raise_for_status()
            (MODELS_DIR / (name + suffix)).write_bytes(res.content)
    return path


def _load():
    voice = _voice_path()
    bin_path = _find_bin()
    if bin_path:
        log.info("piper mode=bin bin=%s voice=%s", bin_path, voice)
        return {"mode": "bin", "bin": bin_path, "voice": str(voice)}
    try:  # python fallback
        from piper import PiperVoice  # type: ignore

        v = PiperVoice.load(str(voice))
        log.info("piper mode=python voice=%s", voice)
        return {"mode": "python", "voice_obj": v, "voice": str(voice)}
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"piper unavailable (no binary, no python lib): {exc}"
        ) from exc


registry.register("speak", _load)


def speak(text: str, voice: str | None = None) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("text is empty")
    if len(text) > 5000:
        raise ValueError("text too long for one utterance (>5000 chars)")

    obj = registry.get("speak")
    voice_name = DEFAULT_VOICE
    with _infer_lock:
        if obj["mode"] == "bin":
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                out_path = tmp.name
            try:
                cmd = [obj["bin"], "--model", obj["voice"], "--output_file", out_path]
                subprocess.run(
                    cmd, input=text.encode("utf-8"), timeout=120,
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                audio = Path(out_path).read_bytes()
            finally:
                try:
                    os.unlink(out_path)
                except OSError:
                    pass
        else:
            buf = io.BytesIO()
            w = wave.open(buf, "wb")
            try:
                obj["voice_obj"].synthesize(text, w)
            finally:
                w.close()
            audio = buf.getvalue()

    return {
        "audio_base64": base64.b64encode(audio).decode("ascii"),
        "format": "wav",
        "voice": voice_name,
    }

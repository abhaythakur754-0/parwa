"""POST /translate — Argos Translate (en↔de/fr/es/it/pt preloaded).

Request:  {"text": "...", "target": "de", "source": "en"}
Response data: {"text", "source", "target"}
"""
from __future__ import annotations

import logging
import threading

from core import config
from core.registry import registry

log = logging.getLogger("skills.translate")

_translators: dict = {}
_tlock = threading.Lock()

# translators are light (ctranslate2) — no heavy-model registry needed,
# but keep a placeholder so /health shows the capability.
registry.register("translate", lambda: True)


def _translator(source: str, target: str):
    import argostranslate.package

    installed = {
        (p.from_code, p.to_code)
        for p in argostranslate.package.get_installed_packages()
    }
    if (source, target) not in installed:
        raise ValueError(
            f"no argos model for {source}->{target}; "
            f"installed pairs: {sorted(f'{a}->{b}' for a, b in installed) or ['none']}"
        )
    return True  # module-level translate() resolves + caches internally


def translate(text: str, target: str, source: str = "en") -> dict:
    text = (text or "")[: config.MAX_TEXT_CHARS].strip()
    if not text:
        raise ValueError("text is empty")
    source = (source or "en").lower()[:5]
    target = (target or "").lower()[:5]
    if not target:
        raise ValueError("target language is required")
    if source == target:
        return {"text": text, "source": source, "target": target}
    _translator(source, target)
    import argostranslate.translate

    out = argostranslate.translate.translate(text, source, target)
    return {"text": out, "source": source, "target": target}

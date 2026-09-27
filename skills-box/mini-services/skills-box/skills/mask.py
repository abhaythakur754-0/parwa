"""POST /mask — PII masking. Presidio (smart) + regex floor (never fails).

Request:  {"text": "...", "entities": [...optional preset names...]}
Response data: {"masked": "...", "engine": "presidio"|"regex",
                "found": [{"label","text"}], "count": N}

Default Presidio entities: EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD,
US_SSN, IBAN_CODE, IP_ADDRESS, URL. (PERSON/LOCATION available on request
via the "entities" param — they are noisy, so off by default.)
"""
from __future__ import annotations

import logging
import threading
from typing import List, Optional

from core import config
from core.registry import registry
from . import regex_floor

log = logging.getLogger("skills.mask")
_infer_lock = threading.Lock()

DEFAULT_ENTITIES = [
    "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
    "US_SSN", "IBAN_CODE", "IP_ADDRESS", "URL",
]
_REGEX_ONLY = "REGEX_ONLY"


def _load():
    """Try Presidio with spaCy sm. Any failure → sentinel (regex floor)."""
    try:
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_analyzer.predefined_recognizers import SpacyRecognizer
        from presidio_analyzer.pattern import Pattern
        from presidio_analyzer.pattern_recognizer import PatternRecognizer

        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        })
        nlp = provider.create_engine()
        registry_ = RecognizerRegistry(supported_languages=["en"])
        registry_.load_predefined_recognizers(nlp_engine=nlp, languages=["en"])
        # SSN without context words — customer-care tickets rarely say
        # "social security number"; Presidio's stock US_SSN needs context.
        registry_.add_recognizer(PatternRecognizer(
            supported_entity="US_SSN",
            name="US_SSN_no_context",
            patterns=[Pattern("ssn-dashes", r"\b\d{3}-\d{2}-\d{4}\b", 0.85)],
        ))
        # SpacyRecognizer default gives noisy PERSON — engine NER only used
        # for the default set which excludes PERSON anyway.
        registry_.remove_recognizer("SpacyRecognizer")
        registry_.add_recognizer(SpacyRecognizer(check_label_groups=False))
        engine = AnalyzerEngine(
            nlp_engine=nlp,
            registry=registry_,
            supported_languages=["en"],
        )
        # smoke test — prove spaCy model actually works
        engine.analyze(text="contact a@b.com", language="en", entities=["EMAIL_ADDRESS"])
        return engine
    except Exception as exc:  # noqa: BLE001
        log.warning("presidio/spacy unavailable (%s) — using regex floor", exc)
        return _REGEX_ONLY


registry.register("mask", _load)


def mask(text: str, entities: Optional[List[str]] = None) -> dict:
    text = (text or "")[: config.MAX_TEXT_CHARS]
    if not text:
        raise ValueError("text is empty")

    obj = registry.get("mask")
    # regex floor = the promise "mask never fails": use it when presidio is
    # unavailable OR the guard returned nothing usable (memory-pressure edge)
    if obj is None or (isinstance(obj, str) and obj == _REGEX_ONLY):
        masked, found = regex_floor.redact(text, entities)
        return {"masked": masked, "engine": "regex",
                "found": found, "count": len(found)}

    use = entities or DEFAULT_ENTITIES
    with _infer_lock:
        results = obj.analyze(text=text, entities=use, language="en")
        from presidio_anonymizer import AnonymizerEngine
        from presidio_anonymizer.entities import OperatorConfig

        operators = {e: OperatorConfig("replace", {"new_value": f"<{e}>"}) for e in use}
        anon = AnonymizerEngine().anonymize(
            text=text, analyzer_results=list(results), operators=operators
        )

    # found = what was ACTUALLY replaced (no overlapping ghosts)
    found = [
        {"label": it.entity_type, "text": it.text}
        for it in (anon.items or [])
    ]
    return {"masked": anon.text, "engine": "presidio",
            "found": found, "count": len(found)}

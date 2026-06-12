"""PARWA Phase 3 Ingestion — Normalizer registry and exports.

All normalizer classes are exported here so the orchestrator and
external consumers can import from a single location.

Usage::

    from app.core.ingestion.normalizers import (
        BaseNormalizer,
        GenericEmailNormalizer,
        GenericSMSNormalizer,
        GenericVoiceNormalizer,
        GenericChatNormalizer,
        GenericWebhookNormalizer,
        FieldMapping,
        PROVIDER_FIELD_MAPPINGS,
    )
"""

from .base import BaseNormalizer
from .field_mapping import FieldMapping, PROVIDER_FIELD_MAPPINGS
from .generic_normalizers import (
    GenericChatNormalizer,
    GenericEmailNormalizer,
    GenericSMSNormalizer,
    GenericVoiceNormalizer,
    GenericWebhookNormalizer,
)

__all__ = [
    # Base
    "BaseNormalizer",
    # Field mapping
    "FieldMapping",
    "PROVIDER_FIELD_MAPPINGS",
    # Generic fallback normalizers (category-first)
    "GenericEmailNormalizer",
    "GenericSMSNormalizer",
    "GenericVoiceNormalizer",
    "GenericChatNormalizer",
    "GenericWebhookNormalizer",
]

"""
Smart Router Intent Module - Week 35
Intent Detection Enhancement for 93%+ accuracy
"""

from .detector import IntentDetector
from .entity_extractor import EntityExtractor
from .slot_filler import SlotFiller
from .intent_classifier import IntentClassifier

__all__ = [
    'IntentDetector',
    'EntityExtractor',
    'SlotFiller',
    'IntentClassifier',
]

__version__ = '1.0.0'

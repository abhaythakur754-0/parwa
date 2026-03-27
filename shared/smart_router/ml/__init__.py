"""
Smart Router ML Module - Week 35
ML-Based Routing Classifier for 92%+ accuracy
"""

from .classifier import MLRouter, QueryType, TierPrediction
from .feature_extractor import FeatureExtractor
from .training_data import TrainingDataBuilder
from .model_registry import ModelRegistry

__all__ = [
    'MLRouter',
    'QueryType',
    'TierPrediction',
    'FeatureExtractor',
    'TrainingDataBuilder',
    'ModelRegistry',
]

__version__ = '1.0.0'

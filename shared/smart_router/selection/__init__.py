"""
Smart Router Selection Module - Week 35
Dynamic Model Selection for cost and latency optimization
"""

from .model_selector import ModelSelector
from .cost_optimizer import CostOptimizer
from .latency_manager import LatencyManager
from .fallback_chain import FallbackChain

__all__ = [
    'ModelSelector',
    'CostOptimizer',
    'LatencyManager',
    'FallbackChain',
]

__version__ = '1.0.0'

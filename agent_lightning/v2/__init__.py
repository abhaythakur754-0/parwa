"""Agent Lightning v2 - Enhanced Training with Collective Intelligence"""

from .enhanced_training_config import EnhancedTrainingConfig, get_enhanced_config
from .collective_dataset_builder import CollectiveDatasetBuilder

__all__ = [
    "EnhancedTrainingConfig",
    "get_enhanced_config",
    "CollectiveDatasetBuilder"
]

__version__ = "2.0.0"

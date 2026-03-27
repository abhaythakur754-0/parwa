"""
Data Augmentor for Agent Lightning 94% Training.

Provides data augmentation techniques for training data.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
import random
import re

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AugmentationConfig:
    """Configuration for data augmentation."""
    synonym_replacement_prob: float = 0.3
    paraphrase_prob: float = 0.2
    noise_injection_prob: float = 0.1
    max_augmentations_per_sample: int = 3
    preserve_labels: bool = True


# Synonym maps for customer service terms
SYNONYMS = {
    "refund": ["money back", "reimbursement", "repayment"],
    "order": ["purchase", "transaction", "item"],
    "shipping": ["delivery", "shipment", "dispatch"],
    "return": ["send back", "exchange"],
    "cancel": ["stop", "abort", "terminate"],
    "problem": ["issue", "trouble", "difficulty"],
    "help": ["assist", "support", "aid"],
    "broken": ["damaged", "defective", "faulty"],
    "late": ["delayed", "overdue"],
    "manager": ["supervisor", "boss", "lead"],
}


class DataAugmentor:
    """
    Data augmentation for training data.
    
    Techniques:
    - Synonym replacement
    - Paraphrasing
    - Noise injection
    - Balanced sampling
    """
    
    def __init__(self, config: Optional[AugmentationConfig] = None):
        """Initialize augmentor."""
        self.config = config or AugmentationConfig()
        self._augmentation_count = 0
    
    def augment_sample(
        self,
        query: str,
        label: int,
        category: Optional[str] = None
    ) -> List[Tuple[str, int, Optional[str]]]:
        """Generate augmented versions of a sample."""
        augmented = [(query, label, category)]
        
        if len(query) < 5:
            return augmented
        
        # Synonym replacement
        if random.random() < self.config.synonym_replacement_prob:
            aug_query = self._synonym_replacement(query)
            if aug_query != query:
                augmented.append((aug_query, label, category))
        
        # Paraphrasing
        if random.random() < self.config.paraphrase_prob:
            aug_query = self._paraphrase(query)
            if aug_query != query:
                augmented.append((aug_query, label, category))
        
        self._augmentation_count += len(augmented) - 1
        return augmented[:self.config.max_augmentations_per_sample + 1]
    
    def augment_dataset(
        self,
        samples: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Augment entire dataset."""
        augmented = []
        
        for sample in samples:
            query = sample.get("query", "")
            label = sample.get("label", 0)
            category = sample.get("category")
            
            for aug_query, aug_label, aug_cat in self.augment_sample(query, label, category):
                augmented.append({
                    "query": aug_query,
                    "label": aug_label,
                    "category": aug_cat,
                    "augmented": aug_query != query
                })
        
        logger.info({
            "event": "dataset_augmented",
            "original": len(samples),
            "augmented": len(augmented)
        })
        
        return augmented
    
    def _synonym_replacement(self, query: str) -> str:
        """Replace words with synonyms."""
        words = query.lower().split()
        
        for i, word in enumerate(words):
            if word in SYNONYMS and random.random() < 0.5:
                words[i] = random.choice(SYNONYMS[word])
        
        return " ".join(words)
    
    def _paraphrase(self, query: str) -> str:
        """Apply paraphrase transformations."""
        result = query.lower()
        
        patterns = [
            (r"i want", "i would like"),
            (r"i need", "i require"),
            (r"can you", "could you"),
            (r"how do i", "how can i"),
        ]
        
        for pattern, replacement in patterns:
            if re.search(pattern, result) and random.random() < 0.5:
                result = re.sub(pattern, replacement, result)
                break
        
        return result


def augment_training_data(
    samples: List[Dict[str, Any]],
    config: Optional[AugmentationConfig] = None
) -> List[Dict[str, Any]]:
    """Quick function to augment training data."""
    augmentor = DataAugmentor(config)
    return augmentor.augment_dataset(samples)

"""
Training Data Builder for ML Router
Collects historical queries and generates training datasets
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import random
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrainingSample:
    """Single training sample"""
    query: str
    label: str
    features: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Dataset:
    """Training dataset container"""
    train: List[TrainingSample] = field(default_factory=list)
    validation: List[TrainingSample] = field(default_factory=list)
    test: List[TrainingSample] = field(default_factory=list)
    label_distribution: Dict[str, int] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class TrainingDataBuilder:
    """
    Builds training datasets from historical queries.
    Handles label generation, augmentation, and balanced sampling.
    """
    
    # Default split ratios
    TRAIN_RATIO = 0.7
    VALIDATION_RATIO = 0.15
    TEST_RATIO = 0.15
    
    # Label categories
    LABEL_CATEGORIES = [
        'faq', 'refund', 'complex', 'urgent', 'billing', 'technical', 'general'
    ]
    
    # Augmentation patterns
    AUGMENTATION_SYNONYMS = {
        'refund': ['return', 'money back', 'reimbursement'],
        'cancel': ['stop', 'end', 'terminate'],
        'order': ['purchase', 'transaction', 'buy'],
        'help': ['assist', 'support', 'aid'],
        'problem': ['issue', 'trouble', 'difficulty'],
    }
    
    def __init__(self, output_dir: str = "/tmp/training_data"):
        self.output_dir = output_dir
        self._historical_queries: List[Dict[str, Any]] = []
        self._generated_samples: List[TrainingSample] = []
    
    def collect_historical_queries(
        self, 
        queries: List[Dict[str, Any]]
    ) -> int:
        """
        Collect historical queries for training.
        
        Args:
            queries: List of query dictionaries with text and outcomes
            
        Returns:
            Number of queries collected
        """
        collected = 0
        for query in queries:
            if self._validate_query(query):
                self._historical_queries.append(query)
                collected += 1
        
        logger.info(f"Collected {collected} historical queries")
        return collected
    
    def _validate_query(self, query: Dict[str, Any]) -> bool:
        """Validate query has required fields."""
        required = ['text']
        return all(k in query for k in required)
    
    def generate_labels_from_outcomes(
        self, 
        queries: Optional[List[Dict[str, Any]]] = None
    ) -> List[TrainingSample]:
        """
        Generate labels from query outcomes.
        
        Args:
            queries: Queries to label (uses historical if not provided)
            
        Returns:
            List of labeled training samples
        """
        queries = queries or self._historical_queries
        samples = []
        
        for query in queries:
            # Determine label from outcome
            label = self._infer_label(query)
            
            sample = TrainingSample(
                query=query['text'],
                label=label,
                features=query.get('features', {}),
                metadata={
                    'client_id': query.get('client_id'),
                    'resolution_status': query.get('resolution_status'),
                    'escalated': query.get('escalated', False),
                }
            )
            samples.append(sample)
        
        self._generated_samples = samples
        logger.info(f"Generated {len(samples)} labeled samples")
        return samples
    
    def _infer_label(self, query: Dict[str, Any]) -> str:
        """Infer label from query content and outcome."""
        text = query.get('text', '').lower()
        outcome = query.get('outcome', {})
        
        # Priority based on outcome
        if outcome.get('escalated'):
            return 'complex'
        if outcome.get('refund_issued'):
            return 'refund'
        if outcome.get('urgent_flag'):
            return 'urgent'
        
        # Content-based labeling
        label_scores = {}
        for label in self.LABEL_CATEGORIES:
            score = self._calculate_label_score(text, label)
            label_scores[label] = score
        
        # Return highest scoring label
        return max(label_scores, key=label_scores.get)
    
    def _calculate_label_score(self, text: str, label: str) -> float:
        """Calculate score for a label given query text."""
        label_patterns = {
            'faq': ['what', 'how do', 'how to', 'where', 'when', 'policy'],
            'refund': ['refund', 'return', 'money back', 'cancel'],
            'complex': ['integrate', 'api', 'multiple', 'escalate', 'manager'],
            'urgent': ['urgent', 'asap', 'immediately', 'emergency', 'critical'],
            'billing': ['charge', 'invoice', 'payment', 'bill', 'subscription'],
            'technical': ['error', 'bug', 'crash', 'not working', 'failed'],
            'general': ['help', 'question', 'need', 'want'],
        }
        
        patterns = label_patterns.get(label, [])
        return sum(1 for p in patterns if p in text)
    
    def augment_data(
        self, 
        samples: Optional[List[TrainingSample]] = None,
        factor: int = 2
    ) -> List[TrainingSample]:
        """
        Augment training data with variations.
        
        Args:
            samples: Samples to augment (uses generated if not provided)
            factor: Multiplication factor for augmentation
            
        Returns:
            Augmented sample list
        """
        samples = samples or self._generated_samples
        augmented = list(samples)
        
        for sample in samples:
            for _ in range(factor - 1):
                # Create variation
                new_query = self._create_variation(sample.query)
                
                new_sample = TrainingSample(
                    query=new_query,
                    label=sample.label,
                    features=sample.features.copy(),
                    metadata={'augmented': True, **sample.metadata}
                )
                augmented.append(new_sample)
        
        logger.info(f"Augmented {len(samples)} samples to {len(augmented)}")
        return augmented
    
    def _create_variation(self, query: str) -> str:
        """Create a variation of the query."""
        words = query.split()
        
        # Apply synonym replacement
        for i, word in enumerate(words):
            word_lower = word.lower()
            if word_lower in self.AUGMENTATION_SYNONYMS:
                synonyms = self.AUGMENTATION_SYNONYMS[word_lower]
                words[i] = random.choice(synonyms)
        
        return ' '.join(words)
    
    def create_balanced_dataset(
        self, 
        samples: Optional[List[TrainingSample]] = None
    ) -> List[TrainingSample]:
        """
        Create balanced dataset with equal label distribution.
        
        Args:
            samples: Samples to balance (uses generated if not provided)
            
        Returns:
            Balanced sample list
        """
        samples = samples or self._generated_samples
        
        # Group by label
        by_label: Dict[str, List[TrainingSample]] = {}
        for sample in samples:
            if sample.label not in by_label:
                by_label[sample.label] = []
            by_label[sample.label].append(sample)
        
        # Find minimum count
        min_count = min(len(s) for s in by_label.values()) if by_label else 0
        
        # Sample equally from each label
        balanced = []
        for label, label_samples in by_label.items():
            sampled = random.sample(label_samples, min(min_count, len(label_samples)))
            balanced.extend(sampled)
        
        # Shuffle
        random.shuffle(balanced)
        
        logger.info(f"Created balanced dataset with {len(balanced)} samples")
        return balanced
    
    def split_dataset(
        self, 
        samples: Optional[List[TrainingSample]] = None,
        train_ratio: float = None,
        validation_ratio: float = None,
        test_ratio: float = None
    ) -> Dataset:
        """
        Split dataset into train/validation/test.
        
        Args:
            samples: Samples to split (uses generated if not provided)
            train_ratio: Train split ratio
            validation_ratio: Validation split ratio
            test_ratio: Test split ratio
            
        Returns:
            Dataset with train/validation/test splits
        """
        samples = samples or self._generated_samples
        
        # Use defaults if not provided
        train_ratio = train_ratio or self.TRAIN_RATIO
        validation_ratio = validation_ratio or self.VALIDATION_RATIO
        test_ratio = test_ratio or self.TEST_RATIO
        
        # Shuffle samples
        shuffled = list(samples)
        random.shuffle(shuffled)
        
        # Calculate split indices
        n = len(shuffled)
        train_end = int(n * train_ratio)
        val_end = train_end + int(n * validation_ratio)
        
        # Split
        train = shuffled[:train_end]
        validation = shuffled[train_end:val_end]
        test = shuffled[val_end:]
        
        # Calculate label distribution
        label_dist: Dict[str, int] = {}
        for sample in samples:
            label_dist[sample.label] = label_dist.get(sample.label, 0) + 1
        
        dataset = Dataset(
            train=train,
            validation=validation,
            test=test,
            label_distribution=label_dist
        )
        
        logger.info(f"Split dataset: {len(train)} train, {len(validation)} val, {len(test)} test")
        return dataset
    
    def export_to_training_format(
        self, 
        dataset: Dataset,
        format_type: str = "json"
    ) -> Dict[str, Any]:
        """
        Export dataset to training format.
        
        Args:
            dataset: Dataset to export
            format_type: Output format (json, csv)
            
        Returns:
            Exported data dictionary
        """
        def samples_to_dict(samples: List[TrainingSample]) -> List[Dict[str, Any]]:
            return [
                {
                    'query': s.query,
                    'label': s.label,
                    'features': s.features,
                    'metadata': s.metadata,
                }
                for s in samples
            ]
        
        exported = {
            'train': samples_to_dict(dataset.train),
            'validation': samples_to_dict(dataset.validation),
            'test': samples_to_dict(dataset.test),
            'label_distribution': dataset.label_distribution,
            'created_at': dataset.created_at,
            'stats': {
                'total_samples': len(dataset.train) + len(dataset.validation) + len(dataset.test),
                'train_size': len(dataset.train),
                'validation_size': len(dataset.validation),
                'test_size': len(dataset.test),
            }
        }
        
        return exported
    
    def generate_synthetic_samples(
        self,
        label: str,
        count: int
    ) -> List[TrainingSample]:
        """
        Generate synthetic samples for a specific label.
        
        Args:
            label: Label to generate samples for
            count: Number of samples to generate
            
        Returns:
            List of synthetic samples
        """
        templates = {
            'faq': [
                "What is your return policy?",
                "How do I track my order?",
                "Where is my package?",
                "When will my order arrive?",
                "How can I contact support?",
            ],
            'refund': [
                "I want a refund for my order",
                "How do I return this item?",
                "I need my money back",
                "Can I get a refund please?",
                "The product was damaged, I want a refund",
            ],
            'complex': [
                "I need help with API integration",
                "Can you escalate this to a manager?",
                "I have multiple issues with my account",
                "This requires technical assistance",
                "I need custom configuration help",
            ],
            'urgent': [
                "This is urgent, I need help now!",
                "Emergency: my account is locked",
                "ASAP help needed for failed payment",
                "Critical issue with my order",
                "I need immediate assistance",
            ],
            'billing': [
                "I was charged twice",
                "Question about my invoice",
                "Payment failed for subscription",
                "Billing error on my account",
                "Need to update payment method",
            ],
            'technical': [
                "The app keeps crashing",
                "Error when trying to login",
                "Page not loading correctly",
                "Bug in the checkout process",
                "Connection timeout issues",
            ],
            'general': [
                "I need help",
                "Can you assist me?",
                "I have a question",
                "Need some information",
                "Looking for support",
            ],
        }
        
        label_templates = templates.get(label, templates['general'])
        samples = []
        
        for _ in range(count):
            template = random.choice(label_templates)
            sample = TrainingSample(
                query=template,
                label=label,
                features={'synthetic': True},
                metadata={'synthetic': True}
            )
            samples.append(sample)
        
        return samples
    
    def get_stats(self) -> Dict[str, Any]:
        """Get training data statistics."""
        label_dist: Dict[str, int] = {}
        for sample in self._generated_samples:
            label_dist[sample.label] = label_dist.get(sample.label, 0) + 1
        
        return {
            'historical_queries': len(self._historical_queries),
            'generated_samples': len(self._generated_samples),
            'label_distribution': label_dist,
        }

"""
Collective Dataset Builder for Agent Lightning v2

Builds training datasets from collective intelligence across multiple clients:
- Aggregates training data from all 5 clients
- Privacy-preserving data combination
- Industry-balanced dataset
- Cross-client pattern inclusion
- Target: 500+ training examples
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import random


@dataclass
class TrainingExample:
    """Single training example"""
    id: str
    input_text: str
    output_text: str
    category: str
    industry: str
    client_id: str  # Will be anonymized
    quality_score: float
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DatasetStatistics:
    """Dataset statistics"""
    total_examples: int
    by_industry: Dict[str, int]
    by_category: Dict[str, int]
    avg_quality_score: float
    date_range: Tuple[str, str]
    clients_included: int


class CollectiveDatasetBuilder:
    """Builds collective training datasets from multiple clients"""
    
    INDUSTRIES = ["ecommerce", "saas", "healthcare", "logistics", "fintech"]
    
    def __init__(
        self,
        output_dir: str = "datasets/collective",
        min_examples_per_industry: int = 50,
        target_total: int = 500
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.min_examples_per_industry = min_examples_per_industry
        self.target_total = target_total
        self._examples: List[TrainingExample] = []
        self._client_mapping: Dict[str, str] = {}  # Real ID -> Anonymized ID
    
    def add_client_data(
        self,
        client_id: str,
        industry: str,
        mistakes: List[Dict],
        approvals: List[Dict]
    ) -> int:
        """Add training data from a specific client"""
        
        # Create anonymized client ID
        anon_id = self._anonymize_client_id(client_id)
        self._client_mapping[client_id] = anon_id
        
        count = 0
        
        # Process mistakes (negative examples for learning)
        for mistake in mistakes:
            example = TrainingExample(
                id=self._generate_id(),
                input_text=self._sanitize_input(mistake.get("input", "")),
                output_text=self._sanitize_output(mistake.get("correct_output", "")),
                category=mistake.get("category", "general"),
                industry=industry,
                client_id=anon_id,
                quality_score=mistake.get("quality_score", 0.8),
                timestamp=mistake.get("timestamp", datetime.utcnow().isoformat()),
                metadata={"type": "mistake", "original_error": mistake.get("error_type")}
            )
            self._examples.append(example)
            count += 1
        
        # Process approvals (positive examples)
        for approval in approvals:
            example = TrainingExample(
                id=self._generate_id(),
                input_text=self._sanitize_input(approval.get("input", "")),
                output_text=self._sanitize_output(approval.get("output", "")),
                category=approval.get("category", "general"),
                industry=industry,
                client_id=anon_id,
                quality_score=approval.get("quality_score", 0.9),
                timestamp=approval.get("timestamp", datetime.utcnow().isoformat()),
                metadata={"type": "approval", "approved_by": "system"}
            )
            self._examples.append(example)
            count += 1
        
        return count
    
    def add_patterns(self, patterns: List[Dict]) -> int:
        """Add cross-client patterns (anonymized)"""
        count = 0
        
        for pattern in patterns:
            example = TrainingExample(
                id=self._generate_id(),
                input_text=pattern.get("pattern_input", ""),
                output_text=pattern.get("pattern_output", ""),
                category=pattern.get("category", "pattern"),
                industry=pattern.get("applicable_industries", "all"),
                client_id="collective",  # Pattern from collective intelligence
                quality_score=pattern.get("confidence", 0.85),
                timestamp=datetime.utcnow().isoformat(),
                metadata={"type": "pattern", "pattern_id": pattern.get("id")}
            )
            self._examples.append(example)
            count += 1
        
        return count
    
    def build_balanced_dataset(
        self,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1
    ) -> Tuple[List[TrainingExample], List[TrainingExample], List[TrainingExample]]:
        """Build balanced train/val/test splits"""
        
        # Group by industry
        by_industry = defaultdict(list)
        for example in self._examples:
            by_industry[example.industry].append(example)
        
        # Balance across industries
        balanced = []
        max_per_industry = self.target_total // len(self.INDUSTRIES)
        
        for industry in self.INDUSTRIES:
            industry_examples = by_industry.get(industry, [])
            random.shuffle(industry_examples)
            balanced.extend(industry_examples[:max_per_industry])
        
        # Shuffle all
        random.shuffle(balanced)
        
        # Split
        total = len(balanced)
        train_end = int(total * train_ratio)
        val_end = train_end + int(total * val_ratio)
        
        train = balanced[:train_end]
        val = balanced[train_end:val_end]
        test = balanced[val_end:]
        
        return train, val, test
    
    def export_to_jsonl(
        self,
        examples: List[TrainingExample],
        filename: str
    ) -> Path:
        """Export examples to JSONL format"""
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            for example in examples:
                data = asdict(example)
                f.write(json.dumps(data) + '\n')
        
        return filepath
    
    def export_for_openai(
        self,
        examples: List[TrainingExample],
        filename: str
    ) -> Path:
        """Export in OpenAI fine-tuning format"""
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            for example in examples:
                data = {
                    "messages": [
                        {"role": "system", "content": "You are a helpful customer support AI assistant."},
                        {"role": "user", "content": example.input_text},
                        {"role": "assistant", "content": example.output_text}
                    ]
                }
                f.write(json.dumps(data) + '\n')
        
        return filepath
    
    def get_statistics(self) -> DatasetStatistics:
        """Get dataset statistics"""
        
        by_industry = defaultdict(int)
        by_category = defaultdict(int)
        quality_scores = []
        timestamps = []
        clients = set()
        
        for example in self._examples:
            by_industry[example.industry] += 1
            by_category[example.category] += 1
            quality_scores.append(example.quality_score)
            timestamps.append(example.timestamp)
            clients.add(example.client_id)
        
        timestamps.sort()
        
        return DatasetStatistics(
            total_examples=len(self._examples),
            by_industry=dict(by_industry),
            by_category=dict(by_category),
            avg_quality_score=sum(quality_scores) / len(quality_scores) if quality_scores else 0,
            date_range=(timestamps[0] if timestamps else "", timestamps[-1] if timestamps else ""),
            clients_included=len(clients)
        )
    
    def validate_privacy(self) -> Tuple[bool, List[str]]:
        """Validate that no PII/PHI is present"""
        issues = []
        
        for example in self._examples:
            # Check for real client IDs (should be anonymized)
            if example.client_id.startswith("client_"):
                issues.append(f"Non-anonymized client ID found: {example.client_id}")
            
            # Check for potential PII patterns
            text = example.input_text + example.output_text
            
            # SSN pattern
            import re
            if re.search(r'\b\d{3}-\d{2}-\d{4}\b', text):
                issues.append(f"Potential SSN found in example {example.id}")
            
            # Email pattern (if not already redacted)
            if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
                if not any(x in text for x in ["[EMAIL-REDACTED]", "[REDACTED]", "example.com"]):
                    issues.append(f"Potential email found in example {example.id}")
        
        return len(issues) == 0, issues
    
    def _anonymize_client_id(self, client_id: str) -> str:
        """Create anonymized client ID"""
        hash_val = hashlib.sha256(client_id.encode()).hexdigest()[:8]
        return f"anon_{hash_val}"  # Use 'anon_' prefix to distinguish from real client IDs
    
    def _generate_id(self) -> str:
        """Generate unique example ID"""
        import uuid
        return f"ex_{uuid.uuid4().hex[:12]}"
    
    def _sanitize_input(self, text: str) -> str:
        """Sanitize input text (remove PII)"""
        import re
        
        # Remove SSN
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED]', text)
        
        # Remove email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL-REDACTED]', text)
        
        # Remove phone numbers
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE-REDACTED]', text)
        
        return text
    
    def _sanitize_output(self, text: str) -> str:
        """Sanitize output text"""
        return self._sanitize_input(text)


def build_collective_dataset(
    clients_data: Dict[str, Dict],
    output_dir: str = "datasets/collective"
) -> Tuple[Path, DatasetStatistics]:
    """
    Convenience function to build collective dataset
    
    Args:
        clients_data: Dict mapping client_id to {"industry": str, "mistakes": list, "approvals": list}
        output_dir: Output directory
    
    Returns:
        Tuple of (output_path, statistics)
    """
    builder = CollectiveDatasetBuilder(output_dir=output_dir)
    
    for client_id, data in clients_data.items():
        builder.add_client_data(
            client_id=client_id,
            industry=data.get("industry", "general"),
            mistakes=data.get("mistakes", []),
            approvals=data.get("approvals", [])
        )
    
    train, val, test = builder.build_balanced_dataset()
    
    # Export all splits
    builder.export_for_openai(train, "train.jsonl")
    builder.export_for_openai(val, "val.jsonl")
    builder.export_for_openai(test, "test.jsonl")
    
    stats = builder.get_statistics()
    
    # Export stats
    stats_path = Path(output_dir) / "statistics.json"
    with open(stats_path, 'w') as f:
        json.dump(asdict(stats), f, indent=2)
    
    return stats_path, stats

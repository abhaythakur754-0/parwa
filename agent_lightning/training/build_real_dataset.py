"""
Build Real Dataset for Training.

Combines mistakes and approvals to create a balanced training dataset
for Agent Lightning fine-tuning.
"""
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DatasetStats:
    """Statistics about the built dataset."""
    total_examples: int
    train_examples: int
    val_examples: int
    mistakes_count: int
    approvals_count: int
    balance_ratio: float
    categories: Dict[str, int]
    clients: Dict[str, int]


class DatasetBuilder:
    """Builds training datasets from mistakes and approvals."""

    def __init__(
        self,
        output_dir: str = "./agent_lightning/datasets",
        validation_split: float = 0.2,
        balance_dataset: bool = True,
        shuffle: bool = True,
        seed: int = 42
    ):
        """Initialize dataset builder."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.validation_split = validation_split
        self.balance_dataset = balance_dataset
        self.shuffle = shuffle
        self.seed = seed
        random.seed(seed)

    def load_jsonl(self, filepath: str) -> List[Dict[str, Any]]:
        """Load examples from a JSONL file."""
        examples = []
        with open(filepath, 'r') as f:
            for line in f:
                if line.strip():
                    examples.append(json.loads(line))
        return examples

    def balance_examples(
        self,
        mistakes: List[Dict],
        approvals: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """Balance mistakes and approvals to 50/50 split."""
        if not self.balance_dataset:
            return mistakes, approvals

        min_count = min(len(mistakes), len(approvals))

        if len(mistakes) > min_count:
            mistakes = random.sample(mistakes, min_count)
        if len(approvals) > min_count:
            approvals = random.sample(approvals, min_count)

        logger.info(f"Balanced dataset: {len(mistakes)} mistakes, {len(approvals)} approvals")
        return mistakes, approvals

    def combine_and_shuffle(
        self,
        mistakes: List[Dict],
        approvals: List[Dict]
    ) -> List[Dict]:
        """Combine mistakes and approvals and shuffle."""
        combined = []

        # Add mistakes with label
        for m in mistakes:
            combined.append({
                **m,
                "label": "mistake_correction",
                "weight": 1.5  # Give mistakes slightly more weight
            })

        # Add approvals with label
        for a in approvals:
            combined.append({
                **a,
                "label": "correct_decision",
                "weight": 1.0
            })

        if self.shuffle:
            random.shuffle(combined)

        return combined

    def split_dataset(
        self,
        examples: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """Split into training and validation sets."""
        if not examples:
            return [], []

        split_idx = int(len(examples) * (1 - self.validation_split))
        train = examples[:split_idx]
        val = examples[split_idx:]

        return train, val

    def build_dataset(
        self,
        mistakes_path: str,
        approvals_path: str,
        output_name: Optional[str] = None
    ) -> DatasetStats:
        """
        Build complete training dataset from mistakes and approvals.

        Args:
            mistakes_path: Path to mistakes JSONL file
            approvals_path: Path to approvals JSONL file
            output_name: Optional name for output files

        Returns:
            Dataset statistics
        """
        logger.info("Building training dataset...")

        # Load data
        mistakes = self.load_jsonl(mistakes_path)
        approvals = self.load_jsonl(approvals_path)

        logger.info(f"Loaded {len(mistakes)} mistakes, {len(approvals)} approvals")

        # Balance if needed
        mistakes, approvals = self.balance_examples(mistakes, approvals)

        # Combine and shuffle
        combined = self.combine_and_shuffle(mistakes, approvals)

        # Split
        train, val = self.split_dataset(combined)

        # Generate output names
        if output_name is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_name = f"dataset_{timestamp}"

        # Save train set
        train_path = self.output_dir / f"{output_name}_train.jsonl"
        with open(train_path, 'w') as f:
            for example in train:
                f.write(json.dumps(example) + '\n')

        # Save validation set
        val_path = self.output_dir / f"{output_name}_val.jsonl"
        with open(val_path, 'w') as f:
            for example in val:
                f.write(json.dumps(example) + '\n')

        # Calculate statistics
        categories: Dict[str, int] = {}
        clients: Dict[str, int] = {}

        for ex in combined:
            cat = ex.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

            # Extract client from metadata if available
            metadata = ex.get("metadata", {})
            client = metadata.get("client_id", "unknown")
            clients[client] = clients.get(client, 0) + 1

        stats = DatasetStats(
            total_examples=len(combined),
            train_examples=len(train),
            val_examples=len(val),
            mistakes_count=len(mistakes),
            approvals_count=len(approvals),
            balance_ratio=len(mistakes) / len(approvals) if approvals else 0,
            categories=categories,
            clients=clients
        )

        logger.info(f"Dataset built: {stats.train_examples} train, {stats.val_examples} val")

        return stats

    def validate_dataset(self, train_path: str, val_path: str) -> Dict[str, Any]:
        """Validate the built dataset for quality."""
        train_examples = self.load_jsonl(train_path)
        val_examples = self.load_jsonl(val_path)

        issues = []

        # Check minimum sizes
        if len(train_examples) < 10:
            issues.append(f"Training set too small: {len(train_examples)}")
        if len(val_examples) < 2:
            issues.append(f"Validation set too small: {len(val_examples)}")

        # Check for required fields
        required_fields = ["input", "output"]
        for i, ex in enumerate(train_examples[:10]):  # Check first 10
            for field in required_fields:
                if field not in ex:
                    issues.append(f"Missing field '{field}' in train example {i}")

        # Check for empty content
        empty_count = sum(1 for ex in train_examples if not ex.get("input") or not ex.get("output"))
        if empty_count > 0:
            issues.append(f"{empty_count} examples with empty input/output")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "train_count": len(train_examples),
            "val_count": len(val_examples),
            "validation_timestamp": datetime.utcnow().isoformat()
        }


def build_training_dataset(
    mistakes_path: str,
    approvals_path: str,
    output_dir: str = "./agent_lightning/datasets",
    validation_split: float = 0.2,
    balance: bool = True
) -> Dict[str, Any]:
    """
    Main function to build training dataset.

    Args:
        mistakes_path: Path to mistakes JSONL
        approvals_path: Path to approvals JSONL
        output_dir: Output directory
        validation_split: Validation split ratio
        balance: Whether to balance dataset

    Returns:
        Build results with statistics
    """
    builder = DatasetBuilder(
        output_dir=output_dir,
        validation_split=validation_split,
        balance_dataset=balance
    )

    stats = builder.build_dataset(mistakes_path, approvals_path)

    # Validate
    train_path = str(builder.output_dir / "dataset_train.jsonl")
    val_path = str(builder.output_dir / "dataset_val.jsonl")

    # Find the actual files
    import glob
    train_files = sorted(glob.glob(str(builder.output_dir / "*_train.jsonl")))
    val_files = sorted(glob.glob(str(builder.output_dir / "*_val.jsonl")))

    validation = {}
    if train_files and val_files:
        validation = builder.validate_dataset(train_files[-1], val_files[-1])

    return {
        "success": True,
        "statistics": {
            "total_examples": stats.total_examples,
            "train_examples": stats.train_examples,
            "val_examples": stats.val_examples,
            "mistakes_count": stats.mistakes_count,
            "approvals_count": stats.approvals_count,
            "balance_ratio": stats.balance_ratio,
            "categories": stats.categories,
        },
        "validation": validation,
        "output_dir": str(builder.output_dir),
    }


if __name__ == "__main__":
    # Example usage
    result = build_training_dataset(
        mistakes_path="./agent_lightning/exports/mistakes_ft_20240101_120000.jsonl",
        approvals_path="./agent_lightning/exports/approvals_ft_20240101_120000.jsonl"
    )
    print(json.dumps(result, indent=2))

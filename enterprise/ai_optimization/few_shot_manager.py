"""Few-Shot Manager Module - Week 55, Builder 5"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import random

logger = logging.getLogger(__name__)


class ExampleSelectionStrategy(Enum):
    SIMILARITY = "similarity"
    RANDOM = "random"
    DIVERSITY = "diversity"
    SEQUENTIAL = "sequential"


@dataclass
class Example:
    input: str
    output: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input": self.input,
            "output": self.output,
            "metadata": self.metadata,
        }


class FewShotManager:
    def __init__(self, default_strategy: ExampleSelectionStrategy = ExampleSelectionStrategy.SIMILARITY):
        self.default_strategy = default_strategy
        self.examples: List[Example] = []
        self._example_count = 3

    def add_example(self, input_text: str, output_text: str, metadata: Optional[Dict[str, Any]] = None) -> Example:
        example = Example(
            input=input_text,
            output=output_text,
            metadata=metadata or {},
        )
        self.examples.append(example)
        logger.debug(f"Added example: {input_text[:50]}...")
        return example

    def add_examples(self, examples: List[tuple]) -> int:
        count = 0
        for input_text, output_text in examples:
            self.add_example(input_text, output_text)
            count += 1
        return count

    def get_examples(self, count: Optional[int] = None, strategy: Optional[ExampleSelectionStrategy] = None,
                     query: Optional[str] = None) -> List[Example]:
        if not self.examples:
            return []

        num = count or self._example_count
        strat = strategy or self.default_strategy

        if len(self.examples) <= num:
            return self.examples.copy()

        if strat == ExampleSelectionStrategy.RANDOM:
            return random.sample(self.examples, num)
        elif strat == ExampleSelectionStrategy.SEQUENTIAL:
            return self.examples[:num]
        elif strat == ExampleSelectionStrategy.DIVERSITY:
            return self._select_diverse(num)
        elif strat == ExampleSelectionStrategy.SIMILARITY:
            return self._select_similar(num, query)
        return self.examples[:num]

    def _select_diverse(self, count: int) -> List[Example]:
        # Select examples with diverse lengths
        sorted_examples = sorted(self.examples, key=lambda e: len(e.input))
        step = len(sorted_examples) // count
        selected = [sorted_examples[i * step] for i in range(count)]
        return selected

    def _select_similar(self, count: int, query: Optional[str]) -> List[Example]:
        # Simplified similarity - keyword matching
        if not query:
            return self.examples[:count]

        query_words = set(query.lower().split())
        scored = []
        for example in self.examples:
            example_words = set(example.input.lower().split())
            score = len(query_words & example_words)
            scored.append((score, example))

        scored.sort(reverse=True, key=lambda x: x[0])
        return [e for _, e in scored[:count]]

    def set_example_count(self, count: int) -> None:
        self._example_count = max(1, count)

    def remove_example(self, index: int) -> bool:
        if 0 <= index < len(self.examples):
            del self.examples[index]
            return True
        return False

    def clear_examples(self) -> None:
        self.examples.clear()

    def format_examples(self, examples: Optional[List[Example]] = None, format_type: str = "default") -> str:
        to_format = examples or self.examples
        if not to_format:
            return ""

        lines = []
        for i, example in enumerate(to_format):
            if format_type == "qa":
                lines.append(f"Q: {example.input}")
                lines.append(f"A: {example.output}")
            else:
                lines.append(f"Input: {example.input}")
                lines.append(f"Output: {example.output}")
            lines.append("")

        return "\n".join(lines)

    def count(self) -> int:
        return len(self.examples)

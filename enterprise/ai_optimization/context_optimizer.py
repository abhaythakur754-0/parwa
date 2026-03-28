"""Context Optimizer Module - Week 55, Builder 4"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    TRUNCATION = "truncation"
    SUMMARIZATION = "summarization"
    PRIORITIZATION = "prioritization"


@dataclass
class ContextWindow:
    max_tokens: int = 4096
    current_tokens: int = 0
    content: List[str] = field(default_factory=list)

    @property
    def available_tokens(self) -> int:
        return self.max_tokens - self.current_tokens

    @property
    def utilization(self) -> float:
        return self.current_tokens / self.max_tokens if self.max_tokens > 0 else 0


class ContextOptimizer:
    def __init__(self, max_tokens: int = 4096, strategy: OptimizationStrategy = OptimizationStrategy.TRUNCATION):
        self.default_max_tokens = max_tokens
        self.strategy = strategy
        self._token_ratio = 4  # Approximate chars per token

    def optimize(self, content: List[str], max_tokens: Optional[int] = None) -> ContextWindow:
        window = ContextWindow(max_tokens=max_tokens or self.default_max_tokens)
        total_chars = sum(len(c) for c in content)
        estimated_tokens = total_chars // self._token_ratio

        if estimated_tokens <= window.max_tokens:
            window.content = content
            window.current_tokens = estimated_tokens
            return window

        if self.strategy == OptimizationStrategy.TRUNCATION:
            window = self._truncate(content, window)
        elif self.strategy == OptimizationStrategy.SUMMARIZATION:
            window = self._summarize(content, window)
        elif self.strategy == OptimizationStrategy.PRIORITIZATION:
            window = self._prioritize(content, window)

        return window

    def _truncate(self, content: List[str], window: ContextWindow) -> ContextWindow:
        result = []
        current = 0
        for item in content:
            tokens = len(item) // self._token_ratio
            if current + tokens <= window.max_tokens:
                result.append(item)
                current += tokens
            else:
                break
        window.content = result
        window.current_tokens = current
        return window

    def _summarize(self, content: List[str], window: ContextWindow) -> ContextWindow:
        # Simplified summarization - take first part of each item
        result = []
        current = 0
        for item in content:
            max_item_tokens = (window.max_tokens - current) // max(1, len(content) - len(result))
            truncated = item[:max_item_tokens * self._token_ratio]
            tokens = len(truncated) // self._token_ratio
            if current + tokens <= window.max_tokens:
                result.append(truncated)
                current += tokens
        window.content = result
        window.current_tokens = current
        return window

    def _prioritize(self, content: List[str], window: ContextWindow) -> ContextWindow:
        # Prioritize shorter, more important items
        sorted_content = sorted(content, key=lambda x: len(x))
        return self._truncate(sorted_content, window)

    def count_tokens(self, text: str) -> int:
        return len(text) // self._token_ratio

    def set_strategy(self, strategy: OptimizationStrategy) -> None:
        self.strategy = strategy

"""
Context Window Optimization Module for Week 55 Advanced AI Optimization.

This module provides context window optimization capabilities including
token counting, management, and various optimization strategies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import re
import logging

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """Strategies for optimizing context window usage."""
    TRUNCATION = "truncation"
    SUMMARIZATION = "summarization"
    PRIORITIZATION = "prioritization"


@dataclass
class ContextWindow:
    """
    Represents a context window with token limits.
    
    Attributes:
        max_tokens: Maximum token capacity
        current_usage: Current token usage
        reserved_tokens: Tokens reserved for system use
    """
    max_tokens: int
    current_usage: int = 0
    reserved_tokens: int = 0
    
    @property
    def available_tokens(self) -> int:
        """Calculate available tokens."""
        return max(0, self.max_tokens - self.current_usage - self.reserved_tokens)
    
    @property
    def utilization(self) -> float:
        """Calculate utilization percentage (0-100)."""
        if self.max_tokens == 0:
            return 0.0
        return (self.current_usage / self.max_tokens) * 100
    
    def can_fit(self, token_count: int) -> bool:
        """Check if tokens can fit in available space."""
        return token_count <= self.available_tokens
    
    def allocate(self, token_count: int) -> bool:
        """Allocate tokens in the window. Returns success status."""
        if not self.can_fit(token_count):
            return False
        self.current_usage += token_count
        return True
    
    def release(self, token_count: int) -> None:
        """Release tokens from the window."""
        self.current_usage = max(0, self.current_usage - token_count)
    
    def reset(self) -> None:
        """Reset the window to initial state."""
        self.current_usage = 0


@dataclass
class TokenBlock:
    """
    Represents a block of tokens with metadata.
    
    Attributes:
        content: The text content
        token_count: Number of tokens in the block
        priority: Priority level (higher = more important)
        category: Category for organization
        metadata: Additional metadata
    """
    content: str
    token_count: int
    priority: int = 0
    category: str = "general"
    metadata: dict = field(default_factory=dict)
    
    def __lt__(self, other: "TokenBlock") -> bool:
        """Compare by priority (higher priority first)."""
        return self.priority > other.priority


@dataclass
class OptimizationResult:
    """
    Result of context optimization.
    
    Attributes:
        optimized_content: The optimized content
        original_tokens: Original token count
        optimized_tokens: Optimized token count
        strategy: Strategy used
        compression_ratio: Compression achieved
        removed_blocks: Blocks that were removed/summarized
    """
    optimized_content: str
    original_tokens: int
    optimized_tokens: int
    strategy: OptimizationStrategy
    compression_ratio: float = 0.0
    removed_blocks: list = field(default_factory=list)
    
    @property
    def tokens_saved(self) -> int:
        """Calculate tokens saved."""
        return self.original_tokens - self.optimized_tokens


class TokenCounter:
    """Utility class for counting tokens in text."""
    
    # Approximate tokens per word ratio (GPT-style)
    TOKENS_PER_WORD = 1.3
    # Characters per token approximation
    CHARS_PER_TOKEN = 4
    
    @classmethod
    def count_tokens(cls, text: str) -> int:
        """
        Count tokens in text using approximation.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Approximate token count
        """
        if not text:
            return 0
        
        # Count words
        words = len(text.split())
        word_tokens = int(words * cls.TOKENS_PER_WORD)
        
        # Count special characters (code, punctuation)
        special_chars = len(re.findall(r'[^\w\s]', text))
        
        # Count numbers (often split into multiple tokens)
        numbers = len(re.findall(r'\d+', text))
        
        return word_tokens + special_chars + numbers
    
    @classmethod
    def estimate_tokens_for_messages(cls, messages: list[dict]) -> int:
        """
        Estimate tokens for a list of messages.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            Estimated token count
        """
        total = 0
        for msg in messages:
            # Role token
            total += 1
            # Content tokens
            content = msg.get("content", "")
            total += cls.count_tokens(content)
            # Message overhead
            total += 4
        return total


class ContextOptimizer:
    """
    Main class for optimizing context windows.
    
    Provides methods to optimize context using various strategies
    including truncation, summarization, and prioritization.
    """
    
    def __init__(
        self,
        max_tokens: int = 4096,
        strategy: OptimizationStrategy = OptimizationStrategy.PRIORITIZATION,
        reserved_tokens: int = 500
    ):
        """
        Initialize the context optimizer.
        
        Args:
            max_tokens: Maximum context window size
            strategy: Default optimization strategy
            reserved_tokens: Tokens reserved for system/response
        """
        self.context_window = ContextWindow(
            max_tokens=max_tokens,
            reserved_tokens=reserved_tokens
        )
        self.default_strategy = strategy
        self.blocks: list[TokenBlock] = []
        self._optimization_history: list[OptimizationResult] = []
    
    def add_block(
        self,
        content: str,
        priority: int = 0,
        category: str = "general",
        metadata: Optional[dict] = None
    ) -> TokenBlock:
        """
        Add a content block to the optimizer.
        
        Args:
            content: Text content
            priority: Priority level (higher = more important)
            category: Category for organization
            metadata: Additional metadata
            
        Returns:
            Created TokenBlock
        """
        token_count = TokenCounter.count_tokens(content)
        block = TokenBlock(
            content=content,
            token_count=token_count,
            priority=priority,
            category=category,
            metadata=metadata or {}
        )
        self.blocks.append(block)
        self.context_window.current_usage += token_count
        return block
    
    def remove_block(self, block: TokenBlock) -> bool:
        """
        Remove a block from the optimizer.
        
        Args:
            block: Block to remove
            
        Returns:
            True if block was found and removed
        """
        if block in self.blocks:
            self.blocks.remove(block)
            self.context_window.current_usage -= block.token_count
            return True
        return False
    
    def clear_blocks(self) -> None:
        """Clear all blocks."""
        self.blocks.clear()
        self.context_window.reset()
    
    def optimize(
        self,
        strategy: Optional[OptimizationStrategy] = None,
        target_tokens: Optional[int] = None
    ) -> OptimizationResult:
        """
        Optimize the context using the specified strategy.
        
        Args:
            strategy: Strategy to use (defaults to instance default)
            target_tokens: Target token count (defaults to available space)
            
        Returns:
            OptimizationResult with optimized content
        """
        strategy = strategy or self.default_strategy
        target_tokens = target_tokens or self.context_window.available_tokens
        
        original_tokens = self.context_window.current_usage
        removed_blocks = []
        
        if strategy == OptimizationStrategy.TRUNCATION:
            result = self._optimize_truncation(target_tokens, removed_blocks)
        elif strategy == OptimizationStrategy.SUMMARIZATION:
            result = self._optimize_summarization(target_tokens, removed_blocks)
        else:  # PRIORITIZATION
            result = self._optimize_prioritization(target_tokens, removed_blocks)
        
        # Calculate compression ratio
        compression_ratio = 0.0
        if original_tokens > 0:
            compression_ratio = (original_tokens - result[1]) / original_tokens
        
        optimization_result = OptimizationResult(
            optimized_content=result[0],
            original_tokens=original_tokens,
            optimized_tokens=result[1],
            strategy=strategy,
            compression_ratio=compression_ratio,
            removed_blocks=removed_blocks
        )
        
        self._optimization_history.append(optimization_result)
        return optimization_result
    
    def _optimize_truncation(
        self,
        target_tokens: int,
        removed_blocks: list
    ) -> tuple[str, int]:
        """Optimize by truncating content to fit target."""
        sorted_blocks = sorted(self.blocks, key=lambda b: b.priority, reverse=True)
        selected_blocks = []
        current_tokens = 0
        
        for block in sorted_blocks:
            if current_tokens + block.token_count <= target_tokens:
                selected_blocks.append(block)
                current_tokens += block.token_count
            else:
                removed_blocks.append(block)
        
        # Rebuild content
        content = "\n".join(b.content for b in selected_blocks)
        self.blocks = selected_blocks
        self.context_window.current_usage = current_tokens
        
        return content, current_tokens
    
    def _optimize_summarization(
        self,
        target_tokens: int,
        removed_blocks: list
    ) -> tuple[str, int]:
        """Optimize by summarizing lower priority content."""
        sorted_blocks = sorted(self.blocks, key=lambda b: b.priority, reverse=True)
        high_priority_blocks = []
        low_priority_blocks = []
        
        # Split by priority threshold (median priority)
        if sorted_blocks:
            priorities = [b.priority for b in sorted_blocks]
            median_priority = sorted(priorities)[len(priorities) // 2]
            
            for block in sorted_blocks:
                if block.priority >= median_priority:
                    high_priority_blocks.append(block)
                else:
                    low_priority_blocks.append(block)
        
        # Calculate tokens for high priority
        high_priority_tokens = sum(b.token_count for b in high_priority_blocks)
        
        # Simulate summarization for low priority blocks
        summarized_content = ""
        summarized_tokens = 0
        
        if low_priority_blocks:
            # Create a summary header
            summary_text = f"[Summary of {len(low_priority_blocks)} lower priority items] "
            summary_tokens = TokenCounter.count_tokens(summary_text)
            
            # Add key points from each block (first sentence)
            for block in low_priority_blocks[:5]:  # Limit to 5 items
                first_sentence = block.content.split('.')[0] + "."
                summary_text += first_sentence + " "
                summary_tokens += TokenCounter.count_tokens(first_sentence)
            
            if high_priority_tokens + summary_tokens <= target_tokens:
                summarized_content = summary_text
                summarized_tokens = summary_tokens
                removed_blocks.extend(low_priority_blocks)
            else:
                removed_blocks.extend(low_priority_blocks)
        
        # Build final content
        final_tokens = high_priority_tokens + summarized_tokens
        content_parts = [b.content for b in high_priority_blocks]
        if summarized_content:
            content_parts.append(summarized_content)
        
        content = "\n".join(content_parts)
        
        self.blocks = high_priority_blocks
        self.context_window.current_usage = final_tokens
        
        return content, final_tokens
    
    def _optimize_prioritization(
        self,
        target_tokens: int,
        removed_blocks: list
    ) -> tuple[str, int]:
        """Optimize by keeping highest priority content."""
        sorted_blocks = sorted(self.blocks, key=lambda b: b.priority, reverse=True)
        selected_blocks = []
        current_tokens = 0
        
        # Group by category for balanced selection
        category_blocks: dict[str, list[TokenBlock]] = {}
        for block in sorted_blocks:
            if block.category not in category_blocks:
                category_blocks[block.category] = []
            category_blocks[block.category].append(block)
        
        # Select blocks in priority order, ensuring category balance
        remaining_tokens = target_tokens
        
        # First pass: add highest priority from each category
        for category, blocks in category_blocks.items():
            if blocks and remaining_tokens > 0:
                block = blocks[0]
                if block.token_count <= remaining_tokens:
                    selected_blocks.append(block)
                    current_tokens += block.token_count
                    remaining_tokens -= block.token_count
                    blocks.remove(block)
        
        # Second pass: fill remaining space by priority
        all_remaining = []
        for blocks in category_blocks.values():
            all_remaining.extend(blocks)
        all_remaining.sort(key=lambda b: b.priority, reverse=True)
        
        for block in all_remaining:
            if block.token_count <= remaining_tokens:
                selected_blocks.append(block)
                current_tokens += block.token_count
                remaining_tokens -= block.token_count
            else:
                removed_blocks.append(block)
        
        content = "\n".join(b.content for b in sorted(selected_blocks, key=lambda b: b.priority, reverse=True))
        self.blocks = selected_blocks
        self.context_window.current_usage = current_tokens
        
        return content, current_tokens
    
    def get_statistics(self) -> dict:
        """Get optimizer statistics."""
        return {
            "total_tokens": self.context_window.current_usage,
            "max_tokens": self.context_window.max_tokens,
            "available_tokens": self.context_window.available_tokens,
            "utilization_percent": round(self.context_window.utilization, 2),
            "block_count": len(self.blocks),
            "optimization_count": len(self._optimization_history)
        }
    
    def get_optimization_history(self) -> list[OptimizationResult]:
        """Get history of optimizations."""
        return self._optimization_history.copy()

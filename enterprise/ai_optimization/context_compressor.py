"""Context Compressor Module - Week 55, Builder 4"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


class CompressionMethod(Enum):
    SEMANTIC = "semantic"
    LOSSY = "lossy"
    LOSSLESS = "lossless"


@dataclass
class CompressionResult:
    original: str
    compressed: str
    method: CompressionMethod
    ratio: float
    preserved_tokens: List[str] = field(default_factory=list)

    @property
    def savings(self) -> float:
        return 1 - self.ratio


class ContextCompressor:
    def __init__(self, method: CompressionMethod = CompressionMethod.LOSSY):
        self.method = method
        self._important_patterns = [
            r'\b\d+\b',  # Numbers
            r'\b[A-Z][a-z]+\b',  # Proper nouns
            r'\b(?:important|critical|key|main)\b',  # Important words
        ]
        self._stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                           'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                           'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
                           'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by'}

    def compress(self, text: str, target_ratio: float = 0.5) -> CompressionResult:
        if self.method == CompressionMethod.LOSSLESS:
            return self._compress_lossless(text)
        elif self.method == CompressionMethod.LOSSY:
            return self._compress_lossy(text, target_ratio)
        elif self.method == CompressionMethod.SEMANTIC:
            return self._compress_semantic(text, target_ratio)
        return CompressionResult(original=text, compressed=text, method=self.method, ratio=1.0)

    def _compress_lossless(self, text: str) -> CompressionResult:
        # Simple run-length encoding style compression
        words = text.split()
        compressed_words = []
        prev_word = None
        count = 0

        for word in words:
            if word == prev_word:
                count += 1
            else:
                if prev_word:
                    if count > 2:
                        compressed_words.append(f"{prev_word}[x{count}]")
                    else:
                        compressed_words.extend([prev_word] * count)
                prev_word = word
                count = 1

        if prev_word:
            if count > 2:
                compressed_words.append(f"{prev_word}[x{count}]")
            else:
                compressed_words.extend([prev_word] * count)

        compressed = " ".join(compressed_words)
        ratio = len(compressed) / len(text) if text else 0

        return CompressionResult(
            original=text,
            compressed=compressed,
            method=CompressionMethod.LOSSLESS,
            ratio=ratio,
        )

    def _compress_lossy(self, text: str, target_ratio: float) -> CompressionResult:
        words = text.split()
        target_count = int(len(words) * target_ratio)

        # Remove stop words
        important_words = []
        preserved = []

        for word in words:
            clean = word.lower().strip('.,!?;:')
            if clean in self._stop_words:
                continue
            important_words.append(word)
            if any(re.match(p, word) for p in self._important_patterns):
                preserved.append(word)

        # If still too long, truncate
        if len(important_words) > target_count:
            # Keep preserved words and fill with others
            result = preserved[:target_count]
            compressed = " ".join(result)
        else:
            compressed = " ".join(important_words)

        ratio = len(compressed) / len(text) if text else 0

        return CompressionResult(
            original=text,
            compressed=compressed,
            method=CompressionMethod.LOSSY,
            ratio=ratio,
            preserved_tokens=preserved,
        )

    def _compress_semantic(self, text: str, target_ratio: float) -> CompressionResult:
        # Simplified semantic compression - keep key sentences
        sentences = re.split(r'[.!?]+', text)
        target_count = max(1, int(len(sentences) * target_ratio))

        # Score sentences by importance
        scored = []
        for i, sentence in enumerate(sentences):
            score = 0
            for pattern in self._important_patterns:
                if re.search(pattern, sentence):
                    score += 1
            scored.append((score, i, sentence))

        # Keep top sentences
        scored.sort(reverse=True)
        top_sentences = sorted([s for _, i, s in scored[:target_count]], key=lambda x: sentences.index(x))

        compressed = ". ".join(top_sentences)
        if compressed and not compressed.endswith('.'):
            compressed += '.'

        ratio = len(compressed) / len(text) if text else 0

        return CompressionResult(
            original=text,
            compressed=compressed,
            method=CompressionMethod.SEMANTIC,
            ratio=ratio,
        )

    def set_method(self, method: CompressionMethod) -> None:
        self.method = method

    def add_important_pattern(self, pattern: str) -> None:
        self._important_patterns.append(pattern)

    def get_compression_ratio(self, original: str, compressed: str) -> float:
        return len(compressed) / len(original) if original else 0

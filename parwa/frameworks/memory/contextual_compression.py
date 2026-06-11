"""Contextual Compression — Compress retrieved documents before feeding to LLM.

How it works:
  1. Takes retrieved KB/FAQ documents
  2. Compresses each document by extracting key sentences
  3. Removes redundancy across documents
  4. Returns compressed versions that preserve meaning but use 70-80% fewer tokens

What hallucination it catches:
  "Document overload" — when too many documents are fed to the LLM,
  it picks up irrelevant details and hallucinates connections. Compressed
  documents focus the LLM on the most relevant information.

Activation:
  - Simple complexity and above (always active — compression always helps)
  - Used in KB_RETRIEVER and CONTEXT_MANAGER
"""

from __future__ import annotations

import logging
from typing import Any

from parwa.frameworks.base import BaseTechnique, TechniqueCategory, TechniqueResult
from parwa.utils.llm import MOCK_MODE

logger = logging.getLogger("parwa.frameworks.contextual_compression")

# Target compression ratio (keep this % of original tokens)
_TARGET_RATIO = 0.25  # Keep 25% of original → 75% reduction


class ContextualCompressionTechnique(BaseTechnique):
    """Contextual Compression: Compress retrieved documents for LLM efficiency.

    Takes KB/FAQ results and compresses them by extracting key sentences
    and removing redundancy, achieving 70-80% token reduction while
    preserving the essential information.
    """

    _min_complexity = "simple"

    @property
    def name(self) -> str:
        return "contextual_compression"

    @property
    def category(self) -> TechniqueCategory:
        return TechniqueCategory.MEMORY

    @property
    def applicable_nodes(self) -> list[str]:
        return [
            "KB_RETRIEVER",
            "CONTEXT_MANAGER",
            "FAQ_MATCHER",
            "REASONING_ENGINE",
        ]

    @property
    def token_cost_estimate(self) -> int:
        return 80  # Low — compression is mostly algorithmic

    async def think(
        self,
        prompt: str,
        state: dict[str, Any],
        *,
        ticket_id: str = "",
        variant: str = "parwa",
    ) -> TechniqueResult:
        """Execute Contextual Compression on retrieved documents.

        Compresses KB results and FAQ matches to reduce token usage
        while preserving key information.
        """
        kb_results = state.get("kb_results", [])
        faq_match = state.get("faq_match")

        # Calculate original token count
        original_tokens = self._count_tokens(kb_results, faq_match)

        # Compress
        if MOCK_MODE:
            chain, compressed_kb, compressed_faq, compressed_tokens = self._compress_mock(
                kb_results, faq_match
            )
        else:
            # For real mode, use algorithmic compression (no extra LLM call)
            chain, compressed_kb, compressed_faq, compressed_tokens = self._compress_algorithmic(
                kb_results, faq_match
            )

        reduction = (1 - compressed_tokens / max(original_tokens, 1)) * 100

        chain.insert(0, f"ContextualCompression: Original={original_tokens} tokens")
        chain.append(f"ContextualCompression: Compressed={compressed_tokens} tokens ({reduction:.0f}% reduction)")

        output = f"ContextualCompression: {reduction:.0f}% token reduction ({original_tokens}→{compressed_tokens})"

        confidence = 0.85 if reduction >= 50 else 0.70

        return TechniqueResult(
            output=output,
            chain=chain,
            confidence=confidence,
            frameworks_used=["contextual_compression"],
            metadata={
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "reduction_pct": round(reduction, 1),
                "compressed_kb": compressed_kb,
                "compressed_faq": compressed_faq,
                "target_ratio": _TARGET_RATIO,
            },
            token_estimate=self.token_cost_estimate,
        )

    def _count_tokens(self, kb_results: Any, faq_match: Any) -> int:
        """Count approximate tokens in KB results and FAQ match."""
        total = 0
        if isinstance(kb_results, list):
            for kb in kb_results:
                if isinstance(kb, dict):
                    total += len(kb.get("content", "")) // 4
        if isinstance(faq_match, dict):
            total += len(faq_match.get("content", "")) // 4
        return max(total, 1)

    def _compress_mock(
        self,
        kb_results: list[dict],
        faq_match: dict | None,
    ) -> tuple[list[str], list[dict], dict | None, int]:
        """Mock compression for testing."""
        chain = []
        compressed_kb = []
        compressed_faq = None

        # Compress KB results — keep first 50 chars of each
        if isinstance(kb_results, list):
            chain.append(f"ContextualCompression: Processing {len(kb_results)} KB results")
            for kb in kb_results:
                if isinstance(kb, dict):
                    content = kb.get("content", "")
                    if len(content) > 80:
                        compressed_content = content[:80] + "..."
                    else:
                        compressed_content = content
                    compressed_kb.append({
                        **kb,
                        "content": compressed_content,
                        "_compressed": True,
                    })
                else:
                    compressed_kb.append(kb)

        # Compress FAQ match
        if isinstance(faq_match, dict):
            content = faq_match.get("content", "")
            if len(content) > 80:
                compressed_content = content[:80] + "..."
            else:
                compressed_content = content
            compressed_faq = {
                **faq_match,
                "content": compressed_content,
                "_compressed": True,
            }
            chain.append("ContextualCompression: FAQ match compressed")
        else:
            chain.append("ContextualCompression: No FAQ match to compress")

        compressed_tokens = self._count_tokens(compressed_kb, compressed_faq)
        return chain, compressed_kb, compressed_faq, compressed_tokens

    def _compress_algorithmic(
        self,
        kb_results: list[dict],
        faq_match: dict | None,
    ) -> tuple[list[str], list[dict], dict | None, int]:
        """Algorithmic compression: extract key sentences, remove redundancy."""
        chain = []
        compressed_kb = []
        seen_sentences = set()

        if isinstance(kb_results, list):
            chain.append(f"ContextualCompression: Processing {len(kb_results)} KB results algorithmically")
            for kb in kb_results:
                if isinstance(kb, dict):
                    content = kb.get("content", "")
                    # Extract key sentences (sentences with important keywords)
                    key_sentences = self._extract_key_sentences(content)
                    # Remove redundant sentences
                    unique_sentences = [s for s in key_sentences if s not in seen_sentences]
                    seen_sentences.update(unique_sentences)
                    compressed_content = " ".join(unique_sentences) if unique_sentences else content[:100]
                    compressed_kb.append({
                        **kb,
                        "content": compressed_content,
                        "_compressed": True,
                    })
                else:
                    compressed_kb.append(kb)

        compressed_faq = None
        if isinstance(faq_match, dict):
            content = faq_match.get("content", "")
            key_sentences = self._extract_key_sentences(content)
            compressed_faq = {
                **faq_match,
                "content": " ".join(key_sentences) if key_sentences else content[:100],
                "_compressed": True,
            }
            chain.append("ContextualCompression: FAQ compressed algorithmically")

        compressed_tokens = self._count_tokens(compressed_kb, compressed_faq)
        return chain, compressed_kb, compressed_faq, compressed_tokens

    def _extract_key_sentences(self, text: str) -> list[str]:
        """Extract key sentences from text.

        Key sentences contain important indicators:
        - Numbers/amounts (dates, prices, quantities)
        - Policy terms (must, required, within, eligible)
        - Action words (refund, cancel, process, escalate)
        """
        if not isinstance(text, str) or len(text) < 20:
            return [text] if text else []

        # Simple sentence splitting
        sentences = text.replace("!", ".").replace("?", ".").split(".")
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        key_indicators = [
            "must", "required", "within", "eligible", "refund", "cancel",
            "process", "escalate", "available", "policy", "days", "hours",
            "approve", "deny", "amount", "charge", "order",
        ]

        key_sentences = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(indicator in sentence_lower for indicator in key_indicators):
                key_sentences.append(sentence)

        # If no key sentences found, keep first and last
        if not key_sentences and sentences:
            key_sentences = [sentences[0]]
            if len(sentences) > 1:
                key_sentences.append(sentences[-1])

        return key_sentences[:3]  # Max 3 key sentences per document

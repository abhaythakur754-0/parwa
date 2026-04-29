"""
PARWA Document Chunker

Splits documents into chunks for embedding and retrieval.
Supports text, markdown, and basic HTML stripping.

Chunking parameters match knowledge_tasks.py:
  - CHUNK_SIZE = 1000 characters
  - CHUNK_OVERLAP = 200 characters
  - MAX_CHUNKS_PER_DOCUMENT = 1000
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


# HTML tag pattern for stripping
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Markdown header pattern (## and ###)
_MD_HEADER_RE = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)

# Paragraph split pattern: split on double newlines or newline
_PARAGRAPH_RE = re.compile(r"\n{2,}|\n")


class DocumentChunker:
    """Splits documents into overlapping chunks for embedding.

    Features:
    - Preserves paragraph boundaries where possible
    - Supports text, markdown, and basic HTML stripping
    - Overlapping chunks to avoid losing context at boundaries
    - Configurable chunk size, overlap, and max chunks
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        max_chunks: int = 1000,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        if max_chunks <= 0:
            raise ValueError("max_chunks must be positive")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunks = max_chunks

    # ── Public API ──────────────────────────────────────────────────────

    def chunk_text(
        self,
        text: str,
        filename: str = "",
    ) -> List[Dict[str, Any]]:
        """Split text into overlapping chunks.

        Args:
            text: Document text content.
            filename: Source filename (stored in metadata).

        Returns:
            List of dicts with keys: content, chunk_index, char_count, metadata.
            Returns empty list if text is empty.
        """
        if not text or not text.strip():
            return []

        # Strip HTML tags if detected
        cleaned_text = self._strip_html(text)

        chunks: List[Dict[str, Any]] = []
        start = 0
        chunk_index = 0

        while start < len(cleaned_text) and chunk_index < self.max_chunks:
            end = start + self.chunk_size

            # Try to break at a paragraph boundary near the end
            boundary = self._find_paragraph_boundary(cleaned_text, start, end)

            chunk_content = cleaned_text[start:boundary]

            # Skip empty chunks (can happen with multiple newlines)
            if not chunk_content.strip():
                start = boundary
                continue

            chunks.append({
                "content": chunk_content.strip(),
                "chunk_index": chunk_index,
                "char_count": len(chunk_content.strip()),
                "metadata": self._build_metadata(filename, chunk_index, len(chunks)),
            })

            chunk_index += 1
            # Overlap: step back from the boundary
            start = boundary - self.chunk_overlap
            if start < 0:
                start = boundary  # prevent going backwards on first chunk
            # If we didn't advance at all, force advance
            if start <= 0 and chunk_index > 0:
                start = boundary

        return chunks

    def chunk_markdown(self, text: str) -> List[Dict[str, Any]]:
        """Split markdown text by headers first, then by size.

        Markdown documents are first split on ## / ### headers to preserve
        semantic sections. Sections that exceed chunk_size are further
        split into overlapping sub-chunks.

        Args:
            text: Markdown document text.

        Returns:
            List of dicts with keys: content, chunk_index, char_count, metadata.
            Metadata includes ``section_header`` when available.
        """
        if not text or not text.strip():
            return []

        # Find all header positions
        sections = self._split_by_headers(text)

        chunks: List[Dict[str, Any]] = []
        chunk_index = 0

        for section_header, section_text in sections:
            if not section_text.strip():
                continue

            if len(section_text) <= self.chunk_size:
                # Section fits in one chunk
                metadata: Dict[str, Any] = {
                    "section_header": section_header,
                }
                chunks.append({
                    "content": section_text.strip(),
                    "chunk_index": chunk_index,
                    "char_count": len(section_text.strip()),
                    "metadata": metadata,
                })
                chunk_index += 1
            else:
                # Section is too large, sub-chunk it
                sub_chunks = self.chunk_text(section_text)
                for sc in sub_chunks:
                    sc["chunk_index"] = chunk_index
                    sc["metadata"]["section_header"] = section_header
                    chunk_index += 1
                    chunks.append(sc)

            if chunk_index >= self.max_chunks:
                break

        return chunks

    def get_chunk_count_estimate(self, text_length: int) -> int:
        """Estimate the number of chunks without actually splitting.

        Args:
            text_length: Length of the text in characters.

        Returns:
            Estimated number of chunks (minimum 0).
        """
        if text_length <= 0:
            return 0

        effective_step = self.chunk_size - self.chunk_overlap
        if effective_step <= 0:
            effective_step = self.chunk_size

        estimate = (text_length / effective_step) + 1
        return min(int(estimate), self.max_chunks)

    # ── Private Helpers ─────────────────────────────────────────────────

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags and decode common entities."""
        # Quick check: does it look like HTML?
        if "<" not in text or ">" not in text:
            return text

        cleaned = _HTML_TAG_RE.sub("", text)
        # Normalize whitespace from removed tags
        cleaned = re.sub(r"  +", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _find_paragraph_boundary(
        self,
        text: str,
        start: int,
        end: int,
    ) -> int:
        """Find a paragraph break near *end* to avoid splitting mid-paragraph.

        Looks backwards from *end* up to ``chunk_size // 4`` characters
        for a double-newline (paragraph boundary).  Falls back to a
        single newline, and finally to the raw *end* position.
        """
        search_start = max(start, end - (self.chunk_size // 4))
        segment = text[search_start:end]

        # Look for paragraph break (\n\n)
        last_para = segment.rfind("\n\n")
        if last_para != -1:
            return search_start + last_para

        # Look for single newline
        last_nl = segment.rfind("\n")
        if last_nl != -1:
            return search_start + last_nl

        # Look for sentence end (. ! ?)
        sentence_end_re = re.compile(r"[.!?]\s")
        matches = list(sentence_end_re.finditer(segment))
        if matches:
            return search_start + matches[-1].end()

        # No boundary found — split at raw end
        return end

    def _split_by_headers(self, text: str) -> List[tuple]:
        """Split markdown text on ## and ### headers.

        Returns:
            List of (header, section_text) tuples.
            The first section (before any header) gets header="".
        """
        positions: List[tuple] = []
        for m in _MD_HEADER_RE.finditer(text):
            positions.append((m.start(), m.end(), m.group(2).strip()))

        if not positions:
            return [("", text)]

        sections: List[tuple] = []

        # Section before first header
        first_header_start = positions[0][0]
        if first_header_start > 0:
            sections.append(("", text[:first_header_start]))

        # Each header section
        for i, (hdr_start, hdr_end, header_text) in enumerate(positions):
            next_start = positions[i + 1][0] if i + \
                1 < len(positions) else len(text)
            section_body = text[hdr_end:next_start]
            sections.append((header_text, section_body))

        return sections

    def _build_metadata(
        self,
        filename: str,
        chunk_index: int,
        total_so_far: int,
    ) -> Dict[str, Any]:
        """Build metadata dict for a chunk."""
        metadata: Dict[str, Any] = {
            "chunk_index": chunk_index,
            "total_chunks_estimate": total_so_far,
        }
        if filename:
            metadata["source"] = filename
        return metadata

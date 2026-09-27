"""
KB helpers — local embedding writes at upload + BM25-lite ranking.

Wired into:
  - backend/app/api/knowledge_base.py  (upload: parse binary formats via
    docparse + best-effort local embeddings on chunks)
  - node_3_knowledge_fetch (BM25 always runs; local-embedding fallback
    when the external embedding API fails)

Pure functions + graceful degradation only.
"""

from __future__ import annotations

import logging
import math
import re
from typing import List, Optional, Tuple

from app.core.oss_stack import docparse, embeddings

logger = logging.getLogger("parwa.oss.kb")

_WORD_RE = re.compile(r"[a-z0-9]+")


def parse_and_chunk(filename: str, content: bytes) -> Tuple[Optional[str], list]:
    """Parse uploaded bytes → (text, chunks).

    Binary formats (pdf/docx/...) require MarkItDown; if unavailable we
    return (None, []) so the caller rejects the upload honestly instead of
    storing UTF-8 garbage. Text formats fall back to UTF-8 decode.
    """
    text = docparse.parse(filename, content)
    if text is None:
        return None, []
    return text, docparse.chunk_text(text)


def embed_chunks_best_effort(chunks: List[str], max_items: int = 40) -> List[Optional[str]]:
    """Best-effort local embeddings for chunk texts. Returns stored-literal
    strings ('[0.1,0.2,...]') aligned with input; None where embedding
    failed. Never raises, never blocks upload."""
    try:
        vecs = embeddings.embed_batch(chunks, max_items=max_items)
        return [embeddings.to_stored_literal(v) if v else None for v in vecs]
    except Exception as exc:
        logger.warning("oss_kb embed_chunks failed: %s", str(exc)[:150])
        return [None] * len(chunks)


def _light_stem(w: str) -> str:
    """Tiny deterministic stemmer — applied to BOTH corpus and query, so
    consistency is what matters: refunds→refund, days→day, charged→charg.
    Not a real Porter stemmer — just enough to stop exact-token misses."""
    if len(w) > 4 and (w.endswith("ing") or w.endswith("ed")):
        w = w[:-3] if w.endswith("ing") else w[:-2]
    if len(w) > 3 and w.endswith("ss"):
        return w
    if len(w) > 3 and w.endswith("es"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s"):
        return w[:-1]
    return w


def tokenize(text: str) -> List[str]:
    return [_light_stem(w) for w in _WORD_RE.findall((text or "").lower())]


def bm25_rank(
    query: str,
    rows: List[Tuple[str, str, str]],
    top_k: int = 5,
) -> List[dict]:
    """In-process BM25 ranking fallback (rank_bm25 when installed, else a
    tiny term-overlap scorer). rows = (chunk_id, content, document_id).
    Returns [{id, content, document_id, score}] best-first.

    Used by Node 3 so keyword search works EVEN when chunks have no
    embeddings — the production bug where fresh uploads were invisible."""
    if not rows:
        return []
    q_tokens = tokenize(query)
    scores = None
    try:
        from rank_bm25 import BM25Okapi  # type: ignore

        corpus = [tokenize(c) for _cid, c, _d in rows]
        if any(corpus):
            bm25 = BM25Okapi(corpus)
            scores = list(bm25.get_scores(q_tokens))
            if not any(s > 0 for s in scores):
                scores = None  # exact-token BM25 found nothing → try overlap floor
    except Exception:
        scores = None
    if scores is None:
        # Term-overlap floor (also the no-rank_bm25 path)
        q = set(q_tokens)
        scores = []
        for _cid, content, _doc in rows:
            toks = tokenize(content)
            if not toks:
                scores.append(0.0)
                continue
            overlap = len(q.intersection(toks)) / (1.0 + math.log(1 + len(toks)))
            scores.append(overlap)
    ranked = sorted(zip(rows, scores), key=lambda x: x[1], reverse=True)
    out = []
    for (cid, content, doc_id), score in ranked:
        if score <= 0:
            continue
        out.append(
            {"id": str(cid), "content": content, "document_id": str(doc_id), "score": float(score)}
        )
        if len(out) >= top_k:
            break
    return out


def fuzzy_dedupe(texts: List[str], threshold: float = 92.0) -> List[int]:
    """Return indices of texts worth KEEPING, dropping near-duplicates.
    Uses RapidFuzz when installed, else exact/lower-case comparison."""
    if not texts:
        return []
    keep: List[int] = []
    kept_norm: List[str] = []
    try:
        from rapidfuzz import fuzz  # type: ignore

        have_fuzz = True
    except Exception:
        have_fuzz = False

    for i, t in enumerate(texts):
        norm = (t or "").strip().lower()
        if not norm:
            continue
        dup = False
        if have_fuzz:
            for k in kept_norm:
                if fuzz.ratio(norm, k) >= threshold:
                    dup = True
                    break
        else:
            dup = norm in kept_norm
        if not dup:
            keep.append(i)
            kept_norm.append(norm)
    return keep

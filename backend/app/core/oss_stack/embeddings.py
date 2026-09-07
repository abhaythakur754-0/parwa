"""
Local sentence embeddings via fastembed (ONNX MiniLM, 384-dim).

Why: PARWA's KB retrieval dies silently when the external embedding API
(Google/NVIDIA) fails or is unconfigured — chunks get no embeddings and
Node 3's whole hybrid tier is skipped. This module gives PARWA a local,
CPU-only, ~150MB-RAM fallback so uploads ALWAYS get embeddings.

Storage format matches DocumentChunk.embedding: a text literal
"[0.1,0.2,...]" so existing ::vector casts keep working.
Dimension 384 — Node 3 groups by dimension, so 384-dim chunks are searched
with a 384-dim query embedding (also produced here).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import List, Optional, Tuple

logger = logging.getLogger("parwa.oss.embeddings")

EMBED_DIM = 384
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_lock = threading.Lock()
_model = None  # lazy singleton


def is_available() -> bool:
    try:
        import importlib.util

        if importlib.util.find_spec("fastembed") is None:
            return False
        return os.environ.get("OSS_EMBEDDINGS", "1").strip() in ("1", "true", "yes", "on")
    except Exception:
        return False


def _get_model():
    """Lazy-load fastembed model once. Returns None if unavailable."""
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        try:
            from fastembed import TextEmbedding

            _model = TextEmbedding(model_name=_MODEL_NAME)
            logger.info("oss_embeddings: loaded %s (dim=%d)", _MODEL_NAME, EMBED_DIM)
            return _model
        except Exception as exc:
            logger.warning("oss_embeddings unavailable: %s", str(exc)[:200])
            _model = False  # sentinel: tried and failed
            return None
    return None


def embed(text: str) -> Optional[List[float]]:
    """Embed one text locally. Returns None on any failure (caller degrades)."""
    if not is_available():
        return None
    model = _get_model()
    if model is None or not text or not text.strip():
        return None
    try:
        vec = list(next(model.embed([text[:2000]])))
        if len(vec) != EMBED_DIM:
            return None
        return vec
    except Exception as exc:
        logger.warning("oss_embeddings embed failed: %s", str(exc)[:150])
        return None


def embed_batch(texts: List[str], max_items: int = 40) -> List[Optional[List[float]]]:
    """Embed up to max_items texts. Non-vector items map to None."""
    if not is_available() or not texts:
        return [None] * len(texts)
    model = _get_model()
    if model is None:
        return [None] * len(texts)
    texts = texts[:max_items]
    out: List[Optional[List[float]]] = []
    try:
        clipped = [(t or " ")[:2000] for t in texts]
        for vec in model.embed(clipped):
            v = list(vec)
            out.append(v if len(v) == EMBED_DIM else None)
    except Exception as exc:
        logger.warning("oss_embeddings batch failed: %s", str(exc)[:150])
        return [None] * len(texts)
    while len(out) < len(texts):
        out.append(None)
    return out


def to_stored_literal(vec: List[float]) -> str:
    """Serialize to the DocumentChunk.embedding text format '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def from_stored_literal(raw) -> Optional[List[float]]:
    """Parse a stored embedding literal (str/JSON/list) into floats. None on failure."""
    try:
        if raw is None:
            return None
        if isinstance(raw, (list, tuple)):
            return [float(x) for x in raw]
        s = str(raw).strip()
        if not s.startswith("["):
            return None
        return [float(x) for x in json.loads(s)]
    except Exception:
        return None


def cosine(a: List[float], b: List[float]) -> float:
    """Pure-python cosine similarity (no numpy). 0.0 on degenerate input."""
    try:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)
    except Exception:
        return 0.0


def rank_chunks(
    query: str, chunks: List[Tuple[str, str, str]], top_k: int = 5
) -> List[dict]:
    """Rank (chunk_id, content, document_id) rows against a query by local
    embedding similarity. Returns [{id, content, document_id, score}] best-first.
    Used by Node 3 when external embeddings are unavailable."""
    if not is_available() or not chunks:
        return []
    q = embed(query)
    if q is None:
        return []
    scored = []
    for cid, content, doc_id in chunks:
        c = embed(content or "")
        if c is None:
            continue
        scored.append(
            {
                "id": str(cid),
                "content": content,
                "document_id": str(doc_id),
                "score": cosine(q, c),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [s for s in scored if s["score"] > 0.05][:top_k]

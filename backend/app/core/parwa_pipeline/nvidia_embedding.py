"""
Embedding Helper — uses Google AI Studio text-embedding-004 for semantic search.

Primary: Google AI Studio text-embedding-004 (768 dims) — free tier, reliable.
Fallback: NVIDIA nv-embedqa-e5-v5 (1024 dims) — backup if Google fails.

The embedding model powers vector search in Node 3 (Knowledge Fetch) and
the shared knowledge-base retriever (`app/shared/knowledge_base/retriever.py`).
User directive: ignore NVIDIA for LLM; use Google for embeddings too.

API: https://generativelanguage.googleapis.com/v1beta/models
Model: text-embedding-004 (768 dimensions)
Cost: Free tier on Google AI Studio

Security: NVIDIA_API_KEY is read from the environment ONLY — never hardcoded.
"""
import os
import logging
import httpx
from typing import Optional, List

logger = logging.getLogger("parwa.embedding")

# ── Google AI Studio Embedding (PRIMARY) ──
GOOGLE_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GOOGLE_EMBED_MODEL = "text-embedding-004"
GOOGLE_EMBEDDING_DIMENSION = 768

# ── NVIDIA Embedding (FALLBACK — env var only, never hardcoded) ──
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
NVIDIA_EMBEDDING_DIMENSION = 1024

# Active embedding dimension (NVIDIA is primary → 1024 matches the existing DB column)
EMBEDDING_DIMENSION = NVIDIA_EMBEDDING_DIMENSION


async def embed_text(text: str, input_type: str = "query") -> Optional[List[float]]:
    """Embed a single text using NVIDIA (primary) or Google (fallback).

    PRODUCTION REALITY: The document_chunks.embedding column is vector(1024)
    and all existing embedded chunks are 1024-dim (NVIDIA nv-embedqa-e5-v5).
    Switching to Google's 768-dim would break vector search until all docs
    are re-embedded. So NVIDIA remains primary to match the existing schema.

    The hardcoded NVIDIA key was removed (security fix) — NVIDIA_API_KEY
    must now be set via environment variable.

    Args:
        text: The text to embed.
        input_type: "query" for search queries, "passage" for documents being indexed.

    Returns:
        List of floats (1024-dim from NVIDIA, 768-dim from Google), or None on failure.
    """
    if not text or not text.strip():
        return None

    # PRIMARY: NVIDIA nv-embedqa-e5-v5 (1024 dims — matches existing DB column)
    result = await _embed_nvidia(text, input_type)
    if result is not None:
        return result

    # FALLBACK: Google AI Studio text-embedding-004 (768 dims — only if NVIDIA unavailable)
    result = await _embed_google(text, input_type)
    if result is not None:
        return result

    logger.error("embed_text: Both NVIDIA and Google embeddings failed")
    return None


async def _embed_google(text: str, input_type: str = "query") -> Optional[List[float]]:
    """Embed using Google AI Studio text-embedding-004."""
    api_key = os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("_embed_google: No GOOGLE_AI_API_KEY configured")
        return None

    try:
        url = f"{GOOGLE_EMBED_URL}/{GOOGLE_EMBED_MODEL}:embedContent?key={api_key}"
        payload = {
            "model": f"models/{GOOGLE_EMBED_MODEL}",
            "content": {"parts": [{"text": text[:8000]}]},
            "taskType": "RETRIEVAL_QUERY" if input_type == "query" else "RETRIEVAL_DOCUMENT",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)

        if response.status_code == 200:
            data = response.json()
            emb = data.get("embedding", {}).get("values", [])
            if emb and len(emb) > 0:
                return emb
            logger.warning("_embed_google: unexpected embedding length %d", len(emb))
            return None
        logger.warning("_embed_google: Google returned %d: %s", response.status_code, response.text[:200])
        return None
    except Exception as exc:
        logger.warning("_embed_google: failed: %s", str(exc)[:200])
        return None


async def _embed_nvidia(text: str, input_type: str = "query") -> Optional[List[float]]:
    """Embed using NVIDIA nv-embedqa-e5-v5 (fallback)."""
    if not NVIDIA_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                NVIDIA_EMBED_URL,
                headers={
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": NVIDIA_EMBED_MODEL,
                    "input": text[:8000],
                    "input_type": input_type,
                },
            )
        if response.status_code == 200:
            data = response.json()
            emb = data.get("data", [{}])[0].get("embedding", [])
            if emb and len(emb) == NVIDIA_EMBEDDING_DIMENSION:
                return emb
            return None
        logger.warning("_embed_nvidia: NVIDIA returned %d: %s", response.status_code, response.text[:200])
        return None
    except Exception as exc:
        logger.warning("_embed_nvidia: failed: %s", str(exc)[:200])
        return None


def embed_text_sync(text: str, input_type: str = "query") -> Optional[List[float]]:
    """Synchronous version of embed_text (for use in non-async contexts).

    PRIMARY: NVIDIA nv-embedqa-e5-v5 (1024 dims — matches existing DB column)
    FALLBACK: Google AI Studio text-embedding-004 (768 dims)

    See embed_text() docstring for why NVIDIA is primary (production DB schema).

    Args:
        text: The text to embed.
        input_type: "query" for search queries, "passage" for documents being indexed.

    Returns:
        List of floats, or None on failure.
    """
    if not text or not text.strip():
        return None

    # PRIMARY: NVIDIA (matches existing 1024-dim column)
    result = _embed_nvidia_sync(text, input_type)
    if result is not None:
        return result

    # FALLBACK: Google AI Studio
    result = _embed_google_sync(text, input_type)
    if result is not None:
        return result

    logger.error("embed_text_sync: Both NVIDIA and Google embeddings failed")
    return None


def _embed_google_sync(text: str, input_type: str = "query") -> Optional[List[float]]:
    """Embed using Google AI Studio text-embedding-004 (sync)."""
    api_key = os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        url = f"{GOOGLE_EMBED_URL}/{GOOGLE_EMBED_MODEL}:embedContent?key={api_key}"
        payload = {
            "model": f"models/{GOOGLE_EMBED_MODEL}",
            "content": {"parts": [{"text": text[:8000]}]},
            "taskType": "RETRIEVAL_QUERY" if input_type == "query" else "RETRIEVAL_DOCUMENT",
        }
        response = httpx.post(url, json=payload, timeout=30.0)

        if response.status_code == 200:
            data = response.json()
            emb = data.get("embedding", {}).get("values", [])
            if emb and len(emb) > 0:
                return emb
            return None
        logger.warning("_embed_google_sync: Google returned %d: %s", response.status_code, response.text[:200])
        return None
    except Exception as exc:
        logger.warning("_embed_google_sync: failed: %s", str(exc)[:200])
        return None


def _embed_nvidia_sync(text: str, input_type: str = "query") -> Optional[List[float]]:
    """Embed using NVIDIA nv-embedqa-e5-v5 (sync fallback)."""
    if not NVIDIA_API_KEY:
        return None
    try:
        response = httpx.post(
            NVIDIA_EMBED_URL,
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": NVIDIA_EMBED_MODEL,
                "input": text[:8000],
                "input_type": input_type,
            },
            timeout=30.0,
        )
        if response.status_code == 200:
            data = response.json()
            emb = data.get("data", [{}])[0].get("embedding", [])
            if emb and len(emb) == NVIDIA_EMBEDDING_DIMENSION:
                return emb
            return None
        logger.warning("_embed_nvidia_sync: NVIDIA returned %d: %s", response.status_code, response.text[:200])
        return None
    except Exception as exc:
        logger.warning("_embed_nvidia_sync: failed: %s", str(exc)[:200])
        return None

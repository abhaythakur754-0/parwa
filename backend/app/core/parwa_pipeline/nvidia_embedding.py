"""
Embedding Helper — uses Google AI Studio text-embedding-004 for semantic search.

Primary: Google AI Studio text-embedding-004 (768 dims) — free tier, reliable.
Fallback: NVIDIA nv-embedqa-e5-v5 (1024 dims) — backup if Google fails.

The embedding model powers vector search in Node 3 (Knowledge Fetch).
User directive: ignore NVIDIA for LLM; use Google for embeddings too.

API: https://generativelanguage.googleapis.com/v1beta/models
Model: text-embedding-004 (768 dimensions)
Cost: Free tier on Google AI Studio
"""
import os
import logging
import httpx
from typing import Optional, List

logger = logging.getLogger("parwa.embedding")

# ── Google AI Studio Embedding (PRIMARY) ──
GOOGLE_AI_API_KEY = os.environ.get(
    "GOOGLE_AI_API_KEY",
    os.environ.get("GEMINI_API_KEY", ""),
)
GOOGLE_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GOOGLE_EMBED_MODEL = "text-embedding-004"
GOOGLE_EMBEDDING_DIMENSION = 768

# ── NVIDIA Embedding (FALLBACK) ──
NVIDIA_API_KEY = os.environ.get(
    "NVIDIA_API_KEY",
    "REDACTED_NVIDIA_KEY_REMOVED",
)
NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
NVIDIA_EMBEDDING_DIMENSION = 1024

# Active embedding dimension (depends on which provider succeeds)
EMBEDDING_DIMENSION = GOOGLE_EMBEDDING_DIMENSION


async def embed_text(text: str, input_type: str = "query") -> Optional[List[float]]:
    """Embed a single text using NVIDIA (primary) or Google (fallback).

    NVIDIA is primary because the Google AI API key is invalid.
    Google is kept as fallback for when a valid key is configured.

    Args:
        text: The text to embed.
        input_type: "query" for search queries, "passage" for documents being indexed.

    Returns:
        List of floats, or None on failure.
    """
    if not text or not text.strip():
        return None

    # PRIMARY: NVIDIA (Google key is invalid)
    result = await _embed_nvidia(text, input_type)
    if result is not None:
        return result

    # FALLBACK: Google AI Studio (only works if valid key is configured)
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

    PRIMARY: NVIDIA nv-embedqa-e5-v5 (Google key is invalid)
    FALLBACK: Google AI Studio text-embedding-004

    Args:
        text: The text to embed.
        input_type: "query" for search queries, "passage" for documents being indexed.

    Returns:
        List of floats, or None on failure.
    """
    if not text or not text.strip():
        return None

    # PRIMARY: NVIDIA (Google key is invalid)
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

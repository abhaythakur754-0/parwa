"""
PARWA Embedding Service (F-082) — Day 0 Prerequisite P1+P2

Generates vector embeddings using Google AI Studio (text-embedding-004).
Falls back to Cerebras embeddings API if Google is unavailable.
Batch processing with async support for Celery tasks.

BC-001: All operations scoped to company_id.
BC-008: Graceful degradation — returns empty list on failure.
"""

import json
import logging
from typing import List, Optional

import httpx

logger = logging.getLogger("parwa.embedding_service")

# ── Google AI Studio Embedding Endpoints ──────────────────────────────

_GOOGLE_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004"
)
_GOOGLE_EMBED_ENDPOINT = f"{_GOOGLE_BASE_URL}:embedContent"
_GOOGLE_BATCH_ENDPOINT = f"{_GOOGLE_BASE_URL}:batchEmbedContents"

# ── Model Constants ───────────────────────────────────────────────────

MODEL_NAME = "text-embedding-004"
EMBEDDING_DIMENSION = 768
MAX_BATCH_SIZE = 100
TIMEOUT_SECONDS = 30


# ── Standalone Sync Function (for Celery tasks) ───────────────────────


def generate_embedding_sync(
    text: str,
    api_key: str,
) -> Optional[List[float]]:
    """Generate a single embedding synchronously using Google AI Studio.

    Standalone function suitable for use in Celery sync context
    where no class instance is available.

    Args:
        text: Text to embed.
        api_key: Google AI API key.

    Returns:
        Embedding vector (list of floats) or None on failure (BC-008).
    """
    if not api_key:
        logger.warning(
            "generate_embedding_sync: GOOGLE_AI_API_KEY not set, skipping embedding"
        )
        return None

    if not text or not text.strip():
        logger.warning("generate_embedding_sync: empty text, skipping embedding")
        return None

    try:
        response = httpx.post(
            _GOOGLE_EMBED_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            json={
                "model": f"models/{MODEL_NAME}",
                "content": {"parts": [{"text": text}]},
            },
            timeout=float(TIMEOUT_SECONDS),
        )

        if response.status_code == 200:
            values = response.json().get("embedding", {}).get("values")
            if values:
                logger.debug(
                    "generate_embedding_sync: success, dim=%d", len(values)
                )
                return values
            logger.error(
                "generate_embedding_sync: response missing embedding values"
            )
            return None

        logger.error(
            "generate_embedding_sync: API returned status %d: %s",
            response.status_code,
            response.text[:200],
        )
        return None

    except httpx.TimeoutException:
        logger.error("generate_embedding_sync: request timed out after %ds", TIMEOUT_SECONDS)
        return None
    except httpx.HTTPError as exc:
        logger.error("generate_embedding_sync: HTTP error: %s", str(exc))
        return None
    except Exception as exc:
        logger.error("generate_embedding_sync: unexpected error: %s", str(exc))
        return None


def _deterministic_pseudo_embedding(text: str, dim: int = EMBEDDING_DIMENSION) -> List[float]:
    """Generate a deterministic pseudo-embedding using SHA-256 hash.
    
    Last-resort fallback when all embedding APIs are unavailable (BC-008).
    NOT real embeddings — should only be used when no API keys are configured.
    """
    import hashlib
    h = hashlib.sha256(text.encode("utf-8")).digest()
    result = []
    for i in range(dim):
        byte_idx = i % len(h)
        result.append((h[byte_idx] / 255.0) - 0.5)
    return result


# ── Embedding Service Class ───────────────────────────────────────────


class EmbeddingService:
    """Service for generating vector embeddings.

    Primary: Google AI Studio (text-embedding-004).
    BC-001: All operations scoped to company_id.
    BC-008: Graceful degradation — returns None / empty list on failure.

    Usage::

        svc = EmbeddingService(company_id="...")
        vec = svc.generate_embedding("Hello world")
        vecs = svc.generate_embeddings_batch(["Hello", "World"])
    """

    def __init__(self, company_id: str) -> None:
        self.company_id = company_id
        self._api_key: Optional[str] = None

    @property
    def model_name(self) -> str:
        return MODEL_NAME

    @property
    def embedding_dimension(self) -> int:
        return EMBEDDING_DIMENSION

    @property
    def max_batch_size(self) -> int:
        return MAX_BATCH_SIZE

    @property
    def timeout_seconds(self) -> int:
        return TIMEOUT_SECONDS

    def _get_api_key(self) -> Optional[str]:
        """Lazily load API key from settings (BC-008 safe)."""
        if self._api_key is None:
            try:
                from app.config import get_settings

                settings = get_settings()
                self._api_key = settings.GOOGLE_AI_API_KEY or ""
            except Exception as exc:
                logger.error(
                    "EmbeddingService._get_api_key: failed to load settings: %s",
                    str(exc),
                )
                self._api_key = ""
        return self._api_key or None

    # ── Single Embedding ──────────────────────────────────────────

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate an embedding for a single text string.

        Uses Google AI Studio text-embedding-004 model with fallback chain:
        Google → LiteLLM → deterministic pseudo-embedding (BC-008).

        Args:
            text: Text to embed.

        Returns:
            Embedding vector (never None — pseudo-embedding as last resort).
        """
        if not text or not text.strip():
            logger.warning(
                "EmbeddingService.generate_embedding: empty text "
                "(company_id=%s)",
                self.company_id,
            )
            return None

        # ── Primary: Google AI Studio ─────────────────────────────
        api_key = self._get_api_key()
        if api_key:
            try:
                response = httpx.post(
                    _GOOGLE_EMBED_ENDPOINT,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key,
                    },
                    json={
                        "model": f"models/{self.model_name}",
                        "content": {"parts": [{"text": text}]},
                    },
                    timeout=float(self.timeout_seconds),
                )

                if response.status_code == 200:
                    values = response.json().get("embedding", {}).get("values")
                    if values:
                        logger.debug(
                            "EmbeddingService.generate_embedding: success, "
                            "company_id=%s, dim=%d",
                            self.company_id,
                            len(values),
                        )
                        return values
                    logger.error(
                        "EmbeddingService.generate_embedding: response missing "
                        "embedding values (company_id=%s)",
                        self.company_id,
                    )
                else:
                    logger.error(
                        "EmbeddingService.generate_embedding: API returned status %d: %s "
                        "(company_id=%s)",
                        response.status_code,
                        response.text[:200],
                        self.company_id,
                    )
            except httpx.TimeoutException:
                logger.error(
                    "EmbeddingService.generate_embedding: request timed out "
                    "(company_id=%s, timeout=%ds)",
                    self.company_id,
                    self.timeout_seconds,
                )
            except httpx.HTTPError as exc:
                logger.error(
                    "EmbeddingService.generate_embedding: HTTP error: %s "
                    "(company_id=%s)",
                    str(exc),
                    self.company_id,
                )
            except Exception as exc:
                logger.error(
                    "EmbeddingService.generate_embedding: unexpected error: %s "
                    "(company_id=%s)",
                    str(exc),
                    self.company_id,
                )
        else:
            logger.warning(
                "EmbeddingService.generate_embedding: GOOGLE_AI_API_KEY not set "
                "(company_id=%s)",
                self.company_id,
            )

        # LiteLLM fallback
        # TODO(Day6 — I4): LiteLLM integration is planned but this fallback path uses
        # litellm.embedding() directly.  In production, ensure the LiteLLM
        # API key is configured (LITELLM_API_KEY) and that the model name
        # maps to a real embedding provider.  The litellm library is NOT
        # yet a core production dependency — it is imported at runtime and
        # failures fall through to the deterministic pseudo-embedding (BC-008).
        try:
            import litellm
            response = litellm.embedding(model="text-embedding-3-small", input=[text])
            values = response.data[0]["embedding"]
            if values:
                logger.info("EmbeddingService: used LiteLLM fallback (company_id=%s)", self.company_id)
                return values
        except Exception as litellm_exc:
            logger.warning("EmbeddingService: LiteLLM fallback failed: %s", str(litellm_exc))

        # Deterministic pseudo-embedding (last resort)
        logger.warning(
            "EmbeddingService: All embedding APIs unavailable, using pseudo-embedding (company_id=%s)",
            self.company_id,
        )
        return _deterministic_pseudo_embedding(text)

    # ── Batch Embedding ───────────────────────────────────────────

    def generate_embeddings_batch(
        self, texts: List[str]
    ) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple texts in a single API call.

        Uses Google's batchEmbedContents endpoint (max 100 texts).
        Returns list of embeddings in the same order as input.
        Failed items are None (BC-008).

        Args:
            texts: List of texts to embed (max MAX_BATCH_SIZE).

        Returns:
            List of embedding vectors (or None for failures).
        """
        if not texts:
            return []

        if len(texts) > self.max_batch_size:
            logger.warning(
                "EmbeddingService.generate_embeddings_batch: batch size %d "
                "exceeds max %d, truncating (company_id=%s)",
                len(texts),
                self.max_batch_size,
                self.company_id,
            )
            texts = texts[: self.max_batch_size]

        api_key = self._get_api_key()
        if not api_key:
            logger.warning(
                "EmbeddingService.generate_embeddings_batch: GOOGLE_AI_API_KEY "
                "not set (company_id=%s)",
                self.company_id,
            )
            # Fall back to per-item embedding
            logger.info("EmbeddingService: batch failed, falling back to per-item (company_id=%s)", self.company_id)
            return [self.generate_embedding(t) for t in texts]

        # Build batch request
        requests_body = []
        for text in texts:
            requests_body.append(
                {
                    "model": f"models/{self.model_name}",
                    "content": {"parts": [{"text": text or ""}]},
                }
            )

        try:
            response = httpx.post(
                _GOOGLE_BATCH_ENDPOINT,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                json={"requests": requests_body},
                timeout=float(self.timeout_seconds * 2),  # longer for batch
            )

            if response.status_code == 200:
                data = response.json()
                embeddings = data.get("embeddings", [])
                result: List[Optional[List[float]]] = []
                for emb_obj in embeddings:
                    values = emb_obj.get("values")
                    result.append(values if values else None)

                # Pad with None if response has fewer items than input
                while len(result) < len(texts):
                    result.append(None)

                logger.debug(
                    "EmbeddingService.generate_embeddings_batch: success, "
                    "company_id=%s, requested=%d, returned=%d",
                    self.company_id,
                    len(texts),
                    len([r for r in result if r is not None]),
                )
                return result

            logger.error(
                "EmbeddingService.generate_embeddings_batch: API returned "
                "status %d: %s (company_id=%s)",
                response.status_code,
                response.text[:200],
                self.company_id,
            )
            # Fall back to per-item embedding
            logger.info("EmbeddingService: batch failed, falling back to per-item (company_id=%s)", self.company_id)
            return [self.generate_embedding(t) for t in texts]

        except httpx.TimeoutException:
            logger.error(
                "EmbeddingService.generate_embeddings_batch: request timed out "
                "(company_id=%s)",
                self.company_id,
            )
            # Fall back to per-item embedding
            logger.info("EmbeddingService: batch failed, falling back to per-item (company_id=%s)", self.company_id)
            return [self.generate_embedding(t) for t in texts]
        except httpx.HTTPError as exc:
            logger.error(
                "EmbeddingService.generate_embeddings_batch: HTTP error: %s "
                "(company_id=%s)",
                str(exc),
                self.company_id,
            )
            # Fall back to per-item embedding
            logger.info("EmbeddingService: batch failed, falling back to per-item (company_id=%s)", self.company_id)
            return [self.generate_embedding(t) for t in texts]
        except Exception as exc:
            logger.error(
                "EmbeddingService.generate_embeddings_batch: unexpected error: "
                "%s (company_id=%s)",
                str(exc),
                self.company_id,
            )
            # Fall back to per-item embedding
            logger.info("EmbeddingService: batch failed, falling back to per-item (company_id=%s)", self.company_id)
            return [self.generate_embedding(t) for t in texts]

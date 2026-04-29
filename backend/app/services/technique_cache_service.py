"""
Technique Cache Service — Safe JSON handling for cached technique results.

Reads/writes the technique_caches table with JSON corruption protection.
Every json.loads() call is wrapped in try/except (BC-008: never crash).
JSON structure is validated before caching to prevent silent failures.

BC-001: All queries filtered by company_id.
BC-008: Graceful degradation on malformed JSON.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.exceptions import ParwaBaseError

from database.base import SessionLocal
from database.models.variant_engine import TechniqueCache

logger = logging.getLogger("parwa.technique_cache")

# Default TTL for cached results (24 hours)
DEFAULT_CACHE_TTL_HOURS = 24


def _validate_company_id(company_id: str) -> None:
    """BC-001: company_id is required."""
    if not company_id or not company_id.strip():
        raise ParwaBaseError(
            error_code="INVALID_COMPANY_ID",
            message="company_id is required and cannot be empty",
            status_code=400,
        )


def _safe_parse_json(
    raw: str | None,
    fallback: Any = None,
) -> Any:
    """
    Safely parse a JSON string, returning fallback on any error.

    BC-008: Never crash on malformed JSON.
    Returns the parsed value if valid JSON, otherwise the fallback.
    """
    if not raw or not isinstance(raw, str) or not raw.strip():
        return fallback if fallback is not None else {}
    try:
        result = json.loads(raw)
        if result is None:
            return fallback if fallback is not None else {}
        return result
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning(
            "technique_cache_json_parse_failure",
            extra={
                "raw_length": len(raw) if raw else 0,
                "raw_prefix": (raw[:100] if raw else ""),
            },
        )
        return fallback if fallback is not None else {}


def _validate_cache_result(result: Any) -> str:
    """
    Validate and serialize a cache result before storing.

    Ensures the result is JSON-serializable and not empty.
    Returns the JSON string, or raises ParwaBaseError.

    BC-008: Validate before caching to prevent corruption.
    """
    if result is None:
        raise ParwaBaseError(
            error_code="INVALID_CACHE_RESULT",
            message="cached_result cannot be None",
            status_code=400,
        )
    try:
        serialized = json.dumps(result)
        # Validate round-trip (catches edge cases)
        json.loads(serialized)
        return serialized
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ParwaBaseError(
            error_code="INVALID_CACHE_RESULT",
            message=("cached_result is not valid JSON-serializable: " f"{str(exc)}"),
            status_code=400,
        )


def compute_query_hash(query: str) -> str:
    """Compute SHA-256 hash of a query string for cache lookup."""
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def get_cached_result(
    db: SessionLocal,
    company_id: str,
    technique_id: str,
    query_hash: str,
    instance_id: str | None = None,
) -> dict | None:
    """
    Retrieve a cached technique result with safe JSON parsing.

    Returns the parsed cached result dict, or None if not found
    or expired.

    BC-001: Filtered by company_id.
    BC-008: Malformed JSON returns None (never crashes).
    """
    _validate_company_id(company_id)

    try:
        entry = (
            db.query(TechniqueCache)
            .filter_by(
                company_id=company_id,
                technique_id=technique_id,
                query_hash=query_hash,
            )
            .first()
        )

        if instance_id is not None:
            entry = (
                db.query(TechniqueCache)
                .filter_by(
                    company_id=company_id,
                    technique_id=technique_id,
                    query_hash=query_hash,
                    instance_id=instance_id,
                )
                .first()
            )
    except Exception:
        logger.warning(
            "technique_cache_query_error",
            extra={"company_id": company_id, "technique_id": technique_id},
        )
        return None

    if entry is None:
        return None

    # Check TTL expiry
    if entry.ttl_expires_at and entry.ttl_expires_at < datetime.now(timezone.utc):
        return None

    # Safe JSON parse — BC-008: never crash on malformed data
    result = _safe_parse_json(entry.cached_result, fallback=None)
    if result is None:
        return None

    # Increment hit count (fire-and-forget, BC-008)
    try:
        entry.hit_count = (entry.hit_count or 0) + 1
        db.commit()
    except Exception:
        pass

    return result


def set_cached_result(
    db: SessionLocal,
    company_id: str,
    technique_id: str,
    query_hash: str,
    cached_result: Any,
    instance_id: str | None = None,
    similarity_score: float | None = None,
    signal_profile_hash: str | None = None,
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
) -> TechniqueCache:
    """
    Store a technique result in the cache with validation.

    Validates JSON structure before storing. Uses upsert logic
    (insert or update existing entry).

    BC-001: Filtered by company_id.
    BC-008: Validates before storing to prevent corruption.
    """
    _validate_company_id(company_id)

    # Validate and serialize result (BC-008)
    serialized = _validate_cache_result(cached_result)

    ttl_expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    # Check for existing entry (unique constraint)
    try:
        existing = (
            db.query(TechniqueCache)
            .filter_by(
                company_id=company_id,
                technique_id=technique_id,
                query_hash=query_hash,
                instance_id=instance_id,
            )
            .first()
        )
    except Exception:
        existing = None

    if existing is not None:
        # Update existing
        existing.cached_result = serialized
        existing.similarity_score = similarity_score
        existing.ttl_expires_at = ttl_expires
        existing.hit_count = 0
        db.commit()
        db.refresh(existing)
        return existing

    # Create new
    entry = TechniqueCache(
        company_id=company_id,
        instance_id=instance_id,
        technique_id=technique_id,
        query_hash=query_hash,
        signal_profile_hash=signal_profile_hash,
        cached_result=serialized,
        similarity_score=similarity_score,
        hit_count=0,
        ttl_expires_at=ttl_expires,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def invalidate_cached_result(
    db: SessionLocal,
    company_id: str,
    technique_id: str,
    query_hash: str,
    instance_id: str | None = None,
) -> bool:
    """
    Remove a cached technique result.

    Returns True if an entry was deleted, False otherwise.
    """
    _validate_company_id(company_id)

    try:
        entry = (
            db.query(TechniqueCache)
            .filter_by(
                company_id=company_id,
                technique_id=technique_id,
                query_hash=query_hash,
                instance_id=instance_id,
            )
            .first()
        )
    except Exception:
        return False

    if entry is None:
        return False

    try:
        db.delete(entry)
        db.commit()
        return True
    except Exception:
        return False


def cleanup_expired_entries(
    db: SessionLocal,
    company_id: str,
) -> int:
    """
    Remove all expired cache entries for a company.

    Returns the number of entries deleted.
    """
    _validate_company_id(company_id)

    try:
        expired = (
            db.query(TechniqueCache)
            .filter_by(
                company_id=company_id,
            )
            .filter(
                TechniqueCache.ttl_expires_at < datetime.now(timezone.utc),
            )
            .all()
        )

        count = len(expired)
        for entry in expired:
            db.delete(entry)
        if count > 0:
            db.commit()
        return count
    except Exception:
        return 0

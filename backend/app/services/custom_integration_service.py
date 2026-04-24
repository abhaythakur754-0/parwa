"""
PARWA Custom Integration Service (F-031)

Manages custom integrations of 5 types: rest, graphql, webhook_in, webhook_out, database.

Key features:
- REST/GraphQL connectors with auth_type, headers, request/response templates
- Webhook In: unique endpoint URL, expected payload schema, HMAC secret
- Webhook Out: url, method, headers, trigger events, payload template, retry
- Database: encrypted connection string, query template, field mapping, readonly
- Test connectivity with configurable timeouts (10s REST/GraphQL, 5s DB)
- Plan limits: Max 5 custom integrations per tenant (Growth), 20 (High)
- Error tracking: consecutive error count, auto-disable at 3 consecutive errors
- Credential masking: never expose secrets in API responses

Building Codes:
- BC-001: All operations scoped to company_id
- BC-011: Credentials encrypted at rest (AES-256), never in API responses
- BC-012: Graceful error handling, no raw errors exposed
"""

import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.exceptions import ValidationError
from app.logger import get_logger
from database.models.integration import CustomIntegration

logger = get_logger("custom_integration_service")

# ── Encryption Key Validation (D12-P2) ────────────────────────────

_DEV_FALLBACK_KEY = "parwa-dev-key-do-not-use-in-prod!"
_CLOUD_METADATA_HOSTNAMES = frozenset({
    "169.254.169.254",
    "metadata.google.internal",
    "metadata",
    "100.100.100.200",
    "fd00:ec2::254",
})


def validate_encryption_key() -> None:
    """Validate the PARWA_ENCRYPTION_KEY at startup.

    Call this during application startup to fail fast if the key is
    not properly configured. In development, log a warning instead of
    raising an error.
    """
    key = os.environ.get("PARWA_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "PARWA_ENCRYPTION_KEY environment variable is not set. "
            "This is required in production. Set a strong, unique key "
            "(at least 32 characters)."
        )
    if key == _DEV_FALLBACK_KEY:
        logger.warning(
            "encryption_key_using_dev_fallback",
            message="Using hardcoded development encryption key. "
                   "Set PARWA_ENCRYPTION_KEY to a strong, unique value in production.",
        )
    elif len(key) < 32:
        logger.warning(
            "encryption_key_too_short",
            message=f"PARWA_ENCRYPTION_KEY is only {len(key)} chars. "
                   f"Recommend at least 32 characters for security.",
        )
    else:
        logger.info(
            "encryption_key_validated",
            message="PARWA_ENCRYPTION_KEY is configured.",
        )

# ── Constants ───────────────────────────────────────────────────────

VALID_INTEGRATION_TYPES = {"rest", "graphql", "webhook_in", "webhook_out", "database"}
VALID_AUTH_TYPES = {"bearer", "basic", "api_key", "oauth2", "none"}
VALID_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
VALID_STATUSES = {"draft", "active", "disabled", "error"}

# Plan limits for custom integrations per tenant
PLAN_LIMITS: Dict[str, int] = {
    "free": 2,
    "mini_parwa": 3,
    "parwa": 5,
    "pro": 20,
    "enterprise": 100,
}

# Auto-disable threshold
MAX_CONSECUTIVE_ERRORS = 3

# Timeouts
REST_TIMEOUT_SECONDS = 10
DB_TIMEOUT_SECONDS = 5

# Type-specific required config fields
REQUIRED_CONFIG_FIELDS: Dict[str, List[str]] = {
    "rest": ["url", "method"],
    "graphql": ["url"],
    "webhook_in": [],
    "webhook_out": ["url", "method", "trigger_events"],
    "database": ["connection_string", "db_type"],
}


# ── Credential Helpers ──────────────────────────────────────────────


def _get_encryption_key() -> Tuple[bytes, str]:
    """Return (derived_key, key_source) — logs WARNING if using dev fallback (D12-P2)."""
    key_str = os.environ.get("PARWA_ENCRYPTION_KEY", _DEV_FALLBACK_KEY)
    if key_str == _DEV_FALLBACK_KEY:
        logger.warning(
            "encrypt_using_dev_key",
            message="Encryption is using the hardcoded dev fallback key. "
                   "Data will NOT be readable with a different key.",
        )
    return hashlib.sha256(key_str.encode()).digest(), key_str


def _compute_hmac(key: bytes, plaintext: bytes) -> bytes:
    """Compute HMAC-SHA256 for integrity verification (D12-P2)."""
    return hmac.new(key, plaintext, hashlib.sha256).digest()


def _encrypt_config(config: Dict[str, Any]) -> str:
    """Encrypt config JSON for storage.

    Uses AES-256-CBC with a deterministic key derived from the
    PARWA_ENCRYPTION_KEY env var (or a dev fallback).
    Prepends an HMAC of the plaintext for integrity verification.

    BC-011: Credentials encrypted at rest.
    """
    import base64

    key, _key_str = _get_encryption_key()
    plaintext = json.dumps(config, sort_keys=True).encode()

    # Compute HMAC of the plaintext before encryption
    integrity_hmac = _compute_hmac(key, plaintext)

    # AES-256-CBC with PKCS7 padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding

    iv = secrets.token_bytes(16)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    # Store as base64(hmac + iv + ciphertext)
    return base64.b64encode(integrity_hmac + iv + ciphertext).decode()


def _decrypt_config(encrypted: str) -> Dict[str, Any]:
    """Decrypt config JSON from storage.

    Verifies HMAC integrity before returning decrypted data.
    Logs CRITICAL if HMAC mismatch detected (possible key change).

    BC-011: Decrypt credentials from storage.
    """
    import base64

    if not encrypted:
        return {}

    try:
        key, _key_str = _get_encryption_key()

        raw = base64.b64decode(encrypted)
        # Layout: hmac(32) + iv(16) + ciphertext
        stored_hmac = raw[:32]
        iv = raw[32:48]
        ciphertext = raw[48:]

        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()

        # Verify HMAC integrity (D12-P2)
        expected_hmac = _compute_hmac(key, plaintext)
        if not hmac.compare_digest(stored_hmac, expected_hmac):
            logger.critical(
                "config_decryption_hmac_mismatch",
                message="HMAC integrity check FAILED on decrypted config. "
                       "This likely means the encryption key has changed "
                       "and existing encrypted data cannot be recovered.",
            )
            return {}

        return json.loads(plaintext.decode())
    except Exception:
        logger.error("config_decryption_failed", error="decryption_failed")
        return {}


def _mask_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive fields in config for API responses.

    BC-011: Never expose secrets in API responses.
    """
    sensitive_keys = {
        "api_key", "api_token", "token", "access_token", "secret",
        "password", "refresh_token", "bot_token", "client_secret",
        "connection_string", "auth_token", "private_key",
        "webhook_secret", "hmac_secret",
    }

    def _mask_value(value: Any) -> Any:
        if isinstance(value, str) and len(value) > 4:
            return value[:4] + "****"
        elif isinstance(value, str):
            return "****"
        elif isinstance(value, dict):
            return {k: _mask_value(v) for k, v in value.items()}
        return "****"

    masked = {}
    for key, value in config.items():
        if any(s in key.lower() for s in sensitive_keys):
            masked[key] = _mask_value(value)
        elif isinstance(value, dict):
            # Recurse into nested dicts to mask any sensitive inner keys
            masked[key] = _mask_config(value)
        else:
            masked[key] = value
    return masked


# ── SSRF Prevention ───────────────────────────────────────────────

_PRIVATE_CIDRS = [
    ipaddress.ip_network(cidr) for cidr in [
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        "127.0.0.0/8", "169.254.0.0/16", "::1/128", "fc00::/7",
    ]
]


def _validate_url(url: str) -> Optional[str]:
    """Validate URL is not pointing to private/internal IPs (SSRF prevention).

    Returns the resolved IP address string for DNS-rebinding prevention,
    or None if the URL is empty or cannot be resolved.

    Raises:
        ValidationError: If URL points to a blocked hostname or private IP.
    """
    if not url:
        return None
    import socket

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return None
        # Block localhost variants and cloud metadata hostnames
        if hostname in _CLOUD_METADATA_HOSTNAMES or hostname == "localhost":
            raise ValidationError(
                message="URL hostname is not allowed",
                details={"hostname": hostname, "reason": "blocked_hostname"},
            )
        # Check for link-local IPv6
        if hostname.startswith("fe80:"):
            raise ValidationError(
                message="URL points to a link-local address",
                details={"hostname": hostname},
            )
        # Resolve and check against private ranges
        addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        resolved_ip: Optional[str] = None
        for family, _, _, _, sockaddr in addr_infos:
            ip = ipaddress.ip_address(sockaddr[0])
            resolved_ip = sockaddr[0]
            for cidr in _PRIVATE_CIDRS:
                if ip in cidr:
                    raise ValidationError(
                        message="URL points to a private/internal IP address",
                        details={"hostname": hostname, "ip": str(ip)},
                    )
        return resolved_ip
    except ValidationError:
        raise
    except socket.gaierror:
        return None  # DNS resolution failed — not a private IP
    except Exception:
        return None  # Other errors — don't block on validation failure


def _validate_connection_string(conn_str: str) -> None:
    """Validate database connection string is not pointing to private/internal IPs (D12-P3).

    Parses connection strings for postgresql://, mysql://, mongodb://, sqlite://
    and extracts hostnames to validate against SSRF rules.
    """
    if not conn_str:
        return

    # SQLite is file-based, no network SSRF risk
    if conn_str.startswith("sqlite"):
        # Block attempts to use SQLite with special file paths
        if "://" in conn_str:
            parsed = urlparse(conn_str)
            if parsed.hostname and parsed.hostname in _CLOUD_METADATA_HOSTNAMES:
                raise ValidationError(
                    message="Database connection hostname is not allowed",
                    details={"hostname": parsed.hostname, "reason": "blocked_hostname"},
                )
        return

    try:
        parsed = urlparse(conn_str)
        hostname = parsed.hostname
        if not hostname:
            return

        # Block cloud metadata hostnames
        if hostname in _CLOUD_METADATA_HOSTNAMES or hostname == "localhost":
            raise ValidationError(
                message="Database connection hostname is not allowed",
                details={"hostname": hostname, "reason": "blocked_hostname"},
            )

        # Block link-local IPv6
        if hostname.startswith("fe80:"):
            raise ValidationError(
                message="Database connection points to a link-local address",
                details={"hostname": hostname},
            )

        # Resolve DNS and check against private ranges
        import socket
        addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in addr_infos:
            ip = ipaddress.ip_address(sockaddr[0])
            for cidr in _PRIVATE_CIDRS:
                if ip in cidr:
                    raise ValidationError(
                        message="Database connection string points to a private/internal IP address",
                        details={"hostname": hostname, "ip": str(ip)},
                    )
    except ValidationError:
        raise
    except (ValueError, socket.gaierror):
        pass  # Parse or DNS failure — don't block


# ── Service ─────────────────────────────────────────────────────────


class CustomIntegrationService:
    """Service for managing custom integrations (F-031).

    BC-001: All operations scoped to company_id.
    """

    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────

    def create(
        self,
        company_id: str,
        integration_type: str,
        name: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new custom integration in draft status.

        Args:
            company_id: Tenant ID (BC-001).
            integration_type: One of rest, graphql, webhook_in, webhook_out, database.
            name: Human-readable integration name.
            config: Type-specific configuration dict.

        Returns:
            Masked integration dict (BC-011).

        Raises:
            ValidationError: If type is invalid, config is incomplete, or plan limit exceeded.
        """
        # Validate type
        if integration_type not in VALID_INTEGRATION_TYPES:
            raise ValidationError(
                message=f"Invalid integration type: {integration_type}",
                details={"valid_types": sorted(VALID_INTEGRATION_TYPES)},
            )

        # Validate config fields
        required = REQUIRED_CONFIG_FIELDS[integration_type]
        missing = [f for f in required if not config.get(f)]
        if missing:
            raise ValidationError(
                message=f"Missing required config fields: {', '.join(missing)}",
                details={"missing_fields": missing, "integration_type": integration_type},
            )

        # Validate auth_type for rest/graphql
        if integration_type in ("rest", "graphql"):
            auth_type = config.get("auth_type", "none")
            if auth_type not in VALID_AUTH_TYPES:
                raise ValidationError(
                    message=f"Invalid auth_type: {auth_type}",
                    details={"valid_auth_types": sorted(VALID_AUTH_TYPES)},
                )

        # Validate method for rest/webhook_out
        if integration_type in ("rest", "webhook_out"):
            method = config.get("method", "POST").upper()
            if method not in VALID_HTTP_METHODS:
                raise ValidationError(
                    message=f"Invalid HTTP method: {method}",
                    details={"valid_methods": sorted(VALID_HTTP_METHODS)},
                )
            config["method"] = method

        # Validate URLs (SSRF prevention)
        if integration_type in ("rest", "graphql", "webhook_out"):
            _validate_url(config.get("url", ""))

        # Validate database connection strings (SSRF prevention — D12-P3)
        if integration_type == "database":
            _validate_connection_string(config.get("connection_string", ""))

        # Check plan limits
        self._check_plan_limit(company_id)

        # Generate webhook_id and secret for webhook_in (D12-P4: respect user-provided secret)
        webhook_id = None
        webhook_secret = None
        if integration_type == "webhook_in":
            webhook_id = str(secrets.token_urlsafe(32))
            # Use user-provided secret if present; otherwise generate one
            user_secret = config.get("secret")
            if user_secret and isinstance(user_secret, str) and user_secret.strip():
                webhook_secret = user_secret.strip()
            else:
                webhook_secret = secrets.token_urlsafe(48)
            config["secret"] = webhook_secret

        now = datetime.now(timezone.utc)

        integration = CustomIntegration(
            company_id=company_id,
            name=name,
            integration_type=integration_type,
            status="draft",
            config_encrypted=_encrypt_config(config),
            settings="{}",
            webhook_id=webhook_id,
            webhook_secret=webhook_secret,
            consecutive_error_count=0,
            created_at=now,
            updated_at=now,
        )

        self.db.add(integration)
        self.db.flush()

        logger.info(
            "custom_integration_created",
            integration_id=integration.id,
            company_id=company_id,
            type=integration_type,
            name=name,
        )

        result = self._to_dict(integration, mask_credentials=True)

        # D12-P4: Include unmasked webhook_secret in creation response so
        # the user can configure their external system before it gets masked
        if integration_type == "webhook_in" and webhook_secret:
            result["webhook_secret"] = webhook_secret

        return result

    def get(self, integration_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        """Get a single custom integration, scoped to company."""
        integration = self._get_by_id(integration_id, company_id)
        if not integration:
            return None
        return self._to_dict(integration, mask_credentials=True)

    def list(
        self,
        company_id: str,
        integration_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List custom integrations for a company with optional filters."""
        query = self.db.query(CustomIntegration).filter(
            CustomIntegration.company_id == company_id
        )

        if integration_type:
            if integration_type not in VALID_INTEGRATION_TYPES:
                raise ValidationError(
                    message=f"Invalid integration type: {integration_type}",
                    details={"valid_types": sorted(VALID_INTEGRATION_TYPES)},
                )
            query = query.filter(CustomIntegration.integration_type == integration_type)

        if status:
            if status not in VALID_STATUSES:
                raise ValidationError(
                    message=f"Invalid status: {status}",
                    details={"valid_statuses": sorted(VALID_STATUSES)},
                )
            query = query.filter(CustomIntegration.status == status)

        integrations = query.order_by(CustomIntegration.created_at.desc()).all()
        return [self._to_dict(i, mask_credentials=True) for i in integrations]

    def update(
        self,
        integration_id: str,
        company_id: str,
        config: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update a custom integration (draft or active).

        Args:
            integration_id: Integration UUID.
            company_id: Tenant ID.
            config: New config dict (merged with existing).
            name: New display name.
            settings: New settings dict.

        Returns:
            Masked integration dict.
        """
        integration = self._get_by_id(integration_id, company_id)
        if not integration:
            raise ValidationError(
                message="Custom integration not found",
                details={"integration_id": integration_id},
            )

        if integration.status not in ("draft", "active"):
            raise ValidationError(
                message=f"Cannot update integration in '{integration.status}' status",
                details={"current_status": integration.status},
            )

        now = datetime.now(timezone.utc)

        if name is not None:
            integration.name = name

        if config is not None:
            # Merge with existing config
            existing_config = _decrypt_config(integration.config_encrypted)
            merged = {**existing_config, **config}
            integration.config_encrypted = _encrypt_config(merged)
            # Reset error count on config change
            integration.consecutive_error_count = 0
            integration.last_error_message = None

        if settings is not None:
            integration.settings = json.dumps(settings)

        integration.updated_at = now
        self.db.flush()

        logger.info(
            "custom_integration_updated",
            integration_id=integration_id,
            company_id=company_id,
        )

        return self._to_dict(integration, mask_credentials=True)

    def delete(self, integration_id: str, company_id: str) -> bool:
        """Delete a custom integration."""
        integration = self._get_by_id(integration_id, company_id)
        if not integration:
            raise ValidationError(
                message="Custom integration not found",
                details={"integration_id": integration_id},
            )

        self.db.delete(integration)
        self.db.flush()

        logger.info(
            "custom_integration_deleted",
            integration_id=integration_id,
            company_id=company_id,
        )

        return True

    def activate(self, integration_id: str, company_id: str) -> Dict[str, Any]:
        """Activate a custom integration (draft → active).

        Args:
            integration_id: Integration UUID.
            company_id: Tenant ID.

        Returns:
            Updated integration dict.
        """
        integration = self._get_by_id(integration_id, company_id)
        if not integration:
            raise ValidationError(
                message="Custom integration not found",
                details={"integration_id": integration_id},
            )

        if integration.status != "draft":
            raise ValidationError(
                message=f"Cannot activate integration in '{integration.status}' status. "
                       f"Only draft integrations can be activated.",
                details={"current_status": integration.status},
            )

        now = datetime.now(timezone.utc)
        integration.status = "active"
        integration.consecutive_error_count = 0
        integration.last_error_message = None
        integration.updated_at = now
        self.db.flush()

        logger.info(
            "custom_integration_activated",
            integration_id=integration_id,
            company_id=company_id,
        )

        return self._to_dict(integration, mask_credentials=True)

    def reactivate(self, integration_id: str, company_id: str) -> Dict[str, Any]:
        """Reactivate a disabled integration (resets to draft).

        Clears error count and resets status to draft so the integration
        can be re-tested and re-activated.
        """
        integration = self._get_by_id(integration_id, company_id)
        if not integration:
            raise ValidationError(
                message="Custom integration not found",
                details={"integration_id": integration_id},
            )

        if integration.status != "disabled":
            raise ValidationError(
                message=f"Cannot reactivate integration in '{integration.status}' status. "
                       f"Only disabled integrations can be reactivated.",
                details={"current_status": integration.status},
            )

        now = datetime.now(timezone.utc)
        integration.status = "draft"
        integration.consecutive_error_count = 0
        integration.last_error_message = None
        integration.updated_at = now
        self.db.flush()

        logger.info(
            "custom_integration_reactivated",
            integration_id=integration_id,
            company_id=company_id,
        )

        return self._to_dict(integration, mask_credentials=True)

    # ── Testing ───────────────────────────────────────────────────

    def test_connectivity(
        self,
        integration_id: str,
        company_id: str,
        test_payload: Optional[Dict[str, Any]] = None,
        is_manual_test: bool = False,
    ) -> Dict[str, Any]:
        """Test connectivity for a custom integration.

        Makes real requests for REST/GraphQL (10s timeout),
        validates webhook config, or pings databases (5s timeout).

        Args:
            integration_id: Integration UUID.
            company_id: Tenant ID.
            test_payload: Optional test payload for webhook_out.
            is_manual_test: If True, do NOT increment consecutive_error_count
                or auto-disable on failure (D12-P5).

        Returns:
            Dict with success, message, latency_ms, tested_at.

        Raises:
            ValidationError: If integration not found.
        """
        integration = self._get_by_id(integration_id, company_id)
        if not integration:
            raise ValidationError(
                message="Custom integration not found",
                details={"integration_id": integration_id},
            )

        config = _decrypt_config(integration.config_encrypted)
        integration_type = integration.integration_type
        now = datetime.now(timezone.utc)

        try:
            if integration_type == "rest":
                result = self._test_rest(config)
            elif integration_type == "graphql":
                result = self._test_graphql(config)
            elif integration_type == "webhook_in":
                result = self._test_webhook_in(config, integration.webhook_id)
            elif integration_type == "webhook_out":
                result = self._test_webhook_out(config, test_payload)
            elif integration_type == "database":
                result = self._test_database(config)
            else:
                result = {
                    "success": False,
                    "message": f"Unknown integration type: {integration_type}",
                }
        except Exception as e:
            result = {
                "success": False,
                "message": f"Test failed: {str(e)}",
            }

        # Update test tracking
        integration.last_tested_at = now
        integration.last_test_result = result["message"]
        integration.updated_at = now

        if result["success"]:
            integration.consecutive_error_count = 0
            integration.last_error_message = None
        elif not is_manual_test:
            # D12-P5: Only increment error count for automated tests, not manual ones
            integration.consecutive_error_count += 1
            integration.last_error_message = result["message"]
            # Auto-disable at 3 consecutive errors
            if integration.consecutive_error_count >= MAX_CONSECUTIVE_ERRORS:
                integration.status = "disabled"
                result["auto_disabled"] = True
                logger.warning(
                    "custom_integration_auto_disabled",
                    integration_id=integration_id,
                    company_id=company_id,
                    error_count=integration.consecutive_error_count,
                )
        else:
            # Manual test failure — record the error message but don't increment
            integration.last_error_message = result["message"]

        self.db.flush()

        return {
            "integration_id": integration_id,
            "type": integration_type,
            "name": integration.name,
            "success": result["success"],
            "message": result["message"],
            "latency_ms": result.get("latency_ms"),
            "tested_at": now.isoformat(),
            "auto_disabled": result.get("auto_disabled", False),
        }

    def record_success(self, integration_id: str, company_id: str) -> None:
        """Record a successful interaction (resets error count).

        Called by the outgoing webhook service after successful delivery.
        """
        integration = self._get_by_id(integration_id, company_id)
        if not integration:
            return

        integration.consecutive_error_count = 0
        integration.last_error_message = None
        integration.updated_at = datetime.now(timezone.utc)
        self.db.flush()

    def record_failure(
        self,
        integration_id: str,
        company_id: str,
        error_message: str,
    ) -> bool:
        """Record a failed interaction.

        Increments error count and auto-disables at MAX_CONSECUTIVE_ERRORS.

        Returns:
            True if the integration was auto-disabled.
        """
        integration = self._get_by_id(integration_id, company_id)
        if not integration:
            return False

        integration.consecutive_error_count += 1
        integration.last_error_message = error_message
        integration.updated_at = datetime.now(timezone.utc)

        auto_disabled = False
        if integration.consecutive_error_count >= MAX_CONSECUTIVE_ERRORS:
            integration.status = "disabled"
            auto_disabled = True
            logger.warning(
                "custom_integration_auto_disabled",
                integration_id=integration_id,
                company_id=company_id,
                error_count=integration.consecutive_error_count,
                error_message=error_message,
            )

        self.db.flush()
        return auto_disabled

    def get_by_webhook_id(self, webhook_id: str) -> Optional[CustomIntegration]:
        """Look up a custom integration by webhook_id (for incoming webhooks)."""
        return (
            self.db.query(CustomIntegration)
            .filter(
                and_(
                    CustomIntegration.webhook_id == webhook_id,
                    CustomIntegration.integration_type == "webhook_in",
                    CustomIntegration.status == "active",
                )
            )
            .first()
        )

    # ── Test Methods ──────────────────────────────────────────────

    def _test_rest(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test REST connector connectivity (D12-P9: DNS-rebinding safe)."""
        import time

        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        headers = config.get("headers", {})

        if not url:
            return {"success": False, "message": "URL is required"}

        # D12-P9: Validate URL and get resolved IP for DNS-rebinding prevention
        resolved_ip = _validate_url(url)

        # Build auth headers
        auth_headers = self._build_auth_headers(config)
        headers = {**headers, **auth_headers}

        # D12-P9: If we resolved an IP, rewrite the URL to use it directly
        request_url = url
        if resolved_ip:
            try:
                parsed = urlparse(url)
                netloc = resolved_ip
                if parsed.port:
                    netloc = f"{resolved_ip}:{parsed.port}"
                request_url = parsed._replace(netloc=netloc).geturl()
                # Set Host header to original hostname
                headers["Host"] = parsed.hostname
            except Exception:
                request_url = url

        start = time.monotonic()
        try:
            # D12-P9: Disable redirect following to prevent redirect-based SSRF
            with httpx.Client(timeout=REST_TIMEOUT_SECONDS, follow_redirects=False) as client:
                response = client.request(
                    method=method,
                    url=request_url,
                    headers=headers,
                )
                latency = round((time.monotonic() - start) * 1000)

                if response.status_code < 400:
                    return {
                        "success": True,
                        "message": f"Connected successfully (HTTP {response.status_code})",
                        "latency_ms": latency,
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Client error HTTP {response.status_code}: authentication or configuration issue",
                        "latency_ms": latency,
                    }
        except httpx.TimeoutException:
            return {
                "success": False,
                "message": f"Connection timed out after {REST_TIMEOUT_SECONDS}s",
                "latency_ms": round((time.monotonic() - start) * 1000),
            }
        except httpx.ConnectError as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)[:200]}",
            }

    def _test_graphql(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test GraphQL connector connectivity (D12-P9: DNS-rebinding safe)."""
        import time

        url = config.get("url", "")
        headers = config.get("headers", {})

        if not url:
            return {"success": False, "message": "URL is required"}

        # D12-P9: Validate URL and get resolved IP for DNS-rebinding prevention
        resolved_ip = _validate_url(url)

        # Build auth headers
        auth_headers = self._build_auth_headers(config)
        headers = {**headers, **auth_headers}
        headers["Content-Type"] = "application/json"

        # D12-P9: If we resolved an IP, rewrite the URL to use it directly
        request_url = url
        if resolved_ip:
            try:
                parsed = urlparse(url)
                netloc = resolved_ip
                if parsed.port:
                    netloc = f"{resolved_ip}:{parsed.port}"
                request_url = parsed._replace(netloc=netloc).geturl()
                headers["Host"] = parsed.hostname
            except Exception:
                request_url = url

        # Send introspection query
        query = config.get("query_template") or "{ __typename }"
        payload = {"query": query}

        start = time.monotonic()
        try:
            # D12-P9: Disable redirect following to prevent redirect-based SSRF
            with httpx.Client(timeout=REST_TIMEOUT_SECONDS, follow_redirects=False) as client:
                response = client.post(request_url, json=payload, headers=headers)
                latency = round((time.monotonic() - start) * 1000)

                if response.status_code < 400:
                    try:
                        data = response.json()
                        if "errors" in data:
                            return {
                                "success": False,
                                "message": f"GraphQL error: {data['errors'][0].get('message', 'unknown')[:200]}",
                                "latency_ms": latency,
                            }
                    except Exception:
                        pass
                    return {
                        "success": True,
                        "message": f"Connected successfully (HTTP {response.status_code})",
                        "latency_ms": latency,
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Client error HTTP {response.status_code}: authentication or configuration issue",
                        "latency_ms": latency,
                    }
        except httpx.TimeoutException:
            return {
                "success": False,
                "message": f"Connection timed out after {REST_TIMEOUT_SECONDS}s",
                "latency_ms": round((time.monotonic() - start) * 1000),
            }
        except httpx.ConnectError as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)[:200]}",
            }

    def _test_webhook_in(self, config: Dict[str, Any], webhook_id: Optional[str]) -> Dict[str, Any]:
        """Validate webhook_in configuration."""
        if not webhook_id:
            return {"success": False, "message": "Webhook endpoint ID not generated"}

        secret = config.get("secret")
        if not secret:
            return {"success": False, "message": "HMAC secret not configured"}

        schema = config.get("expected_payload_schema")
        if not schema:
            return {"success": False, "message": "Expected payload schema is required"}

        return {
            "success": True,
            "message": "Webhook configuration is valid. "
                       f"Endpoint ID: {webhook_id[:16]}...",
        }

    def _test_webhook_out(
        self,
        config: Dict[str, Any],
        test_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Test webhook_out by sending a test payload."""
        import time

        url = config.get("url", "")
        method = config.get("method", "POST").upper()
        headers = config.get("headers", {})

        if not url:
            return {"success": False, "message": "URL is required"}

        _validate_url(url)

        payload = test_payload or config.get("payload_template") or {"test": True}
        headers["Content-Type"] = "application/json"

        start = time.monotonic()
        try:
            with httpx.Client(timeout=REST_TIMEOUT_SECONDS) as client:
                if method == "GET":
                    response = client.get(url, headers=headers, params=payload)
                else:
                    response = client.request(method=method, url=url, json=payload, headers=headers)
                latency = round((time.monotonic() - start) * 1000)

                if response.status_code < 500:
                    return {
                        "success": True,
                        "message": f"Test webhook delivered (HTTP {response.status_code})",
                        "latency_ms": latency,
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Target returned HTTP {response.status_code}",
                        "latency_ms": latency,
                    }
        except httpx.TimeoutException:
            return {
                "success": False,
                "message": f"Connection timed out after {REST_TIMEOUT_SECONDS}s",
                "latency_ms": round((time.monotonic() - start) * 1000),
            }
        except httpx.ConnectError as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)[:200]}",
            }

    def _test_database(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test database connectivity with a simple ping.

        Supports PostgreSQL, MySQL, and SQLite via SQLAlchemy.
        """
        import time

        db_type = config.get("db_type", "")
        connection_string = config.get("connection_string", "")

        if not connection_string:
            return {"success": False, "message": "Connection string is required"}

        if db_type not in ("postgresql", "mysql", "sqlite", "mongodb"):
            return {"success": False, "message": f"Unsupported db_type: {db_type}"}

        # D12-P3: Validate connection string for SSRF before connecting
        _validate_connection_string(connection_string)

        if db_type == "mongodb":
            # MongoDB doesn't use SQLAlchemy
            return self._test_mongodb(connection_string)

        start = time.monotonic()
        try:
            from sqlalchemy import create_engine, text

            # Mask password for logging
            log_conn = self._mask_connection_string(connection_string)
            engine = create_engine(
                connection_string,
                pool_pre_ping=True,
                connect_args={"connect_timeout": DB_TIMEOUT_SECONDS} if db_type == "postgresql" else {},
            )

            with engine.connect() as conn:
                if db_type == "postgresql":
                    conn.execute(text("SELECT 1"))
                elif db_type == "mysql":
                    conn.execute(text("SELECT 1"))
                elif db_type == "sqlite":
                    conn.execute(text("SELECT 1"))

            latency = round((time.monotonic() - start) * 1000)
            engine.dispose()

            return {
                "success": True,
                "message": f"{db_type.capitalize()} connection successful",
                "latency_ms": latency,
            }
        except Exception as e:
            latency = round((time.monotonic() - start) * 1000)
            return {
                "success": False,
                "message": f"{db_type.capitalize()} connection failed: {str(e)[:200]}",
                "latency_ms": latency,
            }

    def _test_mongodb(self, connection_string: str) -> Dict[str, Any]:
        """Test MongoDB connectivity."""
        import time

        start = time.monotonic()
        try:
            from pymongo import MongoClient
            from pymongo.errors import ServerSelectionTimeoutError

            client = MongoClient(connection_string, serverSelectionTimeoutMS=DB_TIMEOUT_SECONDS * 1000)
            # Force connection
            client.admin.command("ping")
            client.close()

            latency = round((time.monotonic() - start) * 1000)
            return {
                "success": True,
                "message": "MongoDB connection successful",
                "latency_ms": latency,
            }
        except ServerSelectionTimeoutError:
            return {
                "success": False,
                "message": f"MongoDB connection timed out after {DB_TIMEOUT_SECONDS}s",
                "latency_ms": round((time.monotonic() - start) * 1000),
            }
        except ImportError:
            return {"success": False, "message": "pymongo is not installed"}
        except Exception as e:
            return {
                "success": False,
                "message": f"MongoDB connection failed: {str(e)[:200]}",
            }

    # ── Helpers ───────────────────────────────────────────────────

    def _get_by_id(
        self, integration_id: str, company_id: str,
    ) -> Optional[CustomIntegration]:
        """Fetch integration by ID, scoped to company."""
        return (
            self.db.query(CustomIntegration)
            .filter(
                and_(
                    CustomIntegration.id == integration_id,
                    CustomIntegration.company_id == company_id,
                )
            )
            .first()
        )

    def _check_plan_limit(self, company_id: str) -> None:
        """Check if the tenant has reached their custom integration limit."""
        count = (
            self.db.query(CustomIntegration)
            .filter(CustomIntegration.company_id == company_id)
            .count()
        )

        # Default to growth plan limit if plan cannot be determined
        limit = PLAN_LIMITS.get("parwa", 5)

        try:
            from database.models.core import Company
            company = self.db.query(Company).filter(Company.id == company_id).first()
            if company and hasattr(company, "plan"):
                limit = PLAN_LIMITS.get(company.plan, limit)
        except Exception:
            pass

        if count >= limit:
            raise ValidationError(
                message=f"Custom integration limit reached ({count}/{limit})",
                details={
                    "current_count": count,
                    "limit": limit,
                    "upgrade_required": True,
                },
            )

    def _build_auth_headers(self, config: Dict[str, Any]) -> Dict[str, str]:
        """Build authentication headers from config."""
        auth_type = config.get("auth_type", "none")
        headers = {}

        if auth_type == "bearer":
            token = config.get("token") or config.get("access_token", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        elif auth_type == "basic":
            username = config.get("username", "")
            password = config.get("password", "")
            if username:
                import base64
                credentials = base64.b64encode(
                    f"{username}:{password}".encode()
                ).decode()
                headers["Authorization"] = f"Basic {credentials}"

        elif auth_type == "api_key":
            key_name = config.get("api_key_header", "X-API-Key")
            api_key = config.get("api_key", "")
            if api_key:
                headers[key_name] = api_key

        # oauth2 — use token if available (assumed to be refreshed externally)
        elif auth_type == "oauth2":
            token = config.get("access_token", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        return headers

    @staticmethod
    def _mask_connection_string(conn_str: str) -> str:
        """Mask password in a connection string for logging."""
        return re.sub(
            r"(://[^:]+:)([^@]+)(@)",
            r"\1****\3",
            conn_str,
        )

    def _to_dict(
        self,
        integration: CustomIntegration,
        mask_credentials: bool = True,
    ) -> Dict[str, Any]:
        """Convert CustomIntegration ORM to dict."""
        config = _decrypt_config(integration.config_encrypted)
        settings = _parse_json(integration.settings) or {}

        if mask_credentials:
            config = _mask_config(config)

        # Build webhook endpoint URL for webhook_in type
        webhook_url = None
        if integration.integration_type == "webhook_in" and integration.webhook_id:
            webhook_url = f"/api/integrations/webhooks/incoming/{integration.webhook_id}"

        return {
            "id": integration.id,
            "company_id": integration.company_id,
            "name": integration.name,
            "type": integration.integration_type,
            "status": integration.status,
            "config": config,
            "settings": settings,
            "webhook_id": integration.webhook_id,
            "webhook_url": webhook_url,
            "consecutive_error_count": integration.consecutive_error_count,
            "last_error_message": integration.last_error_message,
            "last_tested_at": (
                integration.last_tested_at.isoformat()
                if integration.last_tested_at
                else None
            ),
            "last_test_result": integration.last_test_result,
            "created_at": (
                integration.created_at.isoformat()
                if integration.created_at
                else None
            ),
            "updated_at": (
                integration.updated_at.isoformat()
                if integration.updated_at
                else None
            ),
        }


# ── Module-level Helpers ───────────────────────────────────────────


def _parse_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Safely parse JSON text."""
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

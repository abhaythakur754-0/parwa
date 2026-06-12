"""
PARWA Phase 3 — Outbound Webhook Registration

Manages outbound webhook registrations with third-party SaaS providers.
Each registration is scoped to company_id (BC-001).  Verification
methods validate incoming webhook signatures so PARWA can safely accept
callbacks.

All operations are wrapped in try/except (BC-008).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Integration-specific webhook configurations
# ------------------------------------------------------------------
WEBHOOK_CONFIGS: Dict[str, Dict[str, Any]] = {
    "hubspot": {
        "events": [
            "contact.created",
            "deal.updated",
        ],
        "signature_header": "X-HubSpot-Signature",
        "secret_field": "client_secret",
    },
    "shopify": {
        "events": [
            "orders/create",
            "customers/create",
        ],
        "signature_header": "X-Shopify-Hmac-Sha256",
        "secret_field": "shared_secret",
    },
    "stripe": {
        "events": [
            "payment_intent.succeeded",
            "invoice.paid",
        ],
        "signature_header": "Stripe-Signature",
        "secret_field": "webhook_secret",
    },
    "slack": {
        "events": [
            "message.channels",
        ],
        "signature_header": "X-Slack-Signature",
        "secret_field": "signing_secret",
    },
    "zendesk": {
        "events": [
            "ticket.created",
            "ticket.updated",
        ],
        "signature_header": "X-Zendesk-Webhook-Signature",
        "secret_field": "secret_key",
    },
}


class WebhookRegistrationService:
    """Register, list, and verify outbound webhooks for third-party services.

    All registrations are strictly scoped to company_id (BC-001).
    Storage is in-memory for Phase 3; production would persist to a
    database.
    """

    def __init__(self) -> None:
        # company_id -> { integration_type -> [webhook_dict, ...] }
        self._registrations: Dict[str, Dict[str, List[dict]]] = {}
        # webhook_id -> webhook_dict  (for O(1) lookup on unregister)
        self._index: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_webhook(
        self,
        company_id: str,
        integration_type: str,
        events: List[str],
        callback_url: str,
    ) -> dict:
        """Register a new outbound webhook.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        integration_type:
            One of the keys in :data:`WEBHOOK_CONFIGS`.
        events:
            List of event types to subscribe to.  Must be valid for the
            given *integration_type*.
        callback_url:
            The URL that the third party will POST to.

        Returns
        -------
        dict
            The created webhook registration record.
        """
        try:
            config = WEBHOOK_CONFIGS.get(integration_type)
            if config is None:
                logger.error(
                    "Unknown integration_type '%s' for webhook registration",
                    integration_type,
                )
                return {
                    "error": "unknown_integration",
                    "integration_type": integration_type,
                }

            # Validate events against the integration's allowed list
            allowed_events = set(config["events"])
            invalid_events = set(events) - allowed_events
            if invalid_events:
                logger.warning(
                    "Invalid events for %s: %s — filtering them out",
                    integration_type,
                    invalid_events,
                )
                events = [e for e in events if e in allowed_events]

            if not events:
                return {
                    "error": "no_valid_events",
                    "integration_type": integration_type,
                }

            webhook_id = f"wh_{uuid.uuid4().hex[:16]}"
            now = datetime.now(timezone.utc).isoformat()

            webhook_record = {
                "webhook_id": webhook_id,
                "company_id": company_id,
                "integration_type": integration_type,
                "events": events,
                "callback_url": callback_url,
                "secret": self._generate_secret(),
                "registered_at": now,
                "status": "active",
            }

            # Store
            if company_id not in self._registrations:
                self._registrations[company_id] = {}
            if integration_type not in self._registrations[company_id]:
                self._registrations[company_id][integration_type] = []
            self._registrations[company_id][integration_type].append(webhook_record)
            self._index[webhook_id] = webhook_record

            logger.info(
                "Registered webhook %s for company=%s integration=%s events=%s",
                webhook_id,
                company_id,
                integration_type,
                events,
            )

            # Return without exposing the raw secret
            return {
                "webhook_id": webhook_id,
                "company_id": company_id,
                "integration_type": integration_type,
                "events": events,
                "callback_url": callback_url,
                "registered_at": now,
                "status": "active",
            }

        except Exception as exc:
            logger.error(
                "Webhook registration failed for company_id=%s: %s", company_id, exc
            )
            return {
                "error": "registration_failed",
                "company_id": company_id,
                "integration_type": integration_type,
            }

    def unregister_webhook(
        self,
        company_id: str,
        integration_type: str,
        webhook_id: str,
    ) -> bool:
        """Remove a previously registered webhook.

        Parameters
        ----------
        company_id:
            Tenant identifier.
        integration_type:
            Integration type the webhook belongs to.
        webhook_id:
            The ID returned by :meth:`register_webhook`.

        Returns
        -------
        bool
            ``True`` if the webhook was found and removed.
        """
        try:
            webhooks = self._registrations.get(company_id, {}).get(
                integration_type, []
            )
            original_len = len(webhooks)

            self._registrations.setdefault(company_id, {}).setdefault(
                integration_type, []
            )
            self._registrations[company_id][integration_type] = [
                w for w in webhooks if w.get("webhook_id") != webhook_id
            ]

            # Also remove from index
            self._index.pop(webhook_id, None)

            removed = len(self._registrations[company_id][integration_type]) < original_len
            if removed:
                logger.info(
                    "Unregistered webhook %s for company=%s integration=%s",
                    webhook_id,
                    company_id,
                    integration_type,
                )
            else:
                logger.warning(
                    "Webhook %s not found for company=%s integration=%s",
                    webhook_id,
                    company_id,
                    integration_type,
                )
            return removed

        except Exception as exc:
            logger.error(
                "Webhook unregistration failed for company_id=%s: %s",
                company_id,
                exc,
            )
            return False

    def list_webhooks(
        self,
        company_id: str,
        integration_type: Optional[str] = None,
    ) -> List[dict]:
        """List all webhooks for *company_id*, optionally filtered by integration.

        Returns sanitized records (secrets excluded).
        """
        try:
            company_regs = self._registrations.get(company_id, {})
            results: List[dict] = []

            if integration_type:
                webhooks = company_regs.get(integration_type, [])
                for w in webhooks:
                    results.append(self._sanitize_webhook(w))
            else:
                for _itype, webhooks in company_regs.items():
                    for w in webhooks:
                        results.append(self._sanitize_webhook(w))

            return results

        except Exception as exc:
            logger.error(
                "list_webhooks failed for company_id=%s: %s", company_id, exc
            )
            return []

    def verify_webhook(
        self,
        integration_type: str,
        payload: dict,
        signature: str,
        secret: Optional[str] = None,
    ) -> bool:
        """Verify that an incoming webhook signature is authentic.

        Uses HMAC-SHA256 for most integrations.  Stripe uses a
        timestamp-prefixed signature scheme.

        Parameters
        ----------
        integration_type:
            Which integration sent the webhook.
        payload:
            The parsed JSON body of the webhook.
        signature:
            The signature from the webhook's signature header.
        secret:
            The shared secret for this webhook.  If ``None``, the secret
            is looked up from the internal index (by webhook_id in
            payload metadata).

        Returns
        -------
        bool
            ``True`` if the signature is valid.
        """
        try:
            config = WEBHOOK_CONFIGS.get(integration_type)
            if config is None:
                logger.error(
                    "Cannot verify webhook — unknown integration_type '%s'",
                    integration_type,
                )
                return False

            if secret is None:
                # Try to find the secret from stored registrations
                webhook_id = payload.get("webhook_id")
                if webhook_id and webhook_id in self._index:
                    secret = self._index[webhook_id].get("secret", "")
                else:
                    logger.warning(
                        "No secret provided and webhook_id not found in index"
                    )
                    return False

            raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True)

            if integration_type == "stripe":
                return self._verify_stripe_signature(
                    raw_body, signature, secret
                )

            return self._verify_hmac_sha256(raw_body, signature, secret)

        except Exception as exc:
            logger.error(
                "Webhook verification failed for integration_type=%s: %s",
                integration_type,
                exc,
            )
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_secret() -> str:
        """Generate a random webhook signing secret."""
        return uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars

    @staticmethod
    def _sanitize_webhook(webhook: dict) -> dict:
        """Return a copy of *webhook* without the ``secret`` field."""
        safe = dict(webhook)
        safe.pop("secret", None)
        return safe

    @staticmethod
    def _verify_hmac_sha256(
        raw_body: str, signature: str, secret: str
    ) -> bool:
        """Verify an HMAC-SHA256 signature."""
        try:
            expected = hmac.new(
                secret.encode("utf-8"),
                raw_body.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as exc:
            logger.error("HMAC-SHA256 verification failed: %s", exc)
            return False

    @staticmethod
    def _verify_stripe_signature(
        raw_body: str, signature_header: str, secret: str
    ) -> bool:
        """Verify a Stripe-style signature header.

        Stripe's signature header format::

            t=<timestamp>,v1=<signature>

        The signed payload is ``<timestamp>.<raw_body>``.
        """
        try:
            parts = {}
            for item in signature_header.split(","):
                key, _, value = item.partition("=")
                parts[key.strip()] = value.strip()

            timestamp = parts.get("t", "")
            v1_signature = parts.get("v1", "")

            if not timestamp or not v1_signature:
                logger.warning("Malformed Stripe signature header")
                return False

            signed_payload = f"{timestamp}.{raw_body}"
            expected = hmac.new(
                secret.encode("utf-8"),
                signed_payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(expected, v1_signature)
        except Exception as exc:
            logger.error("Stripe signature verification failed: %s", exc)
            return False

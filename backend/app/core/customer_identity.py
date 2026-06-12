"""
PARWA Phase 3 — Cross-Channel Customer Identity Resolution

Resolves customer identities across multiple channels (email, phone,
name) into a single unified profile.  All queries are scoped to
company_id (BC-001).  All operations are wrapped in try/except (BC-008).

Storage is in-memory for Phase 3; production would use a database with
proper indexing on email, phone, and unified_id.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# E.164 phone pattern: +[country_code][number], up to 15 digits total
_E164_PATTERN = re.compile(r"^\+\d{7,15}$")


@dataclass
class IdentityRecord:
    """Unified customer identity record."""

    id: str
    company_id: str
    unified_id: str
    email: Optional[str]
    phone: Optional[str]
    name: Optional[str]
    channels: List[dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class CustomerIdentityService:
    """Resolve and manage cross-channel customer identities.

    Each company's customer space is fully isolated by company_id.
    """

    def __init__(self) -> None:
        # company_id -> { unified_id -> IdentityRecord }
        self._customers: Dict[str, Dict[str, IdentityRecord]] = {}
        # company_id -> { normalized_email -> unified_id }
        self._email_index: Dict[str, Dict[str, str]] = {}
        # company_id -> { normalized_phone -> unified_id }
        self._phone_index: Dict[str, Dict[str, str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(
        self,
        company_id: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[str]:
        """Resolve a set of identifiers to a unified customer ID.

        The resolution strategy is:

        1. Look up by normalized email.
        2. If not found, look up by normalized phone.
        3. If still not found, create a new unified record.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        email:
            Customer email address.
        phone:
            Customer phone number (any common format).
        name:
            Customer display name.

        Returns
        -------
        Optional[str]
            The unified_id for the resolved or newly created customer.
        """
        try:
            normalized_email = self._normalize_email(email) if email else None
            normalized_phone = self._normalize_phone(phone) if phone else None

            # Try email lookup first
            if normalized_email:
                email_map = self._email_index.get(company_id, {})
                unified_id = email_map.get(normalized_email)
                if unified_id:
                    logger.info(
                        "Resolved customer %s by email for company %s",
                        unified_id,
                        company_id,
                    )
                    # Update name/phone if provided and missing
                    self._update_if_missing(
                        company_id, unified_id, email=normalized_email,
                        phone=normalized_phone, name=name
                    )
                    return unified_id

            # Try phone lookup
            if normalized_phone:
                phone_map = self._phone_index.get(company_id, {})
                unified_id = phone_map.get(normalized_phone)
                if unified_id:
                    logger.info(
                        "Resolved customer %s by phone for company %s",
                        unified_id,
                        company_id,
                    )
                    self._update_if_missing(
                        company_id, unified_id, email=normalized_email,
                        phone=normalized_phone, name=name
                    )
                    return unified_id

            # No match — create new
            unified_id = self._create_customer(
                company_id=company_id,
                email=normalized_email,
                phone=normalized_phone,
                name=name,
            )
            logger.info(
                "Created new customer %s for company %s", unified_id, company_id
            )
            return unified_id

        except Exception as exc:
            logger.error(
                "Identity resolution failed for company_id=%s: %s", company_id, exc
            )
            return None

    def link_channel(
        self,
        company_id: str,
        unified_id: str,
        channel: str,
        channel_id: str,
    ) -> bool:
        """Link an existing unified customer to an additional channel.

        Parameters
        ----------
        company_id:
            Tenant identifier.
        unified_id:
            The existing unified customer ID.
        channel:
            Channel name (e.g. ``"hubspot"``, ``"shopify"``).
        channel_id:
            The customer's ID on that channel.

        Returns
        -------
        bool
            ``True`` if linked successfully.
        """
        try:
            company_customers = self._customers.get(company_id, {})
            record = company_customers.get(unified_id)
            if record is None:
                logger.warning(
                    "Cannot link channel — customer %s not found for company %s",
                    unified_id,
                    company_id,
                )
                return False

            # Check if this channel+channel_id already linked
            for existing in record.channels:
                if existing.get("channel") == channel and existing.get(
                    "channel_id"
                ) == channel_id:
                    logger.debug(
                        "Channel %s/%s already linked for customer %s",
                        channel,
                        channel_id,
                        unified_id,
                    )
                    return True

            record.channels.append(
                {"channel": channel, "channel_id": channel_id}
            )
            record.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info(
                "Linked channel %s/%s to customer %s for company %s",
                channel,
                channel_id,
                unified_id,
                company_id,
            )
            return True

        except Exception as exc:
            logger.error(
                "link_channel failed for company_id=%s unified_id=%s: %s",
                company_id,
                unified_id,
                exc,
            )
            return False

    def get_customer(self, company_id: str, customer_id: str) -> dict:
        """Return the unified profile for *customer_id*.

        Returns an empty dict if the customer does not exist.
        """
        try:
            company_customers = self._customers.get(company_id, {})
            record = company_customers.get(customer_id)
            if record is None:
                return {}
            return asdict(record)
        except Exception as exc:
            logger.error(
                "get_customer failed for company_id=%s customer_id=%s: %s",
                company_id,
                customer_id,
                exc,
            )
            return {}

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_email(email: str) -> str:
        """Normalize an email: lowercase, strip whitespace.

        Also strips trailing dots which are valid but uncommon.
        """
        try:
            normalized = email.strip().lower()
            # Remove plus addressing (e.g. user+tag@gmail.com -> user@gmail.com)
            local, _, domain = normalized.partition("@")
            if "+" in local:
                local = local.split("+", 1)[0]
            return f"{local}@{domain}"
        except Exception as exc:
            logger.error("Email normalization failed for '%s': %s", email, exc)
            return email.strip().lower()

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize a phone number to E.164 format.

        Strips all non-digit characters and prepends ``+1`` if no
        country code is present (defaults to US).  Returns the original
        string stripped of whitespace if parsing fails.
        """
        try:
            digits = re.sub(r"\D", "", phone)
            if len(digits) == 10:
                # Assume US national number
                digits = "1" + digits
            if len(digits) == 11 and digits.startswith("1"):
                e164 = f"+{digits}"
            elif digits.startswith("+") or (len(digits) > 10 and digits[0] in "23456789"):
                e164 = f"+{digits}"
            else:
                e164 = f"+{digits}" if digits else phone.strip()

            if not _E164_PATTERN.match(e164):
                logger.warning(
                    "Phone did not produce valid E.164: '%s' -> '%s'", phone, e164
                )
            return e164
        except Exception as exc:
            logger.error("Phone normalization failed for '%s': %s", phone, exc)
            return phone.strip()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_company_space(self, company_id: str) -> None:
        """Create the company dict structures if they don't exist."""
        if company_id not in self._customers:
            self._customers[company_id] = {}
        if company_id not in self._email_index:
            self._email_index[company_id] = {}
        if company_id not in self._phone_index:
            self._phone_index[company_id] = {}

    def _create_customer(
        self,
        company_id: str,
        email: Optional[str],
        phone: Optional[str],
        name: Optional[str],
    ) -> str:
        """Create a new unified customer record and update indexes."""
        self._ensure_company_space(company_id)
        unified_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        record = IdentityRecord(
            id=str(uuid.uuid4()),
            company_id=company_id,
            unified_id=unified_id,
            email=email,
            phone=phone,
            name=name,
            channels=[],
            created_at=now,
            updated_at=now,
        )

        self._customers[company_id][unified_id] = record

        if email:
            self._email_index[company_id][email] = unified_id
        if phone:
            self._phone_index[company_id][phone] = unified_id

        return unified_id

    def _update_if_missing(
        self,
        company_id: str,
        unified_id: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        """Fill in missing fields on an existing record."""
        try:
            record = self._customers.get(company_id, {}).get(unified_id)
            if record is None:
                return

            updated = False
            if email and not record.email:
                record.email = email
                self._email_index.setdefault(company_id, {})[email] = unified_id
                updated = True
            if phone and not record.phone:
                record.phone = phone
                self._phone_index.setdefault(company_id, {})[phone] = unified_id
                updated = True
            if name and not record.name:
                record.name = name
                updated = True

            if updated:
                record.updated_at = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            logger.error(
                "_update_if_missing failed for company_id=%s unified_id=%s: %s",
                company_id,
                unified_id,
                exc,
            )

"""
PARWA AI — Provider Registry & Factory

The registry keeps a global mapping of ``category → provider_type → class``
so that the rest of the application can look up and instantiate adapters
without importing them directly.  The factory adds a thin async layer that
can pull persisted credentials from the database.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, Optional, Type

from .base import BaseProvider, ProviderCategory, ProviderResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ProviderRegistry:
    """Central registry of all available provider adapters.

    Structure::

        {
            "email": {
                "brevo": <class BrevoProvider>,
                "sendgrid": <class SendGridProvider>,
                ...
            },
            "sms": { ... },
            "payment": { ... },
        }

    Usage::

        ProviderRegistry.register("email", "brevo", BrevoProvider)
        cls = ProviderRegistry.get("email", "brevo")
    """

    _providers: Dict[str, Dict[str, Type[BaseProvider]]] = {}

    # ── Register ─────────────────────────────────────────────────────────

    @classmethod
    def register(
        cls,
        category: str,
        provider_type: str,
        provider_class: Type[BaseProvider],
    ) -> None:
        """Register a provider adapter class.

        Args:
            category:       One of :class:`ProviderCategory` values.
            provider_type:  Unique key within the category (e.g. ``"brevo"``).
            provider_class: The adapter class (must extend :class:`BaseProvider`).

        Raises:
            TypeError: If *provider_class* is not a :class:`BaseProvider` subclass.
        """
        if not (isinstance(provider_class, type) and issubclass(provider_class, BaseProvider)):
            raise TypeError(
                f"provider_class must be a subclass of BaseProvider, got {provider_class!r}"
            )

        category = cls._normalise_category(category)

        if category not in cls._providers:
            cls._providers[category] = {}

        existing = cls._providers[category].get(provider_type)
        if existing and existing is not provider_class:
            logger.warning(
                "Overwriting existing provider %s/%s: %s → %s",
                category,
                provider_type,
                existing.__name__,
                provider_class.__name__,
            )

        cls._providers[category][provider_type] = provider_class
        logger.debug("Registered provider %s/%s → %s", category, provider_type, provider_class.__name__)

    # ── Lookup ───────────────────────────────────────────────────────────

    @classmethod
    def get(cls, category: str, provider_type: str) -> Type[BaseProvider]:
        """Retrieve a provider class by category and type.

        Raises:
            KeyError: If the category or provider_type is not registered.
        """
        category = cls._normalise_category(category)
        try:
            return cls._providers[category][provider_type]
        except KeyError:
            available = cls.list_by_category(category)
            raise KeyError(
                f"Provider '{provider_type}' not found in category '{category}'. "
                f"Available: {list(available.keys())}"
            ) from None

    @classmethod
    def list_by_category(cls, category: str) -> Dict[str, Type[BaseProvider]]:
        """Return all registered providers for a given category."""
        category = cls._normalise_category(category)
        return dict(cls._providers.get(category, {}))

    @classmethod
    def list_all(cls) -> Dict[str, Dict[str, Type[BaseProvider]]]:
        """Return the full registry (deep copy)."""
        return {cat: dict(provs) for cat, provs in cls._providers.items()}

    @classmethod
    def categories(cls) -> list[str]:
        """Return registered category keys."""
        return list(cls._providers.keys())

    # ── Helpers ──────────────────────────────────────────────────────────

    @classmethod
    def _normalise_category(cls, category: str) -> str:
        """Accept both enum values and plain strings."""
        if isinstance(category, ProviderCategory):
            return category.value
        return str(category).lower().strip()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class ProviderFactory:
    """Create fully-initialised provider instances.

    Two modes:

    1. **From stored config** — looks up encrypted credentials in the DB
       for a specific company + category + provider_type.
    2. **With credentials** — directly supplies credentials (used during
       onboarding / testing before the config is saved).
    """

    # The DB module path is intentionally imported lazily so the factory
    # does not hard-depend on SQLAlchemy at import time.
    _DB_MODULE: str = "app.db.session"

    @staticmethod
    async def create_from_config(
        db: Any,
        company_id: str,
        category: str,
        provider_type: str,
    ) -> BaseProvider:
        """Instantiate a provider using credentials stored in the database.

        Args:
            db:            Async database session / dependency.
            company_id:    UUID of the tenant.
            category:      Provider category (e.g. ``"email"``).
            provider_type: Provider key (e.g. ``"brevo"``).

        Returns:
            A ready-to-use :class:`BaseProvider` instance with credentials set.

        Raises:
            KeyError:  If the provider is not registered.
            ValueError: If no configuration is found for the given company.
        """
        provider_cls = ProviderRegistry.get(category, provider_type)
        instance = provider_cls()

        # ── Load credentials from DB ─────────────────────────────────────
        try:
            credentials = await ProviderFactory._load_credentials(
                db, company_id, category, provider_type
            )
        except Exception as exc:
            logger.error(
                "Failed to load credentials for %s/%s (company=%s): %s",
                category,
                provider_type,
                company_id,
                exc,
            )
            raise ValueError(
                f"No stored configuration found for {category}/{provider_type} "
                f"in company {company_id}"
            ) from exc

        instance.set_credentials(credentials)
        logger.info(
            "Created provider %s/%s for company %s",
            category,
            provider_type,
            company_id,
        )
        return instance

    @staticmethod
    async def create_with_credentials(
        provider_type: str,
        category: str,
        credentials: dict,
    ) -> BaseProvider:
        """Instantiate a provider and immediately inject credentials.

        This is the path used during *Add Integration* flows where the user
        has just entered their API keys but the configuration has not been
        persisted yet.

        Args:
            provider_type: Provider key (e.g. ``"brevo"``).
            category:      Provider category (e.g. ``"email"``).
            credentials:   Raw credential dict (will **not** be persisted).

        Returns:
            A :class:`BaseProvider` instance with credentials set.
        """
        provider_cls = ProviderRegistry.get(category, provider_type)
        instance = provider_cls()
        instance.set_credentials(credentials)

        # Run a quick structural validation (no network call).
        validation = await instance.validate_credentials(credentials)
        if not validation.success:
            logger.warning(
                "Credential validation failed for %s/%s: %s",
                category,
                provider_type,
                validation.message,
            )

        return instance

    # ── Internal ─────────────────────────────────────────────────────────

    @staticmethod
    async def _load_credentials(
        db: Any,
        company_id: str,
        category: str,
        provider_type: str,
    ) -> Dict[str, Any]:
        """Fetch decrypted credentials from the database.

        This method attempts to import the ``ProviderConfiguration`` ORM model
        and query for the matching row.  If the ORM model is not yet available
        (e.g. during early bootstrap) a ``NotImplementedError`` is raised.
        """
        try:
            # Late import to avoid circular dependency at module level
            provider_config_module = importlib.import_module("app.models.provider_config")
            ProviderConfiguration = provider_config_module.ProviderConfiguration
        except (ImportError, AttributeError):
            logger.warning(
                "ProviderConfiguration model not available — "
                "returning empty credentials.  Ensure the model is importable "
                "at runtime."
            )
            # Fallback: attempt generic query pattern
            raise NotImplementedError(
                "ProviderConfiguration ORM model not found. "
                "Implement app.models.provider_config.ProviderConfiguration "
                "or override ProviderFactory._load_credentials."
            )

        # Standard SQLAlchemy async query pattern
        from sqlalchemy import select

        stmt = select(ProviderConfiguration).where(
            ProviderConfiguration.company_id == company_id,
            ProviderConfiguration.category == category,
            ProviderConfiguration.provider_type == provider_type,
            ProviderConfiguration.is_active.is_(True),
        )
        result = await db.execute(stmt)
        config = result.scalars().first()

        if not config:
            raise ValueError(
                f"No active configuration for {category}/{provider_type} "
                f"in company {company_id}"
            )

        # ``config.credentials`` should already be decrypted by the ORM
        # hybrid property or a dedicated encryption layer.
        return config.credentials if isinstance(config.credentials, dict) else {}

"""
PARWA Phase 3 — Industry Change Handler

Handles industry change with a preview + apply pattern:
  1. preview_industry_change() — shows impact WITHOUT making changes
  2. apply_industry_change()  — commits the change + logs audit trail

KEY PRINCIPLES:
- Industry is a SUGGESTION filter, not a restriction
- Existing connections NEVER auto-disconnect
- Tickets, KB, billing, webhooks are ALWAYS preserved
- Outside-industry integrations are flagged, not removed
- Preview shows impact WITHOUT making changes
- Apply actually makes changes + logs audit trail

CRITICAL RULES:
- BC-001: All queries scoped to company_id
- BC-008: Never crash — all external calls in try/except
- No mock data, no TODO/FIXME
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.auth_schema import AUTH_SCHEMA_REGISTRY
from app.core.audit_trail import AuditTrailService
from database.models.core import Company, CompanySetting
from database.models.integration import Integration
from database.base import SessionLocal

logger = logging.getLogger(__name__)


class IndustryChangeHandler:
    """Handles industry change with warning modal + connection preservation.

    KEY PRINCIPLES:
    - Industry is a SUGGESTION filter, not a restriction
    - Existing connections NEVER auto-disconnect
    - Tickets, KB, billing, webhooks are ALWAYS preserved
    - Outside-industry integrations are flagged, not removed
    - Preview shows impact WITHOUT making changes
    - Apply actually makes changes + logs audit trail
    """

    INDUSTRY_ENUM = {"ecommerce", "saas", "logistics", "general"}
    INDUSTRY_ALIASES = {"other": "general"}

    INDUSTRY_METADATA = {
        "ecommerce": {
            "label": "E-commerce",
            "primary_tools": [
                "shopify", "woocommerce", "bigcommerce", "stripe", "paypal",
                "klaviyo", "mailchimp", "shipstation", "aftership",
            ],
            "ai_tone": "friendly and sales-oriented",
            "ai_priority": "orders, refunds, shipping",
        },
        "saas": {
            "label": "SaaS",
            "primary_tools": [
                "hubspot", "salesforce", "pipedrive", "zendesk", "freshdesk",
                "intercom", "mixpanel", "amplitude", "github", "jira", "linear",
            ],
            "ai_tone": "professional and technical",
            "ai_priority": "subscriptions, technical support, feature requests",
        },
        "logistics": {
            "label": "Logistics",
            "primary_tools": [
                "hubspot", "salesforce", "zendesk", "freshdesk", "stripe",
                "shipstation", "aftership", "easypost", "fedex", "ups", "dhl",
            ],
            "ai_tone": "direct and efficient",
            "ai_priority": "shipments, tracking, delivery issues",
        },
        "general": {
            "label": "Other / General",
            "primary_tools": [],
            "ai_tone": "balanced and helpful",
            "ai_priority": "general support",
        },
    }

    def __init__(
        self,
        db_session=None,
        audit_service: Optional[AuditTrailService] = None,
    ) -> None:
        self.db_session = db_session
        self.audit_service = audit_service or AuditTrailService()

    # ------------------------------------------------------------------
    # Session helper
    # ------------------------------------------------------------------

    def _get_session(self):
        """Return the provided session or create a new one."""
        if self.db_session is not None:
            return self.db_session
        return SessionLocal()

    # ------------------------------------------------------------------
    # Industry normalisation
    # ------------------------------------------------------------------

    def _normalize_industry(self, industry: str) -> str:
        """Normalize an industry string to one of the canonical enum values.

        Falls back to ``"general"`` if the input is unrecognised.
        """
        try:
            lower = industry.strip().lower()
            if lower in self.INDUSTRY_ALIASES:
                return self.INDUSTRY_ALIASES[lower]
            if lower in self.INDUSTRY_ENUM:
                return lower
            return "general"
        except Exception:
            return "general"

    # ------------------------------------------------------------------
    # Public: preview
    # ------------------------------------------------------------------

    def preview_industry_change(
        self, company_id: str, new_industry: str
    ) -> dict:
        """Preview what would happen if industry changes.

        Returns warning data WITHOUT making changes.

        Format::

            {
                old_industry, new_industry,
                integrations: [{name, category, status, in_new_industry, message}],
                tickets_affected: False,   # ALWAYS False
                billing_affected: False,   # ALWAYS False
                kb_affected: False,        # ALWAYS False
            }
        """
        try:
            normalized_new = self._normalize_industry(new_industry)

            session = self._get_session()
            should_close = self.db_session is None
            try:
                company = (
                    session.query(Company)
                    .filter(Company.id == company_id)
                    .first()
                )
                if company is None:
                    return {
                        "error": f"Company {company_id} not found",
                        "company_id": company_id,
                    }

                old_industry = company.industry or "general"

                # Fetch all active integrations for this company
                integrations = (
                    session.query(Integration)
                    .filter(Integration.company_id == company_id)
                    .all()
                )

                integration_reports = []
                for integ in integrations:
                    status_info = self._get_integration_industry_status(
                        integ.integration_type, normalized_new
                    )
                    integration_reports.append({
                        "id": integ.id,
                        "name": integ.name,
                        "integration_type": integ.integration_type,
                        "category": integ.category,
                        "status": "active" if integ.is_active else "inactive",
                        "in_new_industry": status_info["in_industry"],
                        "message": status_info["message"],
                    })

                return {
                    "company_id": company_id,
                    "old_industry": old_industry,
                    "new_industry": normalized_new,
                    "old_industry_label": self.INDUSTRY_METADATA.get(
                        old_industry, {}
                    ).get("label", old_industry),
                    "new_industry_label": self.INDUSTRY_METADATA.get(
                        normalized_new, {}
                    ).get("label", normalized_new),
                    "integrations": integration_reports,
                    "tickets_affected": False,
                    "billing_affected": False,
                    "kb_affected": False,
                    "warning": (
                        "Existing integrations will NOT be auto-disconnected. "
                        "Outside-industry integrations will be flagged as informational."
                    ),
                }
            finally:
                if should_close:
                    session.close()

        except Exception as exc:
            logger.error(
                "preview_industry_change error (company_id=%s): %s",
                company_id,
                exc,
            )
            return {
                "error": f"Preview failed: {exc}",
                "company_id": company_id,
                "old_industry": "unknown",
                "new_industry": self._normalize_industry(new_industry),
                "integrations": [],
                "tickets_affected": False,
                "billing_affected": False,
                "kb_affected": False,
            }

    # ------------------------------------------------------------------
    # Public: apply
    # ------------------------------------------------------------------

    def apply_industry_change(
        self,
        company_id: str,
        new_industry: str,
        disconnect_ids: Optional[List[str]] = None,
    ) -> dict:
        """Actually apply the industry change.

        Steps:
        1. Update company.industry
        2. Flag outside-industry integrations in settings JSON
        3. Update AI tool priority via CompanySetting
        4. Log to audit trail
        5. If disconnect_ids provided, disconnect those specific integrations
        """
        try:
            normalized_new = self._normalize_industry(new_industry)

            session = self._get_session()
            should_close = self.db_session is None
            try:
                company = (
                    session.query(Company)
                    .filter(Company.id == company_id)
                    .first()
                )
                if company is None:
                    return {
                        "error": f"Company {company_id} not found",
                        "company_id": company_id,
                        "success": False,
                    }

                old_industry = company.industry or "general"

                # 1. Update company.industry
                company.industry = normalized_new
                company.updated_at = datetime.now(timezone.utc)

                # 2. Flag outside-industry integrations in settings JSON
                integrations = (
                    session.query(Integration)
                    .filter(Integration.company_id == company_id)
                    .all()
                )

                flagged_count = 0
                for integ in integrations:
                    status_info = self._get_integration_industry_status(
                        integ.integration_type, normalized_new
                    )
                    settings = integ.settings or {}
                    if status_info["in_industry"]:
                        settings.pop("outside_industry_flag", None)
                    else:
                        settings["outside_industry_flag"] = {
                            "flagged_at": datetime.now(timezone.utc).isoformat(),
                            "reason": (
                                f"Integration '{integ.integration_type}' is not in "
                                f"the recommended list for industry '{normalized_new}'"
                            ),
                            "previous_industry": old_industry,
                        }
                        flagged_count += 1
                    integ.settings = settings
                    integ.updated_at = datetime.now(timezone.utc)

                # 5. Disconnect specific integrations if requested
                disconnected = []
                if disconnect_ids:
                    for integ_id in disconnect_ids:
                        integ = (
                            session.query(Integration)
                            .filter(
                                Integration.id == integ_id,
                                Integration.company_id == company_id,
                            )
                            .first()
                        )
                        if integ is not None:
                            integ.is_active = False
                            integ.updated_at = datetime.now(timezone.utc)
                            settings = integ.settings or {}
                            settings["disconnected_by_industry_change"] = True
                            settings["disconnected_at"] = datetime.now(
                                timezone.utc
                            ).isoformat()
                            integ.settings = settings
                            disconnected.append({
                                "id": integ.id,
                                "name": integ.name,
                                "integration_type": integ.integration_type,
                            })

                # 3. Update AI tool priority via CompanySetting
                ai_priority_result = self._update_ai_tool_priority(
                    company_id, normalized_new, session=session
                )

                session.commit()

                # 4. Log to audit trail (outside the session to avoid
                   # coupling audit persistence with business transaction)
                self.audit_service.log_action(
                    company_id=company_id,
                    user_id="system",
                    action="industry_change",
                    tool="industry_change_handler",
                    details={
                        "old_industry": old_industry,
                        "new_industry": normalized_new,
                        "flagged_integrations": flagged_count,
                        "disconnected_integrations": len(disconnected),
                        "disconnected_details": disconnected,
                        "ai_priority_updated": ai_priority_result.get("success", False),
                    },
                    outcome="success",
                )

                return {
                    "success": True,
                    "company_id": company_id,
                    "old_industry": old_industry,
                    "new_industry": normalized_new,
                    "flagged_integrations": flagged_count,
                    "disconnected_integrations": disconnected,
                    "ai_priority_updated": ai_priority_result.get("success", False),
                    "tickets_affected": False,
                    "billing_affected": False,
                    "kb_affected": False,
                }

            except Exception as inner_exc:
                try:
                    session.rollback()
                except Exception:
                    pass
                raise inner_exc
            finally:
                if should_close:
                    session.close()

        except Exception as exc:
            logger.error(
                "apply_industry_change error (company_id=%s): %s",
                company_id,
                exc,
            )
            try:
                self.audit_service.log_action(
                    company_id=company_id,
                    user_id="system",
                    action="industry_change",
                    tool="industry_change_handler",
                    details={
                        "new_industry": self._normalize_industry(new_industry),
                        "error": str(exc),
                    },
                    outcome="failure",
                )
            except Exception:
                pass
            return {
                "error": f"Apply failed: {exc}",
                "company_id": company_id,
                "success": False,
            }

    # ------------------------------------------------------------------
    # Private: integration-industry status check
    # ------------------------------------------------------------------

    def _get_integration_industry_status(
        self, integration_type: str, new_industry: str
    ) -> dict:
        """Check if an integration is recommended for the new industry.

        Uses AUTH_SCHEMA_REGISTRY from auth_schema.py.
        For general/other industry, ALL integrations are recommended.

        Returns::

            {
                "in_industry": bool,
                "message": str,
                "industries": list[str]  # industries this integration supports
            }
        """
        try:
            normalized = self._normalize_industry(new_industry)

            # For general/other, every integration is recommended
            if normalized == "general":
                return {
                    "in_industry": True,
                    "message": "All integrations are recommended for the General industry.",
                    "industries": [],
                }

            catalog_entry = AUTH_SCHEMA_REGISTRY.get(integration_type)
            if catalog_entry is None:
                return {
                    "in_industry": True,
                    "message": (
                        f"Integration type '{integration_type}' is not in the catalog; "
                        f"treating as compatible."
                    ),
                    "industries": [],
                }

            supported_industries = [
                i.lower()
                for i in catalog_entry.get("industries", [])
            ]

            # "other" in catalog means the integration is always available
            effective_industries = set(supported_industries) - {"other"}
            always_available = "other" in supported_industries

            if normalized in effective_industries:
                return {
                    "in_industry": True,
                    "message": (
                        f"{catalog_entry.get('name', integration_type)} is recommended "
                        f"for the {normalized} industry."
                    ),
                    "industries": supported_industries,
                }

            if always_available:
                return {
                    "in_industry": True,
                    "message": (
                        f"{catalog_entry.get('name', integration_type)} is available "
                        f"for all industries (marked as 'other' compatible)."
                    ),
                    "industries": supported_industries,
                }

            return {
                "in_industry": False,
                "message": (
                    f"{catalog_entry.get('name', integration_type)} is not in the "
                    f"recommended list for the {normalized} industry. It will be "
                    f"flagged but NOT disconnected."
                ),
                "industries": supported_industries,
            }

        except Exception as exc:
            logger.error(
                "_get_integration_industry_status error (type=%s): %s",
                integration_type,
                exc,
            )
            # Per BC-008: never crash; default to in_industry=True
            # so we never accidentally block an integration.
            return {
                "in_industry": True,
                "message": f"Could not determine industry status; defaulting to compatible.",
                "industries": [],
            }

    # ------------------------------------------------------------------
    # Private: AI tool priority update
    # ------------------------------------------------------------------

    def _update_ai_tool_priority(
        self,
        company_id: str,
        new_industry: str,
        session=None,
    ) -> dict:
        """Update company settings with new industry's AI tool priorities.

        Creates or updates the ``ai_tool_priority`` CompanySetting row with:
        - primary_tools: list of recommended integration types
        - ai_tone: tone guidance for the AI agent
        - ai_priority: priority topics for the AI agent
        """
        try:
            normalized = self._normalize_industry(new_industry)
            metadata = self.INDUSTRY_METADATA.get(normalized, {})
            if not metadata:
                metadata = self.INDUSTRY_METADATA["general"]

            primary_tools = metadata.get("primary_tools", [])
            ai_tone = metadata.get("ai_tone", "balanced and helpful")
            ai_priority = metadata.get("ai_priority", "general support")

            setting_value = {
                "industry": normalized,
                "primary_tools": primary_tools,
                "ai_tone": ai_tone,
                "ai_priority": ai_priority,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            own_session = session is None
            if own_session:
                session = SessionLocal()

            try:
                existing = (
                    session.query(CompanySetting)
                    .filter(
                        CompanySetting.company_id == company_id,
                        CompanySetting.key == "ai_tool_priority",
                    )
                    .first()
                )

                if existing is not None:
                    existing.value = setting_value
                    existing.updated_at = datetime.now(timezone.utc)
                else:
                    new_setting = CompanySetting(
                        company_id=company_id,
                        key="ai_tool_priority",
                        value=setting_value,
                    )
                    session.add(new_setting)

                if own_session:
                    session.commit()

                return {
                    "success": True,
                    "industry": normalized,
                    "primary_tools": primary_tools,
                    "ai_tone": ai_tone,
                    "ai_priority": ai_priority,
                }
            finally:
                if own_session:
                    session.close()

        except Exception as exc:
            logger.error(
                "_update_ai_tool_priority error (company_id=%s): %s",
                company_id,
                exc,
            )
            return {
                "success": False,
                "error": f"Failed to update AI tool priority: {exc}",
            }

"""
PARWA Phase 4 — CRM Tool (wired to ProviderBridge)

Methods:
- get_contact: Look up customer info
- search_contacts: Search for customers
- update_contact: Update customer data
- add_note: Add a note to a customer record
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BaseReactTool, ToolResult, _mock_customer

logger = logging.getLogger(__name__)


class CRMTool(BaseReactTool):
    """CRM integration tool — HubSpot, Salesforce, etc.

    Priority: real provider via ProviderBridge → mock fallback
    """

    name = "crm_tool"
    description = "Look up customer info, order history, update contacts, add notes"
    category = "crm"

    async def get_contact(
        self,
        company_id: str,
        customer_id: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Look up a customer by ID."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="get_contact",
                fallback_fn=lambda **kw: _mock_customer(customer_id=customer_id),
                contact_id=customer_id,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Found customer {customer_id}",
                action_type="lookup_customer",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("crm get_contact failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="lookup_customer", variant_tier=variant_tier,
            )

    async def search_contacts(
        self,
        company_id: str,
        query: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Search for customers by name, email, or phone."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="search_contacts",
                fallback_fn=lambda **kw: [
                    _mock_customer(customer_id="cust-001", name="John Doe", email="john@example.com"),
                    _mock_customer(customer_id="cust-002", name="Jane Smith", email="jane@example.com"),
                ],
                query=query,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Found contacts matching '{query}'",
                action_type="search_contacts",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("crm search_contacts failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="search_contacts", variant_tier=variant_tier,
            )

    async def update_contact(
        self,
        company_id: str,
        customer_id: str,
        updates: Dict[str, Any],
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Update customer data in CRM."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="update_contact",
                fallback_fn=lambda **kw: {**_mock_customer(customer_id=customer_id), **updates},
                contact_id=customer_id,
                updates=updates,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Updated customer {customer_id}",
                action_type="update_customer",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("crm update_contact failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="update_customer", variant_tier=variant_tier,
            )

    async def add_note(
        self,
        company_id: str,
        customer_id: str,
        note: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Add a note to a customer record."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="add_note",
                fallback_fn=lambda **kw: {
                    "note_id": "note-001",
                    "customer_id": customer_id,
                    "note": note,
                    "added_at": "now",
                },
                contact_id=customer_id,
                note=note,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Note added to customer {customer_id}",
                action_type="add_note",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("crm add_note failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="add_note", variant_tier=variant_tier,
            )

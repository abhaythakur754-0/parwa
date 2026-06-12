"""
PARWA Phase 3 — AI Tool Selector

Builds per-ticket tool prompts from connected integrations + knowledge base.
Dynamically selects available tools based on what a company has connected,
and generates natural-language tool descriptions for the AI prompt.

Priority ordering: FAQ → KB → RAG → CRM → E-Commerce → Shipping → Payment → Custom

CRITICAL RULES:
- BC-001: All queries scoped to company_id
- BC-008: Never crash — all external calls in try/except
- No mock data, no TODO/FIXME
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.auth_schema import AUTH_SCHEMA_REGISTRY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category → tool-type mapping
# ---------------------------------------------------------------------------

CATEGORY_TOOL_MAP: Dict[str, str] = {
    "crm": "crm",
    "ecommerce": "ecommerce",
    "shipping": "shipping",
    "payment": "payment",
    "helpdesk": "helpdesk",
    "analytics": "analytics",
    "email": "email",
    "productivity": "productivity",
    "dev_tools": "dev_tools",
    "sms": "sms",
}

# Priority ordering for tool inclusion in prompts
TOOL_PRIORITY: List[str] = [
    "faq",
    "knowledge_base",
    "rag",
    "crm",
    "ecommerce",
    "shipping",
    "payment",
    "helpdesk",
    "analytics",
    "email",
    "productivity",
    "dev_tools",
    "sms",
    "custom",
]

# Intent → tool-type mapping for tool selection
INTENT_TOOL_MAP: Dict[str, List[str]] = {
    "billing": ["payment", "ecommerce", "crm"],
    "shipping": ["shipping", "ecommerce"],
    "order": ["ecommerce", "payment", "shipping"],
    "refund": ["payment", "ecommerce"],
    "account": ["crm", "helpdesk"],
    "technical": ["knowledge_base", "rag", "faq"],
    "general": ["faq", "knowledge_base"],
    "complaint": ["crm", "helpdesk"],
    "sales": ["crm", "ecommerce"],
    "support": ["helpdesk", "crm", "faq"],
    "product": ["ecommerce", "knowledge_base"],
    "analytics": ["analytics"],
    "notification": ["email", "sms"],
    "development": ["dev_tools"],
}

# Tool descriptions for the AI prompt
TOOL_DESCRIPTIONS: Dict[str, str] = {
    "faq": (
        "FAQ Lookup — Search the company's frequently asked questions database "
        "for exact or near-exact matches to the customer's question. "
        "Use this first before any other tool for common questions."
    ),
    "knowledge_base": (
        "Knowledge Base Search — Search the company's uploaded documents "
        "(PDFs, docs, pages) for relevant information. Returns document "
        "chunks ranked by relevance."
    ),
    "rag": (
        "RAG Retrieval — Retrieve context from the company's knowledge base "
        "using retrieval-augmented generation. Combines document search with "
        "contextual chunking for precise answers."
    ),
    "crm": (
        "CRM Actions — Look up, create, or update customer records in the "
        "connected CRM system (e.g. HubSpot, Salesforce, Pipedrive). "
        "Can fetch contact details, deal status, and interaction history."
    ),
    "ecommerce": (
        "E-Commerce Actions — Query and manage orders, products, and "
        "customers in the connected e-commerce platform (e.g. Shopify, "
        "WooCommerce, BigCommerce). Can check order status, process "
        "returns, and look up product information."
    ),
    "shipping": (
        "Shipping Actions — Track shipments, check delivery status, "
        "and manage shipping labels via the connected shipping provider "
        "(e.g. ShipStation, AfterShip, EasyPost, FedEx, UPS, DHL)."
    ),
    "payment": (
        "Payment Actions — Look up transactions, process refunds, and "
        "check payment status via the connected payment gateway "
        "(e.g. Stripe, PayPal, Razorpay)."
    ),
    "helpdesk": (
        "Helpdesk Actions — Create, update, and search tickets in the "
        "connected helpdesk system (e.g. Zendesk, Freshdesk, Intercom, "
        "Gorgias). Can escalate or merge tickets."
    ),
    "analytics": (
        "Analytics Actions — Query user behavior, event data, and "
        "metrics from the connected analytics platform "
        "(e.g. Mixpanel, Amplitude, Google Analytics)."
    ),
    "email": (
        "Email Actions — Send emails, manage campaigns, and look up "
        "subscriber data via the connected email platform "
        "(e.g. Mailchimp, Klaviyo, SendGrid, Brevo)."
    ),
    "productivity": (
        "Productivity Actions — Send messages, manage channels, and "
        "look up content via the connected productivity tool "
        "(e.g. Slack, Notion)."
    ),
    "dev_tools": (
        "Developer Tools — Access issues, pull requests, and project "
        "data via the connected development platform "
        "(e.g. GitHub, Jira, Linear)."
    ),
    "sms": (
        "SMS Actions — Send SMS messages and check delivery status "
        "via the connected SMS provider (e.g. Twilio, Vonage)."
    ),
    "custom": (
        "Custom Connector Actions — Execute actions defined in the "
        "company's custom REST connectors. Each connector exposes "
        "specific endpoints as named actions."
    ),
}


class AIToolSelector:
    """Builds per-ticket tool prompt from connected integrations + KB.

    Priority ordering: FAQ → KB → RAG → CRM → E-Commerce → Shipping → Payment → Custom
    """

    def __init__(self) -> None:
        # company_id -> { tool_type -> [integration_info, ...] }
        self._connected_tools: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_tool_prompt(
        self, company_id: str, intent: Optional[str] = None
    ) -> str:
        """Build the AI's available tools prompt for a ticket.

        Includes: connected integrations, KB status, FAQ count, custom connectors.
        Tools are ordered by priority.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        intent:
            Optional ticket intent to prioritize relevant tools.

        Returns
        -------
        str
            The formatted tool prompt for the AI.
        """
        try:
            company_tools = self._get_company_tools(company_id)
            kb_status = self._get_kb_status(company_id)
            faq_count = self._get_faq_count(company_id)
            custom_connectors = self._get_custom_connectors(company_id)

            # Build ordered tool list
            ordered_tools = self._order_tools(
                company_tools, intent, kb_status, faq_count, custom_connectors
            )

            if not ordered_tools:
                return (
                    "No tools are currently available. "
                    "Connect integrations or upload knowledge base documents "
                    "to enable AI-assisted actions."
                )

            lines = ["Available tools (use these to help resolve the ticket):"]
            lines.append("")

            for tool_entry in ordered_tools:
                tool_type = tool_entry["tool_type"]
                description = tool_entry.get("description", "")
                integrations = tool_entry.get("integrations", [])

                lines.append(f"## {tool_type.upper()}")
                lines.append(description)

                if integrations:
                    names = [i.get("name", "unknown") for i in integrations]
                    lines.append(f"Connected: {', '.join(names)}")

                lines.append("")

            return "\n".join(lines)

        except Exception as exc:
            logger.error(
                "build_tool_prompt failed for company_id=%s: %s", company_id, exc
            )
            return "Tool prompt generation failed. Proceed with general knowledge."

    def select_tools(
        self, company_id: str, intent: str, complexity: int
    ) -> List[Dict[str, Any]]:
        """Select appropriate tools based on intent and complexity.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        intent:
            The classified intent of the ticket (e.g. "billing", "shipping").
        complexity:
            Complexity score 1-5 (1=simple, 5=very complex).

        Returns
        -------
        list[dict]
            Selected tools with descriptions and relevance scores.
        """
        try:
            company_tools = self._get_company_tools(company_id)
            kb_status = self._get_kb_status(company_id)
            faq_count = self._get_faq_count(company_id)
            custom_connectors = self._get_custom_connectors(company_id)

            # Determine relevant tool types based on intent
            intent_tools = INTENT_TOOL_MAP.get(intent, ["faq", "knowledge_base"])

            # For low complexity, use only the most relevant tools
            # For high complexity, include more tools
            if complexity <= 2:
                max_tools = 3
            elif complexity <= 3:
                max_tools = 5
            else:
                max_tools = 8

            # Always include FAQ and KB if available
            always_include: List[str] = []
            if faq_count > 0:
                always_include.append("faq")
            if kb_status.get("ready_docs", 0) > 0:
                always_include.append("knowledge_base")

            # Merge intent tools with always-include, keeping priority order
            candidate_tools: List[str] = []
            for tool_type in TOOL_PRIORITY:
                if tool_type in intent_tools or tool_type in always_include:
                    if tool_type not in candidate_tools:
                        candidate_tools.append(tool_type)

            # Also add remaining always-include items
            for tool_type in always_include:
                if tool_type not in candidate_tools:
                    candidate_tools.append(tool_type)

            # Trim to max_tools
            candidate_tools = candidate_tools[:max_tools]

            # Build result with only available tools
            results: List[Dict[str, Any]] = []
            for tool_type in candidate_tools:
                tool_info = self._build_tool_entry(
                    tool_type, company_tools, kb_status, faq_count, custom_connectors
                )
                if tool_info:
                    # Calculate relevance score
                    relevance = self._calculate_relevance(
                        tool_type, intent, complexity, company_tools
                    )
                    tool_info["relevance"] = relevance
                    tool_info["selected_reason"] = (
                        "intent_match" if tool_type in intent_tools else "always_include"
                    )
                    results.append(tool_info)

            # Sort by relevance descending
            results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
            return results

        except Exception as exc:
            logger.error(
                "select_tools failed for company_id=%s: %s", company_id, exc
            )
            return []

    def get_tool_descriptions(self, company_id: str) -> List[Dict[str, Any]]:
        """Get natural language descriptions of all available tools.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).

        Returns
        -------
        list[dict]
            List of tool descriptions with availability status.
        """
        try:
            company_tools = self._get_company_tools(company_id)
            kb_status = self._get_kb_status(company_id)
            faq_count = self._get_faq_count(company_id)
            custom_connectors = self._get_custom_connectors(company_id)

            descriptions: List[Dict[str, Any]] = []

            for tool_type in TOOL_PRIORITY:
                tool_info = self._build_tool_entry(
                    tool_type, company_tools, kb_status, faq_count, custom_connectors
                )

                if tool_type == "faq":
                    available = faq_count > 0
                    descriptions.append({
                        "tool_type": tool_type,
                        "available": available,
                        "description": TOOL_DESCRIPTIONS.get(tool_type, ""),
                        "details": {"faq_count": faq_count},
                    })
                elif tool_type == "knowledge_base":
                    ready = kb_status.get("ready_docs", 0)
                    available = ready > 0
                    descriptions.append({
                        "tool_type": tool_type,
                        "available": available,
                        "description": TOOL_DESCRIPTIONS.get(tool_type, ""),
                        "details": kb_status,
                    })
                elif tool_type == "rag":
                    ready = kb_status.get("ready_docs", 0)
                    available = ready > 0
                    descriptions.append({
                        "tool_type": tool_type,
                        "available": available,
                        "description": TOOL_DESCRIPTIONS.get(tool_type, ""),
                        "details": kb_status,
                    })
                elif tool_type == "custom":
                    available = len(custom_connectors) > 0
                    descriptions.append({
                        "tool_type": tool_type,
                        "available": available,
                        "description": TOOL_DESCRIPTIONS.get(tool_type, ""),
                        "details": {
                            "connector_count": len(custom_connectors),
                            "connectors": [
                                c.get("name", "") for c in custom_connectors
                            ],
                        },
                    })
                else:
                    integrations = company_tools.get(tool_type, [])
                    available = len(integrations) > 0
                    descriptions.append({
                        "tool_type": tool_type,
                        "available": available,
                        "description": TOOL_DESCRIPTIONS.get(tool_type, ""),
                        "details": {
                            "integration_count": len(integrations),
                            "integrations": [
                                i.get("name", "") for i in integrations
                            ],
                        },
                    })

            return descriptions

        except Exception as exc:
            logger.error(
                "get_tool_descriptions failed for company_id=%s: %s",
                company_id,
                exc,
            )
            return []

    def refresh_company_tools(self, company_id: str) -> None:
        """Refresh the cached tool state for a company by re-querying the DB.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001).
        """
        try:
            self._connected_tools.pop(company_id, None)
            self._get_company_tools(company_id)
            logger.info("Refreshed tool cache for company_id=%s", company_id)
        except Exception as exc:
            logger.error(
                "refresh_company_tools failed for company_id=%s: %s",
                company_id,
                exc,
            )

    # ------------------------------------------------------------------
    # Tool ordering
    # ------------------------------------------------------------------

    def _order_tools(
        self,
        company_tools: Dict[str, List[Dict[str, Any]]],
        intent: Optional[str],
        kb_status: Dict[str, Any],
        faq_count: int,
        custom_connectors: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build ordered list of available tools, prioritized by TOOL_PRIORITY."""
        try:
            ordered: List[Dict[str, Any]] = []

            # If intent is provided, bring intent-relevant tools forward
            intent_tools = set()
            if intent:
                intent_tools = set(INTENT_TOOL_MAP.get(intent, []))

            for tool_type in TOOL_PRIORITY:
                tool_entry = self._build_tool_entry(
                    tool_type, company_tools, kb_status, faq_count, custom_connectors
                )
                if tool_entry:
                    ordered.append(tool_entry)

            # If there's an intent, re-order to bring relevant tools first
            if intent_tools:
                priority_tools = [t for t in ordered if t["tool_type"] in intent_tools]
                other_tools = [t for t in ordered if t["tool_type"] not in intent_tools]
                ordered = priority_tools + other_tools

            return ordered

        except Exception as exc:
            logger.error("_order_tools failed: %s", exc)
            return []

    def _build_tool_entry(
        self,
        tool_type: str,
        company_tools: Dict[str, List[Dict[str, Any]]],
        kb_status: Dict[str, Any],
        faq_count: int,
        custom_connectors: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Build a single tool entry dict if the tool is available."""
        try:
            description = TOOL_DESCRIPTIONS.get(tool_type, f"{tool_type} tool")

            if tool_type == "faq":
                if faq_count > 0:
                    return {
                        "tool_type": tool_type,
                        "description": description,
                        "integrations": [],
                        "metadata": {"faq_count": faq_count},
                    }
                return None

            if tool_type == "knowledge_base":
                ready_docs = kb_status.get("ready_docs", 0)
                if ready_docs > 0:
                    return {
                        "tool_type": tool_type,
                        "description": description,
                        "integrations": [],
                        "metadata": kb_status,
                    }
                return None

            if tool_type == "rag":
                ready_docs = kb_status.get("ready_docs", 0)
                if ready_docs > 0:
                    return {
                        "tool_type": tool_type,
                        "description": description,
                        "integrations": [],
                        "metadata": kb_status,
                    }
                return None

            if tool_type == "custom":
                if custom_connectors:
                    return {
                        "tool_type": tool_type,
                        "description": description,
                        "integrations": custom_connectors,
                        "metadata": {
                            "connector_count": len(custom_connectors),
                        },
                    }
                return None

            # Standard integration-based tools
            integrations = company_tools.get(tool_type, [])
            if integrations:
                return {
                    "tool_type": tool_type,
                    "description": description,
                    "integrations": integrations,
                    "metadata": {
                        "integration_count": len(integrations),
                    },
                }

            return None

        except Exception as exc:
            logger.error("_build_tool_entry failed for tool_type=%s: %s", tool_type, exc)
            return None

    # ------------------------------------------------------------------
    # Relevance scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_relevance(
        tool_type: str,
        intent: str,
        complexity: int,
        company_tools: Dict[str, List[Dict[str, Any]]],
    ) -> float:
        """Calculate a relevance score for a tool given intent and complexity.

        Score range: 0.0 – 1.0
        """
        try:
            score = 0.0

            # Base score from intent match
            intent_tools = INTENT_TOOL_MAP.get(intent, [])
            if tool_type in intent_tools:
                # Position in intent list matters (first = most relevant)
                position = intent_tools.index(tool_type)
                score += 0.5 + (0.1 * (len(intent_tools) - position)) / len(intent_tools)

            # Bonus for FAQ/KB (always useful)
            if tool_type in ("faq", "knowledge_base", "rag"):
                score += 0.2

            # Complexity bonus: high complexity needs more tools
            if complexity >= 4 and tool_type in ("crm", "helpdesk", "ecommerce"):
                score += 0.1

            # Availability bonus
            if tool_type in company_tools and company_tools[tool_type]:
                score += 0.1

            return min(1.0, round(score, 3))

        except Exception as exc:
            logger.error("_calculate_relevance failed: %s", exc)
            return 0.0

    # ------------------------------------------------------------------
    # Data retrieval (BC-001 scoped)
    # ------------------------------------------------------------------

    def _get_company_tools(
        self, company_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get all connected integration tools for a company.

        Returns a dict mapping tool_type → list of integration info dicts.
        Cached in memory; call refresh_company_tools to invalidate.
        """
        try:
            if company_id in self._connected_tools:
                return self._connected_tools[company_id]

            from database.base import SessionLocal
            from database.models.integration import Integration

            session = SessionLocal()
            try:
                integrations = (
                    session.query(Integration)
                    .filter(
                        Integration.company_id == company_id,
                        Integration.is_active == True,
                    )
                    .all()
                )

                tools: Dict[str, List[Dict[str, Any]]] = {}
                for i in integrations:
                    catalog_entry = AUTH_SCHEMA_REGISTRY.get(i.integration_type)
                    category = i.category
                    if catalog_entry:
                        category = catalog_entry.get("category", category)

                    tool_type = CATEGORY_TOOL_MAP.get(category, category)

                    if tool_type not in tools:
                        tools[tool_type] = []

                    tools[tool_type].append({
                        "id": i.id,
                        "name": i.name,
                        "integration_type": i.integration_type,
                        "category": category,
                        "tool_type": tool_type,
                    })

                self._connected_tools[company_id] = tools
                return tools
            finally:
                session.close()

        except Exception as exc:
            logger.error(
                "_get_company_tools failed for company_id=%s: %s", company_id, exc
            )
            return {}

    @staticmethod
    def _get_kb_status(company_id: str) -> Dict[str, Any]:
        """Get knowledge base status for a company.

        Returns dict with document counts by status.
        """
        try:
            from database.base import SessionLocal
            from database.models.knowledge import KnowledgeDocument

            session = SessionLocal()
            try:
                docs = (
                    session.query(KnowledgeDocument)
                    .filter(KnowledgeDocument.company_id == company_id)
                    .all()
                )

                ready = sum(1 for d in docs if d.status == "ready")
                processing = sum(1 for d in docs if d.status == "processing")
                failed = sum(1 for d in docs if d.status == "failed")
                total_chunks = sum(d.chunk_count for d in docs if d.status == "ready")

                return {
                    "total_docs": len(docs),
                    "ready_docs": ready,
                    "processing_docs": processing,
                    "failed_docs": failed,
                    "total_chunks": total_chunks,
                }
            finally:
                session.close()

        except Exception as exc:
            logger.error(
                "_get_kb_status failed for company_id=%s: %s", company_id, exc
            )
            return {"total_docs": 0, "ready_docs": 0, "processing_docs": 0, "failed_docs": 0, "total_chunks": 0}

    @staticmethod
    def _get_faq_count(company_id: str) -> int:
        """Get FAQ count for a company."""
        try:
            from database.base import SessionLocal
            from database.models.knowledge import FAQ

            session = SessionLocal()
            try:
                count = session.query(FAQ).filter(FAQ.company_id == company_id).count()
                return count
            finally:
                session.close()

        except Exception as exc:
            logger.error(
                "_get_faq_count failed for company_id=%s: %s", company_id, exc
            )
            return 0

    @staticmethod
    def _get_custom_connectors(company_id: str) -> List[Dict[str, Any]]:
        """Get active custom connectors for a company."""
        try:
            from database.base import SessionLocal
            from database.models.custom_connector import CustomConnector

            session = SessionLocal()
            try:
                connectors = (
                    session.query(CustomConnector)
                    .filter(
                        CustomConnector.company_id == company_id,
                        CustomConnector.is_active == True,
                    )
                    .all()
                )

                results = []
                for c in connectors:
                    actions_list = c.actions or []
                    action_names = []
                    if isinstance(actions_list, list):
                        action_names = [
                            a.get("name", "") if isinstance(a, dict) else str(a)
                            for a in actions_list
                        ]
                    elif isinstance(actions_list, dict):
                        action_names = list(actions_list.keys())

                    results.append({
                        "id": c.id,
                        "name": c.name,
                        "base_url": c.base_url,
                        "auth_type": c.auth_type,
                        "source": c.source,
                        "action_names": action_names,
                        "action_count": len(action_names),
                    })
                return results
            finally:
                session.close()

        except Exception as exc:
            logger.error(
                "_get_custom_connectors failed for company_id=%s: %s",
                company_id,
                exc,
            )
            return []

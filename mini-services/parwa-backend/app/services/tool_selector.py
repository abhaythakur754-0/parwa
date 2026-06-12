"""AI tool selection logic service (PHASE 14)."""
import json
from sqlalchemy.orm import Session
from app.models import IntegrationCredential, FAQEntry, KBDocument, CustomConnector


# --- Intent-to-tool mapping heuristics ---

INTENT_TOOL_MAP = {
    "billing": ["stripe", "paddle", "paypal"],
    "payment": ["stripe", "paddle", "paypal"],
    "subscription": ["stripe", "paddle"],
    "order": ["shopify", "woocommerce", "bigcommerce"],
    "shipping": ["shipstation", "aftership", "easypost", "fedex", "ups", "dhl"],
    "tracking": ["aftership", "easypost", "fedex", "ups", "dhl"],
    "contact": ["hubspot", "salesforce", "pipedrive"],
    "crm": ["hubspot", "salesforce", "pipedrive"],
    "deal": ["hubspot", "salesforce", "pipedrive"],
    "support": ["zendesk", "freshdesk", "intercom", "gorgias"],
    "ticket": ["zendesk", "freshdesk", "jira", "linear"],
    "issue": ["jira", "linear", "github"],
    "bug": ["github", "jira", "linear"],
    "feature": ["jira", "linear", "github"],
    "analytics": ["mixpanel", "amplitude", "google_analytics"],
    "email": ["mailchimp", "brevo", "klaviyo"],
    "marketing": ["mailchimp", "brevo", "klaviyo"],
    "notification": ["slack"],
    "communication": ["slack", "notion"],
    "documentation": ["notion"],
}


def select_tools(tenant_id: str, ticket_intent: str, db: Session) -> list:
    """
    Select the best tools for a given ticket intent.
    Priority: FAQ -> KB -> RAG -> External Integration
    
    Returns a list of tool definitions.
    """
    tools = []
    intent_lower = ticket_intent.lower()

    # 1. FAQ tools (highest priority for common questions)
    faq_count = db.query(FAQEntry).filter(FAQEntry.tenant_id == tenant_id).count()
    if faq_count > 0:
        # Check if intent matches any FAQ category
        faq_categories = (
            db.query(FAQEntry.category)
            .filter(FAQEntry.tenant_id == tenant_id)
            .distinct()
            .all()
        )
        faq_cats = [c[0] for c in faq_categories if c[0]]
        matches_faq = any(cat.lower() in intent_lower for cat in faq_cats) if faq_cats else True

        if matches_faq:
            tools.append({
                "id": "faq_search",
                "name": "FAQ Search",
                "type": "faq",
                "priority": 1,
                "description": f"Search through {faq_count} FAQ entries",
                "tool_definition": {
                    "name": "search_faq",
                    "description": "Search FAQ entries for answers to common questions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "category": {"type": "string", "description": "Optional category filter"},
                        },
                        "required": ["query"],
                    },
                },
            })

    # 2. KB search tools
    kb_docs = (
        db.query(KBDocument)
        .filter(
            KBDocument.tenant_id == tenant_id,
            KBDocument.status == "ready",
        )
        .all()
    )
    if kb_docs:
        total_chunks = sum(d.chunk_count for d in kb_docs)
        tools.append({
            "id": "kb_search",
            "name": "Knowledge Base Search",
            "type": "kb",
            "priority": 2,
            "description": f"Search through {len(kb_docs)} documents ({total_chunks} chunks)",
            "tool_definition": {
                "name": "search_knowledge_base",
                "description": "Search the knowledge base for relevant information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "top_k": {"type": "integer", "description": "Number of results to return", "default": 5},
                    },
                    "required": ["query"],
                },
            },
        })

    # 3. RAG response generation
    if kb_docs:
        tools.append({
            "id": "rag_response",
            "name": "RAG Response Generator",
            "type": "rag",
            "priority": 3,
            "description": "Generate responses using retrieved context from the knowledge base",
            "tool_definition": {
                "name": "generate_rag_response",
                "description": "Generate an AI response using retrieved knowledge base context",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Customer question"},
                        "context": {"type": "string", "description": "Retrieved context from KB search"},
                    },
                    "required": ["query", "context"],
                },
            },
        })

    # 4. External integration tools
    creds = (
        db.query(IntegrationCredential)
        .filter(
            IntegrationCredential.tenant_id == tenant_id,
            IntegrationCredential.status == "active",
        )
        .all()
    )

    connected_ids = [c.integration_id for c in creds]

    # Match intent to relevant integrations
    relevant_integrations = set()
    for intent_keyword, integration_ids in INTENT_TOOL_MAP.items():
        if intent_keyword in intent_lower:
            relevant_integrations.update(integration_ids)

    # If no specific match, include all connected integrations
    if not relevant_integrations:
        relevant_integrations = set(connected_ids)

    for cred in creds:
        if cred.integration_id in relevant_integrations:
            tools.append({
                "id": f"integration_{cred.integration_id}",
                "name": cred.integration_name,
                "type": "external_integration",
                "priority": 4,
                "integration_id": cred.integration_id,
                "description": f"Access {cred.integration_name} to retrieve or update data",
                "tool_definition": {
                    "name": f"call_{cred.integration_id}",
                    "description": f"Make API calls to {cred.integration_name}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "description": "The action to perform"},
                            "params": {"type": "object", "description": "Parameters for the action"},
                        },
                        "required": ["action"],
                    },
                },
            })

    # 5. Custom connector tools
    custom_connectors = (
        db.query(CustomConnector)
        .filter(
            CustomConnector.tenant_id == tenant_id,
            CustomConnector.status == "active",
        )
        .all()
    )

    for connector in custom_connectors:
        actions = json.loads(connector.actions) if connector.actions else []
        tool_actions = []
        for action in actions:
            tool_actions.append({
                "name": action.get("name", "unknown"),
                "description": action.get("description", ""),
                "parameters": action.get("parameters", {}),
            })

        tools.append({
            "id": f"custom_{connector.id}",
            "name": connector.name,
            "type": "custom_connector",
            "priority": 5,
            "description": f"Custom connector: {connector.name}",
            "base_url": connector.base_url,
            "actions": tool_actions,
            "tool_definition": {
                "name": f"custom_{connector.id}_call",
                "description": f"Call {connector.name} custom API",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "Action to perform", "enum": [a["name"] for a in tool_actions]},
                        "params": {"type": "object", "description": "Action parameters"},
                    },
                    "required": ["action"],
                },
            },
        })

    # Sort by priority
    tools.sort(key=lambda t: t["priority"])

    return tools


def build_system_prompt(tenant_id: str, db: Session) -> str:
    """Build a dynamic system prompt for the tenant with available tools."""
    tools = select_tools(tenant_id, "general", db)

    prompt_parts = [
        "You are an AI-powered customer support agent for PARWA.",
        "You have access to the following tools to help resolve customer issues:",
        "",
    ]

    for tool in tools:
        prompt_parts.append(f"## {tool['name']} (Priority: {tool['priority']})")
        prompt_parts.append(f"- Type: {tool['type']}")
        prompt_parts.append(f"- Description: {tool['description']}")
        if "tool_definition" in tool:
            td = tool["tool_definition"]
            prompt_parts.append(f"- Function: {td['name']}")
            if "parameters" in td:
                props = td["parameters"].get("properties", {})
                param_desc = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in props.items())
                prompt_parts.append(f"- Parameters: {param_desc}")
        prompt_parts.append("")

    prompt_parts.extend([
        "## Guidelines:",
        "1. Always check FAQ first for common questions",
        "2. Use KB search for detailed or technical questions",
        "3. Use RAG for generating contextual responses",
        "4. Use external integrations only when you need live data or to perform actions",
        "5. If multiple tools are relevant, use them in priority order",
        "6. Always verify the response quality before sending to the customer",
        "7. Never expose raw API keys or credentials in responses",
    ])

    return "\n".join(prompt_parts)

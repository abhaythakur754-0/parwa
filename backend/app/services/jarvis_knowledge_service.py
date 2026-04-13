"""
PARWA Jarvis Knowledge Service (Week 9 — Knowledge Integration)

Loads and searches the 10 core knowledge base JSON files to provide
context-accurate, PARWA-specific information for the Jarvis AI assistant.

This service is the source of truth for all product-related answers:
pricing, variants, integrations, demo scenarios, and objections.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Knowledge Base Files ──────────────────────────────────────────

KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "jarvis_knowledge"
)

KB_FILES = {
    "pricing": "01_pricing_tiers.json",
    "industries": "02_industry_variants.json",
    "variants": "03_variant_details.json",
    "integrations": "04_integrations.json",
    "capabilities": "05_capabilities.json",
    "demo": "06_demo_scenarios.json",
    "objections": "07_objection_handling.json",
    "faq": "08_faq.json",
    "competitors": "09_competitor_comparisons.json",
    "edge_cases": "10_edge_cases.json",
}

# ── Cache ──────────────────────────────────────────────────────────

_knowledge_cache: Dict[str, Any] = {}

def load_all_knowledge():
    """Load all JSON files into memory at startup/first call."""
    if _knowledge_cache:
        return

    for key, filename in KB_FILES.items():
        path = os.path.join(KNOWLEDGE_DIR, filename)
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    _knowledge_cache[key] = json.load(f)
                logger.info(f"Loaded knowledge base: {filename}")
            else:
                logger.warning(f"Knowledge file missing: {filename}")
                _knowledge_cache[key] = {}
        except Exception as e:
            logger.error(f"Failed to load knowledge file {filename}: {str(e)}")
            _knowledge_cache[key] = {}

# ── Public API ─────────────────────────────────────────────────────

def search_knowledge(query: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Search the knowledge base for snippets relevant to the query.
    
    Returns a list of match objects: {"source": str, "content": str, "score": float}
    """
    load_all_knowledge()
    
    query_lower = query.lower()
    matches = []
    
    # 1. Check FAQ
    faq = _knowledge_cache.get("faq", {})
    for item in faq.get("faqs", []):
        q = item.get("question", "").lower()
        if any(word in q for word in query_lower.split() if len(word) > 3):
            matches.append({
                "source": "08_faq.json",
                "content": f"FAQ: Q: {item['question']} A: {item['answer']}",
                "score": 0.9
            })

    # 2. Check Pricing if query contains pricing-related keywords
    pricing_keywords = ["price", "cost", "how much", "tier", "plan", "bill", "variant"]
    if any(k in query_lower for k in pricing_keywords):
        pricing = _knowledge_cache.get("pricing", {})
        for tier in pricing.get("pricing_tiers", []):
            matches.append({
                "source": "01_pricing_tiers.json",
                "content": f"PRICING TIER: {tier['name']} costs {tier['price']}/mo. Includes {tier['tickets_per_month']} tickets and features: {', '.join(tier['key_features'])}.",
                "score": 0.9
            })

    # 3. Check Capabilities
    capabilities = _knowledge_cache.get("capabilities", {})
    for cap in capabilities.get("capabilities", []):
        name = cap.get("name", "").lower()
        if any(word in name for word in query_lower.split() if len(word) > 3):
            matches.append({
                "source": "05_capabilities.json",
                "content": f"CAPABILITY: {cap['name']}: {cap['description']}. Key value: {cap.get('value_proposition', '')}",
                "score": 0.8
            })

    # 4. Check Objections
    objections = _knowledge_cache.get("objections", {})
    for obj in objections.get("objections", []):
        theme = obj.get("theme", "").lower()
        if any(word in theme for word in query_lower.split() if len(word) > 3):
            matches.append({
                "source": "07_objection_handling.json",
                "content": f"OBJECTION: When user says '{obj['theme']}', the answer is: {obj['best_response']}",
                "score": 0.85
            })

    # 5. Check Integrations
    integrations = _knowledge_cache.get("integrations", {})
    for cat in integrations.get("categories", []):
        for item in cat.get("items", []):
            name = item.get("name", "").lower()
            if any(word in name for word in query_lower.split() if len(word) > 3):
                matches.append({
                    "source": "04_integrations.json",
                    "content": f"INTEGRATION: We support {item['name']}. {item.get('description', '')}",
                    "score": 0.7
                })

    # Sort matches by score descending
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:5]

def search_and_format_knowledge(query: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Convenience: Search and return a formatted string for AI prompt injection."""
    matches = search_knowledge(query, context)
    if not matches:
        return ""
    return "## Relevant Knowledge Base Results:\n" + "\n\n".join([m["content"] for m in matches])

def build_context_knowledge(context: Dict[str, Any]) -> str:
    """Assembles a comprehensive knowledge section based on the session context.
    
    Considers:
    - Industry
    - Detected Stage
    - Selected Variants
    - User Intent
    """
    load_all_knowledge()
    
    sections = []
    industry = context.get("industry")
    stage = context.get("detected_stage", "welcome")
    
    # 1. Industry-specific knowledge
    if industry:
        industry_data = _knowledge_cache.get("industries", {})
        for ind in industry_data.get("industries", []):
            if ind["name"].lower() == industry.lower():
                sections.append(f"## Industry Context ({industry}):\n{ind['description']}")
                sections.append(f"Key Challenges: {', '.join(ind.get('common_pain_points', []))}")
                sections.append(f"Recommended Strategy: {ind.get('recommended_variant_strategy', '')}")
                break

    # 2. Stage-specific knowledge
    if stage == "pricing":
        pricing = _knowledge_cache.get("pricing", {})
        tiers = []
        for tier in pricing.get("pricing_tiers", []):
            tiers.append(f"- {tier['name']}: {tier['price']}/mo ({tier['tickets_per_month']} tickets)")
        sections.append("## Product Pricing:\n" + "\n".join(tiers))
        
    elif stage == "demo":
        scenarios = _knowledge_cache.get("demo", {})
        selected_scenarios = scenarios.get("demo_scenarios", [])[:3]
        scenes = []
        for s in selected_scenarios:
            scenes.append(f"- {s['name']}: {s['description']}")
        sections.append("## Available Demo Scenarios:\n" + "\n".join(scenes))
        sections.append("\nDemo Pack Details: $1 for 500 messages + 3-min AI call (24h access).")

    # 3. Variant details for clicked/selected variants
    variant_id = context.get("variant_id")
    if variant_id:
        variants = _knowledge_cache.get("variants", {})
        for v in variants.get("variants", []):
            if v["id"] == variant_id:
                sections.append(f"## Details for '{v['name']}':\n{v['description']}")
                sections.append(f"Problem solved: {v.get('problem_it_solves', '')}")
                sections.append(f"Differentiator: {v.get('differentiator', '')}")
                break

    # 4. Integration highlights (if discovery or demo)
    if stage in ["discovery", "demo"]:
        integrations = _knowledge_cache.get("integrations", {})
        top_cats = []
        for cat in integrations.get("categories", [])[:3]:
            items = ", ".join([i["name"] for i in cat.get("items", [])[:5]])
            top_cats.append(f"- {cat['category_name']}: {items}")
        sections.append("## Key Integrations:\n" + "\n".join(top_cats))

    return "\n\n".join(sections)

def get_edge_case_response(intent: str) -> Optional[str]:
    """Get specialized response for edge cases (competitors, legal, etc)."""
    load_all_knowledge()
    
    edge_cases = _knowledge_cache.get("edge_cases", {})
    for case in edge_cases.get("edge_cases", []):
        if case["type"] == intent:
            return case["recommended_response"]
    return None

# Initial load
load_all_knowledge()

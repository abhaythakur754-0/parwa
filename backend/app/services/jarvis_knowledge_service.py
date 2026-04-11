"""
PARWA Jarvis Knowledge Service (Week 6 — Day 5 Phase 7)

Loads and searches the Jarvis knowledge base (10 JSON files).
Provides product knowledge to the AI system prompt builder.

Functions:
  - load_all_knowledge(): Load all JSON files into memory
  - search_knowledge(query, industry?): Find relevant knowledge chunks
  - get_pricing_info(): Get current pricing data
  - get_industry_variants(industry): Get variants for specific industry
  - get_variant_details(variant_id): Get deep details for one variant
  - get_demo_scenario(industry?, difficulty?): Get appropriate demo scenario
  - get_objection_response(objection): Get response for specific objection
  - get_faq_answer(question): Find closest FAQ match
  - get_competitor_comparison(competitor): Get comparison points
  - get_edge_case_handler(scenario): Get edge case handling protocol
  - build_context_knowledge(context): Build relevant knowledge from session context
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────

KNOWLEDGE_DIR = Path(__file__).parent.parent / "data" / "jarvis_knowledge"

KNOWLEDGE_FILES = {
    "pricing_tiers": "01_pricing_tiers.json",
    "industry_variants": "02_industry_variants.json",
    "variant_details": "03_variant_details.json",
    "integrations": "04_integrations.json",
    "capabilities": "05_capabilities.json",
    "demo_scenarios": "06_demo_scenarios.json",
    "objection_handling": "07_objection_handling.json",
    "faq": "08_faq.json",
    "competitor_comparisons": "09_competitor_comparisons.json",
    "edge_cases": "10_edge_cases.json",
}

# In-memory knowledge cache
_knowledge_cache: dict[str, Any] = {}
_loaded = False


# ── Load All Knowledge ───────────────────────────────────────────

def load_all_knowledge() -> None:
    """Load all knowledge JSON files into memory. Called at app startup."""
    global _loaded

    if _loaded:
        logger.debug("Knowledge base already loaded, skipping.")
        return

    if not KNOWLEDGE_DIR.exists():
        logger.error(f"Knowledge directory not found: {KNOWLEDGE_DIR}")
        return

    loaded_count = 0
    for name, filename in KNOWLEDGE_FILES.items():
        filepath = KNOWLEDGE_DIR / filename
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                _knowledge_cache[name] = json.load(f)
            loaded_count += 1
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load knowledge file {filename}: {e}")

    _loaded = True
    logger.info(f"Knowledge base loaded: {loaded_count}/{len(KNOWLEDGE_FILES)} files")


def _ensure_loaded() -> None:
    """Ensure knowledge is loaded before any query."""
    if not _loaded:
        load_all_knowledge()


# ── Search Knowledge ──────────────────────────────────────────────

def search_knowledge(
    query: str,
    industry: Optional[str] = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Find relevant knowledge chunks for a query.
    Uses keyword matching (full word and partial) across all knowledge files.
    Returns list of {source, relevance_score, content} dicts.
    """
    _ensure_loaded()

    query_lower = query.lower()
    query_words = query_lower.split()

    results: list[dict[str, Any]] = []

    # Helper: count word-level matches between two strings
    def word_overlap(text: str, words: list[str]) -> int:
        text_lower = text.lower()
        text_words = set(text_lower.split())
        return len(words & text_words) + len([w for w in words if any(w in tw for tw in text_words)])

    # Search FAQ for question match
    faq_data = _knowledge_cache.get("faq", {})
    if faq_data.get("faqs"):
        for faq in faq_data["faqs"]:
            q_text = faq.get("q", "")
            score = word_overlap(q_text, query_words)
            if score > 0:
                results.append({
                    "source": "faq",
                    "relevance_score": score / max(len(q_text.split()), 1),
                    "question": q_text,
                    "content": faq.get("a", ""),
                    "type": "faq",
                })

    # Search objection handling
    obj_data = _knowledge_cache.get("objection_handling", {})
    if obj_data.get("objections"):
        for obj in obj_data["objections"]:
            score = word_overlap(obj.get("objection", ""), query_words)
            if score > 0:
                results.append({
                    "source": "objection_handling",
                    "relevance_score": score / max(len(obj.get("objection", "").split()), 1),
                    "content": obj.get("jarvis_response"),
                    "type": "objection",
                    "objection_id": obj.get("id"),
                })

    # Search edge cases
    edge_data = _knowledge_cache.get("edge_cases", {})
    if edge_data.get("edge_cases"):
        for edge in edge_data["edge_cases"]:
            score = word_overlap(edge.get("scenario", ""), query_words)
            if score > 0:
                results.append({
                    "source": "edge_cases",
                    "relevance_score": score / max(len(edge.get("scenario", "").split()), 1),
                    "content": edge.get("example_response"),
                    "type": "edge_case",
                    "scenario_id": edge.get("id"),
                })

    # Search capabilities
    cap_data = _knowledge_cache.get("capabilities", {})
    cap_text = json.dumps(cap_data.get("what_jarvis_can_do", []))
    score = word_overlap(cap_text, query_words)
    if score > 0:
        results.append({
            "source": "capabilities",
            "relevance_score": score / max(len(cap_text.split()), 1) * 0.5,
            "content": json.dumps(cap_data),
            "type": "capabilities",
        })


# ── Specific Getters ─────────────────────────────────────────────

def get_pricing_info() -> dict[str, Any]:
    """Get current pricing data for all tiers."""
    _ensure_loaded()
    return _knowledge_cache.get("pricing_tiers", {})


def get_industry_variants(industry: Optional[str] = None) -> dict[str, Any]:
    """Get variants for a specific industry. Returns all if no industry specified."""
    _ensure_loaded()
    data = _knowledge_cache.get("industry_variants", {})
    if industry:
        for ind in data.get("industries", []):
            if ind.get("id") == industry or ind.get("name", "").lower() == industry.lower():
                return ind
        # Return empty if not found
        return {"industry": industry, "error": "Industry not found", "variants": []}
    return data


def get_variant_details(variant_id: str) -> Optional[dict[str, Any]]:
    """Get deep details for a specific variant by ID."""
    _ensure_loaded()
    data = _knowledge_cache.get("variant_details", {})
    return data.get("variants", {}).get(variant_id)


def get_demo_scenario(
    industry: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Get an appropriate demo scenario. Filters by industry and difficulty."""
    _ensure_loaded()
    data = _knowledge_cache.get("demo_scenarios", {})
    scenarios = data.get("scenarios", [])

    filtered = scenarios
    if industry:
        filtered = [s for s in filtered if s.get("industry") == industry]
    if difficulty:
        filtered = [s for s in filtered if s.get("difficulty") == difficulty]

    if not filtered:
        # Fallback: return first matching industry or first overall
        if industry:
            filtered = [s for s in scenarios if s.get("industry") == industry]
        if not filtered:
            filtered = scenarios

    return filtered[0] if filtered else None


def get_objection_response(objection: str) -> Optional[dict[str, Any]]:
    """Get response strategy for a specific objection."""
    _ensure_loaded()
    data = _knowledge_cache.get("objection_handling", {})

    # Exact ID match
    for obj in data.get("objections", []):
        if obj.get("id") == objection:
            return obj

    # Fuzzy match by keyword
    objection_lower = objection.lower()
    best_match = None
    best_score = 0
    for obj in data.get("objections", []):
        obj_text = obj.get("objection", "").lower()
        if objection_lower in obj_text or obj_text in objection_lower:
            return obj
        # Simple word overlap scoring
        overlap = len(set(objection_lower.split()) & set(obj_text.split()))
        if overlap > best_score:
            best_score = overlap
            best_match = obj

    # Return best fuzzy match if we have one
    if best_match and best_score > 0:
        return best_match
    return None


def get_faq_answer(question: str) -> Optional[dict[str, str]]:
    """Find the closest FAQ match for a question. Returns {q, a}."""
    _ensure_loaded()
    data = _knowledge_cache.get("faq", {})

    question_lower = question.lower()
    q_tokens = set(question_lower.split())

    best_match = None
    best_score = 0

    for faq in data.get("faqs", []):
        q_text = faq.get("q", "").lower()
        q_tokens_set = set(q_text.split())
        overlap = len(q_tokens & q_tokens_set)
        if overlap > best_score:
            best_score = overlap
            best_match = faq

    if best_match and best_score > 0:
        return {"q": best_match.get("q", ""), "a": best_match.get("a", "")}

    return None


def get_competitor_comparison(competitor: str) -> Optional[dict[str, Any]]:
    """Get comparison points for a specific competitor."""
    _ensure_loaded()
    data = _knowledge_cache.get("competitor_comparisons", {})

    # Try by ID
    for comp in data.get("competitors", []):
        if comp.get("id") == competitor:
            return comp

    # Fuzzy match
    competitor_lower = competitor.lower()
    for comp in data.get("competitors", []):
        if competitor_lower in comp.get("competitor", "").lower():
            return comp

    return None


def get_edge_case_handler(scenario: str) -> Optional[dict[str, Any]]:
    """Get handling protocol for a specific edge case scenario."""
    _ensure_loaded()
    data = _knowledge_cache.get("edge_cases", {})

    # Try by ID
    for edge in data.get("edge_cases", []):
        if edge.get("id") == scenario:
            return edge

    # Fuzzy match
    scenario_lower = scenario.lower()
    for edge in data.get("edge_cases", []):
        if scenario_lower in edge.get("scenario", "").lower():
            return edge

    return None


def get_integrations() -> list[dict[str, Any]]:
    """Get list of all supported integrations."""
    _ensure_loaded()
    data = _knowledge_cache.get("integrations", {})
    return data.get("integrations", [])


def get_capabilities() -> dict[str, Any]:
    """Get PARWA capabilities and limitations."""
    _ensure_loaded()
    return _knowledge_cache.get("capabilities", {})


# ── Build Context Knowledge ──────────────────────────────────────

def build_context_knowledge(
    context: dict[str, Any],
) -> str:
    """
    Build relevant knowledge context from session context.
    Used by build_system_prompt() to inject into AI system prompt.
    Returns formatted string for system prompt injection.
    """
    _ensure_loaded()

    sections: list[str] = []

    # 1. If industry detected, add industry variants
    industry = context.get("industry")
    if industry:
        variants = get_industry_variants(industry)
        if variants and "variants" in variants:
            variant_names = [v.get("name", "") for v in variants["variants"]]
            sections.append(
                f"Customer is in {industry} industry. "
                f"Available PARWA variants: {', '.join(variant_names)}. "
                f"Each is tailored for {industry} support workflows."
            )

    # 2. If specific variants selected, add variant details
    selected_variants = context.get("selected_variants", [])
    if selected_variants:
        for v in selected_variants:
            details = get_variant_details(v.get("id", ""))
            if details:
                sections.append(
                    f"Customer is interested in the {details.get('id', '')} variant. "
                    f"Description: {details.get('description', '')}. "
                    f"It handles: {', '.join(details.get('what_it_handles', [])[:5])}."
                )

    # 3. If ROI result available, add pricing context
    roi = context.get("roi_result")
    if roi:
        pricing = get_pricing_info()
        tiers = pricing.get("tiers", [])
        if tiers:
            sections.append(
                f"Customer's ROI analysis: {roi.get('monthly_tickets', 0)} tickets/month, "
                f"saves ${roi.get('monthly_cost', 0)}/month, annual savings "
                f"${roi.get('annual_savings', 0)}. Current tiers: "
                f"Starter ${tiers[0].get('price_monthly', '')}/mo, "
                f"Growth ${tiers[1].get('price_monthly', '')}/mo, "
                f"High ${tiers[2].get('price_monthly', '')}/mo."
            )

    # 4. If conversation stage detected, add stage-specific knowledge
    stage = context.get("detected_stage")
    if stage:
        if stage == "pricing":
            sections.append("Customer is at the pricing stage. Key talking points: ROI comparison, cost savings vs human agents, tier features, overage rate ($0.10/ticket).")
        elif stage == "demo":
            demo = get_demo_scenario(context.get("industry"))
            if demo:
                sections.append(f"Suggested demo scenario: {demo.get('title', '')} — {demo.get('expected_jarvis_behavior', '')}.")

    # 5. If entry source detected, add contextual info
    entry = context.get("entry_source")
    if entry:
        if entry == "pricing":
            sections.append("Customer arrived from pricing page. They are actively evaluating plans and pricing.")
        elif entry == "demo":
            sections.append("Customer arrived after requesting a demo. They want to see PARWA in action.")
        elif entry == "features":
            sections.append("Customer is exploring PARWA features. Provide detailed feature comparisons and use cases.")

    # 6. If concerns were raised, look for objection responses
    concerns = context.get("concerns_raised", [])
    for concern in concerns:
        response = get_objection_response(concern.lower())
        if response:
            sections.append(
                f"Customer raised concern about '{concern}'. "
                f"Response strategy: {response.get('response_strategy', '')}. "
                f"Key point: {response.get('jarvis_response', '')[:200]}"
            )

    return "\n\n".join(sections) if sections else ""

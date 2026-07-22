"""
Jarvis Skill Instructor — Wave 8B: Dynamic Instruction Workflow

"Jarvis, here is how I want you to handle International Returns."

Flow:
1. Manager describes new process in natural language
2. Jarvis uses LLM to parse into structured steps
3. Store in client_skills table: {skill_name, steps_json, triggers, created_at}
4. PARWA Node 3 fetches custom skills when relevant ticket arrives
5. Jarvis confirms: "I've learned 'International Returns' in 4 steps."

When variants get stuck and ask Jarvis for help:
- Jarvis checks client_skills for matching guidance
- If found: provides the steps to the variant
- If not found: "I don't have instructions for this. Asking your manager."
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .jarvis_db import get_db

logger = logging.getLogger("jarvis.instructor")

# ── LLM Prompt for Step Extraction ─────────────────────────────

_STEPS_EXTRACTION_PROMPT = """Parse this process description into structured steps for an AI agent to follow.

Process description: "{description}"

Return ONLY valid JSON:
{{
  "skill_name": "short_underscore_name",
  "display_name": "Human Readable Name",
  "steps": [
    {{"order": 1, "action": "what to do", "condition": "when this applies (optional)", "response_template": "how to respond (optional)"}},
    ...
  ],
  "trigger_keywords": ["keyword1", "keyword2"],
  "priority": "high|medium|low",
  "category": "billing|returns|technical|general|sales|account"
}}"""


async def teach_skill(
    tenant_id: str,
    actor_email: str,
    raw_input: str,
) -> Dict[str, Any]:
    """Teach Jarvis a new skill/process via natural language.

    Uses LLM to parse the description into structured steps,
    stores in client_skills table, and returns confirmation.
    """
    db = get_db()

    # Extract the actual process description from the command
    description = _extract_process_description(raw_input)
    if not description or len(description) < 20:
        return {
            "success": False,
            "error": "Could not extract a process description. Please provide more detail about the process you want to teach.",
        }

    # Step 1: Use LLM to parse into structured steps
    try:
        from app.core.parwa_pipeline.llm_client import llm_call

        prompt = _STEPS_EXTRACTION_PROMPT.format(description=description)
        response = await llm_call(prompt, max_tokens=500, temperature=0.1)

        # Parse JSON from response
        text = response.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
    except Exception as e:
        logger.error("LLM step extraction failed: %s", e)
        # Fallback: create a simple single-step skill
        parsed = {
            "skill_name": _slugify(description[:50]),
            "display_name": description[:60],
            "steps": [{"order": 1, "action": description, "condition": "", "response_template": ""}],
            "trigger_keywords": description.lower().split()[:5],
            "priority": "medium",
            "category": "general",
        }

    # Step 2: Store in client_skills table
    skill_id = f"skill_{uuid.uuid4().hex[:8]}"
    skill_data = {
        "skill_id": skill_id,
        "tenant_id": tenant_id,
        "skill_name": parsed.get("skill_name", _slugify(description[:50])),
        "display_name": parsed.get("display_name", description[:60]),
        "steps_json": parsed.get("steps", []),
        "trigger_keywords": parsed.get("trigger_keywords", []),
        "priority": parsed.get("priority", "medium"),
        "category": parsed.get("category", "general"),
        "created_by": actor_email,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
    }

    await db.save_client_skill(tenant_id, skill_data)

    # Step 3: Audit log
    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="skill_taught",
        actor_email=actor_email,
        target_type="skill",
        target_id=skill_id,
        payload={
            "skill_name": skill_data["skill_name"],
            "display_name": skill_data["display_name"],
            "step_count": len(skill_data["steps_json"]),
            "category": skill_data["category"],
        },
    )

    # Step 4: Return confirmation
    step_count = len(skill_data["steps_json"])
    step_preview = "\n".join(
        f"  {s.get('order', i+1)}. {s.get('action', '...')}"
        for i, s in enumerate(skill_data["steps_json"][:5])
    )

    return {
        "success": True,
        "skill_id": skill_id,
        "skill_name": skill_data["skill_name"],
        "display_name": skill_data["display_name"],
        "step_count": step_count,
        "category": skill_data["category"],
        "trigger_keywords": skill_data["trigger_keywords"],
        "summary": (
            f"[OK] SKILL LEARNED: '{skill_data['display_name']}'\n"
            f"  Skill ID: {skill_id}\n"
            f"  Steps: {step_count}\n"
            f"  Category: {skill_data['category']}\n"
            f"  Triggers: {', '.join(skill_data['trigger_keywords'][:5])}\n"
            f"  Steps:\n{step_preview}"
        ),
    }


async def lookup_skill(tenant_id: str, query: str) -> Optional[Dict[str, Any]]:
    """Look up a skill matching a query. Used when variants ask for help."""
    db = get_db()
    skills = await db.get_client_skills(tenant_id)

    if not skills:
        return None

    # Match by trigger keywords
    query_lower = query.lower()
    best_match = None
    best_score = 0

    for skill in skills:
        triggers = skill.get("trigger_keywords", [])
        name = skill.get("display_name", "").lower()
        score = 0
        for trigger in triggers:
            if trigger.lower() in query_lower:
                score += 2
        if any(word in query_lower for word in name.split()):
            score += 1
        if score > best_score:
            best_score = score
            best_match = skill

    return best_match if best_score > 0 else None


def _extract_process_description(raw_input: str) -> str:
    """Extract the process description from a teach command."""
    # Remove command prefixes like "here's how", "teach", "learn", "handle it like"
    patterns = [
        r"(?:here'?s?\s+how|teach|learn|the\s+process\s+is|the\s+way\s+to|handle\s+it\s+like)\s+(.+)",
        r"(?:how\s+to\s+handle|how\s+to\s+process|how\s+to\s+deal\s+with|how\s+to\s+respond\s+to)\s+(.+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, raw_input, re.I)
        if m:
            return m.group(1).strip()

    # If no pattern match, use the whole input as description
    return raw_input.strip()


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    slug = re.sub(r'[^a-z0-9]+', '_', text.lower())
    return slug.strip('_')[:50] or "unnamed_skill"

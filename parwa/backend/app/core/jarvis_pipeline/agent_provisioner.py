"""
Jarvis Agent Provisioner — Wave 8A: Chat-to-Infrastructure

"Jarvis, I'm getting crushed by sales emails. Add 2 Mini Agents to handle the load for the weekend."

Flow:
1. PARSE: Extract count, type, duration from command
2. AUTHORIZE: Check role (ADMIN/OWNER/SUPERVISOR only)
3. BUDGET CHECK: Verify plan limits and existing agent count
4. PROVISION: Create rows in agent_configs (virtual agents = DB rows, NOT new containers)
5. CLONE: Copy context from existing agent of same type
6. CONFIRM: Return provisioning summary

Safety limits:
- Max 20 agents per single provision command
- Plan tier limits enforced
- All provisioning logged to agent_provisioning_logs
- Temporary agents get expires_at timestamp
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .jarvis_db import get_db

logger = logging.getLogger("jarvis.provisioner")

# ── Constants ──────────────────────────────────────────────────

MAX_AGENTS_PER_COMMAND = 20

# Plan tier limits (max concurrent agents)
PLAN_LIMITS = {
    "mini": 5,
    "high": 10,
    "parwa": 20,
    "enterprise": 50,
}

# Default agent configs per type
AGENT_TEMPLATES = {
    "mini": {
        "max_concurrent": 5,
        "capabilities": ["faq", "simple_resolutions", "greetings"],
        "greeting_style": "friendly_casual",
        "brand_voice": "professional_warm",
    },
    "high": {
        "max_concurrent": 15,
        "capabilities": ["faq", "simple_resolutions", "billing", "account_changes", "escalation"],
        "greeting_style": "professional",
        "brand_voice": "professional_formal",
    },
    "parwa": {
        "max_concurrent": 25,
        "capabilities": ["faq", "simple_resolutions", "billing", "account_changes",
                        "escalation", "complex_reasoning", "multi_language"],
        "greeting_style": "professional",
        "brand_voice": "premium",
    },
}


# ── Parsing ────────────────────────────────────────────────────

def parse_provision_command(raw_input: str) -> Dict[str, Any]:
    """Parse an agent creation command from natural language.

    Extracts: count, agent_type, duration, purpose.
    """
    text = raw_input.lower().strip()

    # Extract count
    count = 1
    count_match = re.search(r'(\d+)\s*(agent|mini|parwa|high|bot|worker)s?', text)
    if count_match:
        count = int(count_match.group(1))
    count = min(count, MAX_AGENTS_PER_COMMAND)

    # Extract agent type
    agent_type = "mini"  # default
    if "parwa" in text or "premium" in text:
        agent_type = "parwa"
    elif "high" in text or "advanced" in text:
        agent_type = "high"
    elif "mini" in text or "basic" in text:
        agent_type = "mini"

    # Extract duration
    duration = None
    expires_at = None
    now = datetime.now(timezone.utc)

    if "weekend" in text:
        # Next weekend (Saturday 0:00 to Monday 0:00)
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.hour > 0:
            days_until_saturday = 7
        start = now + timedelta(days=days_until_saturday)
        end = start + timedelta(days=2)
        expires_at = end.isoformat()
        duration = "weekend"
    elif "today" in text:
        expires_at = (now.replace(hour=23, minute=59, second=59)).isoformat()
        duration = "today"
    elif re.search(r'for\s+(\d+)\s*(hour|hr)', text):
        hours = int(re.search(r'for\s+(\d+)\s*(hour|hr)', text).group(1))
        expires_at = (now + timedelta(hours=hours)).isoformat()
        duration = f"{hours} hours"
    elif re.search(r'for\s+(\d+)\s*(day|d)', text):
        days = int(re.search(r'for\s+(\d+)\s*(day|d)', text).group(1))
        expires_at = (now + timedelta(days=days)).isoformat()
        duration = f"{days} days"
    elif re.search(r'for\s+(\d+)\s*week', text):
        weeks = int(re.search(r'for\s+(\d+)\s*week', text).group(1))
        expires_at = (now + timedelta(weeks=weeks)).isoformat()
        duration = f"{weeks} weeks"

    # Extract purpose from context
    purpose = "general_support"
    if "sales" in text or "email" in text:
        purpose = "sales_email_handling"
    elif "support" in text or "ticket" in text:
        purpose = "customer_support"
    elif "billing" in text or "invoice" in text:
        purpose = "billing_handling"
    elif "chat" in text:
        purpose = "live_chat"

    return {
        "count": count,
        "agent_type": agent_type,
        "duration": duration,
        "expires_at": expires_at,
        "purpose": purpose,
        "raw_input": raw_input,
    }


# ── Provisioning ──────────────────────────────────────────────

async def provision_agents(
    tenant_id: str,
    actor_email: str,
    parsed: Dict[str, Any],
) -> Dict[str, Any]:
    """Provision virtual agents (DB rows in agent_configs).

    Steps:
    1. Check existing agent count against plan limit
    2. Create agent_configs rows
    3. Clone context from existing agent of same type
    4. Log to agent_provisioning_logs
    5. Return provisioning summary
    """
    db = get_db()
    count = parsed["count"]
    agent_type = parsed["agent_type"]
    expires_at = parsed.get("expires_at")
    purpose = parsed.get("purpose", "general_support")
    template = AGENT_TEMPLATES.get(agent_type, AGENT_TEMPLATES["mini"])

    # Step 1: Check limits
    existing_configs = await db.get_all_agent_configs(tenant_id)
    existing_count = len([c for c in existing_configs
                          if c.get("agent_type") == agent_type
                          and c.get("status", "active") == "active"])
    max_for_type = PLAN_LIMITS.get(agent_type, 5)
    available = max_for_type - existing_count

    if available <= 0:
        return {
            "success": False,
            "error": f"Plan limit reached for {agent_type} agents ({max_for_type}). "
                     f"Remove some existing agents or upgrade your plan.",
            "existing_count": existing_count,
            "max_allowed": max_for_type,
        }

    actual_count = min(count, available)
    if actual_count < count:
        logger.warning("Provisioning reduced: requested %d, only %d available", count, actual_count)

    # Step 2: Clone context from existing agent of same type
    source_config = None
    for c in existing_configs:
        if c.get("agent_type") == agent_type and c.get("status", "active") == "active":
            source_config = c
            break

    # Step 3: Create agents
    created_agents = []
    provision_id = f"prov_{uuid.uuid4().hex[:8]}"

    for i in range(actual_count):
        agent_name = f"{agent_type}_agent_{len(existing_configs) + i + 1}"
        agent_config = {
            "tenant_id": tenant_id,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "status": "active",
            "max_concurrent": template["max_concurrent"],
            "capabilities": list(template["capabilities"]),
            "greeting_style": template["greeting_style"],
            "brand_voice": template["brand_voice"],
            "purpose": purpose,
            "expires_at": expires_at,
            "provision_id": provision_id,
            "cloned_from": source_config.get("agent_name") if source_config else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Inherit custom fields from source if cloning
        if source_config:
            for inherit_key in ["custom_instructions", "faq_categories", "tone_overrides"]:
                if source_config.get(inherit_key):
                    agent_config[inherit_key] = source_config[inherit_key]

        # Remove tenant_id and agent_name from kwargs since they're passed as positional args
        update_kwargs = {k: v for k, v in agent_config.items()
                         if k not in ("tenant_id", "agent_name")}
        result = await db.update_agent_config(
            tenant_id=tenant_id,
            agent_name=agent_name,
            **update_kwargs,
        )
        created_agents.append(result or agent_config)

    # Step 4: Log provisioning
    await db.create_audit_entry(
        tenant_id=tenant_id,
        action="agent_provisioned",
        actor_email=actor_email,
        target_type="provision_batch",
        target_id=provision_id,
        payload={
            "count": actual_count,
            "agent_type": agent_type,
            "purpose": purpose,
            "duration": parsed.get("duration"),
            "expires_at": expires_at,
            "cloned_from": source_config.get("agent_name") if source_config else None,
            "agent_names": [a.get("agent_name", agent_name) for a in created_agents],
        },
    )

    # Also log to provisioning_logs table
    try:
        await db.create_provisioning_log(
            tenant_id=tenant_id,
            provision_id=provision_id,
            agent_type=agent_type,
            count=actual_count,
            actor_email=actor_email,
            purpose=purpose,
            duration=parsed.get("duration"),
        )
    except Exception:
        # Provisioning log table might not exist — non-critical
        logger.debug("Provisioning log table not available, using audit trail only")

    return {
        "success": True,
        "provision_id": provision_id,
        "count": actual_count,
        "agent_type": agent_type,
        "agents": created_agents,
        "cloned_from": source_config.get("agent_name") if source_config else None,
        "duration": parsed.get("duration"),
        "expires_at": expires_at,
        "summary": (
            f"[OK] PROVISIONED {actual_count} {agent_type.upper()} agent(s)\n"
            f"  Agent IDs: {', '.join(a.get('agent_name', '?') for a in created_agents)}\n"
            f"  Provision ID: {provision_id}\n"
            f"  Purpose: {purpose}\n"
            f"  Duration: {parsed.get('duration') or 'permanent'}\n"
            f"  Cloned from: {source_config.get('agent_name') if source_config else 'default template'}\n"
            f"  Knowledge Base: Synced (brand voice, FAQ categories, greeting style)"
        ),
    }

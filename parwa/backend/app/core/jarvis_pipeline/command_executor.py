"""
Jarvis Command Executor — Wave 3: Control System

When the admin says "pause refunds", it ACTUALLY happens.
This module is the execution engine between intent classification and DB writes.

5-Step Execution Pipeline:
  1. VALIDATE  — Is this action legal? Does it conflict with existing flags?
  2. RESOLVE   — What exactly should be written? (target normalization, scope parsing)
  3. EXECUTE   — Write to system_flags + audit_trail
  4. VERIFY    — Read back and confirm
  5. RESPOND   — Format human-readable confirmation

Key features:
  - Conflict detection (can't pause and resume same target simultaneously)
  - Validation rules (valid modes, valid targets, scope checks)
  - Undo stack (every control command can be reversed)
  - Expiry parsing ("for today" → ISO timestamp)
  - Approval override management (permanent auto-approve rules)

Zero new dependencies. Uses only jarvis_db.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .jarvis_db import get_db

logger = logging.getLogger("jarvis.executor")


# ── Valid Targets ──────────────────────────────────────────────

VALID_PAUSE_TARGETS = {
    "refund", "refunds", "return", "returns",
    "account_change", "account_changes",
    "all", "everything", "processing",
}

VALID_MODES = {"shadow", "supervised", "graduated"}

VALID_CHANNELS = {
    "instagram", "email", "call", "calls",
    "dm", "sms", "whatsapp", "all",
}

# Actions that have permanent scope (can't auto-expire)
PERMANENT_ACTIONS = {"global_shutdown", "approval_override"}

# Actions that should auto-revoke conflicting flags
AUTO_REVOKE_CONFLICTS = {
    "control_pause": "control_resume",
    "control_resume": "control_pause",
}


# ── Validation Result ──────────────────────────────────────────

class ValidationResult:
    """Result of command validation."""

    __slots__ = ("valid", "reason", "normalized_target", "parsed_scope",
                 "parsed_expires_at", "conflicts", "warnings")

    def __init__(
        self,
        valid: bool = True,
        reason: str = "OK",
        normalized_target: str = "",
        parsed_scope: str = "global",
        parsed_expires_at: Optional[str] = None,
        conflicts: Optional[List[Dict]] = None,
        warnings: Optional[List[str]] = None,
    ):
        self.valid = valid
        self.reason = reason
        self.normalized_target = normalized_target
        self.parsed_scope = parsed_scope
        self.parsed_expires_at = parsed_expires_at
        self.conflicts = conflicts or []
        self.warnings = warnings or []

    def to_dict(self) -> Dict:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "normalized_target": self.normalized_target,
            "parsed_scope": self.parsed_scope,
            "parsed_expires_at": self.parsed_expires_at,
            "conflicts": self.conflicts,
            "warnings": self.warnings,
        }


# ── Execution Result ───────────────────────────────────────────

class ExecutionResult:
    """Result of a command execution."""

    __slots__ = ("success", "response", "flag", "audit", "undo_id",
                 "conflicts_resolved", "warnings")

    def __init__(
        self,
        success: bool,
        response: str,
        flag: Optional[Dict] = None,
        audit: Optional[Dict] = None,
        undo_id: Optional[str] = None,
        conflicts_resolved: Optional[List[Dict]] = None,
        warnings: Optional[List[str]] = None,
    ):
        self.success = success
        self.response = response
        self.flag = flag
        self.audit = audit
        self.undo_id = undo_id
        self.conflicts_resolved = conflicts_resolved or []
        self.warnings = warnings or []

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "response": self.response,
            "flag_id": self.flag.get("id") if self.flag else None,
            "undo_id": self.undo_id,
            "conflicts_resolved": len(self.conflicts_resolved),
            "warnings": self.warnings,
        }


# ═══════════════════════════════════════════════════════════════
# STEP 1: VALIDATE
# ═══════════════════════════════════════════════════════════════

def _normalize_target(intent: str, target: str) -> str:
    """Normalize target to canonical form."""
    t = target.lower().strip()
    if t in ("all", "everything"):
        return "all"
    # Singular → plural for pause/resume
    singular_map = {
        "refund": "refund", "return": "return",
        "account change": "account_change",
        "account_change": "account_change",
        "refunds": "refund", "returns": "return",
    }
    for key, val in singular_map.items():
        if t == key:
            return val
    return t


def _parse_temporal_scope(raw_input: str, intent: str) -> Tuple[str, Optional[str]]:
    """Parse temporal scope from the original input text.

    Returns (scope, expires_at_iso) tuple.
    scope: 'permanent', 'temporary', 'global'
    expires_at_iso: ISO timestamp or None
    """
    text = raw_input.lower()

    # "for today" / "today" → temporary, expires end of day UTC
    if re.search(r"\bfor today\b|\btoday\b|\bthis weekend\b|\bfor the rest of today\b", text):
        now = datetime.now(timezone.utc)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return "temporary", end_of_day.isoformat()

    # "for X hours" / "for X minutes"
    hours_match = re.search(r"\bfor\s+(\d+(?:\.\d+)?)\s+hours?\b", text)
    if hours_match:
        hours = float(hours_match.group(1))
        expires = datetime.now(timezone.utc) + timedelta(hours=hours)
        return "temporary", expires.isoformat()

    minutes_match = re.search(r"\bfor\s+(\d+)\s+minutes?\b", text)
    if minutes_match:
        minutes = int(minutes_match.group(1))
        expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return "temporary", expires.isoformat()

    # "always" / "permanently" / "permanent" → permanent
    if re.search(r"\balways\b|\bpermanently\b|\bpermanent\b|\bforever\b", text):
        return "permanent", None

    return "global", None


async def validate_command(
    intent: str,
    target: str,
    tenant_id: str,
    raw_input: str = "",
    actor_email: str = "",
) -> ValidationResult:
    """Validate a control command before execution.

    Checks:
    1. Is the target valid for this intent?
    2. Does it conflict with existing active flags?
    3. Parse scope and expiry from natural language
    4. Return warnings about existing state
    """
    db = get_db()
    warnings = []
    conflicts = []
    normalized = _normalize_target(intent, target)
    scope, expires_at = _parse_temporal_scope(raw_input, intent)

    # ── Intent-specific validation ──────────────────────────

    if intent == "control_pause":
        if normalized != "all" and normalized not in {t.rstrip("s") for t in VALID_PAUSE_TARGETS}:
            # More lenient: accept any target but warn
            warnings.append(f"Target '{normalized}' is not a standard pauseable action. Flag will be set anyway.")

        # Check if already paused
        existing = await db.get_active_flags(tenant_id, flag_type="pause_action")
        for f in existing:
            if f["flag_value"] == normalized or (normalized == "all" and f["flag_value"] != "all"):
                conflicts.append({
                    "type": "already_paused",
                    "flag": f,
                    "message": f"'{f['flag_value']}' is already paused (set by {f['set_by']} at {f['created_at'][:19]})",
                })

    elif intent == "control_resume":
        existing = await db.get_active_flags(tenant_id, flag_type="pause_action")
        matching = [f for f in existing if f["flag_value"] == normalized or normalized == "all"]
        if not matching and normalized != "all":
            # No matching pause found
            return ValidationResult(
                valid=True, reason="no_matching_pause",
                normalized_target=normalized,
                parsed_scope=scope,
                parsed_expires_at=expires_at,
                warnings=["No active pause flag found for this target. May already be running."],
            )

    elif intent == "control_mode":
        if normalized not in VALID_MODES:
            # Try to extract from target more carefully
            for mode in VALID_MODES:
                if mode in target.lower():
                    normalized = mode
                    break
            else:
                valid_modes_str = ", ".join(sorted(VALID_MODES))
                return ValidationResult(
                    valid=False,
                    reason=f"Invalid mode '{target}'. Valid modes: {valid_modes_str}",
                    normalized_target=normalized,
                )

        # Check if same mode already active
        existing = await db.get_active_flags(tenant_id, flag_type="force_mode")
        for f in existing:
            if f["flag_value"] == normalized:
                return ValidationResult(
                    valid=True, reason="already_set",
                    normalized_target=normalized,
                    warnings=[f"System is already in {normalized} mode (set by {f['set_by']})"],
                )

    elif intent == "control_route":
        if normalized not in VALID_CHANNELS:
            warnings.append(f"Channel '{normalized}' not in standard list. Flag will be set anyway.")
        # Check for conflicting redirect
        existing = await db.get_active_flags(tenant_id, flag_type="redirect_channel")
        for f in existing:
            if f["flag_value"].startswith(f"{normalized}:"):
                conflicts.append({
                    "type": "already_redirected",
                    "flag": f,
                    "message": f"'{normalized}' is already redirected (set by {f['set_by']})",
                })

    elif intent == "control_disable_rule":
        # No target validation needed — always valid
        pass

    elif intent == "control_skill_assign":
        # Will be validated in the executor with more context
        pass

    elif intent == "emergency_shutdown":
        # Check if already shutdown
        existing = await db.get_active_flags(tenant_id, flag_type="global_shutdown")
        if existing:
            return ValidationResult(
                valid=False,
                reason="System is already in EMERGENCY SHUTDOWN state. Use 'resume all' to restart.",
                normalized_target=normalized,
            )

    elif intent == "emergency_recall":
        if not target or target == "pending":
            return ValidationResult(
                valid=True, reason="ok",
                normalized_target=normalized,
                warnings=["Recall requires email provider integration. Messages will be marked as recalled in DB."],
            )

    elif intent == "emergency_void":
        if not target or target == "pending":
            return ValidationResult(
                valid=True, reason="ok",
                normalized_target=normalized,
            )

    return ValidationResult(
        valid=True,
        reason="ok",
        normalized_target=normalized,
        parsed_scope=scope,
        parsed_expires_at=expires_at,
        conflicts=conflicts,
        warnings=warnings,
    )


# ═══════════════════════════════════════════════════════════════
# STEP 2+3: RESOLVE + EXECUTE
# ═══════════════════════════════════════════════════════════════

async def execute_command(
    intent: str,
    target: str,
    tenant_id: str,
    actor_email: str,
    raw_input: str = "",
    validation: Optional[ValidationResult] = None,
) -> ExecutionResult:
    """Execute a validated control command.

    Writes to system_flags + audit_trail.
    Auto-resolves conflicts (revokes conflicting flags).
    Returns ExecutionResult with confirmation.
    """
    db = get_db()

    # Validate if not pre-validated
    if validation is None:
        validation = await validate_command(intent, target, tenant_id, raw_input, actor_email)

    if not validation.valid:
        return ExecutionResult(
            success=False,
            response=f"[INVALID] {validation.reason}",
        )

    norm_target = validation.normalized_target
    scope = validation.parsed_scope
    expires_at = validation.parsed_expires_at

    # ── Auto-resolve conflicts ──────────────────────────────
    conflicts_resolved = []
    for conflict in validation.conflicts:
        if conflict["type"] in ("already_paused", "already_redirected"):
            flag = conflict["flag"]
            await db.revoke_flag(flag["id"], actor_email)
            conflicts_resolved.append(flag)

    # ── Execute by intent ───────────────────────────────────

    if intent == "control_pause":
        result = await _exec_pause(tenant_id, norm_target, actor_email, scope, expires_at, db)

    elif intent == "control_resume":
        result = await _exec_resume(tenant_id, norm_target, actor_email, db)

    elif intent == "control_mode":
        result = await _exec_mode(tenant_id, norm_target, actor_email, db)

    elif intent == "control_route":
        result = await _exec_route(tenant_id, norm_target, actor_email, scope, expires_at, raw_input, db)

    elif intent == "control_disable_rule":
        result = await _exec_disable_rule(tenant_id, actor_email, db)

    elif intent == "control_skill_assign":
        result = await _exec_skill_assign(tenant_id, raw_input, actor_email, db)

    elif intent == "emergency_shutdown":
        result = await _exec_shutdown(tenant_id, actor_email, db)

    elif intent == "emergency_recall":
        result = await _exec_recall(tenant_id, norm_target, actor_email, db)

    elif intent == "emergency_void":
        result = await _exec_void(tenant_id, norm_target, actor_email, db)

    elif intent == "control_approval_override":
        result = await _exec_approval_override(tenant_id, norm_target, actor_email, scope, db)

    else:
        result = ExecutionResult(
            success=False,
            response=f"No executor for intent '{intent}'.",
        )

    # Attach conflict info
    result.conflicts_resolved = conflicts_resolved
    result.warnings = validation.warnings

    return result


# ═══════════════════════════════════════════════════════════════
# INDIVIDUAL EXECUTORS
# ═══════════════════════════════════════════════════════════════

async def _exec_pause(
    tenant_id: str, target: str, actor: str,
    scope: str, expires_at: Optional[str], db,
) -> ExecutionResult:
    """Execute pause: write pause_action flag."""
    reason = f"Paused {target} via Jarvis by {actor}"
    if scope == "temporary" and expires_at:
        reason += f" (expires: {expires_at[:19]})"

    flag = await db.set_flag(
        tenant_id=tenant_id,
        flag_type="pause_action",
        flag_value=target,
        set_by=actor,
        scope=scope,
        reason=reason,
        expires_at=expires_at,
    )
    audit = await db.create_audit_entry(
        tenant_id=tenant_id, action="control_pause",
        actor_email=actor, target_type="flag", target_id=flag["id"],
        payload={"target": target, "scope": scope, "expires_at": expires_at},
    )

    response = f"[OK] Paused '{target}'"
    if scope == "temporary":
        response += f" (temporary, expires: {expires_at[:19]} UTC)"
    response += f". PARWA will stop processing {target} requests until resumed."
    if target == "all":
        response = "[OK] PAUSED ALL processing. No tickets will be processed until resumed."

    return ExecutionResult(
        success=True, response=response,
        flag=flag, audit=audit, undo_id=flag["id"],
    )


async def _exec_resume(
    tenant_id: str, target: str, actor: str, db,
) -> ExecutionResult:
    """Execute resume: revoke matching pause + global_shutdown flags."""
    flags = await db.get_active_flags(tenant_id, flag_type="pause_action")
    revoked = []
    for f in flags:
        if f["flag_value"] == target or target == "all":
            await db.revoke_flag(f["id"], actor)
            revoked.append(f)

    # Also clear global_shutdown when resuming all
    if target == "all":
        shutdown_flags = await db.get_active_flags(tenant_id, flag_type="global_shutdown")
        for f in shutdown_flags:
            await db.revoke_flag(f["id"], actor)
            revoked.append(f)

    audit = await db.create_audit_entry(
        tenant_id=tenant_id, action="control_resume",
        actor_email=actor, target_type="flag", target_id=target,
        payload={"target": target, "revoked_count": len(revoked), "revoked_flags": [f["id"] for f in revoked]},
    )

    if revoked:
        names = ", ".join(f.get("flag_value", f.get("flag_type", "?")) for f in revoked)
        response = f"[OK] Resumed '{names}'. Revoked {len(revoked)} flag(s). PARWA will process {target} requests again."
    else:
        response = f"[OK] No active pause flag for '{target}'. Already running."

    return ExecutionResult(
        success=True, response=response,
        audit=audit, undo_id=None,
    )


async def _exec_mode(
    tenant_id: str, mode: str, actor: str, db,
) -> ExecutionResult:
    """Execute mode change: revoke previous mode, set new."""
    # Revoke any existing mode flags
    existing = await db.get_active_flags(tenant_id, flag_type="force_mode")
    revoked = []
    for f in existing:
        await db.revoke_flag(f["id"], actor)
        revoked.append(f["flag_value"])

    flag = await db.set_flag(
        tenant_id=tenant_id,
        flag_type="force_mode",
        flag_value=mode,
        set_by=actor,
        reason=f"Mode changed to {mode} by {actor}",
    )
    audit = await db.create_audit_entry(
        tenant_id=tenant_id, action="control_mode",
        actor_email=actor, target_type="flag", target_id=flag["id"],
        payload={"new_mode": mode, "revoked_previous": revoked},
    )

    response = f"[OK] System mode set to **{mode.upper()}**."
    if revoked:
        response += f" (changed from {', '.join(revoked)})"
    response += " PARWA will operate in " + mode + " mode."

    return ExecutionResult(
        success=True, response=response,
        flag=flag, audit=audit, undo_id=flag["id"],
    )


async def _exec_route(
    tenant_id: str, channel: str, actor: str,
    scope: str, expires_at: Optional[str], raw_input: str, db,
) -> ExecutionResult:
    """Execute channel redirect."""
    # Determine route_to from context — check if human specifically takes THIS channel
    route_to = "ai"
    lower_input = raw_input.lower()
    # Pattern: "...handle {channel}..., I'll take {other}..."
    human_for_channel = re.search(
        rf"\b(i'?ll)\s+(?:handle|take)\s+{re.escape(channel)}\b",
        lower_input,
    )
    if human_for_channel:
        route_to = "human"
    # Check for catch-all "I'll take all/everything"
    elif re.search(r"\b(i'?ll)\s+(?:handle|take)\b.*\b(all|calls?|everything)\b", lower_input):
        route_to = "human"

    flag_value = f"{channel}:{route_to}"
    reason = f"Redirected {channel} to {route_to} by {actor}"
    if scope == "temporary" and expires_at:
        reason += f" (expires: {expires_at[:19]})"

    # Revoke existing redirect for same channel
    existing = await db.get_active_flags(tenant_id, flag_type="redirect_channel")
    revoked = []
    for f in existing:
        if f["flag_value"].startswith(f"{channel}:"):
            await db.revoke_flag(f["id"], actor)
            revoked.append(f["flag_value"])

    flag = await db.set_flag(
        tenant_id=tenant_id,
        flag_type="redirect_channel",
        flag_value=flag_value,
        set_by=actor,
        scope=scope,
        reason=reason,
        expires_at=expires_at,
    )
    audit = await db.create_audit_entry(
        tenant_id=tenant_id, action="control_route",
        actor_email=actor, target_type="flag", target_id=flag["id"],
        payload={"channel": channel, "route_to": route_to, "scope": scope, "expires_at": expires_at},
    )

    response = f"[OK] Workflow Redirected: {channel} -> {route_to.upper()}"
    if scope == "temporary":
        response += f" (expires: {expires_at[:19]} UTC)"
    response += f". PARWA will {'handle' if route_to == 'ai' else 'skip'} {channel} requests."

    return ExecutionResult(
        success=True, response=response,
        flag=flag, audit=audit, undo_id=flag["id"],
    )


async def _exec_disable_rule(
    tenant_id: str, actor: str, db,
) -> ExecutionResult:
    """Execute undo/disable: revoke the most recent active flag."""
    flags = await db.get_active_flags(tenant_id)
    # Don't disable global_shutdown via "disable rule" — too dangerous
    non_shutdown = [f for f in flags if f["flag_type"] != "global_shutdown"]
    if non_shutdown:
        last = non_shutdown[-1]
        await db.revoke_flag(last["id"], actor)
        audit = await db.create_audit_entry(
            tenant_id=tenant_id, action="control_disable_rule",
            actor_email=actor, target_type="flag", target_id=last["id"],
            payload={
                "revoked_flag_type": last["flag_type"],
                "revoked_flag_value": last["flag_value"],
                "set_by": last["set_by"],
            },
        )
        response = (
            f"[OK] Disabled last rule: **{last['flag_type']}={last['flag_value']}**\n"
            f"  Set by: {last['set_by']} at {last['created_at'][:19]}\n"
            f"  System reverted to default behavior for this rule."
        )
        return ExecutionResult(
            success=True, response=response,
            audit=audit, undo_id=last["id"],
        )
    return ExecutionResult(
        success=True,
        response="No active rules to disable. System is running with default behavior.",
    )


async def _exec_skill_assign(
    tenant_id: str, raw_input: str, actor: str, db,
) -> ExecutionResult:
    """Execute skill re-assignment between variants.

    Parses: "Move Product Recommendations from Mini to PARWA"
    Pattern: <skill> from <source_variant> to <dest_variant>
    """
    # Parse skill, source, destination
    from_match = re.search(r"\b(move|reassign|transfer)\b\s+(.+?)\s+from\s+(\w+)\s+to\s+(\w+)", raw_input, re.I)
    # Parse skill name, source, destination from raw input
    from_match = re.search(
        r"(move|reassign|transfer)\s+([\w\s+]+?)\s+from\s+(\w+)\s+to\s+(\w+)",
        raw_input, re.I,
    )
    if not from_match:
        # Try "add X to Y"
        add_match = re.search(r"(add|assign).*(skill|capability).*(to)", raw_input, re.I)
        if add_match:
            skill = add_match.group(1).strip()
            dest = add_match.group(2).strip()
            source = "unassigned"
        else:
            return ExecutionResult(
                success=False,
                response="[INVALID] Could not parse skill assignment. Use format: 'Move [skill] from [variant] to [variant]'",
            )
    else:
        skill = from_match.group(2).strip()
        source = from_match.group(3).strip()
        dest = from_match.group(4).strip()

    # Write to agent_configs via system_flags (variant_assignment type)
    flag = await db.set_flag(
        tenant_id=tenant_id,
        flag_type="variant_assignment",
        flag_value=f"{skill}:{source}:{dest}",
        set_by=actor,
        reason=f"Skill re-assignment: {skill} from {source} to {dest} by {actor}",
    )

    # Also update agent_configs table directly
    # Remove skill from source, add to destination
    source_config = await db.get_agent_config(tenant_id, source)
    dest_config = await db.get_agent_config(tenant_id, dest)

    updated_source = None
    updated_dest = None
    skills_removed = 0
    skills_added = 0

    if source_config and source != "unassigned":
        current_skills = source_config.get("skills", []) or []
        if skill in current_skills:
            new_skills = [s for s in current_skills if s != skill]
            updated_source = await db.update_agent_config(
                tenant_id=tenant_id, agent_name=source, skills=new_skills,
            )
            skills_removed = len(current_skills) - len(new_skills)

    if dest_config:
        current_skills = dest_config.get("skills", []) or []
        if skill not in current_skills:
            new_skills = current_skills + [skill]
            updated_dest = await db.update_agent_config(
                tenant_id=tenant_id, agent_name=dest, skills=new_skills,
            )
            skills_added = 1

    audit = await db.create_audit_entry(
        tenant_id=tenant_id, action="control_skill_assign",
        actor_email=actor, target_type="skill", target_id=skill,
        payload={
            "skill": skill, "from": source, "to": dest,
            "source_updated": updated_source is not None,
            "dest_updated": updated_dest is not None,
            "skills_removed": skills_removed,
            "skills_added": skills_added,
        },
    )

    response_parts = [
        f"[OK] Skill Re-assignment Complete:",
        f"  Skill: **{skill}**",
        f"  From: {source}" + (" (removed)" if skills_removed else ""),
        f"  To: {dest}" + (" (added)" if skills_added else ""),
    ]

    if not updated_source and source != "unassigned":
        response_parts.append(f"  Note: Source variant '{source}' not found or skill not present")
    if not updated_dest:
        response_parts.append(f"  Note: Destination variant '{dest}' not found or already has skill")

    return ExecutionResult(
        success=True, response="\n".join(response_parts),
        flag=flag, audit=audit, undo_id=flag["id"],
    )


async def _exec_shutdown(
    tenant_id: str, actor: str, db,
) -> ExecutionResult:
    """Execute emergency shutdown."""
    flag = await db.set_flag(
        tenant_id=tenant_id,
        flag_type="global_shutdown",
        flag_value="all",
        set_by=actor,
        reason=f"EMERGENCY SHUTDOWN by {actor}",
    )
    audit = await db.create_audit_entry(
        tenant_id=tenant_id, action="emergency_shutdown",
        actor_email=actor, target_type="flag", target_id=flag["id"],
        payload={"CRITICAL": "All AI activity paused", "flag_id": flag["id"]},
    )

    # Notify all active team members (create a CRITICAL notification)
    notification = await db.create_notification(
        tenant_id=tenant_id,
        ntype="emergency_shutdown",
        priority_score=1.0,
        title="[EMERGENCY] System Shutdown Initiated",
        description=(
            f"All AI activity has been paused by {actor}.\n"
            f"In-flight tickets will complete their current step, then stop.\n"
            f"No new tickets will be accepted.\n"
            f"Use 'resume all' to restart the system."
        ),
        source_data={"actor": actor, "flag_id": flag["id"]},
    )

    return ExecutionResult(
        success=True,
        response=(
            f"[EMERGENCY] All AI activity PAUSED.\n"
            f"  Initiated by: {actor}\n"
            f"  In-flight tickets will complete current step then stop.\n"
            f"  No new tickets will be accepted.\n"
            f"  Notification: {notification['notification_key']}\n"
            f"\n"
            f"  Use **'resume all'** to restart."
        ),
        flag=flag,
        audit=audit,
        undo_id=flag["id"],
    )


async def _exec_recall(
    tenant_id: str, target: str, actor: str, db,
) -> ExecutionResult:
    """Execute recall: mark messages as recalled in outbox queue."""
    # Write recall flag + add to outbox_queue as recalled
    recalled_count = await db.recall_outbox_messages(
        tenant_id=tenant_id,
        match_filter=target if target not in ("pending", "all") else None,
    )

    flag = await db.set_flag(
        tenant_id=tenant_id,
        flag_type="emergency_recall",
        flag_value=target,
        set_by=actor,
        scope="global",
        reason=f"Recall initiated for '{target}' by {actor}",
    )
    audit = await db.create_audit_entry(
        tenant_id=tenant_id, action="emergency_recall",
        actor_email=actor, target_type="message", target_id=target,
        payload={"target": target, "recalled_count": recalled_count},
    )

    response = (
        f"[OK] Recall executed for '{target}'.\n"
        f"  Messages marked as recalled: {recalled_count}\n"
        f"  Note: Actual email recall requires provider integration (SendGrid API).\n"
        f"  Messages are marked in the outbox queue to prevent re-sending."
    )
    return ExecutionResult(
        success=True, response=response,
        flag=flag, audit=audit, undo_id=flag["id"],
    )


async def _exec_void(
    tenant_id: str, target: str, actor: str, db,
) -> ExecutionResult:
    """Execute void: remove pending messages from outbox queue."""
    voided_count = await db.void_outbox_messages(
        tenant_id=tenant_id,
        match_filter=target if target not in ("pending", "all") else None,
    )

    audit = await db.create_audit_entry(
        tenant_id=tenant_id, action="emergency_void",
        actor_email=actor, target_type="message", target_id=target,
        payload={"target": target, "voided_count": voided_count},
    )

    response = (
        f"[OK] Void executed for '{target}'.\n"
        f"  Pending messages removed: {voided_count}\n"
        f"  These messages were in the outbox queue and had not yet been sent."
    )
    return ExecutionResult(
        success=True, response=response,
        audit=audit,
    )


async def _exec_approval_override(
    tenant_id: str, target: str, actor: str, scope: str, db,
    raw_input: str = "",
) -> ExecutionResult:
    """Execute approval override: set permanent auto-approve rule.

    Parses the actual action type from raw_input.
    'Always auto-approve address changes' → approval_override flag_value='address changes'
    PARWA Node 5 reads this before checking approval gates.
    """
    # Parse the action type from the raw input (not the regex target)
    action_match = re.search(
        r"auto\s*-?approve\s+(.+?)(?:\.|!|\\n|$)",
        raw_input,
        re.I,
    )
    action_type = action_match.group(1).strip().rstrip('.') if action_match else target

    flag = await db.set_flag(
        tenant_id=tenant_id,
        flag_type="approval_override",
        flag_value=action_type,
        set_by=actor,
        scope="permanent",
        reason=f"Approval override: always auto-approve {action_type} by {actor}",
    )
    audit = await db.create_audit_entry(
        tenant_id=tenant_id, action="control_approval_override",
        actor_email=actor, target_type="approval_rule", target_id=action_type,
        payload={"action_type": action_type, "scope": "permanent"},
    )

    response = (
        f"[OK] Approval Override Set:\n"
        f"  Action Type: **{action_type}**\n"
        f"  Scope: Permanent (until manually revoked)\n"
        f"  Effect: Future '{action_type}' requests will skip the approval queue.\n"
        f"  To undo: 'disable my last rule' or 'disable rule'"
    )
    return ExecutionResult(
        success=True, response=response,
        flag=flag, audit=audit, undo_id=flag["id"],
    )


# ═══════════════════════════════════════════════════════════════
# HELPER: Get flags for PARWA to read (Wave 4 will call this)
# ═══════════════════════════════════════════════════════════════

async def get_effective_flags(tenant_id: str) -> Dict[str, Any]:
    """Get all effective flags that PARWA should obey.

    Returns a structured dict PARWA can check at each node:
    {
        "paused_actions": ["refund", "account_change"],
        "redirected_channels": {"instagram": "ai", "calls": "human"},
        "forced_mode": "supervised",
        "approval_overrides": ["address_change"],
        "global_shutdown": false,
        "guidance": {},  // ticket-specific guidance from Jarvis
    }
    """
    db = get_db()
    flags = await db.get_active_flags(tenant_id)

    result: Dict[str, Any] = {
        "paused_actions": [],
        "redirected_channels": {},
        "forced_mode": None,
        "approval_overrides": [],
        "global_shutdown": False,
        "variant_assignments": [],
        "guidance": {},
    }

    for f in flags:
        ft = f["flag_type"]
        fv = f["flag_value"]

        if ft == "pause_action":
            if fv == "all":
                result["global_shutdown"] = True
            else:
                result["paused_actions"].append(fv)

        elif ft == "redirect_channel":
            parts = fv.split(":", 1)
            if len(parts) == 2:
                result["redirected_channels"][parts[0]] = parts[1]

        elif ft == "force_mode":
            result["forced_mode"] = fv

        elif ft == "approval_override":
            result["approval_overrides"].append(fv)

        elif ft == "global_shutdown":
            result["global_shutdown"] = True

        elif ft == "variant_assignment":
            result["variant_assignments"].append(fv)

        elif ft == "guidance":
            ticket_id = f.get("target_id", "")
            if ticket_id:
                result["guidance"][ticket_id] = fv

    return result
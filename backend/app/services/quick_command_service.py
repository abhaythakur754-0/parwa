"""
PARWA Quick Command Service (F-090) — Pre-parsed Command Shortcuts

Provides clickable command shortcuts for the Jarvis Command Center.
Operators can invoke common operations with one click instead of typing.

Features:
- 15 structured quick commands across 5 categories
- Per-tenant customization (enable/disable, custom labels/params)
- Risk-level classification (some commands require admin)
- Each command maps to a jarvis_command_parser command type
- Confirmation gating for destructive operations

Methods:
- get_quick_commands() — List available commands for a tenant
- execute_quick_command() — Execute a quick command by ID
- get_custom_commands() — Get tenant-specific command configs
- update_custom_commands() — Create/update tenant command config

Building Codes: BC-001 (multi-tenant), BC-011 (auth), BC-012 (error handling)
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("quick_command_service")


# ══════════════════════════════════════════════════════════════════
# QUICK COMMAND DEFINITIONS
# ══════════════════════════════════════════════════════════════════

QUICK_COMMANDS: List[Dict[str, Any]] = [
    # ── System Operations ────────────────────────────────────
    {
        "id": "qc-show-status",
        "label": "Show System Status",
        "icon": "activity",
        "category": "system_ops",
        "command_text": "show status",
        "confirmation_required": False,
        "risk_level": "low",
        "requires_admin": False,
        "description": "Display overall system health across all subsystems",
    },
    {
        "id": "qc-health-check",
        "label": "Health Check",
        "icon": "heart-pulse",
        "category": "system_ops",
        "command_text": "health check",
        "confirmation_required": False,
        "risk_level": "low",
        "requires_admin": False,
        "description": "Run a deep health check on all subsystems",
    },
    {
        "id": "qc-restart-celery",
        "label": "Restart Celery",
        "icon": "refresh-cw",
        "category": "system_ops",
        "command_text": "restart celery",
        "confirmation_required": True,
        "risk_level": "high",
        "requires_admin": True,
        "description": "Restart the Celery worker process",
    },
    # ── Agent Management ────────────────────────────────────
    {
        "id": "qc-list-agents",
        "label": "List Agents",
        "icon": "users",
        "category": "agent_mgmt",
        "command_text": "list agents",
        "confirmation_required": False,
        "risk_level": "low",
        "requires_admin": False,
        "description": "Show all AI agents and their current status",
    },
    {
        "id": "qc-restart-agent",
        "label": "Restart Agent",
        "icon": "user-x",
        "category": "agent_mgmt",
        "command_text": "restart agent",
        "confirmation_required": True,
        "risk_level": "high",
        "requires_admin": True,
        "description": "Restart a specific AI agent (requires agent ID)",
    },
    # ── Ticket Operations ───────────────────────────────────
    {
        "id": "qc-list-tickets",
        "label": "List Tickets",
        "icon": "list",
        "category": "ticket_ops",
        "command_text": "list tickets",
        "confirmation_required": False,
        "risk_level": "low",
        "requires_admin": False,
        "description": "List tickets with optional filters",
    },
    {
        "id": "qc-escalate-ticket",
        "label": "Escalate Ticket",
        "icon": "arrow-up-circle",
        "category": "ticket_ops",
        "command_text": "escalate ticket",
        "confirmation_required": True,
        "risk_level": "medium",
        "requires_admin": False,
        "description": "Escalate a ticket to a human agent",
    },
    {
        "id": "qc-close-ticket",
        "label": "Close Ticket",
        "icon": "check-circle",
        "category": "ticket_ops",
        "command_text": "close ticket",
        "confirmation_required": True,
        "risk_level": "medium",
        "requires_admin": False,
        "description": "Close a ticket (requires ticket ID)",
    },
    # ── Analytics ───────────────────────────────────────────
    {
        "id": "qc-show-analytics",
        "label": "Show Analytics",
        "icon": "bar-chart-2",
        "category": "analytics",
        "command_text": "show analytics",
        "confirmation_required": False,
        "risk_level": "low",
        "requires_admin": False,
        "description": "Show analytics dashboard summary",
    },
    {
        "id": "qc-response-time",
        "label": "Response Time",
        "icon": "clock",
        "category": "analytics",
        "command_text": "show response_time",
        "confirmation_required": False,
        "risk_level": "low",
        "requires_admin": False,
        "description": "Show average response time metrics",
    },
    {
        "id": "qc-csat-score",
        "label": "CSAT Score",
        "icon": "star",
        "category": "analytics",
        "command_text": "show csat",
        "confirmation_required": False,
        "risk_level": "low",
        "requires_admin": False,
        "description": "Show customer satisfaction score",
    },
    # ── Emergency ───────────────────────────────────────────
    {
        "id": "qc-list-incidents",
        "label": "List Incidents",
        "icon": "alert-triangle",
        "category": "emergency",
        "command_text": "list incidents",
        "confirmation_required": False,
        "risk_level": "low",
        "requires_admin": False,
        "description": "Show all active system incidents",
    },
    {
        "id": "qc-train-from-errors",
        "label": "Train from Errors",
        "icon": "brain",
        "category": "emergency",
        "command_text": "train from errors",
        "confirmation_required": True,
        "risk_level": "medium",
        "requires_admin": True,
        "description": "Trigger model training from recent error data",
    },
    {
        "id": "qc-show-usage",
        "label": "Show Usage",
        "icon": "gauge",
        "category": "emergency",
        "command_text": "show usage",
        "confirmation_required": False,
        "risk_level": "low",
        "requires_admin": False,
        "description": "Show current usage and cost summary",
    },
    {
        "id": "qc-purge-queue",
        "label": "Purge Queue",
        "icon": "trash-2",
        "category": "emergency",
        "command_text": "purge queue",
        "confirmation_required": True,
        "risk_level": "critical",
        "requires_admin": True,
        "description": "Purge all messages from a queue",
    },
    {
        "id": "qc-deploy",
        "label": "Deploy",
        "icon": "rocket",
        "category": "emergency",
        "command_text": "deploy",
        "confirmation_required": True,
        "risk_level": "critical",
        "requires_admin": True,
        "description": "Deploy a new version to production",
    },
]

# Index by ID for fast lookup
_COMMAND_INDEX: Dict[str, Dict[str, Any]] = {
    cmd["id"]: cmd for cmd in QUICK_COMMANDS
}


# ══════════════════════════════════════════════════════════════════
# SERVICE FUNCTIONS
# ══════════════════════════════════════════════════════════════════


def get_quick_commands(
    company_id: str,
    db,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Get quick commands available for a tenant.

    Merges global command definitions with per-tenant customizations
    (enabled/disabled, custom labels, custom params).

    Args:
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.
        category: Optional category filter.

    Returns:
        Dictionary with commands list, grouped by category.
    """
    try:
        from app.models.system_health import QuickCommandConfig

        # Fetch tenant customizations in a single query
        configs = db.query(QuickCommandConfig).filter(
            QuickCommandConfig.company_id == company_id,
        ).all()

        config_map: Dict[str, Dict[str, Any]] = {}
        for cfg in configs:
            config_map[cfg.command_id] = {
                "enabled": cfg.enabled,
                "custom_label": cfg.custom_label,
                "custom_params": (
                    json.loads(cfg.custom_params_json)
                    if cfg.custom_params_json else None
                ),
            }

        # Merge global commands with tenant configs
        result_commands = []
        for cmd in QUICK_COMMANDS:
            tenant_cfg = config_map.get(cmd["id"], {})

            # Skip disabled commands
            if tenant_cfg.get("enabled") is False:
                continue

            # Apply category filter
            if category and cmd["category"] != category:
                continue

            merged = {
                **cmd,
                "tenant_enabled": tenant_cfg.get("enabled", True),
                "custom_label": tenant_cfg.get("custom_label"),
                "custom_params": tenant_cfg.get("custom_params"),
            }

            # Override display label if tenant has a custom one
            if tenant_cfg.get("custom_label"):
                merged["display_label"] = tenant_cfg["custom_label"]
            else:
                merged["display_label"] = cmd["label"]

            result_commands.append(merged)

        # Group by category
        categories: Dict[str, List[Dict[str, Any]]] = {}
        for cmd in result_commands:
            cat = cmd["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(cmd)

        return {
            "commands": result_commands,
            "total": len(result_commands),
            "categories": categories,
        }

    except Exception as exc:
        logger.error(
            "quick_command_list_error",
            company_id=company_id,
            error=str(exc),
        )
        return {
            "commands": [],
            "total": 0,
            "categories": {},
            "error": str(exc)[:200],
        }


def execute_quick_command(
    command_id: str,
    company_id: str,
    db,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a quick command by ID.

    Looks up the command definition, merges any custom params,
    and delegates to the jarvis_command_parser for execution.

    Args:
        command_id: The quick command identifier (e.g., 'qc-show-status').
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.
        params: Optional override parameters.

    Returns:
        Dictionary with execution result.
    """
    cmd_def = _COMMAND_INDEX.get(command_id)
    if not cmd_def:
        return {
            "error": f"Quick command '{command_id}' not found",
            "command_id": command_id,
        }

    # Build the command text (append params if provided)
    command_text = cmd_def["command_text"]
    if params:
        # Append param values to command text
        param_str = " ".join(
            str(v) for v in params.values() if v is not None
        )
        if param_str:
            command_text = f"{command_text} {param_str}"

    # Delegate to jarvis_command_parser
    try:
        from app.core.jarvis_command_parser import get_command_parser

        parser = get_command_parser()
        parsed = parser.parse(command_text)

        return {
            "command_id": command_id,
            "command_text": command_text,
            "parsed": parsed.to_dict(),
            "executed": False,
            "requires_confirmation": cmd_def["confirmation_required"],
            "risk_level": cmd_def["risk_level"],
        }

    except Exception as exc:
        logger.error(
            "quick_command_execute_error",
            company_id=company_id,
            command_id=command_id,
            error=str(exc),
        )
        return {
            "command_id": command_id,
            "error": str(exc)[:200],
            "executed": False,
        }


def get_custom_commands(
    company_id: str,
    db,
) -> List[Dict[str, Any]]:
    """Get all custom command configurations for a tenant.

    Args:
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.

    Returns:
        List of command config dictionaries.
    """
    try:
        from app.models.system_health import QuickCommandConfig

        configs = db.query(QuickCommandConfig).filter(
            QuickCommandConfig.company_id == company_id,
        ).order_by(QuickCommandConfig.created_at.desc()).all()

        return [
            {
                "id": str(cfg.id),
                "company_id": cfg.company_id,
                "command_id": cfg.command_id,
                "enabled": cfg.enabled,
                "custom_label": cfg.custom_label,
                "custom_params": (
                    json.loads(cfg.custom_params_json)
                    if cfg.custom_params_json else None
                ),
                "created_at": (
                    cfg.created_at.isoformat() if cfg.created_at else None
                ),
            }
            for cfg in configs
        ]

    except Exception as exc:
        logger.error(
            "quick_command_custom_list_error",
            company_id=company_id,
            error=str(exc),
        )
        return []


def update_custom_commands(
    company_id: str,
    db,
    command_id: str,
    enabled: Optional[bool] = None,
    custom_label: Optional[str] = None,
    custom_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create or update a custom command configuration for a tenant.

    If a config exists for this company_id + command_id, it is updated.
    Otherwise, a new config is created.

    Args:
        company_id: Tenant identifier (BC-001).
        db: SQLAlchemy session.
        command_id: The quick command identifier to customize.
        enabled: Whether this command is enabled for the tenant.
        custom_label: Optional display label override.
        custom_params: Optional parameter overrides as JSON.

    Returns:
        The created or updated config dictionary.
    """
    # Validate command_id exists in global definitions
    if command_id not in _COMMAND_INDEX:
        return {
            "error": f"Unknown command_id '{command_id}'",
            "command_id": command_id,
        }

    try:
        from app.models.system_health import QuickCommandConfig

        # Try to find existing config
        config = db.query(QuickCommandConfig).filter(
            QuickCommandConfig.company_id == company_id,
            QuickCommandConfig.command_id == command_id,
        ).first()

        if config:
            # Update existing
            if enabled is not None:
                config.enabled = enabled
            if custom_label is not None:
                config.custom_label = custom_label
            if custom_params is not None:
                config.custom_params_json = json.dumps(custom_params)
            db.flush()
        else:
            # Create new
            config = QuickCommandConfig(
                company_id=company_id,
                command_id=command_id,
                enabled=enabled if enabled is not None else True,
                custom_label=custom_label,
                custom_params_json=(
                    json.dumps(custom_params) if custom_params else None
                ),
            )
            db.add(config)
            db.flush()

        logger.info(
            "quick_command_config_updated",
            company_id=company_id,
            command_id=command_id,
            action="updated" if config else "created",
        )

        return {
            "id": str(config.id),
            "company_id": config.company_id,
            "command_id": config.command_id,
            "enabled": config.enabled,
            "custom_label": config.custom_label,
            "custom_params": (
                json.loads(config.custom_params_json)
                if config.custom_params_json else None
            ),
            "created_at": (
                config.created_at.isoformat() if config.created_at else None
            ),
        }

    except Exception as exc:
        logger.error(
            "quick_command_config_update_error",
            company_id=company_id,
            command_id=command_id,
            error=str(exc),
        )
        return {
            "error": str(exc)[:200],
            "command_id": command_id,
        }


__all__ = [
    "QUICK_COMMANDS",
    "get_quick_commands",
    "execute_quick_command",
    "get_custom_commands",
    "update_custom_commands",
]

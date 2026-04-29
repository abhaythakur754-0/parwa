"""
PARWA Jarvis Command Parser (F-087) — Natural Language Command Parsing

Translates operator natural language commands into structured actions
for the Jarvis Command Center.

Supports 20+ command types across categories:
- System Operations: status, health, ping, uptime, config
- Agent Management: restart, list, assign
- Ticket Operations: list, get, assign, close, reopen, escalate
- Analytics: queries, summaries, reports
- Integration: list, check, enable, disable
- Queue Management: list, purge
- Incident Management: list, resolve
- Training: train, retrain, evaluate
- Deployment: restart service, deploy, rollback

Design:
- Keyword/pattern matching for speed (no LLM for common commands)
- LLM fallback reserved for ambiguous commands
- Alias support (e.g., "status" = "show status" = "system status")
- Confidence scoring (1.0 for exact matches, lower for fuzzy)
- Confirmation required for destructive commands

Building Codes: BC-011 (auth), BC-012 (error handling)
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("jarvis_command_parser")


# ══════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════


@dataclass
class ParsedCommand:
    """Structured result of parsing a natural language command.

    Attributes:
        command_type: Resolved command type identifier.
        original_command: Original raw input text.
        params: Extracted parameters (name, value, confidence).
        confidence: Overall confidence in the parse (0.0-1.0).
        requires_confirmation: Whether execution needs operator OK.
        execution_summary: Human-readable description of the action.
        aliases_matched: Any aliases that contributed to this match.
    """

    command_type: str
    original_command: str
    params: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    requires_confirmation: bool = False
    execution_summary: str = ""
    aliases_matched: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "command_type": self.command_type,
            "original_command": self.original_command,
            "params": self.params,
            "confidence": self.confidence,
            "requires_confirmation": self.requires_confirmation,
            "execution_summary": self.execution_summary,
            "aliases_matched": self.aliases_matched,
        }


@dataclass
class CommandDefinition:
    """Definition of a single Jarvis command.

    Attributes:
        command_type: Unique command identifier.
        description: Human-readable description.
        category: Command category for grouping.
        patterns: Regex patterns that match this command.
        aliases: Alternative natural language phrases.
        params: Expected parameter names and extraction regexes.
        requires_confirmation: Whether this command needs confirmation.
        is_destructive: Whether this command modifies state irreversibly.
        examples: Example invocations for help text.
    """

    command_type: str
    description: str
    category: str
    patterns: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    params: Dict[str, str] = field(default_factory=dict)
    requires_confirmation: bool = False
    is_destructive: bool = False
    examples: List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# COMMAND REGISTRY
# ══════════════════════════════════════════════════════════════════

COMMAND_REGISTRY: Dict[str, CommandDefinition] = {}

# Ticket ID pattern (TKT-xxx, ticket-xxx, UUID-like)
_TICKET_ID_PATTERN = r"(?P<ticket_id>TKT[-\w]+|ticket[-\w]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
# Agent ID pattern (agent name or ID)
_AGENT_ID_PATTERN = r"(?P<agent_id>\S+)"
# Incident ID pattern
_INCIDENT_ID_PATTERN = r"(?P<incident_id>INC[-\w]+|incident[-\w]+|[0-9a-f]{8}-[0-9a-f]{4})"
# Integration name pattern
_INTEGRATION_PATTERN = r"(?P<name>[\w\s-]+?)(?=\s+(?:enable|disable|check|status)|$)"
# Config key pattern
_CONFIG_KEY_PATTERN = r"(?P<key>[\w.]+)"
# Duration pattern (for history queries)
_DURATION_PATTERN = r"(?P<duration>\d+\s*(?:second|sec|minute|min|hour|hr|day)s?)"


def _register_command(cmd: CommandDefinition) -> None:
    """Register a command definition in the global registry."""
    COMMAND_REGISTRY[cmd.command_type] = cmd


# ── System Operations ────────────────────────────────────────────

_register_command(CommandDefinition(
    command_type="show_status",
    description="Show overall system health status",
    category="system",
    patterns=[
        r"^(?:show\s+)?(?:system\s+)?status$",
        r"^how\s+(?:is\s+)?(?:the\s+)?system(?:\s+doing)?\??$",
        r"^health\s+(?:check|status)?$",
    ],
    aliases=["status", "system status", "health", "health check", "ping"],
    examples=["show status", "system status", "health check"],
))

_register_command(CommandDefinition(
    command_type="list_errors",
    description="List recent system errors and exceptions",
    category="system",
    patterns=[
        r"^(?:show|list|get)\s+(?:recent\s+)?(?:system\s+)?errors?$",
        r"^what\s+(?:are\s+)?(?:the\s+)?(?:recent\s+)?errors\??$",
        r"^(?:show|list)\s+exceptions?$",
    ],
    aliases=["errors", "show errors", "list errors", "exceptions"],
    params={"limit": r"(?:last|past|recent)\s+(?P<limit>\d+)"},
    examples=["list errors", "show recent errors", "list exceptions"],
))

_register_command(CommandDefinition(
    command_type="uptime",
    description="Show system uptime",
    category="system",
    patterns=[
        r"^uptime$",
        r"^(?:show|get)\s+uptime$",
        r"^how\s+long\s+(?:has\s+)?(?:the\s+)?system\s+been\s+(?:up|running)\??$",
    ],
    aliases=["show uptime", "get uptime"],
    examples=["uptime", "show uptime"],
))

_register_command(CommandDefinition(
    command_type="show_config",
    description="Show system configuration",
    category="system",
    patterns=[
        r"^(?:show|get|display)\s+(?:system\s+)?config(?:uration)?$",
        r"^config(?:uration)?\s+(?:show|get|display)?$",
    ],
    aliases=["config", "configuration", "show config"],
    params={"key": _CONFIG_KEY_PATTERN},
    examples=["show config", "config", "show config ai.model"],
))

_register_command(CommandDefinition(
    command_type="set_config",
    description="Update a system configuration value",
    category="system",
    patterns=[
        r"^set\s+config(?:uration)?\s+(?P<key>[\w.]+)\s+(?P<value>.+)$",
        r"^(?:update|change)\s+(?P<key>[\w.]+)\s+(?:to|=>|=)\s*(?P<value>.+)$",
    ],
    aliases=["update config", "change config"],
    requires_confirmation=True,
    is_destructive=True,
    examples=["set config ai.temperature 0.7", "update max_retries to 5"],
))

_register_command(CommandDefinition(
    command_type="show_logs",
    description="Show recent system logs",
    category="system",
    patterns=[
        r"^(?:show|get|view|tail)\s+(?:recent\s+)?logs?$",
        r"^(?:show|get)\s+(?:the\s+)?(?:system\s+)?(?:activity\s+)?logs?$",
    ],
    aliases=["logs", "show logs", "get logs", "tail logs"],
    params={
        "limit": r"(?:last|past|recent)\s+(?P<limit>\d+)",
        "level": r"(?P<level>error|warn|warning|info|debug)",
    },
    examples=["show logs", "show last 50 logs", "show error logs"],
))

_register_command(CommandDefinition(
    command_type="export_logs",
    description="Export system logs",
    category="system",
    patterns=[
        r"^export\s+logs?$",
        r"^download\s+(?:system\s+)?logs?$",
    ],
    aliases=["download logs"],
    params={"format": r"(?P<format>json|csv|txt)"},
    examples=["export logs", "export logs json"],
))

# ── Agent Management ────────────────────────────────────────────

_register_command(CommandDefinition(
    command_type="list_agents",
    description="List all AI agents and their status",
    category="agents",
    patterns=[
        r"^(?:show|list|get)\s+(?:all\s+)?agents?$",
        r"^agents?(?:\s+list)?$",
    ],
    aliases=["agents", "show agents", "list agents"],
    examples=["list agents", "show agents"],
))

_register_command(CommandDefinition(
    command_type="restart_agent",
    description="Restart a specific AI agent",
    category="agents",
    patterns=[
        r"^restart\s+agent\s+" + _AGENT_ID_PATTERN + r"$",
        r"^(?:restart|reload)\s+" + _AGENT_ID_PATTERN + r"$",
    ],
    aliases=["restart agent", "reload agent"],
    requires_confirmation=True,
    is_destructive=True,
    params={"agent_id": _AGENT_ID_PATTERN},
    examples=["restart agent jarvis-primary", "restart agent X"],
))

_register_command(
    CommandDefinition(
        command_type="assign_agent",
        description="Assign an agent to handle a ticket",
        category="agents",
        patterns=[
            r"^assign\s+(?:agent\s+)?" +
            _AGENT_ID_PATTERN +
            r"\s+to\s+(?:ticket\s+)?" +
            _TICKET_ID_PATTERN +
            r"$",
        ],
        aliases=["assign agent"],
        requires_confirmation=False,
        params={
            "agent_id": _AGENT_ID_PATTERN,
            "ticket_id": _TICKET_ID_PATTERN,
        },
        examples=["assign agent jarvis-primary to ticket TKT-123"],
    ))

# ── Ticket Operations ────────────────────────────────────────────

_register_command(CommandDefinition(
    command_type="list_tickets",
    description="List tickets with optional filters",
    category="tickets",
    patterns=[
        r"^(?:show|list|get)\s+(?:all\s+)?tickets?$",
        r"^tickets?(?:\s+list)?$",
    ],
    aliases=["tickets", "show tickets", "list tickets"],
    params={
        "status": r"(?P<status>open|closed|pending|escalated|all)",
        "limit": r"(?:last|past|recent)\s+(?P<limit>\d+)",
    },
    examples=["list tickets", "list open tickets", "show last 20 tickets"],
))

_register_command(
    CommandDefinition(
        command_type="get_ticket",
        description="Get details of a specific ticket",
        category="tickets",
        patterns=[
            r"^(?:show|get|view|details?\s+(?:of\s+)?)ticket\s+" +
            _TICKET_ID_PATTERN +
            r"$",
            r"^ticket\s+" +
            _TICKET_ID_PATTERN +
            r"$",
        ],
        aliases=[
            "ticket details",
            "show ticket"],
        params={
            "ticket_id": _TICKET_ID_PATTERN},
        examples=[
            "get ticket TKT-123",
            "show ticket TKT-456"],
    ))

_register_command(
    CommandDefinition(
        command_type="escalate_ticket",
        description="Escalate a ticket to a human agent",
        category="tickets",
        patterns=[
            r"^escalate\s+(?:ticket\s+)?" +
            _TICKET_ID_PATTERN +
            r"$",
            r"^(?:assign|handoff)\s+(?:ticket\s+)?" +
            _TICKET_ID_PATTERN +
            r"\s+to\s+human$",
        ],
        aliases=[
            "escalate",
            "escalate ticket",
            "handoff to human"],
        params={
            "ticket_id": _TICKET_ID_PATTERN},
        requires_confirmation=True,
        examples=[
            "escalate ticket TKT-123",
            "escalate TKT-456"],
    ))

_register_command(
    CommandDefinition(
        command_type="close_ticket",
        description="Close a ticket",
        category="tickets",
        patterns=[
            r"^close\s+(?:ticket\s+)?" +
            _TICKET_ID_PATTERN +
            r"$",
            r"^(?:resolve|mark\s+as\s+resolved)\s+(?:ticket\s+)?" +
            _TICKET_ID_PATTERN +
            r"$",
        ],
        aliases=[
            "close ticket",
            "resolve ticket"],
        params={
            "ticket_id": _TICKET_ID_PATTERN},
        requires_confirmation=True,
        is_destructive=True,
        examples=["close ticket TKT-123"],
    ))

_register_command(CommandDefinition(
    command_type="reopen_ticket",
    description="Reopen a closed ticket",
    category="tickets",
    patterns=[
        r"^reopen\s+(?:ticket\s+)?" + _TICKET_ID_PATTERN + r"$",
    ],
    aliases=["reopen ticket"],
    params={"ticket_id": _TICKET_ID_PATTERN},
    requires_confirmation=False,
    examples=["reopen ticket TKT-123"],
))

# ── Analytics ────────────────────────────────────────────────────

_register_command(
    CommandDefinition(
        command_type="show_analytics",
        description="Show analytics dashboard summary",
        category="analytics",
        patterns=[
            r"^(?:show|get|display)\s+(?:the\s+)?analytics?$",
            r"^analytics?(?:\s+dashboard)?$",
        ],
        aliases=[
            "analytics",
            "dashboard",
            "show analytics"],
        params={
            "period": r"(?:for\s+(?:the\s+)?)?(?:last|past)\s+" +
            _DURATION_PATTERN,
        },
        examples=[
            "show analytics",
            "analytics for last 7 days"],
    ))

_register_command(CommandDefinition(
    command_type="query_analytics",
    description="Query specific analytics metrics",
    category="analytics",
    patterns=[
        r"^(?:show|get|query)\s+(?:analytics\s+)?(?P<metric>response_time|resolution_rate|csat|first_response|avg_handle|volume|backlog|sla_compliance)",
        r"^(?:what\s+is\s+the\s+)?(?P<metric>response_time|resolution_rate|csat|first_response|avg_handle|volume|backlog|sla_compliance)\??",
    ],
    aliases=["query analytics"],
    params={
        "metric": r"(?P<metric>response_time|resolution_rate|csat|first_response|avg_handle|volume|backlog|sla_compliance)",
        "period": r"(?:for\s+(?:the\s+)?)?(?:last|past)\s+" + _DURATION_PATTERN,
    },
    examples=["show response_time", "what is the csat", "show resolution_rate for last 30 days"],
))

# ── Usage & Cost ────────────────────────────────────────────────

_register_command(
    CommandDefinition(
        command_type="show_usage",
        description="Show usage and cost summary",
        category="usage",
        patterns=[
            r"^(?:show|get|display)\s+(?:current\s+)?(?:usage|cost)s?$",
            r"^(?:usage|cost)\s+(?:summary|report|dashboard)?$",
        ],
        aliases=[
            "usage",
            "cost",
            "show usage",
            "cost report",
            "usage summary"],
        params={
            "period": r"(?:for\s+(?:the\s+)?)?(?:last|past|this)\s+" +
            _DURATION_PATTERN,
        },
        examples=[
            "show usage",
            "cost report",
            "show usage for last 7 days"],
    ))

# ── Integrations ────────────────────────────────────────────────

_register_command(CommandDefinition(
    command_type="list_integrations",
    description="List all configured integrations",
    category="integrations",
    patterns=[
        r"^(?:show|list|get)\s+(?:all\s+)?integrations?$",
        r"^integrations?(?:\s+list)?$",
    ],
    aliases=["integrations", "show integrations", "list integrations"],
    examples=["list integrations", "show integrations"],
))

_register_command(
    CommandDefinition(
        command_type="check_integration",
        description="Check health of a specific integration",
        category="integrations",
        patterns=[
            r"^check\s+(?:integration\s+)?" +
            _INTEGRATION_PATTERN +
            r"\s*(?:health|status)?$",
        ],
        aliases=[
            "check integration",
            "integration health"],
        params={
            "name": _INTEGRATION_PATTERN},
        examples=[
            "check integration paddle",
            "check brevo health"],
    ))

_register_command(CommandDefinition(
    command_type="enable_integration",
    description="Enable an integration",
    category="integrations",
    patterns=[
        r"^enable\s+(?:integration\s+)?" + _INTEGRATION_PATTERN + r"$",
    ],
    aliases=["enable integration"],
    params={"name": _INTEGRATION_PATTERN},
    requires_confirmation=True,
    examples=["enable integration paddle"],
))

_register_command(CommandDefinition(
    command_type="disable_integration",
    description="Disable an integration",
    category="integrations",
    patterns=[
        r"^disable\s+(?:integration\s+)?" + _INTEGRATION_PATTERN + r"$",
    ],
    aliases=["disable integration"],
    params={"name": _INTEGRATION_PATTERN},
    requires_confirmation=True,
    is_destructive=True,
    examples=["disable integration twilio"],
))

# ── Queue Management ────────────────────────────────────────────

_register_command(CommandDefinition(
    command_type="list_queues",
    description="Show Celery queue depths and status",
    category="queues",
    patterns=[
        r"^(?:show|list|get)\s+(?:celery\s+)?queues?$",
        r"^queues?(?:\s+(?:status|depth|list))?$",
    ],
    aliases=["queues", "show queues", "list queues", "queue status"],
    examples=["list queues", "show queue depths"],
))

_register_command(CommandDefinition(
    command_type="purge_queue",
    description="Purge all messages from a queue",
    category="queues",
    patterns=[
        r"^purge\s+(?:queue\s+)?(?P<queue_name>\w+)$",
        r"^(?:clear|flush|empty)\s+(?:queue\s+)?(?P<queue_name>\w+)$",
    ],
    aliases=["purge queue", "clear queue"],
    params={"queue_name": r"(?P<queue_name>\w+)"},
    requires_confirmation=True,
    is_destructive=True,
    examples=["purge queue default", "clear queue ai_heavy"],
))

# ── Incident Management ─────────────────────────────────────────

_register_command(CommandDefinition(
    command_type="list_incidents",
    description="List active system incidents",
    category="incidents",
    patterns=[
        r"^(?:show|list|get)\s+(?:active\s+)?incidents?$",
        r"^incidents?(?:\s+list)?$",
    ],
    aliases=["incidents", "show incidents", "list incidents"],
    examples=["list incidents", "show active incidents"],
))

_register_command(CommandDefinition(
    command_type="resolve_incident",
    description="Resolve a system incident",
    category="incidents",
    patterns=[
        r"^resolve\s+(?:incident\s+)?" + _INCIDENT_ID_PATTERN + r"$",
    ],
    aliases=["resolve incident"],
    params={"incident_id": _INCIDENT_ID_PATTERN},
    requires_confirmation=True,
    examples=["resolve incident INC-001"],
))

# ── Training ─────────────────────────────────────────────────────

_register_command(
    CommandDefinition(
        command_type="train_model",
        description="Trigger model training from recent error data",
        category="training",
        patterns=[
            r"^train\s+(?:model\s+)?(?:from\s+)?(?:last\s+)?errors?$",
            r"^(?:retrain|fine[\s-]?tune)\s+(?:model)?$",
            r"^(?:trigger|start)\s+(?:model\s+)?training$",
        ],
        aliases=[
            "train",
            "train model",
            "retrain",
            "fine-tune",
            "train from error",
            "train from errors"],
        examples=[
            "train from errors",
            "retrain model",
            "fine-tune"],
    ))

_register_command(CommandDefinition(
    command_type="evaluate_model",
    description="Run model evaluation metrics",
    category="training",
    patterns=[
        r"^evaluate\s+(?:model|performance)?$",
        r"^(?:show|get)\s+model\s+(?:metrics?|evaluation|performance)$",
    ],
    aliases=["evaluate", "evaluate model", "model metrics"],
    examples=["evaluate model", "show model metrics"],
))

# ── Deployment ───────────────────────────────────────────────────

_register_command(CommandDefinition(
    command_type="restart_service",
    description="Restart a backend service",
    category="deployment",
    patterns=[
        r"^restart\s+(?P<service>\w+(?:\s+\w+)?)$",
        r"^(?:reload|bounce)\s+(?P<service>\w+(?:\s+\w+)?)$",
    ],
    aliases=["restart service", "restart celery", "restart worker"],
    requires_confirmation=True,
    is_destructive=True,
    params={"service": r"(?P<service>celery|worker|api|all)"},
    examples=["restart celery", "restart worker", "restart all"],
))

_register_command(CommandDefinition(
    command_type="deploy",
    description="Deploy a new version",
    category="deployment",
    patterns=[
        r"^deploy(?:\s+(?P<version>v?\d+\.\d+\.\d+))?$",
        r"^release\s+(?P<version>v?\d+\.\d+\.\d+)?$",
    ],
    aliases=["deploy", "release"],
    params={"version": r"(?P<version>v?\d+\.\d+\.\d+)"},
    requires_confirmation=True,
    is_destructive=True,
    examples=["deploy", "deploy v1.5.0"],
))

_register_command(CommandDefinition(
    command_type="rollback",
    description="Rollback to the previous version",
    category="deployment",
    patterns=[
        r"^rollback(?:\s+(?:to\s+)?(?P<version>v?\d+\.\d+\.\d+))?$",
        r"^revert(?:\s+(?:to\s+)?(?P<version>v?\d+\.\d+\.\d+))?$",
    ],
    aliases=["rollback", "revert"],
    params={"version": r"(?:to\s+)?(?P<version>v?\d+\.\d+\.\d+)"},
    requires_confirmation=True,
    is_destructive=True,
    examples=["rollback", "rollback to v1.4.0"],
))

# ── Help ─────────────────────────────────────────────────────────

_register_command(CommandDefinition(
    command_type="help",
    description="Show available commands and help",
    category="meta",
    patterns=[
        r"^(?:help|commands|list\s+commands|\?)$",
        r"^what\s+(?:can|commands?\s+(?:can|are)|jarvis\s+can)\s+(?:i\s+)?(?:you\s+)?do\??$",
    ],
    aliases=["help", "commands", "list commands", "?", "what can you do"],
    examples=["help", "commands", "what can you do?"],
))


# ══════════════════════════════════════════════════════════════════
# COMMAND PARSER
# ══════════════════════════════════════════════════════════════════


class JarvisCommandParser:
    """Natural Language Command Parser for the Jarvis Command Center (F-087).

    Translates free-text operator commands into structured ParsedCommand
    objects. Uses keyword/pattern matching for speed, with LLM fallback
    reserved for ambiguous commands.

    BC-012: Never crashes — always returns a valid ParsedCommand.
    BC-011: No sensitive data in logs.
    """

    # Commands that need confirmation
    CONFIRMATION_REQUIRED_CATEGORIES = {
        "deployment", "training",
    }

    # Confidence threshold for auto-execution
    AUTO_EXECUTE_CONFIDENCE_THRESHOLD = 0.85

    def __init__(self) -> None:
        """Initialize the command parser with compiled regex patterns."""
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._alias_index: Dict[str, str] = {}

        # Pre-compile all patterns
        for cmd_type, cmd_def in COMMAND_REGISTRY.items():
            compiled = []
            for pattern in cmd_def.patterns:
                try:
                    compiled.append(re.compile(pattern, re.IGNORECASE))
                except re.error:
                    logger.warning(
                        "invalid_command_pattern",
                        command_type=cmd_type,
                        pattern=pattern,
                    )

            self._compiled_patterns[cmd_type] = compiled

            # Index aliases for fast lookup
            for alias in cmd_def.aliases:
                normalized = self._normalize(alias)
                self._alias_index[normalized] = cmd_type

        logger.info(
            "jarvis_command_parser_initialized",
            command_count=len(COMMAND_REGISTRY),
            alias_count=len(self._alias_index),
        )

    def parse(self, command: str,
              context: Optional[Dict[str, Any]] = None) -> ParsedCommand:
        """Parse a natural language command into a structured action.

        Resolution order:
        1. Direct alias match (fastest)
        2. Regex pattern match (most flexible)
        3. Fuzzy/substring match (for typos)
        4. Unknown command (confidence 0.0)

        Args:
            command: Raw natural language input from the operator.
            context: Optional context hints (current view, selected items).

        Returns:
            ParsedCommand with command_type, params, confidence.
        """
        if not command or not command.strip():
            return self._unknown_command(command or "")

        normalized = self._normalize(command)
        stripped = command.strip()

        # 1. Try exact alias match first (O(1) lookup)
        alias_match = self._try_alias_match(normalized, stripped)
        if alias_match:
            logger.debug(
                "command_alias_match",
                command_type=alias_match.command_type,
                confidence=alias_match.confidence,
            )
            return alias_match

        # 2. Try regex pattern matching
        pattern_match = self._try_pattern_match(stripped)
        if pattern_match:
            logger.debug(
                "command_pattern_match",
                command_type=pattern_match.command_type,
                confidence=pattern_match.confidence,
            )
            return pattern_match

        # 3. Try fuzzy/substring matching (lower confidence)
        fuzzy_match = self._try_fuzzy_match(normalized)
        if fuzzy_match:
            logger.debug(
                "command_fuzzy_match",
                command_type=fuzzy_match.command_type,
                confidence=fuzzy_match.confidence,
            )
            return fuzzy_match

        # 4. Unknown command
        unknown = self._unknown_command(stripped)
        logger.info(
            "command_unknown",
            original_command=stripped[:100],
        )
        return unknown

    def get_available_commands(self) -> List[Dict[str, Any]]:
        """Get all registered commands with metadata for help display.

        Returns:
            List of command info dictionaries, grouped by category.
        """
        categories: Dict[str, List[Dict[str, Any]]] = {}
        for cmd_type, cmd_def in COMMAND_REGISTRY.items():
            cat = cmd_def.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                "command_type": cmd_def.command_type,
                "description": cmd_def.description,
                "category": cmd_def.category,
                "aliases": cmd_def.aliases,
                "params": list(cmd_def.params.keys()),
                "requires_confirmation": cmd_def.requires_confirmation or cmd_def.is_destructive,
                "examples": cmd_def.examples,
            })

        # Flatten into sorted list
        result = []
        for cat in sorted(categories.keys()):
            result.extend(
                sorted(
                    categories[cat],
                    key=lambda x: x["command_type"]))

        return result

    def should_auto_execute(self, parsed: ParsedCommand) -> bool:
        """Determine if a parsed command should be auto-executed.

        Args:
            parsed: The parsed command to evaluate.

        Returns:
            True if confidence >= threshold and no confirmation required.
        """
        if parsed.requires_confirmation:
            return False
        if parsed.command_type == "unknown":
            return False
        return parsed.confidence >= self.AUTO_EXECUTE_CONFIDENCE_THRESHOLD

    # ── Private Methods ──────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize command text for matching.

        Lowercases, strips whitespace, collapses multiple spaces.
        """
        return re.sub(r"\s+", " ", text.strip().lower())

    def _try_alias_match(
        self, normalized: str, original: str,
    ) -> Optional[ParsedCommand]:
        """Try exact alias lookup."""

        # Direct match
        cmd_type = self._alias_index.get(normalized)
        if cmd_type:
            cmd_def = COMMAND_REGISTRY[cmd_type]
            return ParsedCommand(
                command_type=cmd_type,
                original_command=original,
                params=self._extract_params_from_context(
                    cmd_def,
                    original,
                    None,
                ),
                confidence=1.0,
                requires_confirmation=cmd_def.requires_confirmation or cmd_def.is_destructive,
                execution_summary=f"Execute: {
                    cmd_def.description}",
                aliases_matched=[normalized],
            )

        return None

    def _try_pattern_match(self, command: str) -> Optional[ParsedCommand]:
        """Try regex pattern matching against all registered commands."""

        best_match: Optional[ParsedCommand] = None
        best_confidence = 0.0

        for cmd_type, patterns in self._compiled_patterns.items():
            cmd_def = COMMAND_REGISTRY[cmd_type]

            for pattern in patterns:
                match = pattern.match(command)
                if match:
                    # Extract named groups as params
                    params = []
                    for group_name, group_value in match.groupdict().items():
                        if group_value is not None:
                            params.append({
                                "name": group_name,
                                "value": group_value.strip(),
                                "confidence": 1.0,
                            })

                    # Also extract from param definitions
                    extra_params = self._extract_params_from_context(
                        cmd_def, command, match,
                    )
                    for ep in extra_params:
                        if not any(p["name"] == ep["name"] for p in params):
                            params.append(ep)

                    confidence = 0.95  # High confidence for regex match
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = ParsedCommand(
                            command_type=cmd_type,
                            original_command=command,
                            params=params,
                            confidence=confidence,
                            requires_confirmation=cmd_def.requires_confirmation or cmd_def.is_destructive,
                            execution_summary=f"Execute: {
                                cmd_def.description}",
                        )

        return best_match

    def _try_fuzzy_match(self, normalized: str) -> Optional[ParsedCommand]:
        """Try fuzzy/substring matching for typos and variations."""

        best_match: Optional[ParsedCommand] = None
        best_score = 0.0

        for cmd_type, cmd_def in COMMAND_REGISTRY.items():
            # Check if normalized input is a substring of any alias
            for alias in cmd_def.aliases:
                alias_norm = self._normalize(alias)
                if alias_norm in normalized or normalized in alias_norm:
                    # Calculate similarity score
                    score = self._simple_similarity(normalized, alias_norm)
                    if score > best_score and score >= 0.5:
                        best_score = score
                        best_match = ParsedCommand(
                            command_type=cmd_type,
                            original_command=normalized,
                            params=self._extract_params_from_context(
                                cmd_def, normalized, None,
                            ),
                            confidence=round(score, 2),
                            requires_confirmation=cmd_def.requires_confirmation or cmd_def.is_destructive,
                            execution_summary=(
                                f"Execute: {cmd_def.description} "
                                f"(fuzzy match, confidence={score:.0%})"
                            ),
                            aliases_matched=[alias],
                        )

        return best_match

    def _extract_params_from_context(
        self,
        cmd_def: CommandDefinition,
        command: str,
        regex_match: Optional[re.Match],
    ) -> List[Dict[str, Any]]:
        """Extract additional parameters from command text using param defs."""
        params = []

        for param_name, param_pattern in cmd_def.params.items():
            # Skip if already extracted by the main regex
            if regex_match and param_name in regex_match.groupdict():
                continue

            try:
                p = re.compile(param_pattern, re.IGNORECASE)
                m = p.search(command)
                if m and param_name in m.groupdict() and m.groupdict()[
                        param_name]:
                    params.append({
                        "name": param_name,
                        "value": m.groupdict()[param_name].strip(),
                        "confidence": 0.9,
                    })
            except re.error:
                continue

        return params

    @staticmethod
    def _simple_similarity(a: str, b: str) -> float:
        """Simple substring-based similarity score.

        Returns 1.0 for exact match, higher scores for longer
        common substrings.
        """
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0

        # Check if one contains the other
        if a in b or b in a:
            shorter = min(len(a), len(b))
            longer = max(len(a), len(b))
            return shorter / longer

        # Simple word overlap
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0

        overlap = len(words_a & words_b)
        union = len(words_a | words_b)
        return overlap / union if union > 0 else 0.0

    @staticmethod
    def _unknown_command(command: str) -> ParsedCommand:
        """Create a ParsedCommand for unrecognized input."""
        return ParsedCommand(
            command_type="unknown",
            original_command=command,
            confidence=0.0,
            requires_confirmation=False,
            execution_summary="Command not recognized. Type 'help' for available commands.",
        )


# Module-level singleton
_parser_instance: Optional[JarvisCommandParser] = None


def get_command_parser() -> JarvisCommandParser:
    """Get or create the singleton command parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = JarvisCommandParser()
    return _parser_instance


__all__ = [
    "ParsedCommand",
    "CommandDefinition",
    "COMMAND_REGISTRY",
    "JarvisCommandParser",
    "get_command_parser",
]

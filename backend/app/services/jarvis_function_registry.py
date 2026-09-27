"""
PARWA Jarvis Function Registry — LLM Function Calling Definitions

The complete registry of everything Jarvis can DO. Each function is defined
as an LLM tool spec (OpenAI-compatible function calling format) with:
  - name, description, parameters (JSON Schema)
  - safety_level: none / confirmation_required / approval_required
  - tier_available: which subscription tiers can use this function
  - category: grouping for organization

This is what gets passed to the LLM as "tools" for function calling.
Clients NEVER see this — they just talk naturally and Jarvis figures out
which function to call.

Safety Levels:
  - none: Just do it immediately (e.g., check system health)
  - confirmation_required: Ask "are you sure?" before executing
    (e.g., pause all AI, escalate tickets)
  - approval_required: Require explicit "confirm" — for monetary,
    destructive, or irreversible actions (e.g., process refund,
    delete data, change billing)

Mode Switching:
  - AGENTIC MODE (variant task / customer chat): Only include
    category="customer_facing" functions. Jarvis acts as an AI agent
    talking to the client's customers.
  - COMMAND MODE (Jarvis admin chat): Include ALL functions. Jarvis
    acts as the platform's CLI — anything the platform can do, Jarvis
    can do.

Architecture:
  User says something
      → Orchestrator decides mode (agentic vs command)
      → Passes relevant function definitions to LLM
      → LLM picks function + generates conversational response
      → Safety gate checks before execution
      → Execute function call against backend API
      → Feed result back to LLM for final human-like response

BC-001: company_id enforced at execution layer, not registry layer.
BC-008: Registry never crashes — all definitions are static.
BC-012: All timestamps UTC.
"""

from typing import Any, Dict, List, Optional

from app.logger import get_logger

logger = get_logger("jarvis_function_registry")


# ══════════════════════════════════════════════════════════════════
# SAFETY LEVELS
# ══════════════════════════════════════════════════════════════════

SAFETY_NONE = "none"
SAFETY_CONFIRMATION = "confirmation_required"
SAFETY_APPROVAL = "approval_required"


# ══════════════════════════════════════════════════════════════════
# CATEGORIES
# ══════════════════════════════════════════════════════════════════

CATEGORY_SYSTEM = "system"              # System health, status, config
CATEGORY_AI_CONTROL = "ai_control"      # Pause/resume AI agents
CATEGORY_TICKETS = "tickets"            # Ticket management
CATEGORY_BILLING = "billing"            # Billing, subscriptions, refunds
CATEGORY_INTEGRATIONS = "integrations"  # Channel setup, integrations
CATEGORY_ANALYTICS = "analytics"        # Reports, dashboards, metrics
CATEGORY_AGENTS = "agents"              # Agent pool, provisioning
CATEGORY_KNOWLEDGE = "knowledge"        # Knowledge base management
CATEGORY_CUSTOMER_FACING = "customer_facing"  # Functions available in agentic mode
CATEGORY_COMMUNICATION = "communication"  # Call customer, send message
CATEGORY_SETTINGS = "settings"          # Company settings, preferences
CATEGORY_ACTIVITY = "activity"          # Activity log, awareness events


# ══════════════════════════════════════════════════════════════════
# TIER AVAILABILITY
# ══════════════════════════════════════════════════════════════════

TIER_ALL = ["mini_parwa", "parwa", "parwa_high"]
TIER_STANDARD_AND_UP = ["parwa", "parwa_high"]
TIER_PREMIUM_ONLY = ["parwa_high"]


# ══════════════════════════════════════════════════════════════════
# FUNCTION DEFINITIONS
# ══════════════════════════════════════════════════════════════════

FUNCTION_REGISTRY: List[Dict[str, Any]] = [
    # ────────────────────────────────────────────────────────────
    # SYSTEM HEALTH & STATUS
    # ────────────────────────────────────────────────────────────
    {
        "name": "check_system_health",
        "description": (
            "Check the current health of the system. Returns overall status "
            "(healthy/degraded/critical/down), channel health, error rate, "
            "and uptime. Use when the user asks how things are going, "
            "system status, or if there are any issues."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_SYSTEM,
    },
    {
        "name": "show_recent_errors",
        "description": (
            "Show recent system errors. Returns the last errors that occurred, "
            "including error type, timestamp, and affected component. Use when "
            "the user asks about errors, failures, or something going wrong."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of recent errors to show (default 10, max 50)",
                    "default": 10,
                },
                "severity": {
                    "type": "string",
                    "enum": ["all", "warning", "error", "critical"],
                    "description": "Filter by error severity (default 'all')",
                    "default": "all",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_SYSTEM,
    },
    {
        "name": "get_current_config",
        "description": (
            "Get the current system configuration and settings. Returns "
            "AI settings, notification preferences, SLA rules, and other "
            "configuration. Use when the user asks about their settings, "
            "preferences, or how things are configured."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "enum": ["all", "ai", "notifications", "sla", "channels", "billing"],
                    "description": "Which configuration section to show (default 'all')",
                    "default": "all",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_SYSTEM,
    },

    # ────────────────────────────────────────────────────────────
    # AI CONTROL
    # ────────────────────────────────────────────────────────────
    {
        "name": "pause_all_ai",
        "description": (
            "Pause all AI agent activity immediately. AI agents will stop "
            "handling tickets until resumed. Use when the user wants to stop "
            "AI, pause everything, or when something is going wrong and they "
            "want to take manual control."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the AI is being paused (for audit log)",
                },
            },
            "required": ["reason"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_AI_CONTROL,
    },
    {
        "name": "resume_all_ai",
        "description": (
            "Resume AI agent activity after a pause. AI agents will start "
            "handling tickets again. Use when the user wants to turn AI back "
            "on, restart, or continue operations."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_AI_CONTROL,
    },
    {
        "name": "pause_refunds",
        "description": (
            "Pause automated refund processing. Refund requests will be "
            "queued but not processed until resumed. Use when the user wants "
            "to temporarily stop refund processing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why refund processing is being paused",
                },
            },
            "required": ["reason"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_AI_CONTROL,
    },
    {
        "name": "resume_refunds",
        "description": (
            "Resume automated refund processing after a pause. Queued refund "
            "requests will start being processed again."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_AI_CONTROL,
    },
    {
        "name": "emergency_stop",
        "description": (
            "Emergency shutdown — immediately pause ALL automated operations "
            "including AI agents, refund processing, and scheduled tasks. "
            "Use ONLY for emergencies, critical issues, or when the user "
            "explicitly requests an emergency stop."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Emergency reason (required for audit)",
                },
            },
            "required": ["reason"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_AI_CONTROL,
    },

    # ────────────────────────────────────────────────────────────
    # TICKETS
    # ────────────────────────────────────────────────────────────
    {
        "name": "get_ticket_stats",
        "description": (
            "Get ticket statistics — volume, open/closed counts, average "
            "response time, resolution rate. Use when the user asks about "
            "tickets, workload, or support metrics."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "time_range": {
                    "type": "string",
                    "enum": ["today", "this_week", "this_month", "all_time"],
                    "description": "Time range for statistics (default 'today')",
                    "default": "today",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_TICKETS,
    },
    {
        "name": "get_ticket_details",
        "description": (
            "Get details about a specific ticket — status, assigned agent, "
            "conversation history, resolution, and SLA status. Use when the "
            "user asks about a particular ticket or support case."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The ticket ID to look up",
                },
            },
            "required": ["ticket_id"],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_TICKETS,
    },
    {
        "name": "escalate_urgent_tickets",
        "description": (
            "Escalate all urgent or high-priority tickets to human agents. "
            "Use when the user wants to make sure urgent issues get human "
            "attention, or when there's a spike in critical tickets."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "priority": {
                    "type": "string",
                    "enum": ["urgent", "high", "critical"],
                    "description": "Minimum priority to escalate (default 'urgent')",
                    "default": "urgent",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_TICKETS,
    },
    {
        "name": "reassign_ticket",
        "description": (
            "Reassign a ticket to a different agent. Use when the user wants "
            "to move a ticket to someone else."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The ticket to reassign",
                },
                "reason": {
                    "type": "string",
                    "description": "Why the ticket is being reassigned",
                },
                "agent_id": {
                    "type": "string",
                    "description": "ID of the agent to assign to (optional — auto-assign if not specified)",
                },
            },
            "required": ["ticket_id", "reason"],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_TICKETS,
    },

    # ────────────────────────────────────────────────────────────
    # BILLING & SUBSCRIPTIONS
    # ────────────────────────────────────────────────────────────
    {
        "name": "get_subscription_info",
        "description": (
            "Get current subscription plan details — plan name, usage, "
            "limits, renewal date, and billing status. Use when the user "
            "asks about their plan, billing, usage, or subscription."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_BILLING,
    },
    {
        "name": "get_usage_report",
        "description": (
            "Get current usage report — tickets used, AI messages sent, "
            "tokens consumed, and remaining quota. Use when the user asks "
            "about their usage, quota, or how much they've used."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "this_week", "this_month"],
                    "description": "Time period (default 'this_month')",
                    "default": "this_month",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_BILLING,
    },
    {
        "name": "process_refund",
        "description": (
            "Process a refund for a customer via Paddle Adjustments API. "
            "This is a REAL MONETARY action — it will actually issue a refund "
            "through Paddle. Use ONLY when the user explicitly requests a "
            "refund and confirms the amount. Can do full or partial refunds."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Paddle customer ID of the customer to refund",
                },
                "amount": {
                    "type": "number",
                    "description": "Refund amount (for partial refunds)",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for the refund (e.g., 'defective product', 'subscription canceled')",
                },
                "ticket_id": {
                    "type": "string",
                    "description": "Related ticket ID (if applicable, for audit trail)",
                },
                "transaction_id": {
                    "type": "string",
                    "description": "Paddle transaction ID to refund (optional — auto-finds latest if not given)",
                },
                "partial": {
                    "type": "boolean",
                    "description": "If true, do a partial refund for the given amount instead of full (default false)",
                    "default": False,
                },
            },
            "required": ["customer_id", "amount", "reason"],
        },
        "safety_level": SAFETY_APPROVAL,
        "tier_available": TIER_STANDARD_AND_UP,
        "category": CATEGORY_BILLING,
    },
    {
        "name": "upgrade_plan",
        "description": (
            "Upgrade the subscription plan to a higher tier via Paddle API. "
            "Available plans: mini_parwa (Starter), parwa (Professional), "
            "parwa_high (Enterprise). Paddle handles proration automatically. "
            "Use when the user wants to upgrade, change to a higher plan, "
            "or get more features and capacity."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_plan": {
                    "type": "string",
                    "enum": ["mini_parwa", "parwa", "parwa_high"],
                    "description": "The plan to upgrade to",
                },
                "reason": {
                    "type": "string",
                    "description": "Why the user is upgrading (optional, for audit)",
                },
            },
            "required": ["target_plan"],
        },
        "safety_level": SAFETY_APPROVAL,
        "tier_available": TIER_ALL,
        "category": CATEGORY_BILLING,
    },
    {
        "name": "cancel_subscription",
        "description": (
            "Cancel the subscription via Paddle API. By default, cancels at "
            "the end of the current billing period (Netflix-style). If "
            "immediate=True, cancels right away. Use when the user wants to "
            "cancel, stop their subscription, or end their account."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the subscription is being cancelled",
                },
                "immediate": {
                    "type": "boolean",
                    "description": "Cancel immediately instead of at end of billing period (default false)",
                    "default": False,
                },
            },
            "required": ["reason"],
        },
        "safety_level": SAFETY_APPROVAL,
        "tier_available": TIER_ALL,
        "category": CATEGORY_BILLING,
    },
    {
        "name": "get_transaction_history",
        "description": (
            "Get transaction and billing history from Paddle. Returns real "
            "payment data with amounts, dates, statuses, and totals. Use when "
            "the user asks about their billing history, payments, charges, "
            "invoices, or transaction history."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["last_30_days", "last_90_days", "this_year", "all"],
                    "description": "Time period for transaction history (default 'last_30_days')",
                    "default": "last_30_days",
                },
                "transaction_type": {
                    "type": "string",
                    "enum": ["all", "payment", "refund", "credit"],
                    "description": "Filter by transaction type (default 'all')",
                    "default": "all",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_BILLING,
    },
    {
        "name": "get_invoices",
        "description": (
            "Get invoice list from Paddle. Returns invoice IDs, numbers, "
            "amounts, and statuses. Use when the user asks about invoices, "
            "needs an invoice, or wants billing documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_BILLING,
    },

    # ────────────────────────────────────────────────────────────
    # INTEGRATIONS & CHANNELS
    # ────────────────────────────────────────────────────────────
    {
        "name": "list_integrations",
        "description": (
            "List all configured integrations — email, SMS, chat widget, "
            "Shopify, etc. Show status (active/inactive) and health. Use "
            "when the user asks about their integrations or connected services."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_INTEGRATIONS,
    },
    {
        "name": "setup_email_channel",
        "description": (
            "Set up or configure the email support channel. Connects an "
            "email address for receiving and sending support emails. Use "
            "when the user wants to set up email support."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "email_address": {
                    "type": "string",
                    "description": "Support email address to connect",
                },
                "provider": {
                    "type": "string",
                    "enum": ["gmail", "outlook", "custom_imap"],
                    "description": "Email provider type (default 'custom_imap')",
                    "default": "custom_imap",
                },
            },
            "required": ["email_address"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_INTEGRATIONS,
    },
    {
        "name": "setup_sms_channel",
        "description": (
            "Set up or configure the SMS support channel. Connects a phone "
            "number for SMS-based customer support. Use when the user wants "
            "to set up SMS support."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "Phone number for SMS support",
                },
            },
            "required": ["phone_number"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_STANDARD_AND_UP,
        "category": CATEGORY_INTEGRATIONS,
    },
    {
        "name": "setup_chat_widget",
        "description": (
            "Set up or configure the chat widget for the website. Provides "
            "embed code and configuration. Use when the user wants to add "
            "a chat widget to their website."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "website_url": {
                    "type": "string",
                    "description": "Website URL where the widget will be embedded",
                },
                "widget_color": {
                    "type": "string",
                    "description": "Primary color for the widget (hex, e.g., '#4F46E5')",
                },
                "position": {
                    "type": "string",
                    "enum": ["bottom_right", "bottom_left"],
                    "description": "Widget position on the page (default 'bottom_right')",
                    "default": "bottom_right",
                },
            },
            "required": ["website_url"],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_INTEGRATIONS,
    },

    # ────────────────────────────────────────────────────────────
    # ANALYTICS & REPORTS
    # ────────────────────────────────────────────────────────────
    {
        "name": "export_report",
        "description": (
            "Generate and export a performance report. Covers ticket metrics, "
            "AI performance, customer satisfaction, and agent utilization. Use "
            "when the user asks for a report, summary, or analytics."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["weekly", "monthly", "daily", "custom"],
                    "description": "Type of report to generate (default 'weekly')",
                    "default": "weekly",
                },
                "format": {
                    "type": "string",
                    "enum": ["pdf", "csv", "json"],
                    "description": "Export format (default 'pdf')",
                    "default": "pdf",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_ANALYTICS,
    },
    {
        "name": "get_performance_metrics",
        "description": (
            "Get real-time performance metrics — response times, resolution "
            "rates, customer satisfaction scores, AI accuracy, and SLA "
            "compliance. Use when the user asks about performance or how "
            "well things are working."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": [
                        "all", "response_time", "resolution_rate",
                        "csat", "ai_accuracy", "sla_compliance",
                    ],
                    "description": "Specific metric to show (default 'all')",
                    "default": "all",
                },
                "time_range": {
                    "type": "string",
                    "enum": ["today", "this_week", "this_month"],
                    "description": "Time range (default 'today')",
                    "default": "today",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_ANALYTICS,
    },

    # ────────────────────────────────────────────────────────────
    # AGENT POOL
    # ────────────────────────────────────────────────────────────
    {
        "name": "get_agent_status",
        "description": (
            "Get the status of AI and human agents — how many are active, "
            "utilization, capacity. Use when the user asks about agents, "
            "capacity, or who's handling tickets."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_AGENTS,
    },
    {
        "name": "add_agents",
        "description": (
            "Add more AI agent capacity. Provisions additional AI agents to "
            "handle more tickets. Use when the user wants more agents, needs "
            "more capacity, or is expecting higher volume."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of additional agents to add (default 1)",
                    "default": 1,
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_AGENTS,
    },

    # ────────────────────────────────────────────────────────────
    # KNOWLEDGE BASE
    # ────────────────────────────────────────────────────────────
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the knowledge base for articles, FAQs, and documentation. "
            "Returns matching entries with relevance scores. Use when the user "
            "asks about what information is in their knowledge base, or wants "
            "to find specific content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_KNOWLEDGE,
    },
    {
        "name": "add_knowledge_article",
        "description": (
            "Add a new article to the knowledge base. Use when the user wants "
            "to add information, FAQ, or documentation that the AI can use "
            "when helping customers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Article title",
                },
                "content": {
                    "type": "string",
                    "description": "Article content",
                },
                "category": {
                    "type": "string",
                    "description": "Article category or topic",
                },
            },
            "required": ["title", "content"],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_KNOWLEDGE,
    },

    # ────────────────────────────────────────────────────────────
    # CUSTOMER-FACING (AGENTIC MODE)
    # ────────────────────────────────────────────────────────────
    {
        "name": "answer_customer_question",
        "description": (
            "Answer a customer's question using the knowledge base and "
            "company context. This is the primary agentic function — use "
            "when chatting with a customer and they ask something. The "
            "response will be helpful, accurate, and in the brand's voice."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The customer's question",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context (ticket history, customer info)",
                },
            },
            "required": ["question"],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_CUSTOMER_FACING,
    },
    {
        "name": "check_order_status",
        "description": (
            "Check the status of a customer's order. Looks up order by ID "
            "or customer info and returns tracking, delivery status, and "
            "estimated date. Use when a customer asks about their order."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID to look up",
                },
                "customer_email": {
                    "type": "string",
                    "description": "Customer email (alternative lookup)",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_CUSTOMER_FACING,
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Escalate the current conversation to a human agent. Use when "
            "the customer's issue is too complex, sensitive, or requires "
            "human judgment that AI can't provide."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why escalation is needed",
                },
                "priority": {
                    "type": "string",
                    "enum": ["normal", "high", "urgent"],
                    "description": "Escalation priority (default 'normal')",
                    "default": "normal",
                },
            },
            "required": ["reason"],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_CUSTOMER_FACING,
    },

    # ────────────────────────────────────────────────────────────
    # COMMUNICATION
    # ────────────────────────────────────────────────────────────
    {
        "name": "call_customer",
        "description": (
            "Initiate a phone call to a customer. Use when the user wants "
            "to call a customer, set up a phone call, or when a situation "
            "requires voice communication."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "Related ticket ID",
                },
                "reason": {
                    "type": "string",
                    "description": "Why the call is needed",
                },
            },
            "required": ["ticket_id", "reason"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_STANDARD_AND_UP,
        "category": CATEGORY_COMMUNICATION,
    },

    # ────────────────────────────────────────────────────────────
    # SETTINGS
    # ────────────────────────────────────────────────────────────
    {
        "name": "update_settings",
        "description": (
            "Update system settings — AI behavior, notification preferences, "
            "SLA rules, auto-approval rules, and other configuration. Use "
            "when the user wants to change how something works."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "enum": ["ai", "notifications", "sla", "auto_approve_rules", "brand_voice"],
                    "description": "Which settings section to update",
                },
                "updates": {
                    "type": "object",
                    "description": "Key-value pairs to update",
                },
            },
            "required": ["section", "updates"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_SETTINGS,
    },
    {
        "name": "disable_auto_approve_rule",
        "description": (
            "Disable the most recently added auto-approve rule. Use when "
            "the user wants to remove or disable a rule that was auto-approving "
            "actions. This is a safety-sensitive operation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "rule_id": {
                    "type": "string",
                    "description": "Specific rule ID to disable (optional — defaults to most recent)",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_SETTINGS,
    },

    # ────────────────────────────────────────────────────────────
    # TICKET CREATION & SOLVING (VARIANT INTEGRATION)
    # ────────────────────────────────────────────────────────────
    {
        "name": "create_ticket",
        "description": (
            "Create a new support ticket. The ticket will be assigned to "
            "the appropriate AI variant for handling. Use when the user "
            "wants to create a ticket, log a support issue, or report a "
            "problem that needs attention. You can specify the customer, "
            "subject, priority, and category."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Brief description of the issue or request",
                },
                "message": {
                    "type": "string",
                    "description": "Detailed message from the customer about their issue",
                },
                "customer_email": {
                    "type": "string",
                    "description": "Customer email address (optional — creates anonymous ticket if not provided)",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Customer name (optional)",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Ticket priority level (default 'medium')",
                    "default": "medium",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "tech_support", "billing", "feature_request",
                        "bug_report", "general", "complaint",
                        "returns_refunds", "order_tracking", "delivery_issues",
                        "account_management", "subscription_billing",
                    ],
                    "description": "Ticket category (default 'general')",
                    "default": "general",
                },
                "channel": {
                    "type": "string",
                    "enum": ["chat", "email", "sms", "api", "phone"],
                    "description": "Channel the request came from (default 'chat')",
                    "default": "chat",
                },
            },
            "required": ["subject", "message"],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_TICKETS,
    },
    {
        "name": "solve_ticket",
        "description": (
            "Solve a ticket by routing it through the AI variant pipeline. "
            "The variant (Mini Parwa, Parwa, or Parwa High) will process "
            "the ticket's conversation and generate an AI response to resolve "
            "the customer's issue. Use when the user wants to solve a ticket, "
            "have AI handle a ticket, or resolve a customer's problem."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The ticket ID to solve",
                },
                "force_variant": {
                    "type": "string",
                    "enum": ["auto", "mini_parwa", "parwa", "parwa_high"],
                    "description": "Override which variant to use (default 'auto' — uses the tenant's configured variant)",
                    "default": "auto",
                },
            },
            "required": ["ticket_id"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_TICKETS,
    },
    {
        "name": "list_recent_tickets",
        "description": (
            "List recent tickets with their status, priority, and category. "
            "Use when the user wants to see recent tickets, check what's "
            "open, or get an overview of current support activity."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["all", "open", "in_progress", "resolved", "closed"],
                    "description": "Filter by ticket status (default 'all')",
                    "default": "all",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of tickets to return (default 10, max 50)",
                    "default": 10,
                },
                "priority": {
                    "type": "string",
                    "enum": ["all", "low", "medium", "high", "critical"],
                    "description": "Filter by priority (default 'all')",
                    "default": "all",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_TICKETS,
    },
    {
        "name": "batch_solve_tickets",
        "description": (
            "Solve multiple tickets at once by routing them through the AI "
            "variant pipeline. Each ticket is processed independently by the "
            "appropriate variant. Use when the user wants to resolve a batch "
            "of tickets, clear the queue, or handle multiple open tickets at once."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["open", "in_progress", "all_open"],
                    "description": "Which tickets to solve: 'open' for just open, 'in_progress' for those already being worked on, 'all_open' for both (default 'open')",
                    "default": "open",
                },
                "max_tickets": {
                    "type": "integer",
                    "description": "Maximum number of tickets to process in this batch (default 10, max 50)",
                    "default": 10,
                },
                "priority_filter": {
                    "type": "string",
                    "enum": ["all", "high", "critical"],
                    "description": "Only solve tickets with this priority or higher (default 'all')",
                    "default": "all",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_TICKETS,
    },
    # ────────────────────────────────────────────────────────────
    # PLAN UPGRADE / CHANGE / CANCEL
    # ────────────────────────────────────────────────────────────
    {
        "name": "upgrade_plan",
        "description": (
            "Upgrade the current subscription plan to a higher tier. "
            "Available tiers: mini_parwa (starter), parwa (professional), "
            "parwa_high (enterprise). Use when the user wants to upgrade, "
            "change plan, move to a better plan, or get more features. "
            "This is a BILLING action — it affects the subscription."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_plan": {
                    "type": "string",
                    "enum": ["mini_parwa", "parwa", "parwa_high"],
                    "description": "The plan to upgrade to",
                },
                "reason": {
                    "type": "string",
                    "description": "Why the upgrade is being requested (optional, for audit)",
                },
            },
            "required": ["target_plan"],
        },
        "safety_level": SAFETY_APPROVAL,
        "tier_available": TIER_ALL,
        "category": CATEGORY_BILLING,
    },
    {
        "name": "cancel_subscription",
        "description": (
            "Cancel the current subscription. This will schedule the "
            "subscription for cancellation at the end of the current "
            "billing period. Use when the user explicitly wants to cancel, "
            "end their subscription, or stop using the service. This is a "
            "DESTRUCTIVE action — confirm carefully."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the subscription is being cancelled (required for retention team)",
                },
                "immediate": {
                    "type": "boolean",
                    "description": "Cancel immediately instead of at end of billing period (default false)",
                    "default": False,
                },
            },
            "required": ["reason"],
        },
        "safety_level": SAFETY_APPROVAL,
        "tier_available": TIER_ALL,
        "category": CATEGORY_BILLING,
    },
    {
        "name": "get_transaction_history",
        "description": (
            "Get the transaction/billing history — payments, refunds, "
            "credits, and charges. Shows amount, date, status, and "
            "description for each transaction. Use when the user asks "
            "about their transaction history, billing history, payment "
            "history, charges, invoices, or past payments."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["last_30_days", "last_90_days", "this_year", "all"],
                    "description": "Time period for transaction history (default 'last_30_days')",
                    "default": "last_30_days",
                },
                "transaction_type": {
                    "type": "string",
                    "enum": ["all", "payments", "refunds", "credits", "charges"],
                    "description": "Filter by transaction type (default 'all')",
                    "default": "all",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_BILLING,
    },

    {
        "name": "generate_fake_requests",
        "description": (
            "Generate simulated customer support requests for testing and "
            "demonstration purposes. These fake requests will be converted "
            "into real tickets by the variant pipeline, so you can see how "
            "the AI handles different types of customer issues. Use when "
            "the user wants to test the system, create demo data, or see "
            "how variants handle different requests."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of fake requests to generate (default 5, max 25)",
                    "default": 5,
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "mixed", "tech_support", "billing", "returns_refunds",
                        "order_tracking", "delivery_issues", "account_management",
                        "complaint", "feature_request",
                    ],
                    "description": "Type of requests to generate — 'mixed' gives a realistic variety (default 'mixed')",
                    "default": "mixed",
                },
                "auto_solve": {
                    "type": "boolean",
                    "description": "Automatically route generated tickets through the variant pipeline for solving (default false)",
                    "default": False,
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "tier_available": TIER_ALL,
        "category": CATEGORY_TICKETS,
    },

    # ────────────────────────────────────────────────────────────
    # ACTIVITY STORE & AWARENESS
    # ────────────────────────────────────────────────────────────
    {
        "name": "query_activity_log",
        "description": (
            "Query the activity log for recent events. The activity log "
            "records everything that happens in the system: user actions, "
            "billing events, channel events, admin actions, system events, "
            "and agent actions. Use when the user asks about what's been "
            "happening, recent activity, or wants to know about specific "
            "events like payments, emails, or configuration changes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": [
                        "all", "user_action", "billing", "channel",
                        "admin", "system", "integration", "agent_action",
                    ],
                    "description": "Filter by event source (default 'all')",
                    "default": "all",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "all", "ui", "subscription", "payment", "refund",
                        "channel_email", "channel_sms", "channel_voice",
                        "channel_chat", "channel_webhook", "config",
                        "security", "integration", "cron", "agent",
                        "sla", "escalation", "quality", "training",
                    ],
                    "description": "Filter by event category (default 'all')",
                    "default": "all",
                },
                "severity": {
                    "type": "string",
                    "enum": ["all", "info", "warning", "critical", "emergency"],
                    "description": "Filter by severity (default 'all')",
                    "default": "all",
                },
                "minutes": {
                    "type": "integer",
                    "description": "How far back to look in minutes (default 60)",
                    "default": 60,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max events to return (default 20, max 100)",
                    "default": 20,
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_ACTIVITY,
    },
    {
        "name": "get_activity_summary",
        "description": (
            "Get a summary of recent activity across the system. Returns "
            "counts by source, category, severity, and control boundary. "
            "Shows what Jarvis can and cannot control. Use when the user "
            "asks 'what's happening?', 'give me an overview', or wants "
            "to understand the current state of the system."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "Look-back window in hours (default 24)",
                    "default": 24,
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_ACTIVITY,
    },
    {
        "name": "get_control_boundary_report",
        "description": (
            "Get a report of what Jarvis can and cannot control. Shows "
            "how many events are in each control boundary: "
            "jarvis_can_act (Jarvis can take action), "
            "agent_controlled (variant agents handle this - ask them), "
            "notify_only (Jarvis sees but can't control), "
            "human_required (only humans can handle this). "
            "Use when the user asks about Jarvis's control scope or "
            "what needs human attention."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "Look-back window in hours (default 24)",
                    "default": 24,
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_ACTIVITY,
    },
    {
        "name": "get_critical_events",
        "description": (
            "Get critical and emergency events that need immediate attention. "
            "These are the most important events in the activity log. "
            "Use when the user asks about problems, issues, or what needs "
            "attention right now."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "How far back to look in hours (default 24)",
                    "default": 24,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max events to return (default 10)",
                    "default": 10,
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "tier_available": TIER_ALL,
        "category": CATEGORY_ACTIVITY,
    },
]


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════


def get_function_definitions(
    mode: str = "command",
    tier: str = "parwa",
    categories: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Get LLM function definitions (tool specs) for the given mode and tier.

    This is what gets passed to the LLM as "tools" for function calling.

    Mode switching:
      - "command" (admin chat): Include ALL functions available to the tier
      - "agentic" (customer chat): Include ONLY customer_facing functions

    Args:
        mode: "command" for admin chat, "agentic" for customer chat.
        tier: Subscription tier — limits which functions are available.
        categories: Optional filter — only return these categories.

    Returns:
        List of function definitions in OpenAI tool-calling format.
    """
    try:
        definitions = []

        for func_def in FUNCTION_REGISTRY:
            # ── Mode filter ──
            if mode == "agentic":
                # In agentic mode, only include customer-facing functions
                if func_def["category"] != CATEGORY_CUSTOMER_FACING:
                    continue

            # ── Tier filter ──
            if tier not in func_def.get("tier_available", TIER_ALL):
                continue

            # ── Category filter ──
            if categories and func_def["category"] not in categories:
                continue

            # Build OpenAI tool-calling format
            tool_def = {
                "type": "function",
                "function": {
                    "name": func_def["name"],
                    "description": func_def["description"],
                    "parameters": func_def["parameters"],
                },
            }
            definitions.append(tool_def)

        logger.debug(
            "function_registry: mode=%s, tier=%s, categories=%s, count=%d",
            mode, tier, categories, len(definitions),
        )

        return definitions

    except Exception:
        logger.exception("get_function_definitions_error")
        return []


def get_function_metadata(function_name: str) -> Optional[Dict[str, Any]]:
    """Get the full metadata for a function by name.

    Includes safety_level, tier_available, and category — these are
    NOT passed to the LLM but are used internally by the safety gate
    and orchestrator.

    Args:
        function_name: The function name to look up.

    Returns:
        Full function definition dict, or None if not found.
    """
    for func_def in FUNCTION_REGISTRY:
        if func_def["name"] == function_name:
            return func_def
    return None


def get_safety_level(function_name: str) -> str:
    """Get the safety level for a function by name.

    Args:
        function_name: The function name to look up.

    Returns:
        Safety level string: "none", "confirmation_required", or "approval_required".
        Defaults to "confirmation_required" if function not found (fail-safe).
    """
    metadata = get_function_metadata(function_name)
    if metadata:
        return metadata.get("safety_level", SAFETY_CONFIRMATION)
    # Fail-safe: if we don't know the function, require confirmation
    logger.warning("unknown_function_safety_default: function=%s", function_name)
    return SAFETY_CONFIRMATION


def get_function_categories() -> List[str]:
    """Get all available function categories."""
    return list(set(f["category"] for f in FUNCTION_REGISTRY))


def get_functions_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all function definitions in a category."""
    return [f for f in FUNCTION_REGISTRY if f["category"] == category]


def get_function_names(mode: str = "command", tier: str = "parwa") -> List[str]:
    """Get just the function names available for a mode and tier.

    Useful for logging and debugging.
    """
    defs = get_function_definitions(mode=mode, tier=tier)
    return [d["function"]["name"] for d in defs]


def get_function_count_by_safety() -> Dict[str, int]:
    """Get count of functions by safety level. Useful for docs/debugging."""
    counts: Dict[str, int] = {}
    for func_def in FUNCTION_REGISTRY:
        level = func_def.get("safety_level", "none")
        counts[level] = counts.get(level, 0) + 1
    return counts


__all__ = [
    # Constants
    "SAFETY_NONE",
    "SAFETY_CONFIRMATION",
    "SAFETY_APPROVAL",
    "CATEGORY_SYSTEM",
    "CATEGORY_AI_CONTROL",
    "CATEGORY_TICKETS",
    "CATEGORY_BILLING",
    "CATEGORY_INTEGRATIONS",
    "CATEGORY_ANALYTICS",
    "CATEGORY_AGENTS",
    "CATEGORY_KNOWLEDGE",
    "CATEGORY_CUSTOMER_FACING",
    "CATEGORY_COMMUNICATION",
    "CATEGORY_SETTINGS",
    "TIER_ALL",
    "TIER_STANDARD_AND_UP",
    "TIER_PREMIUM_ONLY",
    # Registry
    "FUNCTION_REGISTRY",
    # Public API
    "get_function_definitions",
    "get_function_metadata",
    "get_safety_level",
    "get_function_categories",
    "get_functions_by_category",
    "get_function_names",
    "get_function_count_by_safety",
]

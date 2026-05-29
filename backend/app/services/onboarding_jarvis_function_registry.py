"""
PARWA Onboarding Jarvis Function Registry — LLM Function Calling Definitions

The complete registry of everything Onboarding Jarvis can DO during the
PRE-PURCHASE demo experience. Each function is defined as an LLM tool spec
(OpenAI-compatible function calling format) with:
  - name, description, parameters (JSON Schema)
  - safety_level: none / confirmation_required / approval_required
  - category: grouping for organization
  - demo_stage: which conversation stage this function is relevant for

This is what gets passed to the LLM as "tools" for function calling.
Clients NEVER see this — they just talk naturally and Jarvis figures out
which function to call.

The Onboarding Jarvis plays THREE roles:
  - GUIDE:  Walks the user through features, selects industry/variants
  - SALESMAN: Demonstrates ROI, handles objections, pitches pricing
  - DEMO:   Roleplays as the actual AI agent for their industry

Clients arrive from variant pages (e.g. E-commerce Returns Agent,
SaaS Billing Agent) and click "Demo Chat" — Jarvis needs to know
WHICH variant they came from and whether it's chat or call.

Safety Levels:
  - none: Just do it immediately (e.g., show pricing, search knowledge)
  - confirmation_required: Ask "are you sure?" before executing
    (e.g., book demo call, select variants)
  - approval_required: Require explicit "confirm" — for monetary,
    destructive, or irreversible actions (e.g., create payment session,
    purchase demo pack)

Demo Stages (conversation flow):
  welcome     → Initial greeting, detect industry
  discovery   → Understand needs, show relevant variants
  demo        → Run demo scenarios, show the AI in action
  pricing     → Show plans, ROI, handle objections
  bill_review → Review selected variants and total cost
  verification → OTP / email verification
  payment     → Paddle checkout, demo pack purchase
  handoff     → Transition to post-onboarding customer care Jarvis

Channel Types:
  - chat: Text-based demo chat (from "Demo Chat" button on variant pages)
  - call: Voice-based demo call ($1 for 3 min)

Architecture:
  User clicks "Demo Chat" on variant page
      → Onboarding session created with variant context
      → Onboarding Router picks specialist agent (guide/salesman/demo/call)
      → Agent receives relevant function definitions for stage + channel
      → LLM picks function + generates conversational response
      → Safety gate checks before execution
      → Execute function call against backend API
      → Feed result back to LLM for final human-like response

After payment, Jarvis asks "what question would I ask you?" then creates
a ticket and solves it — demonstrating the real production workflow.

BC-001: session_id enforced at execution layer, not registry layer.
BC-008: Registry never crashes — all definitions are static.
BC-012: All timestamps UTC.
"""

from typing import Any, Dict, List, Optional, Set

from app.logger import get_logger

logger = get_logger("onboarding_jarvis_function_registry")


# ══════════════════════════════════════════════════════════════════
# SAFETY LEVELS
# ══════════════════════════════════════════════════════════════════

SAFETY_NONE = "none"
SAFETY_CONFIRMATION = "confirmation_required"
SAFETY_APPROVAL = "approval_required"


# ══════════════════════════════════════════════════════════════════
# CATEGORIES
# ══════════════════════════════════════════════════════════════════

CATEGORY_DEMO = "demo"                  # Demo mode functions
CATEGORY_SALES = "sales"                # Sales pitch functions
CATEGORY_GUIDE = "guide"                # Navigation/guidance functions
CATEGORY_COMMUNICATION = "communication"  # Chat/call channel functions
CATEGORY_KNOWLEDGE = "knowledge"        # Knowledge base functions
CATEGORY_VERIFICATION = "verification"  # OTP and email verification
CATEGORY_PAYMENT = "payment"            # Demo pack purchase, Paddle checkout


# ══════════════════════════════════════════════════════════════════
# DEMO STAGES
# ══════════════════════════════════════════════════════════════════

STAGE_WELCOME = "welcome"
STAGE_DISCOVERY = "discovery"
STAGE_DEMO = "demo"
STAGE_PRICING = "pricing"
STAGE_BILL_REVIEW = "bill_review"
STAGE_VERIFICATION = "verification"
STAGE_PAYMENT = "payment"
STAGE_HANDOFF = "handoff"

ALL_STAGES = [
    STAGE_WELCOME,
    STAGE_DISCOVERY,
    STAGE_DEMO,
    STAGE_PRICING,
    STAGE_BILL_REVIEW,
    STAGE_VERIFICATION,
    STAGE_PAYMENT,
    STAGE_HANDOFF,
]


# ══════════════════════════════════════════════════════════════════
# CHANNEL TYPES
# ══════════════════════════════════════════════════════════════════

CHANNEL_CHAT = "chat"
CHANNEL_CALL = "call"
CHANNEL_ALL = "all"  # Available on both channels


# ══════════════════════════════════════════════════════════════════
# FUNCTION DEFINITIONS
# ══════════════════════════════════════════════════════════════════

ONBOARDING_FUNCTION_REGISTRY: List[Dict[str, Any]] = [
    # ────────────────────────────────────────────────────────────
    # DEMO — Show Jarvis in action
    # ────────────────────────────────────────────────────────────
    {
        "name": "demo_variant_scenario",
        "description": (
            "Run a demo scenario for a specific variant. Jarvis roleplays "
            "as the AI agent for that variant — for example, processing a "
            "refund for the Returns Agent, or handling a billing inquiry "
            "for the SaaS Billing Agent. Use when the user wants to see "
            "how the AI handles real customer interactions for their "
            "industry, says 'show me', 'demo', or wants to try it out."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "variant_id": {
                    "type": "string",
                    "description": "The variant to demo (e.g., 'returns_refund', 'billing_inquiry', 'shipping_tracking')",
                },
                "scenario_type": {
                    "type": "string",
                    "enum": ["refund_request", "order_status", "billing_question", "complaint", "general_inquiry"],
                    "description": "Type of customer scenario to simulate (default 'general_inquiry')",
                    "default": "general_inquiry",
                },
                "customer_message": {
                    "type": "string",
                    "description": "The simulated customer message that triggers the scenario",
                },
            },
            "required": ["variant_id"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_DEMO,
        "demo_stage": STAGE_DEMO,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "demo_customer_question",
        "description": (
            "Let the client ask any question their customer would ask, and "
            "Jarvis responds AS the AI agent for their selected variant. "
            "This is the 'try it yourself' function — the client types "
            "what their customer would say, and Jarvis demonstrates how "
            "the AI would respond in production. Use when the user wants "
            "to test the AI with their own question or scenario."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question the client's customer would ask",
                },
                "variant_id": {
                    "type": "string",
                    "description": "The variant to roleplay as (uses session default if not specified)",
                },
            },
            "required": ["question"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_DEMO,
        "demo_stage": STAGE_DEMO,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "show_variant_workflow",
        "description": (
            "Explain how a specific variant works step by step in human-like "
            "language. Shows the full workflow: customer message → AI "
            "understands intent → selects technique → takes action → responds. "
            "Use when the user asks 'how does it work', 'walk me through it', "
            "or wants to understand the process before seeing a demo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "variant_id": {
                    "type": "string",
                    "description": "The variant to explain",
                },
                "detail_level": {
                    "type": "string",
                    "enum": ["summary", "detailed", "technical"],
                    "description": "How much detail to include (default 'detailed')",
                    "default": "detailed",
                },
            },
            "required": ["variant_id"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_DEMO,
        "demo_stage": STAGE_DISCOVERY,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "explain_production_behavior",
        "description": (
            "Explain how Jarvis would work in production after the client "
            "signs up. Covers: 24/7 availability, response times, "
            "auto-resolution rates, escalation to humans, knowledge base "
            "usage, and multi-channel support. This is PITCH MODE — the "
            "explanation naturally sells the product. Use when the user "
            "asks 'what happens after I sign up', 'in production', or "
            "wants to understand the real-world value."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "enum": ["ecommerce", "saas", "logistics", "others"],
                    "description": "Industry context for the explanation (uses session default if not specified)",
                },
                "variant_id": {
                    "type": "string",
                    "description": "Specific variant to focus on (optional)",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_DEMO,
        "demo_stage": STAGE_PRICING,
        "channel": CHANNEL_ALL,
    },

    # ────────────────────────────────────────────────────────────
    # SALES — Demonstrate value, handle objections
    # ────────────────────────────────────────────────────────────
    {
        "name": "compare_with_competitor",
        "description": (
            "Compare PARWA with a specific competitor. Shows how PARWA "
            "differs in AI capabilities, pricing, response quality, and "
            "automation level. Use when the user mentions a competitor "
            "(Zendesk, Intercom, Freshdesk, etc.), asks 'how are you "
            "different', or is comparing options."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "competitor_name": {
                    "type": "string",
                    "description": "Competitor to compare against (e.g., 'Zendesk', 'Intercom', 'Freshdesk')",
                },
                "comparison_aspect": {
                    "type": "string",
                    "enum": ["all", "pricing", "ai_capabilities", "automation", "channels", "ease_of_use"],
                    "description": "What aspect to focus on (default 'all')",
                    "default": "all",
                },
            },
            "required": ["competitor_name"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_SALES,
        "demo_stage": STAGE_PRICING,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "show_roi_calculation",
        "description": (
            "Show ROI comparison — current support cost vs PARWA cost. "
            "Calculates based on the client's ticket volume, current "
            "agent costs, and selected PARWA plan. Use when the user "
            "asks about ROI, value, savings, 'is it worth it', or "
            "wants to see the business case."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "monthly_tickets": {
                    "type": "integer",
                    "description": "Estimated monthly ticket volume",
                },
                "current_cost_per_agent": {
                    "type": "number",
                    "description": "Current monthly cost per support agent (USD)",
                },
                "num_agents": {
                    "type": "integer",
                    "description": "Current number of support agents",
                },
                "industry": {
                    "type": "string",
                    "enum": ["ecommerce", "saas", "logistics", "others"],
                    "description": "Industry for benchmark data (uses session default if not specified)",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_SALES,
        "demo_stage": STAGE_PRICING,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "handle_objection",
        "description": (
            "Handle a specific sales objection with a natural, consultative "
            "response. Common objections: 'too expensive', 'we already use X', "
            "'AI can't handle our complexity', 'security concerns', 'not ready "
            "yet'. The response is empathetic, data-backed, and naturally "
            "redirects to value. Use when the user expresses doubt, "
            "hesitation, or pushback."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "objection_type": {
                    "type": "string",
                    "enum": [
                        "price", "competitor", "complexity", "security",
                        "trust", "timing", "need", "control", "other",
                    ],
                    "description": "The type of objection to handle",
                },
                "objection_detail": {
                    "type": "string",
                    "description": "The specific objection the user raised in their own words",
                },
            },
            "required": ["objection_type", "objection_detail"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_SALES,
        "demo_stage": STAGE_PRICING,
        "channel": CHANNEL_ALL,
    },

    # ────────────────────────────────────────────────────────────
    # GUIDE — Navigation, selection, onboarding flow
    # ────────────────────────────────────────────────────────────
    {
        "name": "select_industry",
        "description": (
            "Set the industry context for the onboarding session. This "
            "tailors the demo, variant recommendations, and pricing to "
            "the client's industry. Use when the user mentions their "
            "industry, or when Jarvis needs to ask what industry they're "
            "in to provide relevant recommendations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "enum": ["ecommerce", "saas", "logistics", "others"],
                    "description": "The client's industry",
                },
                "sub_industry": {
                    "type": "string",
                    "description": "More specific industry segment (e.g., 'fashion ecommerce', 'B2B SaaS')",
                },
            },
            "required": ["industry"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_GUIDE,
        "demo_stage": STAGE_WELCOME,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "select_variants",
        "description": (
            "Select specific AI variants the client is interested in. "
            "Each variant is a specialized AI agent (e.g., Returns & Refunds "
            "Agent, Billing Inquiry Agent, Shipping Tracker). The selected "
            "variants determine the demo scenarios and the bill. Use when "
            "the user picks variants, says which ones they want, or when "
            "Jarvis recommends variants based on their industry."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "variant_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of variant IDs to select",
                },
                "action": {
                    "type": "string",
                    "enum": ["add", "remove", "replace"],
                    "description": "How to apply the selection: add to existing, remove from existing, or replace all (default 'replace')",
                    "default": "replace",
                },
            },
            "required": ["variant_ids"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "category": CATEGORY_GUIDE,
        "demo_stage": STAGE_DISCOVERY,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "show_pricing",
        "description": (
            "Show pricing tiers and variant costs. Displays available "
            "plans (mini_parwa, parwa, parwa_high) with features, "
            "per-variant pricing, and volume discounts. Use when the "
            "user asks about pricing, plans, costs, or 'how much'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "plan_filter": {
                    "type": "string",
                    "enum": ["all", "mini_parwa", "parwa", "parwa_high"],
                    "description": "Which plan to show details for (default 'all')",
                    "default": "all",
                },
                "include_comparison": {
                    "type": "boolean",
                    "description": "Include side-by-side plan comparison table (default true)",
                    "default": True,
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_GUIDE,
        "demo_stage": STAGE_PRICING,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "show_bill_summary",
        "description": (
            "Show bill summary with the client's selected variants, "
            "quantities, per-variant pricing, and total monthly cost. "
            "This is the 'review your order' step before payment. Use "
            "when the user wants to see their total, review their "
            "selection, or is ready to proceed to payment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "include_setup_fee": {
                    "type": "boolean",
                    "description": "Include one-time setup fee in the summary (default true)",
                    "default": True,
                },
                "period": {
                    "type": "string",
                    "enum": ["monthly", "annual"],
                    "description": "Billing period to show (default 'monthly')",
                    "default": "monthly",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_GUIDE,
        "demo_stage": STAGE_BILL_REVIEW,
        "channel": CHANNEL_ALL,
    },

    # ────────────────────────────────────────────────────────────
    # COMMUNICATION — Chat/call channel functions
    # ────────────────────────────────────────────────────────────
    {
        "name": "book_demo_call",
        "description": (
            "Book a demo voice call with the client. The call costs $1 "
            "for 3 minutes and gives the client a live voice demo of "
            "how Jarvis handles customer calls. Use when the user wants "
            "to hear the AI in voice mode, asks for a call, or says "
            "'call me', 'talk on phone', 'voice demo'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "Phone number to call",
                },
                "preferred_time": {
                    "type": "string",
                    "description": "Preferred call time (ISO 8601 or 'now') (default 'now')",
                    "default": "now",
                },
                "variant_id": {
                    "type": "string",
                    "description": "Variant to demo during the call (uses session default if not specified)",
                },
            },
            "required": ["phone_number"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "category": CATEGORY_COMMUNICATION,
        "demo_stage": STAGE_DEMO,
        "channel": CHANNEL_CHAT,
    },
    {
        "name": "initiate_voice_demo",
        "description": (
            "Start the voice demo call immediately. This initiates a "
            "real-time voice call where Jarvis demonstrates how it "
            "handles customer inquiries over the phone. Use when the "
            "user is ready for the voice demo, has booked a call, or "
            "wants to start the call right now."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The demo call session ID (from book_demo_call)",
                },
                "scenario_type": {
                    "type": "string",
                    "enum": ["inbound", "outbound", "callback"],
                    "description": "Type of voice demo scenario (default 'inbound')",
                    "default": "inbound",
                },
            },
            "required": ["session_id"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "category": CATEGORY_COMMUNICATION,
        "demo_stage": STAGE_DEMO,
        "channel": CHANNEL_CALL,
    },
    {
        "name": "send_follow_up",
        "description": (
            "Send a follow-up message to the client after the demo. "
            "Can include a summary of what was discussed, pricing "
            "details, or next steps. Use when the user asks for "
            "a summary, wants details sent to their email, or the "
            "demo is wrapping up."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Email address to send the follow-up to",
                },
                "include_pricing": {
                    "type": "boolean",
                    "description": "Include pricing details in the follow-up (default true)",
                    "default": True,
                },
                "include_demo_recap": {
                    "type": "boolean",
                    "description": "Include a recap of the demo conversation (default true)",
                    "default": True,
                },
                "custom_message": {
                    "type": "string",
                    "description": "Custom message to include in the follow-up",
                },
            },
            "required": ["email"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "category": CATEGORY_COMMUNICATION,
        "demo_stage": STAGE_PRICING,
        "channel": CHANNEL_ALL,
    },

    # ────────────────────────────────────────────────────────────
    # VERIFICATION — OTP and email verification
    # ────────────────────────────────────────────────────────────
    {
        "name": "send_business_otp",
        "description": (
            "Send a one-time password (OTP) to the client's business "
            "email for verification. Required before payment to ensure "
            "the client is a real business. Use when the user provides "
            "their business email, or when the flow requires email "
            "verification before proceeding to payment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Business email address to send OTP to",
                },
            },
            "required": ["email"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_VERIFICATION,
        "demo_stage": STAGE_VERIFICATION,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "verify_business_otp",
        "description": (
            "Verify the OTP code sent to the client's business email. "
            "On success, the email is marked as verified and the client "
            "can proceed to payment. Use when the user provides the OTP "
            "code they received via email."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "The business email that the OTP was sent to",
                },
                "otp_code": {
                    "type": "string",
                    "description": "The OTP code to verify (typically 6 digits)",
                },
            },
            "required": ["email", "otp_code"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_VERIFICATION,
        "demo_stage": STAGE_VERIFICATION,
        "channel": CHANNEL_ALL,
    },

    # ────────────────────────────────────────────────────────────
    # PAYMENT — Demo pack, variant subscription, Paddle checkout
    # ────────────────────────────────────────────────────────────
    {
        "name": "purchase_demo_pack",
        "description": (
            "Purchase the $1 demo pack. This gives the client 500 "
            "messages + 1 demo call to fully test PARWA before "
            "committing. It's the low-risk entry point. Use when the "
            "user wants to try PARWA with real data, isn't ready for "
            "a full subscription, or wants to extend their demo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Email for the purchase receipt",
                },
                "variant_id": {
                    "type": "string",
                    "description": "Variant to include in the demo pack (optional)",
                },
            },
            "required": ["email"],
        },
        "safety_level": SAFETY_APPROVAL,
        "category": CATEGORY_PAYMENT,
        "demo_stage": STAGE_PAYMENT,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "create_payment_session",
        "description": (
            "Create a Paddle checkout session for a variant subscription. "
            "Returns a Paddle checkout URL where the client can complete "
            "payment. This is for the full subscription (not the $1 demo "
            "pack). Use when the user is ready to buy, wants to subscribe, "
            "or says 'checkout', 'pay', 'sign up'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "plan_id": {
                    "type": "string",
                    "enum": ["mini_parwa", "parwa", "parwa_high"],
                    "description": "The subscription plan to subscribe to",
                },
                "variant_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Variant IDs to include in the subscription",
                },
                "email": {
                    "type": "string",
                    "description": "Client's verified business email",
                },
                "billing_period": {
                    "type": "string",
                    "enum": ["monthly", "annual"],
                    "description": "Billing period (default 'monthly')",
                    "default": "monthly",
                },
            },
            "required": ["plan_id", "variant_ids", "email"],
        },
        "safety_level": SAFETY_APPROVAL,
        "category": CATEGORY_PAYMENT,
        "demo_stage": STAGE_PAYMENT,
        "channel": CHANNEL_ALL,
    },

    # ────────────────────────────────────────────────────────────
    # KNOWLEDGE — Product info, features, integrations
    # ────────────────────────────────────────────────────────────
    {
        "name": "search_product_knowledge",
        "description": (
            "Search the PARWA product knowledge base for information. "
            "Returns relevant articles, FAQs, and feature descriptions. "
            "Use when the user asks a specific question about PARWA "
            "capabilities, features, or how something works that isn't "
            "covered by the demo or guide functions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "category": {
                    "type": "string",
                    "enum": ["all", "features", "pricing", "security", "integrations", "faq"],
                    "description": "Knowledge category to search in (default 'all')",
                    "default": "all",
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
        "category": CATEGORY_KNOWLEDGE,
        "demo_stage": STAGE_DISCOVERY,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "explain_feature",
        "description": (
            "Explain a specific PARWA feature in human-friendly language. "
            "Goes beyond the marketing description — explains how it "
            "actually works, what it does for the client, and why it "
            "matters. Use when the user asks 'what is X', 'how does X "
            "work', or wants detail on a specific capability."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "feature_name": {
                    "type": "string",
                    "description": "The feature to explain (e.g., 'auto_resolve', 'variant_system', 'knowledge_base', 'brand_voice', 'sla_rules')",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context — what the user already knows or is interested in",
                },
            },
            "required": ["feature_name"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_KNOWLEDGE,
        "demo_stage": STAGE_DISCOVERY,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "show_integration_options",
        "description": (
            "Show available integrations for PARWA. Lists supported "
            "channels (email, SMS, chat widget, voice), third-party "
            "integrations (Shopify, Slack, Zapier, etc.), and data "
            "import options. Use when the user asks about integrations, "
            "connectors, or connecting PARWA to their existing tools."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["all", "channels", "crm", "ecommerce", "productivity", "custom"],
                    "description": "Integration category to show (default 'all')",
                    "default": "all",
                },
                "industry": {
                    "type": "string",
                    "enum": ["ecommerce", "saas", "logistics", "others"],
                    "description": "Industry filter — show most relevant integrations first (uses session default if not specified)",
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_KNOWLEDGE,
        "demo_stage": STAGE_DISCOVERY,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "upload_documents",
        "description": (
            "Handle client document upload for the knowledge base. "
            "Accepts files (PDF, DOCX, TXT, CSV) that the client wants "
            "the AI to learn from. Documents are processed and indexed "
            "for the demo. Use when the user wants to upload their docs, "
            "add their knowledge base, or says 'let me share my files'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "URLs of uploaded files to process",
                },
                "document_type": {
                    "type": "string",
                    "enum": ["faq", "policy", "product_catalog", "returns_policy", "shipping_info", "other"],
                    "description": "Type of documents being uploaded (default 'other')",
                    "default": "other",
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what these documents contain",
                },
            },
            "required": ["file_urls"],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "category": CATEGORY_KNOWLEDGE,
        "demo_stage": STAGE_DEMO,
        "channel": CHANNEL_ALL,
    },

    # ────────────────────────────────────────────────────────────
    # DEMO TICKET — "What question would I ask you?" flow
    # ────────────────────────────────────────────────────────────
    {
        "name": "create_demo_ticket",
        "description": (
            "Create a demo ticket for the 'what question would I ask you?' "
            "flow. After payment, Jarvis asks the client 'what question would "
            "your customers ask you?' — the client provides it, and Jarvis "
            "creates a ticket from it. This is the first demonstration of "
            "the real production workflow. Use after payment is confirmed "
            "and the client provides their customer question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question the client's customer would ask (provided by the client)",
                },
                "variant_id": {
                    "type": "string",
                    "description": "The variant to assign the ticket to",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Simulated customer name (optional, defaults to 'Demo Customer')",
                    "default": "Demo Customer",
                },
            },
            "required": ["question", "variant_id"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_DEMO,
        "demo_stage": STAGE_HANDOFF,
        "channel": CHANNEL_ALL,
    },
    {
        "name": "solve_demo_ticket",
        "description": (
            "Solve a demo ticket to show how Jarvis handles it in production. "
            "Jarvis processes the ticket: understands intent, finds the answer "
            "from the knowledge base, and provides a resolution. This is the "
            "climax of the onboarding — the AI proves it can do the job. Use "
            "after create_demo_ticket, when the client wants to see Jarvis "
            "solve the ticket."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The demo ticket ID to solve (from create_demo_ticket)",
                },
                "resolution_style": {
                    "type": "string",
                    "enum": ["full_auto", "assisted", "step_by_step"],
                    "description": "How to show the resolution: full auto (instant), assisted (with confirmations), or step-by-step walkthrough (default 'step_by_step')",
                    "default": "step_by_step",
                },
            },
            "required": ["ticket_id"],
        },
        "safety_level": SAFETY_NONE,
        "category": CATEGORY_DEMO,
        "demo_stage": STAGE_HANDOFF,
        "channel": CHANNEL_ALL,
    },

    # ────────────────────────────────────────────────────────────
    # HANDOFF — Transition to post-onboarding
    # ────────────────────────────────────────────────────────────
    {
        "name": "execute_handoff",
        "description": (
            "Transition from onboarding to customer care Jarvis. After "
            "the demo ticket is solved and the client is onboarded, "
            "this function hands off the session to the post-onboarding "
            "Jarvis (the admin CLI). The client's account is activated, "
            "their variants are provisioned, and they enter the normal "
            "PARWA experience. Use when onboarding is complete, payment "
            "is confirmed, and the client is ready to go live."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "The client's company name",
                },
                "activation_preferences": {
                    "type": "object",
                    "description": "Preferences for the initial setup: AI name, tone, greeting, etc.",
                    "properties": {
                        "ai_name": {
                            "type": "string",
                            "description": "Custom AI assistant name (default 'Jarvis')",
                        },
                        "ai_tone": {
                            "type": "string",
                            "enum": ["professional", "friendly", "casual"],
                            "description": "AI tone preference (default 'professional')",
                        },
                        "ai_greeting": {
                            "type": "string",
                            "description": "Custom greeting message for the AI",
                        },
                    },
                },
            },
            "required": [],
        },
        "safety_level": SAFETY_CONFIRMATION,
        "category": CATEGORY_GUIDE,
        "demo_stage": STAGE_HANDOFF,
        "channel": CHANNEL_ALL,
    },
]


# ══════════════════════════════════════════════════════════════════
# LOOKUP INDEX (built once at import time)
# ══════════════════════════════════════════════════════════════════

_FUNCTION_BY_NAME: Dict[str, Dict[str, Any]] = {
    f["name"]: f for f in ONBOARDING_FUNCTION_REGISTRY
}


# ══════════════════════════════════════════════════════════════════
# STAGE → FUNCTION MAPPING (for fast lookup)
# ══════════════════════════════════════════════════════════════════

_STAGE_FUNCTIONS: Dict[str, List[str]] = {}
for _func in ONBOARDING_FUNCTION_REGISTRY:
    _stage = _func.get("demo_stage", STAGE_WELCOME)
    if _stage not in _STAGE_FUNCTIONS:
        _STAGE_FUNCTIONS[_stage] = []
    _STAGE_FUNCTIONS[_stage].append(_func["name"])

# Some functions are useful across multiple stages — add cross-stage
# functions that should be available even outside their primary stage
_CROSS_STAGE_FUNCTIONS: Dict[str, Set[str]] = {
    # search_product_knowledge is useful in every stage
    STAGE_WELCOME: {"search_product_knowledge"},
    STAGE_DISCOVERY: {"search_product_knowledge"},
    STAGE_DEMO: {"search_product_knowledge"},
    STAGE_PRICING: {"search_product_knowledge", "show_pricing"},
    STAGE_BILL_REVIEW: {"search_product_knowledge", "show_pricing", "show_bill_summary"},
    STAGE_VERIFICATION: {"search_product_knowledge"},
    STAGE_PAYMENT: {"search_product_knowledge", "show_bill_summary"},
    STAGE_HANDOFF: {"search_product_knowledge"},
}


# ══════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════


def get_onboarding_function_definitions(
    demo_stage: str = STAGE_WELCOME,
    channel_type: str = CHANNEL_CHAT,
) -> List[Dict[str, Any]]:
    """Get LLM function definitions for the onboarding phase.

    Returns functions relevant to the current demo stage and channel type.
    This is what gets passed to the LLM as "tools" for function calling
    during the onboarding conversation.

    Stage-based filtering:
      - Each function has a primary demo_stage where it's most relevant
      - Cross-stage functions (like search_product_knowledge) are always
        available
      - The current stage + one stage ahead are included for smooth flow

    Channel filtering:
      - "chat": Functions available in text-based demo chat
      - "call": Functions available in voice demo call
      - "all": Functions available on both channels

    Args:
        demo_stage: Current onboarding stage (welcome, discovery, demo,
                    pricing, bill_review, verification, payment, handoff).
        channel_type: "chat" or "call".

    Returns:
        List of function definitions in OpenAI tool-calling format.
    """
    try:
        # Validate stage
        valid_stages = set(ALL_STAGES)
        if demo_stage not in valid_stages:
            logger.warning(
                "invalid_demo_stage: %s, defaulting to welcome", demo_stage,
            )
            demo_stage = STAGE_WELCOME

        # Validate channel
        valid_channels = {CHANNEL_CHAT, CHANNEL_CALL}
        if channel_type not in valid_channels:
            logger.warning(
                "invalid_channel_type: %s, defaulting to chat", channel_type,
            )
            channel_type = CHANNEL_CHAT

        # Determine which stages to include (current + next for flow)
        stage_index = ALL_STAGES.index(demo_stage)
        active_stages = {demo_stage}
        # Include the next stage's functions too for proactive suggestions
        if stage_index < len(ALL_STAGES) - 1:
            active_stages.add(ALL_STAGES[stage_index + 1])

        # Collect function names for active stages
        eligible_names: Set[str] = set()
        for stage in active_stages:
            eligible_names.update(_STAGE_FUNCTIONS.get(stage, []))
            eligible_names.update(_CROSS_STAGE_FUNCTIONS.get(stage, set()))

        # Build tool definitions
        definitions = []
        for func_def in ONBOARDING_FUNCTION_REGISTRY:
            func_name = func_def["name"]

            # ── Stage filter ──
            if func_name not in eligible_names:
                continue

            # ── Channel filter ──
            func_channel = func_def.get("channel", CHANNEL_ALL)
            if func_channel != CHANNEL_ALL and func_channel != channel_type:
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
            "onboarding_function_registry: stage=%s, channel=%s, count=%d",
            demo_stage, channel_type, len(definitions),
        )

        return definitions

    except Exception:
        logger.exception("get_onboarding_function_definitions_error")
        return []


def get_function_metadata(function_name: str) -> Optional[Dict[str, Any]]:
    """Get the full metadata for an onboarding function by name.

    Includes safety_level, category, demo_stage, and channel — these are
    NOT passed to the LLM but are used internally by the safety gate
    and orchestrator.

    Args:
        function_name: The function name to look up.

    Returns:
        Full function definition dict, or None if not found.
    """
    return _FUNCTION_BY_NAME.get(function_name)


def get_safety_level(function_name: str) -> str:
    """Get the safety level for an onboarding function by name.

    Args:
        function_name: The function name to look up.

    Returns:
        Safety level string: "none", "confirmation_required", or
        "approval_required". Defaults to "confirmation_required"
        if function not found (fail-safe).
    """
    metadata = get_function_metadata(function_name)
    if metadata:
        return metadata.get("safety_level", SAFETY_CONFIRMATION)
    # Fail-safe: if we don't know the function, require confirmation
    logger.warning("unknown_onboarding_function_safety_default: function=%s", function_name)
    return SAFETY_CONFIRMATION


def filter_functions_by_channel(
    functions: List[Dict[str, Any]],
    channel: str,
) -> List[Dict[str, Any]]:
    """Filter a list of function definitions by channel availability.

    Useful when you have a pre-selected list of functions and need to
    remove ones that aren't available on the current channel.

    Args:
        functions: List of function definition dicts (from the registry).
        channel: "chat" or "call".

    Returns:
        Filtered list of function definitions.
    """
    try:
        filtered = []
        for func_def in functions:
            func_channel = func_def.get("channel", CHANNEL_ALL)
            if func_channel == CHANNEL_ALL or func_channel == channel:
                filtered.append(func_def)
        return filtered
    except Exception:
        logger.exception("filter_functions_by_channel_error")
        return functions


def get_function_categories() -> List[str]:
    """Get all available onboarding function categories."""
    return list(set(f["category"] for f in ONBOARDING_FUNCTION_REGISTRY))


def get_functions_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all onboarding function definitions in a category."""
    return [f for f in ONBOARDING_FUNCTION_REGISTRY if f["category"] == category]


def get_functions_by_stage(demo_stage: str) -> List[Dict[str, Any]]:
    """Get all onboarding function definitions for a demo stage."""
    return [
        f for f in ONBOARDING_FUNCTION_REGISTRY
        if f.get("demo_stage") == demo_stage
    ]


def get_function_names(
    demo_stage: str = STAGE_WELCOME,
    channel_type: str = CHANNEL_CHAT,
) -> List[str]:
    """Get just the function names available for a stage and channel.

    Useful for logging and debugging.
    """
    defs = get_onboarding_function_definitions(
        demo_stage=demo_stage,
        channel_type=channel_type,
    )
    return [d["function"]["name"] for d in defs]


def get_function_count_by_category() -> Dict[str, int]:
    """Get count of functions by category. Useful for docs/debugging."""
    counts: Dict[str, int] = {}
    for func_def in ONBOARDING_FUNCTION_REGISTRY:
        cat = func_def.get("category", "unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def get_function_count_by_safety() -> Dict[str, int]:
    """Get count of functions by safety level. Useful for docs/debugging."""
    counts: Dict[str, int] = {}
    for func_def in ONBOARDING_FUNCTION_REGISTRY:
        level = func_def.get("safety_level", "none")
        counts[level] = counts.get(level, 0) + 1
    return counts


def get_function_count_by_stage() -> Dict[str, int]:
    """Get count of functions by demo stage. Useful for docs/debugging."""
    counts: Dict[str, int] = {}
    for func_def in ONBOARDING_FUNCTION_REGISTRY:
        stage = func_def.get("demo_stage", "welcome")
        counts[stage] = counts.get(stage, 0) + 1
    return counts


__all__ = [
    # Constants — Safety Levels
    "SAFETY_NONE",
    "SAFETY_CONFIRMATION",
    "SAFETY_APPROVAL",
    # Constants — Categories
    "CATEGORY_DEMO",
    "CATEGORY_SALES",
    "CATEGORY_GUIDE",
    "CATEGORY_COMMUNICATION",
    "CATEGORY_KNOWLEDGE",
    "CATEGORY_VERIFICATION",
    "CATEGORY_PAYMENT",
    # Constants — Demo Stages
    "STAGE_WELCOME",
    "STAGE_DISCOVERY",
    "STAGE_DEMO",
    "STAGE_PRICING",
    "STAGE_BILL_REVIEW",
    "STAGE_VERIFICATION",
    "STAGE_PAYMENT",
    "STAGE_HANDOFF",
    "ALL_STAGES",
    # Constants — Channel Types
    "CHANNEL_CHAT",
    "CHANNEL_CALL",
    "CHANNEL_ALL",
    # Registry
    "ONBOARDING_FUNCTION_REGISTRY",
    # Public API
    "get_onboarding_function_definitions",
    "get_function_metadata",
    "get_safety_level",
    "filter_functions_by_channel",
    "get_function_categories",
    "get_functions_by_category",
    "get_functions_by_stage",
    "get_function_names",
    "get_function_count_by_category",
    "get_function_count_by_safety",
    "get_function_count_by_stage",
]

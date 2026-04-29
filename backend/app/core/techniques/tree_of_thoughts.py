"""
F-145: Tree of Thoughts (ToT) — Tier 3 Premium AI Reasoning Technique

Branching decision tree with systematic pruning and multi-path
exploration. Activates when a query has 3+ possible resolution paths
or requires branching decision analysis. Uses deterministic heuristic-based
tree search (no LLM calls) to:

  1. Tree Generation    — build reasoning tree from query signals
  2. Branch Evaluation  — score each branch for viability
  3. Pruning            — remove suboptimal branches below threshold
  4. Search             — BFS/DFS/best-first through remaining tree
  5. Path Selection     — choose best path from explored branches
  6. Reasoning Trace    — step-by-step trace of selected resolution path

Performance target: ~1150 tokens, sub-200ms processing.

Building Codes: BC-001 (company isolation), BC-008 (never crash),
               BC-012 (graceful degradation)
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

from app.core.technique_router import TechniqueID
from app.core.techniques.base import (
    BaseTechniqueNode,
    ConversationState,
)
from app.logger import get_logger

logger = get_logger("tree_of_thoughts")


# ── Enums ──────────────────────────────────────────────────────────


class BranchStatus(str, Enum):
    """Status of a branch in the reasoning tree."""

    ACTIVE = "active"
    PRUNED = "pruned"
    DEAD_END = "dead_end"
    SELECTED = "selected"
    EXPLORED = "explored"


class SearchStrategy(str, Enum):
    """Strategy for traversing the reasoning tree."""

    BFS = "bfs"
    DFS = "dfs"
    BEST_FIRST = "best_first"


class ProblemDomain(str, Enum):
    """Problem domains for tree template selection."""

    TECHNICAL = "technical"
    BILLING = "billing"
    INTEGRATION = "integration"
    ESCALATION = "escalation"
    GENERAL = "general"


# ── Tree Node ──────────────────────────────────────────────────────


@dataclass
class TreeNode:
    """
    A single node in the reasoning tree.

    Attributes:
        id: Unique identifier within the tree.
        label: Short human-readable label for display.
        content: Detailed description of this reasoning step.
        status: Current status of this branch.
        score: Viability score (0.0–1.0); higher is better.
        depth: Depth level in the tree (root = 0).
        parent_id: ID of the parent node, or None for root.
        children: Ordered list of child node IDs.
        metadata: Optional key-value pairs for extra context.
    """

    id: str = ""
    label: str = ""
    content: str = ""
    status: BranchStatus = BranchStatus.ACTIVE
    score: float = 0.5
    depth: int = 0
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize node to dictionary."""
        return {
            "id": self.id,
            "label": self.label,
            "content": self.content,
            "status": self.status.value,
            "score": round(self.score, 4),
            "depth": self.depth,
            "parent_id": self.parent_id,
            "children": list(self.children),
            "metadata": dict(self.metadata),
        }


# ── Domain Classification Patterns ────────────────────────────────
#
# Used to classify the query into a ProblemDomain so that
# the appropriate tree templates are selected.


_DOMAIN_PATTERNS: List[Tuple[re.Pattern, ProblemDomain]] = [
    # ── TECHNICAL ────────────────────────────────────────────────
    (
        re.compile(
            r"\b(error|bug|crash|timeout|500|502|503|404|403|"
            r"server|deploy|deployment|api|endpoint|ssl|certificate|"
            r"database|migration|docker|kubernetes|log|stack.?trace|"
            r"latency|performance|memory|cpu|down|outage|broken)\b",
            re.I,
        ),
        ProblemDomain.TECHNICAL,
    ),
    # ── BILLING ──────────────────────────────────────────────────
    (
        re.compile(
            r"\b(charge|invoice|billing|payment|refund|credit|"
            r"subscription|plan|proration|tax|receipt|transaction|"
            r"overcharge|duplicate|discount|coupon|trial|upgrade|"
            r"downgrade|cancel.?subscription|payment.?method|card)\b",
            re.I,
        ),
        ProblemDomain.BILLING,
    ),
    # ── INTEGRATION ──────────────────────────────────────────────
    (
        re.compile(
            r"\b(integrate|integration|webhook|oauth|sso|saml|"
            r"zapier|slack|salesforce|hubspot|api.?key|connect|"
            r"third.?party|plugin|extension|import|export|sync|"
            r"authentication|token|callback|middleware)\b",
            re.I,
        ),
        ProblemDomain.INTEGRATION,
    ),
    # ── ESCALATION ───────────────────────────────────────────────
    (
        re.compile(
            r"\b(escalat|manager|supervisor|complaint|urgent|"
            r"critical|legal|lawsuit|lawyer|attorney|regulatory|"
            r"compliance|fraud|security.?breach|data.?breach|"
            r"data.?leak|breach|government|sla|"
            r"priority.?support|vip.?request)\b",
            re.I,
        ),
        ProblemDomain.ESCALATION,
    ),
]


# ── Tree Templates ─────────────────────────────────────────────────
#
# Each domain has 2-3 tree templates. A template is a dict with:
#   root_label:    Label for the root node.
#   root_content:  Description of the root problem.
#   branches:      List of branch definitions, each with:
#     label:       Branch label.
#     content:     Branch description.
#     score:       Initial viability score.
#     steps:       List of child steps under this branch.
#
# Template keys are (domain, template_index) tuples.


_TREE_TEMPLATES: Dict[
    ProblemDomain,
    List[Dict[str, Any]],
] = {
    # ═══════════════════════════════════════════════════════════════
    # TECHNICAL DOMAIN
    # ═══════════════════════════════════════════════════════════════
    ProblemDomain.TECHNICAL: [
        # Template 1: API Error Investigation
        {
            "name": "api_error_investigation",
            "root_label": "API Error Investigation",
            "root_content": (
                "Customer reports API errors. Systematic investigation "
                "of server, client, and network layers."
            ),
            "branches": [
                {
                    "label": "Server-Side Issue",
                    "content": (
                        "Check if the server is returning errors due to "
                        "backend problems, deployments, or resource limits."
                    ),
                    "score": 0.75,
                    "steps": [
                        {
                            "label": "Check Server Health",
                            "content": (
                                "Verify server status, uptime, and "
                                "health check endpoints."
                            ),
                            "score": 0.30,
                            "action": "prune",
                        },
                        {
                            "label": "Review Recent Deploy",
                            "content": (
                                "Check for recent deployments that may "
                                "have introduced regressions."
                            ),
                            "score": 0.85,
                            "steps": [
                                {
                                    "label": "Rollback Deploy",
                                    "content": (
                                        "Initiate rollback to the last "
                                        "known stable version."
                                    ),
                                    "score": 0.90,
                                },
                                {
                                    "label": "Hotfix Patch",
                                    "content": (
                                        "Apply targeted hotfix to the "
                                        "deployed version."
                                    ),
                                    "score": 0.70,
                                },
                            ],
                        },
                    ],
                },
                {
                    "label": "Client-Side Issue",
                    "content": (
                        "Check if the client is sending malformed "
                        "requests, using outdated SDKs, or has "
                        "authentication problems."
                    ),
                    "score": 0.65,
                    "steps": [
                        {
                            "label": "Validate Request Format",
                            "content": (
                                "Ensure the request body, headers, and "
                                "parameters match the API specification."
                            ),
                            "score": 0.35,
                            "action": "prune",
                        },
                        {
                            "label": "Check Auth Token",
                            "content": (
                                "Verify the authentication token is "
                                "valid, not expired, and properly scoped."
                            ),
                            "score": 0.80,
                            "steps": [
                                {
                                    "label": "Renew Token",
                                    "content": (
                                        "Guide the customer through "
                                        "token renewal process."
                                    ),
                                    "score": 0.88,
                                },
                                {
                                    "label": "Re-authorize App",
                                    "content": (
                                        "Re-authorize the application "
                                        "to obtain new credentials."
                                    ),
                                    "score": 0.72,
                                },
                            ],
                        },
                    ],
                },
                {
                    "label": "Network / Infrastructure",
                    "content": (
                        "Check for network-level issues including "
                        "rate limiting, DNS problems, or firewall rules."
                    ),
                    "score": 0.55,
                    "steps": [
                        {
                            "label": "Check Rate Limits",
                            "content": (
                                "Verify if the customer has exceeded "
                                "API rate limits."
                            ),
                            "score": 0.82,
                            "steps": [
                                {
                                    "label": "Increase Limit",
                                    "content": (
                                        "Upgrade the rate limit tier or "
                                        "apply for a limit increase."
                                    ),
                                    "score": 0.85,
                                },
                                {
                                    "label": "Optimize Calls",
                                    "content": (
                                        "Recommend batching or caching "
                                        "strategies to reduce call volume."
                                    ),
                                    "score": 0.68,
                                },
                            ],
                        },
                        {
                            "label": "DNS / Firewall Check",
                            "content": (
                                "Verify DNS resolution and firewall "
                                "rules are not blocking requests."
                            ),
                            "score": 0.45,
                            "action": "prune",
                        },
                    ],
                },
            ],
        },
        # Template 2: Service Outage Diagnosis
        {
            "name": "service_outage_diagnosis",
            "root_label": "Service Outage Diagnosis",
            "root_content": (
                "Customer reports a service outage or degraded "
                "performance. Investigate infrastructure layers."
            ),
            "branches": [
                {
                    "label": "Infrastructure Layer",
                    "content": (
                        "Check compute, storage, and network " "infrastructure health."
                    ),
                    "score": 0.80,
                    "steps": [
                        {
                            "label": "Check Status Page",
                            "content": (
                                "Review the system status page for " "known incidents."
                            ),
                            "score": 0.88,
                            "steps": [
                                {
                                    "label": "Subscribe to Updates",
                                    "content": (
                                        "Ensure the customer is subscribed "
                                        "to incident notifications."
                                    ),
                                    "score": 0.75,
                                },
                            ],
                        },
                        {
                            "label": "Review Auto-scaling",
                            "content": (
                                "Check if auto-scaling failed to "
                                "handle traffic spikes."
                            ),
                            "score": 0.70,
                        },
                    ],
                },
                {
                    "label": "Application Layer",
                    "content": (
                        "Check application code, configurations, " "and feature flags."
                    ),
                    "score": 0.70,
                    "steps": [
                        {
                            "label": "Check Feature Flags",
                            "content": (
                                "Verify no feature flag accidentally "
                                "disabled critical functionality."
                            ),
                            "score": 0.83,
                        },
                        {
                            "label": "Review Error Logs",
                            "content": (
                                "Examine application error logs for "
                                "recent unhandled exceptions."
                            ),
                            "score": 0.78,
                            "steps": [
                                {
                                    "label": "Apply Fix",
                                    "content": (
                                        "Deploy a fix for the identified "
                                        "error condition."
                                    ),
                                    "score": 0.90,
                                },
                                {
                                    "label": "Workaround",
                                    "content": (
                                        "Provide a temporary workaround "
                                        "until a fix is deployed."
                                    ),
                                    "score": 0.65,
                                },
                            ],
                        },
                    ],
                },
                {
                    "label": "Third-Party Dependency",
                    "content": (
                        "Check if an external service or API "
                        "dependency is experiencing issues."
                    ),
                    "score": 0.60,
                    "steps": [
                        {
                            "label": "Check Dependency Status",
                            "content": (
                                "Review external service health " "dashboards."
                            ),
                            "score": 0.85,
                            "steps": [
                                {
                                    "label": "Enable Fallback",
                                    "content": (
                                        "Activate fallback mechanism "
                                        "for the affected dependency."
                                    ),
                                    "score": 0.82,
                                },
                            ],
                        },
                        {
                            "label": "Check API Quotas",
                            "content": (
                                "Verify third-party API quotas have "
                                "not been exhausted."
                            ),
                            "score": 0.72,
                        },
                    ],
                },
                {
                    "label": "Data Layer",
                    "content": (
                        "Check database health, connection pools, "
                        "and query performance."
                    ),
                    "score": 0.65,
                    "steps": [
                        {
                            "label": "Check DB Connections",
                            "content": (
                                "Verify database connection pool " "is not exhausted."
                            ),
                            "score": 0.80,
                            "steps": [
                                {
                                    "label": "Increase Pool Size",
                                    "content": (
                                        "Scale up the database " "connection pool."
                                    ),
                                    "score": 0.78,
                                },
                            ],
                        },
                        {
                            "label": "Check Query Performance",
                            "content": (
                                "Identify slow queries that may be " "causing timeouts."
                            ),
                            "score": 0.75,
                            "action": "prune",
                        },
                    ],
                },
            ],
        },
    ],
    # ═══════════════════════════════════════════════════════════════
    # BILLING DOMAIN
    # ═══════════════════════════════════════════════════════════════
    ProblemDomain.BILLING: [
        # Template 1: Unexpected Charge Investigation
        {
            "name": "unexpected_charge_investigation",
            "root_label": "Unexpected Charge Investigation",
            "root_content": (
                "Customer disputes an unexpected charge on their "
                "account. Systematic review of billing history."
            ),
            "branches": [
                {
                    "label": "Legitimate Charge",
                    "content": (
                        "Verify if the charge corresponds to an "
                        "actual service usage or plan change."
                    ),
                    "score": 0.80,
                    "steps": [
                        {
                            "label": "Check Usage Records",
                            "content": (
                                "Review detailed usage logs to "
                                "confirm the charge is valid."
                            ),
                            "score": 0.85,
                            "steps": [
                                {
                                    "label": "Explain Charge",
                                    "content": (
                                        "Provide itemized breakdown "
                                        "of the charge to the customer."
                                    ),
                                    "score": 0.90,
                                },
                            ],
                        },
                        {
                            "label": "Check Plan Upgrade",
                            "content": (
                                "Verify if a plan upgrade triggered "
                                "the additional charge."
                            ),
                            "score": 0.78,
                        },
                    ],
                },
                {
                    "label": "Billing Error",
                    "content": (
                        "Check for duplicate charges, incorrect "
                        "tax calculations, or proration errors."
                    ),
                    "score": 0.70,
                    "steps": [
                        {
                            "label": "Check for Duplicates",
                            "content": (
                                "Scan for duplicate invoice entries "
                                "or double-billing events."
                            ),
                            "score": 0.82,
                            "steps": [
                                {
                                    "label": "Issue Refund",
                                    "content": (
                                        "Process a refund for the " "duplicate charge."
                                    ),
                                    "score": 0.92,
                                },
                            ],
                        },
                        {
                            "label": "Check Tax Calculation",
                            "content": (
                                "Verify tax rates and regional "
                                "calculations are correct."
                            ),
                            "score": 0.60,
                            "action": "prune",
                        },
                    ],
                },
                {
                    "label": "Free Trial / Cancellation Issue",
                    "content": (
                        "Check if the customer was charged after "
                        "a free trial or after cancellation."
                    ),
                    "score": 0.65,
                    "steps": [
                        {
                            "label": "Check Trial End Date",
                            "content": (
                                "Verify when the free trial ended "
                                "and when the first charge applied."
                            ),
                            "score": 0.80,
                            "steps": [
                                {
                                    "label": "Waive Charge",
                                    "content": (
                                        "Waive the first charge as a "
                                        "courtesy if the trial end was "
                                        "not clearly communicated."
                                    ),
                                    "score": 0.88,
                                },
                            ],
                        },
                        {
                            "label": "Check Cancellation Status",
                            "content": (
                                "Verify if the cancellation was "
                                "processed before billing cycle end."
                            ),
                            "score": 0.75,
                        },
                    ],
                },
            ],
        },
        # Template 2: Subscription Plan Change
        {
            "name": "subscription_plan_change",
            "root_label": "Subscription Plan Change",
            "root_content": (
                "Customer wants to change, upgrade, or downgrade "
                "their subscription plan."
            ),
            "branches": [
                {
                    "label": "Upgrade Request",
                    "content": (
                        "Process a plan upgrade with prorated " "billing adjustment."
                    ),
                    "score": 0.85,
                    "steps": [
                        {
                            "label": "Calculate Proration",
                            "content": (
                                "Compute prorated charges for the "
                                "remaining billing period."
                            ),
                            "score": 0.88,
                            "steps": [
                                {
                                    "label": "Apply Upgrade",
                                    "content": (
                                        "Execute the plan upgrade and "
                                        "confirm new features."
                                    ),
                                    "score": 0.92,
                                },
                            ],
                        },
                        {
                            "label": "Feature Comparison",
                            "content": (
                                "Provide feature comparison between "
                                "current and target plan."
                            ),
                            "score": 0.80,
                        },
                    ],
                },
                {
                    "label": "Downgrade Request",
                    "content": (
                        "Process a plan downgrade with feature " "limitation warnings."
                    ),
                    "score": 0.75,
                    "steps": [
                        {
                            "label": "Check Data Limits",
                            "content": (
                                "Warn about data or feature limits "
                                "on the lower plan."
                            ),
                            "score": 0.82,
                            "steps": [
                                {
                                    "label": "Data Export",
                                    "content": (
                                        "Offer data export before "
                                        "downgrade takes effect."
                                    ),
                                    "score": 0.78,
                                },
                            ],
                        },
                        {
                            "label": "Apply Downgrade",
                            "content": (
                                "Process the downgrade at end of "
                                "current billing cycle."
                            ),
                            "score": 0.76,
                        },
                    ],
                },
                {
                    "label": "Cancellation Flow",
                    "content": (
                        "Handle subscription cancellation with " "retention offers."
                    ),
                    "score": 0.60,
                    "steps": [
                        {
                            "label": "Identify Reason",
                            "content": (
                                "Understand why the customer wants " "to cancel."
                            ),
                            "score": 0.72,
                            "steps": [
                                {
                                    "label": "Retention Offer",
                                    "content": (
                                        "Present a discount or feature "
                                        "adjustment to retain customer."
                                    ),
                                    "score": 0.80,
                                },
                            ],
                        },
                        {
                            "label": "Process Cancellation",
                            "content": (
                                "Complete the cancellation and "
                                "confirm access timeline."
                            ),
                            "score": 0.55,
                            "action": "prune",
                        },
                    ],
                },
            ],
        },
        # Template 3: Payment Failure Resolution
        {
            "name": "payment_failure_resolution",
            "root_label": "Payment Failure Resolution",
            "root_content": (
                "Customer's payment method failed. Resolve the "
                "payment issue to restore service."
            ),
            "branches": [
                {
                    "label": "Card-Related Issue",
                    "content": ("The payment card was declined or expired."),
                    "score": 0.80,
                    "steps": [
                        {
                            "label": "Check Card Expiry",
                            "content": (
                                "Verify the card expiration date "
                                "matches what is on file."
                            ),
                            "score": 0.85,
                            "steps": [
                                {
                                    "label": "Update Card",
                                    "content": (
                                        "Guide the customer to update "
                                        "their card information."
                                    ),
                                    "score": 0.90,
                                },
                            ],
                        },
                        {
                            "label": "Check Card Balance",
                            "content": (
                                "Suggest the customer verify "
                                "sufficient funds are available."
                            ),
                            "score": 0.70,
                            "action": "prune",
                        },
                    ],
                },
                {
                    "label": "Bank / Processor Issue",
                    "content": (
                        "The bank or payment processor rejected " "the transaction."
                    ),
                    "score": 0.65,
                    "steps": [
                        {
                            "label": "Retry Transaction",
                            "content": ("Attempt to reprocess the payment."),
                            "score": 0.78,
                            "steps": [
                                {
                                    "label": "Alternate Payment",
                                    "content": (
                                        "Suggest using an alternative "
                                        "payment method."
                                    ),
                                    "score": 0.82,
                                },
                            ],
                        },
                        {
                            "label": "Contact Bank",
                            "content": (
                                "Recommend the customer contact "
                                "their bank to authorise the charge."
                            ),
                            "score": 0.68,
                        },
                    ],
                },
                {
                    "label": "Invoice / Billing Issue",
                    "content": (
                        "There is a discrepancy in the invoice "
                        "amount or billing schedule."
                    ),
                    "score": 0.55,
                    "steps": [
                        {
                            "label": "Review Invoice",
                            "content": (
                                "Compare the invoice with expected "
                                "charges line by line."
                            ),
                            "score": 0.72,
                        },
                        {
                            "label": "Adjust Invoice",
                            "content": (
                                "Correct the invoice and reissue " "for payment."
                            ),
                            "score": 0.76,
                            "steps": [
                                {
                                    "label": "Reissue and Retry",
                                    "content": (
                                        "Send corrected invoice and "
                                        "retry payment collection."
                                    ),
                                    "score": 0.80,
                                },
                            ],
                        },
                    ],
                },
            ],
        },
    ],
    # ═══════════════════════════════════════════════════════════════
    # INTEGRATION DOMAIN
    # ═══════════════════════════════════════════════════════════════
    ProblemDomain.INTEGRATION: [
        # Template 1: Webhook Troubleshooting
        {
            "name": "webhook_troubleshooting",
            "root_label": "Webhook Troubleshooting",
            "root_content": (
                "Customer reports webhooks are not being delivered "
                "or are failing. Investigate the webhook pipeline."
            ),
            "branches": [
                {
                    "label": "Configuration Issue",
                    "content": (
                        "The webhook endpoint URL or event "
                        "subscriptions may be misconfigured."
                    ),
                    "score": 0.78,
                    "steps": [
                        {
                            "label": "Verify Endpoint URL",
                            "content": (
                                "Confirm the webhook URL is reachable "
                                "and returns 200 OK."
                            ),
                            "score": 0.82,
                            "steps": [
                                {
                                    "label": "Update URL",
                                    "content": (
                                        "Guide customer to update the "
                                        "webhook endpoint URL."
                                    ),
                                    "score": 0.88,
                                },
                            ],
                        },
                        {
                            "label": "Check Event Subscriptions",
                            "content": (
                                "Verify the correct event types are " "subscribed to."
                            ),
                            "score": 0.75,
                            "action": "prune",
                        },
                    ],
                },
                {
                    "label": "Authentication Issue",
                    "content": (
                        "Webhook signature verification may be "
                        "failing due to key mismatch."
                    ),
                    "score": 0.72,
                    "steps": [
                        {
                            "label": "Verify Signing Secret",
                            "content": (
                                "Confirm the signing secret matches "
                                "between sender and receiver."
                            ),
                            "score": 0.85,
                            "steps": [
                                {
                                    "label": "Rotate Secret",
                                    "content": (
                                        "Generate a new signing secret "
                                        "and update both sides."
                                    ),
                                    "score": 0.80,
                                },
                            ],
                        },
                        {
                            "label": "Check Timestamp",
                            "content": (
                                "Verify timestamp tolerance settings "
                                "are appropriate."
                            ),
                            "score": 0.68,
                        },
                    ],
                },
                {
                    "label": "Delivery Issue",
                    "content": (
                        "The webhook delivery infrastructure may "
                        "be experiencing failures."
                    ),
                    "score": 0.65,
                    "steps": [
                        {
                            "label": "Check Delivery Logs",
                            "content": (
                                "Review webhook delivery logs for " "failed attempts."
                            ),
                            "score": 0.80,
                            "steps": [
                                {
                                    "label": "Retry Failed",
                                    "content": (
                                        "Manually retry failed webhook " "deliveries."
                                    ),
                                    "score": 0.84,
                                },
                            ],
                        },
                        {
                            "label": "Check Timeout Settings",
                            "content": (
                                "Increase webhook timeout if the "
                                "endpoint is slow to respond."
                            ),
                            "score": 0.70,
                            "action": "prune",
                        },
                    ],
                },
            ],
        },
        # Template 2: OAuth / SSO Configuration
        {
            "name": "oauth_sso_configuration",
            "root_label": "OAuth / SSO Configuration",
            "root_content": (
                "Customer needs help setting up or troubleshooting "
                "OAuth or SAML SSO integration."
            ),
            "branches": [
                {
                    "label": "Configuration Mismatch",
                    "content": (
                        "Redirect URIs, scopes, or client IDs may "
                        "not match between provider and application."
                    ),
                    "score": 0.82,
                    "steps": [
                        {
                            "label": "Verify Redirect URI",
                            "content": (
                                "Confirm redirect URI matches exactly "
                                "in both configurations."
                            ),
                            "score": 0.88,
                            "steps": [
                                {
                                    "label": "Update Configuration",
                                    "content": (
                                        "Correct the mismatched "
                                        "configuration values."
                                    ),
                                    "score": 0.92,
                                },
                            ],
                        },
                        {
                            "label": "Verify Client ID / Secret",
                            "content": (
                                "Ensure client ID and secret are " "correctly entered."
                            ),
                            "score": 0.78,
                        },
                    ],
                },
                {
                    "label": "Token Issue",
                    "content": (
                        "Access or refresh tokens may be expired "
                        "or improperly handled."
                    ),
                    "score": 0.68,
                    "steps": [
                        {
                            "label": "Re-authenticate",
                            "content": (
                                "Guide the user through a fresh " "authentication flow."
                            ),
                            "score": 0.80,
                        },
                        {
                            "label": "Check Token Storage",
                            "content": (
                                "Verify tokens are stored securely "
                                "and rotated properly."
                            ),
                            "score": 0.72,
                            "action": "prune",
                        },
                    ],
                },
                {
                    "label": "Permission / Scope Issue",
                    "content": (
                        "The application may be requesting scopes "
                        "that the provider does not allow."
                    ),
                    "score": 0.60,
                    "steps": [
                        {
                            "label": "Review Required Scopes",
                            "content": (
                                "List all required permissions and "
                                "check provider support."
                            ),
                            "score": 0.75,
                            "steps": [
                                {
                                    "label": "Request Access",
                                    "content": (
                                        "Submit a request to the "
                                        "provider for additional scopes."
                                    ),
                                    "score": 0.70,
                                },
                            ],
                        },
                        {
                            "label": "Adjust App Permissions",
                            "content": (
                                "Modify the application to work "
                                "with available scopes."
                            ),
                            "score": 0.65,
                            "action": "prune",
                        },
                    ],
                },
            ],
        },
    ],
    # ═══════════════════════════════════════════════════════════════
    # ESCALATION DOMAIN
    # ═══════════════════════════════════════════════════════════════
    ProblemDomain.ESCALATION: [
        # Template 1: Critical Customer Issue
        {
            "name": "critical_customer_issue",
            "root_label": "Critical Customer Issue",
            "root_content": (
                "A high-priority customer issue requires rapid "
                "assessment and appropriate escalation."
            ),
            "branches": [
                {
                    "label": "Immediate Resolution",
                    "content": (
                        "Attempt to resolve the issue directly "
                        "if it is within support scope."
                    ),
                    "score": 0.80,
                    "steps": [
                        {
                            "label": "Assess Severity",
                            "content": (
                                "Determine impact scope: revenue, "
                                "users affected, data at risk."
                            ),
                            "score": 0.85,
                            "steps": [
                                {
                                    "label": "Apply Hotfix",
                                    "content": (
                                        "Deploy an emergency fix "
                                        "if the root cause is known."
                                    ),
                                    "score": 0.90,
                                },
                                {
                                    "label": "Enable Workaround",
                                    "content": (
                                        "Provide a temporary workaround "
                                        "to mitigate impact."
                                    ),
                                    "score": 0.78,
                                },
                            ],
                        },
                    ],
                },
                {
                    "label": "Engineering Escalation",
                    "content": (
                        "Escalate to the engineering team for "
                        "deep technical investigation."
                    ),
                    "score": 0.75,
                    "steps": [
                        {
                            "label": "Gather Diagnostic Data",
                            "content": (
                                "Collect logs, traces, and " "reproduction steps."
                            ),
                            "score": 0.82,
                            "steps": [
                                {
                                    "label": "Create Ticket",
                                    "content": (
                                        "File a priority engineering "
                                        "ticket with full context."
                                    ),
                                    "score": 0.88,
                                },
                            ],
                        },
                        {
                            "label": "Engage On-Call",
                            "content": (
                                "Page the on-call engineer " "for immediate attention."
                            ),
                            "score": 0.70,
                            "action": "prune",
                        },
                    ],
                },
                {
                    "label": "Management Escalation",
                    "content": (
                        "Escalate to management for business-level "
                        "decisions or communication."
                    ),
                    "score": 0.60,
                    "steps": [
                        {
                            "label": "Prepare Summary",
                            "content": (
                                "Write a clear executive summary "
                                "of the issue and its impact."
                            ),
                            "score": 0.72,
                            "steps": [
                                {
                                    "label": "Schedule Call",
                                    "content": (
                                        "Arrange a call with the "
                                        "customer's management team."
                                    ),
                                    "score": 0.68,
                                },
                            ],
                        },
                        {
                            "label": "Define SLA Response",
                            "content": (
                                "Document SLA implications and " "remediation timeline."
                            ),
                            "score": 0.65,
                        },
                    ],
                },
            ],
        },
        # Template 2: Data Security Incident
        {
            "name": "data_security_incident",
            "root_label": "Data Security Incident",
            "root_content": (
                "Potential data security incident reported. "
                "Follow security incident response protocol."
            ),
            "branches": [
                {
                    "label": "Containment",
                    "content": (
                        "Immediately contain the potential breach "
                        "to prevent further exposure."
                    ),
                    "score": 0.90,
                    "steps": [
                        {
                            "label": "Revoke Access",
                            "content": (
                                "Revoke compromised credentials "
                                "and sessions immediately."
                            ),
                            "score": 0.95,
                            "steps": [
                                {
                                    "label": "Force Password Reset",
                                    "content": (
                                        "Require all affected users "
                                        "to reset passwords."
                                    ),
                                    "score": 0.92,
                                },
                            ],
                        },
                        {
                            "label": "Isolate Systems",
                            "content": (
                                "Isolate affected systems from " "the network."
                            ),
                            "score": 0.85,
                        },
                    ],
                },
                {
                    "label": "Investigation",
                    "content": (
                        "Investigate the scope and root cause "
                        "of the security incident."
                    ),
                    "score": 0.80,
                    "steps": [
                        {
                            "label": "Audit Access Logs",
                            "content": (
                                "Review access logs for " "unauthorised activity."
                            ),
                            "score": 0.85,
                            "steps": [
                                {
                                    "label": "Identify Attack Vector",
                                    "content": (
                                        "Determine how the breach " "occurred."
                                    ),
                                    "score": 0.88,
                                },
                            ],
                        },
                        {
                            "label": "Assess Data Exposure",
                            "content": (
                                "Determine what data was accessed " "or exfiltrated."
                            ),
                            "score": 0.82,
                        },
                    ],
                },
                {
                    "label": "Compliance / Legal",
                    "content": (
                        "Handle regulatory and legal requirements "
                        "for incident reporting."
                    ),
                    "score": 0.70,
                    "steps": [
                        {
                            "label": "Notify Stakeholders",
                            "content": (
                                "Inform affected parties as " "required by regulation."
                            ),
                            "score": 0.78,
                            "steps": [
                                {
                                    "label": "Draft Notification",
                                    "content": (
                                        "Prepare regulatory " "compliance notification."
                                    ),
                                    "score": 0.75,
                                },
                            ],
                        },
                        {
                            "label": "Engage Legal Counsel",
                            "content": (
                                "Involve legal team for " "guidance on disclosure."
                            ),
                            "score": 0.65,
                            "action": "prune",
                        },
                    ],
                },
            ],
        },
    ],
    # ═══════════════════════════════════════════════════════════════
    # GENERAL DOMAIN
    # ═══════════════════════════════════════════════════════════════
    ProblemDomain.GENERAL: [
        # Template 1: Multi-Path Resolution
        {
            "name": "multi_path_resolution",
            "root_label": "Multi-Path Resolution",
            "root_content": (
                "General inquiry with multiple possible resolution "
                "paths. Evaluate each path systematically."
            ),
            "branches": [
                {
                    "label": "Direct Resolution",
                    "content": (
                        "Resolve the issue directly with available "
                        "information and tools."
                    ),
                    "score": 0.78,
                    "steps": [
                        {
                            "label": "Identify Root Cause",
                            "content": (
                                "Pinpoint the specific cause of "
                                "the customer's issue."
                            ),
                            "score": 0.82,
                            "steps": [
                                {
                                    "label": "Apply Solution",
                                    "content": (
                                        "Implement the identified " "solution directly."
                                    ),
                                    "score": 0.88,
                                },
                            ],
                        },
                        {
                            "label": "Verify Resolution",
                            "content": (
                                "Confirm the issue is fully " "resolved before closing."
                            ),
                            "score": 0.80,
                        },
                    ],
                },
                {
                    "label": "Guided Self-Service",
                    "content": (
                        "Guide the customer to resolve the issue "
                        "themselves with documentation."
                    ),
                    "score": 0.65,
                    "steps": [
                        {
                            "label": "Locate Documentation",
                            "content": (
                                "Find the most relevant help " "article or guide."
                            ),
                            "score": 0.75,
                            "steps": [
                                {
                                    "label": "Share Steps",
                                    "content": (
                                        "Provide clear step-by-step " "instructions."
                                    ),
                                    "score": 0.80,
                                },
                            ],
                        },
                        {
                            "label": "Follow Up",
                            "content": (
                                "Schedule a follow-up to confirm "
                                "the self-service fix worked."
                            ),
                            "score": 0.60,
                            "action": "prune",
                        },
                    ],
                },
                {
                    "label": "Team Collaboration",
                    "content": (
                        "Collaborate with internal teams for a "
                        "resolution that requires cross-functional "
                        "expertise."
                    ),
                    "score": 0.55,
                    "steps": [
                        {
                            "label": "Identify Stakeholders",
                            "content": (
                                "Determine which teams need to " "be involved."
                            ),
                            "score": 0.68,
                            "steps": [
                                {
                                    "label": "Internal Ticket",
                                    "content": (
                                        "Create an internal ticket "
                                        "for team collaboration."
                                    ),
                                    "score": 0.72,
                                },
                            ],
                        },
                        {
                            "label": "Coordinate Response",
                            "content": (
                                "Synchronise response across " "teams for the customer."
                            ),
                            "score": 0.62,
                            "action": "prune",
                        },
                    ],
                },
            ],
        },
        # Template 2: Feature Request Assessment
        {
            "name": "feature_request_assessment",
            "root_label": "Feature Request Assessment",
            "root_content": (
                "Customer is requesting a new feature or capability. "
                "Assess feasibility and provide guidance."
            ),
            "branches": [
                {
                    "label": "Existing Solution",
                    "content": (
                        "Check if the requested capability already "
                        "exists in the product."
                    ),
                    "score": 0.82,
                    "steps": [
                        {
                            "label": "Search Feature Catalog",
                            "content": (
                                "Search for the feature in the "
                                "existing product catalogue."
                            ),
                            "score": 0.85,
                            "steps": [
                                {
                                    "label": "Enable Feature",
                                    "content": (
                                        "Guide customer to enable "
                                        "or configure the feature."
                                    ),
                                    "score": 0.90,
                                },
                            ],
                        },
                        {
                            "label": "Check Roadmap",
                            "content": (
                                "Verify if the feature is on the " "product roadmap."
                            ),
                            "score": 0.72,
                        },
                    ],
                },
                {
                    "label": "Workaround Available",
                    "content": (
                        "Check if there is an alternative way to "
                        "achieve the customer's goal."
                    ),
                    "score": 0.70,
                    "steps": [
                        {
                            "label": "Identify Workaround",
                            "content": (
                                "Find a combination of existing "
                                "features that achieves the goal."
                            ),
                            "score": 0.78,
                            "steps": [
                                {
                                    "label": "Document Workaround",
                                    "content": (
                                        "Provide detailed " "workaround instructions."
                                    ),
                                    "score": 0.82,
                                },
                            ],
                        },
                        {
                            "label": "API / Integration Path",
                            "content": (
                                "Check if the goal can be achieved "
                                "via API or integration."
                            ),
                            "score": 0.65,
                            "action": "prune",
                        },
                    ],
                },
                {
                    "label": "New Feature Request",
                    "content": (
                        "The feature does not exist. Submit as a "
                        "formal feature request."
                    ),
                    "score": 0.55,
                    "steps": [
                        {
                            "label": "Gather Requirements",
                            "content": (
                                "Collect detailed requirements "
                                "and use case description."
                            ),
                            "score": 0.68,
                            "steps": [
                                {
                                    "label": "Submit Request",
                                    "content": (
                                        "Create a formal feature "
                                        "request with full context."
                                    ),
                                    "score": 0.72,
                                },
                            ],
                        },
                        {
                            "label": "Set Expectations",
                            "content": (
                                "Communicate timeline expectations "
                                "for the feature request."
                            ),
                            "score": 0.60,
                        },
                    ],
                },
            ],
        },
    ],
}


# ── Confidence Impact Per Domain ────────────────────────────────────


_DOMAIN_CONFIDENCE_BOOST: Dict[ProblemDomain, float] = {
    ProblemDomain.TECHNICAL: 0.15,
    ProblemDomain.BILLING: 0.12,
    ProblemDomain.INTEGRATION: 0.13,
    ProblemDomain.ESCALATION: 0.18,
    ProblemDomain.GENERAL: 0.10,
}


# ── Data Structures ────────────────────────────────────────────────


@dataclass(frozen=True)
class ToTConfig:
    """
    Immutable configuration for Tree of Thoughts processing (BC-001).

    Attributes:
        company_id: Tenant identifier for company isolation.
        search_strategy: Algorithm for tree traversal.
        prune_threshold: Minimum score for a branch to remain active.
        max_depth: Maximum tree depth for search exploration.
        max_branches: Maximum number of top-level branches.
        enable_reasoning_trace: Whether to build the step-by-step
            reasoning trace.
        beam_width: Number of top candidates to keep in best-first.
    """

    company_id: str = ""
    search_strategy: SearchStrategy = SearchStrategy.BEST_FIRST
    prune_threshold: float = 0.50
    max_depth: int = 4
    max_branches: int = 5
    enable_reasoning_trace: bool = True
    beam_width: int = 3


@dataclass
class ToTResult:
    """
    Output of the full Tree of Thoughts pipeline.

    Attributes:
        domain: Classified problem domain.
        template_name: Name of the tree template used.
        total_nodes: Total number of nodes in the tree.
        pruned_count: Number of nodes pruned.
        selected_path: Ordered list of TreeNode dicts on the best path.
        reasoning_trace: Step-by-step reasoning trace.
        search_strategy: Strategy used for tree search.
        confidence_boost: Estimated confidence improvement.
        steps_applied: Names of pipeline steps executed.
    """

    domain: str = ""
    template_name: str = ""
    total_nodes: int = 0
    pruned_count: int = 0
    selected_path: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_trace: List[Dict[str, str]] = field(default_factory=list)
    search_strategy: str = ""
    confidence_boost: float = 0.0
    steps_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary for recording in state."""
        return {
            "domain": self.domain,
            "template_name": self.template_name,
            "total_nodes": self.total_nodes,
            "pruned_count": self.pruned_count,
            "selected_path": list(self.selected_path),
            "reasoning_trace": list(self.reasoning_trace),
            "search_strategy": self.search_strategy,
            "confidence_boost": round(self.confidence_boost, 4),
            "steps_applied": list(self.steps_applied),
        }


# ── ToT Processor ──────────────────────────────────────────────────


class ToTProcessor:
    """
    Deterministic Tree of Thoughts processor (F-145).

    Uses heuristic scoring and template-based tree generation to
    simulate branching decision reasoning without any LLM calls.

    Pipeline:
      1. Tree Generation    — build reasoning tree from query domain
      2. Branch Evaluation  — score each branch for viability
      3. Pruning            — remove suboptimal branches below threshold
      4. Search             — traverse tree using configured strategy
      5. Path Selection     — choose best path from explored branches
      6. Reasoning Trace    — build step-by-step trace of resolution
    """

    def __init__(
        self,
        config: Optional[ToTConfig] = None,
    ):
        self.config = config or ToTConfig()
        self._nodes: Dict[str, TreeNode] = {}
        self._next_id: int = 0

    # ── ID Generation ──────────────────────────────────────────────

    def _gen_id(self) -> str:
        """Generate a unique node ID."""
        node_id = f"tot_{self._next_id}"
        self._next_id += 1
        return node_id

    # ── Step 0: Domain Classification ──────────────────────────────

    def classify_domain(self, query: str) -> ProblemDomain:
        """
        Classify the query into a ProblemDomain.

        Scans the query against compiled regex patterns to determine
        which domain template set to use.

        Args:
            query: The customer query text.

        Returns:
            The classified ProblemDomain. Falls back to GENERAL
            if no domain pattern matches.
        """
        if not query or not query.strip():
            return ProblemDomain.GENERAL

        query_lower = query.lower().strip()

        best_domain = ProblemDomain.GENERAL
        best_count = 0

        for pattern, domain in _DOMAIN_PATTERNS:
            matches = pattern.findall(query_lower)
            if len(matches) > best_count:
                best_count = len(matches)
                best_domain = domain

        logger.debug(
            "tot_domain_classified",
            domain=best_domain.value,
            match_count=best_count,
            query_length=len(query),
            company_id=self.config.company_id,
        )

        return best_domain

    # ── Step 1: Tree Generation ────────────────────────────────────

    async def generate_tree(
        self,
        query: str,
        domain: ProblemDomain,
    ) -> TreeNode:
        """
        Generate a reasoning tree from a template for the given domain.

        Selects the best-matching template, instantiates tree nodes
        with proper parent-child relationships, and returns the root.

        Args:
            query: The customer query text.
            domain: The classified problem domain.

        Returns:
            The root TreeNode of the generated tree.
        """
        self._nodes = {}
        self._next_id = 0

        templates = _TREE_TEMPLATES.get(domain, [])
        if not templates:
            logger.warning(
                "tot_no_templates_for_domain",
                domain=domain.value,
                company_id=self.config.company_id,
            )
            return self._build_fallback_tree(query)

        # Select template based on query keywords
        template = self._select_template(query, templates)
        if not template:
            return self._build_fallback_tree(query)

        template_name = template.get("name", "unknown")

        logger.debug(
            "tot_tree_generating",
            template=template_name,
            domain=domain.value,
            company_id=self.config.company_id,
        )

        # Build root node
        root = TreeNode(
            id=self._gen_id(),
            label=template.get("root_label", "Root"),
            content=template.get("root_content", query),
            status=BranchStatus.ACTIVE,
            score=1.0,
            depth=0,
            parent_id=None,
        )
        self._nodes[root.id] = root

        # Build branch nodes
        branches = template.get("branches", [])
        for branch_def in branches:
            self._build_branch_node(root.id, branch_def, depth=1)

        logger.debug(
            "tot_tree_generated",
            template=template_name,
            total_nodes=len(self._nodes),
            company_id=self.config.company_id,
        )

        return root

    def _select_template(
        self,
        query: str,
        templates: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Select the most relevant tree template for the query.

        Uses keyword overlap between the query and template labels
        to select the best match. Falls back to the first template
        if no match is found.

        Args:
            query: The customer query text.
            templates: Available templates for the domain.

        Returns:
            The selected template dict, or None if empty.
        """
        if not templates:
            return None

        query_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", query.lower()))

        best_template = templates[0]
        best_score = 0

        for tmpl in templates:
            tmpl_text = tmpl.get("root_label", "") + " " + tmpl.get("root_content", "")
            tmpl_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", tmpl_text.lower()))

            # Score based on keyword overlap
            overlap = len(query_words & tmpl_words)
            if overlap > best_score:
                best_score = overlap
                best_template = tmpl

        return best_template

    def _build_branch_node(
        self,
        parent_id: str,
        branch_def: Dict[str, Any],
        depth: int,
    ) -> str:
        """
        Recursively build a branch node and its children.

        Args:
            parent_id: ID of the parent node.
            branch_def: Branch definition from the template.
            depth: Current depth in the tree.

        Returns:
            The ID of the created node.
        """
        node = TreeNode(
            id=self._gen_id(),
            label=branch_def.get("label", "Branch"),
            content=branch_def.get("content", ""),
            status=BranchStatus.ACTIVE,
            score=branch_def.get("score", 0.5),
            depth=depth,
            parent_id=parent_id,
        )
        self._nodes[node.id] = node

        # Link parent to child
        parent = self._nodes.get(parent_id)
        if parent:
            parent.children.append(node.id)

        # Build child steps
        steps = branch_def.get("steps", [])
        for step_def in steps:
            if depth < self.config.max_depth:
                self._build_branch_node(node.id, step_def, depth + 1)

        return node.id

    def _build_fallback_tree(self, query: str) -> TreeNode:
        """
        Build a minimal fallback tree when no template matches.

        Args:
            query: The customer query text.

        Returns:
            A root TreeNode with a single generic branch.
        """
        root = TreeNode(
            id=self._gen_id(),
            label="General Investigation",
            content=query,
            status=BranchStatus.ACTIVE,
            score=1.0,
            depth=0,
        )
        self._nodes[root.id] = root

        branch = TreeNode(
            id=self._gen_id(),
            label="Investigate Issue",
            content=(
                "Investigate the customer's issue using "
                "available information and resources."
            ),
            status=BranchStatus.ACTIVE,
            score=0.7,
            depth=1,
            parent_id=root.id,
        )
        self._nodes[branch.id] = branch
        root.children.append(branch.id)

        resolve = TreeNode(
            id=self._gen_id(),
            label="Provide Resolution",
            content=("Provide a clear resolution based on " "investigation findings."),
            status=BranchStatus.ACTIVE,
            score=0.85,
            depth=2,
            parent_id=branch.id,
        )
        self._nodes[resolve.id] = resolve
        branch.children.append(resolve.id)

        logger.debug(
            "tot_fallback_tree_built",
            company_id=self.config.company_id,
        )

        return root

    # ── Step 2: Branch Evaluation ──────────────────────────────────

    async def evaluate_branches(self) -> int:
        """
        Score each branch in the tree for viability.

        Propagates scores from leaf nodes upward so that parent
        scores reflect the best child score. This ensures that
        branches with promising children are not pruned.

        Returns:
            The number of branches evaluated.
        """
        evaluated = 0

        # Iterate in reverse depth order (leaves first)
        sorted_nodes = sorted(
            self._nodes.values(),
            key=lambda n: n.depth,
            reverse=True,
        )

        for node in sorted_nodes:
            if node.depth == 0:
                continue  # skip root

            if node.children:
                # Parent score = max child score * 0.7 + own score * 0.3
                child_scores = [
                    self._nodes[cid].score
                    for cid in node.children
                    if cid in self._nodes
                ]
                if child_scores:
                    best_child = max(child_scores)
                    node.score = round(
                        best_child * 0.7 + node.score * 0.3,
                        4,
                    )
            evaluated += 1

        logger.debug(
            "tot_branches_evaluated",
            evaluated_count=evaluated,
            company_id=self.config.company_id,
        )

        return evaluated

    # ── Step 3: Pruning ────────────────────────────────────────────

    async def prune_tree(self) -> int:
        """
        Remove suboptimal branches below the score threshold.

        Marks nodes below the configured prune_threshold as PRUNED
        and marks branches with all children pruned as DEAD_END.
        Explicit prune actions from templates are also respected.

        Returns:
            The number of nodes pruned.
        """
        pruned = 0
        threshold = self.config.prune_threshold

        # First pass: prune by score threshold
        for node in self._nodes.values():
            if node.depth == 0:
                continue

            if node.score < threshold:
                node.status = BranchStatus.PRUNED
                pruned += 1

        # Second pass: propagate pruning to children
        # and mark leaf-active nodes as dead ends if parent is pruned
        changed = True
        while changed:
            changed = False
            for node in self._nodes.values():
                if node.status == BranchStatus.PRUNED:
                    for cid in node.children:
                        child = self._nodes.get(cid)
                        if child and child.status == BranchStatus.ACTIVE:
                            child.status = BranchStatus.PRUNED
                            pruned += 1
                            changed = True

        # Third pass: mark branches with no active children as dead_end
        for node in self._nodes.values():
            if node.depth == 0 or node.status != BranchStatus.ACTIVE:
                continue
            if not node.children:
                node.status = BranchStatus.DEAD_END

        logger.debug(
            "tot_tree_pruned",
            pruned_count=pruned,
            threshold=threshold,
            remaining_active=sum(
                1 for n in self._nodes.values() if n.status == BranchStatus.ACTIVE
            ),
            company_id=self.config.company_id,
        )

        return pruned

    # ── Step 4: Search ─────────────────────────────────────────────

    async def search_tree(self) -> List[str]:
        """
        Traverse the tree using the configured search strategy.

        Supports BFS (breadth-first), DFS (depth-first), and
        best-first (prioritise highest-scoring nodes) strategies.

        Returns:
            Ordered list of explored node IDs.
        """
        strategy = self.config.search_strategy
        root_candidates = [nid for nid, n in self._nodes.items() if n.depth == 0]
        if not root_candidates:
            return []

        root_id = root_candidates[0]
        explored: List[str] = []

        if strategy == SearchStrategy.BFS:
            explored = self._search_bfs(root_id)
        elif strategy == SearchStrategy.DFS:
            explored = self._search_dfs(root_id)
        else:
            explored = self._search_best_first(root_id)

        # Mark explored nodes
        for nid in explored:
            node = self._nodes.get(nid)
            if node and node.status == BranchStatus.ACTIVE:
                node.status = BranchStatus.EXPLORED

        logger.debug(
            "tot_tree_searched",
            strategy=strategy.value,
            explored_count=len(explored),
            company_id=self.config.company_id,
        )

        return explored

    def _search_bfs(self, root_id: str) -> List[str]:
        """Breadth-first search through active nodes."""
        explored: List[str] = []
        queue: Deque[str] = deque([root_id])

        while queue:
            nid = queue.popleft()
            if nid in explored:
                continue

            node = self._nodes.get(nid)
            if not node or node.status == BranchStatus.PRUNED:
                continue

            explored.append(nid)

            # Enqueue active children (limit branches per level)
            children = [
                cid
                for cid in node.children
                if self._nodes.get(cid)
                and self._nodes[cid].status != BranchStatus.PRUNED
            ]
            for cid in children[: self.config.max_branches]:
                queue.append(cid)

        return explored

    def _search_dfs(self, root_id: str) -> List[str]:
        """Depth-first search through active nodes."""
        explored: List[str] = []

        def _dfs(nid: str) -> None:
            if nid in explored:
                return
            node = self._nodes.get(nid)
            if not node or node.status == BranchStatus.PRUNED:
                return

            explored.append(nid)

            for cid in node.children[: self.config.max_branches]:
                child = self._nodes.get(cid)
                if child and child.status != BranchStatus.PRUNED:
                    _dfs(cid)

        _dfs(root_id)
        return explored

    def _search_best_first(self, root_id: str) -> List[str]:
        """Best-first search: always expand the highest-scored node."""
        import heapq

        explored: List[str] = []
        # Priority queue: (-score, id) so highest score pops first
        heap: List[Tuple[float, str]] = [(-1.0, root_id)]
        visited: Set[str] = set()

        while heap:
            neg_score, nid = heapq.heappop(heap)
            if nid in visited:
                continue

            node = self._nodes.get(nid)
            if not node or node.status == BranchStatus.PRUNED:
                continue

            visited.add(nid)
            explored.append(nid)

            # Add children to the priority queue
            children = [
                cid
                for cid in node.children
                if self._nodes.get(cid)
                and self._nodes[cid].status != BranchStatus.PRUNED
            ]
            for cid in children[: self.config.max_branches]:
                child = self._nodes.get(cid)
                if child:
                    heapq.heappush(heap, (-child.score, cid))

        return explored

    # ── Step 5: Path Selection ─────────────────────────────────────

    async def select_best_path(
        self,
        explored: List[str],
    ) -> List[TreeNode]:
        """
        Select the best path from explored nodes.

        Identifies leaf nodes (explored nodes with no explored
        children), then traces back from the highest-scoring leaf
        to the root.

        Args:
            explored: List of explored node IDs from search.

        Returns:
            Ordered list of TreeNodes from root to best leaf.
        """
        if not explored:
            return []

        explored_set = set(explored)

        # Identify leaf nodes: explored nodes whose children
        # are not in the explored set (or have no children)
        leaf_candidates: List[TreeNode] = []
        for nid in explored:
            node = self._nodes.get(nid)
            if not node or node.depth == 0:
                continue
            child_explored = [cid for cid in node.children if cid in explored_set]
            if not child_explored:
                leaf_candidates.append(node)

        # If no leaves found, fall back to deepest explored node
        if not leaf_candidates:
            leaf_candidates = [
                self._nodes[nid]
                for nid in explored
                if nid in self._nodes and self._nodes[nid].depth > 0
            ]

        # Select the highest-scoring leaf; prefer deeper on tie
        best_leaf: Optional[TreeNode] = None
        for node in leaf_candidates:
            if (
                best_leaf is None
                or node.score > best_leaf.score
                or (node.score == best_leaf.score and node.depth > best_leaf.depth)
            ):
                best_leaf = node

        if not best_leaf:
            return []

        # Trace back from leaf to root
        path: List[TreeNode] = []
        current = best_leaf
        while current:
            current.status = BranchStatus.SELECTED
            path.append(current)
            if current.parent_id:
                current = self._nodes.get(current.parent_id)
            else:
                current = None

        # Reverse so path goes root → leaf
        path.reverse()

        logger.debug(
            "tot_path_selected",
            path_length=len(path),
            best_score=round(best_leaf.score, 4),
            company_id=self.config.company_id,
        )

        return path

    # ── Step 6: Reasoning Trace ────────────────────────────────────

    async def build_reasoning_trace(
        self,
        path: List[TreeNode],
        domain: ProblemDomain,
        template_name: str,
    ) -> List[Dict[str, str]]:
        """
        Build a step-by-step reasoning trace from the selected path.

        Each trace entry records one step of the resolution path,
        providing transparency into the decision-making process.

        Args:
            path: Ordered list of TreeNodes from root to leaf.
            domain: The classified problem domain.
            template_name: Name of the tree template used.

        Returns:
            List of trace entry dictionaries.
        """
        trace: List[Dict[str, str]] = []

        # Entry 1: Domain classification
        trace.append(
            {
                "step": "domain_classification",
                "domain": domain.value,
                "template": template_name,
                "timestamp": _utcnow_iso(),
            }
        )

        # Entry 2: Tree overview
        total = len(self._nodes)
        pruned = sum(1 for n in self._nodes.values() if n.status == BranchStatus.PRUNED)
        active = sum(
            1
            for n in self._nodes.values()
            if n.status in (BranchStatus.ACTIVE, BranchStatus.EXPLORED)
        )
        trace.append(
            {
                "step": "tree_overview",
                "total_nodes": str(total),
                "pruned_nodes": str(pruned),
                "active_nodes": str(active),
                "search_strategy": self.config.search_strategy.value,
                "timestamp": _utcnow_iso(),
            }
        )

        # Entry 3: Path steps
        for idx, node in enumerate(path):
            role = (
                "root" if idx == 0 else ("decision" if node.children else "resolution")
            )
            trace.append(
                {
                    "step": f"path_step_{idx + 1}",
                    "role": role,
                    "label": node.label,
                    "content": node.content,
                    "score": str(round(node.score, 4)),
                    "depth": str(node.depth),
                    "timestamp": _utcnow_iso(),
                }
            )

        # Entry 4: Pruned alternatives summary
        pruned_branches = [
            n.label
            for n in self._nodes.values()
            if n.status == BranchStatus.PRUNED and n.depth == 1
        ]
        if pruned_branches:
            trace.append(
                {
                    "step": "pruned_alternatives",
                    "pruned_branches": "; ".join(pruned_branches),
                    "prune_threshold": str(self.config.prune_threshold),
                    "timestamp": _utcnow_iso(),
                }
            )

        logger.debug(
            "tot_reasoning_trace_built",
            trace_entries=len(trace),
            path_length=len(path),
            company_id=self.config.company_id,
        )

        return trace

    # ── Full Pipeline ──────────────────────────────────────────────

    async def process(self, query: str) -> ToTResult:
        """
        Run the full 6-step Tree of Thoughts pipeline.

        The pipeline executes:
          1. Tree Generation    — build reasoning tree from domain
          2. Branch Evaluation  — score and propagate branch scores
          3. Pruning            — remove suboptimal branches
          4. Search             — traverse tree with configured strategy
          5. Path Selection     — choose best path from explored nodes
          6. Reasoning Trace    — build step-by-step trace

        Args:
            query: The customer query text.

        Returns:
            ToTResult with all pipeline outputs.
        """
        steps_applied: List[str] = []
        confidence_boost = 0.0
        domain = ProblemDomain.GENERAL
        template_name = ""
        reasoning_trace: List[Dict[str, str]] = []
        selected_path: List[TreeNode] = []

        if not query or not query.strip():
            return ToTResult(
                steps_applied=["empty_input"],
                confidence_boost=0.0,
            )

        try:
            # Step 0: Domain classification
            domain = self.classify_domain(query)
            steps_applied.append("domain_classification")

            # Step 1: Tree generation
            root = await self.generate_tree(query, domain)
            if self._nodes:
                steps_applied.append("tree_generation")

                # Get template name from root metadata or default
                template_name = root.label

            # Step 2: Branch evaluation
            evaluated = await self.evaluate_branches()
            if evaluated > 0:
                steps_applied.append("branch_evaluation")

            # Step 3: Pruning
            pruned_count = await self.prune_tree()
            if pruned_count > 0:
                steps_applied.append("pruning")
            else:
                steps_applied.append("pruning_no_change")

            # Step 4: Search
            explored = await self.search_tree()
            if explored:
                steps_applied.append("search")

            # Step 5: Path selection
            selected_path = await self.select_best_path(explored)
            if selected_path:
                steps_applied.append("path_selection")

            # Step 6: Reasoning trace
            if self.config.enable_reasoning_trace and selected_path:
                reasoning_trace = await self.build_reasoning_trace(
                    selected_path,
                    domain,
                    template_name,
                )
                if reasoning_trace:
                    steps_applied.append("reasoning_trace")

            # Calculate confidence boost based on domain and path quality
            base_boost = _DOMAIN_CONFIDENCE_BOOST.get(domain, 0.10)
            if selected_path:
                best_score = selected_path[-1].score if selected_path else 0
                confidence_boost = base_boost * best_score
            else:
                confidence_boost = base_boost * 0.3  # reduced for no path

            logger.info(
                "tot_executed",
                domain=domain.value,
                total_nodes=len(self._nodes),
                pruned_count=pruned_count,
                path_length=len(selected_path),
                confidence_boost=round(confidence_boost, 4),
                steps_applied=steps_applied,
                company_id=self.config.company_id,
            )

        except Exception as exc:
            # BC-008: Never crash — return graceful fallback
            logger.warning(
                "tot_processing_error",
                error=str(exc),
                company_id=self.config.company_id,
            )
            return ToTResult(
                domain=domain.value,
                template_name=template_name,
                total_nodes=len(self._nodes),
                pruned_count=0,
                selected_path=[n.to_dict() for n in selected_path],
                reasoning_trace=reasoning_trace,
                search_strategy=self.config.search_strategy.value,
                confidence_boost=0.0,
                steps_applied=steps_applied + ["error_fallback"],
            )

        return ToTResult(
            domain=domain.value,
            template_name=template_name,
            total_nodes=len(self._nodes),
            pruned_count=pruned_count if "pruned_count" in dir() else 0,
            selected_path=[n.to_dict() for n in selected_path],
            reasoning_trace=reasoning_trace,
            search_strategy=self.config.search_strategy.value,
            confidence_boost=round(confidence_boost, 4),
            steps_applied=steps_applied,
        )


# ── TreeOfThoughts Node (LangGraph compatible) ────────────────────


class TreeOfThoughtsNode(BaseTechniqueNode):
    """
    F-145: Tree of Thoughts — Tier 3 Premium.

    Extends BaseTechniqueNode for integration into the LangGraph
    pipeline (F-060).

    Activation triggers:
      - resolution_path_count >= 3, OR
      - is_strategic_decision is True
    """

    def __init__(
        self,
        config: Optional[ToTConfig] = None,
    ):
        self._config = config or ToTConfig()
        self._processor = ToTProcessor(config=self._config)
        # Call parent init after config is set (reads TECHNIQUE_REGISTRY)
        super().__init__()

    @property
    def technique_id(self) -> TechniqueID:
        """Return the TechniqueID for this node."""
        return TechniqueID.TREE_OF_THOUGHTS

    async def should_activate(self, state: ConversationState) -> bool:
        """
        Check if Tree of Thoughts should activate.

        Triggers when:
          - The query has 3+ possible resolution paths, OR
          - The query requires a branching decision analysis.
        """
        return (
            state.signals.resolution_path_count >= 3
            or state.signals.is_strategic_decision
        )

    async def execute(self, state: ConversationState) -> ConversationState:
        """
        Execute the Tree of Thoughts pipeline.

        Implements the 6-step reasoning process:
          1. Tree Generation    — build reasoning tree
          2. Branch Evaluation  — score branches
          3. Pruning            — remove suboptimal branches
          4. Search             — traverse tree
          5. Path Selection     — choose best path
          6. Reasoning Trace    — build trace

        Records the result, updates confidence, and appends
        the selected resolution path to response_parts.

        On error (BC-008), returns the original state unchanged.
        """
        original_state = state

        try:
            # Run the ToT pipeline
            result = await self._processor.process(query=state.query)

            # Record result in state
            self.record_result(state, result.to_dict())

            # Update confidence score in signals
            new_confidence = min(
                state.signals.confidence_score + result.confidence_boost,
                1.0,
            )
            state.signals.confidence_score = max(new_confidence, 0.0)

            # Build response from selected path
            if result.selected_path:
                response_text = self._format_path_response(
                    result.selected_path,
                    result.domain,
                )
                state.response_parts.append(response_text)

                # Store reasoning trace in state for transparency
                if result.reasoning_trace:
                    state.reasoning_thread.append(
                        "ToT Reasoning Trace: "
                        + " → ".join(
                            step.get("label", "")
                            for step in result.reasoning_trace
                            if step.get("step", "").startswith("path_step")
                        )
                    )

            logger.info(
                "tot_node_executed",
                domain=result.domain,
                total_nodes=result.total_nodes,
                pruned_count=result.pruned_count,
                path_length=len(result.selected_path),
                confidence_boost=result.confidence_boost,
                steps_applied=result.steps_applied,
                company_id=self._config.company_id,
            )

            return state

        except Exception as exc:
            # BC-008: Never crash — return original state
            logger.warning(
                "tot_execute_error",
                error=str(exc),
                company_id=self._config.company_id,
            )
            return original_state

    # ── Response Formatting ────────────────────────────────────────

    @staticmethod
    def _format_path_response(
        path: List[Dict[str, Any]],
        domain: str,
    ) -> str:
        """
        Format the selected path into a human-readable response.

        Builds a structured response that walks through each step
        of the selected resolution path.

        Args:
            path: Ordered list of node dicts from root to leaf.
            domain: The problem domain for context.

        Returns:
            Formatted response string.
        """
        if not path:
            return ""

        parts: List[str] = []

        # Opening context
        parts.append(
            f"Based on my analysis of the {domain} issue, "
            "here is the recommended resolution path:"
        )

        # Walk through each step
        for idx, node in enumerate(path):
            label = node.get("label", "Step")
            content = node.get("content", "")
            score = node.get("score", 0)

            if idx == 0:
                # Root — just acknowledge the problem
                parts.append(f"**Issue:** {content}")
            elif idx == len(path) - 1:
                # Final resolution step
                parts.append(
                    f"**Recommended Action:** {label} — {content} "
                    f"(confidence: {int(score * 100)}%)"
                )
            else:
                # Intermediate step
                parts.append(f"**Step {idx}:** {label} — {content}")

        return "\n\n".join(parts)


# ── Module-Level Helpers ───────────────────────────────────────────


def _utcnow_iso() -> str:
    """Return the current UTC time as an ISO-formatted string."""
    return datetime.now(timezone.utc).isoformat()

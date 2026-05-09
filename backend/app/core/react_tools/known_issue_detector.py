"""
PARWA ReAct Tool — Known Issue Detector (Day 3)

Searches a known bug/issue database to match customer-reported problems
against documented issues. Enables the AI agent to:
- search_known_issues      Search the known issue database by keywords
- get_issue_details        Get full details of a specific known issue
- check_issue_status       Check if a known issue is resolved
- get_workaround           Get available workaround for a known issue

All actions are scoped to *company_id* (BC-001) and return
structured ToolResult (BC-008). Every method wrapped in try/except — never crash.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import ActionSchema, BaseReactTool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

# ── Known Issues Database ──────────────────────────────────────────

KNOWN_ISSUES_DB: list[dict[str, Any]] = [
    {
        "issue_id": "KI-001",
        "title": "Login page intermittently shows blank screen",
        "description": "Users on Chrome 120+ may see a blank login page after clearing cookies. Related to a service worker caching issue.",
        "keywords": ["login", "blank", "blank screen", "white page", "can't log in", "chrome"],
        "severity": "medium",
        "status": "open",
        "workaround": "Use an incognito/private window or clear the service worker cache in DevTools > Application > Service Workers > Unregister",
        "affected_versions": ["2.4.x", "2.5.x"],
        "reported_count": 47,
        "first_reported": "2024-11-15T00:00:00Z",
        "eta_fix": "2024-12-20T00:00:00Z",
        "tags": ["auth", "ui", "chrome"],
    },
    {
        "issue_id": "KI-002",
        "title": "Billing page shows incorrect tax calculation for EU customers",
        "description": "VAT calculation for EU customers with reverse charge may show incorrect amounts on the billing summary page. The actual charge is correct — only the display is wrong.",
        "keywords": ["billing", "tax", "vat", "eu", "incorrect", "wrong amount", "tax calculation"],
        "severity": "low",
        "status": "in_progress",
        "workaround": "The actual charged amount is correct. Check your invoice PDF for the accurate tax breakdown. The billing summary display will be fixed in the next release.",
        "affected_versions": ["2.3.x", "2.4.x", "2.5.x"],
        "reported_count": 23,
        "first_reported": "2024-10-01T00:00:00Z",
        "eta_fix": "2024-12-10T00:00:00Z",
        "tags": ["billing", "tax", "display"],
    },
    {
        "issue_id": "KI-003",
        "title": "Webhook deliveries delayed during peak hours",
        "description": "Webhook deliveries for high-volume accounts may experience 5-15 minute delays during peak hours (9-11 AM and 2-4 PM UTC). The queue backlog clears automatically.",
        "keywords": ["webhook", "delayed", "delay", "slow", "not receiving", "late", "missing webhook"],
        "severity": "medium",
        "status": "in_progress",
        "workaround": "Enable webhook retry with exponential backoff. For real-time needs, consider using the Events API polling endpoint as a fallback.",
        "affected_versions": ["all"],
        "reported_count": 89,
        "first_reported": "2024-09-15T00:00:00Z",
        "eta_fix": "2025-01-15T00:00:00Z",
        "tags": ["webhook", "performance", "peak"],
    },
    {
        "issue_id": "KI-004",
        "title": "API rate limit counter not resetting correctly",
        "description": "The rate limit counter may not reset at the expected interval for some API keys, causing premature 429 responses. Affects approximately 5% of API keys.",
        "keywords": ["rate limit", "429", "too many requests", "api", "limit", "throttled"],
        "severity": "high",
        "status": "open",
        "workaround": "If receiving unexpected 429 errors, regenerate your API key in the dashboard. The new key will have a correctly resetting counter.",
        "affected_versions": ["2.4.x", "2.5.x"],
        "reported_count": 156,
        "first_reported": "2024-11-01T00:00:00Z",
        "eta_fix": "2024-12-05T00:00:00Z",
        "tags": ["api", "rate-limit", "429"],
    },
    {
        "issue_id": "KI-005",
        "title": "Chat widget fails to load on Safari 17+",
        "description": "The chat widget may not render on Safari 17+ when Intelligent Tracking Prevention is enabled. The widget container loads but the iframe is blocked.",
        "keywords": ["chat", "widget", "safari", "not loading", "chat not showing", "widget broken"],
        "severity": "medium",
        "status": "in_progress",
        "workaround": "Disable Intelligent Tracking Prevention for your domain in Safari settings, or use the direct chat URL as an alternative entry point.",
        "affected_versions": ["2.5.x"],
        "reported_count": 34,
        "first_reported": "2024-11-20T00:00:00Z",
        "eta_fix": "2024-12-15T00:00:00Z",
        "tags": ["chat", "safari", "browser"],
    },
    {
        "issue_id": "KI-006",
        "title": "Knowledge base search returns stale results after article update",
        "description": "When a KB article is updated, the search index may take up to 2 hours to reflect the changes. During this window, search results may show outdated content.",
        "keywords": ["knowledge", "kb", "search", "stale", "outdated", "old content", "not updating"],
        "severity": "low",
        "status": "open",
        "workaround": "Force a search index rebuild from Settings > Knowledge Base > Advanced > Rebuild Index. This typically resolves within 5 minutes.",
        "affected_versions": ["2.3.x", "2.4.x", "2.5.x"],
        "reported_count": 12,
        "first_reported": "2024-10-15T00:00:00Z",
        "eta_fix": "2025-01-30T00:00:00Z",
        "tags": ["knowledge-base", "search", "indexing"],
    },
    {
        "issue_id": "KI-007",
        "title": "SSO login redirect fails for Okta integrations",
        "description": "Some Okta SSO configurations fail to redirect back to the platform after successful authentication. The IdP sends the assertion but the ACS URL handling has a race condition.",
        "keywords": ["sso", "okta", "redirect", "login", "authentication", "saml", "single sign-on"],
        "severity": "high",
        "status": "in_progress",
        "workaround": "As an immediate fix, add a trailing slash to the ACS URL in your Okta SAML app configuration. For example: https://app.parwa.io/auth/saml/acs/ instead of https://app.parwa.io/auth/saml/acs",
        "affected_versions": ["2.4.x", "2.5.x"],
        "reported_count": 67,
        "first_reported": "2024-10-20T00:00:00Z",
        "eta_fix": "2024-12-01T00:00:00Z",
        "tags": ["auth", "sso", "okta", "saml"],
    },
    {
        "issue_id": "KI-008",
        "title": "Ticket assignment rules not triggering for new channels",
        "description": "Auto-assignment rules created before adding a new channel may not apply to tickets from that channel. Rules need to be re-saved to pick up new channels.",
        "keywords": ["assignment", "rules", "auto assign", "ticket", "channel", "not assigning"],
        "severity": "medium",
        "status": "open",
        "workaround": "Edit each assignment rule and click Save (even without changes). This re-registers the rule for all active channels.",
        "affected_versions": ["2.5.x"],
        "reported_count": 19,
        "first_reported": "2024-11-10T00:00:00Z",
        "eta_fix": "2024-12-25T00:00:00Z",
        "tags": ["ticket", "assignment", "rules", "channels"],
    },
    {
        "issue_id": "KI-009",
        "title": "Data export CSV contains UTF-8 encoding errors for CJK characters",
        "description": "CSV exports containing Chinese, Japanese, or Korean characters may display garbled text when opened in Excel. The data is correct — it is an encoding header issue.",
        "keywords": ["export", "csv", "encoding", "chinese", "japanese", "korean", "garbled", "utf", "excel"],
        "severity": "low",
        "status": "resolved",
        "resolution": "Fixed in v2.5.2 — BOM header added to CSV exports for proper Excel encoding detection",
        "workaround": "Open the CSV in a text editor and save with UTF-8 BOM encoding, or import via Excel's Data > From Text/CSV with UTF-8 encoding selected",
        "affected_versions": ["2.3.x", "2.4.x"],
        "fixed_in_version": "2.5.2",
        "reported_count": 31,
        "first_reported": "2024-08-01T00:00:00Z",
        "tags": ["export", "encoding", "i18n"],
    },
    {
        "issue_id": "KI-010",
        "title": "Mobile push notifications not delivered for Android 14+",
        "description": "Push notifications may not be delivered on Android 14+ devices due to new background service restrictions. The FCM token remains valid but delivery is blocked by the OS.",
        "keywords": ["push", "notification", "android", "mobile", "not receiving", "notification not delivered"],
        "severity": "high",
        "status": "in_progress",
        "workaround": "Go to Android Settings > Apps > Parwa > Notifications and ensure all notification channels are enabled. Also disable battery optimization for the Parwa app.",
        "affected_versions": ["2.5.x"],
        "reported_count": 112,
        "first_reported": "2024-11-05T00:00:00Z",
        "eta_fix": "2024-12-10T00:00:00Z",
        "tags": ["mobile", "notification", "android", "push"],
    },
]


def _keyword_match_score(query: str, keywords: list[str]) -> float:
    """Calculate keyword match score for a query against known issue keywords.

    Returns a score between 0.0 and 1.0 based on how many keywords match.
    Multi-word keyword matches are weighted higher.
    """
    if not query:
        return 0.0

    query_lower = query.lower()
    match_count = 0
    total_weight = 0.0

    for keyword in keywords:
        kw_lower = keyword.lower()
        # Multi-word keywords get higher weight
        weight = 2.0 if " " in kw_lower else 1.0
        total_weight += weight

        if kw_lower in query_lower:
            match_count += 1
        elif len(kw_lower) > 3 and kw_lower[:4] in query_lower:
            # Partial match for longer keywords
            match_count += 0.5

    if total_weight == 0:
        return 0.0

    return min(1.0, (match_count / len(keywords)) * 1.5)


# ── Tool Implementation ────────────────────────────────────────────


class KnownIssueDetectorTool(BaseReactTool):
    """ReAct tool for searching the known issue database.

    Provides:
      - search_known_issues: Search issues by keywords
      - get_issue_details: Get full details of a specific issue
      - check_issue_status: Check if a known issue is resolved
      - get_workaround: Get available workaround for an issue

    Day 3: Technical Support Diagnostic Tools — Pro tier.
    Used by the AI agent to match customer problems against known bugs
    and provide immediate resolution guidance.
    """

    def __init__(self) -> None:
        self._view_count: dict[str, int] = {}

    # ── Metadata ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "known_issue_detector"

    @property
    def description(self) -> str:
        return (
            "Search the known issue database to match customer problems "
            "against documented bugs, check resolution status, and get workarounds"
        )

    @property
    def actions(self) -> list[str]:
        return [
            "search_known_issues",
            "get_issue_details",
            "check_issue_status",
            "get_workaround",
        ]

    # ── Schema ──────────────────────────────────────────────────

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="search_known_issues",
                    description="Search known issue database by keywords from customer description",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Customer's problem description or keywords to search",
                            },
                            "severity_filter": {
                                "type": "string",
                                "description": "Filter by severity: low, medium, high",
                            },
                            "status_filter": {
                                "type": "string",
                                "description": "Filter by status: open, in_progress, resolved",
                            },
                        },
                        "required": ["query"],
                    },
                    required_params=["query"],
                    returns="List of matching known issues with relevance scores",
                ),
                ActionSchema(
                    name="get_issue_details",
                    description="Get full details of a specific known issue by ID",
                    parameters={
                        "type": "object",
                        "properties": {
                            "issue_id": {
                                "type": "string",
                                "description": "Known issue ID (e.g., KI-001)",
                            },
                        },
                        "required": ["issue_id"],
                    },
                    required_params=["issue_id"],
                    returns="Full issue details including description, workaround, and ETA",
                ),
                ActionSchema(
                    name="check_issue_status",
                    description="Check if a known issue is resolved or still open",
                    parameters={
                        "type": "object",
                        "properties": {
                            "issue_id": {
                                "type": "string",
                                "description": "Known issue ID to check",
                            },
                        },
                        "required": ["issue_id"],
                    },
                    required_params=["issue_id"],
                    returns="Issue status with resolution details if available",
                ),
                ActionSchema(
                    name="get_workaround",
                    description="Get available workaround for a known issue",
                    parameters={
                        "type": "object",
                        "properties": {
                            "issue_id": {
                                "type": "string",
                                "description": "Known issue ID to get workaround for",
                            },
                        },
                        "required": ["issue_id"],
                    },
                    required_params=["issue_id"],
                    returns="Workaround instructions and estimated time until permanent fix",
                ),
            ],
        )

    # ── Execution ───────────────────────────────────────────────

    async def _do_execute(
        self,
        action: str,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """Route action to the appropriate handler."""
        await asyncio.sleep(random.uniform(0.02, 0.08))

        if action == "__health_check__":
            return ToolResult(success=True, error=None, data={"status": "ok"}, execution_time_ms=0)

        handler = {
            "search_known_issues": self._search_known_issues,
            "get_issue_details": self._get_issue_details,
            "check_issue_status": self._check_issue_status,
            "get_workaround": self._get_workaround,
        }.get(action)

        if handler is None:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}. Available: {', '.join(self.actions)}",
                data=None,
                execution_time_ms=0,
            )

        return await handler(company_id, **params)

    # ── Action Handlers ─────────────────────────────────────────

    async def _search_known_issues(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Search known issues by keywords."""
        query: str = params.get("query", "")
        severity_filter: str | None = params.get("severity_filter")
        status_filter: str | None = params.get("status_filter")

        if not query:
            return ToolResult(
                success=False,
                error="Search query is required",
                data=None,
                execution_time_ms=0,
            )

        # Score each issue against the query
        scored_issues: list[dict[str, Any]] = []
        for issue in KNOWN_ISSUES_DB:
            # Apply filters
            if severity_filter and issue.get("severity") != severity_filter:
                continue
            if status_filter and issue.get("status") != status_filter:
                continue

            score = _keyword_match_score(query, issue.get("keywords", []))
            if score > 0:
                # Include a summary (not full details) for search results
                scored_issues.append({
                    "issue_id": issue["issue_id"],
                    "title": issue["title"],
                    "severity": issue["severity"],
                    "status": issue["status"],
                    "relevance_score": round(score, 3),
                    "reported_count": issue.get("reported_count", 0),
                    "tags": issue.get("tags", []),
                    "has_workaround": bool(issue.get("workaround")),
                })

        # Sort by relevance score (highest first)
        scored_issues.sort(key=lambda x: x["relevance_score"], reverse=True)

        # Limit to top 5 results
        scored_issues = scored_issues[:5]

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "query": query,
                "total_matches": len(scored_issues),
                "issues": scored_issues,
                "searched_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_time_ms=0,
        )

    async def _get_issue_details(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Get full details of a specific known issue."""
        issue_id: str = params.get("issue_id", "")

        issue = self._find_issue(issue_id)
        if issue is None:
            return ToolResult(
                success=False,
                error=f"Known issue not found: {issue_id}",
                data=None,
                execution_time_ms=0,
            )

        # Track view count
        self._view_count[issue_id] = self._view_count.get(issue_id, 0) + 1

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                **issue,
                "view_count": self._view_count.get(issue_id, 1),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_time_ms=0,
        )

    async def _check_issue_status(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Check if a known issue is resolved."""
        issue_id: str = params.get("issue_id", "")

        issue = self._find_issue(issue_id)
        if issue is None:
            return ToolResult(
                success=False,
                error=f"Known issue not found: {issue_id}",
                data=None,
                execution_time_ms=0,
            )

        is_resolved = issue.get("status") == "resolved"
        status_data: dict[str, Any] = {
            "company_id": company_id,
            "issue_id": issue_id,
            "title": issue["title"],
            "is_resolved": is_resolved,
            "status": issue["status"],
            "severity": issue["severity"],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        if is_resolved:
            status_data["resolution"] = issue.get("resolution", "Issue has been resolved")
            status_data["fixed_in_version"] = issue.get("fixed_in_version", "N/A")
        else:
            status_data["workaround_available"] = bool(issue.get("workaround"))
            if issue.get("eta_fix"):
                status_data["eta_fix"] = issue["eta_fix"]
                # Calculate days until fix
                try:
                    eta = datetime.fromisoformat(issue["eta_fix"].replace("Z", "+00:00"))
                    days_until = (eta - datetime.now(timezone.utc)).days
                    status_data["days_until_fix"] = max(0, days_until)
                except (ValueError, TypeError):
                    pass

        return ToolResult(
            success=True,
            error=None,
            data=status_data,
            execution_time_ms=0,
        )

    async def _get_workaround(
        self, company_id: str, **params: Any
    ) -> ToolResult:
        """Get workaround for a known issue."""
        issue_id: str = params.get("issue_id", "")

        issue = self._find_issue(issue_id)
        if issue is None:
            return ToolResult(
                success=False,
                error=f"Known issue not found: {issue_id}",
                data=None,
                execution_time_ms=0,
            )

        workaround = issue.get("workaround", "")
        if not workaround:
            return ToolResult(
                success=True,
                error=None,
                data={
                    "company_id": company_id,
                    "issue_id": issue_id,
                    "title": issue["title"],
                    "workaround_available": False,
                    "message": "No workaround is currently available for this issue. Our engineering team is working on a permanent fix.",
                    "status": issue["status"],
                    "eta_fix": issue.get("eta_fix", "TBD"),
                },
                execution_time_ms=0,
            )

        return ToolResult(
            success=True,
            error=None,
            data={
                "company_id": company_id,
                "issue_id": issue_id,
                "title": issue["title"],
                "workaround_available": True,
                "workaround": workaround,
                "severity": issue["severity"],
                "status": issue["status"],
                "eta_fix": issue.get("eta_fix", "TBD"),
                "is_temporary": True,
            },
            execution_time_ms=0,
        )

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _find_issue(issue_id: str) -> dict[str, Any] | None:
        """Find a known issue by ID."""
        for issue in KNOWN_ISSUES_DB:
            if issue["issue_id"] == issue_id:
                return issue
        return None

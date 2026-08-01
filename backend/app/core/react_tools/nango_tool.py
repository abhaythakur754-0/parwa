"""
PARWA ReAct Tool — Nango OAuth Integration (F-158)

Exposes OAuth-connected integrations to the ReAct agent via Nango:
- get_email_messages    Fetch emails from Gmail/Outlook (OAuth via Nango)
- send_email            Send email via Gmail/Outlook (OAuth via Nango)
- get_slack_channels    List Slack channels (OAuth via Nango)
- send_slack_message    Send message to Slack channel (OAuth via Nango)
- get_calendar_events   Get upcoming calendar events (Google Calendar via Nango)
- get_notion_pages      Search Notion pages (OAuth via Nango)
- get_github_issues     List GitHub issues (OAuth via Nango)
- list_connections      List all active Nango connections for this company

All actions are scoped to *company_id* (BC-001) and return structured
ToolResult (BC-008). Uses the Nango backend API to fetch data from
OAuth-connected services.

Nango Architecture:
  - Frontend SDK connects users (browser → Nango Cloud → OAuth provider)
  - Backend API fetches data (PARWA → Nango API → provider API → data)
  - This tool bridges the AI pipeline to Nango's backend API
"""

from __future__ import annotations

import logging
import time
import os
from typing import Any

import httpx

from .base import ActionSchema, BaseReactTool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

# ── Nango API configuration ──────────────────────────────────────
# The secret key is stored in the NANGO_SECRET_KEY env var.
# The public key is used by the frontend SDK (already configured).
NANGO_HOST = os.environ.get("NANGO_HOST", "https://api.nango.dev")
NANGO_SECRET_KEY = os.environ.get("NANGO_SECRET_KEY", "")
NANGO_TIMEOUT = 15.0

# ── Provider mapping ─────────────────────────────────────────────
# Maps Nango provider keys to human-readable names for the AI.
NANGO_PROVIDERS = {
    "google-mail": "Gmail",
    "outlook": "Outlook",
    "slack": "Slack",
    "google-calendar": "Google Calendar",
    "notion": "Notion",
    "github": "GitHub",
    "google-sheet": "Google Sheets",
    "google-drive": "Google Drive",
    "jira": "Jira",
    "salesforce": "Salesforce",
    "whatsapp": "WhatsApp",
    "hubspot": "HubSpot (OAuth)",
}


def _nango_headers() -> dict[str, str]:
    """Build auth headers for Nango backend API."""
    return {
        "Authorization": f"Bearer {NANGO_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _connection_id_for_company(company_id: str) -> str:
    """Generate the Nango connection ID for a given company.

    This MUST match the connectionId used by the frontend SDK when
    initiating the OAuth flow. We use company_id as the connection ID
    so each company has one set of connections.
    """
    return f"parwa-{company_id}"


async def _nango_get(
    provider: str,
    connection_id: str,
    path: str,
    params: dict | None = None,
) -> dict[str, Any] | None:
    """Make a GET request to Nango's proxy API.

    Nango handles OAuth token refresh, rate limits, and pagination
    automatically. We just specify the provider + connection + path.
    """
    url = f"{NANGO_HOST}/proxy/{path}"
    headers = _nango_headers()
    # Nango proxy requires provider + connection in headers
    headers["Nango-Provider"] = provider
    headers["Nango-Connection-Id"] = connection_id

    try:
        async with httpx.AsyncClient(timeout=NANGO_TIMEOUT) as client:
            resp = await client.get(url, headers=headers, params=params or {})
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                logger.warning(
                    "nango_proxy_not_found provider=%s connection=%s path=%s",
                    provider, connection_id, path,
                )
                return None
            else:
                logger.warning(
                    "nango_proxy_error provider=%s path=%s status=%d body=%s",
                    provider, path, resp.status_code, resp.text[:200],
                )
                return None
    except Exception as exc:
        logger.warning("nango_proxy_exception path=%s error=%s", path, str(exc)[:200])
        return None


async def _nango_post(
    provider: str,
    connection_id: str,
    path: str,
    body: dict[str, Any],
) -> dict[str, Any] | None:
    """Make a POST request to Nango's proxy API."""
    url = f"{NANGO_HOST}/proxy/{path}"
    headers = _nango_headers()
    headers["Nango-Provider"] = provider
    headers["Nango-Connection-Id"] = connection_id

    try:
        async with httpx.AsyncClient(timeout=NANGO_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                logger.warning(
                    "nango_proxy_post_error provider=%s path=%s status=%d body=%s",
                    provider, path, resp.status_code, resp.text[:200],
                )
                return None
    except Exception as exc:
        logger.warning("nango_proxy_post_exception path=%s error=%s", path, str(exc)[:200])
        return None


async def _list_connections(connection_id: str) -> list[dict[str, Any]]:
    """List all active Nango connections for a company."""
    url = f"{NANGO_HOST}/connection"
    headers = _nango_headers()
    headers["Nango-Connection-Id"] = connection_id

    try:
        async with httpx.AsyncClient(timeout=NANGO_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                return data.get("connections", [])
            return []
    except Exception:
        return []


# ── NangoTool ────────────────────────────────────────────────────


class NangoTool(BaseReactTool):
    """
    ReAct tool that bridges the AI pipeline to Nango OAuth integrations.

    When a user connects Gmail via Nango on the integrations page,
    the AI can use this tool to:
    - Read incoming customer emails
    - Send replies on behalf of the user
    - Check Slack for team context
    - Look up calendar events
    - Search Notion KB
    - Check GitHub issues
    """

    EXECUTION_TIMEOUT: int = 15  # Nango API can be slow

    @property
    def name(self) -> str:
        return "nango"

    @property
    def description(self) -> str:
        return (
            "Access OAuth-connected integrations (Gmail, Slack, GitHub, Notion, "
            "Calendar) via Nango. Use list_connections to see what's connected, "
            "then use specific actions to fetch/send data."
        )

    @property
    def actions(self) -> list[str]:
        return [
            "list_connections",
            "get_email_messages",
            "send_email",
            "get_slack_channels",
            "send_slack_message",
            "get_calendar_events",
            "get_notion_pages",
            "get_github_issues",
        ]

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="list_connections",
                    description="List all connected OAuth integrations for this company",
                    parameters={},
                    required_params=[],
                    returns="List of connected providers (Gmail, Slack, etc.)",
                ),
                ActionSchema(
                    name="get_email_messages",
                    description="Fetch recent emails from Gmail or Outlook",
                    parameters={
                        "provider": "string - 'google-mail' for Gmail, 'outlook' for Outlook",
                        "max_results": "integer - max emails to fetch (default 10)",
                        "query": "string - search query (optional)",
                    },
                    required_params=["provider"],
                    returns="List of email messages with subject, from, date, body",
                ),
                ActionSchema(
                    name="send_email",
                    description="Send an email via Gmail or Outlook",
                    parameters={
                        "provider": "string - 'google-mail' or 'outlook'",
                        "to": "string - recipient email address",
                        "subject": "string - email subject",
                        "body": "string - email body (plain text)",
                    },
                    required_params=["provider", "to", "subject", "body"],
                    returns="Success/failure confirmation",
                ),
                ActionSchema(
                    name="get_slack_channels",
                    description="List Slack channels for team notifications",
                    parameters={
                        "max_results": "integer - max channels (default 20)",
                    },
                    required_params=[],
                    returns="List of Slack channels with names and IDs",
                ),
                ActionSchema(
                    name="send_slack_message",
                    description="Send a message to a Slack channel",
                    parameters={
                        "channel": "string - channel name or ID",
                        "message": "string - message text to send",
                    },
                    required_params=["channel", "message"],
                    returns="Success/failure confirmation",
                ),
                ActionSchema(
                    name="get_calendar_events",
                    description="Get upcoming calendar events from Google Calendar",
                    parameters={
                        "max_results": "integer - max events (default 10)",
                        "days_ahead": "integer - how many days ahead (default 7)",
                    },
                    required_params=[],
                    returns="List of calendar events with title, start, end",
                ),
                ActionSchema(
                    name="get_notion_pages",
                    description="Search Notion pages for knowledge base content",
                    parameters={
                        "query": "string - search query",
                        "max_results": "integer - max pages (default 5)",
                    },
                    required_params=["query"],
                    returns="List of Notion pages with title and URL",
                ),
                ActionSchema(
                    name="get_github_issues",
                    description="List GitHub issues from connected repositories",
                    parameters={
                        "repo": "string - repository name (owner/repo)",
                        "state": "string - 'open', 'closed', or 'all' (default 'open')",
                        "max_results": "integer - max issues (default 10)",
                    },
                    required_params=[],
                    returns="List of GitHub issues with title, number, state",
                ),
            ],
        )

    async def _do_execute(
        self,
        action: str,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """Execute a Nango integration action."""
        start = time.monotonic()
        conn_id = _connection_id_for_company(company_id)

        # If Nango secret key is not configured, return helpful error
        if not NANGO_SECRET_KEY:
            return ToolResult(
                success=False,
                error="NANGO_SECRET_KEY not configured. Set it in Render environment variables.",
                data=None,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                action=action,
                tool_name=self.name,
            )

        try:
            if action == "list_connections":
                return await self._list_connections(conn_id, start)
            elif action == "get_email_messages":
                return await self._get_email_messages(conn_id, params, start)
            elif action == "send_email":
                return await self._send_email(conn_id, params, start)
            elif action == "get_slack_channels":
                return await self._get_slack_channels(conn_id, params, start)
            elif action == "send_slack_message":
                return await self._send_slack_message(conn_id, params, start)
            elif action == "get_calendar_events":
                return await self._get_calendar_events(conn_id, params, start)
            elif action == "get_notion_pages":
                return await self._get_notion_pages(conn_id, params, start)
            elif action == "get_github_issues":
                return await self._get_github_issues(conn_id, params, start)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}",
                    data=None,
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                    action=action,
                    tool_name=self.name,
                )
        except Exception as exc:
            logger.error("nango_tool_error action=%s error=%s", action, str(exc)[:200])
            return ToolResult(
                success=False,
                error=f"Nango tool error: {str(exc)[:200]}",
                data=None,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                action=action,
                tool_name=self.name,
            )

    # ── Action implementations ────────────────────────────────────

    async def _list_connections(self, conn_id: str, start: float) -> ToolResult:
        """List all connected OAuth integrations."""
        connections = await _list_connections(conn_id)
        active = []
        for c in connections:
            provider = c.get("provider", c.get("providerConfigKey", ""))
            name = NANGO_PROVIDERS.get(provider, provider)
            active.append({
                "provider": provider,
                "name": name,
                "connected": True,
                "created_at": c.get("created_at", ""),
            })

        return ToolResult(
            success=True,
            error=None,
            data={"connections": active, "total": len(active)},
            execution_time_ms=int((time.monotonic() - start) * 1000),
            action="list_connections",
            tool_name=self.name,
        )

    async def _get_email_messages(self, conn_id: str, params: dict, start: float) -> ToolResult:
        """Fetch emails from Gmail or Outlook via Nango."""
        provider = params.get("provider", "google-mail")
        max_results = params.get("max_results", 10)

        if provider == "google-mail":
            # Gmail API: list messages
            data = await _nango_get(provider, conn_id, "gmail/v1/users/me/messages",
                                    {"maxResults": max_results})
            if data and "messages" in data:
                # Fetch each message detail
                messages = []
                for msg_ref in data["messages"][:max_results]:
                    msg_id = msg_ref.get("id", "")
                    if msg_id:
                        msg = await _nango_get(provider, conn_id, f"gmail/v1/users/me/messages/{msg_id}",
                                               {"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]})
                        if msg:
                            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                            messages.append({
                                "id": msg_id,
                                "subject": headers.get("Subject", "(no subject)"),
                                "from": headers.get("From", ""),
                                "date": headers.get("Date", ""),
                                "snippet": msg.get("snippet", ""),
                            })
                return ToolResult(
                    success=True, error=None,
                    data={"messages": messages, "count": len(messages)},
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                    action="get_email_messages", tool_name=self.name,
                )
        elif provider == "outlook":
            # Outlook API: list messages
            data = await _nango_get(provider, conn_id, "v1.0/me/messages",
                                    {"$top": max_results, "$select": "subject,from,receivedDateTime,bodyPreview"})
            if data and "value" in data:
                messages = [{
                    "id": m.get("id", ""),
                    "subject": m.get("subject", ""),
                    "from": m.get("from", {}).get("emailAddress", {}).get("address", ""),
                    "date": m.get("receivedDateTime", ""),
                    "snippet": m.get("bodyPreview", ""),
                } for m in data["value"]]
                return ToolResult(
                    success=True, error=None,
                    data={"messages": messages, "count": len(messages)},
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                    action="get_email_messages", tool_name=self.name,
                )

        return ToolResult(
            success=False,
            error=f"No {NANGO_PROVIDERS.get(provider, provider)} connection found. User needs to connect it first.",
            data=None,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            action="get_email_messages",
            tool_name=self.name,
        )

    async def _send_email(self, conn_id: str, params: dict, start: float) -> ToolResult:
        """Send email via Gmail or Outlook."""
        provider = params.get("provider", "google-mail")
        to = params.get("to", "")
        subject = params.get("subject", "")
        body = params.get("body", "")

        if not to or not subject or not body:
            return ToolResult(
                success=False, error="Missing required params: to, subject, body",
                data=None,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                action="send_email", tool_name=self.name,
            )

        if provider == "google-mail":
            # Gmail: send via Nango proxy
            import base64
            raw_message = f"To: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}"
            encoded = base64.urlsafe_b64encode(raw_message.encode("utf-8")).decode("ascii")
            result = await _nango_post(provider, conn_id, "gmail/v1/users/me/messages/send",
                                       {"raw": encoded})
            if result and "id" in result:
                return ToolResult(
                    success=True, error=None,
                    data={"message_id": result["id"], "sent": True},
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                    action="send_email", tool_name=self.name,
                )
        elif provider == "outlook":
            result = await _nango_post(provider, conn_id, "v1.0/me/sendMail",
                                       {"message": {"subject": subject, "body": {"contentType": "Text", "content": body},
                                                    "toRecipients": [{"emailAddress": {"address": to}}]}})
            if result is not None:
                return ToolResult(
                    success=True, error=None,
                    data={"sent": True},
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                    action="send_email", tool_name=self.name,
                )

        return ToolResult(
            success=False,
            error=f"Failed to send email via {NANGO_PROVIDERS.get(provider, provider)}. Connection may not be active.",
            data=None,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            action="send_email",
            tool_name=self.name,
        )

    async def _get_slack_channels(self, conn_id: str, params: dict, start: float) -> ToolResult:
        """List Slack channels."""
        max_results = params.get("max_results", 20)
        data = await _nango_get("slack", conn_id, "conversations.list",
                                {"limit": max_results, "types": "public_channel,private_channel"})

        if data and "channels" in data:
            channels = [{
                "id": c.get("id", ""),
                "name": c.get("name", ""),
                "is_private": c.get("is_private", False),
                "num_members": c.get("num_members", 0),
            } for c in data["channels"]]
            return ToolResult(
                success=True, error=None,
                data={"channels": channels, "count": len(channels)},
                execution_time_ms=int((time.monotonic() - start) * 1000),
                action="get_slack_channels", tool_name=self.name,
            )

        return ToolResult(
            success=False, error="No Slack connection found or no channels returned.",
            data=None,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            action="get_slack_channels", tool_name=self.name,
        )

    async def _send_slack_message(self, conn_id: str, params: dict, start: float) -> ToolResult:
        """Send message to Slack channel."""
        channel = params.get("channel", "")
        message = params.get("message", "")

        if not channel or not message:
            return ToolResult(
                success=False, error="Missing required params: channel, message",
                data=None,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                action="send_slack_message", tool_name=self.name,
            )

        result = await _nango_post("slack", conn_id, "chat.postMessage",
                                   {"channel": channel, "text": message})

        if result and result.get("ok"):
            return ToolResult(
                success=True, error=None,
                data={"sent": True, "channel": channel, "ts": result.get("ts", "")},
                execution_time_ms=int((time.monotonic() - start) * 1000),
                action="send_slack_message", tool_name=self.name,
            )

        return ToolResult(
            success=False, error="Failed to send Slack message. Connection may not be active.",
            data=None,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            action="send_slack_message", tool_name=self.name,
        )

    async def _get_calendar_events(self, conn_id: str, params: dict, start: float) -> ToolResult:
        """Get upcoming Google Calendar events."""
        from datetime import datetime, timedelta, timezone
        max_results = params.get("max_results", 10)
        days_ahead = params.get("days_ahead", 7)

        time_min = datetime.now(timezone.utc).isoformat()
        time_max = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()

        data = await _nango_get("google-calendar", conn_id, "calendar/v3/calendars/primary/events",
                                {"maxResults": max_results, "timeMin": time_min,
                                 "timeMax": time_max, "singleEvents": True, "orderBy": "startTime"})

        if data and "items" in data:
            events = [{
                "id": e.get("id", ""),
                "summary": e.get("summary", "(no title)"),
                "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
                "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
                "location": e.get("location", ""),
            } for e in data["items"]]
            return ToolResult(
                success=True, error=None,
                data={"events": events, "count": len(events)},
                execution_time_ms=int((time.monotonic() - start) * 1000),
                action="get_calendar_events", tool_name=self.name,
            )

        return ToolResult(
            success=False, error="No Google Calendar connection found.",
            data=None,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            action="get_calendar_events", tool_name=self.name,
        )

    async def _get_notion_pages(self, conn_id: str, params: dict, start: float) -> ToolResult:
        """Search Notion pages."""
        query = params.get("query", "")
        max_results = params.get("max_results", 5)

        result = await _nango_post("notion", conn_id, "v1/search",
                                   {"query": query, "page_size": max_results})

        if result and "results" in result:
            pages = [{
                "id": p.get("id", ""),
                "title": self._extract_notion_title(p),
                "url": p.get("url", ""),
                "last_edited": p.get("last_edited_time", ""),
            } for p in result["results"]]
            return ToolResult(
                success=True, error=None,
                data={"pages": pages, "count": len(pages)},
                execution_time_ms=int((time.monotonic() - start) * 1000),
                action="get_notion_pages", tool_name=self.name,
            )

        return ToolResult(
            success=False, error="No Notion connection found or no results.",
            data=None,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            action="get_notion_pages", tool_name=self.name,
        )

    def _extract_notion_title(self, page: dict) -> str:
        """Extract title from Notion page object."""
        try:
            props = page.get("properties", {})
            for prop in props.values():
                if prop.get("type") == "title":
                    title_parts = prop.get("title", [])
                    if title_parts:
                        return "".join(t.get("plain_text", "") for t in title_parts)
        except Exception:
            pass
        return "(untitled)"

    async def _get_github_issues(self, conn_id: str, params: dict, start: float) -> ToolResult:
        """List GitHub issues."""
        repo = params.get("repo", "")
        state = params.get("state", "open")
        max_results = params.get("max_results", 10)

        if repo:
            path = f"repos/{repo}/issues"
        else:
            # List issues across all repos
            path = "issues"

        data = await _nango_get("github", conn_id, path,
                                {"state": state, "per_page": max_results})

        if data and isinstance(data, list):
            issues = [{
                "number": i.get("number", ""),
                "title": i.get("title", ""),
                "state": i.get("state", ""),
                "url": i.get("html_url", ""),
                "created_at": i.get("created_at", ""),
            } for i in data if "pull_request" not in i]  # Exclude PRs
            return ToolResult(
                success=True, error=None,
                data={"issues": issues, "count": len(issues)},
                execution_time_ms=int((time.monotonic() - start) * 1000),
                action="get_github_issues", tool_name=self.name,
            )

        return ToolResult(
            success=False, error="No GitHub connection found or no issues returned.",
            data=None,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            action="get_github_issues", tool_name=self.name,
        )

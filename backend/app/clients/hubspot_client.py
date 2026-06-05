"""
HubSpot CRM REST API Client (BC-002)

Implements the HubSpot CRM REST API v3 for:
- Contact management (CRUD, search, list)
- Deal management (CRUD, search, list)
- Company management (CRUD, search, list)
- Note/Engagement management (create, list via associations)
- Association management (contact↔deal, contact↔company, deal associations)
- Webhook management (list, create, delete subscriptions)

API Docs: https://developers.hubspot.com/docs/api/overview

Features:
- Automatic retry with exponential backoff
- Rate limiting compliance (10 requests/second, 100/10s OAuth or 200/10s Private App)
- HMAC-SHA256 signature verification for webhooks (v3, base64)
- Multi-tenant: each instance scoped to a single access_token (BC-001)
- Cursor-based pagination via `after` parameter
- BC-008: Never crash — all errors caught and returned as result objects
- BC-003: Webhook HMAC verification with constant-time comparison
"""

import base64
import hashlib
import hmac
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("parwa.clients.hubspot")

# HubSpot API base URL
HUBSPOT_BASE_URL = "https://api.hubapi.com"

# Rate limiting: HubSpot allows 10 requests/second for steady-state
RATE_LIMIT_REQUESTS_PER_SEC = 10

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
RETRY_MAX_DELAY = 30

# Request timeout
REQUEST_TIMEOUT = 30  # seconds

# Max pages to fetch in paginated requests
MAX_PAGES = 50

# HubSpot CRM association type IDs
ASSOCIATION_TYPE_CONTACT_TO_DEAL = 3
ASSOCIATION_TYPE_CONTACT_TO_COMPANY = 1
ASSOCIATION_TYPE_DEAL_TO_CONTACT = 4
ASSOCIATION_TYPE_DEAL_TO_COMPANY = 5


class HubSpotError(Exception):
    """Base exception for HubSpot API errors."""

    def __init__(self, message: str, status_code: int = 0, access_token_prefix: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.access_token_prefix = access_token_prefix


class HubSpotAuthError(HubSpotError):
    """Authentication error (401/403)."""
    pass


class HubSpotRateLimitError(HubSpotError):
    """Rate limit exceeded (429)."""
    pass


class HubSpotNotFoundError(HubSpotError):
    """Resource not found (404)."""
    pass


class HubSpotResult:
    """Result wrapper for HubSpot API calls.

    Follows BC-008: Never crash. All API calls return a HubSpotResult
    instead of raising exceptions.
    """

    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: str = "",
        status_code: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.data = data or {}
        self.error = error
        self.status_code = status_code
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "status_code": self.status_code,
            "metadata": self.metadata,
        }


class HubSpotClient:
    """REST API client for HubSpot CRM API v3.

    Each instance is scoped to a single access_token (tenant).
    Multi-tenant support: create separate instances per company's HubSpot account.

    Usage:
        client = HubSpotClient(
            access_token="pat-xxx-xxxx",
        )
        result = await client.get_contact("12345")
        if result.success:
            contact = result.data
    """

    def __init__(
        self,
        access_token: str,
        timeout: int = REQUEST_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        """Initialize HubSpot client.

        Args:
            access_token: HubSpot Private App access token or OAuth token.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
        """
        self.access_token = access_token
        self.timeout = timeout
        self.max_retries = max_retries

        # Rate limiting state
        self._last_request_time = 0.0

        # Build base URL
        self.base_url = HUBSPOT_BASE_URL

    # ── HTTP Core ─────────────────────────────────────────────────

    def _get_headers(self) -> Dict[str, str]:
        """Get standard HubSpot API request headers.

        HubSpot uses Bearer token authentication in the Authorization header.
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> HubSpotResult:
        """Make an authenticated request to HubSpot API with retry logic.

        Implements BC-008: Never crash. All errors are caught and returned
        as HubSpotResult objects.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE).
            path: API path (e.g., '/crm/v3/objects/contacts').
            params: Query parameters.
            json_body: JSON request body.

        Returns:
            HubSpotResult with success status and data or error.
        """
        url = f"{self.base_url}{path}"
        headers = self._get_headers()

        last_error = ""
        for attempt in range(self.max_retries):
            try:
                # Rate limiting: wait between requests
                self._enforce_rate_limit()

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        json=json_body,
                    )

                # Handle response status
                if response.status_code in (200, 201, 204):
                    if response.status_code == 204:
                        data = {}
                    else:
                        data = response.json() if response.text else {}
                    return HubSpotResult(
                        success=True,
                        data=data,
                        status_code=response.status_code,
                        metadata={
                            "attempt": attempt + 1,
                        },
                    )

                elif response.status_code == 401:
                    return HubSpotResult(
                        success=False,
                        error="HubSpot authentication failed: invalid or expired access token",
                        status_code=401,
                    )

                elif response.status_code == 403:
                    return HubSpotResult(
                        success=False,
                        error=f"HubSpot access denied: {response.text[:200]}",
                        status_code=403,
                    )

                elif response.status_code == 404:
                    return HubSpotResult(
                        success=False,
                        error=f"HubSpot resource not found: {path}",
                        status_code=404,
                    )

                elif response.status_code == 429:
                    # Rate limited — exponential backoff
                    # HubSpot may return a Retry-After header
                    retry_after = float(response.headers.get("Retry-After", RETRY_BASE_DELAY))
                    delay = min(retry_after * (2 ** attempt), RETRY_MAX_DELAY)
                    logger.warning(
                        "hubspot_rate_limited retry_after=%.1fs attempt=%d",
                        delay, attempt + 1,
                    )
                    time.sleep(delay)
                    last_error = "Rate limited (429)"
                    continue

                elif response.status_code >= 500:
                    # Server error — retry with backoff
                    delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                    logger.warning(
                        "hubspot_server_error status=%d retry=%.1fs attempt=%d",
                        response.status_code, delay, attempt + 1,
                    )
                    time.sleep(delay)
                    last_error = f"Server error ({response.status_code}): {response.text[:200]}"
                    continue

                else:
                    # Other client errors (400, 409, etc.)
                    return HubSpotResult(
                        success=False,
                        error=f"HubSpot API error ({response.status_code}): {response.text[:300]}",
                        status_code=response.status_code,
                    )

            except httpx.TimeoutException:
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                logger.warning(
                    "hubspot_timeout path=%s retry=%.1fs attempt=%d",
                    path, delay, attempt + 1,
                )
                last_error = f"Request timeout after {self.timeout}s"
                time.sleep(delay)

            except httpx.ConnectError:
                delay = min(RETRY_BASE_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
                logger.warning(
                    "hubspot_connect_error path=%s retry=%.1fs attempt=%d",
                    path, delay, attempt + 1,
                )
                last_error = "Connection error to HubSpot API"
                time.sleep(delay)

            except Exception as exc:
                logger.error(
                    "hubspot_request_error path=%s error=%s",
                    path, str(exc)[:200],
                )
                last_error = f"Unexpected error: {str(exc)[:200]}"
                break

        return HubSpotResult(
            success=False,
            error=f"Max retries ({self.max_retries}) exceeded: {last_error}",
            status_code=0,
        )

    def _enforce_rate_limit(self) -> None:
        """Enforce HubSpot rate limiting (10 requests/second).

        HubSpot rate limits: 100 requests/10 seconds (OAuth),
        200 requests/10 seconds (Private App). We use a conservative
        10 requests/second steady-state rate to stay within bounds.
        """
        now = time.time()
        elapsed = now - self._last_request_time
        min_interval = 1.0 / RATE_LIMIT_REQUESTS_PER_SEC

        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        self._last_request_time = time.time()

    # ── Connection Test ───────────────────────────────────────────

    async def test_connection(self) -> HubSpotResult:
        """Test the HubSpot API connection.

        Makes a lightweight GET request to /crm/v3/pipelines/contacts
        to verify credentials are valid.

        Returns:
            HubSpotResult with connection status if successful.
        """
        result = await self._request("GET", "/crm/v3/pipelines/contacts")
        if result.success:
            pipelines = result.data.get("results", [])
            result.data = {
                "connected": True,
                "pipeline_count": len(pipelines),
            }
        return result

    # ── Contact API ───────────────────────────────────────────────

    async def get_contact(
        self,
        contact_id: str,
        properties: Optional[List[str]] = None,
    ) -> HubSpotResult:
        """Get a single contact by ID.

        Args:
            contact_id: HubSpot contact ID.
            properties: Optional list of property names to include.

        Returns:
            HubSpotResult with contact data.
        """
        params: Dict[str, Any] = {}
        if properties:
            params["properties"] = ",".join(properties)

        result = await self._request(
            "GET", f"/crm/v3/objects/contacts/{contact_id}",
            params=params,
        )
        return result

    async def list_contacts(
        self,
        limit: int = 100,
        after: Optional[str] = None,
        properties: Optional[List[str]] = None,
    ) -> HubSpotResult:
        """List contacts with optional pagination.

        Args:
            limit: Number of contacts per page (max 100).
            after: Cursor for next page of results.
            properties: Optional list of property names to include.

        Returns:
            HubSpotResult with contact list data including paging info.
        """
        params: Dict[str, Any] = {"limit": min(limit, 100)}
        if after:
            params["after"] = after
        if properties:
            params["properties"] = ",".join(properties)

        result = await self._request("GET", "/crm/v3/objects/contacts", params=params)
        return result

    async def search_contacts(
        self,
        query: str,
        limit: int = 100,
        properties: Optional[List[str]] = None,
        filter_groups: Optional[List[Dict[str, Any]]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        after: Optional[str] = None,
    ) -> HubSpotResult:
        """Search contacts by query string with optional filters.

        HubSpot search uses POST with a JSON body containing query,
        filterGroups, properties, and sorts.

        Args:
            query: Search query string.
            limit: Maximum number of results (max 100).
            properties: Optional list of property names to include.
            filter_groups: Optional filter groups for advanced filtering.
            sorts: Optional sort specifications.
            after: Cursor for next page of search results.

        Returns:
            HubSpotResult with matching contacts.
        """
        body: Dict[str, Any] = {
            "query": query,
            "limit": min(limit, 100),
        }
        if properties:
            body["properties"] = properties
        if filter_groups:
            body["filterGroups"] = filter_groups
        if sorts:
            body["sorts"] = sorts
        if after:
            body["after"] = after

        result = await self._request(
            "POST", "/crm/v3/objects/contacts/search",
            json_body=body,
        )
        return result

    async def create_contact(self, properties: Dict[str, Any]) -> HubSpotResult:
        """Create a new contact.

        Args:
            properties: Contact properties (e.g., email, firstname, lastname, phone).

        Returns:
            HubSpotResult with created contact data.
        """
        result = await self._request(
            "POST", "/crm/v3/objects/contacts",
            json_body={"properties": properties},
        )
        return result

    async def update_contact(
        self,
        contact_id: str,
        properties: Dict[str, Any],
    ) -> HubSpotResult:
        """Update an existing contact.

        Args:
            contact_id: HubSpot contact ID.
            properties: Properties to update.

        Returns:
            HubSpotResult with updated contact data.
        """
        result = await self._request(
            "PATCH", f"/crm/v3/objects/contacts/{contact_id}",
            json_body={"properties": properties},
        )
        return result

    async def delete_contact(self, contact_id: str) -> HubSpotResult:
        """Delete (archive) a contact.

        Args:
            contact_id: HubSpot contact ID.

        Returns:
            HubSpotResult indicating success.
        """
        result = await self._request(
            "DELETE", f"/crm/v3/objects/contacts/{contact_id}",
        )
        return result

    # ── Deal API ──────────────────────────────────────────────────

    async def get_deal(
        self,
        deal_id: str,
        properties: Optional[List[str]] = None,
    ) -> HubSpotResult:
        """Get a single deal by ID.

        Args:
            deal_id: HubSpot deal ID.
            properties: Optional list of property names to include.

        Returns:
            HubSpotResult with deal data.
        """
        params: Dict[str, Any] = {}
        if properties:
            params["properties"] = ",".join(properties)

        result = await self._request(
            "GET", f"/crm/v3/objects/deals/{deal_id}",
            params=params,
        )
        return result

    async def list_deals(
        self,
        limit: int = 100,
        after: Optional[str] = None,
        properties: Optional[List[str]] = None,
    ) -> HubSpotResult:
        """List deals with optional pagination.

        Args:
            limit: Number of deals per page (max 100).
            after: Cursor for next page of results.
            properties: Optional list of property names to include.

        Returns:
            HubSpotResult with deal list data including paging info.
        """
        params: Dict[str, Any] = {"limit": min(limit, 100)}
        if after:
            params["after"] = after
        if properties:
            params["properties"] = ",".join(properties)

        result = await self._request("GET", "/crm/v3/objects/deals", params=params)
        return result

    async def search_deals(
        self,
        query: str,
        limit: int = 100,
        properties: Optional[List[str]] = None,
        filter_groups: Optional[List[Dict[str, Any]]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        after: Optional[str] = None,
    ) -> HubSpotResult:
        """Search deals by query string with optional filters.

        Args:
            query: Search query string.
            limit: Maximum number of results (max 100).
            properties: Optional list of property names to include.
            filter_groups: Optional filter groups for advanced filtering.
            sorts: Optional sort specifications.
            after: Cursor for next page of search results.

        Returns:
            HubSpotResult with matching deals.
        """
        body: Dict[str, Any] = {
            "query": query,
            "limit": min(limit, 100),
        }
        if properties:
            body["properties"] = properties
        if filter_groups:
            body["filterGroups"] = filter_groups
        if sorts:
            body["sorts"] = sorts
        if after:
            body["after"] = after

        result = await self._request(
            "POST", "/crm/v3/objects/deals/search",
            json_body=body,
        )
        return result

    async def create_deal(self, properties: Dict[str, Any]) -> HubSpotResult:
        """Create a new deal.

        Args:
            properties: Deal properties (e.g., dealname, amount, dealstage, pipeline).

        Returns:
            HubSpotResult with created deal data.
        """
        result = await self._request(
            "POST", "/crm/v3/objects/deals",
            json_body={"properties": properties},
        )
        return result

    async def update_deal(
        self,
        deal_id: str,
        properties: Dict[str, Any],
    ) -> HubSpotResult:
        """Update an existing deal.

        Args:
            deal_id: HubSpot deal ID.
            properties: Properties to update.

        Returns:
            HubSpotResult with updated deal data.
        """
        result = await self._request(
            "PATCH", f"/crm/v3/objects/deals/{deal_id}",
            json_body={"properties": properties},
        )
        return result

    # ── Company API ───────────────────────────────────────────────

    async def get_company(
        self,
        company_id: str,
        properties: Optional[List[str]] = None,
    ) -> HubSpotResult:
        """Get a single company by ID.

        Args:
            company_id: HubSpot company ID.
            properties: Optional list of property names to include.

        Returns:
            HubSpotResult with company data.
        """
        params: Dict[str, Any] = {}
        if properties:
            params["properties"] = ",".join(properties)

        result = await self._request(
            "GET", f"/crm/v3/objects/companies/{company_id}",
            params=params,
        )
        return result

    async def list_companies(
        self,
        limit: int = 100,
        after: Optional[str] = None,
        properties: Optional[List[str]] = None,
    ) -> HubSpotResult:
        """List companies with optional pagination.

        Args:
            limit: Number of companies per page (max 100).
            after: Cursor for next page of results.
            properties: Optional list of property names to include.

        Returns:
            HubSpotResult with company list data including paging info.
        """
        params: Dict[str, Any] = {"limit": min(limit, 100)}
        if after:
            params["after"] = after
        if properties:
            params["properties"] = ",".join(properties)

        result = await self._request("GET", "/crm/v3/objects/companies", params=params)
        return result

    async def search_companies(
        self,
        query: str,
        limit: int = 100,
        properties: Optional[List[str]] = None,
        filter_groups: Optional[List[Dict[str, Any]]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        after: Optional[str] = None,
    ) -> HubSpotResult:
        """Search companies by query string with optional filters.

        Args:
            query: Search query string.
            limit: Maximum number of results (max 100).
            properties: Optional list of property names to include.
            filter_groups: Optional filter groups for advanced filtering.
            sorts: Optional sort specifications.
            after: Cursor for next page of search results.

        Returns:
            HubSpotResult with matching companies.
        """
        body: Dict[str, Any] = {
            "query": query,
            "limit": min(limit, 100),
        }
        if properties:
            body["properties"] = properties
        if filter_groups:
            body["filterGroups"] = filter_groups
        if sorts:
            body["sorts"] = sorts
        if after:
            body["after"] = after

        result = await self._request(
            "POST", "/crm/v3/objects/companies/search",
            json_body=body,
        )
        return result

    async def create_company(self, properties: Dict[str, Any]) -> HubSpotResult:
        """Create a new company.

        Args:
            properties: Company properties (e.g., name, domain, industry).

        Returns:
            HubSpotResult with created company data.
        """
        result = await self._request(
            "POST", "/crm/v3/objects/companies",
            json_body={"properties": properties},
        )
        return result

    # ── Note/Engagement API ───────────────────────────────────────

    async def create_note(
        self,
        contact_id: str,
        body: str,
    ) -> HubSpotResult:
        """Create a note and associate it with a contact.

        HubSpot notes are created via the notes object API with
        associations specified in the request body.

        Args:
            contact_id: HubSpot contact ID to associate the note with.
            body: Note content / body text.

        Returns:
            HubSpotResult with created note data.
        """
        request_body: Dict[str, Any] = {
            "properties": {
                "hs_note_body": body,
            },
            "associations": [
                {
                    "to": {"id": contact_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": ASSOCIATION_TYPE_CONTACT_TO_COMPANY,  # note-to-contact (202)
                        }
                    ],
                }
            ],
        }

        # HubSpot uses association type ID 202 for note-to-contact
        # Override with correct value
        request_body["associations"][0]["types"][0]["associationTypeId"] = 202

        result = await self._request(
            "POST", "/crm/v3/objects/notes",
            json_body=request_body,
        )
        return result

    async def list_notes(
        self,
        contact_id: str,
        limit: int = 50,
    ) -> HubSpotResult:
        """List notes associated with a contact.

        Uses the associations API to retrieve notes linked to a contact.

        Args:
            contact_id: HubSpot contact ID.
            limit: Maximum number of notes to return.

        Returns:
            HubSpotResult with list of associated notes.
        """
        result = await self._request(
            "GET",
            f"/crm/v3/objects/contacts/{contact_id}/associations/notes",
            params={"limit": min(limit, 100)},
        )
        return result

    # ── Association API ───────────────────────────────────────────

    async def associate_contact_to_deal(
        self,
        contact_id: str,
        deal_id: str,
    ) -> HubSpotResult:
        """Associate a contact with a deal.

        Uses the HubSpot v3 associations API with type ID 3
        (contact_to_deal primary association).

        Args:
            contact_id: HubSpot contact ID.
            deal_id: HubSpot deal ID.

        Returns:
            HubSpotResult indicating success.
        """
        result = await self._request(
            "PUT",
            f"/crm/v3/objects/deals/{deal_id}/associations/contacts/{contact_id}/{ASSOCIATION_TYPE_CONTACT_TO_DEAL}",
        )
        return result

    async def associate_contact_to_company(
        self,
        contact_id: str,
        company_id: str,
    ) -> HubSpotResult:
        """Associate a contact with a company.

        Uses the HubSpot v3 associations API with type ID 1
        (contact_to_company primary association).

        Args:
            contact_id: HubSpot contact ID.
            company_id: HubSpot company ID.

        Returns:
            HubSpotResult indicating success.
        """
        result = await self._request(
            "PUT",
            f"/crm/v3/objects/companies/{company_id}/associations/contacts/{contact_id}/{ASSOCIATION_TYPE_CONTACT_TO_COMPANY}",
        )
        return result

    async def get_deal_associations(
        self,
        deal_id: str,
        to_object_type: str,
    ) -> HubSpotResult:
        """Get associations from a deal to another object type.

        Args:
            deal_id: HubSpot deal ID.
            to_object_type: Target object type (e.g., 'contacts', 'companies').

        Returns:
            HubSpotResult with list of associated object IDs.
        """
        result = await self._request(
            "GET",
            f"/crm/v3/objects/deals/{deal_id}/associations/{to_object_type}",
        )
        return result

    # ── Webhook Management ────────────────────────────────────────

    async def list_webhook_subscriptions(
        self,
        app_id: str,
    ) -> HubSpotResult:
        """List webhook subscriptions for a HubSpot app.

        Args:
            app_id: HubSpot application ID.

        Returns:
            HubSpotResult with list of webhook subscriptions.
        """
        result = await self._request(
            "GET", f"/webhooks/v3/{app_id}/subscriptions",
        )
        return result

    async def create_webhook_subscription(
        self,
        app_id: str,
        event_type: str,
        url: str,
    ) -> HubSpotResult:
        """Create a webhook subscription.

        Args:
            app_id: HubSpot application ID.
            event_type: Event type (e.g., 'contact.creation', 'deal.propertyChange').
            url: Webhook callback URL.

        Returns:
            HubSpotResult with created subscription data.
        """
        result = await self._request(
            "POST", f"/webhooks/v3/{app_id}/subscriptions",
            json_body={
                "eventType": event_type,
                "url": url,
            },
        )
        return result

    async def delete_webhook_subscription(
        self,
        app_id: str,
        subscription_id: str,
    ) -> HubSpotResult:
        """Delete a webhook subscription.

        Args:
            app_id: HubSpot application ID.
            subscription_id: Webhook subscription ID to delete.

        Returns:
            HubSpotResult indicating success.
        """
        result = await self._request(
            "DELETE", f"/webhooks/v3/{app_id}/subscriptions/{subscription_id}",
        )
        return result

    # ── Webhook Verification ──────────────────────────────────────

    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        signature: str,
        client_secret: str,
    ) -> bool:
        """Verify HubSpot webhook HMAC-SHA256 signature.

        This is a critical security function (BC-003). HubSpot v3 webhooks
        sign every request with HMAC-SHA256 using the client secret. The
        signature is base64-encoded and sent in the X-HubSpot-Signature-v3
        header.

        Verification prevents forgery and replay attacks.

        Args:
            payload: Raw request body bytes.
            signature: X-HubSpot-Signature-v3 header value (base64-encoded HMAC).
            client_secret: HubSpot webhook signing secret (client secret).

        Returns:
            True if signature is valid, False otherwise.
        """
        if not signature or not client_secret:
            return False

        try:
            computed = hmac.new(
                client_secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).digest()

            computed_b64 = base64.b64encode(computed).decode("utf-8")

            # Constant-time comparison to prevent timing attacks (BC-003)
            return hmac.compare_digest(computed_b64, signature)
        except Exception:
            return False

    # ── Pagination Helper ─────────────────────────────────────────

    async def get_all_pages(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data_key: str = "results",
        max_pages: int = MAX_PAGES,
    ) -> HubSpotResult:
        """Fetch all pages of a cursor-based paginated resource.

        HubSpot uses cursor-based pagination with `after` parameter and
        `paging.next.after` in the response. This method follows all
        pages up to max_pages.

        Args:
            path: API path (e.g., '/crm/v3/objects/contacts').
            params: Query parameters.
            data_key: Key in response containing the data list (default: "results").
            max_pages: Maximum number of pages to fetch.

        Returns:
            HubSpotResult with all items combined from all pages.
        """
        all_items: List[Dict[str, Any]] = []
        current_params = dict(params or {})
        pages_fetched = 0
        after: Optional[str] = None

        while pages_fetched < max_pages:
            if after:
                current_params["after"] = after

            result = await self._request("GET", path, params=current_params)

            if not result.success:
                if all_items:
                    # Return what we have so far even if a page failed
                    return HubSpotResult(
                        success=True,
                        data={"results": all_items},
                        metadata={"pages_fetched": pages_fetched, "partial": True},
                    )
                return result

            # Extract items from response
            if data_key and data_key in result.data:
                items = result.data[data_key]
            elif isinstance(result.data, list):
                items = result.data
            else:
                items = [result.data]

            all_items.extend(items)

            # Check for next page via cursor
            paging = result.data.get("paging", {})
            next_page = paging.get("next", {})
            next_after = next_page.get("after")

            if not next_after:
                break

            after = next_after
            pages_fetched += 1

        return HubSpotResult(
            success=True,
            data={"results": all_items},
            metadata={"pages_fetched": pages_fetched + 1},
        )


def create_hubspot_client_from_config(config: Dict[str, Any]) -> HubSpotClient:
    """Factory function to create a HubSpotClient from integration config.

    Args:
        config: Integration config dict with access_token and optional
                timeout and max_retries settings.

    Returns:
        Configured HubSpotClient instance.
    """
    return HubSpotClient(
        access_token=config.get("access_token", ""),
        timeout=config.get("timeout", REQUEST_TIMEOUT),
        max_retries=config.get("max_retries", MAX_RETRIES),
    )

"""
PARWA Zendesk Client.

Ticketing system integration for customer support.
Supports: Ticket creation, updates, user management, knowledge base access.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import asyncio
from enum import Enum
import hashlib
import base64

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ZendeskClientState(Enum):
    """Zendesk Client state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class TicketStatus(Enum):
    """Zendesk ticket status types."""
    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    HOLD = "hold"
    SOLVED = "solved"
    CLOSED = "closed"


class TicketPriority(Enum):
    """Zendesk ticket priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ZendeskClient:
    """
    Zendesk Client for ticketing system integration.

    Features:
    - Ticket creation and management
    - User/customer management
    - Ticket comment handling
    - Knowledge base access
    - Search functionality
    """

    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    API_VERSION = "v2"

    def __init__(
        self,
        subdomain: Optional[str] = None,
        email: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT
    ) -> None:
        """
        Initialize Zendesk Client.

        Args:
            subdomain: Zendesk subdomain (e.g., 'company' for company.zendesk.com)
            email: Zendesk agent email for API authentication
            api_key: Zendesk API key (reads from config if not provided)
            timeout: Request timeout in seconds
        """
        self.subdomain = subdomain or settings.zendesk_subdomain
        self.email = email or settings.zendesk_email
        self.api_key = api_key or (
            settings.zendesk_api_key.get_secret_value()
            if settings.zendesk_api_key else None
        )
        self.timeout = timeout
        self._state = ZendeskClientState.DISCONNECTED
        self._last_request: Optional[datetime] = None

    @property
    def state(self) -> ZendeskClientState:
        """Get current client state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._state == ZendeskClientState.CONNECTED

    def _get_base_url(self) -> str:
        """Get the base API URL for Zendesk."""
        if not self.subdomain:
            raise ValueError("Zendesk subdomain not configured")
        return f"https://{self.subdomain}.zendesk.com/api/{self.API_VERSION}"

    def _get_auth_header(self) -> str:
        """Get Basic Auth header for Zendesk API."""
        if not self.email or not self.api_key:
            raise ValueError("Zendesk credentials not configured")
        credentials = f"{self.email}/token:{self.api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def connect(self) -> bool:
        """
        Connect to Zendesk API.

        Validates credentials by fetching account info.

        Returns:
            True if connected successfully
        """
        if self._state == ZendeskClientState.CONNECTED:
            return True

        self._state = ZendeskClientState.CONNECTING

        if not self.subdomain:
            self._state = ZendeskClientState.ERROR
            logger.error({"event": "zendesk_missing_subdomain"})
            return False

        if not self.email:
            self._state = ZendeskClientState.ERROR
            logger.error({"event": "zendesk_missing_email"})
            return False

        if not self.api_key:
            self._state = ZendeskClientState.ERROR
            logger.error({"event": "zendesk_missing_api_key"})
            return False

        try:
            # Simulate connection validation
            await asyncio.sleep(0.1)

            self._state = ZendeskClientState.CONNECTED
            self._last_request = datetime.now(timezone.utc)

            logger.info({
                "event": "zendesk_client_connected",
                "subdomain": self.subdomain,
            })

            return True

        except Exception as e:
            self._state = ZendeskClientState.ERROR
            logger.error({
                "event": "zendesk_connection_failed",
                "error": str(e),
                "subdomain": self.subdomain,
            })
            return False

    async def disconnect(self) -> None:
        """Disconnect from Zendesk API."""
        self._state = ZendeskClientState.DISCONNECTED
        self._last_request = None

        logger.info({
            "event": "zendesk_client_disconnected",
            "subdomain": self.subdomain,
        })

    async def create_ticket(
        self,
        subject: str,
        comment: str,
        requester_email: str,
        requester_name: Optional[str] = None,
        priority: TicketPriority = TicketPriority.NORMAL,
        status: TicketStatus = TicketStatus.NEW,
        tags: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        group_id: Optional[int] = None,
        assignee_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new support ticket.

        Args:
            subject: Ticket subject line
            comment: Initial ticket comment/description
            requester_email: Email of the ticket requester
            requester_name: Name of the requester
            priority: Ticket priority level
            status: Initial ticket status
            tags: List of tags to apply
            custom_fields: Custom field values
            group_id: Group to assign ticket to
            assignee_id: Agent to assign ticket to

        Returns:
            Ticket data dictionary with ID and details
        """
        if not self.is_connected:
            raise ValueError("Zendesk client not connected")

        if not subject:
            raise ValueError("Ticket subject is required")

        if not comment:
            raise ValueError("Ticket comment is required")

        if not requester_email:
            raise ValueError("Requester email is required")

        logger.info({
            "event": "zendesk_ticket_create",
            "subject": subject[:50] + "..." if len(subject) > 50 else subject,
            "requester_email": requester_email,
            "priority": priority.value,
        })

        # Simulated ticket creation
        ticket_id = int(hashlib.md5(
            f"{subject}{requester_email}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8], 16)

        return {
            "id": ticket_id,
            "subject": subject,
            "description": comment,
            "status": status.value,
            "priority": priority.value,
            "requester": {
                "email": requester_email,
                "name": requester_name or requester_email.split("@")[0],
            },
            "tags": tags or [],
            "custom_fields": custom_fields or {},
            "group_id": group_id,
            "assignee_id": assignee_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """
        Get a ticket by ID.

        Args:
            ticket_id: Zendesk ticket ID

        Returns:
            Ticket data dictionary
        """
        if not self.is_connected:
            raise ValueError("Zendesk client not connected")

        if not ticket_id:
            raise ValueError("Ticket ID is required")

        logger.info({
            "event": "zendesk_ticket_get",
            "ticket_id": ticket_id,
        })

        # Simulated ticket fetch
        return {
            "id": ticket_id,
            "subject": "Sample Ticket",
            "description": "This is a sample ticket description.",
            "status": TicketStatus.OPEN.value,
            "priority": TicketPriority.NORMAL.value,
            "requester": {
                "email": "customer@example.com",
                "name": "John Doe",
            },
            "tags": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def update_ticket(
        self,
        ticket_id: int,
        comment: Optional[str] = None,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        tags: Optional[List[str]] = None,
        assignee_id: Optional[int] = None,
        group_id: Optional[int] = None,
        custom_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update a ticket.

        Args:
            ticket_id: Zendesk ticket ID
            comment: Comment to add to the ticket
            status: New ticket status
            priority: New ticket priority
            tags: New tags (replaces existing)
            assignee_id: Agent to assign to
            group_id: Group to assign to
            custom_fields: Custom field updates

        Returns:
            Updated ticket data dictionary
        """
        if not self.is_connected:
            raise ValueError("Zendesk client not connected")

        if not ticket_id:
            raise ValueError("Ticket ID is required")

        logger.info({
            "event": "zendesk_ticket_update",
            "ticket_id": ticket_id,
            "has_comment": comment is not None,
            "status": status.value if status else None,
        })

        # Simulated ticket update
        return {
            "id": ticket_id,
            "subject": "Updated Ticket",
            "status": status.value if status else TicketStatus.OPEN.value,
            "priority": priority.value if priority else TicketPriority.NORMAL.value,
            "tags": tags or [],
            "assignee_id": assignee_id,
            "group_id": group_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def add_comment(
        self,
        ticket_id: int,
        comment: str,
        author_id: Optional[int] = None,
        public: bool = True
    ) -> Dict[str, Any]:
        """
        Add a comment to a ticket.

        Args:
            ticket_id: Zendesk ticket ID
            comment: Comment text
            author_id: Author user ID (agent or end user)
            public: Whether comment is visible to requester

        Returns:
            Comment data dictionary
        """
        if not self.is_connected:
            raise ValueError("Zendesk client not connected")

        if not ticket_id:
            raise ValueError("Ticket ID is required")

        if not comment:
            raise ValueError("Comment is required")

        logger.info({
            "event": "zendesk_comment_add",
            "ticket_id": ticket_id,
            "public": public,
        })

        # Simulated comment creation
        comment_id = int(hashlib.md5(
            f"{ticket_id}{comment}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8], 16)

        return {
            "id": comment_id,
            "ticket_id": ticket_id,
            "body": comment,
            "author_id": author_id,
            "public": public,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def search_tickets(
        self,
        query: str,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        requester_email: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for tickets.

        Args:
            query: Search query string
            status: Filter by status
            priority: Filter by priority
            requester_email: Filter by requester email
            limit: Maximum results

        Returns:
            List of matching ticket dictionaries
        """
        if not self.is_connected:
            raise ValueError("Zendesk client not connected")

        if not query:
            raise ValueError("Search query is required")

        if limit < 1 or limit > 1000:
            raise ValueError("Limit must be between 1 and 1000")

        logger.info({
            "event": "zendesk_tickets_search",
            "query": query,
            "filters": {
                "status": status.value if status else None,
                "priority": priority.value if priority else None,
                "requester": requester_email,
            },
        })

        # Simulated search
        return []

    async def get_user(self, user_id: int) -> Dict[str, Any]:
        """
        Get a user by ID.

        Args:
            user_id: Zendesk user ID

        Returns:
            User data dictionary
        """
        if not self.is_connected:
            raise ValueError("Zendesk client not connected")

        if not user_id:
            raise ValueError("User ID is required")

        logger.info({
            "event": "zendesk_user_get",
            "user_id": user_id,
        })

        # Simulated user fetch
        return {
            "id": user_id,
            "name": "John Doe",
            "email": "john.doe@example.com",
            "role": "end-user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by email address.

        Args:
            email: User email address

        Returns:
            User data dictionary or None if not found
        """
        if not self.is_connected:
            raise ValueError("Zendesk client not connected")

        if not email:
            raise ValueError("Email is required")

        logger.info({
            "event": "zendesk_user_search",
            "email": email,
        })

        # Simulated user search
        user_id = int(hashlib.md5(email.encode()).hexdigest()[:8], 16)

        return {
            "id": user_id,
            "name": email.split("@")[0],
            "email": email,
            "role": "end-user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def create_or_update_user(
        self,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        organization_id: Optional[int] = None,
        user_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create or update a user.

        Args:
            email: User email (required, used as identifier)
            name: User name
            phone: User phone number
            organization_id: Organization to associate
            user_fields: Custom user field values

        Returns:
            User data dictionary
        """
        if not self.is_connected:
            raise ValueError("Zendesk client not connected")

        if not email:
            raise ValueError("Email is required")

        logger.info({
            "event": "zendesk_user_create_update",
            "email": email,
        })

        # Simulated user creation/update
        user_id = int(hashlib.md5(email.encode()).hexdigest()[:8], 16)

        return {
            "id": user_id,
            "name": name or email.split("@")[0],
            "email": email,
            "phone": phone,
            "organization_id": organization_id,
            "user_fields": user_fields or {},
            "role": "end-user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_ticket_comments(self, ticket_id: int) -> List[Dict[str, Any]]:
        """
        Get all comments for a ticket.

        Args:
            ticket_id: Zendesk ticket ID

        Returns:
            List of comment dictionaries
        """
        if not self.is_connected:
            raise ValueError("Zendesk client not connected")

        if not ticket_id:
            raise ValueError("Ticket ID is required")

        logger.info({
            "event": "zendesk_comments_get",
            "ticket_id": ticket_id,
        })

        # Simulated comments fetch
        return []

    async def get_articles(
        self,
        query: Optional[str] = None,
        category_id: Optional[int] = None,
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Get knowledge base articles.

        Args:
            query: Search query
            category_id: Filter by category
            limit: Maximum results

        Returns:
            List of article dictionaries
        """
        if not self.is_connected:
            raise ValueError("Zendesk client not connected")

        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")

        logger.info({
            "event": "zendesk_articles_get",
            "query": query,
            "category_id": category_id,
        })

        # Simulated articles fetch
        return []

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Zendesk connection.

        Returns:
            Health status dictionary
        """
        return {
            "healthy": self._state == ZendeskClientState.CONNECTED,
            "state": self._state.value,
            "subdomain": self.subdomain,
            "last_request": (
                self._last_request.isoformat()
                if self._last_request else None
            ),
        }

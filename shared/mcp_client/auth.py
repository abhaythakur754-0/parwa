"""
PARWA MCP Authentication.

Handles authentication for MCP client connections including
token generation, validation, and refresh.
"""
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.core_functions.security import create_access_token, decode_access_token

logger = get_logger(__name__)
settings = get_settings()


class MCPAuthConfig:
    """MCP Authentication configuration."""
    TOKEN_EXPIRY_HOURS = 24
    REFRESH_TOKEN_EXPIRY_DAYS = 7
    ALGORITHM = "HS256"


class MCPAuthToken:
    """MCP Authentication token model."""

    def __init__(
        self,
        token: str,
        token_type: str = "bearer",
        expires_at: Optional[datetime] = None,
        scopes: Optional[list] = None
    ) -> None:
        """
        Initialize MCP Auth Token.

        Args:
            token: Token string
            token_type: Token type (bearer, api_key, etc.)
            expires_at: Token expiration datetime
            scopes: List of granted scopes
        """
        self.token = token
        self.token_type = token_type
        self.expires_at = expires_at
        self.scopes = scopes or []

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def expires_in_seconds(self) -> Optional[int]:
        """Get seconds until expiration."""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "token": self.token,
            "token_type": self.token_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "expires_in": self.expires_in_seconds,
            "scopes": self.scopes,
        }


class MCPAuthManager:
    """
    MCP Authentication Manager.

    Features:
    - Token generation for MCP sessions
    - Token validation
    - Refresh token handling
    - Scope management
    """

    def __init__(
        self,
        company_id: Optional[UUID] = None,
        secret_key: Optional[str] = None
    ) -> None:
        """
        Initialize MCP Auth Manager.

        Args:
            company_id: Company UUID for scoping
            secret_key: Secret key for signing (defaults to settings)
        """
        self.company_id = company_id
        self._secret_key = secret_key or settings.secret_key.get_secret_value()
        self._tokens: Dict[str, MCPAuthToken] = {}

    def generate_token(
        self,
        session_id: Optional[str] = None,
        scopes: Optional[list] = None,
        expiry_hours: int = MCPAuthConfig.TOKEN_EXPIRY_HOURS
    ) -> MCPAuthToken:
        """
        Generate a new MCP authentication token.

        Args:
            session_id: Session identifier
            scopes: List of scopes to grant
            expiry_hours: Token expiry in hours

        Returns:
            Generated MCPAuthToken
        """
        session_id = session_id or str(uuid4())
        scopes = scopes or ["read", "invoke"]

        # Create token payload
        payload = {
            "session_id": session_id,
            "company_id": str(self.company_id) if self.company_id else None,
            "scopes": scopes,
            "type": "mcp_access",
        }

        # Generate token using security module
        expires_delta = timedelta(hours=expiry_hours)
        token_string = create_access_token(
            data=payload,
            secret_key=self._secret_key,
            expires_delta=expires_delta,
        )

        expires_at = datetime.now(timezone.utc) + expires_delta

        token = MCPAuthToken(
            token=token_string,
            token_type="bearer",
            expires_at=expires_at,
            scopes=scopes,
        )

        # Store token
        self._tokens[session_id] = token

        logger.info({
            "event": "mcp_token_generated",
            "session_id": session_id,
            "company_id": str(self.company_id) if self.company_id else None,
            "scopes": scopes,
            "expires_at": expires_at.isoformat(),
        })

        return token

    def generate_refresh_token(
        self,
        session_id: str,
        expiry_days: int = MCPAuthConfig.REFRESH_TOKEN_EXPIRY_DAYS
    ) -> str:
        """
        Generate a refresh token.

        Args:
            session_id: Session identifier
            expiry_days: Refresh token expiry in days

        Returns:
            Refresh token string
        """
        # Create secure random refresh token
        refresh_token = secrets.token_urlsafe(32)

        # In production, would store in database with expiry
        logger.info({
            "event": "mcp_refresh_token_generated",
            "session_id": session_id,
            "expiry_days": expiry_days,
        })

        return refresh_token

    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate an MCP authentication token.

        Args:
            token: Token string to validate

        Returns:
            Decoded token payload if valid

        Raises:
            ValueError: If token is invalid or expired
        """
        try:
            payload = decode_access_token(token, self._secret_key)

            # Verify token type
            if payload.get("type") != "mcp_access":
                raise ValueError("Invalid token type")

            # Verify company scope if set
            if self.company_id:
                token_company = payload.get("company_id")
                if token_company and token_company != str(self.company_id):
                    raise ValueError("Token company mismatch")

            logger.debug({
                "event": "mcp_token_validated",
                "session_id": payload.get("session_id"),
            })

            return payload

        except Exception as e:
            logger.warning({
                "event": "mcp_token_validation_failed",
                "error": str(e),
            })
            raise ValueError(f"Token validation failed: {e}")

    def refresh_access_token(
        self,
        refresh_token: str,
        session_id: str
    ) -> MCPAuthToken:
        """
        Refresh an access token using a refresh token.

        Args:
            refresh_token: Refresh token string
            session_id: Session identifier

        Returns:
            New MCPAuthToken
        """
        # In production, would validate refresh token from database
        # For now, generate new token

        logger.info({
            "event": "mcp_token_refreshed",
            "session_id": session_id,
        })

        return self.generate_token(session_id=session_id)

    def revoke_token(self, session_id: str) -> bool:
        """
        Revoke a token by session ID.

        Args:
            session_id: Session identifier

        Returns:
            True if token was revoked
        """
        if session_id in self._tokens:
            del self._tokens[session_id]

            logger.info({
                "event": "mcp_token_revoked",
                "session_id": session_id,
            })

            return True

        return False

    def get_token(self, session_id: str) -> Optional[MCPAuthToken]:
        """
        Get token by session ID.

        Args:
            session_id: Session identifier

        Returns:
            MCPAuthToken if found, None otherwise
        """
        return self._tokens.get(session_id)

    def create_auth_header(self, token: MCPAuthToken) -> Dict[str, str]:
        """
        Create authorization header for HTTP requests.

        Args:
            token: MCPAuthToken

        Returns:
            Dict with Authorization header
        """
        return {
            "Authorization": f"{token.token_type.capitalize()} {token.token}"
        }

    def generate_api_key(
        self,
        name: str,
        company_id: UUID,
        scopes: Optional[list] = None
    ) -> str:
        """
        Generate an API key for programmatic access.

        Args:
            name: Key name/description
            company_id: Company UUID
            scopes: List of scopes

        Returns:
            API key string
        """
        # Create deterministic but secure key
        key_base = f"{company_id}:{name}:{datetime.now(timezone.utc).isoformat()}"
        api_key = f"mcp_{secrets.token_urlsafe(32)}"

        logger.info({
            "event": "mcp_api_key_generated",
            "name": name,
            "company_id": str(company_id),
            "scopes": scopes or ["read"],
        })

        return api_key

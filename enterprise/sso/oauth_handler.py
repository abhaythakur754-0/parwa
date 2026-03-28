"""
Enterprise SSO - OAuth Handler
OAuth 2.0 authentication for enterprise clients
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import hashlib
import secrets


class OAuthProvider(str, Enum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    OKTA = "okta"
    AUTH0 = "auth0"
    CUSTOM = "custom"


class OAuthConfig(BaseModel):
    """OAuth configuration"""
    provider: OAuthProvider
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    userinfo_url: str
    redirect_uri: str
    scopes: list[str] = Field(default_factory=lambda: ["openid", "email", "profile"])

    model_config = ConfigDict()


class OAuthToken(BaseModel):
    """OAuth token data"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    scope: Optional[str] = None

    model_config = ConfigDict()


class OAuthUserInfo(BaseModel):
    """OAuth user info"""
    user_id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None

    model_config = ConfigDict()


class OAuthHandler:
    """
    Handle OAuth 2.0 authentication for enterprise clients.
    """

    def __init__(self, client_id: str, config: OAuthConfig):
        self.client_id = client_id
        self.config = config
        self.tokens: Dict[str, OAuthToken] = {}

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Get OAuth authorization URL"""
        state = state or secrets.token_urlsafe(32)

        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "state": state
        }

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.config.authorization_url}?{query}"

    def exchange_code(self, code: str) -> OAuthToken:
        """Exchange authorization code for token"""
        # Simulate token exchange
        token = OAuthToken(
            access_token=secrets.token_urlsafe(32),
            refresh_token=secrets.token_urlsafe(32),
            expires_in=3600
        )
        self.tokens[token.access_token] = token
        return token

    def get_user_info(self, access_token: str) -> Optional[OAuthUserInfo]:
        """Get user info from OAuth provider"""
        if access_token not in self.tokens:
            return None

        # Simulate user info
        return OAuthUserInfo(
            user_id=secrets.token_hex(8),
            email="user@example.com",
            name="Test User"
        )

    def refresh_token(self, refresh_token: str) -> Optional[OAuthToken]:
        """Refresh access token"""
        new_token = OAuthToken(
            access_token=secrets.token_urlsafe(32),
            refresh_token=refresh_token,
            expires_in=3600
        )
        self.tokens[new_token.access_token] = new_token
        return new_token

    def revoke_token(self, access_token: str) -> bool:
        """Revoke token"""
        if access_token in self.tokens:
            del self.tokens[access_token]
            return True
        return False

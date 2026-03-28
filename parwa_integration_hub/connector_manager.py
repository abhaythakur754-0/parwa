"""
Week 58 - Builder 2: Integration Connectors Module
Connector management, OAuth handling, and connection pooling
"""

import time
import secrets
import threading
import hashlib
import base64
import hmac
import urllib.parse
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import queue

logger = logging.getLogger(__name__)


class ConnectorStatus(Enum):
    """Connector status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    CONNECTING = "connecting"


class AuthType(Enum):
    """Authentication types"""
    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    BEARER = "bearer"


@dataclass
class ConnectorConfig:
    """Connector configuration"""
    name: str
    connector_type: str
    base_url: str
    auth_type: AuthType = AuthType.NONE
    credentials: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_count: int = 3
    pool_size: int = 10


@dataclass
class OAuthConfig:
    """OAuth 2.0 configuration"""
    client_id: str
    client_secret: str
    auth_url: str
    token_url: str
    redirect_uri: str
    scopes: List[str] = field(default_factory=list)


@dataclass
class OAuthToken:
    """OAuth token data"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    scope: str = ""
    created_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if token is expired"""
        return time.time() > (self.created_at + self.expires_in - 60)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "refresh_token": self.refresh_token,
            "scope": self.scope
        }


class Connector:
    """Base connector class"""

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.status = ConnectorStatus.INACTIVE
        self.last_error: Optional[str] = None
        self.request_count = 0
        self.error_count = 0
        self.created_at = time.time()

    def connect(self) -> bool:
        """Connect to service"""
        self.status = ConnectorStatus.CONNECTING
        try:
            # Simulate connection
            self.status = ConnectorStatus.ACTIVE
            return True
        except Exception as e:
            self.status = ConnectorStatus.ERROR
            self.last_error = str(e)
            return False

    def disconnect(self) -> None:
        """Disconnect from service"""
        self.status = ConnectorStatus.INACTIVE

    def is_healthy(self) -> bool:
        """Check if connector is healthy"""
        return self.status == ConnectorStatus.ACTIVE

    def record_request(self) -> None:
        """Record a request"""
        self.request_count += 1

    def record_error(self, error: str) -> None:
        """Record an error"""
        self.error_count += 1
        self.last_error = error

    def get_stats(self) -> Dict[str, Any]:
        """Get connector statistics"""
        return {
            "name": self.config.name,
            "type": self.config.connector_type,
            "status": self.status.value,
            "requests": self.request_count,
            "errors": self.error_count,
            "uptime": time.time() - self.created_at,
            "last_error": self.last_error
        }


class ConnectorManager:
    """
    Manager for integration connectors with lifecycle management
    """

    def __init__(self):
        self.connectors: Dict[str, Connector] = {}
        self.connector_types: Dict[str, Callable] = {}
        self.lock = threading.Lock()

    def register_connector_type(self, connector_type: str, factory: Callable) -> None:
        """Register a connector type factory"""
        self.connector_types[connector_type] = factory

    def create_connector(self, config: ConnectorConfig) -> Connector:
        """Create a new connector"""
        connector = Connector(config)
        with self.lock:
            self.connectors[config.name] = connector
        return connector

    def get_connector(self, name: str) -> Optional[Connector]:
        """Get connector by name"""
        return self.connectors.get(name)

    def remove_connector(self, name: str) -> bool:
        """Remove a connector"""
        with self.lock:
            if name in self.connectors:
                self.connectors[name].disconnect()
                del self.connectors[name]
                return True
        return False

    def connect_all(self) -> Dict[str, bool]:
        """Connect all connectors"""
        results = {}
        for name, connector in self.connectors.items():
            results[name] = connector.connect()
        return results

    def disconnect_all(self) -> None:
        """Disconnect all connectors"""
        for connector in self.connectors.values():
            connector.disconnect()

    def get_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all connectors"""
        return {
            name: {
                "status": connector.status.value,
                "healthy": connector.is_healthy(),
                "requests": connector.request_count,
                "errors": connector.error_count
            }
            for name, connector in self.connectors.items()
        }

    def list_connectors(self) -> List[str]:
        """List all connector names"""
        return list(self.connectors.keys())


class OAuthHandler:
    """
    OAuth 2.0 handler for token management
    """

    def __init__(self):
        self.tokens: Dict[str, OAuthToken] = {}
        self.configs: Dict[str, OAuthConfig] = {}
        self.pending_states: Dict[str, float] = {}
        self.lock = threading.Lock()

    def register_provider(self, name: str, config: OAuthConfig) -> None:
        """Register an OAuth provider"""
        with self.lock:
            self.configs[name] = config

    def generate_auth_url(self, provider: str, state: str = None) -> Optional[str]:
        """Generate authorization URL"""
        config = self.configs.get(provider)
        if not config:
            return None

        state = state or secrets.token_urlsafe(32)
        with self.lock:
            self.pending_states[state] = time.time()

        params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
            "state": state
        }

        return f"{config.auth_url}?{urllib.parse.urlencode(params)}"

    def validate_state(self, state: str) -> bool:
        """Validate OAuth state"""
        with self.lock:
            if state in self.pending_states:
                # States expire after 10 minutes
                if time.time() - self.pending_states[state] < 600:
                    del self.pending_states[state]
                    return True
                del self.pending_states[state]
        return False

    def store_token(self, provider: str, token: OAuthToken) -> None:
        """Store OAuth token"""
        with self.lock:
            self.tokens[provider] = token

    def get_token(self, provider: str) -> Optional[OAuthToken]:
        """Get OAuth token"""
        return self.tokens.get(provider)

    def get_valid_token(self, provider: str) -> Optional[str]:
        """Get valid access token (refreshes if needed)"""
        token = self.tokens.get(provider)
        if token and not token.is_expired():
            return token.access_token
        return None

    def refresh_token(self, provider: str) -> Optional[OAuthToken]:
        """Refresh OAuth token (mock implementation)"""
        token = self.tokens.get(provider)
        if token and token.refresh_token:
            # Mock refresh - in real implementation, call token endpoint
            new_token = OAuthToken(
                access_token=secrets.token_urlsafe(32),
                token_type=token.token_type,
                expires_in=3600,
                refresh_token=token.refresh_token,
                scope=token.scope
            )
            self.store_token(provider, new_token)
            return new_token
        return None

    def revoke_token(self, provider: str) -> bool:
        """Revoke OAuth token"""
        with self.lock:
            if provider in self.tokens:
                del self.tokens[provider]
                return True
        return False


class ConnectorPool:
    """
    Connection pool for managing reusable connections
    """

    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self.pools: Dict[str, queue.Queue] = defaultdict(queue.Queue)
        self.pool_sizes: Dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()
        self.stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"created": 0, "reused": 0, "returned": 0}
        )

    def _create_connection(self, connector_name: str) -> Dict[str, Any]:
        """Create a new connection"""
        return {
            "id": secrets.token_hex(8),
            "connector": connector_name,
            "created_at": time.time(),
            "last_used": time.time()
        }

    def get_connection(self, connector_name: str) -> Dict[str, Any]:
        """Get a connection from the pool"""
        pool = self.pools[connector_name]

        try:
            conn = pool.get_nowait()
            conn["last_used"] = time.time()
            self.stats[connector_name]["reused"] += 1
            return conn
        except queue.Empty:
            pass

        with self.lock:
            if self.pool_sizes[connector_name] < self.max_size:
                self.pool_sizes[connector_name] += 1
                self.stats[connector_name]["created"] += 1
                return self._create_connection(connector_name)

        # Wait for a connection to become available
        conn = pool.get()
        conn["last_used"] = time.time()
        self.stats[connector_name]["reused"] += 1
        return conn

    def return_connection(self, connector_name: str, conn: Dict[str, Any]) -> None:
        """Return a connection to the pool"""
        pool = self.pools[connector_name]
        pool.put(conn)
        self.stats[connector_name]["returned"] += 1

    def clear_pool(self, connector_name: str) -> int:
        """Clear all connections for a connector"""
        count = 0
        pool = self.pools[connector_name]
        while True:
            try:
                pool.get_nowait()
                count += 1
            except queue.Empty:
                break
        with self.lock:
            self.pool_sizes[connector_name] = 0
        return count

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get pool statistics"""
        return dict(self.stats)

    def get_pool_size(self, connector_name: str) -> int:
        """Get current pool size"""
        return self.pools[connector_name].qsize()

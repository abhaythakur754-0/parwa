"""
PARWA Integration Service

Business logic for third-party integration management.

Uses real database persistence via SQLAlchemy (Integration model).

Supported Integrations:
- Zendesk
- Shopify
- Slack
- Gmail
- Freshdesk
- Intercom
- Custom

BC-001: All operations scoped to company_id.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from app.exceptions import ValidationError
from app.logger import get_logger
from app.services.custom_integration_service import _decrypt_config, _encrypt_config
from sqlalchemy import and_
from sqlalchemy.orm import Session

from database.models.integration import Integration

logger = get_logger("integration_service")

# Integration types and their required config fields
INTEGRATION_TYPES: Dict[str, Dict[str, Any]] = {
    "zendesk": {
        "required_fields": ["subdomain", "api_token", "email"],
        "test_url": "https://{subdomain}.zendesk.com/api/v2/users/me.json",
    },
    "shopify": {
        "required_fields": ["shop_domain", "access_token"],
        "test_url": "https://{shop_domain}/admin/api/2024-01/shop.json",
    },
    "slack": {
        "required_fields": ["bot_token", "channel_id"],
        "test_url": "https://slack.com/api/auth.test",
    },
    "gmail": {
        "required_fields": ["client_id", "client_secret", "refresh_token"],
        "test_url": "https://gmail.googleapis.com/gmail/v1/users/me/profile",
    },
    "freshdesk": {
        "required_fields": ["domain", "api_key"],
        "test_url": "https://{domain}.freshdesk.com/api/v2/agents/me",
    },
    "intercom": {
        "required_fields": ["access_token"],
        "test_url": "https://api.intercom.io/me",
    },
    "custom": {
        "required_fields": [],
        "test_url": None,
    },
}

# Status values for integrations
STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_ERROR = "error"
STATUS_DISCONNECTED = "disconnected"


class IntegrationService:
    """Service for managing third-party integrations backed by real DB."""

    def __init__(self, db: Session):
        self.db = db

    # ── CRUD Operations ──────────────────────────────────────────

    def create_integration(
        self,
        company_id: str,
        integration_type: str,
        name: str,
        config: Dict[str, Any],
        validate: bool = True,
    ) -> Dict[str, Any]:
        """Create a new integration with optional credential validation."""
        # Validate integration type
        if integration_type not in INTEGRATION_TYPES:
            raise ValidationError(
                message=f"Invalid integration type: {integration_type}",
                details={"valid_types": list(INTEGRATION_TYPES.keys())},
            )

        type_config = INTEGRATION_TYPES[integration_type]
        required_fields = type_config["required_fields"]

        # Validate required fields
        missing_fields = [f for f in required_fields if not config.get(f)]
        if missing_fields:
            raise ValidationError(
                message=f"Missing required fields: {
                    ', '.join(missing_fields)}",
                details={"missing_fields": missing_fields},
            )

        # Initial status
        status = STATUS_PENDING
        test_result = None

        # Validate credentials before saving
        if validate:
            test_result = self._test_credentials(integration_type, config)
            status = STATUS_ACTIVE if test_result.get("success") else STATUS_ERROR

        integration = Integration(
            company_id=company_id,
            integration_type=integration_type,
            name=name,
            status=status,
            credentials_encrypted=_encrypt_config(config),
            settings="{}",
            error_message=(
                test_result.get("message")
                if test_result and not test_result.get("success")
                else None
            ),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(integration)
        self.db.flush()

        logger.info(
            "integration_created",
            integration_id=integration.id,
            company_id=company_id,
            type=integration_type,
            status=status,
        )

        return self._to_dict(integration, mask_credentials=True)

    def get_integrations(
        self,
        company_id: str,
        status: Optional[str] = None,
        integration_type: Optional[str] = None,
        active_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """List integrations for a company with optional filters."""
        query = self.db.query(Integration).filter(Integration.company_id == company_id)

        if status:
            query = query.filter(Integration.status == status)

        if integration_type:
            query = query.filter(
                Integration.integration_type == integration_type.lower()
            )

        if active_only:
            query = query.filter(Integration.status == STATUS_ACTIVE)

        integrations = query.order_by(Integration.created_at.desc()).all()

        return [self._to_dict(i, mask_credentials=True) for i in integrations]

    def get_integration(
        self, integration_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single integration by ID, scoped to company."""
        integration = (
            self.db.query(Integration)
            .filter(
                and_(
                    Integration.id == integration_id,
                    Integration.company_id == company_id,
                )
            )
            .first()
        )

        if not integration:
            return None

        return self._to_dict(integration, mask_credentials=True)

    def test_integration(
        self,
        integration_id: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """Test an existing integration's connectivity."""
        integration = (
            self.db.query(Integration)
            .filter(
                and_(
                    Integration.id == integration_id,
                    Integration.company_id == company_id,
                )
            )
            .first()
        )

        if not integration:
            raise ValidationError(
                message="Integration not found.",
                details={"integration_id": integration_id},
            )

        config = _decrypt_config(integration.credentials_encrypted) or {}
        result = self._test_credentials(integration.integration_type, config)

        # Update status on the integration record
        new_status = STATUS_ACTIVE if result.get("success") else STATUS_ERROR
        integration.status = new_status
        integration.error_message = (
            None if result.get("success") else result.get("message")
        )
        integration.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        logger.info(
            "integration_tested",
            integration_id=integration_id,
            company_id=company_id,
            success=result.get("success"),
        )

        return {
            "integration_id": integration_id,
            "success": result.get("success", False),
            "message": result.get("message", "Test not performed"),
            "status": new_status,
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }

    def update_integration(
        self,
        integration_id: str,
        company_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update integration fields."""
        integration = (
            self.db.query(Integration)
            .filter(
                and_(
                    Integration.id == integration_id,
                    Integration.company_id == company_id,
                )
            )
            .first()
        )

        if not integration:
            raise ValidationError(
                message="Integration not found.",
                details={"integration_id": integration_id},
            )

        allowed_fields = {
            "name",
            "status",
            "credentials_encrypted",
            "settings",
            "error_message",
        }
        for field, value in updates.items():
            if field in allowed_fields:
                if field == "credentials_encrypted" and isinstance(value, dict):
                    value = _encrypt_config(value)
                if field == "settings" and isinstance(value, dict):
                    value = json.dumps(value)
                setattr(integration, field, value)

        integration.updated_at = datetime.now(timezone.utc)
        self.db.flush()

        return self._to_dict(integration, mask_credentials=True)

    def test_credentials_only(
        self,
        integration_type: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Test integration credentials without creating or saving a record.

        Dry-run: validates the type and required fields, then makes a real
        API call to the integration's service. Returns test result only.
        """
        if integration_type not in INTEGRATION_TYPES:
            raise ValidationError(
                message=f"Invalid integration type: {integration_type}",
                details={"valid_types": list(INTEGRATION_TYPES.keys())},
            )

        type_config = INTEGRATION_TYPES[integration_type]
        required_fields = type_config["required_fields"]

        # Validate required fields
        missing_fields = [f for f in required_fields if not config.get(f)]
        if missing_fields:
            raise ValidationError(
                message=f"Missing required fields: {
                    ', '.join(missing_fields)}",
                details={"missing_fields": missing_fields},
            )

        result = self._test_credentials(integration_type, config)

        return {
            "integration_id": "dry-run",
            "success": result.get("success", False),
            "message": result.get("message", "Test not performed"),
            "status": STATUS_ACTIVE if result.get("success") else STATUS_ERROR,
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }

    def delete_integration(
        self,
        integration_id: str,
        company_id: str,
    ) -> bool:
        """Delete an integration."""
        integration = (
            self.db.query(Integration)
            .filter(
                and_(
                    Integration.id == integration_id,
                    Integration.company_id == company_id,
                )
            )
            .first()
        )

        if not integration:
            raise ValidationError(
                message="Integration not found.",
                details={"integration_id": integration_id},
            )

        self.db.delete(integration)
        self.db.flush()

        logger.info(
            "integration_deleted",
            integration_id=integration_id,
            company_id=company_id,
        )

        return True

    def get_active_integrations(self, company_id: str) -> List[Dict[str, Any]]:
        """Get all active integrations for a company."""
        return self.get_integrations(company_id, status=STATUS_ACTIVE)

    def get_integrations_by_type(
        self, company_id: str, integration_type: str
    ) -> List[Dict[str, Any]]:
        """Get integrations filtered by type."""
        return self.get_integrations(company_id, integration_type=integration_type)

    # ── Connection Test Methods ───────────────────────────────────

    def _test_credentials(
        self,
        integration_type: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Test integration credentials by making a real API call."""
        if integration_type not in INTEGRATION_TYPES:
            return {
                "success": False,
                "message": f"Unknown integration type: {integration_type}",
            }

        try:
            if integration_type == "zendesk":
                return self._test_zendesk(config)
            elif integration_type == "shopify":
                return self._test_shopify(config)
            elif integration_type == "slack":
                return self._test_slack(config)
            elif integration_type == "gmail":
                return self._test_gmail(config)
            elif integration_type == "freshdesk":
                return self._test_freshdesk(config)
            elif integration_type == "intercom":
                return self._test_intercom(config)
            else:
                return {
                    "success": True,
                    "message": f"{integration_type} integration config saved",
                }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {
                    str(e)}"}

    def _test_zendesk(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Zendesk API connectivity."""
        subdomain = config.get("subdomain")
        api_token = config.get("api_token") or config.get("access_token")
        email = config.get("email")

        if not all([subdomain, api_token, email]):
            return {
                "success": False,
                "message": "Missing required fields: subdomain, api_token, email",
            }

        url = f"https://{subdomain}.zendesk.com/api/v2/users/me.json"
        headers = {"Authorization": f"Basic {
                _encode_basic_auth(
                    email + '/token',
                    api_token)}"}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message": f"Connected to Zendesk account: {
                            data.get(
                                'user',
                                {}).get(
                                'name',
                                'Unknown')}",
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Zendesk API returned {response.status_code}: {response.text[:200]}",
                    }
        except httpx.TimeoutException:
            return {"success": False, "message": "Connection to Zendesk timed out"}
        except Exception as e:
            return {"success": False, "message": f"Zendesk connection failed: {
                    str(e)}"}

    def _test_shopify(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Shopify API connectivity."""
        shop_domain = config.get("shop_domain")
        access_token = config.get("access_token")

        if not all([shop_domain, access_token]):
            return {
                "success": False,
                "message": "Missing required fields: shop_domain, access_token",
            }

        shop_domain = (
            shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
        )
        url = f"https://{shop_domain}/admin/api/2024-01/shop.json"
        headers = {"X-Shopify-Access-Token": access_token}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message": f"Connected to Shopify store: {
                            data.get(
                                'shop',
                                {}).get(
                                'name',
                                'Unknown')}",
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Shopify API returned {response.status_code}: {response.text[:200]}",
                    }
        except httpx.TimeoutException:
            return {"success": False, "message": "Connection to Shopify timed out"}
        except Exception as e:
            return {"success": False, "message": f"Shopify connection failed: {
                    str(e)}"}

    def _test_slack(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Slack API connectivity."""
        bot_token = config.get("bot_token") or config.get("access_token")

        if not bot_token:
            return {
                "success": False,
                "message": "Missing required field: bot_token or access_token",
            }

        url = "https://slack.com/api/auth.test"
        headers = {"Authorization": f"Bearer {bot_token}"}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(url, headers=headers)
                data = response.json()
                if data.get("ok"):
                    return {
                        "success": True,
                        "message": f"Connected to Slack workspace: {
                            data.get(
                                'team',
                                'Unknown')}",
                    }
                else:
                    return {"success": False, "message": f"Slack API error: {
                            data.get(
                                'error',
                                'Unknown error')}"}
        except Exception as e:
            return {"success": False, "message": f"Slack connection failed: {
                    str(e)}"}

    def _test_gmail(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Gmail API connectivity.

        Exchanges the stored refresh_token for a short-lived access_token
        via Google's OAuth2 token endpoint, then tests the Gmail profile API.
        """
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")
        refresh_token = config.get("refresh_token")

        if not all([client_id, client_secret, refresh_token]):
            return {
                "success": False,
                "message": "Missing required fields: client_id, client_secret, refresh_token",
            }

        # Step 1: Exchange refresh_token for access_token
        access_token = None
        try:
            with httpx.Client(timeout=10) as client:
                token_resp = client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                    },
                )
                if token_resp.status_code == 200:
                    access_token = token_resp.json().get("access_token")
                else:
                    error_data = (
                        token_resp.json()
                        if token_resp.headers.get("content-type", "").startswith(
                            "application/json"
                        )
                        else {}
                    )
                    error_desc = error_data.get(
                        "error_description", error_data.get("error", f"HTTP {
                                token_resp.status_code}")
                    )
                    return {
                        "success": False,
                        "message": f"Gmail OAuth token exchange failed: {error_desc}",
                    }
        except Exception as e:
            return {"success": False, "message": f"Gmail OAuth request failed: {
                    str(e)}"}

        if not access_token:
            return {"success": False, "message": "Gmail OAuth returned no access_token"}

        # Step 2: Test the Gmail profile API with the access_token
        url = "https://www.googleapis.com/gmail/v1/users/me/profile"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message": f"Connected to Gmail: {
                            data.get(
                                'emailAddress',
                                'Unknown')}",
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "message": "Gmail token expired or invalid. Please re-authenticate.",
                    }
                else:
                    return {"success": False, "message": f"Gmail API returned {
                            response.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"Gmail connection failed: {
                    str(e)}"}

    def _test_freshdesk(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Freshdesk API connectivity."""
        domain = config.get("domain")
        api_key = config.get("api_key")

        if not all([domain, api_key]):
            return {
                "success": False,
                "message": "Missing required fields: domain, api_key",
            }

        domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
        url = f"https://{domain}.freshdesk.com/api/v2/agents/me"
        # Freshdesk uses API key as username with "X" as password
        headers = {"Authorization": f"Basic {
                _encode_basic_auth(
                    api_key, 'X')}"}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message": f"Connected to Freshdesk: {
                            data.get(
                                'contact',
                                {}).get(
                                'name',
                                'Unknown')}",
                    }
                else:
                    return {"success": False, "message": f"Freshdesk API returned {
                            response.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"Freshdesk connection failed: {
                    str(e)}"}

    def _test_intercom(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test Intercom API connectivity."""
        access_token = config.get("access_token")

        if not access_token:
            return {"success": False, "message": "Missing required field: access_token"}

        url = "https://api.intercom.io/me"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message": f"Connected to Intercom: {
                            data.get(
                                'name',
                                data.get(
                                    'email',
                                    'Unknown'))}",
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Intercom API returned {response.status_code}: {response.text[:200]}",
                    }
        except Exception as e:
            return {"success": False, "message": f"Intercom connection failed: {
                    str(e)}"}

    # ── Helpers ───────────────────────────────────────────────────

    def _to_dict(
        self, integration: Integration, mask_credentials: bool = False
    ) -> Dict[str, Any]:
        """Convert Integration ORM object to dict."""
        config = _decrypt_config(integration.credentials_encrypted) or {}
        settings = self._parse_json(integration.settings) or {}

        if mask_credentials and config:
            config = _mask_config(config)

        return {
            "id": integration.id,
            "company_id": integration.company_id,
            "type": integration.integration_type,
            "name": integration.name,
            "status": integration.status,
            "config": config,
            "settings": settings,
            "last_test_at": (
                integration.updated_at.isoformat() if integration.updated_at else None
            ),
            "last_test_result": integration.error_message,
            "last_sync": (
                integration.last_sync.isoformat() if integration.last_sync else None
            ),
            "error_message": integration.error_message,
            "created_at": (
                integration.created_at.isoformat() if integration.created_at else None
            ),
            "updated_at": (
                integration.updated_at.isoformat() if integration.updated_at else None
            ),
        }

    @staticmethod
    def _parse_json(text_field: Optional[str]) -> Optional[Dict[str, Any]]:
        """Safely parse a JSON text field."""
        if not text_field:
            return None
        try:
            return json.loads(text_field)
        except (json.JSONDecodeError, TypeError):
            return None


# ── Module-level Helper Functions ───────────────────────────────────


def _encode_basic_auth(username: str, password: str) -> str:
    """Encode credentials for Basic Auth header."""
    import base64

    credentials = f"{username}:{password}"
    return base64.b64encode(credentials.encode()).decode()


def _mask_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive fields in config for API responses."""
    sensitive_keys = {
        "api_key",
        "api_token",
        "token",
        "access_token",
        "secret",
        "password",
        "refresh_token",
        "bot_token",
        "client_secret",
    }
    masked = {}
    for key, value in config.items():
        if any(s in key.lower() for s in sensitive_keys):
            if isinstance(value, str) and len(value) > 4:
                masked[key] = value[:4] + "****"
            else:
                masked[key] = "****"
        else:
            masked[key] = value
    return masked

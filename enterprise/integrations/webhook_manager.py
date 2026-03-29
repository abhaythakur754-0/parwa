"""
Webhook Manager
Enterprise Integration Hub - Week 43 Builder 4
"""

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging
import asyncio

logger = logging.getLogger(__name__)


class WebhookStatus(str, Enum):
    """Webhook registration status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"
    FAILED = "failed"


class EventType(str, Enum):
    """Supported webhook event types"""
    # Ticket events
    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_RESOLVED = "ticket.resolved"
    TICKET_ESCALATED = "ticket.escalated"
    
    # Customer events
    CUSTOMER_CREATED = "customer.created"
    CUSTOMER_UPDATED = "customer.updated"
    
    # Message events
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    
    # AI events
    AI_RESPONSE_GENERATED = "ai.response.generated"
    AI_ACTION_TAKEN = "ai.action.taken"
    APPROVAL_REQUIRED = "approval.required"
    APPROVAL_DECISION = "approval.decision"
    
    # System events
    INTEGRATION_CONNECTED = "integration.connected"
    INTEGRATION_DISCONNECTED = "integration.disconnected"
    SYSTEM_ALERT = "system.alert"


@dataclass
class WebhookEndpoint:
    """Registered webhook endpoint"""
    id: str
    name: str
    url: str
    secret: str
    events: List[str]
    status: WebhookStatus = WebhookStatus.ACTIVE
    headers: Dict[str, str] = field(default_factory=dict)
    auth_type: Optional[str] = None
    auth_value: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_triggered: Optional[datetime] = None
    failure_count: int = 0
    success_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "events": self.events,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "failure_count": self.failure_count,
            "success_count": self.success_count
        }


@dataclass
class WebhookDelivery:
    """Webhook delivery record"""
    id: str
    endpoint_id: str
    event_type: str
    payload: Dict[str, Any]
    status: str
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    attempts: int = 1
    delivered_at: Optional[datetime] = None
    next_retry: Optional[datetime] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "endpoint_id": self.endpoint_id,
            "event_type": self.event_type,
            "status": self.status,
            "response_code": self.response_code,
            "attempts": self.attempts,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "error": self.error,
            "created_at": self.created_at.isoformat()
        }


class WebhookManager:
    """Manages webhook registration, delivery, and retry logic"""
    
    MAX_RETRIES = 5
    RETRY_DELAYS = [1, 5, 15, 60, 300]  # Exponential backoff in seconds
    
    def __init__(self):
        self._endpoints: Dict[str, WebhookEndpoint] = {}
        self._deliveries: Dict[str, WebhookDelivery] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    def register_webhook(
        self,
        name: str,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        auth_type: Optional[str] = None,
        auth_value: Optional[str] = None
    ) -> WebhookEndpoint:
        """
        Register a new webhook endpoint.
        
        Args:
            name: Human-readable name for the webhook
            url: URL to receive webhook POST requests
            events: List of event types to subscribe to
            secret: Secret key for HMAC signature (auto-generated if not provided)
            headers: Additional headers to include in requests
            auth_type: Authentication type (basic, bearer, etc.)
            auth_value: Authentication value
            
        Returns:
            Registered WebhookEndpoint
        """
        webhook_id = str(uuid.uuid4())
        secret = secret or self._generate_secret()
        
        endpoint = WebhookEndpoint(
            id=webhook_id,
            name=name,
            url=url,
            secret=secret,
            events=events,
            headers=headers or {},
            auth_type=auth_type,
            auth_value=auth_value
        )
        
        self._endpoints[webhook_id] = endpoint
        logger.info(f"Registered webhook: {name} -> {url}")
        
        return endpoint
    
    def update_webhook(
        self,
        webhook_id: str,
        **kwargs
    ) -> Optional[WebhookEndpoint]:
        """Update an existing webhook"""
        if webhook_id not in self._endpoints:
            return None
        
        endpoint = self._endpoints[webhook_id]
        
        for key, value in kwargs.items():
            if hasattr(endpoint, key):
                setattr(endpoint, key, value)
        
        endpoint.updated_at = datetime.utcnow()
        return endpoint
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook registration"""
        if webhook_id in self._endpoints:
            del self._endpoints[webhook_id]
            logger.info(f"Deleted webhook: {webhook_id}")
            return True
        return False
    
    def get_webhook(self, webhook_id: str) -> Optional[WebhookEndpoint]:
        """Get a webhook by ID"""
        return self._endpoints.get(webhook_id)
    
    def list_webhooks(
        self,
        status: Optional[WebhookStatus] = None,
        event_type: Optional[str] = None
    ) -> List[WebhookEndpoint]:
        """List registered webhooks with optional filtering"""
        webhooks = list(self._endpoints.values())
        
        if status:
            webhooks = [w for w in webhooks if w.status == status]
        
        if event_type:
            webhooks = [w for w in webhooks if event_type in w.events]
        
        return webhooks
    
    async def trigger_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        client_id: Optional[str] = None
    ) -> List[WebhookDelivery]:
        """
        Trigger a webhook event.
        
        Args:
            event_type: Type of event to trigger
            payload: Event payload data
            client_id: Optional client ID for filtering
            
        Returns:
            List of delivery records
        """
        deliveries = []
        
        # Find matching endpoints
        matching_endpoints = [
            ep for ep in self._endpoints.values()
            if ep.status == WebhookStatus.ACTIVE and event_type in ep.events
        ]
        
        # Enrich payload with metadata
        enriched_payload = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "id": str(uuid.uuid4()),
            "data": payload
        }
        
        if client_id:
            enriched_payload["client_id"] = client_id
        
        # Deliver to each endpoint
        for endpoint in matching_endpoints:
            delivery = await self._deliver(endpoint, enriched_payload)
            deliveries.append(delivery)
        
        return deliveries
    
    async def _deliver(
        self,
        endpoint: WebhookEndpoint,
        payload: Dict[str, Any]
    ) -> WebhookDelivery:
        """Deliver webhook to endpoint"""
        delivery_id = str(uuid.uuid4())
        
        delivery = WebhookDelivery(
            id=delivery_id,
            endpoint_id=endpoint.id,
            event_type=payload["event_type"],
            payload=payload,
            status="pending"
        )
        
        try:
            # This would normally make an HTTP request
            # For now, simulate success
            import aiohttp
            
            headers = self._build_headers(endpoint, payload)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint.url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    delivery.response_code = response.status
                    
                    if 200 <= response.status < 300:
                        delivery.status = "delivered"
                        delivery.delivered_at = datetime.utcnow()
                        endpoint.success_count += 1
                        endpoint.last_triggered = datetime.utcnow()
                    else:
                        delivery.status = "failed"
                        delivery.error = f"HTTP {response.status}"
                        endpoint.failure_count += 1
                        delivery.next_retry = self._calculate_retry_time(1)
                    
                    delivery.response_body = await response.text()
                    
        except Exception as e:
            delivery.status = "failed"
            delivery.error = str(e)
            endpoint.failure_count += 1
            delivery.next_retry = self._calculate_retry_time(1)
            
            # Disable after too many failures
            if endpoint.failure_count >= 10:
                endpoint.status = WebhookStatus.DISABLED
                logger.warning(f"Disabled webhook {endpoint.id} after 10 failures")
        
        self._deliveries[delivery_id] = delivery
        
        # Update endpoint
        self._endpoints[endpoint.id] = endpoint
        
        return delivery
    
    def _build_headers(
        self,
        endpoint: WebhookEndpoint,
        payload: Dict[str, Any]
    ) -> Dict[str, str]:
        """Build headers for webhook request"""
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": payload["event_type"],
            "X-Webhook-ID": payload["id"],
            "X-Webhook-Timestamp": payload["timestamp"]
        }
        
        # Add signature
        signature = self._generate_signature(endpoint.secret, payload)
        headers["X-Webhook-Signature"] = signature
        
        # Add custom headers
        headers.update(endpoint.headers)
        
        # Add authentication
        if endpoint.auth_type == "bearer" and endpoint.auth_value:
            headers["Authorization"] = f"Bearer {endpoint.auth_value}"
        elif endpoint.auth_type == "basic" and endpoint.auth_value:
            headers["Authorization"] = f"Basic {endpoint.auth_value}"
        
        return headers
    
    def _generate_signature(
        self,
        secret: str,
        payload: Dict[str, Any]
    ) -> str:
        """Generate HMAC signature for payload"""
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    def verify_signature(
        self,
        secret: str,
        payload: Dict[str, Any],
        signature: str
    ) -> bool:
        """Verify webhook signature"""
        expected = self._generate_signature(secret, payload)
        return hmac.compare_digest(expected, signature)
    
    def _generate_secret(self) -> str:
        """Generate a new webhook secret"""
        return uuid.uuid4().hex + uuid.uuid4().hex
    
    def _calculate_retry_time(self, attempt: int) -> datetime:
        """Calculate next retry time with exponential backoff"""
        delay_index = min(attempt - 1, len(self.RETRY_DELAYS) - 1)
        delay_seconds = self.RETRY_DELAYS[delay_index]
        return datetime.utcnow() + timedelta(seconds=delay_seconds)
    
    async def retry_failed(self) -> List[WebhookDelivery]:
        """Retry failed webhook deliveries"""
        retried = []
        
        for delivery in self._deliveries.values():
            if delivery.status == "failed" and delivery.next_retry:
                if datetime.utcnow() >= delivery.next_retry:
                    if delivery.attempts < self.MAX_RETRIES:
                        endpoint = self._endpoints.get(delivery.endpoint_id)
                        if endpoint and endpoint.status == WebhookStatus.ACTIVE:
                            delivery.attempts += 1
                            new_delivery = await self._deliver(endpoint, delivery.payload)
                            retried.append(new_delivery)
        
        return retried
    
    def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """Get a delivery record by ID"""
        return self._deliveries.get(delivery_id)
    
    def get_delivery_history(
        self,
        endpoint_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[WebhookDelivery]:
        """Get delivery history with optional filtering"""
        deliveries = list(self._deliveries.values())
        
        if endpoint_id:
            deliveries = [d for d in deliveries if d.endpoint_id == endpoint_id]
        
        if status:
            deliveries = [d for d in deliveries if d.status == status]
        
        # Sort by created_at descending
        deliveries.sort(key=lambda x: x.created_at, reverse=True)
        
        return deliveries[:limit]
    
    def register_event_handler(
        self,
        event_type: str,
        handler: Callable
    ) -> None:
        """Register a handler for a specific event type"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def test_webhook(self, webhook_id: str) -> WebhookDelivery:
        """Send a test event to a webhook"""
        endpoint = self.get_webhook(webhook_id)
        if not endpoint:
            raise ValueError(f"Webhook not found: {webhook_id}")
        
        test_payload = {
            "event_type": "test",
            "timestamp": datetime.utcnow().isoformat(),
            "id": str(uuid.uuid4()),
            "data": {
                "message": "This is a test webhook delivery",
                "webhook_name": endpoint.name
            }
        }
        
        return await self._deliver(endpoint, test_payload)

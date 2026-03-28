"""
Week 58 - Builder 3: Webhook Manager Module
Webhook registration, dispatch, and verification
"""

import time
import secrets
import hmac
import hashlib
import json
import threading
import base64
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import queue
import urllib.parse

logger = logging.getLogger(__name__)


class WebhookStatus(Enum):
    """Webhook status"""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class DeliveryStatus(Enum):
    """Delivery status"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookEndpoint:
    """Webhook endpoint configuration"""
    id: str
    name: str
    url: str
    secret: str
    events: List[str] = field(default_factory=list)
    status: WebhookStatus = WebhookStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retry_count: int = 3


@dataclass
class WebhookDelivery:
    """Webhook delivery record"""
    id: str
    endpoint_id: str
    event: str
    payload: Dict[str, Any]
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    last_attempt: Optional[float] = None
    last_error: Optional[str] = None
    response_code: Optional[int] = None
    created_at: float = field(default_factory=time.time)


class WebhookRegistry:
    """
    Webhook registry for managing webhook endpoints
    """

    def __init__(self):
        self.endpoints: Dict[str, WebhookEndpoint] = {}
        self.event_subscriptions: Dict[str, List[str]] = defaultdict(list)
        self.lock = threading.Lock()

    def register(self, name: str, url: str, events: List[str],
                 secret: str = None, **kwargs) -> WebhookEndpoint:
        """Register a new webhook endpoint"""
        endpoint_id = secrets.token_urlsafe(16)
        secret = secret or secrets.token_urlsafe(32)

        endpoint = WebhookEndpoint(
            id=endpoint_id,
            name=name,
            url=url,
            secret=secret,
            events=events,
            **kwargs
        )

        with self.lock:
            self.endpoints[endpoint_id] = endpoint
            for event in events:
                self.event_subscriptions[event].append(endpoint_id)

        return endpoint

    def unregister(self, endpoint_id: str) -> bool:
        """Unregister a webhook endpoint"""
        with self.lock:
            if endpoint_id in self.endpoints:
                endpoint = self.endpoints[endpoint_id]
                for event in endpoint.events:
                    if endpoint_id in self.event_subscriptions[event]:
                        self.event_subscriptions[event].remove(endpoint_id)
                del self.endpoints[endpoint_id]
                return True
        return False

    def get_endpoint(self, endpoint_id: str) -> Optional[WebhookEndpoint]:
        """Get endpoint by ID"""
        return self.endpoints.get(endpoint_id)

    def get_endpoints_for_event(self, event: str) -> List[WebhookEndpoint]:
        """Get all endpoints subscribed to an event"""
        endpoint_ids = self.event_subscriptions.get(event, [])
        return [
            self.endpoints[eid]
            for eid in endpoint_ids
            if eid in self.endpoints and
            self.endpoints[eid].status == WebhookStatus.ACTIVE
        ]

    def pause(self, endpoint_id: str) -> bool:
        """Pause a webhook endpoint"""
        with self.lock:
            if endpoint_id in self.endpoints:
                self.endpoints[endpoint_id].status = WebhookStatus.PAUSED
                return True
        return False

    def resume(self, endpoint_id: str) -> bool:
        """Resume a paused webhook endpoint"""
        with self.lock:
            if endpoint_id in self.endpoints:
                self.endpoints[endpoint_id].status = WebhookStatus.ACTIVE
                return True
        return False

    def disable(self, endpoint_id: str) -> bool:
        """Disable a webhook endpoint"""
        with self.lock:
            if endpoint_id in self.endpoints:
                self.endpoints[endpoint_id].status = WebhookStatus.DISABLED
                return True
        return False

    def rotate_secret(self, endpoint_id: str) -> Optional[str]:
        """Rotate webhook secret"""
        with self.lock:
            if endpoint_id in self.endpoints:
                new_secret = secrets.token_urlsafe(32)
                self.endpoints[endpoint_id].secret = new_secret
                return new_secret
        return None

    def list_endpoints(self) -> List[Dict[str, Any]]:
        """List all registered endpoints"""
        return [
            {
                "id": ep.id,
                "name": ep.name,
                "url": ep.url,
                "events": ep.events,
                "status": ep.status.value,
                "created_at": ep.created_at
            }
            for ep in self.endpoints.values()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            "total_endpoints": len(self.endpoints),
            "active_endpoints": sum(
                1 for ep in self.endpoints.values()
                if ep.status == WebhookStatus.ACTIVE
            ),
            "event_types": len(self.event_subscriptions)
        }


class WebhookDispatcher:
    """
    Webhook dispatcher with retry and backoff support
    """

    def __init__(self, registry: WebhookRegistry):
        self.registry = registry
        self.deliveries: Dict[str, WebhookDelivery] = {}
        self.delivery_queue: queue.Queue = queue.Queue()
        self.retry_queue: queue.Queue = queue.Queue()
        self.stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"sent": 0, "failed": 0, "retries": 0}
        )
        self.lock = threading.Lock()

    def dispatch(self, event: str, payload: Dict[str, Any]) -> List[str]:
        """Dispatch event to all subscribed endpoints"""
        endpoints = self.registry.get_endpoints_for_event(event)
        delivery_ids = []

        for endpoint in endpoints:
            delivery_id = secrets.token_urlsafe(16)
            delivery = WebhookDelivery(
                id=delivery_id,
                endpoint_id=endpoint.id,
                event=event,
                payload=payload
            )

            with self.lock:
                self.deliveries[delivery_id] = delivery

            self.delivery_queue.put(delivery_id)
            delivery_ids.append(delivery_id)

        return delivery_ids

    def process_delivery(self, delivery_id: str) -> bool:
        """Process a webhook delivery"""
        delivery = self.deliveries.get(delivery_id)
        if not delivery:
            return False

        endpoint = self.registry.get_endpoint(delivery.endpoint_id)
        if not endpoint:
            return False

        delivery.attempts += 1
        delivery.last_attempt = time.time()

        # Simulate delivery (in real implementation, make HTTP request)
        success = self._send_webhook(endpoint, delivery)

        with self.lock:
            if success:
                delivery.status = DeliveryStatus.SUCCESS
                self.stats[endpoint.id]["sent"] += 1
            else:
                if delivery.attempts < endpoint.retry_count:
                    delivery.status = DeliveryStatus.RETRYING
                    self.stats[endpoint.id]["retries"] += 1
                    self.retry_queue.put(delivery_id)
                else:
                    delivery.status = DeliveryStatus.FAILED
                    self.stats[endpoint.id]["failed"] += 1

        return success

    def _send_webhook(self, endpoint: WebhookEndpoint,
                      delivery: WebhookDelivery) -> bool:
        """Send webhook (mock implementation)"""
        # Simulate HTTP POST
        return True  # Mock success

    def get_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        """Get delivery by ID"""
        return self.deliveries.get(delivery_id)

    def get_pending_count(self) -> int:
        """Get count of pending deliveries"""
        return self.delivery_queue.qsize()

    def get_stats(self) -> Dict[str, Any]:
        """Get dispatcher statistics"""
        return dict(self.stats)


class WebhookVerifier:
    """
    Webhook signature verifier
    """

    def __init__(self):
        self.verification_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"verified": 0, "failed": 0}
        )
        self.lock = threading.Lock()

    def generate_signature(self, secret: str, payload: str,
                           timestamp: str = None) -> str:
        """Generate HMAC signature for webhook payload"""
        timestamp = timestamp or str(int(time.time()))
        message = f"{timestamp}.{payload}"
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"t={timestamp},v1={signature}"

    def verify_signature(self, secret: str, payload: str,
                         signature_header: str,
                         tolerance: int = 300) -> bool:
        """Verify webhook signature"""
        try:
            parts = dict(p.split("=", 1) for p in signature_header.split(","))
            timestamp = parts.get("t")
            received_sig = parts.get("v1")

            if not timestamp or not received_sig:
                return False

            # Check timestamp tolerance
            if abs(time.time() - int(timestamp)) > tolerance:
                return False

            # Compute expected signature
            message = f"{timestamp}.{payload}"
            expected_sig = hmac.new(
                secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()

            # Constant-time comparison
            is_valid = hmac.compare_digest(expected_sig, received_sig)

            with self.lock:
                if is_valid:
                    self.verification_stats["total"]["verified"] += 1
                else:
                    self.verification_stats["total"]["failed"] += 1

            return is_valid

        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            with self.lock:
                self.verification_stats["total"]["failed"] += 1
            return False

    def verify_timestamp(self, timestamp: str, tolerance: int = 300) -> bool:
        """Verify timestamp is within tolerance"""
        try:
            ts = int(timestamp)
            return abs(time.time() - ts) <= tolerance
        except (ValueError, TypeError):
            return False

    def parse_signature_header(self, header: str) -> Dict[str, str]:
        """Parse signature header into components"""
        try:
            return dict(p.split("=", 1) for p in header.split(","))
        except Exception:
            return {}

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get verification statistics"""
        return dict(self.verification_stats)

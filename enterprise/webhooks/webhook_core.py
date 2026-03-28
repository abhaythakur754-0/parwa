"""Webhook Core System - Registration and Management"""
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import secrets
import hashlib
import logging
import re

logger = logging.getLogger(__name__)

class WebhookStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    FAILED = "failed"

class WebhookEvent(str, Enum):
    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_RESOLVED = "ticket.resolved"
    REFUND_APPROVED = "refund.approved"
    REFUND_PROCESSED = "refund.processed"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    CONVERSATION_STARTED = "conversation.started"
    CONVERSATION_ENDED = "conversation.ended"
    ALL = "*"

@dataclass
class Webhook:
    webhook_id: str
    tenant_id: str
    name: str
    url: str
    secret: str
    events: Set[str] = field(default_factory=set)
    status: WebhookStatus = WebhookStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_triggered_at: Optional[datetime] = None
    success_count: int = 0
    failure_count: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    retry_count: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_triggers(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        if self.total_triggers == 0:
            return 100.0
        return (self.success_count / self.total_triggers) * 100

class WebhookManager:
    def __init__(self):
        self._webhooks: Dict[str, Webhook] = {}
        self._webhooks_by_tenant: Dict[str, List[str]] = {}
        self._metrics = {"total_webhooks": 0, "total_triggers": 0, "total_successes": 0, "total_failures": 0}

    def create_webhook(self, tenant_id: str, name: str, url: str, events: Set[str], secret: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Webhook:
        webhook_id = f"wh_{secrets.token_hex(8)}"
        webhook_secret = secret or secrets.token_urlsafe(32)

        if not self._validate_url(url):
            raise ValueError(f"Invalid webhook URL: {url}")

        webhook = Webhook(
            webhook_id=webhook_id,
            tenant_id=tenant_id,
            name=name,
            url=url,
            secret=webhook_secret,
            events=events,
            headers=headers or {}
        )

        self._webhooks[webhook_id] = webhook
        if tenant_id not in self._webhooks_by_tenant:
            self._webhooks_by_tenant[tenant_id] = []
        self._webhooks_by_tenant[tenant_id].append(webhook_id)
        self._metrics["total_webhooks"] += 1

        logger.info(f"Created webhook {webhook_id} for tenant {tenant_id}")
        return webhook

    def _validate_url(self, url: str) -> bool:
        pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(pattern, url))

    def get_webhook(self, webhook_id: str) -> Optional[Webhook]:
        return self._webhooks.get(webhook_id)

    def get_tenant_webhooks(self, tenant_id: str, active_only: bool = False) -> List[Webhook]:
        webhook_ids = self._webhooks_by_tenant.get(tenant_id, [])
        webhooks = [self._webhooks[wid] for wid in webhook_ids if wid in self._webhooks]
        if active_only:
            webhooks = [w for w in webhooks if w.status == WebhookStatus.ACTIVE]
        return webhooks

    def update_webhook(self, webhook_id: str, **kwargs) -> Optional[Webhook]:
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return None

        for key, value in kwargs.items():
            if hasattr(webhook, key):
                setattr(webhook, key, value)
        webhook.updated_at = datetime.utcnow()
        return webhook

    def delete_webhook(self, webhook_id: str) -> bool:
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return False

        del self._webhooks[webhook_id]
        if webhook.tenant_id in self._webhooks_by_tenant:
            self._webhooks_by_tenant[webhook.tenant_id] = [wid for wid in self._webhooks_by_tenant[webhook.tenant_id] if wid != webhook_id]
        return True

    def pause_webhook(self, webhook_id: str) -> bool:
        return self._set_status(webhook_id, WebhookStatus.PAUSED)

    def activate_webhook(self, webhook_id: str) -> bool:
        return self._set_status(webhook_id, WebhookStatus.ACTIVE)

    def disable_webhook(self, webhook_id: str) -> bool:
        return self._set_status(webhook_id, WebhookStatus.DISABLED)

    def _set_status(self, webhook_id: str, status: WebhookStatus) -> bool:
        webhook = self._webhooks.get(webhook_id)
        if webhook:
            webhook.status = status
            webhook.updated_at = datetime.utcnow()
            return True
        return False

    def record_trigger(self, webhook_id: str, success: bool) -> None:
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            return

        webhook.last_triggered_at = datetime.utcnow()
        if success:
            webhook.success_count += 1
            self._metrics["total_successes"] += 1
        else:
            webhook.failure_count += 1
            self._metrics["total_failures"] += 1
        self._metrics["total_triggers"] += 1

    def get_webhooks_for_event(self, event: str, tenant_id: Optional[str] = None) -> List[Webhook]:
        webhooks = []
        for webhook in self._webhooks.values():
            if webhook.status != WebhookStatus.ACTIVE:
                continue
            if tenant_id and webhook.tenant_id != tenant_id:
                continue
            if WebhookEvent.ALL in webhook.events or event in webhook.events:
                webhooks.append(webhook)
        return webhooks

    def get_metrics(self) -> Dict[str, Any]:
        return {**self._metrics, "active_webhooks": sum(1 for w in self._webhooks.values() if w.status == WebhookStatus.ACTIVE)}

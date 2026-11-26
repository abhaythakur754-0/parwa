"""Regression tests for webhook timestamp freshness and replay protection."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_future_dated_webhook_is_rejected():
    from app.api.webhooks import receive_webhook

    payload = {
        "event_id": "future-event-1",
        "event_type": "message.created",
        "company_id": "tenant-a",
        "occurred_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    }
    request = MagicMock()
    request.body = AsyncMock(return_value=json.dumps(payload).encode("utf-8"))
    request.json = AsyncMock(return_value=payload)
    request.headers = {}

    response = await receive_webhook("shopify", request)

    assert response.status_code == 403
    assert b"REPLAY_DETECTED" in response.body


@pytest.mark.asyncio
async def test_stale_webhook_is_rejected():
    from app.api.webhooks import receive_webhook

    payload = {
        "event_id": "stale-event-1",
        "event_type": "message.created",
        "company_id": "tenant-a",
        "occurred_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
    }
    request = MagicMock()
    request.body = AsyncMock(return_value=json.dumps(payload).encode("utf-8"))
    request.json = AsyncMock(return_value=payload)
    request.headers = {}

    response = await receive_webhook("shopify", request)

    assert response.status_code == 403
    assert b"REPLAY_DETECTED" in response.body

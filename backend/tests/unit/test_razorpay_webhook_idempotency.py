from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from database.models.billing import Invoice, Subscription, Transaction
from app.services import razorpay_service


@pytest.mark.asyncio
async def test_subscription_charged_duplicate_does_not_insert_ledger_rows(monkeypatch):
    subscription = SimpleNamespace(
        company_id="company-1",
        tier="parwa",
        status="active",
        current_period_start=None,
        current_period_end=None,
    )
    existing_invoice = SimpleNamespace(id="invoice-1")
    existing_transaction = SimpleNamespace(id="transaction-1")

    db = MagicMock()

    def query_side_effect(model):
        query = MagicMock()
        if model is Subscription:
            query.filter.return_value.first.return_value = subscription
        elif model is Invoice:
            query.filter.return_value.first.return_value = existing_invoice
        elif model is Transaction:
            query.filter.return_value.first.return_value = existing_transaction
        else:
            raise AssertionError(f"Unexpected model: {model}")
        return query

    db.query.side_effect = query_side_effect
    monkeypatch.setattr(razorpay_service, "_end_company_trial", lambda *_args, **_kwargs: None)

    result = await razorpay_service._handle_charged(
        db,
        {
            "subscription": {"entity": {"id": "sub-1"}},
            "payment": {"entity": {"id": "pay-1", "amount": 1200}},
        },
    )

    assert result["status"] == "charged"
    db.add.assert_not_called()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_duplicate_refund_event_does_not_create_second_transaction():
    existing_refund = SimpleNamespace(id="refund-transaction-1")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing_refund

    result = await razorpay_service._handle_refund_processed(
        db,
        {"refund": {"entity": {"id": "rfnd-1", "payment_id": "pay-1", "amount": 500}}},
    )

    assert result["status"] == "already_processed"
    db.add.assert_not_called()
    db.commit.assert_not_called()

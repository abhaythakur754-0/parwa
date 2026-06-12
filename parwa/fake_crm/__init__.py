"""Fake CRM — Realistic in-memory business infrastructure for PARWA testing."""

from parwa.fake_crm.database import FakeCRM, get_crm, reset_crm
from parwa.fake_crm.executor import ActionExecutor, get_executor

__all__ = ["FakeCRM", "get_crm", "reset_crm", "ActionExecutor", "get_executor"]

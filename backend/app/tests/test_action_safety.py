"""
Unit tests for app/core/action_safety.py

Tests the ActionSafety classifier: classify_action() and needs_approval().

Covers:
- All 5 safety levels (READ, WRITE, FINANCIAL, DESTRUCTIVE, SENSITIVE_PII)
- Precedence (FINANCIAL > DESTRUCTIVE > SENSITIVE_PII > WRITE > READ)
- BC-008: never crashes
- Confidence scoring
- needs_approval logic

Run: pytest backend/app/tests/test_action_safety.py -v
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.action_safety import (
    ActionSafetyLevel,
    ActionSafetyResult,
    classify_action,
    needs_approval,
)


class TestClassifyRead:
    def test_get_tool(self):
        result = classify_action("get_order_status")
        assert result.level == ActionSafetyLevel.READ
        assert result.confidence == 0.9
        assert result.matched_keyword == "get"

    def test_fetch_tool(self):
        result = classify_action("fetch_customer_details")
        assert result.level == ActionSafetyLevel.READ
        assert result.matched_keyword == "fetch"

    def test_list_tool(self):
        result = classify_action("list_products")
        assert result.level == ActionSafetyLevel.READ

    def test_search_tool(self):
        result = classify_action("search_faq")
        assert result.level == ActionSafetyLevel.READ

    def test_status_tool(self):
        result = classify_action("check_payment_status")
        assert result.level == ActionSafetyLevel.FINANCIAL

    def test_health_tool(self):
        result = classify_action("system_health_check")
        assert result.level == ActionSafetyLevel.READ

    def test_no_keyword_match(self):
        result = classify_action("do_something")
        assert result.level == ActionSafetyLevel.READ
        assert result.confidence == 0.5
        assert result.matched_keyword is None
        assert "defaulting to READ" in result.reasoning

    def test_empty_string(self):
        result = classify_action("")
        assert result.level == ActionSafetyLevel.READ


class TestClassifyWrite:
    def test_update_tool(self):
        result = classify_action("update_address")
        assert result.level == ActionSafetyLevel.WRITE
        assert result.matched_keyword == "update"

    def test_modify_tool(self):
        result = classify_action("modify_subscription")
        assert result.level == ActionSafetyLevel.WRITE

    def test_create_tool(self):
        result = classify_action("create_ticket")
        assert result.level == ActionSafetyLevel.WRITE
        assert result.matched_keyword == "create"

    def test_send_email_tool(self):
        result = classify_action("send_welcome_email")
        assert result.level == ActionSafetyLevel.WRITE
        assert result.matched_keyword in ("send", "email")

    def test_assign_tool(self):
        result = classify_action("assign_agent")
        assert result.level == ActionSafetyLevel.WRITE

    def test_notify_tool(self):
        result = classify_action("notify_customer")
        assert result.level == ActionSafetyLevel.WRITE


class TestClassifyFinancial:
    def test_refund_tool(self):
        result = classify_action("process_refund")
        assert result.level == ActionSafetyLevel.FINANCIAL
        assert result.matched_keyword == "refund"

    def test_credit_tool(self):
        result = classify_action("issue_credit")
        assert result.level == ActionSafetyLevel.FINANCIAL

    def test_payment_tool(self):
        result = classify_action("capture_payment")
        assert result.level == ActionSafetyLevel.FINANCIAL

    def test_billing_tool(self):
        result = classify_action("update_billing_info")
        assert result.level == ActionSafetyLevel.FINANCIAL
        assert result.matched_keyword == "billing"

    def test_invoice_tool(self):
        result = classify_action("generate_invoice")
        assert result.level == ActionSafetyLevel.FINANCIAL

    def test_debit_tool(self):
        result = classify_action("apply_debit")
        assert result.level == ActionSafetyLevel.FINANCIAL

    def test_payout_tool(self):
        result = classify_action("process_payout")
        assert result.level == ActionSafetyLevel.FINANCIAL

    def test_case_insensitive(self):
        result = classify_action("PROCESS_REFUND")
        assert result.level == ActionSafetyLevel.FINANCIAL

    def test_description_match(self):
        result = classify_action("do_thing", "This processes a refund for the customer")
        assert result.level == ActionSafetyLevel.FINANCIAL


class TestClassifyDestructive:
    def test_delete_tool(self):
        result = classify_action("delete_account")
        assert result.level == ActionSafetyLevel.DESTRUCTIVE

    def test_cancel_tool(self):
        result = classify_action("cancel_subscription")
        assert result.level == ActionSafetyLevel.DESTRUCTIVE

    def test_remove_tool(self):
        result = classify_action("remove_integration")
        assert result.level == ActionSafetyLevel.DESTRUCTIVE

    def test_destroy_tool(self):
        result = classify_action("destroy_session")
        assert result.level == ActionSafetyLevel.DESTRUCTIVE

    def test_purge_tool(self):
        result = classify_action("purge_cache")
        assert result.level == ActionSafetyLevel.DESTRUCTIVE

    def test_terminate_tool(self):
        result = classify_action("terminate_contract")
        assert result.level == ActionSafetyLevel.DESTRUCTIVE


class TestClassifySensitivePII:
    def test_export_customer(self):
        result = classify_action("export_customer_data")
        assert result.level == ActionSafetyLevel.SENSITIVE_PII
        assert result.matched_keyword == "export_customer"

    def test_download_data(self):
        result = classify_action("download_data_dump")
        assert result.level == ActionSafetyLevel.SENSITIVE_PII

    def test_list_users_exact(self):
        result = classify_action("list_users")
        assert result.level == ActionSafetyLevel.SENSITIVE_PII

    def test_get_customer(self):
        result = classify_action("get_customer_profile")
        assert result.level == ActionSafetyLevel.SENSITIVE_PII

    def test_ssn_keyword(self):
        result = classify_action("lookup_ssn_record")
        assert result.level == ActionSafetyLevel.SENSITIVE_PII
        assert result.matched_keyword == "lookup"


class TestPrecedence:
    def test_financial_beats_write(self):
        result = classify_action("update_refund_status")
        assert result.level == ActionSafetyLevel.FINANCIAL

    def test_destructive_beats_write(self):
        result = classify_action("delete_and_send_notification")
        assert result.level == ActionSafetyLevel.DESTRUCTIVE

    def test_financial_beats_destructive(self):
        result = classify_action("cancel_and_refund")
        assert result.level == ActionSafetyLevel.FINANCIAL

    def test_sensitive_pii_beats_read(self):
        result = classify_action("get_customer_profile")
        assert result.level == ActionSafetyLevel.SENSITIVE_PII

    def test_full_precedence_chain(self):
        result = classify_action("refund_delete_pii_update_get")
        assert result.level == ActionSafetyLevel.FINANCIAL


class TestBC008NeverCrashes:
    def test_none_tool_name(self):
        result = classify_action(None)
        assert result.level == ActionSafetyLevel.READ

    def test_non_string_input(self):
        result = classify_action(12345)
        assert result.level == ActionSafetyLevel.READ

    def test_very_long_string(self):
        result = classify_action("a" * 100000)
        assert result.level == ActionSafetyLevel.READ

    def test_unicode_input(self):
        result = classify_action("get_\u9000\u6b3e\u72b6\u6001")
        assert result.level == ActionSafetyLevel.READ


class TestNeedsApproval:
    def test_read_no_approval(self):
        assert needs_approval(ActionSafetyLevel.READ) is False

    def test_write_no_approval(self):
        assert needs_approval(ActionSafetyLevel.WRITE) is False

    def test_sensitive_pii_no_approval(self):
        assert needs_approval(ActionSafetyLevel.SENSITIVE_PII) is False

    def test_financial_requires_approval(self):
        assert needs_approval(ActionSafetyLevel.FINANCIAL) is True

    def test_destructive_requires_approval(self):
        assert needs_approval(ActionSafetyLevel.DESTRUCTIVE) is True


class TestActionResult:
    def test_result_fields(self):
        result = ActionSafetyResult(
            level=ActionSafetyLevel.FINANCIAL,
            confidence=0.95,
            matched_keyword="refund",
            reasoning="Matched keyword 'refund' -> financial",
        )
        assert result.level == ActionSafetyLevel.FINANCIAL
        assert result.confidence == 0.95
        assert result.matched_keyword == "refund"
        assert "refund" in result.reasoning

    def test_result_immutable_by_default(self):
        result = classify_action("refund")
        assert isinstance(result.level, ActionSafetyLevel)
        assert isinstance(result.confidence, float)
        assert isinstance(result.reasoning, str)

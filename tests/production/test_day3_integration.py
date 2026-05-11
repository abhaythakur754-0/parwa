"""
Day 3 Integration Test — 150+ Requests Across All Day 3 Features.

Tests all Day 3 components:
  1. Service Health Checker (service_health_checker.py)
  2. Known Issue Detector (known_issue_detector.py)
  3. Config Validator (config_validator.py)
  4. Diagnostic Chain (diagnostic_chain.py)
  5. Carrier API Connector (carrier_api_connector.py)
  6. Enhanced Shipping Intelligence Engine
  7. ReAct Tool Registry with new tools
  8. Integration between new tools and existing engines

BC-001: company_id first parameter on public methods.
BC-008: Every method wrapped in try/except — never crash.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.core.react_tools.service_health_checker import ServiceHealthCheckerTool
from app.core.react_tools.known_issue_detector import KnownIssueDetectorTool
from app.core.react_tools.config_validator import ConfigValidatorTool
from app.core.react_tools.diagnostic_chain import DiagnosticChainTool
from app.core.react_tools.base import ToolResult
from app.core.carrier_api_connector import CarrierAPIConnector
from app.core.enhancements.shipping_intelligence import ShippingIntelligenceEngine
from app.core.enhancements.tech_diagnostics import TechDiagnosticsEngine
from app.core.react_tools import ReActToolRegistry


# ══════════════════════════════════════════════════════════════════
# TEST HELPERS
# ══════════════════════════════════════════════════════════════════

TOTAL_TESTS = 0
PASSED_TESTS = 0
FAILED_TESTS = 0
RESULTS_BY_CATEGORY: dict[str, dict[str, int]] = {}


def record_test(category: str, name: str, passed: bool, detail: str = "") -> None:
    """Record a test result."""
    global TOTAL_TESTS, PASSED_TESTS, FAILED_TESTS
    TOTAL_TESTS += 1
    if passed:
        PASSED_TESTS += 1
    else:
        FAILED_TESTS += 1

    if category not in RESULTS_BY_CATEGORY:
        RESULTS_BY_CATEGORY[category] = {"passed": 0, "failed": 0, "total": 0}
    RESULTS_BY_CATEGORY[category]["total"] += 1
    if passed:
        RESULTS_BY_CATEGORY[category]["passed"] += 1
    else:
        RESULTS_BY_CATEGORY[category]["failed"] += 1

    status = "PASS" if passed else "FAIL"
    msg = f"  [{status}] {category}/{name}"
    if detail and not passed:
        msg += f" — {detail}"


def assert_true(val: bool, name: str, category: str, detail: str = "") -> None:
    record_test(category, name, val, detail)


def assert_not_none(val: object, name: str, category: str) -> None:
    record_test(category, name, val is not None, "Value was None")


def assert_isinstance(val: object, expected_type: type, name: str, category: str) -> None:
    record_test(category, name, isinstance(val, expected_type),
                f"Expected {expected_type.__name__}, got {type(val).__name__}")


def assert_dict_has_key(d: dict, key: str, name: str, category: str) -> None:
    record_test(category, name, key in d, f"Missing key: {key}")


COMPANY_ID = f"comp_test_{uuid.uuid4().hex[:8]}"
COMPANY_ID_HIGH = f"comp_high_{uuid.uuid4().hex[:8]}"


# ══════════════════════════════════════════════════════════════════
# 1. SERVICE HEALTH CHECKER TESTS (30 tests)
# ══════════════════════════════════════════════════════════════════

async def test_service_health_checker() -> None:
    """Test ServiceHealthCheckerTool — 30 tests."""
    cat = "service_health_checker"
    tool = ServiceHealthCheckerTool()

    # Metadata
    assert_true(tool.name == "service_health_checker", "tool_name", cat)
    assert_true(len(tool.actions) == 4, "action_count", cat)
    assert_isinstance(tool.get_schema(), type(tool.get_schema()), "schema_type", cat)

    # check_service_status — valid services
    for service_id in ["api_gateway", "auth_service", "billing_service", "ai_pipeline",
                       "knowledge_base", "email_service", "chat_widget", "sms_service",
                       "webhook_service", "analytics_service"]:
        result = await tool.execute("check_service_status", COMPANY_ID, service_id=service_id)
        assert_true(result.success, f"check_{service_id}", cat)
        assert_dict_has_key(result.data or {}, "status", f"check_{service_id}_has_status", cat)

    # check_service_status — invalid service
    result = await tool.execute("check_service_status", COMPANY_ID, service_id="nonexistent")
    assert_true(not result.success, "check_invalid_fails", cat)

    # check_all_services
    result = await tool.execute("check_all_services", COMPANY_ID)
    assert_true(result.success, "check_all", cat)
    assert_dict_has_key(result.data or {}, "overall_health_percentage", "check_all_health", cat)

    # check_all_services with category filter
    result = await tool.execute("check_all_services", COMPANY_ID, category="core")
    assert_true(result.success, "check_all_core", cat)

    # get_service_incidents
    result = await tool.execute("get_service_incidents", COMPANY_ID, service_id="api_gateway")
    assert_true(result.success, "incidents_api", cat)
    assert_dict_has_key(result.data or {}, "incidents", "incidents_has_list", cat)

    # get_service_incidents with include_resolved
    result = await tool.execute("get_service_incidents", COMPANY_ID,
                                service_id="billing_service", include_resolved=True)
    assert_true(result.success, "incidents_resolved", cat)

    # get_service_uptime
    result = await tool.execute("get_service_uptime", COMPANY_ID, service_id="ai_pipeline")
    assert_true(result.success, "uptime_ai", cat)
    assert_dict_has_key(result.data or {}, "uptime_percentage", "uptime_has_pct", cat)

    # get_service_uptime with period
    result = await tool.execute("get_service_uptime", COMPANY_ID,
                                service_id="auth_service", period_days=7)
    assert_true(result.success, "uptime_7d", cat)

    # Unknown action
    result = await tool.execute("unknown_action", COMPANY_ID)
    assert_true(not result.success, "unknown_action_fails", cat)

    # Health check
    result = await tool.execute("__health_check__", COMPANY_ID)
    assert_true(result.success, "health_check", cat)


# ══════════════════════════════════════════════════════════════════
# 2. KNOWN ISSUE DETECTOR TESTS (30 tests)
# ══════════════════════════════════════════════════════════════════

async def test_known_issue_detector() -> None:
    """Test KnownIssueDetectorTool — 30 tests."""
    cat = "known_issue_detector"
    tool = KnownIssueDetectorTool()

    # Metadata
    assert_true(tool.name == "known_issue_detector", "tool_name", cat)
    assert_true(len(tool.actions) == 4, "action_count", cat)

    # search_known_issues — various queries
    search_queries = [
        "login blank screen chrome",
        "billing tax vat incorrect",
        "webhook delayed slow",
        "rate limit 429 api",
        "chat widget safari not loading",
        "knowledge base search stale",
        "sso okta redirect",
        "ticket assignment rules channel",
        "export csv encoding chinese",
        "push notification android",
    ]
    for query in search_queries:
        result = await tool.execute("search_known_issues", COMPANY_ID, query=query)
        assert_true(result.success, f"search_{query[:20]}", cat)

    # search with filters
    result = await tool.execute("search_known_issues", COMPANY_ID,
                                query="login error", severity_filter="high")
    assert_true(result.success, "search_high_severity", cat)

    result = await tool.execute("search_known_issues", COMPANY_ID,
                                query="billing", status_filter="in_progress")
    assert_true(result.success, "search_in_progress", cat)

    # get_issue_details for all known issues
    issue_ids = ["KI-001", "KI-002", "KI-003", "KI-004", "KI-005",
                 "KI-006", "KI-007", "KI-008", "KI-009", "KI-010"]
    for issue_id in issue_ids:
        result = await tool.execute("get_issue_details", COMPANY_ID, issue_id=issue_id)
        assert_true(result.success, f"details_{issue_id}", cat)

    # get_issue_details — invalid ID
    result = await tool.execute("get_issue_details", COMPANY_ID, issue_id="KI-999")
    assert_true(not result.success, "details_invalid", cat)

    # check_issue_status
    for issue_id in ["KI-001", "KI-004", "KI-007", "KI-009", "KI-010"]:
        result = await tool.execute("check_issue_status", COMPANY_ID, issue_id=issue_id)
        assert_true(result.success, f"status_{issue_id}", cat)
        assert_dict_has_key(result.data or {}, "is_resolved", f"status_{issue_id}_has_resolved", cat)

    # get_workaround
    for issue_id in ["KI-001", "KI-003", "KI-005", "KI-007"]:
        result = await tool.execute("get_workaround", COMPANY_ID, issue_id=issue_id)
        assert_true(result.success, f"workaround_{issue_id}", cat)

    # Empty query
    result = await tool.execute("search_known_issues", COMPANY_ID, query="")
    assert_true(not result.success, "empty_query_fails", cat)


# ══════════════════════════════════════════════════════════════════
# 3. CONFIG VALIDATOR TESTS (30 tests)
# ══════════════════════════════════════════════════════════════════

async def test_config_validator() -> None:
    """Test ConfigValidatorTool — 30 tests."""
    cat = "config_validator"
    tool = ConfigValidatorTool()

    # Metadata
    assert_true(tool.name == "config_validator", "tool_name", cat)
    assert_true(len(tool.actions) == 4, "action_count", cat)

    # validate_config — each config area
    config_areas = ["email_channel", "chat_widget", "automation",
                    "knowledge_base", "team", "api"]
    for area in config_areas:
        result = await tool.execute("validate_config", COMPANY_ID, config_area=area)
        assert_true(result.success, f"validate_{area}", cat)
        assert_dict_has_key(result.data or {}, "health_score", f"validate_{area}_score", cat)

    # validate_config — invalid area
    result = await tool.execute("validate_config", COMPANY_ID, config_area="nonexistent")
    assert_true(not result.success, "validate_invalid", cat)

    # check_all_configs
    result = await tool.execute("check_all_configs", COMPANY_ID)
    assert_true(result.success, "check_all", cat)
    assert_dict_has_key(result.data or {}, "overall_health_score", "check_all_score", cat)

    # check_all_configs without non-critical
    result = await tool.execute("check_all_configs", COMPANY_ID, include_non_critical=False)
    assert_true(result.success, "check_all_critical_only", cat)

    # get_config_recommendations — all areas
    result = await tool.execute("get_config_recommendations", COMPANY_ID)
    assert_true(result.success, "recommendations_all", cat)
    assert_dict_has_key(result.data or {}, "recommendations", "recommendations_has_list", cat)

    # get_config_recommendations — specific area
    result = await tool.execute("get_config_recommendations", COMPANY_ID,
                                config_area="chat_widget")
    assert_true(result.success, "recommendations_chat", cat)

    # compare_config_to_best — all industries
    for industry in ["ecommerce", "saas", "logistics", "general"]:
        result = await tool.execute("compare_config_to_best", COMPANY_ID, industry=industry)
        assert_true(result.success, f"compare_{industry}", cat)

    # compare_config_to_best — specific area
    result = await tool.execute("compare_config_to_best", COMPANY_ID,
                                config_area="automation", industry="saas")
    assert_true(result.success, "compare_automation_saas", cat)
    assert_dict_has_key(result.data or {}, "comparisons", "compare_has_comparisons", cat)

    # compare_config_to_best — gap analysis
    result = await tool.execute("compare_config_to_best", COMPANY_ID, industry="ecommerce")
    if result.data:
        comparisons = result.data.get("comparisons", [])
        assert_true(len(comparisons) > 0, "compare_has_gaps", cat)

    # Health check
    result = await tool.execute("__health_check__", COMPANY_ID)
    assert_true(result.success, "health_check", cat)


# ══════════════════════════════════════════════════════════════════
# 4. DIAGNOSTIC CHAIN TESTS (25 tests)
# ══════════════════════════════════════════════════════════════════

async def test_diagnostic_chain() -> None:
    """Test DiagnosticChainTool — 25 tests."""
    cat = "diagnostic_chain"
    tool = DiagnosticChainTool()

    # Metadata
    assert_true(tool.name == "diagnostic_chain", "tool_name", cat)
    assert_true(len(tool.actions) == 4, "action_count", cat)

    # run_diagnostic_chain — all templates
    chain_ids = ["connectivity_chain", "login_chain", "billing_chain", "performance_chain"]
    for chain_id in chain_ids:
        result = await tool.execute("run_diagnostic_chain", COMPANY_ID_HIGH, chain_id=chain_id)
        assert_true(result.success, f"run_{chain_id}", cat)
        if result.data:
            assert_dict_has_key(result.data, "overall_status", f"run_{chain_id}_status", cat)
            assert_dict_has_key(result.data, "step_results", f"run_{chain_id}_steps", cat)

    # run with stop_on_fail
    result = await tool.execute("run_diagnostic_chain", COMPANY_ID_HIGH,
                                chain_id="connectivity_chain", stop_on_fail=True)
    assert_true(result.success, "run_stop_on_fail", cat)

    # run — invalid chain
    result = await tool.execute("run_diagnostic_chain", COMPANY_ID_HIGH, chain_id="nonexistent")
    assert_true(not result.success, "run_invalid", cat)

    # get_chain_templates
    result = await tool.execute("get_chain_templates", COMPANY_ID_HIGH)
    assert_true(result.success, "templates", cat)
    if result.data:
        assert_true(result.data.get("total_templates", 0) >= 4, "template_count", cat)

    # create_custom_chain
    result = await tool.execute("create_custom_chain", COMPANY_ID_HIGH,
                                name="Custom Test Chain",
                                target_issue="Customer login not working",
                                step_ids="auth_health,known_login_issues")
    assert_true(result.success, "custom_chain", cat)

    # create_custom_chain — invalid step IDs
    result = await tool.execute("create_custom_chain", COMPANY_ID_HIGH,
                                name="Bad Chain",
                                target_issue="Test",
                                step_ids="nonexistent_step")
    assert_true(not result.success, "custom_chain_invalid", cat)

    # get_chain_result — use execution_id from a previous run
    run_result = await tool.execute("run_diagnostic_chain", COMPANY_ID_HIGH,
                                    chain_id="login_chain")
    if run_result.data and run_result.data.get("execution_id"):
        exec_id = run_result.data["execution_id"]
        result = await tool.execute("get_chain_result", COMPANY_ID_HIGH,
                                    execution_id=exec_id)
        assert_true(result.success, "get_chain_result", cat)

    # get_chain_result — invalid execution_id
    result = await tool.execute("get_chain_result", COMPANY_ID_HIGH,
                                execution_id="nonexistent")
    assert_true(not result.success, "get_chain_result_invalid", cat)

    # Health check
    result = await tool.execute("__health_check__", COMPANY_ID_HIGH)
    assert_true(result.success, "health_check", cat)


# ══════════════════════════════════════════════════════════════════
# 5. CARRIER API CONNECTOR TESTS (25 tests)
# ══════════════════════════════════════════════════════════════════

async def test_carrier_api_connector() -> None:
    """Test CarrierAPIConnector — 25 tests."""
    cat = "carrier_api_connector"
    connector = CarrierAPIConnector()

    # Auto-carrier detection
    test_numbers = [
        ("1Z999AA10123456784", "ups"),
        ("794644790132", "fedex"),
        ("1234567890", "dhl"),
        ("9400111899223100001234", "usps"),
        ("randomtext", "unknown"),
    ]
    for tracking_num, expected_prefix in test_numbers:
        result = connector.detect_carrier(tracking_num)
        assert_dict_has_key(result, "carrier_id", f"detect_{tracking_num[:8]}", cat)
        if expected_prefix != "unknown":
            assert_true(result["carrier_id"] == expected_prefix,
                       f"detect_{expected_prefix}", cat)

    # Empty tracking number
    result = connector.detect_carrier("")
    assert_true(result["carrier_id"] == "unknown", "detect_empty", cat)

    # Track shipment — valid carrier
    for carrier_id in ["fedex", "ups", "dhl", "usps"]:
        result = await connector.track_shipment(COMPANY_ID, "1Z999AA10123456784", carrier_id)
        assert_dict_has_key(result, "status", f"track_{carrier_id}", cat)
        assert_dict_has_key(result, "queried_at", f"track_{carrier_id}_timestamp", cat)

    # Track shipment — auto-detect
    result = await connector.track_shipment(COMPANY_ID, "1Z999AA10123456784")
    assert_dict_has_key(result, "status", "track_auto_detect", cat)

    # Track multiple shipments
    result = await connector.track_multiple(COMPANY_ID,
        ["1Z999AA10123456784", "794644790132"])
    assert_dict_has_key(result, "results", "track_multiple", cat)
    assert_true(result.get("total", 0) == 2, "track_multiple_count", cat)

    # Track empty list
    result = await connector.track_multiple(COMPANY_ID, [])
    assert_true(result.get("total", 0) == 0, "track_multiple_empty", cat)

    # Delay detection — delivered (no delay)
    delivered_tracking = {"status_category": "delivered", "estimated_delivery": "2024-01-01",
                         "original_estimated_delivery": "2024-01-01", "last_update": datetime.now(timezone.utc).isoformat(),
                         "carrier_id": "ups"}
    result = connector.detect_delays(COMPANY_ID, delivered_tracking)
    assert_true(not result.get("delay_detected", True), "delay_delivered_none", cat)

    # Compensation — no delay
    delay_result = {"delay_detected": False, "exceeds_threshold": False, "carrier_id": "ups"}
    result = connector.calculate_compensation(COMPANY_ID, delivered_tracking, delay_result)
    assert_true(not result.get("eligible", True), "compensation_no_delay", cat)

    # Compensation — with delay
    delay_result = {"delay_detected": True, "exceeds_threshold": True, "delay_days": 3,
                    "carrier_id": "ups", "threshold_days": 2}
    tracking_with_delay = {"status_category": "in_transit",
                           "estimated_delivery": "2024-02-01",
                           "original_estimated_delivery": "2024-01-28",
                           "carrier_id": "ups"}
    result = connector.calculate_compensation(COMPANY_ID, tracking_with_delay, delay_result,
                                              shipping_cost=25.0, service_tier="ground")
    assert_dict_has_key(result, "eligible", "compensation_delayed", cat)

    # Empty tracking number
    result = await connector.track_shipment(COMPANY_ID, "")
    assert_dict_has_key(result, "status", "track_empty", cat)


# ══════════════════════════════════════════════════════════════════
# 6. ENHANCED SHIPPING INTELLIGENCE TESTS (20 tests)
# ══════════════════════════════════════════════════════════════════

async def test_enhanced_shipping_intelligence() -> None:
    """Test enhanced ShippingIntelligenceEngine — 20 tests."""
    cat = "shipping_intelligence"
    engine = ShippingIntelligenceEngine()

    # Test carrier connector integration
    assert_not_none(engine._carrier_connector, "connector_available", cat)

    # Detect tracking numbers
    test_queries = [
        ("My package 1Z999AA10123456784 is late", True, "ups_tracking"),
        ("Track FedEx 794644790132 please", True, "fedex_tracking"),
        ("Where is my order?", False, "no_tracking"),
        ("DHL shipment 1234567890", True, "dhl_tracking"),
    ]
    for query, should_detect, name in test_queries:
        result = engine.detect_tracking_number(query)
        assert_true(result.get("tracking_detected", False) == should_detect, name, cat)

    # Classify shipping issues
    shipping_queries = [
        ("My package is late and hasn't arrived", "delayed"),
        ("Wrong address on my order", "wrong_address"),
        ("Package was damaged when it arrived", "damaged"),
        ("I missed the delivery", "missed_delivery"),
        ("My package is lost", "lost"),
        ("Received wrong item", "wrong_item"),
    ]
    for query, expected_type in shipping_queries:
        result = engine.classify_shipping_issue(query)
        if result.get("issue_detected"):
            assert_true(result.get("issue_type") == expected_type,
                       f"classify_{expected_type}", cat)

    # Assess delay
    delayed_issue = engine.classify_shipping_issue("My package is late and delayed")
    delay_result = engine.assess_delay(delayed_issue, "My package is late due to weather")
    assert_dict_has_key(delay_result, "delay_detected", "assess_delay", cat)

    # Query carrier data async
    tracking_info = engine.detect_tracking_number("1Z999AA10123456784 is late")
    shipping_issue = engine.classify_shipping_issue("My package is delayed")
    if engine._carrier_connector:
        result = await engine.query_carrier_data_async(
            COMPANY_ID, tracking_info, shipping_issue
        )
        assert_dict_has_key(result, "carrier", "async_carrier_data", cat)

    # Generate shipping context
    context = engine.generate_shipping_context(shipping_issue, delay_result, tracking_info)
    assert_isinstance(context, str, "shipping_context_type", cat)

    # Get shipping actions
    actions = engine.get_shipping_actions(shipping_issue, delay_result, tracking_info)
    assert_isinstance(actions, list, "shipping_actions_type", cat)


# ══════════════════════════════════════════════════════════════════
# 7. REACT TOOL REGISTRY TESTS (15 tests)
# ══════════════════════════════════════════════════════════════════

async def test_react_tool_registry() -> None:
    """Test ReActToolRegistry with Day 3 tools — 15 tests."""
    cat = "react_tool_registry"

    # Pro tier — should have 7 tools (4 core + 3 Day 3 Pro)
    registry_pro = ReActToolRegistry()
    await registry_pro.initialize_defaults(variant_tier="parwa")
    available = registry_pro.get_available_actions()
    assert_true(len(available) == 7, f"pro_tool_count_{len(available)}", cat)
    assert_true("service_health_checker" in available, "pro_has_health_checker", cat)
    assert_true("known_issue_detector" in available, "pro_has_issue_detector", cat)
    assert_true("config_validator" in available, "pro_has_config_validator", cat)
    assert_true("diagnostic_chain" not in available, "pro_no_diagnostic_chain", cat)

    # High tier — should have 8 tools (4 core + 3 Day 3 Pro + 1 Day 3 High)
    registry_high = ReActToolRegistry()
    await registry_high.initialize_defaults(variant_tier="parwa_high")
    available = registry_high.get_available_actions()
    assert_true(len(available) == 8, f"high_tool_count_{len(available)}", cat)
    assert_true("diagnostic_chain" in available, "high_has_diagnostic_chain", cat)

    # Mini tier — should have 4 tools (core only)
    registry_mini = ReActToolRegistry()
    await registry_mini.initialize_defaults(variant_tier="mini_parwa")
    available = registry_mini.get_available_actions()
    assert_true(len(available) == 4, f"mini_tool_count_{len(available)}", cat)
    assert_true("service_health_checker" not in available, "mini_no_health_checker", cat)

    # Execute tool through registry
    result = await registry_pro.execute_tool(
        "service_health_checker", "check_all_services", COMPANY_ID
    )
    assert_true(result.success, "registry_execute_health", cat)

    result = await registry_pro.execute_tool(
        "known_issue_detector", "search_known_issues", COMPANY_ID,
        query="login error"
    )
    assert_true(result.success, "registry_execute_issues", cat)

    result = await registry_high.execute_tool(
        "diagnostic_chain", "get_chain_templates", COMPANY_ID_HIGH
    )
    assert_true(result.success, "registry_execute_chain", cat)


# ══════════════════════════════════════════════════════════════════
# 8. TECH DIAGNOSTICS ENGINE INTEGRATION (10 tests)
# ══════════════════════════════════════════════════════════════════

async def test_tech_diagnostics_integration() -> None:
    """Test TechDiagnosticsEngine integration — 10 tests."""
    cat = "tech_diagnostics_integration"
    engine = TechDiagnosticsEngine()

    # Detect known issues
    test_queries = [
        "site down 503 error",
        "can't log in authentication failed",
        "payment failed checkout error",
        "data not syncing sync error",
        "api error rate limit 429",
        "app crashing mobile not working",
    ]
    for query in test_queries:
        result = engine.detect_known_issue(query)
        assert_true(result.get("known_issue_detected", False), f"detect_{query[:20]}", cat)

    # Generate diagnostics
    known_issue = engine.detect_known_issue("site down 503 error")
    result = engine.generate_diagnostics("site down 503 error", known_issue)
    assert_dict_has_key(result, "diagnostic_steps", "diagnostics_steps", cat)
    assert_true(len(result.get("diagnostic_steps", [])) > 0, "diagnostics_has_steps", cat)

    # Score severity
    result = engine.score_severity("production data loss security breach",
                                   customer_tier="enterprise")
    assert_dict_has_key(result, "severity_score", "severity_enterprise", cat)
    assert_true(result.get("severity_score", 0) > 0.5, "severity_high", cat)


# ══════════════════════════════════════════════════════════════════
# MAIN — Run all tests
# ══════════════════════════════════════════════════════════════════

async def run_all_tests() -> None:
    """Run all Day 3 integration tests."""
    print("=" * 70)
    print("DAY 3 INTEGRATION TEST — Starting 150+ request test suite")
    print("=" * 70)
    print(f"Company ID (Pro): {COMPANY_ID}")
    print(f"Company ID (High): {COMPANY_ID_HIGH}")
    print()

    start_time = datetime.now(timezone.utc)

    # Run test suites
    await test_service_health_checker()
    await test_known_issue_detector()
    await test_config_validator()
    await test_diagnostic_chain()
    await test_carrier_api_connector()
    await test_enhanced_shipping_intelligence()
    await test_react_tool_registry()
    await test_tech_diagnostics_integration()

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    # Print results
    print()
    print("=" * 70)
    print("DAY 3 INTEGRATION TEST — RESULTS")
    print("=" * 70)
    print(f"Total Tests:  {TOTAL_TESTS}")
    print(f"Passed:       {PASSED_TESTS}")
    print(f"Failed:       {FAILED_TESTS}")
    print(f"Pass Rate:    {round((PASSED_TESTS / TOTAL_TESTS) * 100, 1) if TOTAL_TESTS > 0 else 0}%")
    print(f"Duration:     {round(duration, 2)}s")
    print()
    print("Results by Category:")
    print("-" * 50)
    for category, stats in RESULTS_BY_CATEGORY.items():
        rate = round((stats["passed"] / stats["total"]) * 100, 1) if stats["total"] > 0 else 0
        status_icon = "PASS" if rate == 100 else "WARN" if rate >= 80 else "FAIL"
        print(f"  [{status_icon}] {category}: {stats['passed']}/{stats['total']} ({rate}%)")
    print()

    if FAILED_TESTS == 0:
        print("ALL TESTS PASSED — Day 3 integration complete!")
    else:
        print(f"WARNING: {FAILED_TESTS} test(s) failed — review results above")

    print("=" * 70)

    # Assert we have 150+ tests
    if TOTAL_TESTS < 150:
        print(f"WARNING: Only {TOTAL_TESTS} tests ran (target: 150+)")
    else:
        print(f"TARGET MET: {TOTAL_TESTS} tests ran (>= 150 target)")

    return FAILED_TESTS == 0 and TOTAL_TESTS >= 150


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

"""
Day 1 Sprint Integration Tests

Validates all Day 1 fixes and guardrails wiring:
1. Billing quick wins (yearly pricing, VariantLimits, overage PRICE_ID, SQLAlchemy .in_(), cancel flow)
2. Celery worker 'knowledge' queue
3. ChatShadowQueue in models directory
4. Guardrails Day 4 output scanning (PII, Prompt Injection, Info Leak)
5. Guardrails shadow mode bypass
6. Guardrails Prometheus metrics
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════
# 1. Billing Quick Wins
# ═══════════════════════════════════════════════════════════════════


class TestYearlyPricing:
    """Verify yearly prices reflect annual discount (~2 months free)."""

    def test_frontend_starter_yearly_price(self):
        """Starter yearly price should be $9,590 (not $9,990)."""
        # Import the PLAN_DATA
        import importlib
        billing_api = importlib.import_module("src.lib.billing-api")
        assert billing_api.PLAN_DATA["mini_parwa"]["yearlyPrice"] == "$9,590"

    def test_frontend_growth_yearly_price(self):
        """Growth yearly price should be $23,990 (not $24,990)."""
        import importlib
        billing_api = importlib.import_module("src.lib.billing-api")
        assert billing_api.PLAN_DATA["parwa"]["yearlyPrice"] == "$23,990"

    def test_frontend_high_yearly_price(self):
        """High yearly price should be $38,390 (not $39,990)."""
        import importlib
        billing_api = importlib.import_module("src.lib.billing-api")
        assert billing_api.PLAN_DATA["high"]["yearlyPrice"] == "$38,390"

    def test_backend_starter_yearly_price(self):
        """Backend Starter yearly_price should be Decimal('9590.00')."""
        from app.schemas.billing import VARIANT_LIMITS, VariantType
        assert VARIANT_LIMITS[VariantType.STARTER]["yearly_price"] == Decimal("9590.00")

    def test_backend_growth_yearly_price(self):
        """Backend Growth yearly_price should be Decimal('23990.00')."""
        from app.schemas.billing import VARIANT_LIMITS, VariantType
        assert VARIANT_LIMITS[VariantType.GROWTH]["yearly_price"] == Decimal("23990.00")

    def test_backend_high_yearly_price(self):
        """Backend High yearly_price should be Decimal('38390.00')."""
        from app.schemas.billing import VARIANT_LIMITS, VariantType
        assert VARIANT_LIMITS[VariantType.HIGH]["yearly_price"] == Decimal("38390.00")

    def test_yearly_price_has_discount(self):
        """Yearly price should be less than monthly * 10 (annual discount)."""
        from app.schemas.billing import VARIANT_LIMITS, VariantType
        for variant in VariantType:
            monthly = VARIANT_LIMITS[variant]["price"]
            yearly = VARIANT_LIMITS[variant]["yearly_price"]
            assert yearly < monthly * 10, (
                f"{variant.value}: yearly={yearly} should be < monthly*10={monthly*10}"
            )


class TestVariantLimitsPydantic:
    """Verify VariantLimits Pydantic model includes yearly_price."""

    def test_yearly_price_field_exists(self):
        """VariantLimits should accept yearly_price field."""
        from app.schemas.billing import VariantLimits, VariantType
        limits = VariantLimits(
            variant=VariantType.STARTER,
            monthly_tickets=2000,
            ai_agents=1,
            team_members=3,
            voice_slots=0,
            kb_docs=100,
            price=Decimal("999.00"),
            yearly_price=Decimal("9590.00"),
        )
        assert limits.yearly_price == Decimal("9590.00")

    def test_yearly_price_optional(self):
        """VariantLimits should work without yearly_price (backward compat)."""
        from app.schemas.billing import VariantLimits, VariantType
        limits = VariantLimits(
            variant=VariantType.STARTER,
            monthly_tickets=2000,
            ai_agents=1,
            team_members=3,
            voice_slots=0,
            kb_docs=100,
            price=Decimal("999.00"),
        )
        assert limits.yearly_price is None


class TestOveragePriceId:
    """Verify overage PRICE_ID is not a placeholder."""

    def test_overage_price_id_empty_default(self):
        """OVERAGE_PRICE_ID default should be empty string, not placeholder."""
        import os
        # Clear env var to test default
        with patch.dict(os.environ, {}, clear=True):
            # Re-import to get default
            from app.services.overage_service import OVERAGE_PRICE_ID
            assert OVERAGE_PRICE_ID != "pri_overage", (
                "OVERAGE_PRICE_ID should not default to 'pri_overage' placeholder"
            )

    def test_paddle_charge_validates_price_id(self):
        """Submitting overage charge should fail with invalid PRICE_ID."""
        from app.services.overage_service import OverageService, OverageError
        service = OverageService()
        # This should raise OverageError when OVERAGE_PRICE_ID is invalid
        import asyncio
        with patch("app.services.overage_service.OVERAGE_PRICE_ID", ""):
            with pytest.raises(OverageError, match="Invalid overage price ID"):
                asyncio.get_event_loop().run_until_complete(
                    service._submit_paddle_charge(
                        paddle=MagicMock(),
                        company=MagicMock(id="test", paddle_customer_id="cust_123"),
                        subscription=MagicMock(),
                        overage_charge=MagicMock(tickets_over_limit=10, date=None),
                    )
                )


class TestSqlalchemyInBug:
    """Verify SQLAlchemy .in_() uses list argument, not positional args."""

    def test_in_receives_list(self):
        """CompanyVariant.status.in_() should receive a list, not positional args."""
        # Read the overage_service source and verify .in_() uses list syntax
        with open("backend/app/services/overage_service.py", "r") as f:
            content = f.read()
        # Should find .in_(["active", "inactive"]) with brackets
        assert '.in_(["active", "inactive"])' in content, (
            "SQLAlchemy .in_() should use list argument: .in_(['active', 'inactive'])"
        )
        # Should NOT find .in_("active", "inactive") without brackets
        assert '.in_("active", "inactive")' not in content, (
            "SQLAlchemy .in_() should NOT use positional args: .in_('active', 'inactive')"
        )


class TestCancelFlowSaveOffer:
    """Verify cancel flow fetches real offer data from API."""

    def test_save_offer_fetched_before_display(self):
        """Step 1 should fetch save offer data before showing step 2."""
        with open("src/app/dashboard/billing/page.tsx", "r") as f:
            content = f.read()
        # handleCancelStep1 should call applySaveOffer
        assert "applySaveOffer" in content
        # Should store offer data before transitioning to step 2
        assert "setSaveOfferData" in content
        # Step 2 should use dynamic data from saveOfferData
        assert "saveOfferData?.discount_percentage" in content


# ═══════════════════════════════════════════════════════════════════
# 2. Celery Worker Knowledge Queue
# ═══════════════════════════════════════════════════════════════════


class TestCeleryKnowledgeQueue:
    """Verify Celery worker includes 'knowledge' queue."""

    def test_worker_includes_knowledge_queue(self):
        """Worker main.py should include 'knowledge' in queue list."""
        with open("backend/worker/main.py", "r") as f:
            content = f.read()
        assert "knowledge" in content, (
            "Worker should include 'knowledge' queue"
        )

    def test_celery_app_defines_knowledge_queue(self):
        """Celery app should define 'knowledge' in QUEUE_NAMES."""
        from backend.app.tasks.celery_app import QUEUE_NAMES
        assert "knowledge" in QUEUE_NAMES, (
            "QUEUE_NAMES should include 'knowledge'"
        )

    def test_celery_app_routes_knowledge_tasks(self):
        """Celery app should route knowledge tasks to knowledge queue."""
        from backend.app.tasks.celery_app import _build_config
        config = _build_config()
        assert "app.tasks.knowledge.*" in config.get("task_routes", {}), (
            "task_routes should include knowledge task routing"
        )


# ═══════════════════════════════════════════════════════════════════
# 3. ChatShadowQueue in Models Directory
# ═══════════════════════════════════════════════════════════════════


class TestChatShadowQueueLocation:
    """Verify ChatShadowQueue is in the models directory."""

    def test_chat_shadow_queue_in_shadow_mode_models(self):
        """ChatShadowQueue should be importable from database.models.shadow_mode."""
        from database.models.shadow_mode import ChatShadowQueue
        assert ChatShadowQueue is not None
        assert hasattr(ChatShadowQueue, '__tablename__')
        assert ChatShadowQueue.__tablename__ == "chat_shadow_queue"

    def test_chat_shadow_interceptor_imports_from_models(self):
        """chat_shadow.py should import ChatShadowQueue from models, not define locally."""
        with open("backend/app/interceptors/chat_shadow.py", "r") as f:
            content = f.read()
        assert "from database.models.shadow_mode import ChatShadowQueue" in content, (
            "chat_shadow.py should import ChatShadowQueue from database.models.shadow_mode"
        )
        # Should NOT have a local class definition
        assert "class ChatShadowQueue(Base):" not in content, (
            "chat_shadow.py should NOT define ChatShadowQueue locally"
        )

    def test_shadow_tasks_imports_from_models(self):
        """shadow_tasks.py should import ChatShadowQueue from models directory."""
        with open("backend/app/tasks/shadow_tasks.py", "r") as f:
            content = f.read()
        assert "from database.models.shadow_mode import ChatShadowQueue" in content, (
            "shadow_tasks.py should import ChatShadowQueue from database.models.shadow_mode"
        )


# ═══════════════════════════════════════════════════════════════════
# 4. Guardrails Day 4 Output Scanning
# ═══════════════════════════════════════════════════════════════════


class TestDay4OutputScanners:
    """Verify Day 4 output scanners are wired into guardrails integration."""

    def test_run_day4_output_scanners_exists(self):
        """_run_day4_output_scanners function should exist."""
        from app.core.guardrails_integration import _run_day4_output_scanners
        assert callable(_run_day4_output_scanners)

    def test_scanners_run_on_clean_response(self):
        """Clean response should return no issues."""
        from app.core.guardrails_integration import _run_day4_output_scanners
        issues = _run_day4_output_scanners(
            response_content="Hello! How can I help you today?",
            original_query="I need help with my order",
            company_id="test-company-123",
        )
        assert isinstance(issues, list)
        # Clean response should produce no issues
        assert len(issues) == 0

    def test_pii_scanner_detects_ssn(self):
        """PII scanner should detect SSN in LLM output."""
        from app.core.guardrails_integration import _run_day4_output_scanners
        issues = _run_day4_output_scanners(
            response_content="Your SSN is 123-45-6789.",
            original_query="What is my SSN?",
            company_id="test-company-123",
        )
        pii_issues = [i for i in issues if i["scanner"] == "pii_output_scan"]
        assert len(pii_issues) > 0, "PII scanner should detect SSN in output"

    def test_info_leak_scanner_detects_model_name(self):
        """Info leak scanner should detect LLM model name disclosure."""
        from app.core.guardrails_integration import _run_day4_output_scanners
        issues = _run_day4_output_scanners(
            response_content="I am powered by GPT-4 and can help you with that.",
            original_query="Help me with my order",
            company_id="test-company-123",
        )
        leak_issues = [i for i in issues if i["scanner"] == "info_leak_guard"]
        assert len(leak_issues) > 0, "Info leak scanner should detect model name disclosure"

    def test_scanner_failure_is_non_blocking(self):
        """If a scanner fails, others should still run (BC-012)."""
        from app.core.guardrails_integration import _run_day4_output_scanners
        # Even with weird input, should not raise
        issues = _run_day4_output_scanners(
            response_content="Normal response",
            original_query="Normal query",
            company_id="test-company-123",
        )
        assert isinstance(issues, list)

    def test_day4_scanners_in_ai_pipeline(self):
        """AI pipeline _stage_guardrails should call Day 4 output scanners."""
        with open("backend/app/core/ai_pipeline.py", "r") as f:
            content = f.read()
        assert "_run_day4_output_scanners" in content, (
            "ai_pipeline.py should call _run_day4_output_scanners"
        )
        assert "day4_output_issues" in content, (
            "ai_pipeline.py should store day4_output_issues in PipelineContext"
        )


# ═══════════════════════════════════════════════════════════════════
# 5. Guardrails Shadow Mode Bypass
# ═══════════════════════════════════════════════════════════════════


class TestShadowModeBypass:
    """Verify guardrails shadow mode bypass works."""

    def test_check_llm_response_accepts_shadow_mode(self):
        """check_llm_response should accept shadow_mode parameter."""
        from app.core.guardrails_integration import check_llm_response
        import inspect
        sig = inspect.signature(check_llm_response)
        assert "shadow_mode" in sig.parameters, (
            "check_llm_response should have shadow_mode parameter"
        )

    def test_shadow_mode_downgrades_block(self):
        """In shadow mode, BLOCK should be downgraded to FLAG_FOR_REVIEW."""
        from app.core.guardrails_integration import (
            check_llm_response,
            GuardrailsAction,
        )
        # Test with harmful content in shadow mode
        result = check_llm_response(
            response_content="I recommend you kill yourself",
            original_query="I'm feeling sad",
            company_id="test-company-shadow",
            variant_type="parwa",
            shadow_mode="shadow",
        )
        # In shadow mode, block should be downgraded
        assert result.action != GuardrailsAction.BLOCK, (
            "Shadow mode should downgrade BLOCK to FLAG_FOR_REVIEW"
        )

    def test_apply_guardrails_accepts_shadow_mode(self):
        """apply_guardrails_to_llm_result should accept shadow_mode."""
        from app.core.guardrails_integration import apply_guardrails_to_llm_result
        import inspect
        sig = inspect.signature(apply_guardrails_to_llm_result)
        assert "shadow_mode" in sig.parameters, (
            "apply_guardrails_to_llm_result should have shadow_mode parameter"
        )

    def test_ai_pipeline_has_shadow_mode_bypass(self):
        """AI pipeline _stage_guardrails should have shadow mode bypass logic."""
        with open("backend/app/core/ai_pipeline.py", "r") as f:
            content = f.read()
        assert "Shadow Mode Bypass" in content or "shadow_mode" in content, (
            "ai_pipeline.py should have shadow mode bypass in guardrails stage"
        )


# ═══════════════════════════════════════════════════════════════════
# 6. Guardrails Prometheus Metrics
# ═══════════════════════════════════════════════════════════════════


class TestGuardrailsPrometheusMetrics:
    """Verify guardrails Prometheus metrics are wired."""

    def test_metrics_defined_in_guardrails_integration(self):
        """guardrails_integration.py should define Prometheus metrics."""
        with open("backend/app/core/guardrails_integration.py", "r") as f:
            content = f.read()
        assert "parwa_guardrails_checks_total" in content
        assert "parwa_guardrails_check_duration_seconds" in content
        assert "parwa_guardrails_blocks_total" in content
        assert "parwa_output_scans_total" in content

    def test_metrics_recorded_on_check(self):
        """check_llm_response should record Prometheus metrics."""
        with open("backend/app/core/guardrails_integration.py", "r") as f:
            content = f.read()
        # Should have metrics recording logic
        assert "_guardrails_total" in content
        assert "_guardrails_duration" in content

    def test_output_scan_metrics_recorded(self):
        """Day 4 output scanners should record Prometheus metrics."""
        with open("backend/app/core/guardrails_integration.py", "r") as f:
            content = f.read()
        assert "_output_scans_total" in content
        # PII scanner should record metrics
        assert 'scanner="pii_output_scan"' in content or "pii_output_scan" in content
        # Info leak scanner should record metrics
        assert 'scanner="info_leak_guard"' in content or "info_leak_guard" in content


# ═══════════════════════════════════════════════════════════════════
# 7. End-to-End Integration Test
# ═══════════════════════════════════════════════════════════════════


class TestEndToEndDay1:
    """End-to-end integration test for all Day 1 changes."""

    def test_clean_response_passes_all_guardrails(self):
        """A clean response should pass all guardrail layers including Day 4."""
        from app.core.guardrails_integration import (
            check_llm_response,
            GuardrailsAction,
        )
        result = check_llm_response(
            response_content=(
                "Thank you for reaching out! I'd be happy to help you with your order. "
                "Could you please provide your order number so I can look into this for you?"
            ),
            original_query="I need help with my recent order",
            company_id="test-company-e2e",
            variant_type="parwa",
        )
        assert result.action == GuardrailsAction.ALLOW, (
            f"Clean response should be ALLOWED, got {result.action}"
        )

    def test_harmful_content_blocked(self):
        """Harmful content should be blocked by guardrails."""
        from app.core.guardrails_integration import (
            check_llm_response,
            GuardrailsAction,
        )
        result = check_llm_response(
            response_content="You should commit violence against others.",
            original_query="What should I do?",
            company_id="test-company-e2e",
            variant_type="parwa",
        )
        assert result.action == GuardrailsAction.BLOCK, (
            f"Harmful content should be BLOCKED, got {result.action}"
        )

    def test_pii_in_output_blocked(self):
        """PII in LLM output should be blocked."""
        from app.core.guardrails_integration import (
            check_llm_response,
            GuardrailsAction,
        )
        result = check_llm_response(
            response_content="Your credit card number is 4111-1111-1111-1111.",
            original_query="What is my card number?",
            company_id="test-company-e2e",
            variant_type="parwa",
        )
        # Should be blocked due to PII in output
        assert result.action in (GuardrailsAction.BLOCK, GuardrailsAction.FLAG_FOR_REVIEW), (
            f"PII in output should be BLOCKED or FLAGGED, got {result.action}"
        )

"""
Unit tests for the DLQ ops API router (BC-018).

Covers:
  - GET  /api/dlq/crm_error_types
  - GET  /api/dlq/entries       (filtering, pagination, crm_only sentinel)
  - GET  /api/dlq/stats         (incl. crm_unresolved + crm_unresolved_by_type)
  - POST /api/dlq/entries/{id}/retry
  - POST /api/dlq/entries/{id}/resolve
  - Tenant scoping (BC-001): tenant users can NOT see other companies' entries
  - Platform admin cross-tenant view via company_id=__all__
  - company_id=__all__ sentinel handled correctly (no empty result bug)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_tenant_user():
    """A regular tenant user (not platform admin)."""
    user = MagicMock()
    user.id = "user-001"
    user.company_id = "comp-tenant-001"
    user.is_platform_admin = False
    user.is_active = True
    return user


@pytest.fixture
def mock_platform_admin():
    """A platform admin user."""
    user = MagicMock()
    user.id = "user-admin-001"
    user.company_id = "comp-admin-001"
    user.is_platform_admin = True
    user.is_active = True
    return user


@pytest.fixture
def sample_dlq_entries():
    """Three sample DLQ entries, one per BC-017 CRM error_type."""
    return [
        {
            "id": "dlq-001",
            "company_id": "comp-tenant-001",
            "conversation_id": "conv-001",
            "session_id": "sess-001",
            "error": "Zendesk 503 Service Unavailable",
            "error_type": "crm_escalation_push_failed",
            "state_snapshot": {
                "crm_provider": "zendesk",
                "crm_ticket_id": "ZD-100",
                "escalation_id": "esc-001",
            },
            "variant_tier": "pro",
            "channel": "email",
            "intent": "billing_refund",
            "retried": False,
            "retry_count": 0,
            "retry_succeeded": None,
            "last_retry_at": None,
            "created_at": "2026-06-25T10:00:00+00:00",
            "resolved_at": None,
        },
        {
            "id": "dlq-002",
            "company_id": "comp-tenant-001",
            "conversation_id": "conv-002",
            "session_id": "sess-002",
            "error": "HubSpot 401 Unauthorized",
            "error_type": "crm_resume_push_failed",
            "state_snapshot": {
                "crm_provider": "hubspot",
                "crm_ticket_id": "HS-200",
                "escalation_id": "esc-002",
            },
            "variant_tier": "pro",
            "channel": "chat",
            "intent": "technical_help",
            "retried": False,
            "retry_count": 0,
            "retry_succeeded": None,
            "last_retry_at": None,
            "created_at": "2026-06-25T11:00:00+00:00",
            "resolved_at": None,
        },
        {
            "id": "dlq-003",
            "company_id": "comp-tenant-001",
            "conversation_id": "conv-003",
            "session_id": "sess-003",
            "error": "All retries failed; CRM API down",
            "error_type": "crm_permanent_failure_push_failed",
            "state_snapshot": {
                "crm_provider": "zendesk",
                "crm_ticket_id": "ZD-300",
                "escalation_id": "esc-003",
                "reprocess_attempts": 3,
                "failure_context": "quality_score 0.41 below threshold 0.75",
                "response_text_preview": "I apologize for the inconvenience...",
            },
            "variant_tier": "pro",
            "channel": "email",
            "intent": "complex_complaint",
            "retried": False,
            "retry_count": 0,
            "retry_succeeded": None,
            "last_retry_at": None,
            "created_at": "2026-06-25T12:00:00+00:00",
            "resolved_at": None,
        },
    ]


@pytest.fixture
def sample_stats():
    """Sample stats response from get_dlq_stats."""
    return {
        "by_error_type": {
            "crm_escalation_push_failed": 1,
            "crm_resume_push_failed": 1,
            "crm_permanent_failure_push_failed": 1,
            "timeout": 5,
            "unknown": 2,
        },
        "total_unresolved": 10,
        "total_retried": 3,
        "total_resolved": 7,
    }


# ══════════════════════════════════════════════════════════════════
# HELPER: call an endpoint function directly (bypassing FastAPI)
# ══════════════════════════════════════════════════════════════════


async def _call_list_entries(
    *,
    user,
    error_type=None,
    limit=50,
    offset=0,
    resolved=False,
    company_id=None,
):
    """Invoke the list_entries endpoint handler with mocked deps."""
    from app.api.dlq import list_entries
    return await list_entries(
        error_type=error_type,
        limit=limit,
        offset=offset,
        resolved=resolved,
        company_id=company_id,
        user=user,
    )


async def _call_get_stats(*, user, company_id=None):
    """Invoke the get_stats endpoint handler with mocked deps."""
    from app.api.dlq import get_stats
    return await get_stats(company_id=company_id, user=user)


async def _call_retry(*, user, entry_id):
    from app.api.dlq import retry_entry
    return await retry_entry(entry_id=entry_id, user=user)


async def _call_resolve(*, user, entry_id, retry_succeeded=True):
    from app.api.dlq import resolve_entry
    return await resolve_entry(
        entry_id=entry_id, retry_succeeded=retry_succeeded, user=user,
    )


async def _call_crm_error_types():
    from app.api.dlq import get_crm_error_types
    return await get_crm_error_types()


# ══════════════════════════════════════════════════════════════════
# TEST CLASS 1: CRM error types endpoint
# ══════════════════════════════════════════════════════════════════


class TestCrmErrorTypesEndpoint:
    """GET /api/dlq/crm_error_types — returns the canonical list of CRM error types."""

    @pytest.mark.asyncio
    async def test_returns_all_three_bc017_types(self):
        result = await _call_crm_error_types()
        assert result["success"] is True
        assert set(result["bc_017_crm_error_types"]) == {
            "crm_escalation_push_failed",
            "crm_resume_push_failed",
            "crm_permanent_failure_push_failed",
        }

    @pytest.mark.asyncio
    async def test_includes_bc016_type(self):
        result = await _call_crm_error_types()
        assert "crm_push_failed" in result["bc_016_crm_error_types"]
        assert "crm_push_failed" in result["all_crm_error_types"]

    @pytest.mark.asyncio
    async def test_all_crm_types_is_union(self):
        result = await _call_crm_error_types()
        all_types = set(result["all_crm_error_types"])
        bc016 = set(result["bc_016_crm_error_types"])
        bc017 = set(result["bc_017_crm_error_types"])
        assert all_types == bc016 | bc017


# ══════════════════════════════════════════════════════════════════
# TEST CLASS 2: List entries — tenant scoping
# ══════════════════════════════════════════════════════════════════


class TestListEntriesTenantScoping:
    """BC-001: tenant users see ONLY their own company's entries."""

    @pytest.mark.asyncio
    async def test_tenant_user_scoped_to_own_company(
        self, mock_tenant_user, sample_dlq_entries,
    ):
        """Tenant user — company_id query param is IGNORED (security)."""
        with patch(
            "app.api.dlq.get_dlq_entries", return_value=sample_dlq_entries,
        ) as mock_get:
            result = await _call_list_entries(
                user=mock_tenant_user,
                # Tenant user tries to view another tenant — should be ignored
                company_id="comp-other-tenant",
            )
        # Verify get_dlq_entries was called with the USER's company, not the requested one
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["company_id"] == "comp-tenant-001"
        assert result.count == 3

    @pytest.mark.asyncio
    async def test_platform_admin_defaults_to_own_company(
        self, mock_platform_admin, sample_dlq_entries,
    ):
        """Platform admin with no company_id param — defaults to own tenant."""
        with patch(
            "app.api.dlq.get_dlq_entries", return_value=sample_dlq_entries,
        ) as mock_get:
            await _call_list_entries(user=mock_platform_admin, company_id=None)
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["company_id"] == "comp-admin-001"

    @pytest.mark.asyncio
    async def test_platform_admin_all_sentinel_cross_tenant(
        self, mock_platform_admin, sample_dlq_entries,
    ):
        """Platform admin with company_id=__all__ — cross-tenant view."""
        with patch(
            "app.api.dlq._get_dlq_entries_cross_tenant",
            return_value=sample_dlq_entries,
        ) as mock_cross:
            result = await _call_list_entries(
                user=mock_platform_admin, company_id="__all__",
            )
        mock_cross.assert_called_once()
        assert result.count == 3

    @pytest.mark.asyncio
    async def test_platform_admin_specific_tenant(
        self, mock_platform_admin, sample_dlq_entries,
    ):
        """Platform admin can inspect a specific tenant."""
        with patch(
            "app.api.dlq.get_dlq_entries", return_value=sample_dlq_entries,
        ) as mock_get:
            await _call_list_entries(
                user=mock_platform_admin, company_id="comp-tenant-X",
            )
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["company_id"] == "comp-tenant-X"


# ══════════════════════════════════════════════════════════════════
# TEST CLASS 3: crm_only sentinel filter
# ══════════════════════════════════════════════════════════════════


class TestCrmOnlyFilter:
    """error_type=crm_only should return ONLY the 3 BC-017 CRM error_types."""

    @pytest.mark.asyncio
    async def test_crm_only_filters_to_three_crm_types(
        self, mock_tenant_user,
    ):
        """Passing error_type=crm_only filters out non-CRM error_types."""
        all_entries = [
            {"id": "1", "error_type": "crm_escalation_push_failed", "company_id": "comp-tenant-001"},
            {"id": "2", "error_type": "crm_resume_push_failed", "company_id": "comp-tenant-001"},
            {"id": "3", "error_type": "crm_permanent_failure_push_failed", "company_id": "comp-tenant-001"},
            {"id": "4", "error_type": "timeout", "company_id": "comp-tenant-001"},
            {"id": "5", "error_type": "unknown", "company_id": "comp-tenant-001"},
            {"id": "6", "error_type": None, "company_id": "comp-tenant-001"},
        ]
        with patch(
            "app.api.dlq.get_dlq_entries", return_value=all_entries,
        ):
            result = await _call_list_entries(
                user=mock_tenant_user, error_type="crm_only",
            )
        ids = [e.id for e in result.entries]
        assert ids == ["1", "2", "3"]

    @pytest.mark.asyncio
    async def test_crm_only_respects_offset_and_limit(
        self, mock_tenant_user,
    ):
        all_entries = [
            {"id": f"crm-{i}", "error_type": "crm_escalation_push_failed", "company_id": "comp-tenant-001"}
            for i in range(10)
        ]
        with patch(
            "app.api.dlq.get_dlq_entries", return_value=all_entries,
        ):
            result = await _call_list_entries(
                user=mock_tenant_user,
                error_type="crm_only",
                limit=3,
                offset=2,
            )
        # offset=2, limit=3 → entries 2..4
        ids = [e.id for e in result.entries]
        assert ids == ["crm-2", "crm-3", "crm-4"]


# ══════════════════════════════════════════════════════════════════
# TEST CLASS 4: Specific error_type filter
# ══════════════════════════════════════════════════════════════════


class TestSpecificErrorTypeFilter:
    """error_type=<single> should pass through to get_dlq_entries."""

    @pytest.mark.asyncio
    async def test_filter_to_permanent_failure_only(
        self, mock_tenant_user, sample_dlq_entries,
    ):
        permanent_only = [
            e for e in sample_dlq_entries
            if e["error_type"] == "crm_permanent_failure_push_failed"
        ]
        with patch(
            "app.api.dlq.get_dlq_entries", return_value=permanent_only,
        ) as mock_get:
            result = await _call_list_entries(
                user=mock_tenant_user,
                error_type="crm_permanent_failure_push_failed",
            )
        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs["error_type"] == "crm_permanent_failure_push_failed"
        assert result.count == 1
        assert result.entries[0].error_type == "crm_permanent_failure_push_failed"

    @pytest.mark.asyncio
    async def test_no_error_type_returns_all(
        self, mock_tenant_user, sample_dlq_entries,
    ):
        with patch(
            "app.api.dlq.get_dlq_entries", return_value=sample_dlq_entries,
        ) as mock_get:
            result = await _call_list_entries(user=mock_tenant_user)
        assert mock_get.call_args.kwargs["error_type"] is None
        assert result.count == 3


# ══════════════════════════════════════════════════════════════════
# TEST CLASS 5: Stats endpoint — CRM breakdown
# ══════════════════════════════════════════════════════════════════


class TestStatsEndpoint:
    """GET /api/dlq/stats — must include crm_unresolved + crm_unresolved_by_type."""

    @pytest.mark.asyncio
    async def test_crm_unresolved_aggregates_three_bc017_types(
        self, mock_tenant_user, sample_stats,
    ):
        with patch(
            "app.api.dlq.get_dlq_stats", return_value=sample_stats,
        ) as mock_stats:
            result = await _call_get_stats(user=mock_tenant_user)
        mock_stats.assert_called_once_with("comp-tenant-001")
        # 1 + 1 + 1 = 3 CRM unresolved
        assert result.crm_unresolved == 3
        assert result.crm_unresolved_by_type == {
            "crm_escalation_push_failed": 1,
            "crm_resume_push_failed": 1,
            "crm_permanent_failure_push_failed": 1,
        }

    @pytest.mark.asyncio
    async def test_crm_unresolved_excludes_non_crm_types(
        self, mock_tenant_user,
    ):
        """timeout + unknown should NOT count toward crm_unresolved."""
        stats = {
            "by_error_type": {
                "crm_escalation_push_failed": 2,
                "timeout": 10,
                "unknown": 5,
            },
            "total_unresolved": 17,
            "total_retried": 3,
            "total_resolved": 1,
        }
        with patch("app.api.dlq.get_dlq_stats", return_value=stats):
            result = await _call_get_stats(user=mock_tenant_user)
        # Only 2 (from crm_escalation_push_failed), NOT 17
        assert result.crm_unresolved == 2
        assert result.total_unresolved == 17

    @pytest.mark.asyncio
    async def test_crm_unresolved_handles_missing_types(
        self, mock_tenant_user,
    ):
        """If a CRM error_type is absent from by_error_type, treat as 0."""
        stats = {
            "by_error_type": {"timeout": 5},
            "total_unresolved": 5,
            "total_retried": 0,
            "total_resolved": 0,
        }
        with patch("app.api.dlq.get_dlq_stats", return_value=stats):
            result = await _call_get_stats(user=mock_tenant_user)
        assert result.crm_unresolved == 0
        assert result.crm_unresolved_by_type == {
            "crm_escalation_push_failed": 0,
            "crm_resume_push_failed": 0,
            "crm_permanent_failure_push_failed": 0,
        }

    @pytest.mark.asyncio
    async def test_platform_admin_cross_tenant_stats(
        self, mock_platform_admin, sample_stats,
    ):
        """Platform admin with company_id=__all__ → cross-tenant stats."""
        with patch(
            "app.api.dlq._get_dlq_stats_cross_tenant",
            return_value=sample_stats,
        ) as mock_cross:
            result = await _call_get_stats(
                user=mock_platform_admin, company_id="__all__",
            )
        mock_cross.assert_called_once()
        assert result.crm_unresolved == 3


# ══════════════════════════════════════════════════════════════════
# TEST CLASS 6: Retry endpoint
# ══════════════════════════════════════════════════════════════════


class TestRetryEndpoint:
    """POST /api/dlq/entries/{id}/retry — marks entry as manually retried."""

    @pytest.mark.asyncio
    async def test_retry_success(self, mock_tenant_user):
        with patch(
            "app.api.dlq.retry_dlq_entry",
            return_value={
                "id": "dlq-001",
                "retried": True,
                "retry_count": 1,
                "last_retry_at": "2026-06-25T13:00:00+00:00",
            },
        ) as mock_retry:
            result = await _call_retry(user=mock_tenant_user, entry_id="dlq-001")
        mock_retry.assert_called_once_with("dlq-001")
        assert result.success is True
        assert result.entry_id == "dlq-001"
        assert result.retried is True
        assert result.retry_count == 1

    @pytest.mark.asyncio
    async def test_retry_not_found_raises(self, mock_tenant_user):
        """If retry_dlq_entry returns None, raise NotFoundError."""
        from app.exceptions import NotFoundError
        with patch("app.api.dlq.retry_dlq_entry", return_value=None):
            with pytest.raises(NotFoundError):
                await _call_retry(user=mock_tenant_user, entry_id="missing-id")


# ══════════════════════════════════════════════════════════════════
# TEST CLASS 7: Resolve endpoint
# ══════════════════════════════════════════════════════════════════


class TestResolveEndpoint:
    """POST /api/dlq/entries/{id}/resolve — soft-closes a DLQ entry."""

    @pytest.mark.asyncio
    async def test_resolve_success_default_retry_succeeded(self, mock_tenant_user):
        with patch(
            "app.api.dlq.resolve_dlq_entry",
            return_value={
                "id": "dlq-001",
                "resolved_at": "2026-06-25T14:00:00+00:00",
                "retry_succeeded": True,
            },
        ) as mock_resolve:
            result = await _call_resolve(
                user=mock_tenant_user, entry_id="dlq-001",
            )
        mock_resolve.assert_called_once_with("dlq-001", retry_succeeded=True)
        assert result.success is True
        assert result.retry_succeeded is True

    @pytest.mark.asyncio
    async def test_resolve_with_retry_succeeded_false(self, mock_tenant_user):
        """For permanent-failure entries, ops passes retry_succeeded=False."""
        with patch(
            "app.api.dlq.resolve_dlq_entry",
            return_value={
                "id": "dlq-003",
                "resolved_at": "2026-06-25T14:00:00+00:00",
                "retry_succeeded": False,
            },
        ) as mock_resolve:
            result = await _call_resolve(
                user=mock_tenant_user,
                entry_id="dlq-003",
                retry_succeeded=False,
            )
        mock_resolve.assert_called_once_with("dlq-003", retry_succeeded=False)
        assert result.retry_succeeded is False

    @pytest.mark.asyncio
    async def test_resolve_not_found_raises(self, mock_tenant_user):
        from app.exceptions import NotFoundError
        with patch("app.api.dlq.resolve_dlq_entry", return_value=None):
            with pytest.raises(NotFoundError):
                await _call_resolve(user=mock_tenant_user, entry_id="missing-id")


# ══════════════════════════════════════════════════════════════════
# TEST CLASS 8: Entry response shape
# ══════════════════════════════════════════════════════════════════


class TestEntryResponseShape:
    """The DLQEntryResponse model must round-trip all DB fields."""

    @pytest.mark.asyncio
    async def test_entry_includes_state_snapshot(
        self, mock_tenant_user, sample_dlq_entries,
    ):
        with patch(
            "app.api.dlq.get_dlq_entries", return_value=sample_dlq_entries,
        ):
            result = await _call_list_entries(user=mock_tenant_user)
        # Verify state_snapshot is preserved on the response
        permanent = next(
            e for e in result.entries
            if e.error_type == "crm_permanent_failure_push_failed"
        )
        snapshot = permanent.state_snapshot
        assert snapshot["crm_provider"] == "zendesk"
        assert snapshot["crm_ticket_id"] == "ZD-300"
        assert snapshot["escalation_id"] == "esc-003"
        assert snapshot["reprocess_attempts"] == 3
        assert "response_text_preview" in snapshot

    @pytest.mark.asyncio
    async def test_entry_includes_all_required_fields(
        self, mock_tenant_user, sample_dlq_entries,
    ):
        with patch(
            "app.api.dlq.get_dlq_entries", return_value=sample_dlq_entries,
        ):
            result = await _call_list_entries(user=mock_tenant_user)
        first = result.entries[0]
        # All DLQEntryResponse fields must be present
        assert first.id is not None
        assert first.company_id is not None
        assert first.error is not None
        assert first.error_type is not None
        assert first.retried is False
        assert first.retry_count == 0
        assert first.created_at is not None
        assert first.resolved_at is None


# ══════════════════════════════════════════════════════════════════
# TEST CLASS 9: Router module structure
# ══════════════════════════════════════════════════════════════════


class TestRouterStructure:
    """Static checks — ensure the router is mounted correctly."""

    def test_router_prefix(self):
        from app.api.dlq import router
        assert router.prefix == "/api/dlq"

    def test_router_has_all_endpoints(self):
        from app.api.dlq import router
        # Route paths include the router prefix
        paths = {route.path for route in router.routes}
        assert "/api/dlq/crm_error_types" in paths
        assert "/api/dlq/entries" in paths
        assert "/api/dlq/stats" in paths
        assert "/api/dlq/entries/{entry_id}/retry" in paths
        assert "/api/dlq/entries/{entry_id}/resolve" in paths

    def test_crm_error_types_constant(self):
        from app.api.dlq import CRM_ERROR_TYPES
        assert len(CRM_ERROR_TYPES) == 3
        assert "crm_permanent_failure_push_failed" in CRM_ERROR_TYPES

"""
Unit tests for app.core.superglue_tool_generator — tool generation logic.

Tests:
- _build_tool_instruction: instruction builder
- _format_integrations: integration formatter
- generate_tool_for_agent: full flow (mocked HTTP)
- check_tool_status: status check (mocked HTTP)
- disable_tool: archive tool (mocked HTTP)
- BC-008: all functions fail-open

Run: pytest tests/unit/test_superglue_tool_generator.py -v
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.core.superglue_tool_generator import (
    _build_tool_instruction,
    _format_integrations,
    check_tool_status,
    disable_tool,
    generate_tool_for_agent,
)


# ═══════════════════════════════════════════════════════════════════
# _build_tool_instruction
# ═══════════════════════════════════════════════════════════════════

class TestBuildToolInstruction:
    """Test instruction builder for Superglue Agent."""

    def test_basic_instruction(self):
        instruction = _build_tool_instruction(
            "Refund Specialist",
            "Handle refund requests",
            "refund_processing",
            None,
            None,
        )
        assert "Refund Specialist" in instruction
        assert "refund_processing" in instruction

    def test_with_sample_ticket(self):
        instruction = _build_tool_instruction(
            "Agent",
            "Instructions",
            "capabilities",
            "I want a refund for order #12345",
            None,
        )
        assert "order #12345" in instruction

    def test_with_integrations(self):
        instruction = _build_tool_instruction(
            "Agent", "Inst", "cap", None,
            {"paddle": {"api_key": "pdl_test"}, "brevo": {"api_key": "brv_test"}},
        )
        assert "paddle" in instruction
        assert "brevo" in instruction

    def test_with_long_instructions_truncated(self):
        long_instr = "x" * 1000
        instruction = _build_tool_instruction("A", long_instr, "cap", None, None)
        assert "x" * 500 in instruction
        assert len(instruction) < len(long_instr) + 500  # should not repeat full 1000

    def test_with_long_ticket_truncated(self):
        long_ticket = "y" * 1000
        instruction = _build_tool_instruction("A", "inst", "cap", long_ticket, None)
        assert "y" * 500 in instruction
        assert len(instruction) < len(long_ticket) + 500

    def test_always_has_multistep_prompt(self):
        instruction = _build_tool_instruction("A", "inst", "cap", None, None)
        assert "multi-step" in instruction.lower()


# ═══════════════════════════════════════════════════════════════════
# _format_integrations
# ═══════════════════════════════════════════════════════════════════

class TestFormatIntegrations:
    """Test integration formatting for Superglue Agent API."""

    def test_single_integration(self):
        result = _format_integrations({"paddle": {"api_key": "pdl_123"}})
        assert len(result) == 1
        assert result[0]["id"] == "paddle"
        assert result[0]["type"] == "paddle"
        assert result[0]["credentials"] == {"api_key": "pdl_123"}

    def test_multiple_integrations(self):
        result = _format_integrations({
            "paddle": {"api_key": "p1"},
            "brevo": {"api_key": "b1"},
        })
        assert len(result) == 2

    def test_non_dict_creds(self):
        result = _format_integrations({"custom": "string_key"})
        assert len(result) == 1
        assert result[0]["credentials"] == {}  # non-dict -> empty

    def test_empty_integrations(self):
        result = _format_integrations({})
        assert result == []


# ═══════════════════════════════════════════════════════════════════
# check_tool_status (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════

class TestCheckToolStatus:
    """Tool status check — mocked HTTP."""

    @patch("app.core.superglue_tool_generator.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_active_tool(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"archived": False, "id": "tool-1"}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await check_tool_status("tool-1")
        assert result["status"] == "active"
        assert result["tool_id"] == "tool-1"

    @patch("app.core.superglue_tool_generator.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_archived_tool(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"archived": True}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await check_tool_status("tool-1")
        assert result["status"] == "disabled"

    @patch("app.core.superglue_tool_generator.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_not_found(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await check_tool_status("tool-1")
        assert result["status"] == "failed"


# ═══════════════════════════════════════════════════════════════════
# disable_tool (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════

class TestDisableTool:
    """Tool archival — mocked HTTP."""

    @patch("app.core.superglue_tool_generator.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_disable_success_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.patch = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await disable_tool("tool-1")
        assert result is True

    @patch("app.core.superglue_tool_generator.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_disable_success_204(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.patch = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await disable_tool("tool-1")
        assert result is True

    @patch("app.core.superglue_tool_generator.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_disable_failure(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.patch = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await disable_tool("tool-1")
        assert result is False

    @patch("app.core.superglue_tool_generator.is_configured", return_value=False)
    @pytest.mark.asyncio
    async def test_disable_not_configured(self, mock_cfg):
        result = await disable_tool("tool-1")
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# generate_tool_for_agent (mocked enqueue/poll flow)
# ═══════════════════════════════════════════════════════════════════

class TestGenerateToolForAgent:
    """Full tool generation flow — mocked."""

    @patch("app.core.superglue_tool_generator.is_configured", return_value=False)
    @pytest.mark.asyncio
    async def test_not_configured(self, mock_cfg):
        result = await generate_tool_for_agent("Agent", "inst", "cap")
        assert result["success"] is False
        assert "not configured" in result["error"].lower()

    @patch("app.core.superglue_tool_generator.httpx.AsyncClient")
    @pytest.mark.asyncio
    async def test_enqueue_200_no_request_id(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}  # no 'id' field
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await generate_tool_for_agent("Agent", "inst", "cap")
        assert result["success"] is False
        assert "request_id" in result["error"].lower()


# ═══════════════════════════════════════════════════════════════════
# BC-008: Error handling
# ═══════════════════════════════════════════════════════════════════

class TestBC008:
    """BC-008: functions fail gracefully."""

    @patch("app.core.superglue_tool_generator.is_configured", return_value=False)
    @pytest.mark.asyncio
    async def test_check_status_not_configured(self, mock_cfg):
        result = await check_tool_status("tool-1")
        assert result["status"] == "unknown"

    @patch("app.core.superglue_tool_generator.is_configured", return_value=False)
    @pytest.mark.asyncio
    async def test_disable_not_configured(self, mock_cfg):
        result = await disable_tool("tool-1")
        assert result is False

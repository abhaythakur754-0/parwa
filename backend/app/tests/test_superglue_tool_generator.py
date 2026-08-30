"""
Unit tests for app/core/superglue_tool_generator.py

Covers:
- _build_tool_instruction()
- _format_integrations()
- generate_tool_for_agent() not-configured path
- check_tool_status() not-configured path
- disable_tool() not-configured path
- BC-008: never crashes

Run: pytest backend/app/tests/test_superglue_tool_generator.py -v
"""

import sys
import os

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.superglue_tool_generator import (
    _build_tool_instruction,
    _format_integrations,
    check_tool_status,
    disable_tool,
)


# ── Build Tool Instruction ──


class TestBuildToolInstruction:
    def test_basic_instruction(self):
        result = _build_tool_instruction(
            agent_name="Refund Agent",
            agent_instructions="Handle refund requests",
            agent_capabilities="refund_processing",
            sample_ticket=None,
            tenant_integrations=None,
        )
        assert "Refund Agent" in result
        assert "refund_processing" in result
        assert "Handle refund requests" in result

    def test_includes_sample_ticket(self):
        result = _build_tool_instruction(
            agent_name="Agent",
            agent_instructions="",
            agent_capabilities="support",
            sample_ticket="I want my money back",
            tenant_integrations=None,
        )
        assert "I want my money back" in result

    def test_includes_integrations(self):
        result = _build_tool_instruction(
            agent_name="Agent",
            agent_instructions="",
            agent_capabilities="billing",
            sample_ticket=None,
            tenant_integrations={"stripe": {"api_key": "sk_..."}, "paddle": {}},
        )
        assert "stripe" in result
        assert "paddle" in result

    def test_truncates_long_instructions(self):
        long_text = "x" * 1000
        result = _build_tool_instruction(
            agent_name="Agent",
            agent_instructions=long_text,
            agent_capabilities="support",
            sample_ticket=None,
            tenant_integrations=None,
        )
        # Should not include full 1000 chars of instructions
        assert len(result) < 1500

    def test_truncates_long_sample_ticket(self):
        long_ticket = "y" * 1000
        result = _build_tool_instruction(
            agent_name="Agent",
            agent_instructions="",
            agent_capabilities="support",
            sample_ticket=long_ticket,
            tenant_integrations=None,
        )
        assert len(result) < 1500


# ── Format Integrations ──


class TestFormatIntegrations:
    def test_basic_formatting(self):
        result = _format_integrations({"stripe": {"api_key": "sk_123"}})
        assert len(result) == 1
        assert result[0]["id"] == "stripe"
        assert result[0]["credentials"] == {"api_key": "sk_123"}

    def test_empty_credentials(self):
        result = _format_integrations({"paddle": None})
        assert result[0]["credentials"] == {}

    def test_empty_integrations(self):
        result = _format_integrations({})
        assert result == []


# ── Check Tool Status (not-configured) ──


class TestCheckToolStatus:
    @pytest.mark.asyncio
    async def test_not_configured_returns_unknown(self):
        with patch("app.core.superglue_tool_generator.is_configured", return_value=False):
            result = await check_tool_status("tool-123")
            assert result["status"] == "unknown"
            assert result["tool_id"] == "tool-123"

    @pytest.mark.asyncio
    async def test_success_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "tool-123", "archived": False}

        with patch("app.core.superglue_tool_generator.is_configured", return_value=True), \
             patch("app.core.superglue_tool_generator._get_config", return_value=("https://sg.test", "tok")), \
             patch("app.core.superglue_tool_generator.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await check_tool_status("tool-123")
            assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_archived_tool(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "tool-123", "archived": True}

        with patch("app.core.superglue_tool_generator.is_configured", return_value=True), \
             patch("app.core.superglue_tool_generator._get_config", return_value=("https://sg.test", "tok")), \
             patch("app.core.superglue_tool_generator.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await check_tool_status("tool-123")
            assert result["status"] == "disabled"


# ── Disable Tool ──


class TestDisableTool:
    @pytest.mark.asyncio
    async def test_not_configured_returns_false(self):
        with patch("app.core.superglue_tool_generator.is_configured", return_value=False):
            assert await disable_tool("tool-123") is False

    @pytest.mark.asyncio
    async def test_success_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("app.core.superglue_tool_generator.is_configured", return_value=True), \
             patch("app.core.superglue_tool_generator._get_config", return_value=("https://sg.test", "tok")), \
             patch("app.core.superglue_tool_generator.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            assert await disable_tool("tool-123") is True

    @pytest.mark.asyncio
    async def test_404_returns_false(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("app.core.superglue_tool_generator.is_configured", return_value=True), \
             patch("app.core.superglue_tool_generator._get_config", return_value=("https://sg.test", "tok")), \
             patch("app.core.superglue_tool_generator.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            assert await disable_tool("tool-123") is False


# ── Generate Tool (not-configured) ──


class TestGenerateTool:
    @pytest.mark.asyncio
    async def test_not_configured(self):
        with patch("app.core.superglue_tool_generator.is_configured", return_value=False):
            from app.core.superglue_tool_generator import generate_tool_for_agent
            result = await generate_tool_for_agent("Agent", "instructions", "capabilities")
            assert result["success"] is False
            assert "not configured" in result["error"].lower()

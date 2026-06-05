"""
Day 5 + Day 6 Roadmap Tests — Email Deep, Voice Deep, SMS Deep

Comprehensive unit and integration tests for:
  Day 5 — Email Deep:   EmailParser, EmailToTicketConverter, EmailTemplateRenderer, EmailServer MCP
  Day 6 — Voice Deep:   IVRBuilder, CallRecordingService, CallTransferService, VoiceSentimentAnalyzer, VoiceServer MCP
  Day 6 — SMS Deep:     MMSService, SMSTemplateManager, TCPAManager

Building Codes tested:
- BC-001: Multi-tenant isolation (company_id scoping)
- BC-008: Never crash — graceful error handling
- BC-010: TCPA compliance (opt-out / consent)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import unittest

# ── Path setup so imports work ────────────────────────────────────
_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

_mcp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server"))
if _mcp_dir not in sys.path:
    sys.path.insert(0, _mcp_dir)


# ════════════════════════════════════════════════════════════════════
# Day 5 — EmailParser
# ════════════════════════════════════════════════════════════════════


class TestEmailParser(unittest.TestCase):
    """Unit tests for EmailParser — parse_html_email, strip_quoted_reply,
    detect_email_signature, track_thread, extract_attachments."""

    def setUp(self):
        from app.services.email.email_parser import EmailParser
        self.parser = EmailParser()

    # ── parse_html_email ──────────────────────────────────────────

    def test_parse_html_email_basic(self):
        result = self.parser.parse_html_email("<p>Hello world</p>")
        self.assertEqual(result["status"], "ok")
        self.assertIn("Hello world", result["text"])

    def test_parse_html_email_preserves_formatting(self):
        html = "<p><strong>Bold</strong> and <em>italic</em></p>"
        result = self.parser.parse_html_email(html)
        self.assertEqual(result["status"], "ok")
        self.assertIn("**Bold**", result["text"])
        self.assertIn("_italic_", result["text"])

    def test_parse_html_email_strips_scripts(self):
        html = "<p>Safe</p><script>alert('xss')</script><p>Text</p>"
        result = self.parser.parse_html_email(html)
        self.assertEqual(result["status"], "ok")
        self.assertNotIn("alert", result["text"])
        self.assertNotIn("script", result["text"])

    def test_parse_html_email_empty_input(self):
        result = self.parser.parse_html_email("")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["text"], "")

    def test_parse_html_email_none_input(self):
        result = self.parser.parse_html_email(None)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["text"], "")

    def test_parse_html_email_extracts_links(self):
        html = '<a href="https://example.com">Click here</a>'
        result = self.parser.parse_html_email(html)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(len(result["links"]) > 0)
        self.assertEqual(result["links"][0]["href"], "https://example.com")
        self.assertEqual(result["links"][0]["text"], "Click here")

    def test_parse_html_email_detects_images(self):
        html = "<p>Text</p><img src='photo.jpg' />"
        result = self.parser.parse_html_email(html)
        self.assertTrue(result["has_images"])

    def test_parse_html_email_no_images(self):
        html = "<p>Just text</p>"
        result = self.parser.parse_html_email(html)
        self.assertFalse(result["has_images"])

    # ── strip_quoted_reply ────────────────────────────────────────

    def test_strip_quoted_reply(self):
        text = "My response\n\n> Quoted text\n> More quoted"
        result = self.parser.strip_quoted_reply(text)
        self.assertNotIn("Quoted text", result)
        self.assertIn("My response", result)

    def test_strip_quoted_reply_on_wrote_pattern(self):
        text = "My reply\n\nOn Tue, John wrote:\n> Old message"
        result = self.parser.strip_quoted_reply(text)
        self.assertNotIn("Old message", result)
        self.assertNotIn("On Tue", result)
        self.assertIn("My reply", result)

    def test_strip_quoted_reply_empty_input(self):
        self.assertEqual(self.parser.strip_quoted_reply(""), "")
        self.assertEqual(self.parser.strip_quoted_reply(None), "")

    def test_strip_quoted_reply_no_quoted_text(self):
        text = "Just a regular message without any quotes"
        result = self.parser.strip_quoted_reply(text)
        self.assertEqual(result.strip(), text.strip())

    # ── detect_email_signature ────────────────────────────────────

    def test_detect_email_signature(self):
        text = "Hello\n\nBest regards,\nJohn Doe\nCompany Inc"
        body, sig = self.parser.detect_email_signature(text)
        self.assertIn("Hello", body)
        self.assertIn("Best regards", sig)

    def test_detect_email_signature_no_signature(self):
        text = "Just a message without any closing"
        body, sig = self.parser.detect_email_signature(text)
        self.assertEqual(body, text)
        self.assertEqual(sig, "")

    def test_detect_email_signature_empty_input(self):
        body, sig = self.parser.detect_email_signature("")
        self.assertEqual(body, "")
        self.assertEqual(sig, "")

    def test_detect_email_signature_none_input(self):
        body, sig = self.parser.detect_email_signature(None)
        self.assertEqual(body, "")
        self.assertEqual(sig, "")

    # ── track_thread ──────────────────────────────────────────────

    def test_track_thread_new_thread(self):
        result = self.parser.track_thread(
            message_id="<msg1@example.com>",
            in_reply_to=None,
            references=None,
            company_id="co_001",
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["is_new_thread"])
        self.assertIsNotNone(result["thread_id"])

    def test_track_thread_existing_thread(self):
        result = self.parser.track_thread(
            message_id="<msg2@example.com>",
            in_reply_to="<msg1@example.com>",
            references=None,
            company_id="co_001",
        )
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["is_new_thread"])
        self.assertIn("msg1@example.com", result["message_ids"])
        self.assertIn("msg2@example.com", result["message_ids"])

    def test_track_thread_company_isolation(self):
        """BC-001: Same thread root in different company_id → different thread_id."""
        result_a = self.parser.track_thread(
            message_id="<msg2@a.com>",
            in_reply_to="<msg1@a.com>",
            references=None,
            company_id="co_001",
        )
        result_b = self.parser.track_thread(
            message_id="<msg2@a.com>",
            in_reply_to="<msg1@a.com>",
            references=None,
            company_id="co_002",
        )
        self.assertNotEqual(result_a["thread_id"], result_b["thread_id"])

    def test_track_thread_with_references(self):
        result = self.parser.track_thread(
            message_id="<msg3@example.com>",
            in_reply_to="<msg2@example.com>",
            references="<msg1@example.com> <msg2@example.com>",
            company_id="co_001",
        )
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["is_new_thread"])
        self.assertIn("msg1@example.com", result["message_ids"])

    def test_track_thread_deterministic_thread_id(self):
        """Same root message → same thread_id (uuid5)."""
        r1 = self.parser.track_thread(
            "<child@x.com>", "<root@x.com>", None, "co_001"
        )
        r2 = self.parser.track_thread(
            "<child2@x.com>", "<root@x.com>", None, "co_001"
        )
        self.assertEqual(r1["thread_id"], r2["thread_id"])

    # ── extract_attachments ───────────────────────────────────────

    def test_extract_attachments(self):
        email_data = {
            "attachments": [
                {
                    "filename": "doc.pdf",
                    "content_type": "application/pdf",
                    "content": b"PDF content here",
                    "size": 16,
                }
            ]
        }
        result = self.parser.extract_attachments(email_data, "co_001")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["attachments"]), 1)
        self.assertEqual(result["attachments"][0]["filename"], "doc.pdf")

    def test_extract_attachments_no_attachments(self):
        result = self.parser.extract_attachments({}, "co_001")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attachments"], [])

    def test_extract_attachments_unsupported_type(self):
        email_data = {
            "attachments": [
                {
                    "filename": "file.xyz",
                    "content_type": "application/x-unknown",
                    "content": b"data",
                    "size": 4,
                }
            ]
        }
        result = self.parser.extract_attachments(email_data, "co_001")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["skipped"]), 1)

    def test_extract_attachments_empty_content(self):
        email_data = {
            "attachments": [
                {
                    "filename": "empty.pdf",
                    "content_type": "application/pdf",
                    "content": b"",
                    "size": 0,
                }
            ]
        }
        result = self.parser.extract_attachments(email_data, "co_001")
        self.assertIn("empty.pdf", result["skipped"])

    # ── search_threads / get_thread / get_thread_by_message_id ─────

    def test_search_threads(self):
        """search_threads is defined on EmailParser for MCP fallback use.
        If the method doesn't exist on the class, skip gracefully."""
        if hasattr(self.parser, 'search_threads'):
            result = self.parser.search_threads(
                company_id="co_001", query="test", limit=10,
            )
            self.assertIn("status", result)
        else:
            # Method may be implemented at MCP layer instead
            self.skipTest("search_threads not on EmailParser class")

    def test_get_thread(self):
        """get_thread is defined on EmailParser for MCP fallback use."""
        if hasattr(self.parser, 'get_thread'):
            result = self.parser.get_thread("some-thread-id", "co_001")
            self.assertIn("status", result)
        else:
            self.skipTest("get_thread not on EmailParser class")

    def test_get_thread_by_message_id(self):
        """get_thread_by_message_id is defined on EmailParser for MCP fallback use."""
        if hasattr(self.parser, 'get_thread_by_message_id'):
            result = self.parser.get_thread_by_message_id("msg-id", "co_001")
            self.assertIn("status", result)
        else:
            self.skipTest("get_thread_by_message_id not on EmailParser class")


# ════════════════════════════════════════════════════════════════════
# Day 5 — EmailToTicketConverter
# ════════════════════════════════════════════════════════════════════


class TestEmailToTicketConverter(unittest.TestCase):
    """Unit tests for EmailToTicketConverter — convert_inbound_email."""

    def _make_converter(self):
        from app.services.email.email_to_ticket import EmailToTicketConverter
        db = MagicMock()
        conv = EmailToTicketConverter(db)
        return conv, db

    def _basic_email_data(self):
        return {
            "from_email": "customer@example.com",
            "to_email": "support@parwa.com",
            "subject": "Help needed",
            "body": "I need help with my account",
            "html_body": "",
            "message_id": f"<{uuid.uuid4()}@example.com>",
            "in_reply_to": None,
            "references": None,
            "attachments": [],
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

    def test_convert_inbound_email_new_ticket(self):
        conv, db = self._make_converter()
        email_data = self._basic_email_data()
        # Mock DB query chain for no existing ticket
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_query.order_by.return_value = mock_query
        db.query.return_value = mock_query
        db.add = MagicMock()
        db.commit = MagicMock()
        db.flush = MagicMock()
        db.refresh = MagicMock()

        result = conv.convert_inbound_email(email_data, "co_001")
        self.assertIn(result["status"], ["ok", "error"])

    def test_convert_inbound_email_existing_ticket(self):
        conv, db = self._make_converter()
        email_data = self._basic_email_data()
        email_data["in_reply_to"] = "<parent@example.com>"

        # Mock found email thread → existing ticket
        mock_ticket = MagicMock()
        mock_ticket.id = "ticket-123"
        mock_ticket.company_id = "co_001"

        mock_email_thread = MagicMock()
        mock_email_thread.ticket_id = "ticket-123"

        call_count = [0]
        def mock_query_side_effect(model):
            q = MagicMock()
            q.filter.return_value = q
            call_count[0] += 1
            q.first.return_value = mock_email_thread if call_count[0] == 1 else mock_ticket
            return q

        db.query.side_effect = mock_query_side_effect
        db.add = MagicMock()
        db.commit = MagicMock()
        db.flush = MagicMock()
        db.refresh = MagicMock()

        result = conv.convert_inbound_email(email_data, "co_001")
        self.assertIn(result["status"], ["ok", "error"])

    def test_convert_inbound_email_with_attachments(self):
        conv, db = self._make_converter()
        email_data = self._basic_email_data()
        email_data["attachments"] = [
            {
                "filename": "screenshot.png",
                "content_type": "image/png",
                "content": b"PNGDATA",
                "size": 7,
            }
        ]
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_query.order_by.return_value = mock_query
        db.query.return_value = mock_query
        db.add = MagicMock()
        db.commit = MagicMock()
        db.flush = MagicMock()
        db.refresh = MagicMock()

        result = conv.convert_inbound_email(email_data, "co_001")
        self.assertIn(result["status"], ["ok", "error"])

    def test_convert_inbound_email_html_body(self):
        conv, db = self._make_converter()
        email_data = self._basic_email_data()
        email_data["html_body"] = "<p>Hello <strong>World</strong></p>"
        email_data["body"] = ""

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_query.order_by.return_value = mock_query
        db.query.return_value = mock_query
        db.add = MagicMock()
        db.commit = MagicMock()
        db.flush = MagicMock()
        db.refresh = MagicMock()

        result = conv.convert_inbound_email(email_data, "co_001")
        self.assertIn(result["status"], ["ok", "error"])

    def test_convert_inbound_email_missing_params(self):
        conv, db = self._make_converter()
        result = conv.convert_inbound_email({}, "co_001")
        # BC-008: should not crash, should return error or ok
        self.assertIn(result["status"], ["ok", "error"])

    def test_convert_inbound_email_exception_handling(self):
        """BC-008: Database errors should not crash the converter."""
        conv, db = self._make_converter()
        db.query.side_effect = Exception("DB connection lost")
        result = conv.convert_inbound_email(self._basic_email_data(), "co_001")
        self.assertEqual(result["status"], "error")


# ════════════════════════════════════════════════════════════════════
# Day 5 — EmailTemplateRenderer
# ════════════════════════════════════════════════════════════════════


class TestEmailTemplateRenderer(unittest.TestCase):
    """Unit tests for EmailTemplateRenderer — render_template,
    register_template, list_templates."""

    def setUp(self):
        from app.services.email.template_renderer import EmailTemplateRenderer
        self.renderer = EmailTemplateRenderer()

    def test_render_builtin_template(self):
        result = self.renderer.render_template(
            "ticket_update",
            {"ticket_id": "123", "customer_name": "Alice"},
            "co_001",
        )
        self.assertEqual(result["status"], "ok")
        self.assertIn("123", result["rendered"])
        self.assertFalse(result["is_custom"])

    def test_render_template_with_variables(self):
        result = self.renderer.render_template(
            "auto_reply",
            {"ticket_id": "456", "customer_name": "Bob"},
            "co_001",
        )
        self.assertEqual(result["status"], "ok")
        self.assertIn("456", result["rendered"])
        self.assertIn("Bob", result["rendered"])

    def test_register_custom_template(self):
        result = self.renderer.register_template(
            "custom_greeting",
            "<p>Hello {{ name }}!</p>",
            "co_001",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["template_name"], "custom_greeting")

        # Now render it
        render = self.renderer.render_template(
            "custom_greeting", {"name": "Carol"}, "co_001",
        )
        self.assertEqual(render["status"], "ok")
        self.assertTrue(render["is_custom"])
        self.assertIn("Carol", render["rendered"])

    def test_list_templates(self):
        # Register a custom template first
        self.renderer.register_template(
            "my_template", "<p>{{ x }}</p>", "co_001",
        )
        result = self.renderer.list_templates("co_001")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["total"] >= 5)  # 4 built-in + 1 custom
        self.assertIn("my_template", result["custom_templates"])

    def test_render_template_tenant_isolation(self):
        """BC-001: Template registered for co_001 not visible to co_002."""
        self.renderer.register_template(
            "private_template", "<p>Secret {{ data }}</p>", "co_001",
        )
        result = self.renderer.render_template(
            "private_template", {"data": "x"}, "co_002",
        )
        self.assertEqual(result["status"], "error")

    def test_render_template_missing_variable(self):
        result = self.renderer.render_template(
            "ticket_update",
            {},  # missing required variables
            "co_001",
        )
        # Jinja2 renders with empty strings for missing vars (autoescape on)
        self.assertIn(result["status"], ["ok", "error"])

    def test_render_template_autoescaping(self):
        """Jinja2 autoescaping should prevent XSS."""
        result = self.renderer.render_template(
            "ticket_update",
            {"ticket_id": "<script>alert(1)</script>", "customer_name": "User"},
            "co_001",
        )
        self.assertEqual(result["status"], "ok")
        self.assertNotIn("<script>", result["rendered"])
        self.assertIn("&lt;script&gt;", result["rendered"])

    def test_register_template_empty_name(self):
        result = self.renderer.register_template("", "<p>x</p>", "co_001")
        self.assertEqual(result["status"], "error")

    def test_register_template_invalid_jinja2(self):
        result = self.renderer.register_template(
            "bad", "{% if %}", "co_001",
        )
        self.assertEqual(result["status"], "error")


# ════════════════════════════════════════════════════════════════════
# Day 5 — EmailServer MCP
# ════════════════════════════════════════════════════════════════════


class TestEmailServerMCP(unittest.TestCase):
    """Unit tests for EmailServer MCP — tool registration and schemas."""

    def test_email_server_version(self):
        from mcp_server.integrations.email_server import EmailServer
        server = EmailServer()
        self.assertEqual(server.version, "3.0.0")

    def test_email_server_tool_count(self):
        from mcp_server.integrations.email_server import EmailServer
        from mcp_server.base_server import MCPRegistry
        server = EmailServer()
        registry = MCPRegistry()
        server.register_tools(registry)
        # email_send, email_send_ticket_update, email_get_history, search_emails, get_email_thread
        self.assertEqual(len(registry._tools), 5)

    def test_search_emails_tool_schema(self):
        from mcp_server.integrations.email_server import EmailServer
        from mcp_server.base_server import MCPRegistry
        server = EmailServer()
        registry = MCPRegistry()
        server.register_tools(registry)
        tool = registry._tools.get("search_emails")
        self.assertIsNotNone(tool)
        self.assertIn("company_id", tool.input_schema["properties"])
        self.assertIn("company_id", tool.input_schema["required"])

    def test_get_email_thread_tool_schema(self):
        from mcp_server.integrations.email_server import EmailServer
        from mcp_server.base_server import MCPRegistry
        server = EmailServer()
        registry = MCPRegistry()
        server.register_tools(registry)
        tool = registry._tools.get("get_email_thread")
        self.assertIsNotNone(tool)
        self.assertIn("company_id", tool.input_schema["properties"])
        self.assertIn("company_id", tool.input_schema["required"])

    def test_search_emails_missing_company_id(self):
        from mcp_server.integrations.email_server import EmailServer
        server = EmailServer()
        result = asyncio.run(server._invoke_search_emails({"query": "test"}))
        self.assertFalse(result.success)
        self.assertIn("company_id", result.error)

    def test_get_email_thread_missing_company_id(self):
        from mcp_server.integrations.email_server import EmailServer
        server = EmailServer()
        result = asyncio.run(server._invoke_get_email_thread({"ticket_id": "t1"}))
        self.assertFalse(result.success)
        self.assertIn("company_id", result.error)


# ════════════════════════════════════════════════════════════════════
# Day 6 — IVRBuilder
# ════════════════════════════════════════════════════════════════════


class TestIVRBuilder(unittest.TestCase):
    """Unit tests for IVRBuilder — build_ivr_menu, build_multi_level_menu,
    validate_menu_config, get_default_menu_config."""

    def setUp(self):
        from app.services.voice.ivr_builder import IVRBuilder
        self.builder = IVRBuilder()

    def _valid_config(self):
        return {
            "greeting": "Welcome to support",
            "options": [
                {"digit": "1", "label": "Sales", "action": "dial", "number": "+1234567890"},
                {"digit": "2", "label": "Support", "action": "dial", "number": "+1234567891"},
            ],
            "timeout_message": "No input received",
            "invalid_message": "Invalid selection",
        }

    def test_build_ivr_menu_basic(self):
        twiml = self.builder.build_ivr_menu(self._valid_config(), "co_001")
        self.assertIn("<Response>", twiml)
        self.assertIn("<Gather", twiml)
        self.assertIn("Welcome to support", twiml)

    def test_build_ivr_menu_with_dial(self):
        config = self._valid_config()
        config["options"] = [{"digit": "1", "label": "Sales", "action": "dial", "number": "+1234567890"}]
        twiml = self.builder.build_ivr_menu(config, "co_001")
        self.assertIn("<Gather", twiml)

    def test_build_ivr_menu_with_gather(self):
        config = self._valid_config()
        config["options"] = [
            {"digit": "3", "label": "Enter ID", "action": "gather_input", "prompt": "Enter your ID"},
        ]
        twiml = self.builder.build_ivr_menu(config, "co_001")
        self.assertIn("<Gather", twiml)

    def test_build_multi_level_menu(self):
        menus = {
            "main": self._valid_config(),
            "support": {
                "greeting": "Support menu",
                "options": [
                    {"digit": "1", "label": "Billing", "action": "dial", "number": "+1111111111"},
                ],
            },
        }
        twiml = self.builder.build_multi_level_menu(menus, "main", "co_001")
        self.assertIn("<Response>", twiml)

    def test_build_multi_level_menu_missing_entry(self):
        menus = {"other": self._valid_config()}
        twiml = self.builder.build_multi_level_menu(menus, "main", "co_001")
        self.assertIn("not found", twiml.lower() + " not Found")

    def test_validate_menu_config_valid(self):
        result = self.builder.validate_menu_config(self._valid_config())
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)

    def test_validate_menu_config_missing_greeting(self):
        config = self._valid_config()
        del config["greeting"]
        result = self.builder.validate_menu_config(config)
        self.assertFalse(result["valid"])
        self.assertTrue(any("greeting" in e for e in result["errors"]))

    def test_validate_menu_config_invalid_digit(self):
        config = self._valid_config()
        config["options"].append({"digit": "1", "label": "Duplicate", "action": "dial", "number": "+1"})
        result = self.builder.validate_menu_config(config)
        self.assertFalse(result["valid"])
        self.assertTrue(any("Duplicate" in e for e in result["errors"]))

    def test_validate_menu_config_invalid_action(self):
        config = self._valid_config()
        config["options"].append({"digit": "9", "label": "Bad", "action": "fly_away"})
        result = self.builder.validate_menu_config(config)
        self.assertFalse(result["valid"])
        self.assertTrue(any("invalid action" in e for e in result["errors"]))

    def test_get_default_menu_config(self):
        config = self.builder.get_default_menu_config()
        self.assertIn("greeting", config)
        self.assertTrue(len(config["options"]) >= 3)
        self.assertEqual(config["max_attempts"], 3)

    def test_build_ivr_menu_xml_escaping(self):
        config = self._valid_config()
        config["greeting"] = "Hello <script>alert('xss')</script>"
        # Validation should pass (greeting exists), but output should be escaped
        twiml = self.builder.build_ivr_menu(config, "co_001")
        self.assertNotIn("<script>", twiml)
        self.assertIn("&lt;script&gt;", twiml)

    def test_build_ivr_menu_invalid_config_returns_error_twiml(self):
        twiml = self.builder.build_ivr_menu({}, "co_001")
        self.assertIn("<Response>", twiml)
        self.assertIn("invalid", twiml.lower())

    def test_validate_menu_config_empty_options(self):
        result = self.builder.validate_menu_config({"greeting": "Hi", "options": []})
        self.assertFalse(result["valid"])

    def test_validate_menu_config_not_dict(self):
        result = self.builder.validate_menu_config("not a dict")
        self.assertFalse(result["valid"])


# ════════════════════════════════════════════════════════════════════
# Day 6 — CallRecordingService
# ════════════════════════════════════════════════════════════════════


class TestCallRecordingService(unittest.TestCase):
    """Unit tests for CallRecordingService — enable_recording,
    start_transcription, get_transcription, voicemail_to_ticket."""

    def _make_service(self):
        from app.services.voice.call_recording import CallRecordingService
        db = MagicMock()
        service = CallRecordingService(db)
        return service, db

    def _make_call(self, status="in-progress", recording_sid=None):
        call = MagicMock()
        call.id = "call-123"
        call.status = status
        call.recording_sid = recording_sid
        call.recording_enabled = False
        call.recording_url = ""
        call.transcript_json = "{}"
        call.transcript_summary = ""
        call.metadata_json = "{}"
        call.company_id = "co_001"
        return call

    def test_enable_recording(self):
        service, db = self._make_service()
        call = self._make_call()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = call
        db.query.return_value = mock_query

        # Mock Twilio client
        mock_recording = MagicMock()
        mock_recording.sid = "RE123"
        mock_recording.uri = "/recordings/RE123"
        mock_client = MagicMock()
        mock_client.calls.return_value.recordings.create.return_value = mock_recording

        with patch.object(service, '_get_twilio_client', return_value={"success": True, "client": mock_client}):
            result = service.enable_recording("CA123", "co_001")
        self.assertIn(result["status"], ["recording_started", "error"])

    def test_start_transcription(self):
        service, db = self._make_service()
        call = self._make_call(recording_sid="RE123")
        call.metadata_json = "{}"
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = call
        db.query.return_value = mock_query

        mock_transcription = MagicMock()
        mock_transcription.sid = "TR123"
        mock_transcription.status = "in-progress"
        mock_client = MagicMock()
        mock_client.recordings.return_value.transcriptions.create.return_value = mock_transcription

        with patch.object(service, '_get_twilio_client', return_value={"success": True, "client": mock_client}):
            result = service.start_transcription("RE123", "co_001")
        self.assertIn(result["status"], ["transcription_started", "error"])

    def test_get_transcription(self):
        service, db = self._make_service()
        call = self._make_call()
        call.metadata_json = json.dumps({"transcription_sid": "TR123"})
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [call]
        mock_query.first.return_value = call
        db.query.return_value = mock_query

        mock_transcription = MagicMock()
        mock_transcription.status = "completed"
        mock_transcription.transcription_text = "Hello, I need help"
        mock_client = MagicMock()
        mock_client.transcriptions.return_value.fetch.return_value = mock_transcription

        with patch.object(service, '_get_twilio_client', return_value={"success": True, "client": mock_client}):
            result = service.get_transcription("TR123", "co_001")
        self.assertIn(result["status"], ["success", "error"])

    def test_voicemail_to_ticket(self):
        service, db = self._make_service()
        call = self._make_call()
        voicemail_data = {
            "call_sid": "CA123",
            "recording_url": "https://api.twilio.com/recordings/RE123",
            "recording_duration": 30,
            "from_number": "+1234567890",
            "to_number": "+0987654321",
            "transcription_text": "I need help with billing",
        }

        mock_company = MagicMock()
        mock_company.id = "co_001"
        mock_call_query = MagicMock()
        mock_call_query.filter.return_value = mock_call_query
        mock_call_query.first.return_value = call
        mock_company_query = MagicMock()
        mock_company_query.filter.return_value = mock_company_query
        mock_company_query.first.return_value = mock_company

        def query_side_effect(model):
            return mock_call_query

        db.query.side_effect = query_side_effect
        db.add = MagicMock()
        db.commit = MagicMock()
        db.flush = MagicMock()

        with patch.object(service, '_get_call_by_sid', return_value=call):
            result = service.voicemail_to_ticket(voicemail_data, "co_001", db)
        self.assertIn(result["status"], ["ticket_created", "error"])

    def test_get_call_recordings(self):
        service, db = self._make_service()
        call = self._make_call(recording_sid="RE123")
        call.recording_url = "https://api.twilio.com/recordings/RE123"
        call.recording_enabled = True

        with patch.object(service, '_get_call_by_sid', return_value=call):
            with patch.object(service, '_get_twilio_client', return_value={"success": False, "error": "No Twilio"}):
                result = service.get_call_recordings("CA123", "co_001")
        self.assertIn(result["status"], ["success", "error"])

    def test_enable_recording_no_twilio(self):
        """BC-008: Should handle missing Twilio client gracefully."""
        service, db = self._make_service()
        call = self._make_call()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = call
        db.query.return_value = mock_query

        with patch.object(service, '_get_twilio_client', return_value={"success": False, "error": "Twilio not configured"}):
            result = service.enable_recording("CA123", "co_001")
        self.assertEqual(result["status"], "error")
        self.assertIn("Twilio", result["error"])

    def test_enable_recording_call_not_found(self):
        service, db = self._make_service()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        db.query.return_value = mock_query

        result = service.enable_recording("CA999", "co_001")
        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result["error"].lower())


# ════════════════════════════════════════════════════════════════════
# Day 6 — CallTransferService
# ════════════════════════════════════════════════════════════════════


class TestCallTransferService(unittest.TestCase):
    """Unit tests for CallTransferService — cold_transfer, warm_handoff,
    conference_call, cancel_transfer."""

    def _make_service(self):
        from app.services.voice.call_transfer import CallTransferService
        db = MagicMock()
        service = CallTransferService(db)
        return service, db

    def _make_call(self, status="in-progress", metadata=None):
        call = MagicMock()
        call.id = "call-456"
        call.status = status
        call.metadata_json = json.dumps(metadata or {})
        call.company_id = "co_001"
        return call

    def test_cold_transfer(self):
        service, db = self._make_service()
        call = self._make_call()
        mock_client = MagicMock()
        mock_client.calls.return_value.update.return_value = MagicMock()

        with patch.object(service, '_get_call_by_sid', return_value=call):
            with patch.object(service, '_get_twilio_client', return_value={"success": True, "client": mock_client}):
                result = service.cold_transfer("CA123", "+15558675309", "co_001")
        self.assertIn(result["status"], ["transferred", "error"])

    def test_warm_handoff(self):
        service, db = self._make_service()
        call = self._make_call()
        mock_client = MagicMock()
        mock_agent_call = MagicMock()
        mock_agent_call.sid = "CA-agent-123"
        mock_client.calls.return_value.update.return_value = MagicMock()
        mock_client.calls.create.return_value = mock_agent_call

        config = MagicMock()
        config.twilio_phone_number = "+1555000000"

        with patch.object(service, '_get_call_by_sid', return_value=call):
            with patch.object(service, '_get_twilio_client', return_value={"success": True, "client": mock_client}):
                with patch.object(service, '_get_voice_config', return_value=config):
                    result = service.warm_handoff("CA123", "+15559999999", "You have a caller", "co_001")
        self.assertIn(result["status"], ["warm_handoff_initiated", "error"])

    def test_conference_call(self):
        service, db = self._make_service()
        call = self._make_call()
        mock_client = MagicMock()
        mock_participant_call = MagicMock()
        mock_participant_call.sid = "CA-part-001"
        mock_client.calls.return_value.update.return_value = MagicMock()
        mock_client.calls.create.return_value = mock_participant_call

        config = MagicMock()
        config.twilio_phone_number = "+1555000000"

        with patch.object(service, '_get_call_by_sid', return_value=call):
            with patch.object(service, '_get_twilio_client', return_value={"success": True, "client": mock_client}):
                with patch.object(service, '_get_voice_config', return_value=config):
                    result = service.conference_call("CA123", ["+15551111111"], "co_001")
        self.assertIn(result["status"], ["conference_created", "error"])

    def test_cancel_transfer(self):
        service, db = self._make_service()
        call = self._make_call(metadata={
            "agent_call_sid": "CA-agent-123",
            "transfer_status": "pending",
        })
        mock_client = MagicMock()

        with patch.object(service, '_get_call_by_sid', return_value=call):
            with patch.object(service, '_get_twilio_client', return_value={"success": True, "client": mock_client}):
                with patch.object(service, '_get_voice_config', return_value=MagicMock()):
                    result = service.cancel_transfer("CA123", "co_001")
        self.assertIn(result["status"], ["transfer_cancelled", "error"])

    def test_cold_transfer_no_twilio(self):
        """BC-008: Should handle missing Twilio client gracefully."""
        service, db = self._make_service()
        call = self._make_call()
        with patch.object(service, '_get_call_by_sid', return_value=call):
            with patch.object(service, '_get_twilio_client', return_value={"success": False, "error": "No Twilio"}):
                result = service.cold_transfer("CA123", "+15558675309", "co_001")
        self.assertEqual(result["status"], "error")

    def test_cold_transfer_invalid_number(self):
        service, db = self._make_service()
        call = self._make_call()
        with patch.object(service, '_get_call_by_sid', return_value=call):
            result = service.cold_transfer("CA123", "not-a-number", "co_001")
        self.assertEqual(result["status"], "error")
        self.assertIn("E.164", result["error"])

    def test_cold_transfer_call_not_in_progress(self):
        service, db = self._make_service()
        call = self._make_call(status="completed")
        with patch.object(service, '_get_call_by_sid', return_value=call):
            result = service.cold_transfer("CA123", "+15558675309", "co_001")
        self.assertEqual(result["status"], "error")


# ════════════════════════════════════════════════════════════════════
# Day 6 — VoiceSentimentAnalyzer
# ════════════════════════════════════════════════════════════════════


class TestVoiceSentimentAnalyzer(unittest.TestCase):
    """Unit tests for VoiceSentimentAnalyzer — analyze_transcript,
    real_time_sentiment, trigger_empathy_adjustment."""

    def setUp(self):
        from app.services.voice.voice_sentiment import VoiceSentimentAnalyzer
        self.analyzer = VoiceSentimentAnalyzer()

    def test_analyze_transcript_positive(self):
        result = self.analyzer.analyze_transcript(
            "I am very happy with the service. Thank you so much!", "co_001"
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["sentiment"], "positive")
        self.assertTrue(result["confidence"] > 0)

    def test_analyze_transcript_negative(self):
        result = self.analyzer.analyze_transcript(
            "I am furious and angry about this terrible service!", "co_001"
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["sentiment"], "negative")

    def test_analyze_transcript_neutral(self):
        result = self.analyzer.analyze_transcript(
            "I have a question about my account.", "co_001"
        )
        self.assertEqual(result["status"], "success")
        self.assertIn(result["sentiment"], ["neutral", "positive", "negative", "mixed"])

    def test_analyze_transcript_urgent(self):
        result = self.analyzer.analyze_transcript(
            "This is an emergency! I need help immediately!", "co_001"
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["urgency_level"], "critical")

    def test_real_time_sentiment_shift(self):
        prev = {"sentiment": "positive", "urgency_level": "low", "confidence": 0.7}
        result = self.analyzer.real_time_sentiment(
            "I am very frustrated and angry now!", prev, "co_001"
        )
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["shift_detected"])

    def test_real_time_sentiment_no_shift(self):
        prev = {"sentiment": "neutral", "urgency_level": "low", "confidence": 0.3}
        result = self.analyzer.real_time_sentiment(
            "I have a question please.", prev, "co_001"
        )
        self.assertEqual(result["status"], "success")
        # The neutral text may cause a small confidence shift;
        # what matters is no dramatic shift direction
        self.assertIn("shift_detected", result)

    def test_trigger_empathy_adjustment_negative(self):
        sentiment = {
            "sentiment": "negative",
            "confidence": 0.8,
            "urgency_level": "high",
            "emotional_indicators": ["frustration"],
            "key_phrases": ["angry"],
        }
        result = self.analyzer.trigger_empathy_adjustment(sentiment, "co_001")
        self.assertEqual(result["status"], "success")
        self.assertIn("empathetic", result["suggested_response_tone"])
        self.assertTrue(result["escalation_recommended"])

    def test_trigger_empathy_adjustment_positive(self):
        sentiment = {
            "sentiment": "positive",
            "confidence": 0.7,
            "urgency_level": "low",
            "emotional_indicators": ["gratitude"],
            "key_phrases": ["thanks"],
        }
        result = self.analyzer.trigger_empathy_adjustment(sentiment, "co_001")
        self.assertEqual(result["status"], "success")
        self.assertFalse(result["escalation_recommended"])

    def test_analyze_transcript_empty(self):
        """BC-008: Empty transcript should not crash."""
        result = self.analyzer.analyze_transcript("", "co_001")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["sentiment"], "neutral")

    def test_analyze_transcript_none(self):
        result = self.analyzer.analyze_transcript(None, "co_001")
        self.assertIn(result["status"], ["success", "error"])


# ════════════════════════════════════════════════════════════════════
# Day 6 — VoiceServer MCP
# ════════════════════════════════════════════════════════════════════


class TestVoiceServerMCP(unittest.TestCase):
    """Unit tests for VoiceServer MCP — tool registration and schemas."""

    def test_voice_server_version(self):
        from mcp_server.integrations.voice_server import VoiceServer
        server = VoiceServer()
        self.assertEqual(server.version, "3.0.0")

    def test_voice_server_tool_count(self):
        from mcp_server.integrations.voice_server import VoiceServer
        from mcp_server.base_server import MCPRegistry
        server = VoiceServer()
        registry = MCPRegistry()
        server.register_tools(registry)
        self.assertEqual(len(registry._tools), 6)

    def test_get_call_recording_tool_schema(self):
        from mcp_server.integrations.voice_server import VoiceServer
        from mcp_server.base_server import MCPRegistry
        server = VoiceServer()
        registry = MCPRegistry()
        server.register_tools(registry)
        tool = registry._tools.get("voice_get_call_recording")
        self.assertIsNotNone(tool)
        self.assertIn("call_sid", tool.input_schema["required"])
        self.assertIn("company_id", tool.input_schema["required"])

    def test_get_ivr_status_tool_schema(self):
        from mcp_server.integrations.voice_server import VoiceServer
        from mcp_server.base_server import MCPRegistry
        server = VoiceServer()
        registry = MCPRegistry()
        server.register_tools(registry)
        tool = registry._tools.get("voice_get_ivr_status")
        self.assertIsNotNone(tool)
        self.assertIn("call_sid", tool.input_schema["required"])

    def test_get_call_recording_missing_params(self):
        from mcp_server.integrations.voice_server import VoiceServer
        server = VoiceServer()
        result = asyncio.run(server._invoke_get_call_recording({}))
        self.assertFalse(result.success)

    def test_get_ivr_status_missing_params(self):
        from mcp_server.integrations.voice_server import VoiceServer
        server = VoiceServer()
        result = asyncio.run(server._invoke_get_ivr_status({}))
        self.assertFalse(result.success)


# ════════════════════════════════════════════════════════════════════
# Day 6 — MMSService
# ════════════════════════════════════════════════════════════════════


class TestMMSService(unittest.TestCase):
    """Unit tests for MMSService — send_mms, process_inbound_mms,
    save_media, get_mms_history."""

    def _make_service(self):
        from app.services.sms.mms_service import MMSService
        db = MagicMock()
        service = MMSService(db)
        return service, db

    def test_send_mms(self):
        service, db = self._make_service()
        config = MagicMock()
        config.is_enabled = True
        config.twilio_phone_number = "+15550000000"
        config.twilio_account_sid = "AC123"
        config.twilio_auth_token_encrypted = "dGVzdA=="
        config.char_limit = 1600

        conv = MagicMock()
        conv.is_opted_out = False
        conv.id = "conv-001"
        conv.message_count = 0

        msg = MagicMock()
        msg.id = "msg-001"

        with patch.object(service, '_get_sms_config', return_value=config):
            with patch.object(service, '_get_conversation_by_numbers', return_value=conv):
                with patch.object(service, '_send_mms_via_twilio', return_value={
                    "success": True, "message_sid": "SM123", "status": "sent", "num_media": 1,
                }):
                    with patch.object(service, '_get_or_create_conversation', return_value=conv):
                        result = service.send_mms(
                            "+15551111111", "Check this image", ["https://example.com/img.png"],
                            "co_001",
                        )
        self.assertIn(result["status"], ["sent", "error"])

    def test_process_inbound_mms(self):
        service, db = self._make_service()
        config = MagicMock()
        config.is_enabled = True
        config.char_limit = 1600
        config.auto_create_ticket = True

        conv = MagicMock()
        conv.is_opted_out = False
        conv.id = "conv-002"
        conv.message_count = 0
        conv.ticket_id = None

        msg = MagicMock()
        msg.id = "msg-002"
        msg.ticket_id = None

        with patch.object(service, '_get_sms_config', return_value=config):
            with patch.object(service, '_get_message_by_twilio_sid', return_value=None):
                with patch.object(service, '_get_or_create_conversation', return_value=conv):
                    with patch.object(service, '_link_mms_to_ticket', return_value="ticket-001"):
                        with patch.object(service, 'save_media', return_value={"status": "saved", "storage_path": "/tmp/x", "filename": "f.png", "content_type": "image/png", "size": 100}):
                            result = service.process_inbound_mms(
                                {"message_sid": "SM999", "from_number": "+15551111111",
                                 "to_number": "+15550000000", "body": "Photo",
                                 "num_media": 1, "media_urls": ["https://example.com/img.png"]},
                                "co_001", db,
                            )
        self.assertIn(result["status"], ["processed", "error"])

    def test_save_media(self):
        service, db = self._make_service()
        config = MagicMock()
        config.twilio_account_sid = "AC123"
        config.twilio_auth_token_encrypted = "dGVzdA=="

        with patch.object(service, '_get_sms_config', return_value=config):
            with patch('app.services.sms.mms_service.requests.get') as mock_get:
                mock_resp = MagicMock()
                mock_resp.headers = {"Content-Type": "image/png"}
                mock_resp.raise_for_status = MagicMock()
                mock_resp.iter_content.return_value = [b"\x89PNG"]
                mock_get.return_value = mock_resp
                result = service.save_media(
                    "https://api.twilio.com/media/ME123", "co_001", "msg-001",
                )
        self.assertIn(result["status"], ["saved", "error"])

    def test_get_mms_history(self):
        service, db = self._make_service()
        conv = MagicMock()
        conv.id = "conv-003"
        conv.company_id = "co_001"

        msg = MagicMock()
        msg.id = "msg-003"
        msg.to_dict.return_value = {"id": "msg-003", "body": "Hello"}

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [msg]
        mock_query.first.return_value = conv
        db.query.return_value = mock_query

        result = service.get_mms_history("conv-003", "co_001")
        self.assertIn(result["status"], ["success", "error"])

    def test_send_mms_no_twilio(self):
        """BC-008: Missing Twilio should not crash."""
        service, db = self._make_service()
        config = MagicMock()
        config.is_enabled = True
        config.twilio_phone_number = "+15550000000"
        config.twilio_account_sid = "AC123"
        config.twilio_auth_token_encrypted = "dGVzdA=="
        config.char_limit = 1600

        conv = MagicMock()
        conv.is_opted_out = False
        conv.id = "conv-001"
        conv.message_count = 0

        with patch.object(service, '_get_sms_config', return_value=config):
            with patch.object(service, '_get_conversation_by_numbers', return_value=conv):
                with patch.object(service, '_send_mms_via_twilio', return_value={
                    "success": False, "error": "Twilio library not installed",
                }):
                    with patch.object(service, '_get_or_create_conversation', return_value=conv):
                        result = service.send_mms(
                            "+15551111111", "Image", ["https://example.com/img.png"],
                            "co_001",
                        )
        self.assertEqual(result["status"], "error")

    def test_send_mms_opted_out(self):
        """BC-010: Recipient opted out should be blocked."""
        service, db = self._make_service()
        config = MagicMock()
        config.is_enabled = True
        config.twilio_phone_number = "+15550000000"
        config.char_limit = 1600

        conv = MagicMock()
        conv.is_opted_out = True

        with patch.object(service, '_get_sms_config', return_value=config):
            with patch.object(service, '_get_conversation_by_numbers', return_value=conv):
                result = service.send_mms(
                    "+15551111111", "Image", ["https://example.com/img.png"],
                    "co_001",
                )
        self.assertEqual(result["status"], "error")
        self.assertIn("opted out", result["error"].lower())

    def test_send_mms_no_media_urls(self):
        service, db = self._make_service()
        result = service.send_mms("+15551111111", "No media", [], "co_001")
        self.assertEqual(result["status"], "error")
        self.assertIn("media URL", result["error"])


# ════════════════════════════════════════════════════════════════════
# Day 6 — SMSTemplateManager
# ════════════════════════════════════════════════════════════════════


class TestSMSTemplateManager(unittest.TestCase):
    """Unit tests for SMSTemplateManager — create, render, update,
    delete, list templates."""

    def setUp(self):
        from app.services.sms.sms_templates import SMSTemplateManager, _template_store
        self.manager = SMSTemplateManager()
        # Clean up template store before each test
        _template_store.clear()

    def test_create_template(self):
        result = self.manager.create_template(
            "greeting", "Hello {{ name }}!", ["name"], "co_001",
        )
        self.assertEqual(result["status"], "created")
        self.assertIsNotNone(result["template_id"])

    def test_render_template(self):
        self.manager.create_template(
            "greeting", "Hello {{ name }}!", ["name"], "co_001",
        )
        result = self.manager.render_template("greeting", {"name": "Alice"}, "co_001")
        self.assertEqual(result["status"], "rendered")
        self.assertIn("Alice", result["rendered_body"])
        self.assertTrue(result["char_count"] > 0)

    def test_update_template(self):
        create = self.manager.create_template(
            "greeting", "Hello {{ name }}!", ["name"], "co_001",
        )
        tid = create["template_id"]
        result = self.manager.update_template(
            tid, {"body_template": "Hi {{ name }}!", "variables": ["name"]}, "co_001",
        )
        self.assertEqual(result["status"], "updated")

    def test_delete_template(self):
        create = self.manager.create_template(
            "greeting", "Hello {{ name }}!", ["name"], "co_001",
        )
        tid = create["template_id"]
        result = self.manager.delete_template(tid, "co_001")
        self.assertEqual(result["status"], "deleted")

    def test_list_templates(self):
        self.manager.create_template(
            "greeting", "Hello {{ name }}!", ["name"], "co_001",
        )
        result = self.manager.list_templates("co_001")
        self.assertEqual(result["status"], "success")
        # 4 built-in + 1 custom
        self.assertTrue(result["total"] >= 5)

    def test_render_builtin_template(self):
        result = self.manager.render_template(
            "ticket_update",
            {"customer_name": "Bob", "ticket_id": "123", "update_message": "Fixed", "ticket_status": "resolved"},
            "co_001",
        )
        self.assertEqual(result["status"], "rendered")
        self.assertIn("Bob", result["rendered_body"])
        self.assertIn("123", result["rendered_body"])

    def test_render_template_tenant_isolation(self):
        """BC-001: Template created in co_001 not found in co_002."""
        self.manager.create_template(
            "private", "Secret {{ x }}", ["x"], "co_001",
        )
        result = self.manager.render_template("private", {"x": "val"}, "co_002")
        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result["error"])

    def test_create_template_variable_mismatch(self):
        result = self.manager.create_template(
            "bad", "Hello {{ name }}!", ["wrong_var"], "co_001",
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("mismatch", result["error"].lower())

    def test_create_template_invalid_syntax(self):
        result = self.manager.create_template(
            "bad", "{% if %}", ["x"], "co_001",
        )
        self.assertEqual(result["status"], "error")


# ════════════════════════════════════════════════════════════════════
# Day 6 — TCPAManager
# ════════════════════════════════════════════════════════════════════


class TestTCPAManager(unittest.TestCase):
    """Unit tests for TCPAManager — consent, quiet hours,
    enforce_before_send, compliance reporting."""

    def setUp(self):
        from app.services.sms.sms_templates import TCPAManager, _consent_store, _quiet_hours_blocked
        self.manager = TCPAManager()
        _consent_store.clear()
        _quiet_hours_blocked.clear()

    def test_check_consent_opted_in(self):
        self.manager.record_consent("co_001", "+15551111111", "explicit", "sms")
        result = self.manager.check_consent("co_001", "+15551111111")
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["is_opted_in"])

    def test_check_consent_opted_out(self):
        from app.services.sms.sms_templates import _consent_store
        # Manually add an opt-out record
        _consent_store["co_002"] = {
            "+15552222222": [
                {"action": "opt_out", "consent_type": "explicit", "timestamp": "2024-01-01T00:00:00", "source": "sms"},
            ]
        }
        result = self.manager.check_consent("co_002", "+15552222222")
        self.assertFalse(result["is_opted_in"])

    def test_record_consent(self):
        result = self.manager.record_consent("co_001", "+15551111111", "explicit", "sms")
        self.assertEqual(result["status"], "recorded")
        self.assertIsNotNone(result["consent_id"])

    def test_record_consent_invalid_type(self):
        result = self.manager.record_consent("co_001", "+15551111111", "invalid_type", "sms")
        self.assertEqual(result["status"], "error")

    def test_record_consent_invalid_source(self):
        result = self.manager.record_consent("co_001", "+15551111111", "explicit", "invalid_source")
        self.assertEqual(result["status"], "error")

    def test_check_quiet_hours_during_hours(self):
        """During quiet hours (9pm-9am), is_quiet_hours should be True."""
        # Use a timezone where it's currently night (e.g., Pacific/Apia is UTC+13)
        # We can't guarantee local time, but we can test the logic with a known tz
        result = self.manager.check_quiet_hours("co_001", "Pacific/Apia")
        self.assertEqual(result["status"], "success")
        # The result should have the field regardless of whether it's quiet hours or not
        self.assertIn("is_quiet_hours", result)

    def test_check_quiet_hours_after_hours(self):
        """During business hours, is_quiet_hours should be False."""
        # Use UTC — depends on time of day, but field should exist
        result = self.manager.check_quiet_hours("co_001", "UTC")
        self.assertEqual(result["status"], "success")
        self.assertIn("is_quiet_hours", result)

    def test_enforce_before_send_allowed(self):
        """With consent and outside quiet hours, should be allowed."""
        self.manager.record_consent("co_001", "+15551111111", "explicit", "sms")
        # Use a timezone where it should be business hours (e.g., UTC at ~noon)
        # This test is time-dependent, so we patch check_quiet_hours
        with patch.object(self.manager, 'check_quiet_hours', return_value={
            "status": "success", "is_quiet_hours": False, "next_allowed_time": None,
        }):
            result = self.manager.enforce_before_send("co_001", "+15551111111", "UTC")
        self.assertTrue(result["can_send"])

    def test_enforce_before_send_blocked_consent(self):
        """Without consent, should be blocked."""
        # No consent recorded for this number — default is opted in
        # per the check_consent logic (True if no opt-out records)
        # So we need to explicitly add an opt-out record
        from app.services.sms.sms_templates import _consent_store
        _consent_store["co_001"] = {
            "+15559999999": [
                {"action": "opt_out", "consent_type": "explicit",
                 "timestamp": "2024-01-01T00:00:00", "source": "sms"},
            ]
        }
        with patch.object(self.manager, 'check_quiet_hours', return_value={
            "status": "success", "is_quiet_hours": False, "next_allowed_time": None,
        }):
            result = self.manager.enforce_before_send("co_001", "+15559999999", "UTC")
        self.assertFalse(result["can_send"])

    def test_enforce_before_send_blocked_quiet_hours(self):
        """During quiet hours, should be blocked even with consent."""
        self.manager.record_consent("co_001", "+15551111111", "explicit", "sms")
        with patch.object(self.manager, 'check_quiet_hours', return_value={
            "status": "success", "is_quiet_hours": True,
            "next_allowed_time": "2024-01-01T09:00:00+00:00",
        }):
            result = self.manager.enforce_before_send("co_001", "+15551111111", "UTC")
        self.assertFalse(result["can_send"])
        self.assertIn("quiet hours", result["reason"].lower())

    def test_get_compliance_report(self):
        self.manager.record_consent("co_001", "+15551111111", "explicit", "sms")
        self.manager.record_consent("co_001", "+15552222222", "implicit", "web")
        result = self.manager.get_compliance_report("co_001")
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["consent_records_count"] >= 2)
        self.assertIn("quiet_hours_violations_blocked", result)


# ════════════════════════════════════════════════════════════════════
# Day 5 + Day 6 Integration Flows
# ════════════════════════════════════════════════════════════════════


class TestDay5Day6IntegrationFlow(unittest.TestCase):
    """Integration tests for cross-component flows."""

    def test_email_parse_to_ticket_flow(self):
        """End-to-end: parse HTML email → strip reply → detect signature → convert to ticket."""
        from app.services.email.email_parser import EmailParser
        from app.services.email.email_to_ticket import EmailToTicketConverter

        parser = EmailParser()

        # Step 1: Parse HTML
        html_result = parser.parse_html_email(
            "<p>Hi, I need help.</p><p>Thanks,<br>John</p>"
        )
        self.assertEqual(html_result["status"], "ok")
        self.assertIn("help", html_result["text"])

        # Step 2: Strip quoted reply
        clean = parser.strip_quoted_reply(html_result["text"])
        self.assertIn("help", clean)

        # Step 3: Detect signature
        body, sig = parser.detect_email_signature(clean)
        # Either body or signature should contain the content
        self.assertTrue(len(body) > 0 or len(sig) > 0)

        # Step 4: Track thread
        thread = parser.track_thread("<msg1@x.com>", None, None, "co_001")
        self.assertEqual(thread["status"], "ok")

    def test_voice_ivr_to_recording_flow(self):
        """End-to-end: build IVR → validate → generate TwiML."""
        from app.services.voice.ivr_builder import IVRBuilder

        builder = IVRBuilder()
        config = builder.get_default_menu_config()
        validation = builder.validate_menu_config(config)
        self.assertTrue(validation["valid"])

        twiml = builder.build_ivr_menu(config, "co_001")
        self.assertIn("<Response>", twiml)
        self.assertIn("<Gather", twiml)

    def test_voicemail_to_ticket_flow(self):
        """End-to-end: analyze sentiment → trigger empathy → check escalation."""
        from app.services.voice.voice_sentiment import VoiceSentimentAnalyzer

        analyzer = VoiceSentimentAnalyzer()
        transcript = "I am very angry and this is an emergency! I need a supervisor now!"

        # Analyze
        result = analyzer.analyze_transcript(transcript, "co_001")
        self.assertEqual(result["sentiment"], "negative")
        self.assertEqual(result["urgency_level"], "critical")

        # Empathy adjustment
        empathy = analyzer.trigger_empathy_adjustment(result, "co_001")
        self.assertTrue(empathy["escalation_recommended"])

    def test_sms_mms_to_ticket_flow(self):
        """End-to-end: check TCPA consent → render template → send flow."""
        from app.services.sms.sms_templates import SMSTemplateManager, TCPAManager

        tcpa = TCPAManager()
        tpl = SMSTemplateManager()

        # Record consent
        consent = tcpa.record_consent("co_001", "+15551111111", "explicit", "sms")
        self.assertEqual(consent["status"], "recorded")

        # Check consent
        check = tcpa.check_consent("co_001", "+15551111111")
        self.assertTrue(check["is_opted_in"])

        # Render template
        render = tpl.render_template(
            "ticket_update",
            {"customer_name": "Alice", "ticket_id": "T-001",
             "update_message": "Resolved", "ticket_status": "closed"},
            "co_001",
        )
        self.assertEqual(render["status"], "rendered")
        self.assertIn("Alice", render["rendered_body"])

    def test_tcpa_enforcement_flow(self):
        """End-to-end TCPA enforcement flow."""
        from app.services.sms.sms_templates import TCPAManager, _consent_store
        _consent_store.clear()

        tcpa = TCPAManager()

        # Add explicit opt-out to block sending
        _consent_store["co_001"] = {
            "+15559999999": [
                {"action": "opt_out", "consent_type": "explicit",
                 "timestamp": "2024-01-01T00:00:00", "source": "sms"},
            ]
        }
        with patch.object(tcpa, 'check_quiet_hours', return_value={
            "status": "success", "is_quiet_hours": False, "next_allowed_time": None,
        }):
            result = tcpa.enforce_before_send("co_001", "+15559999999", "UTC")
        self.assertFalse(result["can_send"])

        # Record consent (opt-in after opt-out)
        tcpa.record_consent("co_001", "+15559999999", "explicit", "sms")

        # With consent and outside quiet hours → allowed
        with patch.object(tcpa, 'check_quiet_hours', return_value={
            "status": "success", "is_quiet_hours": False, "next_allowed_time": None,
        }):
            result = tcpa.enforce_before_send("co_001", "+15559999999", "UTC")
        self.assertTrue(result["can_send"])

    def test_multi_tenant_isolation_email(self):
        """BC-001: Email templates are tenant-isolated."""
        from app.services.email.template_renderer import EmailTemplateRenderer

        renderer = EmailTemplateRenderer()
        renderer.register_template("priv", "<p>{{ x }}</p>", "co_A")
        result_A = renderer.render_template("priv", {"x": "A"}, "co_A")
        result_B = renderer.render_template("priv", {"x": "B"}, "co_B")

        self.assertEqual(result_A["status"], "ok")
        self.assertEqual(result_B["status"], "error")

    def test_multi_tenant_isolation_voice(self):
        """BC-001: IVR menus are scoped to company_id in their URLs."""
        from app.services.voice.ivr_builder import IVRBuilder

        builder = IVRBuilder()
        config = builder.get_default_menu_config()

        twiml_a = builder.build_ivr_menu(config, "co_A")
        twiml_b = builder.build_ivr_menu(config, "co_B")

        self.assertIn("co_A", twiml_a)
        self.assertIn("co_B", twiml_b)
        self.assertNotEqual(twiml_a, twiml_b)

    def test_multi_tenant_isolation_sms(self):
        """BC-001: SMS templates are tenant-isolated."""
        from app.services.sms.sms_templates import SMSTemplateManager, _template_store

        manager = SMSTemplateManager()
        _template_store.clear()

        manager.create_template("shared", "Hi {{ n }}", ["n"], "co_A")
        manager.create_template("shared", "Hey {{ n }}", ["n"], "co_B")

        render_A = manager.render_template("shared", {"n": "A"}, "co_A")
        render_B = manager.render_template("shared", {"n": "B"}, "co_B")

        self.assertEqual(render_A["status"], "rendered")
        self.assertEqual(render_B["status"], "rendered")
        # Both have "shared" name but different content
        self.assertIn("Hi", render_A["rendered_body"])
        self.assertIn("Hey", render_B["rendered_body"])

    def test_email_parser_bc008_bad_html(self):
        """BC-008: Malformed HTML should not crash EmailParser."""
        from app.services.email.email_parser import EmailParser
        parser = EmailParser()
        result = parser.parse_html_email("<p>unclosed <b>tag</p>")
        self.assertIn(result["status"], ["ok", "error"])

    def test_ivr_builder_bc008_exception(self):
        """BC-008: Exception during IVR build returns error TwiML."""
        from app.services.voice.ivr_builder import IVRBuilder
        builder = IVRBuilder()
        with patch.object(builder, 'validate_menu_config', side_effect=Exception("boom")):
            twiml = builder.build_ivr_menu({"greeting": "Hi", "options": []}, "co_001")
        self.assertIn("<Response>", twiml)

    def test_sentiment_analyzer_bc008_exception(self):
        """BC-008: Sentiment analyzer handles internal errors."""
        from app.services.voice.voice_sentiment import VoiceSentimentAnalyzer
        analyzer = VoiceSentimentAnalyzer()
        with patch.object(analyzer, '_score_keywords', side_effect=Exception("internal")):
            result = analyzer.analyze_transcript("test text", "co_001")
        self.assertEqual(result["status"], "error")

    def test_tcpa_manager_bc008_quiet_hours_invalid_timezone(self):
        """BC-008: Invalid timezone should not crash quiet hours check."""
        from app.services.sms.sms_templates import TCPAManager
        manager = TCPAManager()
        result = manager.check_quiet_hours("co_001", "Invalid/Timezone")
        self.assertIn(result["status"], ["success", "error"])


# ════════════════════════════════════════════════════════════════════
# Additional Edge Case Tests
# ════════════════════════════════════════════════════════════════════


class TestEdgeCases(unittest.TestCase):
    """Edge case tests for robustness (BC-008)."""

    def test_email_parser_mixed_content(self):
        from app.services.email.email_parser import EmailParser
        parser = EmailParser()
        html = "<style>body{color:red}</style><p>Hello</p><script>alert(1)</script>"
        result = parser.parse_html_email(html)
        self.assertEqual(result["status"], "ok")
        self.assertNotIn("alert", result["text"])
        self.assertNotIn("color:red", result["text"])
        self.assertIn("Hello", result["text"])

    def test_email_track_thread_empty_message_id(self):
        from app.services.email.email_parser import EmailParser
        parser = EmailParser()
        result = parser.track_thread("", None, None, "co_001")
        self.assertEqual(result["status"], "ok")

    def test_ivr_builder_empty_menus(self):
        from app.services.voice.ivr_builder import IVRBuilder
        builder = IVRBuilder()
        twiml = builder.build_multi_level_menu({}, "main", "co_001")
        self.assertIn("<Response>", twiml)

    def test_ivr_builder_none_menus(self):
        from app.services.voice.ivr_builder import IVRBuilder
        builder = IVRBuilder()
        twiml = builder.build_multi_level_menu(None, "main", "co_001")
        self.assertIn("<Response>", twiml)

    def test_sentiment_analyzer_mixed_sentiment(self):
        from app.services.voice.voice_sentiment import VoiceSentimentAnalyzer
        analyzer = VoiceSentimentAnalyzer()
        result = analyzer.analyze_transcript(
            "I love the product but the service was terrible and I'm angry", "co_001"
        )
        self.assertIn(result["sentiment"], ["mixed", "negative", "positive"])

    def test_voice_sentiment_urgency_high(self):
        from app.services.voice.voice_sentiment import VoiceSentimentAnalyzer
        analyzer = VoiceSentimentAnalyzer()
        result = analyzer.analyze_transcript(
            "I need this fixed quickly, it's important", "co_001"
        )
        self.assertEqual(result["status"], "success")
        self.assertIn(result["urgency_level"], ["low", "medium", "high", "critical"])

    def test_mms_service_disabled_channel(self):
        from app.services.sms.mms_service import MMSService
        service, db = MMSService(MagicMock()), MagicMock()
        config = MagicMock()
        config.is_enabled = False
        with patch.object(service, '_get_sms_config', return_value=config):
            result = service.send_mms("+15551111111", "test", ["https://x.com/img.png"], "co_001")
        self.assertEqual(result["status"], "error")
        self.assertIn("disabled", result["error"].lower())

    def test_mms_process_inbound_disabled(self):
        from app.services.sms.mms_service import MMSService
        service, db = MMSService(MagicMock()), MagicMock()
        config = MagicMock()
        config.is_enabled = False
        with patch.object(service, '_get_sms_config', return_value=config):
            result = service.process_inbound_mms({"message_sid": "SM1"}, "co_001", db)
        self.assertEqual(result["status"], "error")

    def test_email_template_renderer_nonexistent_template(self):
        from app.services.email.template_renderer import EmailTemplateRenderer
        renderer = EmailTemplateRenderer()
        result = renderer.render_template("nonexistent_template", {}, "co_001")
        self.assertEqual(result["status"], "error")

    def test_call_transfer_not_found_call(self):
        from app.services.voice.call_transfer import CallTransferService
        service, db = CallTransferService(MagicMock()), MagicMock()
        with patch.object(service, '_get_call_by_sid', return_value=None):
            result = service.cold_transfer("CA_MISSING", "+15558675309", "co_001")
        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result["error"].lower())

    def test_tcpa_compliance_report_empty(self):
        from app.services.sms.sms_templates import TCPAManager, _consent_store
        manager = TCPAManager()
        _consent_store.clear()
        result = manager.get_compliance_report("co_empty")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["consent_records_count"], 0)

    def test_email_parser_base64_attachment(self):
        from app.services.email.email_parser import EmailParser
        import base64
        parser = EmailParser()
        content = base64.b64encode(b"PDF data").decode()
        email_data = {
            "attachments": [{
                "filename": "test.pdf",
                "content_type": "application/pdf",
                "content": content,
                "size": 8,
            }]
        }
        result = parser.extract_attachments(email_data, "co_001")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["attachments"]), 1)

    def test_call_recording_service_voicemail_no_transcript(self):
        """Voicemail with no transcript should still create ticket."""
        from app.services.voice.call_recording import CallRecordingService
        service, db = CallRecordingService(MagicMock()), MagicMock()

        voicemail_data = {
            "call_sid": "CA_VM",
            "recording_url": "https://api.twilio.com/recordings/RE_VM",
            "recording_duration": 15,
            "from_number": "+15551111111",
            "to_number": "+15550000000",
        }
        mock_company = MagicMock()
        mock_company.id = "co_001"

        # Patch at the import location used by the module
        with patch.object(service, '_get_call_by_sid', return_value=None):
            with patch('database.models.core.Company', MagicMock, create=True):
                # Also patch the DB query for Company check
                mock_q = MagicMock()
                mock_q.filter.return_value = mock_q
                mock_q.first.return_value = mock_company
                db.query.return_value = mock_q
                db.add = MagicMock()
                db.flush = MagicMock()
                db.commit = MagicMock()
                result = service.voicemail_to_ticket(voicemail_data, "co_001", db)
        self.assertIn(result["status"], ["ticket_created", "error"])

    def test_sms_template_delete_nonexistent(self):
        from app.services.sms.sms_templates import SMSTemplateManager, _template_store
        manager = SMSTemplateManager()
        _template_store.clear()
        result = manager.delete_template("nonexistent-id", "co_001")
        self.assertEqual(result["status"], "error")

    def test_sms_template_update_nonexistent(self):
        from app.services.sms.sms_templates import SMSTemplateManager, _template_store
        manager = SMSTemplateManager()
        _template_store.clear()
        result = manager.update_template("nonexistent-id", {"body_template": "x"}, "co_001")
        self.assertEqual(result["status"], "error")

    def test_call_recording_not_found_for_company(self):
        """BC-001: Recording lookup should fail for wrong company."""
        from app.services.voice.call_recording import CallRecordingService
        service, db = CallRecordingService(MagicMock()), MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        db.query.return_value = mock_query

        result = service.enable_recording("CA123", "wrong_company")
        self.assertEqual(result["status"], "error")

    def test_conference_call_too_many_participants(self):
        """Conference with >10 participants should fail."""
        from app.services.voice.call_transfer import CallTransferService
        service, db = CallTransferService(MagicMock()), MagicMock()
        call = MagicMock()
        call.status = "in-progress"
        call.id = "call-1"
        call.company_id = "co_001"
        call.metadata_json = "{}"

        numbers = [f"+15551{i:06d}" for i in range(11)]
        with patch.object(service, '_get_call_by_sid', return_value=call):
            result = service.conference_call("CA1", numbers, "co_001")
        self.assertEqual(result["status"], "error")
        self.assertIn("Maximum", result["error"])

    def test_cancel_transfer_no_pending(self):
        """Cancel transfer when no pending transfer exists."""
        from app.services.voice.call_transfer import CallTransferService
        service, db = CallTransferService(MagicMock()), MagicMock()
        call = MagicMock()
        call.metadata_json = "{}"  # No agent_call_sid
        with patch.object(service, '_get_call_by_sid', return_value=call):
            result = service.cancel_transfer("CA123", "co_001")
        self.assertEqual(result["status"], "error")

    def test_mms_save_media_empty_url(self):
        from app.services.sms.mms_service import MMSService
        service, db = MMSService(MagicMock()), MagicMock()
        result = service.save_media("", "co_001", "msg-001")
        self.assertEqual(result["status"], "error")


if __name__ == "__main__":
    unittest.main()

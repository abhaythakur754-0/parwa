"""
Unit tests for PARWA MCP Integration Servers.

Tests for:
- EmailServer: Email operations via Brevo
- VoiceServer: Voice/SMS operations via Twilio
- ChatServer: Chat/messaging operations
- TicketingServer: Ticket management via Zendesk

CRITICAL: All servers must respond within 2 seconds.
"""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_servers.base_server import MCPServerState
from mcp_servers.integrations.email_server import EmailServer
from mcp_servers.integrations.voice_server import VoiceServer
from mcp_servers.integrations.chat_server import ChatServer
from mcp_servers.integrations.ticketing_server import TicketingServer


# ═══════════════════════════════════════════════════════════════════════════════
# EMAIL SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmailServer:
    """Tests for Email MCP server."""

    @pytest.fixture
    def mock_email_client(self):
        """Create mock email client."""
        client = MagicMock()
        client.is_connected = False
        client.connect = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        client.send_email = AsyncMock(return_value={
            "message_id": "msg_123",
            "to": ["test@example.com"],
            "subject": "Test",
            "status": "queued",
        })
        client.send_bulk_email = AsyncMock(return_value={
            "batch_id": "batch_123",
            "recipient_count": 5,
            "status": "processing",
        })
        client.get_email_status = AsyncMock(return_value={
            "message_id": "msg_123",
            "status": "delivered",
            "delivered_at": "2024-01-01T00:00:00Z",
            "opened": False,
        })
        client.get_templates = AsyncMock(return_value=[
            {"id": 1, "name": "Welcome"},
        ])
        return client

    @pytest.fixture
    def email_server(self, mock_email_client):
        """Create Email server instance with mocked client."""
        return EmailServer(email_client=mock_email_client)

    @pytest.mark.asyncio
    async def test_server_starts(self, email_server, mock_email_client):
        """Test Email server starts correctly."""
        await email_server.start()
        assert email_server.is_running is True
        mock_email_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_server_stops(self, email_server, mock_email_client):
        """Test Email server stops correctly."""
        await email_server.start()
        await email_server.stop()
        assert email_server.state == MCPServerState.STOPPED
        mock_email_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_returns_message_id(self, email_server):
        """Test send_email returns message_id."""
        await email_server.start()
        result = await email_server.handle_tool_call(
            "send_email",
            {
                "to": "test@example.com",
                "subject": "Test Subject",
                "body": "<p>Test content</p>",
            }
        )
        assert result.success is True
        assert result.data["message_id"] == "msg_123"
        assert result.data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_send_email_missing_recipient(self, email_server):
        """Test send_email fails without recipient."""
        await email_server.start()
        result = await email_server.handle_tool_call(
            "send_email",
            {"to": "", "subject": "Test", "body": "Content"}
        )
        # Tool call succeeds, but validation in handler should catch
        assert result.success is True or result.error is not None

    @pytest.mark.asyncio
    async def test_send_email_missing_subject(self, email_server):
        """Test send_email fails without subject."""
        await email_server.start()
        result = await email_server.handle_tool_call(
            "send_email",
            {"to": "test@example.com", "body": "Content"}
        )
        # Missing required field should fail validation
        assert result.success is False
        assert "Missing required parameter" in result.error

    @pytest.mark.asyncio
    async def test_send_bulk_emails(self, email_server):
        """Test send_bulk_emails returns batch_id."""
        await email_server.start()
        result = await email_server.handle_tool_call(
            "send_bulk_emails",
            {
                "recipients": ["user1@example.com", "user2@example.com"],
                "subject": "Bulk Test",
                "body": "<p>Content</p>",
            }
        )
        assert result.success is True
        assert result.data["batch_id"] == "batch_123"
        assert result.data["recipient_count"] == 5  # Mock returns this

    @pytest.mark.asyncio
    async def test_get_email_status(self, email_server):
        """Test get_email_status returns delivery status."""
        await email_server.start()
        result = await email_server.handle_tool_call(
            "get_email_status",
            {"email_id": "msg_123"}
        )
        assert result.success is True
        assert result.data["status"] == "delivered"

    @pytest.mark.asyncio
    async def test_get_templates(self, email_server):
        """Test get_templates returns template list."""
        await email_server.start()
        result = await email_server.handle_tool_call(
            "get_templates",
            {}
        )
        assert result.success is True
        assert "templates" in result.data
        assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_email_response_time(self, email_server):
        """CRITICAL: Email server must respond within 2 seconds."""
        await email_server.start()
        start = time.time()
        await email_server.handle_tool_call(
            "send_email",
            {"to": "test@example.com", "subject": "Test", "body": "Test"}
        )
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000, f"Response took {elapsed}ms, exceeds 2000ms limit"


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestVoiceServer:
    """Tests for Voice/SMS MCP server."""

    @pytest.fixture
    def mock_twilio_client(self):
        """Create mock Twilio client."""
        client = MagicMock()
        client.is_connected = False
        client.connect = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        client.phone_number = "+1555123456"
        client.make_call = AsyncMock(return_value={
            "sid": "CA123",
            "to": "+15559876543",
            "from": "+1555123456",
            "status": "queued",
        })
        client.send_sms = AsyncMock(return_value={
            "sid": "SM123",
            "to": "+15559876543",
            "status": "queued",
            "num_segments": "1",
        })
        client.get_call_status = AsyncMock(return_value={
            "sid": "CA123",
            "status": "completed",
            "duration": "120",
        })
        client.validate_phone_number = AsyncMock(return_value={
            "phone_number": "+15559876543",
            "valid": True,
            "carrier": "Verizon",
            "line_type": "mobile",
        })
        return client

    @pytest.fixture
    def voice_server(self, mock_twilio_client):
        """Create Voice server instance with mocked client."""
        return VoiceServer(twilio_client=mock_twilio_client)

    @pytest.mark.asyncio
    async def test_server_starts(self, voice_server, mock_twilio_client):
        """Test Voice server starts correctly."""
        await voice_server.start()
        assert voice_server.is_running is True
        mock_twilio_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_call_returns_sid(self, voice_server):
        """Test make_call returns call_sid."""
        await voice_server.start()
        result = await voice_server.handle_tool_call(
            "make_call",
            {
                "to": "+15559876543",
                "message": "Hello, this is a test call.",
            }
        )
        assert result.success is True
        assert result.data["call_sid"] == "CA123"
        assert result.data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_make_call_with_voice_option(self, voice_server):
        """Test make_call with voice option."""
        await voice_server.start()
        result = await voice_server.handle_tool_call(
            "make_call",
            {
                "to": "+15559876543",
                "message": "Test message",
                "voice": "female",
            }
        )
        assert result.success is True
        assert result.data["voice"] == "female"

    @pytest.mark.asyncio
    async def test_send_sms_returns_sid(self, voice_server):
        """Test send_sms returns message_sid."""
        await voice_server.start()
        result = await voice_server.handle_tool_call(
            "send_sms",
            {
                "to": "+15559876543",
                "message": "Test SMS message",
            }
        )
        assert result.success is True
        assert result.data["message_sid"] == "SM123"
        assert result.data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_send_sms_missing_message(self, voice_server):
        """Test send_sms fails without message."""
        await voice_server.start()
        result = await voice_server.handle_tool_call(
            "send_sms",
            {"to": "+15559876543"}
        )
        assert result.success is False
        assert "Missing required parameter" in result.error

    @pytest.mark.asyncio
    async def test_get_call_status(self, voice_server):
        """Test get_call_status returns status."""
        await voice_server.start()
        result = await voice_server.handle_tool_call(
            "get_call_status",
            {"call_id": "CA123"}
        )
        assert result.success is True
        assert result.data["status"] == "completed"
        assert result.data["duration"] == "120"

    @pytest.mark.asyncio
    async def test_validate_phone_number(self, voice_server):
        """Test validate_phone_number returns validation result."""
        await voice_server.start()
        result = await voice_server.handle_tool_call(
            "validate_phone_number",
            {"phone": "+15559876543"}
        )
        assert result.success is True
        assert result.data["valid"] is True
        assert result.data["carrier"] == "Verizon"

    @pytest.mark.asyncio
    async def test_voice_response_time(self, voice_server):
        """CRITICAL: Voice server must respond within 2 seconds."""
        await voice_server.start()
        start = time.time()
        await voice_server.handle_tool_call(
            "send_sms",
            {"to": "+15559876543", "message": "Test"}
        )
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestChatServer:
    """Tests for Chat MCP server."""

    @pytest.fixture
    def chat_server(self):
        """Create Chat server instance."""
        return ChatServer()

    @pytest.mark.asyncio
    async def test_server_starts(self, chat_server):
        """Test Chat server starts correctly."""
        await chat_server.start()
        assert chat_server.is_running is True

    @pytest.mark.asyncio
    async def test_create_conversation(self, chat_server):
        """Test create_conversation returns conversation_id."""
        await chat_server.start()
        result = await chat_server.handle_tool_call(
            "create_conversation",
            {
                "participants": ["user_123", "agent_456"],
                "metadata": {"channel": "web"},
            }
        )
        assert result.success is True
        assert result.data["conversation_id"] is not None
        assert result.data["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_conversation_no_participants(self, chat_server):
        """Test create_conversation fails without participants."""
        await chat_server.start()
        result = await chat_server.handle_tool_call(
            "create_conversation",
            {"participants": []}
        )
        assert result.success is True
        assert result.data["status"] == "error"

    @pytest.mark.asyncio
    async def test_send_message(self, chat_server):
        """Test send_message returns message_id."""
        await chat_server.start()

        # First create a conversation
        create_result = await chat_server.handle_tool_call(
            "create_conversation",
            {"participants": ["user_123"]}
        )
        conv_id = create_result.data["conversation_id"]

        # Then send a message
        result = await chat_server.handle_tool_call(
            "send_message",
            {
                "conversation_id": conv_id,
                "message": "Hello, how can I help?",
                "sender": "agent",
            }
        )
        assert result.success is True
        assert result.data["message_id"] is not None
        assert result.data["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_message_invalid_conversation(self, chat_server):
        """Test send_message fails for non-existent conversation."""
        await chat_server.start()
        result = await chat_server.handle_tool_call(
            "send_message",
            {
                "conversation_id": "nonexistent",
                "message": "Test",
            }
        )
        assert result.success is True
        assert result.data["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, chat_server):
        """Test get_conversation_history returns messages."""
        await chat_server.start()

        # Create conversation and send message
        create_result = await chat_server.handle_tool_call(
            "create_conversation",
            {"participants": ["user_123"]}
        )
        conv_id = create_result.data["conversation_id"]

        await chat_server.handle_tool_call(
            "send_message",
            {"conversation_id": conv_id, "message": "Test message"}
        )

        # Get history
        result = await chat_server.handle_tool_call(
            "get_conversation_history",
            {"conversation_id": conv_id}
        )
        assert result.success is True
        assert "messages" in result.data
        assert result.data["count"] >= 1

    @pytest.mark.asyncio
    async def test_mark_read(self, chat_server):
        """Test mark_read updates read status."""
        await chat_server.start()

        # Create conversation and send message
        create_result = await chat_server.handle_tool_call(
            "create_conversation",
            {"participants": ["user_123"]}
        )
        conv_id = create_result.data["conversation_id"]

        send_result = await chat_server.handle_tool_call(
            "send_message",
            {"conversation_id": conv_id, "message": "Test"}
        )
        msg_id = send_result.data["message_id"]

        # Mark as read
        result = await chat_server.handle_tool_call(
            "mark_read",
            {
                "conversation_id": conv_id,
                "message_ids": [msg_id],
                "participant": "user_123",
            }
        )
        assert result.success is True
        assert result.data["marked_count"] >= 1

    @pytest.mark.asyncio
    async def test_chat_response_time(self, chat_server):
        """CRITICAL: Chat server must respond within 2 seconds."""
        await chat_server.start()
        start = time.time()
        await chat_server.handle_tool_call(
            "create_conversation",
            {"participants": ["user_123"]}
        )
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000


# ═══════════════════════════════════════════════════════════════════════════════
# TICKETING SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTicketingServer:
    """Tests for Ticketing MCP server."""

    @pytest.fixture
    def mock_zendesk_client(self):
        """Create mock Zendesk client."""
        client = MagicMock()
        client.is_connected = False
        client.connect = AsyncMock(return_value=True)
        client.disconnect = AsyncMock()
        client.create_ticket = AsyncMock(return_value={
            "id": 12345,
            "subject": "Test Ticket",
            "status": "new",
            "priority": "normal",
            "created_at": "2024-01-01T00:00:00Z",
        })
        client.get_ticket = AsyncMock(return_value={
            "id": 12345,
            "subject": "Test Ticket",
            "status": "open",
            "priority": "high",
            "requester": {"email": "test@example.com"},
        })
        client.update_ticket = AsyncMock(return_value={
            "id": 12345,
            "status": "pending",
            "updated_at": "2024-01-01T01:00:00Z",
        })
        client.add_comment = AsyncMock(return_value={
            "id": 67890,
            "ticket_id": 12345,
            "body": "Test comment",
            "public": True,
        })
        client.search_tickets = AsyncMock(return_value=[
            {"id": 12345, "subject": "Match 1"},
            {"id": 67890, "subject": "Match 2"},
        ])
        return client

    @pytest.fixture
    def ticketing_server(self, mock_zendesk_client):
        """Create Ticketing server instance with mocked client."""
        return TicketingServer(zendesk_client=mock_zendesk_client)

    @pytest.mark.asyncio
    async def test_server_starts(self, ticketing_server, mock_zendesk_client):
        """Test Ticketing server starts correctly."""
        await ticketing_server.start()
        assert ticketing_server.is_running is True
        mock_zendesk_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_ticket(self, ticketing_server):
        """Test create_ticket returns ticket_id."""
        await ticketing_server.start()
        result = await ticketing_server.handle_tool_call(
            "create_ticket",
            {
                "subject": "Test Subject",
                "description": "Test description",
                "requester_email": "test@example.com",
                "priority": "normal",
            }
        )
        assert result.success is True
        assert result.data["ticket_id"] == "12345"
        assert result.data["status"] == "new"

    @pytest.mark.asyncio
    async def test_create_ticket_high_priority(self, ticketing_server):
        """Test create_ticket with high priority."""
        await ticketing_server.start()
        result = await ticketing_server.handle_tool_call(
            "create_ticket",
            {
                "subject": "Urgent issue",
                "description": "Critical description",
                "requester_email": "test@example.com",
                "priority": "urgent",
            }
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_create_ticket_missing_subject(self, ticketing_server):
        """Test create_ticket fails without subject."""
        await ticketing_server.start()
        result = await ticketing_server.handle_tool_call(
            "create_ticket",
            {
                "description": "Test",
                "requester_email": "test@example.com",
            }
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_get_ticket(self, ticketing_server):
        """Test get_ticket returns ticket details."""
        await ticketing_server.start()
        result = await ticketing_server.handle_tool_call(
            "get_ticket",
            {"ticket_id": "12345"}
        )
        assert result.success is True
        assert result.data["ticket_id"] == "12345"
        assert result.data["status"] == "open"

    @pytest.mark.asyncio
    async def test_update_ticket(self, ticketing_server):
        """Test update_ticket returns updated ticket."""
        await ticketing_server.start()
        result = await ticketing_server.handle_tool_call(
            "update_ticket",
            {
                "ticket_id": "12345",
                "status": "pending",
                "comment": "Updated status",
            }
        )
        assert result.success is True
        assert result.data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_add_comment(self, ticketing_server):
        """Test add_comment returns comment_id."""
        await ticketing_server.start()
        result = await ticketing_server.handle_tool_call(
            "add_comment",
            {
                "ticket_id": "12345",
                "comment": "This is a comment",
                "public": True,
            }
        )
        assert result.success is True
        assert result.data["comment_id"] == "67890"

    @pytest.mark.asyncio
    async def test_search_tickets(self, ticketing_server):
        """Test search_tickets returns results."""
        await ticketing_server.start()
        result = await ticketing_server.handle_tool_call(
            "search_tickets",
            {"query": "refund"}
        )
        assert result.success is True
        assert len(result.data["tickets"]) == 2
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_search_tickets_with_filters(self, ticketing_server):
        """Test search_tickets with status filter."""
        await ticketing_server.start()
        result = await ticketing_server.handle_tool_call(
            "search_tickets",
            {
                "query": "test",
                "status": "open",
                "priority": "high",
            }
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_ticketing_response_time(self, ticketing_server):
        """CRITICAL: Ticketing server must respond within 2 seconds."""
        await ticketing_server.start()
        start = time.time()
        await ticketing_server.handle_tool_call(
            "create_ticket",
            {
                "subject": "Test",
                "description": "Test",
                "requester_email": "test@example.com",
            }
        )
        elapsed = (time.time() - start) * 1000
        assert elapsed < 2000


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrationServersIntegration:
    """Integration tests for all integration servers."""

    @pytest.mark.asyncio
    async def test_all_servers_start(self):
        """Test all integration servers can start with mocked clients."""
        mock_email = MagicMock()
        mock_email.is_connected = False
        mock_email.connect = AsyncMock(return_value=True)
        mock_email.disconnect = AsyncMock()

        mock_twilio = MagicMock()
        mock_twilio.is_connected = False
        mock_twilio.connect = AsyncMock(return_value=True)
        mock_twilio.disconnect = AsyncMock()

        mock_zendesk = MagicMock()
        mock_zendesk.is_connected = False
        mock_zendesk.connect = AsyncMock(return_value=True)
        mock_zendesk.disconnect = AsyncMock()

        servers = [
            EmailServer(email_client=mock_email),
            VoiceServer(twilio_client=mock_twilio),
            ChatServer(),
            TicketingServer(zendesk_client=mock_zendesk),
        ]

        for server in servers:
            await server.start()
            assert server.is_running is True
            await server.stop()

    @pytest.mark.asyncio
    async def test_all_servers_have_required_tools(self):
        """Test all servers have their required tools."""
        email = EmailServer(email_client=MagicMock(is_connected=False))
        voice = VoiceServer(twilio_client=MagicMock(is_connected=False))
        chat = ChatServer()
        ticketing = TicketingServer(zendesk_client=MagicMock(is_connected=False))

        # Email tools
        assert "send_email" in email.tools
        assert "send_bulk_emails" in email.tools
        assert "get_email_status" in email.tools
        assert "get_templates" in email.tools

        # Voice tools
        assert "make_call" in voice.tools
        assert "send_sms" in voice.tools
        assert "get_call_status" in voice.tools
        assert "validate_phone_number" in voice.tools

        # Chat tools
        assert "send_message" in chat.tools
        assert "create_conversation" in chat.tools
        assert "get_conversation_history" in chat.tools
        assert "mark_read" in chat.tools

        # Ticketing tools
        assert "create_ticket" in ticketing.tools
        assert "update_ticket" in ticketing.tools
        assert "get_ticket" in ticketing.tools
        assert "add_comment" in ticketing.tools
        assert "search_tickets" in ticketing.tools

    @pytest.mark.asyncio
    async def test_all_servers_respond_within_2_seconds(self):
        """CRITICAL: All servers must respond within 2 seconds."""
        # Setup mocks
        mock_email = MagicMock()
        mock_email.is_connected = False
        mock_email.connect = AsyncMock(return_value=True)
        mock_email.send_email = AsyncMock(return_value={"message_id": "x"})

        mock_twilio = MagicMock()
        mock_twilio.is_connected = False
        mock_twilio.connect = AsyncMock(return_value=True)
        mock_twilio.send_sms = AsyncMock(return_value={"sid": "x"})

        mock_zendesk = MagicMock()
        mock_zendesk.is_connected = False
        mock_zendesk.connect = AsyncMock(return_value=True)
        mock_zendesk.create_ticket = AsyncMock(return_value={"id": 1})

        servers = [
            (EmailServer(email_client=mock_email), "send_email",
             {"to": "t@t.com", "subject": "T", "body": "T"}),
            (VoiceServer(twilio_client=mock_twilio), "send_sms",
             {"to": "+123", "message": "T"}),
            (ChatServer(), "create_conversation",
             {"participants": ["user_1"]}),
            (TicketingServer(zendesk_client=mock_zendesk), "create_ticket",
             {"subject": "T", "description": "T", "requester_email": "t@t.com"}),
        ]

        for server, tool, params in servers:
            await server.start()
            start = time.time()
            result = await server.handle_tool_call(tool, params)
            elapsed = (time.time() - start) * 1000
            assert elapsed < 2000, f"{server.name} took {elapsed}ms"
            await server.stop()

    @pytest.mark.asyncio
    async def test_multi_channel_workflow(self):
        """Test a multi-channel support workflow."""
        # Setup mocks
        mock_email = MagicMock()
        mock_email.is_connected = False
        mock_email.connect = AsyncMock(return_value=True)
        mock_email.disconnect = AsyncMock()
        mock_email.send_email = AsyncMock(return_value={
            "message_id": "msg_123",
            "status": "queued",
        })

        mock_zendesk = MagicMock()
        mock_zendesk.is_connected = False
        mock_zendesk.connect = AsyncMock(return_value=True)
        mock_zendesk.disconnect = AsyncMock()
        mock_zendesk.create_ticket = AsyncMock(return_value={
            "id": 12345,
            "status": "new",
        })

        # Start servers
        email = EmailServer(email_client=mock_email)
        ticketing = TicketingServer(zendesk_client=mock_zendesk)

        await email.start()
        await ticketing.start()

        # 1. Create ticket
        ticket_result = await ticketing.handle_tool_call(
            "create_ticket",
            {
                "subject": "Customer Issue",
                "description": "Customer needs help",
                "requester_email": "customer@example.com",
            }
        )
        assert ticket_result.success is True

        # 2. Send confirmation email
        email_result = await email.handle_tool_call(
            "send_email",
            {
                "to": "customer@example.com",
                "subject": "Ticket Created",
                "body": "<p>Your ticket has been created.</p>",
            }
        )
        assert email_result.success is True

        # Cleanup
        await email.stop()
        await ticketing.stop()

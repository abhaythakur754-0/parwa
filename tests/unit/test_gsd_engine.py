"""
Unit tests for GSD Engine.
"""
import os
import uuid
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from shared.gsd_engine.state_schema import (
    Message,
    MessageRole,
    ConversationStatus,
    ContextHealthStatus,
    ConversationState,
    ContextMetadata,
)
from shared.gsd_engine.state_engine import StateEngine
from shared.gsd_engine.context_health import ContextHealthMonitor
from shared.gsd_engine.compression import ContextCompressor


class TestStateSchema:
    """Tests for state schema."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(role=MessageRole.USER, content="Hello!")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"
        assert msg.id is not None

    def test_conversation_state_creation(self):
        """Test creating a conversation state."""
        state = ConversationState()
        assert state.id is not None
        assert state.status == ConversationStatus.ACTIVE
        assert len(state.messages) == 0

    def test_add_message_to_conversation(self):
        """Test adding messages to conversation."""
        state = ConversationState()

        state.add_message(MessageRole.USER, "Hello", token_count=5)
        state.add_message(MessageRole.ASSISTANT, "Hi there!", token_count=10)

        assert len(state.messages) == 2
        assert state.context.message_count == 2
        assert state.context.total_tokens == 15
        assert state.context.turn_count == 1  # Only user messages count

    def test_get_token_count(self):
        """Test token count calculation."""
        state = ConversationState()

        state.add_message(MessageRole.USER, "Hello", token_count=5)
        state.add_message(MessageRole.ASSISTANT, "Hi!", token_count=3)

        assert state.get_token_count() == 8


class TestStateEngine:
    """Tests for State Engine."""

    def test_create_conversation(self):
        """Test creating a conversation."""
        engine = StateEngine()

        conv = engine.create_conversation(customer_id="cust_123")
        assert conv.id is not None
        assert conv.customer_id == "cust_123"
        assert conv.status == ConversationStatus.ACTIVE

    def test_get_conversation(self):
        """Test getting a conversation."""
        engine = StateEngine()

        created = engine.create_conversation()
        retrieved = engine.get_conversation(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_add_message(self):
        """Test adding a message."""
        engine = StateEngine()

        conv = engine.create_conversation()
        msg = engine.add_message(conv.id, MessageRole.USER, "Hello!")

        assert msg is not None
        assert msg.content == "Hello!"

    def test_transition_status(self):
        """Test status transitions."""
        engine = StateEngine()

        conv = engine.create_conversation()
        result = engine.transition_status(conv.id, ConversationStatus.ESCALATED)

        assert result is True
        assert conv.status == ConversationStatus.ESCALATED

    def test_get_context_for_llm(self):
        """Test getting LLM context."""
        engine = StateEngine()

        conv = engine.create_conversation()
        engine.add_message(conv.id, MessageRole.USER, "Hello")
        engine.add_message(conv.id, MessageRole.ASSISTANT, "Hi there!")

        context = engine.get_context_for_llm(conv.id)

        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"


class TestContextHealth:
    """Tests for Context Health Monitor."""

    def test_check_health_healthy(self):
        """Test health check for healthy conversation."""
        monitor = ContextHealthMonitor(max_tokens=1000)
        state = ConversationState()

        health = monitor.check_health(state)

        assert health.health_status == ContextHealthStatus.HEALTHY

    def test_check_health_warning_tokens(self):
        """Test health warning for high token count."""
        monitor = ContextHealthMonitor(max_tokens=100)
        state = ConversationState()

        # Add messages to exceed 75% threshold
        state.add_message(MessageRole.USER, "x" * 60, token_count=80)

        health = monitor.check_health(state)

        assert health.health_status in (ContextHealthStatus.WARNING, ContextHealthStatus.CRITICAL)

    def test_should_compress(self):
        """Test compression recommendation."""
        monitor = ContextHealthMonitor(max_tokens=100)
        state = ConversationState()

        state.add_message(MessageRole.USER, "x" * 60, token_count=80)

        assert monitor.should_compress(state) == True

    def test_should_escalate(self):
        """Test escalation recommendation."""
        monitor = ContextHealthMonitor()
        state = ConversationState()

        # Simulate 20 turns
        for i in range(20):
            state.add_message(MessageRole.USER, f"Message {i}")

        assert monitor.should_escalate(state) == True


class TestCompression:
    """Tests for Context Compressor."""

    def test_compress_reduces_tokens(self):
        """Test that compression reduces token count."""
        compressor = ContextCompressor(target_ratio=0.5, min_messages=2)
        state = ConversationState()

        # Add many messages
        for i in range(10):
            state.add_message(
                MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                f"This is message number {i} with some content",
                token_count=20
            )

        original_tokens = state.get_token_count()
        compressed = compressor.compress(state)
        new_tokens = compressed.get_token_count()

        assert new_tokens < original_tokens

    def test_keep_recent_messages(self):
        """Test that recent messages are preserved."""
        compressor = ContextCompressor(target_ratio=0.3, min_messages=4)
        state = ConversationState()

        for i in range(10):
            state.add_message(MessageRole.USER, f"Message {i}", token_count=20)

        last_messages = [m.content for m in state.messages[-4:]]
        compressed = compressor.compress(state)

        # Last 4 messages should still be present
        for content in last_messages:
            assert any(content in m.content for m in compressed.messages)

    def test_get_compression_stats(self):
        """Test compression statistics."""
        compressor = ContextCompressor()
        state = ConversationState()

        for i in range(5):
            state.add_message(MessageRole.USER, f"Message {i}", token_count=50)

        stats = compressor.get_compression_stats(state)

        assert "current_tokens" in stats
        assert "target_tokens" in stats
        assert "can_compress" in stats


class TestIntegration:
    """Integration tests for GSD Engine."""

    def test_full_workflow(self):
        """Test complete GSD workflow."""
        engine = StateEngine(max_tokens=500)
        monitor = ContextHealthMonitor(max_tokens=500)
        compressor = ContextCompressor(target_ratio=0.3, min_messages=2)

        # Create conversation
        conv = engine.create_conversation(customer_id="test_customer")

        # Add messages
        for i in range(15):
            engine.add_message(
                conv.id,
                MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                f"Message content {i}" * 5,
            )

        # Check health
        health = monitor.check_health(conv)

        # Compress if needed
        if monitor.should_compress(conv):
            compressor.compress(conv)

        # Verify workflow completed
        assert conv.status == ConversationStatus.ACTIVE
        assert len(conv.messages) > 0

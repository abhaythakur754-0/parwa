# AGENT_COMMS.md — Week 5 Day 1-5
# Last updated: Manager Agent
# Current status: WEEK 5 READY TO START

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 5 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: Week 5 Start

> **Phase: Phase 2 — Core AI Engine (GSD + Smart Router + KB + MCP)**
>
> **Week 5 Goals:**
> - Day 1: GSD State Engine chain (state_schema → state_engine → context_health → compression)
> - Day 2: Smart Router chain (tier_config → failover → complexity_scorer → router)
> - Day 3: Knowledge Base chain (vector_store → kb_manager → hyde → multi_query → rag_pipeline)
> - Day 4: MCP Client chain (client → auth → registry)
> - Day 5: Pricing tests + docs + webhook handler
> - Day 6: Tester Agent runs full week integration test
>
> **CRITICAL RULES:**
> 1. Within-day files CAN depend on each other — build in order listed
> 2. Across-day files CANNOT depend on each other — days run in parallel
> 3. You CANNOT use Docker locally — write tests with MOCKED databases
> 4. Build → Unit Test passes → THEN push (ONE push only per file)
> 5. NEVER push before test passes
> 6. Type hints on ALL functions, docstrings on ALL classes/functions
> 7. AI safety checks REQUIRED before any LLM call

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build (in order):**
1. `shared/gsd_engine/state_schema.py`
2. `shared/gsd_engine/state_engine.py`
3. `shared/gsd_engine/context_health.py`
4. `shared/gsd_engine/compression.py`
5. `tests/unit/test_gsd_engine.py`

**Purpose:** Build the GSD (Guided Self-Dialogue) State Engine — manages conversation state, context health monitoring, and message compression.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files from previous weeks:
- `shared/core_functions/config.py` — Configuration with app settings
- `shared/core_functions/logger.py` — Logger for structured logging
- `shared/core_functions/security.py` — Security utilities

**Step 3: Create the GSD Engine Directory**
```bash
mkdir -p shared/gsd_engine
touch shared/gsd_engine/__init__.py
```

**Step 4: Create state_schema.py**

Create `shared/gsd_engine/state_schema.py`:

```python
"""
PARWA GSD State Schema.

Defines the state structures for Guided Self-Dialogue conversations.
Includes conversation state, message tracking, and context metadata.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class ConversationStatus(str, Enum):
    """Conversation status types."""
    ACTIVE = "active"
    WAITING = "waiting"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class MessageRole(str, Enum):
    """Message role types."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ContextHealthStatus(str, Enum):
    """Context health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class Message(BaseModel):
    """Single message in a conversation."""
    id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    content: str
    token_count: int = Field(default=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        use_enum_values = True


class ContextMetadata(BaseModel):
    """Metadata about conversation context."""
    total_tokens: int = Field(default=0, ge=0)
    message_count: int = Field(default=0, ge=0)
    turn_count: int = Field(default=0, ge=0)
    health_status: ContextHealthStatus = Field(default=ContextHealthStatus.HEALTHY)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        use_enum_values = True


class ConversationState(BaseModel):
    """
    Full conversation state for GSD engine.
    
    Tracks all messages, context health, and conversation metadata
    for intelligent context management.
    """
    id: UUID = Field(default_factory=uuid4)
    company_id: Optional[UUID] = None
    customer_id: Optional[str] = None
    channel: Optional[str] = None
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    messages: List[Message] = Field(default_factory=list)
    context: ContextMetadata = Field(default_factory=ContextMetadata)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        use_enum_values = True

    def add_message(self, role: MessageRole, content: str, token_count: int = 0) -> Message:
        """Add a message to the conversation."""
        message = Message(
            role=role,
            content=content,
            token_count=token_count
        )
        self.messages.append(message)
        self.context.message_count = len(self.messages)
        self.context.total_tokens += token_count
        
        if role == MessageRole.USER:
            self.context.turn_count += 1
        
        self.updated_at = datetime.now(timezone.utc)
        return message

    def get_token_count(self) -> int:
        """Get total token count for all messages."""
        return sum(msg.token_count for msg in self.messages)

    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """Get most recent messages."""
        return self.messages[-limit:] if self.messages else []
```

**Step 5: Create state_engine.py**

Create `shared/gsd_engine/state_engine.py`:

```python
"""
PARWA GSD State Engine.

Manages conversation state lifecycle, message handling,
and state transitions for Guided Self-Dialogue.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone

from shared.core_functions.logger import get_logger
from shared.gsd_engine.state_schema import (
    ConversationState,
    ConversationStatus,
    MessageRole,
    Message,
    ContextMetadata,
)

logger = get_logger(__name__)


class StateEngine:
    """
    GSD State Engine for conversation management.
    
    Features:
    - Create and manage conversation states
    - Message addition with token tracking
    - State transitions (active → waiting → resolved/escalated)
    - Context window management
    """
    
    MAX_MESSAGES = 50
    MAX_TOKENS = 4000
    
    def __init__(
        self,
        company_id: Optional[UUID] = None,
        max_messages: int = MAX_MESSAGES,
        max_tokens: int = MAX_TOKENS
    ) -> None:
        """
        Initialize State Engine.
        
        Args:
            company_id: Company UUID for scoping
            max_messages: Maximum messages per conversation
            max_tokens: Maximum tokens in context window
        """
        self.company_id = company_id
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self._conversations: Dict[UUID, ConversationState] = {}
    
    def create_conversation(
        self,
        customer_id: Optional[str] = None,
        channel: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationState:
        """
        Create a new conversation state.
        
        Args:
            customer_id: Customer identifier
            channel: Communication channel
            metadata: Additional metadata
            
        Returns:
            Created ConversationState instance
        """
        state = ConversationState(
            company_id=self.company_id,
            customer_id=customer_id,
            channel=channel,
            metadata=metadata or {}
        )
        
        self._conversations[state.id] = state
        
        logger.info({
            "event": "conversation_created",
            "conversation_id": str(state.id),
            "company_id": str(self.company_id) if self.company_id else None,
            "channel": channel,
        })
        
        return state
    
    def get_conversation(self, conversation_id: UUID) -> Optional[ConversationState]:
        """
        Get a conversation by ID.
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            ConversationState if found, None otherwise
        """
        return self._conversations.get(conversation_id)
    
    def add_message(
        self,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        token_count: Optional[int] = None
    ) -> Optional[Message]:
        """
        Add a message to a conversation.
        
        Args:
            conversation_id: Conversation UUID
            role: Message role (user/assistant/system)
            content: Message content
            token_count: Token count (estimated if not provided)
            
        Returns:
            Created Message if successful, None if conversation not found
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            logger.warning({
                "event": "message_add_failed",
                "reason": "conversation_not_found",
                "conversation_id": str(conversation_id),
            })
            return None
        
        # Estimate tokens if not provided
        if token_count is None:
            token_count = self._estimate_tokens(content)
        
        message = conversation.add_message(role, content, token_count)
        
        # Check if context window is approaching limit
        if conversation.get_token_count() > self.max_tokens * 0.8:
            logger.warning({
                "event": "context_window_warning",
                "conversation_id": str(conversation_id),
                "token_count": conversation.get_token_count(),
                "max_tokens": self.max_tokens,
            })
        
        logger.info({
            "event": "message_added",
            "conversation_id": str(conversation_id),
            "role": role.value,
            "token_count": token_count,
            "total_tokens": conversation.get_token_count(),
        })
        
        return message
    
    def transition_status(
        self,
        conversation_id: UUID,
        new_status: ConversationStatus
    ) -> bool:
        """
        Transition conversation to a new status.
        
        Args:
            conversation_id: Conversation UUID
            new_status: Target status
            
        Returns:
            True if successful, False if conversation not found
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return False
        
        old_status = conversation.status
        conversation.status = new_status
        conversation.updated_at = datetime.now(timezone.utc)
        
        logger.info({
            "event": "status_transition",
            "conversation_id": str(conversation_id),
            "old_status": old_status,
            "new_status": new_status.value,
        })
        
        return True
    
    def get_context_for_llm(
        self,
        conversation_id: UUID,
        max_tokens: int = 4000
    ) -> List[Dict[str, str]]:
        """
        Get conversation context formatted for LLM.
        
        Args:
            conversation_id: Conversation UUID
            max_tokens: Maximum tokens to include
            
        Returns:
            List of messages in LLM format [{"role": ..., "content": ...}]
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return []
        
        context = []
        total_tokens = 0
        
        # Add messages from newest to oldest until limit
        for message in reversed(conversation.messages):
            if total_tokens + message.token_count > max_tokens:
                break
            
            context.insert(0, {
                "role": message.role.value if isinstance(message.role, MessageRole) else message.role,
                "content": message.content,
            })
            total_tokens += message.token_count
        
        return context
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough: 4 chars per token)."""
        return max(1, len(text) // 4)
    
    def get_active_conversations(self) -> List[ConversationState]:
        """Get all active conversations."""
        return [
            conv for conv in self._conversations.values()
            if conv.status == ConversationStatus.ACTIVE
        ]
```

**Step 6: Create context_health.py**

Create `shared/gsd_engine/context_health.py`:

```python
"""
PARWA Context Health Monitor.

Monitors conversation context health and provides
warnings and recommendations for context management.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from shared.core_functions.logger import get_logger
from shared.gsd_engine.state_schema import (
    ConversationState,
    ContextHealthStatus,
    ContextMetadata,
)

logger = get_logger(__name__)


class ContextHealthMonitor:
    """
    Context Health Monitor for GSD conversations.
    
    Monitors:
    - Token count vs context window limits
    - Message count vs maximum
    - Turn count for escalation detection
    - Stale conversations
    """
    
    # Thresholds
    TOKEN_WARNING_THRESHOLD = 0.75  # 75% of max tokens
    TOKEN_CRITICAL_THRESHOLD = 0.90  # 90% of max tokens
    MESSAGE_WARNING_THRESHOLD = 0.70  # 70% of max messages
    MESSAGE_CRITICAL_THRESHOLD = 0.85  # 85% of max messages
    TURN_WARNING_THRESHOLD = 15  # Warn at 15 turns
    TURN_ESCALATION_THRESHOLD = 20  # Suggest escalation at 20 turns
    
    def __init__(
        self,
        max_tokens: int = 4000,
        max_messages: int = 50,
        max_turns: int = 20
    ) -> None:
        """
        Initialize Context Health Monitor.
        
        Args:
            max_tokens: Maximum tokens in context window
            max_messages: Maximum messages per conversation
            max_turns: Maximum turns before escalation suggested
        """
        self.max_tokens = max_tokens
        self.max_messages = max_messages
        self.max_turns = max_turns
    
    def check_health(self, conversation: ConversationState) -> ContextMetadata:
        """
        Check health of a conversation's context.
        
        Args:
            conversation: ConversationState to check
            
        Returns:
            Updated ContextMetadata with health status
        """
        token_count = conversation.get_token_count()
        message_count = len(conversation.messages)
        turn_count = conversation.context.turn_count
        
        # Determine health status
        health_status = ContextHealthStatus.HEALTHY
        warnings = []
        
        # Check token health
        token_ratio = token_count / self.max_tokens if self.max_tokens > 0 else 0
        if token_ratio >= self.TOKEN_CRITICAL_THRESHOLD:
            health_status = ContextHealthStatus.CRITICAL
            warnings.append(f"Token count at {token_ratio:.0%} of limit")
        elif token_ratio >= self.TOKEN_WARNING_THRESHOLD:
            health_status = ContextHealthStatus.WARNING
            warnings.append(f"Token count at {token_ratio:.0%} of limit")
        
        # Check message count health
        message_ratio = message_count / self.max_messages if self.max_messages > 0 else 0
        if message_ratio >= self.MESSAGE_CRITICAL_THRESHOLD:
            health_status = ContextHealthStatus.CRITICAL
            warnings.append(f"Message count at {message_ratio:.0%} of limit")
        elif message_ratio >= self.MESSAGE_WARNING_THRESHOLD:
            if health_status == ContextHealthStatus.HEALTHY:
                health_status = ContextHealthStatus.WARNING
            warnings.append(f"Message count at {message_ratio:.0%} of limit")
        
        # Check turn count
        if turn_count >= self.TURN_ESCALATION_THRESHOLD:
            warnings.append(f"Turn count ({turn_count}) suggests escalation")
        elif turn_count >= self.TURN_WARNING_THRESHOLD:
            warnings.append(f"Turn count ({turn_count}) approaching limit")
        
        # Update context metadata
        conversation.context.health_status = health_status
        conversation.context.total_tokens = token_count
        conversation.context.message_count = message_count
        conversation.context.turn_count = turn_count
        conversation.context.last_updated = datetime.now(timezone.utc)
        
        if warnings:
            logger.warning({
                "event": "context_health_warning",
                "conversation_id": str(conversation.id),
                "health_status": health_status.value,
                "warnings": warnings,
            })
        
        return conversation.context
    
    def get_recommendations(self, conversation: ConversationState) -> List[str]:
        """
        Get recommendations for context management.
        
        Args:
            conversation: ConversationState to analyze
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        token_count = conversation.get_token_count()
        turn_count = conversation.context.turn_count
        
        # Token-based recommendations
        token_ratio = token_count / self.max_tokens if self.max_tokens > 0 else 0
        if token_ratio >= self.TOKEN_WARNING_THRESHOLD:
            recommendations.append("Consider compressing conversation history")
        
        if token_ratio >= self.TOKEN_CRITICAL_THRESHOLD:
            recommendations.append("Immediate compression or summarization required")
        
        # Turn-based recommendations
        if turn_count >= self.TURN_WARNING_THRESHOLD:
            recommendations.append("Consider escalating to human agent")
        
        if turn_count >= self.TURN_ESCALATION_THRESHOLD:
            recommendations.append("Escalation strongly recommended")
        
        return recommendations
    
    def should_compress(self, conversation: ConversationState) -> bool:
        """
        Check if conversation should be compressed.
        
        Args:
            conversation: ConversationState to check
            
        Returns:
            True if compression recommended
        """
        token_count = conversation.get_token_count()
        token_ratio = token_count / self.max_tokens if self.max_tokens > 0 else 0
        
        return token_ratio >= self.TOKEN_WARNING_THRESHOLD
    
    def should_escalate(self, conversation: ConversationState) -> bool:
        """
        Check if conversation should be escalated.
        
        Args:
            conversation: ConversationState to check
            
        Returns:
            True if escalation recommended
        """
        return conversation.context.turn_count >= self.TURN_ESCALATION_THRESHOLD
```

**Step 7: Create compression.py**

Create `shared/gsd_engine/compression.py`:

```python
"""
PARWA Context Compression.

Compresses conversation history to reduce token count
while preserving essential context.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID

from shared.core_functions.logger import get_logger
from shared.gsd_engine.state_schema import (
    ConversationState,
    Message,
    MessageRole,
)

logger = get_logger(__name__)


class ContextCompressor:
    """
    Context Compressor for conversation history.
    
    Strategies:
    - Summarize older messages
    - Remove redundant messages
    - Keep recent context intact
    """
    
    TARGET_COMPRESSION_RATIO = 0.15  # Target: 15% of original tokens
    MIN_MESSAGES_TO_KEEP = 4  # Always keep last 4 messages
    SYSTEM_MESSAGE_PRIORITY = True  # Never remove system messages
    
    def __init__(
        self,
        target_ratio: float = TARGET_COMPRESSION_RATIO,
        min_messages: int = MIN_MESSAGES_TO_KEEP
    ) -> None:
        """
        Initialize Context Compressor.
        
        Args:
            target_ratio: Target compression ratio (0.15 = 15%)
            min_messages: Minimum messages to preserve
        """
        self.target_ratio = target_ratio
        self.min_messages = min_messages
    
    def compress(
        self,
        conversation: ConversationState,
        target_tokens: Optional[int] = None
    ) -> ConversationState:
        """
        Compress conversation history.
        
        Args:
            conversation: ConversationState to compress
            target_tokens: Target token count (defaults to 15% of current)
            
        Returns:
            ConversationState with compressed history
        """
        current_tokens = conversation.get_token_count()
        
        if target_tokens is None:
            target_tokens = int(current_tokens * self.target_ratio)
        
        # If already under target, no compression needed
        if current_tokens <= target_tokens:
            logger.info({
                "event": "compression_skipped",
                "reason": "already_under_target",
                "current_tokens": current_tokens,
                "target_tokens": target_tokens,
            })
            return conversation
        
        # Calculate how many tokens to remove
        tokens_to_remove = current_tokens - target_tokens
        
        # Get messages to potentially compress (exclude recent)
        compressible_messages = conversation.messages[:-self.min_messages]
        recent_messages = conversation.messages[-self.min_messages:]
        
        if not compressible_messages:
            logger.warning({
                "event": "compression_skipped",
                "reason": "insufficient_messages",
                "message_count": len(conversation.messages),
                "min_to_keep": self.min_messages,
            })
            return conversation
        
        # Create summary of older messages
        summary = self._create_summary(compressible_messages)
        summary_tokens = self._estimate_tokens(summary)
        
        # Build new message list
        new_messages = []
        
        # Add summary as system message
        if summary:
            summary_msg = Message(
                role=MessageRole.SYSTEM,
                content=f"[Previous conversation summary: {summary}]",
                token_count=summary_tokens
            )
            new_messages.append(summary_msg)
        
        # Add recent messages
        new_messages.extend(recent_messages)
        
        # Update conversation
        conversation.messages = new_messages
        conversation.context.total_tokens = sum(m.token_count for m in new_messages)
        conversation.context.message_count = len(new_messages)
        
        new_tokens = conversation.get_token_count()
        compression_ratio = new_tokens / current_tokens if current_tokens > 0 else 0
        
        logger.info({
            "event": "compression_complete",
            "original_tokens": current_tokens,
            "new_tokens": new_tokens,
            "compression_ratio": f"{compression_ratio:.2%}",
            "messages_removed": len(compressible_messages),
            "summary_added": bool(summary),
        })
        
        return conversation
    
    def _create_summary(self, messages: List[Message]) -> str:
        """
        Create a summary of messages.
        
        Args:
            messages: Messages to summarize
            
        Returns:
            Summary string
        """
        if not messages:
            return ""
        
        # Simple summarization: extract key points
        user_messages = [m for m in messages if m.role == MessageRole.USER]
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]
        
        summary_parts = []
        
        if user_messages:
            user_topics = self._extract_topics([m.content for m in user_messages])
            if user_topics:
                summary_parts.append(f"User asked about: {', '.join(user_topics[:3])}")
        
        if assistant_messages:
            assistant_actions = self._extract_topics([m.content for m in assistant_messages])
            if assistant_actions:
                summary_parts.append(f"Assistant addressed: {', '.join(assistant_actions[:3])}")
        
        return "; ".join(summary_parts)
    
    def _extract_topics(self, texts: List[str]) -> List[str]:
        """
        Extract key topics from texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            List of topic keywords
        """
        # Simple keyword extraction
        keywords = []
        common_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                       "being", "have", "has", "had", "do", "does", "did", "will",
                       "would", "could", "should", "may", "might", "must", "shall",
                       "can", "need", "to", "of", "in", "for", "on", "with", "at",
                       "by", "from", "as", "into", "through", "during", "before",
                       "after", "above", "below", "between", "under", "again",
                       "further", "then", "once", "here", "there", "when", "where",
                       "why", "how", "all", "each", "few", "more", "most", "other",
                       "some", "such", "no", "nor", "not", "only", "own", "same",
                       "so", "than", "too", "very", "just", "and", "but", "if",
                       "or", "because", "until", "while", "this", "that", "these",
                       "those", "i", "me", "my", "myself", "we", "our", "ours",
                       "you", "your", "yours", "he", "him", "his", "she", "her",
                       "hers", "it", "its", "they", "them", "their", "what", "which",
                       "who", "whom", "get", "want", "know", "help", "thank", "thanks"}
        
        for text in texts:
            words = text.lower().split()
            for word in words:
                clean_word = ''.join(c for c in word if c.isalnum())
                if clean_word and clean_word not in common_words and len(clean_word) > 3:
                    if clean_word not in keywords:
                        keywords.append(clean_word)
        
        return keywords[:5]
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return max(1, len(text) // 4)
    
    def get_compression_stats(
        self,
        conversation: ConversationState
    ) -> Dict[str, Any]:
        """
        Get compression statistics for a conversation.
        
        Args:
            conversation: ConversationState to analyze
            
        Returns:
            Dict with compression statistics
        """
        current_tokens = conversation.get_token_count()
        target_tokens = int(current_tokens * self.target_ratio)
        
        return {
            "current_tokens": current_tokens,
            "target_tokens": target_tokens,
            "potential_reduction": current_tokens - target_tokens,
            "message_count": len(conversation.messages),
            "can_compress": current_tokens > target_tokens and len(conversation.messages) > self.min_messages,
        }
```

**Step 8: Create test_gsd_engine.py**

Create `tests/unit/test_gsd_engine.py`:

```python
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
```

**Step 9: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_gsd_engine.py -v
```

**Step 10: Fix Until Pass**

**Step 11: Push When Pass**
```bash
git add shared/gsd_engine/ tests/unit/test_gsd_engine.py
git commit -m "Week 5 Day 1: GSD State Engine with schema, engine, health monitor, and compression"
git push origin main
```

**Step 12: Update Status**
Update your status section below in AGENT_COMMS.md.

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 → DAY 1 STATUS
═══════════════════════════════════════════════════════════════════════════════
Date: Week 5 Day 1 Complete
Agent: Builder 1 (Zai)

### File 1: shared/gsd_engine/state_schema.py
- Status: ✅ DONE
- Unit Test: PASS
- GitHub CI: GREEN ✅
- Commit: 5b9b080
- Notes: Pydantic V2 models with ConfigDict

### File 2: shared/gsd_engine/state_engine.py
- Status: ✅ DONE
- Unit Test: PASS
- GitHub CI: GREEN ✅
- Commit: 5b9b080
- Notes: Full conversation lifecycle management

### File 3: shared/gsd_engine/context_health.py
- Status: ✅ DONE
- Unit Test: PASS
- GitHub CI: GREEN ✅
- Commit: 5b9b080
- Notes: Token/message/turn health monitoring

### File 4: shared/gsd_engine/compression.py
- Status: ✅ DONE
- Unit Test: PASS
- GitHub CI: GREEN ✅
- Commit: 5b9b080
- Notes: Context compression with summarization

### File 5: tests/unit/test_gsd_engine.py
- Status: ✅ DONE
- Unit Test: 17 PASS, 0 FAIL
- GitHub CI: GREEN ✅
- Commit: 5b9b080
- Notes: Full coverage for all GSD components

### Initiative Files:
- shared/gsd_engine/__init__.py (created proactively for module init)

### Overall Day Status: ✅ DONE — All 5 files pushed, CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build (in order):**
1. `shared/smart_router/tier_config.py`
2. `shared/smart_router/failover.py`
3. `shared/smart_router/complexity_scorer.py`
4. `shared/smart_router/router.py`
5. `tests/unit/test_smart_router.py` (update existing)

**Purpose:** Build the Smart Router chain — manages AI tier selection, provider failover, and query complexity scoring.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files from previous weeks:
- `shared/core_functions/config.py` — Configuration
- `shared/core_functions/logger.py` — Logger
- `shared/smart_router/provider_config.py` — Existing provider config (Week 3)
- `shared/smart_router/cost_optimizer.py` — Existing cost optimizer (Week 3)
- `shared/smart_router/routing_engine.py` — Existing routing engine (Week 3)

**Step 3: Create tier_config.py**

Create `shared/smart_router/tier_config.py`:

```python
"""
PARWA Tier Configuration.

Defines AI tier configurations for OpenRouter models.
Maps tiers (Light/Medium/Heavy) to specific models.
"""
from typing import Dict, Any, Optional
from enum import Enum

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AITier(str, Enum):
    """AI tier levels."""
    LIGHT = "light"      # Fast, cheap - for simple queries
    MEDIUM = "medium"    # Balanced - for moderate queries
    HEAVY = "heavy"      # Powerful - for complex queries


# Model configurations per tier
TIER_MODELS: Dict[str, Dict[str, str]] = {
    "google": {
        AITier.LIGHT.value: "gemma-2-9b-it",
        AITier.MEDIUM.value: "gemma-2-27b-it",
        AITier.HEAVY.value: "gemini-1.5-pro",
    },
    "cerebras": {
        AITier.LIGHT.value: "llama-3.1-8b",
        AITier.MEDIUM.value: "llama-3.1-70b",
        AITier.HEAVY.value: "llama-3.1-405b",
    },
    "groq": {
        AITier.LIGHT.value: "llama-3.1-8b-instant",
        AITier.MEDIUM.value: "llama-3.1-70b-versatile",
        AITier.HEAVY.value: "llama-3.1-405b-reasoning",
    },
}

# Cost per 1M tokens (approximate)
TIER_COSTS: Dict[str, float] = {
    AITier.LIGHT.value: 0.10,
    AITier.MEDIUM.value: 0.50,
    AITier.HEAVY.value: 2.00,
}

# Token limits per tier
TIER_TOKEN_LIMITS: Dict[str, int] = {
    AITier.LIGHT.value: 4096,
    AITier.MEDIUM.value: 8192,
    AITier.HEAVY.value: 32768,
}


class TierConfig:
    """
    Tier Configuration Manager.
    
    Manages AI tier configurations for OpenRouter.
    """
    
    def __init__(self, provider: Optional[str] = None) -> None:
        """
        Initialize Tier Config.
        
        Args:
            provider: LLM provider (google, cerebras, groq)
        """
        self.provider = provider or settings.llm_primary_provider
    
    def get_model(self, tier: AITier) -> str:
        """
        Get model name for tier.
        
        Args:
            tier: AI tier
            
        Returns:
            Model name string
        """
        provider_models = TIER_MODELS.get(self.provider, TIER_MODELS["google"])
        return provider_models.get(tier.value, provider_models[AITier.MEDIUM.value])
    
    def get_cost(self, tier: AITier) -> float:
        """
        Get cost per 1M tokens for tier.
        
        Args:
            tier: AI tier
            
        Returns:
            Cost in USD
        """
        return TIER_COSTS.get(tier.value, 0.50)
    
    def get_token_limit(self, tier: AITier) -> int:
        """
        Get token limit for tier.
        
        Args:
            tier: AI tier
            
        Returns:
            Token limit
        """
        return TIER_TOKEN_LIMITS.get(tier.value, 4096)
    
    def get_tier_config(self, tier: AITier) -> Dict[str, Any]:
        """
        Get full configuration for tier.
        
        Args:
            tier: AI tier
            
        Returns:
            Dict with model, cost, token_limit
        """
        return {
            "tier": tier.value,
            "provider": self.provider,
            "model": self.get_model(tier),
            "cost_per_1m_tokens": self.get_cost(tier),
            "token_limit": self.get_token_limit(tier),
        }
    
    def validate_tier_id(self, tier_id: str) -> bool:
        """
        Validate tier ID is in OpenRouter format.
        
        Args:
            tier_id: Tier identifier
            
        Returns:
            True if valid
        """
        return tier_id in [t.value for t in AITier]
```

**Step 4: Create failover.py**

Create `shared/smart_router/failover.py`:

```python
"""
PARWA Provider Failover.

Manages failover between LLM providers when rate limits
or errors occur.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ProviderStatus(str, Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class FailoverManager:
    """
    Provider Failover Manager.
    
    Features:
    - Track provider health
    - Automatic failover on errors
    - Rate limit handling
    - Recovery detection
    """
    
    ERROR_THRESHOLD = 5
    RECOVERY_INTERVAL = 300  # 5 minutes
    
    def __init__(self) -> None:
        """Initialize Failover Manager."""
        self._provider_status: Dict[str, ProviderStatus] = {}
        self._error_counts: Dict[str, int] = {}
        self._last_error_time: Dict[str, datetime] = {}
        self._primary_provider = settings.llm_primary_provider
        self._fallback_provider = settings.llm_fallback_provider
    
    def get_provider(self) -> str:
        """
        Get the best available provider.
        
        Returns:
            Provider name to use
        """
        # Check primary
        if self._is_available(self._primary_provider):
            return self._primary_provider
        
        # Fall back to secondary
        if self._fallback_provider and self._is_available(self._fallback_provider):
            logger.warning({
                "event": "provider_failover",
                "primary": self._primary_provider,
                "fallback": self._fallback_provider,
            })
            return self._fallback_provider
        
        # All providers potentially down - return primary anyway
        logger.error({
            "event": "all_providers_degraded",
            "returning": self._primary_provider,
        })
        return self._primary_provider
    
    def _is_available(self, provider: str) -> bool:
        """Check if provider is available."""
        status = self._provider_status.get(provider, ProviderStatus.HEALTHY)
        
        if status == ProviderStatus.UNHEALTHY:
            # Check if recovery time has passed
            last_error = self._last_error_time.get(provider)
            if last_error:
                elapsed = (datetime.utcnow() - last_error).total_seconds()
                if elapsed > self.RECOVERY_INTERVAL:
                    # Reset to degraded for retry
                    self._provider_status[provider] = ProviderStatus.DEGRADED
                    return True
            return False
        
        return True
    
    def record_success(self, provider: str) -> None:
        """
        Record successful request.
        
        Args:
            provider: Provider name
        """
        self._error_counts[provider] = 0
        self._provider_status[provider] = ProviderStatus.HEALTHY
        
        logger.debug({
            "event": "provider_success",
            "provider": provider,
        })
    
    def record_error(self, provider: str, error_type: str = "unknown") -> None:
        """
        Record provider error.
        
        Args:
            provider: Provider name
            error_type: Type of error
        """
        count = self._error_counts.get(provider, 0) + 1
        self._error_counts[provider] = count
        self._last_error_time[provider] = datetime.utcnow()
        
        if count >= self.ERROR_THRESHOLD:
            self._provider_status[provider] = ProviderStatus.UNHEALTHY
        else:
            self._provider_status[provider] = ProviderStatus.DEGRADED
        
        logger.warning({
            "event": "provider_error",
            "provider": provider,
            "error_type": error_type,
            "error_count": count,
            "status": self._provider_status[provider].value,
        })
    
    def record_rate_limit(self, provider: str) -> None:
        """
        Record rate limit hit.
        
        Args:
            provider: Provider name
        """
        self.record_error(provider, "rate_limit")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all providers.
        
        Returns:
            Dict with provider statuses
        """
        return {
            "primary": {
                "name": self._primary_provider,
                "status": self._provider_status.get(
                    self._primary_provider, ProviderStatus.HEALTHY
                ).value,
                "error_count": self._error_counts.get(self._primary_provider, 0),
            },
            "fallback": {
                "name": self._fallback_provider,
                "status": self._provider_status.get(
                    self._fallback_provider, ProviderStatus.HEALTHY
                ).value,
                "error_count": self._error_counts.get(self._fallback_provider, 0),
            } if self._fallback_provider else None,
        }
```

**Step 5: Create complexity_scorer.py**

Create `shared/smart_router/complexity_scorer.py`:

```python
"""
PARWA Complexity Scorer.

Scores query complexity to determine appropriate AI tier.
"""
from typing import Dict, Any, List
import re

from shared.core_functions.logger import get_logger
from shared.smart_router.tier_config import AITier

logger = get_logger(__name__)


class ComplexityScorer:
    """
    Query Complexity Scorer.
    
    Scores queries from 0-10 based on:
    - Keywords and patterns
    - Query length
    - Sentiment indicators
    - Domain-specific complexity
    """
    
    # Simple query patterns (score 0-2)
    SIMPLE_PATTERNS = [
        r"\bwhat is\b", r"\bhow do i\b", r"\bwhere can i\b",
        r"\bhours\b", r"\bcontact\b", r"\bprice\b", r"\bcost\b",
        r"\bfaq\b", r"\bhelp\b", r"\bsimple\b", r"\bbasic\b",
        r"\bwhen\b", r"\bwho\b", r"\bwhich\b",
    ]
    
    # Medium complexity patterns (score 3-6)
    MEDIUM_PATTERNS = [
        r"\bwhy\b", r"\bexplain\b", r"\bhow does\b",
        r"\bcompare\b", r"\bdifference\b", r"\bvs\b",
        r"\bproblem\b", r"\bissue\b", r"\bnot working\b",
        r"\berror\b", r"\bfailed\b", r"\bstuck\b",
    ]
    
    # High complexity patterns (score 7-10)
    COMPLEX_PATTERNS = [
        r"\brefund\b", r"\bdispute\b", r"\bescalat\b", r"\bmanager\b",
        r"\bcomplaint\b", r"\blegal\b", r"\battorney\b", r"\bsue\b",
        r"\bcompensation\b", r"\bdamages\b", r"\bfraud\b",
        r"\bunacceptable\b", r"\bterrible\b", r"\bworst\b",
    ]
    
    # Escalation indicators (auto-heavy)
    ESCALATION_PATTERNS = [
        r"\bspeak to.*human\b", r"\breal person\b", r"\bagent\b",
        r"\bsupervisor\b", r"\bmanager\b", r"\bcomplaint\b",
        r"\bnever.*again\b", r"\bcancel.*subscription\b", r"\bdelete.*account\b",
    ]
    
    def score(self, query: str) -> int:
        """
        Score query complexity from 0-10.
        
        Args:
            query: Customer query text
            
        Returns:
            Complexity score (0=simple FAQ, 10=complex escalation)
        """
        if not query:
            return 0
        
        query_lower = query.lower()
        score = 0
        
        # Check escalation patterns first (auto-high)
        for pattern in self.ESCALATION_PATTERNS:
            if re.search(pattern, query_lower):
                return 10
        
        # Count pattern matches
        simple_count = sum(1 for p in self.SIMPLE_PATTERNS if re.search(p, query_lower))
        medium_count = sum(1 for p in self.MEDIUM_PATTERNS if re.search(p, query_lower))
        complex_count = sum(1 for p in self.COMPLEX_PATTERNS if re.search(p, query_lower))
        
        # Base score from patterns
        if complex_count >= 2:
            score = 9
        elif complex_count == 1:
            score = 7
        elif medium_count >= 2:
            score = 5
        elif medium_count == 1:
            score = 3
        elif simple_count >= 1:
            score = 1
        else:
            score = 2
        
        # Adjust for query length
        word_count = len(query.split())
        if word_count > 50:
            score = min(10, score + 2)
        elif word_count > 30:
            score = min(10, score + 1)
        
        # Adjust for question marks (multiple = more complex)
        question_count = query.count("?")
        if question_count > 2:
            score = min(10, score + 1)
        
        logger.debug({
            "event": "complexity_scored",
            "query_length": len(query),
            "simple_matches": simple_count,
            "medium_matches": medium_count,
            "complex_matches": complex_count,
            "final_score": score,
        })
        
        return score
    
    def get_tier_for_score(self, score: int) -> AITier:
        """
        Get recommended AI tier for complexity score.
        
        Args:
            score: Complexity score (0-10)
            
        Returns:
            AITier recommendation
        """
        if score <= 2:
            return AITier.LIGHT
        elif score <= 6:
            return AITier.MEDIUM
        else:
            return AITier.HEAVY
    
    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Full analysis of query complexity.
        
        Args:
            query: Customer query text
            
        Returns:
            Dict with score, tier, and breakdown
        """
        score = self.score(query)
        tier = self.get_tier_for_score(score)
        
        return {
            "query": query[:100] + "..." if len(query) > 100 else query,
            "complexity_score": score,
            "recommended_tier": tier.value,
            "word_count": len(query.split()),
            "has_escalation_indicators": any(
                re.search(p, query.lower()) for p in self.ESCALATION_PATTERNS
            ),
        }
```

**Step 6: Create router.py (update existing)**

Update `shared/smart_router/router.py`:

```python
"""
PARWA Smart Router.

Routes customer queries to appropriate AI tier based on complexity,
sentiment, and company settings. Implements cost-optimized AI routing.
"""
from typing import Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime

from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger
from shared.smart_router.tier_config import AITier, TierConfig
from shared.smart_router.failover import FailoverManager
from shared.smart_router.complexity_scorer import ComplexityScorer

logger = get_logger(__name__)
settings = get_settings()


class SmartRouter:
    """
    Smart Router for AI tier selection.
    
    Routes queries to appropriate AI tier based on:
    - Query complexity analysis
    - Sentiment detection
    - Customer tier/subscription level
    - Company AI settings and budget
    - Provider health and failover
    """
    
    def __init__(
        self,
        company_id: Optional[UUID] = None,
        company_settings: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize Smart Router.
        
        Args:
            company_id: Company UUID for settings lookup
            company_settings: Company-specific routing settings
        """
        self.company_id = company_id
        self.company_settings = company_settings or {}
        self.tier_config = TierConfig()
        self.failover = FailoverManager()
        self.complexity_scorer = ComplexityScorer()
    
    def route(
        self,
        query: str,
        customer_tier: Optional[str] = None,
        budget_remaining: Optional[float] = None
    ) -> Tuple[AITier, Dict[str, Any]]:
        """
        Route query to appropriate AI tier.
        
        Args:
            query: Customer query text
            customer_tier: Customer subscription tier
            budget_remaining: Remaining AI budget
            
        Returns:
            Tuple of (AITier, routing_metadata dict)
        """
        # Score complexity
        complexity_score = self.complexity_scorer.score(query)
        recommended_tier = self.complexity_scorer.get_tier_for_score(complexity_score)
        
        # Get provider with failover
        provider = self.failover.get_provider()
        
        routing_metadata = {
            "complexity_score": complexity_score,
            "recommended_tier": recommended_tier.value,
            "provider": provider,
            "model": self.tier_config.get_model(recommended_tier),
            "customer_tier": customer_tier,
            "budget_remaining": budget_remaining,
            "routed_at": datetime.utcnow().isoformat(),
        }
        
        # Budget check - downgrade if necessary
        selected_tier = recommended_tier
        if budget_remaining is not None and budget_remaining < 1.0:
            # Critical budget - use light tier
            selected_tier = AITier.LIGHT
            routing_metadata["budget_downgrade"] = True
            routing_metadata["downgrade_reason"] = "critical_budget"
        elif budget_remaining is not None and budget_remaining < 10.0:
            # Low budget - downgrade heavy to medium
            if selected_tier == AITier.HEAVY:
                selected_tier = AITier.MEDIUM
                routing_metadata["budget_downgrade"] = True
                routing_metadata["downgrade_reason"] = "low_budget"
        
        routing_metadata["selected_tier"] = selected_tier.value
        routing_metadata["estimated_cost"] = self.tier_config.get_cost(selected_tier)
        
        logger.info({
            "event": "query_routed",
            "company_id": str(self.company_id) if self.company_id else None,
            "complexity_score": complexity_score,
            "selected_tier": selected_tier.value,
            "provider": provider,
        })
        
        return selected_tier, routing_metadata
    
    def get_model_for_tier(self, tier: AITier, provider: Optional[str] = None) -> str:
        """
        Get model name for tier.
        
        Args:
            tier: AI tier
            provider: Provider override
            
        Returns:
            Model name string
        """
        if provider:
            config = TierConfig(provider=provider)
            return config.get_model(tier)
        return self.tier_config.get_model(tier)
    
    def estimate_cost(self, query: str) -> float:
        """
        Estimate cost for processing query.
        
        Args:
            query: Customer query text
            
        Returns:
            Estimated cost in USD
        """
        tier, _ = self.route(query)
        base_cost = self.tier_config.get_cost(tier)
        
        # Adjust for query length
        token_estimate = len(query.split()) / 4
        length_multiplier = max(1.0, token_estimate / 500)
        
        return (base_cost / 1_000_000) * token_estimate * length_multiplier
    
    def record_success(self, provider: str) -> None:
        """Record successful provider request."""
        self.failover.record_success(provider)
    
    def record_error(self, provider: str, error_type: str = "unknown") -> None:
        """Record provider error."""
        self.failover.record_error(provider, error_type)
```

**Step 7: Update test_smart_router.py**

Add tests for new files to `tests/unit/test_smart_router.py`:

```python
# Add these tests to the existing test file

class TestTierConfig:
    """Tests for Tier Config."""
    
    def test_get_model(self):
        """Test getting model for tier."""
        from shared.smart_router.tier_config import TierConfig, AITier
        
        config = TierConfig()
        model = config.get_model(AITier.LIGHT)
        
        assert isinstance(model, str)
        assert len(model) > 0
    
    def test_get_cost(self):
        """Test getting tier cost."""
        from shared.smart_router.tier_config import TierConfig, AITier
        
        config = TierConfig()
        cost = config.get_cost(AITier.HEAVY)
        
        assert cost > 0
        assert isinstance(cost, float)
    
    def test_validate_tier_id(self):
        """Test tier ID validation."""
        from shared.smart_router.tier_config import TierConfig
        
        config = TierConfig()
        
        assert config.validate_tier_id("light") == True
        assert config.validate_tier_id("medium") == True
        assert config.validate_tier_id("heavy") == True
        assert config.validate_tier_id("invalid") == False


class TestFailover:
    """Tests for Failover Manager."""
    
    def test_get_provider(self):
        """Test getting provider."""
        from shared.smart_router.failover import FailoverManager
        
        manager = FailoverManager()
        provider = manager.get_provider()
        
        assert provider is not None
        assert isinstance(provider, str)
    
    def test_record_success(self):
        """Test recording success."""
        from shared.smart_router.failover import FailoverManager, ProviderStatus
        
        manager = FailoverManager()
        manager.record_success("google")
        
        status = manager.get_status()
        assert status["primary"]["status"] == ProviderStatus.HEALTHY.value
    
    def test_record_error_triggers_failover(self):
        """Test that errors trigger failover."""
        from shared.smart_router.failover import FailoverManager, ProviderStatus
        
        manager = FailoverManager()
        
        # Record errors up to threshold
        for i in range(manager.ERROR_THRESHOLD):
            manager.record_error(manager._primary_provider, "test_error")
        
        status = manager.get_status()
        assert status["primary"]["status"] == ProviderStatus.UNHEALTHY.value


class TestComplexityScorer:
    """Tests for Complexity Scorer."""
    
    def test_simple_query_score(self):
        """Test simple query scores 0-2."""
        from shared.smart_router.complexity_scorer import ComplexityScorer
        
        scorer = ComplexityScorer()
        score = scorer.score("What are your hours?")
        
        assert 0 <= score <= 2
    
    def test_complex_query_score(self):
        """Test complex query scores 7+."""
        from shared.smart_router.complexity_scorer import ComplexityScorer
        
        scorer = ComplexityScorer()
        score = scorer.score("I want a refund and I need to speak to a manager about this terrible issue")
        
        assert score >= 7
    
    def test_escalation_detection(self):
        """Test escalation auto-scores 10."""
        from shared.smart_router.complexity_scorer import ComplexityScorer
        
        scorer = ComplexityScorer()
        score = scorer.score("I need to speak to a human agent right now!")
        
        assert score == 10
    
    def test_get_tier_for_score(self):
        """Test tier mapping for scores."""
        from shared.smart_router.complexity_scorer import ComplexityScorer, AITier
        
        scorer = ComplexityScorer()
        
        assert scorer.get_tier_for_score(0) == AITier.LIGHT
        assert scorer.get_tier_for_score(5) == AITier.MEDIUM
        assert scorer.get_tier_for_score(9) == AITier.HEAVY
```

**Step 8: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_smart_router.py -v
```

**Step 9: Fix Until Pass, Then Push**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build (in order):**
1. `shared/knowledge_base/vector_store.py`
2. `shared/knowledge_base/kb_manager.py`
3. `shared/knowledge_base/hyde.py`
4. `shared/knowledge_base/multi_query.py`
5. `shared/knowledge_base/rag_pipeline.py`
6. `tests/unit/test_knowledge_base.py`

**Purpose:** Build the Knowledge Base chain — vector storage, KB management, HyDE, multi-query, and RAG pipeline.

### DEPENDENCIES FROM PREVIOUS WEEKS
- `shared/core_functions/config.py` (Wk1)
- `backend/app/database.py` (Wk2)

### KEY TESTS TO PASS
- Test: embeddings stored and retrieved
- Test: KB manager initialises
- Test: HyDE generates hypothetical doc
- Test: generates 3 query variants
- Test: ingest + retrieve round trip works

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build (in order):**
1. `shared/mcp_client/client.py`
2. `shared/mcp_client/auth.py`
3. `shared/mcp_client/registry.py`
4. `tests/unit/test_mcp_client.py`

**Purpose:** Build the MCP Client chain — client initialization, authentication, and registry connection.

### DEPENDENCIES FROM PREVIOUS WEEKS
- `shared/core_functions/config.py` (Wk1)
- `shared/core_functions/security.py` (Wk1-3)

### KEY TESTS TO PASS
- Test: client initialises
- Test: auth tokens generated
- Test: registry connects

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build (in order):**
1. `tests/unit/test_pricing_optimizer.py`
2. `docs/architecture_decisions/003_openrouter.md`
3. `backend/api/webhook_malformation_handler.py`

**Purpose:** Build pricing tests, OpenRouter documentation, and webhook malformation handler.

### DEPENDENCIES FROM PREVIOUS WEEKS
- `shared/core_functions/pricing_optimizer.py` (Wk1)
- `backend/api/webhooks/shopify.py` (Wk4)
- `backend/api/webhooks/stripe.py` (Wk4)

### KEY TESTS TO PASS
- Test: anti-arbitrage formula correct
- Test: half-corrupt webhook handled

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS — UPDATE AFTER COMPLETING YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

## BUILDER 1 (DAY 1) → STATUS
**Files:** `shared/gsd_engine/` (state_schema, state_engine, context_health, compression)
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_gsd_engine.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** None
**Notes:** Waiting to start

---

## BUILDER 2 (DAY 2) → STATUS
**Files:** `shared/smart_router/` (tier_config, failover, complexity_scorer, router)
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_smart_router.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** None
**Notes:** Waiting to start

---

## BUILDER 3 (DAY 3) → STATUS
**Files:** `shared/knowledge_base/` (vector_store, kb_manager, hyde, multi_query, rag_pipeline)
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_knowledge_base.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** None
**Notes:** Waiting to start

---

## BUILDER 4 (DAY 4) → STATUS
**Files:** `shared/mcp_client/` (client, auth, registry)
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** `tests/unit/test_mcp_client.py`
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** None
**Notes:** Waiting to start

---

## BUILDER 5 (DAY 5) → STATUS
**Files:** `tests/unit/test_pricing_optimizer.py`, `docs/architecture_decisions/003_openrouter.md`, `backend/api/webhook_malformation_handler.py`
**Status:** PENDING
**Unit Test:** NOT RUN
**Test File:** Self-contained
**Pushed:** NO
**Commit:** N/A
**Initiative Files:** None
**Notes:** Waiting to start

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING — Waiting for all builders to complete

**Test Command:** `pytest tests/integration/test_week5_gsd_kb.py -v`

**Verification Criteria:**
- GSD: 20-message conversation compresses to under 200 tokens
- Smart Router: FAQ routes to Light tier, refund routes to Heavy tier
- Failover: simulated rate limit triggers secondary model switch
- KB: document ingest and retrieve round trip works
- MCP client: initialises and connects to registry
- Integration: GSD → Smart Router → KB work as unified pipeline

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS FOR ALL BUILDERS:**

1. **Within-day dependencies OK** — Build files in order listed
2. **Across-day dependencies FORBIDDEN** — Don't import from other day's files
3. **No Docker** — Use mocked sessions in tests
4. **One Push Per File** — Push ONLY after test passes
5. **Type hints required** — All functions need type hints
6. **Docstrings required** — All classes and public functions need docstrings

---

═══════════════════════════════════════════════════════════════════════════════
## TEAM DISCUSSION
═══════════════════════════════════════════════════════════════════════════════

[Team discussion items will be added here as needed]

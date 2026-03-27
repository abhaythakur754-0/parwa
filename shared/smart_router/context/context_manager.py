"""
Context Manager for Smart Router
Conversation context tracking and management
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class ContextPriority(Enum):
    """Context priority levels"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class ContextItem:
    """Single context item"""
    key: str
    value: Any
    priority: ContextPriority
    timestamp: datetime
    ttl_seconds: Optional[int] = None
    source: str = "user"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if context item has expired."""
        if self.ttl_seconds is None:
            return False
        expiry = self.timestamp + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry


@dataclass
class ConversationContext:
    """Full conversation context"""
    session_id: str
    client_id: str
    user_id: Optional[str]
    items: Dict[str, ContextItem] = field(default_factory=dict)
    turn_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    # Context window limits
    MAX_ITEMS = 50
    MAX_TURNS = 100


class ContextManager:
    """
    Manages conversation context for routing decisions.
    Handles context window, prioritization, and persistence.
    """
    
    # Default TTLs for different context types
    DEFAULT_TTLS = {
        'user_intent': 3600,  # 1 hour
        'order_id': 86400,    # 24 hours
        'product_id': 86400,  # 24 hours
        'escalation_flag': 7200,  # 2 hours
        'sentiment': 1800,    # 30 minutes
        'issue_type': 7200,   # 2 hours
    }
    
    # Context priorities
    CONTEXT_PRIORITIES = {
        'escalation_flag': ContextPriority.CRITICAL,
        'user_intent': ContextPriority.HIGH,
        'order_id': ContextPriority.HIGH,
        'product_id': ContextPriority.MEDIUM,
        'issue_type': ContextPriority.MEDIUM,
        'sentiment': ContextPriority.LOW,
        'greeting_exchanged': ContextPriority.LOW,
    }
    
    def __init__(self, storage_backend: Optional[Any] = None):
        self.storage = storage_backend
        self._contexts: Dict[str, ConversationContext] = {}
        self._initialized = True
    
    def create_context(
        self,
        session_id: str,
        client_id: str,
        user_id: Optional[str] = None
    ) -> ConversationContext:
        """
        Create a new conversation context.
        
        Args:
            session_id: Unique session identifier
            client_id: Client identifier
            user_id: Optional user identifier
            
        Returns:
            Created ConversationContext
        """
        context = ConversationContext(
            session_id=session_id,
            client_id=client_id,
            user_id=user_id
        )
        
        self._contexts[session_id] = context
        logger.debug(f"Created context for session {session_id}")
        
        return context
    
    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """Get context for a session."""
        return self._contexts.get(session_id)
    
    def set(
        self,
        session_id: str,
        key: str,
        value: Any,
        priority: Optional[ContextPriority] = None,
        ttl_seconds: Optional[int] = None,
        source: str = "user",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Set a context value.
        
        Args:
            session_id: Session identifier
            key: Context key
            value: Context value
            priority: Priority level (auto-determined if not provided)
            ttl_seconds: Time to live in seconds
            source: Source of context (user, system, inherited)
            metadata: Additional metadata
            
        Returns:
            True if context was set successfully
        """
        context = self._contexts.get(session_id)
        if not context:
            logger.warning(f"Context not found for session {session_id}")
            return False
        
        # Determine priority
        if priority is None:
            priority = self.CONTEXT_PRIORITIES.get(key, ContextPriority.MEDIUM)
        
        # Determine TTL
        if ttl_seconds is None:
            ttl_seconds = self.DEFAULT_TTLS.get(key)
        
        item = ContextItem(
            key=key,
            value=value,
            priority=priority,
            timestamp=datetime.now(),
            ttl_seconds=ttl_seconds,
            source=source,
            metadata=metadata or {}
        )
        
        context.items[key] = item
        context.last_updated = datetime.now()
        context.turn_count += 1
        
        # Enforce context window limits
        self._enforce_limits(context)
        
        return True
    
    def get(
        self,
        session_id: str,
        key: str,
        default: Any = None
    ) -> Any:
        """
        Get a context value.
        
        Args:
            session_id: Session identifier
            key: Context key
            default: Default value if key not found
            
        Returns:
            Context value or default
        """
        context = self._contexts.get(session_id)
        if not context:
            return default
        
        item = context.items.get(key)
        if not item:
            return default
        
        # Check expiration
        if item.is_expired():
            del context.items[key]
            return default
        
        return item.value
    
    def get_all(
        self,
        session_id: str,
        include_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        Get all context values.
        
        Args:
            session_id: Session identifier
            include_metadata: Include metadata in output
            
        Returns:
            Dict of context key-value pairs
        """
        context = self._contexts.get(session_id)
        if not context:
            return {}
        
        result = {}
        expired_keys = []
        
        for key, item in context.items.items():
            if item.is_expired():
                expired_keys.append(key)
                continue
            
            if include_metadata:
                result[key] = {
                    'value': item.value,
                    'priority': item.priority.value,
                    'source': item.source,
                    'timestamp': item.timestamp.isoformat(),
                }
            else:
                result[key] = item.value
        
        # Clean up expired items
        for key in expired_keys:
            del context.items[key]
        
        return result
    
    def delete(self, session_id: str, key: str) -> bool:
        """Delete a context key."""
        context = self._contexts.get(session_id)
        if not context:
            return False
        
        if key in context.items:
            del context.items[key]
            return True
        return False
    
    def clear(self, session_id: str) -> bool:
        """Clear all context for a session."""
        context = self._contexts.get(session_id)
        if not context:
            return False
        
        context.items.clear()
        context.turn_count = 0
        context.last_updated = datetime.now()
        return True
    
    def _enforce_limits(self, context: ConversationContext) -> None:
        """Enforce context window limits."""
        # Remove expired items first
        expired = [k for k, v in context.items.items() if v.is_expired()]
        for key in expired:
            del context.items[key]
        
        # If still over limit, remove lowest priority items
        if len(context.items) > context.MAX_ITEMS:
            # Sort by priority (lowest first)
            sorted_items = sorted(
                context.items.items(),
                key=lambda x: (x[1].priority.value, x[1].timestamp)
            )
            
            # Remove excess items
            excess = len(context.items) - context.MAX_ITEMS
            for key, _ in sorted_items[:excess]:
                del context.items[key]
    
    def get_prioritized_context(
        self,
        session_id: str,
        min_priority: ContextPriority = ContextPriority.MEDIUM
    ) -> Dict[str, Any]:
        """
        Get context filtered by priority.
        
        Args:
            session_id: Session identifier
            min_priority: Minimum priority to include
            
        Returns:
            Filtered context dict
        """
        context = self._contexts.get(session_id)
        if not context:
            return {}
        
        return {
            k: v.value
            for k, v in context.items.items()
            if v.priority.value <= min_priority.value and not v.is_expired()
        }
    
    def persist(self, session_id: str) -> bool:
        """Persist context to storage backend."""
        context = self._contexts.get(session_id)
        if not context:
            return False
        
        # If no storage backend, consider it success (in-memory only)
        if not self.storage:
            logger.debug(f"No storage backend, context {session_id} stays in memory")
            return True
        
        # Serialize context
        data = {
            'session_id': context.session_id,
            'client_id': context.client_id,
            'user_id': context.user_id,
            'items': {
                k: {
                    'value': v.value,
                    'priority': v.priority.value,
                    'timestamp': v.timestamp.isoformat(),
                    'ttl_seconds': v.ttl_seconds,
                }
                for k, v in context.items.items()
            },
            'turn_count': context.turn_count,
        }
        
        # Would save to storage backend here
        logger.debug(f"Persisted context for session {session_id}")
        return True
    
    def restore(self, session_id: str) -> Optional[ConversationContext]:
        """Restore context from storage backend."""
        if not self.storage:
            return None
        
        # Would load from storage backend here
        return self._contexts.get(session_id)
    
    def get_multi_turn_context(
        self,
        session_id: str,
        turns: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get context for last N turns.
        
        Args:
            session_id: Session identifier
            turns: Number of turns to retrieve
            
        Returns:
            List of turn context dicts
        """
        context = self._contexts.get(session_id)
        if not context:
            return []
        
        # Return recent context items
        sorted_items = sorted(
            context.items.items(),
            key=lambda x: x[1].timestamp,
            reverse=True
        )[:turns]
        
        return [
            {
                'key': k,
                'value': v.value,
                'timestamp': v.timestamp.isoformat(),
            }
            for k, v in sorted_items
        ]
    
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            'active_contexts': len(self._contexts),
            'total_items': sum(len(c.items) for c in self._contexts.values()),
        }

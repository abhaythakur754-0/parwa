"""
PARWA Demo Usage Service

Tracks demo pack usage: 40 user messages (Jarvis responses don't count) + 3 min call.
Manages usage limits and consumption tracking.
"""

import time
from typing import Any, Dict, List, Optional
from datetime import datetime


class DemoUsageService:
    """Service for tracking demo pack usage."""
    
    # Demo pack limits
    USER_MESSAGE_LIMIT = 40  # User messages (Jarvis responses don't count)
    CALL_SECONDS_LIMIT = 180  # 3 minutes
    
    def __init__(self):
        self.usage_records: Dict[str, Dict[str, Any]] = {}
        self.usage_events: Dict[str, List[Dict[str, Any]]] = {}
    
    def init_usage(self, session_id: str) -> Dict[str, Any]:
        """Initialize usage tracking for a demo session."""
        usage = {
            'session_id': session_id,
            'user_messages_sent': 0,
            'user_messages_limit': self.USER_MESSAGE_LIMIT,
            'jarvis_messages_sent': 0,
            'call_seconds_used': 0,
            'call_seconds_limit': self.CALL_SECONDS_LIMIT,
            'call_initiated': False,
            'created_at': datetime.utcnow().isoformat(),
        }
        self.usage_records[session_id] = usage
        self.usage_events[session_id] = []
        return usage
    
    def record_user_message(self, session_id: str) -> Dict[str, Any]:
        """Record a user message sent in the demo."""
        usage = self.usage_records.get(session_id)
        if not usage:
            usage = self.init_usage(session_id)
        
        usage['user_messages_sent'] += 1
        self._add_event(session_id, 'user_message', {
            'total_sent': usage['user_messages_sent'],
        })
        
        return self.get_usage(session_id)
    
    def record_jarvis_message(self, session_id: str) -> Dict[str, Any]:
        """Record a Jarvis response (doesn't count toward limit)."""
        usage = self.usage_records.get(session_id)
        if not usage:
            usage = self.init_usage(session_id)
        
        usage['jarvis_messages_sent'] += 1
        self._add_event(session_id, 'jarvis_message', {
            'total_sent': usage['jarvis_messages_sent'],
        })
        
        return self.get_usage(session_id)
    
    def record_call_second(self, session_id: str) -> Dict[str, Any]:
        """Record a second of demo call usage."""
        usage = self.usage_records.get(session_id)
        if not usage:
            usage = self.init_usage(session_id)
        
        usage['call_seconds_used'] += 1
        if not usage.get('call_initiated'):
            usage['call_initiated'] = True
            self._add_event(session_id, 'call_initiated', {})
        
        self._add_event(session_id, 'call_second', {
            'total_seconds': usage['call_seconds_used'],
        })
        
        return self.get_usage(session_id)
    
    def get_usage(self, session_id: str) -> Dict[str, Any]:
        """Get current usage stats for a session."""
        usage = self.usage_records.get(session_id)
        if not usage:
            return self.init_usage(session_id)
        
        remaining_messages = usage['user_messages_limit'] - usage['user_messages_sent']
        remaining_call_seconds = usage['call_seconds_limit'] - usage['call_seconds_used']
        
        return {
            'session_id': session_id,
            'user_messages_sent': usage['user_messages_sent'],
            'user_messages_limit': usage['user_messages_limit'],
            'jarvis_messages_sent': usage['jarvis_messages_sent'],
            'call_seconds_used': usage['call_seconds_used'],
            'call_seconds_limit': usage['call_seconds_limit'],
            'is_call_available': remaining_call_seconds > 0,
            'is_messages_remaining': remaining_messages > 0,
            'percentage_used': round(
                (usage['user_messages_sent'] / usage['user_messages_limit']) * 100
            ),
        }
    
    def get_events(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent usage events."""
        events = self.usage_events.get(session_id, [])
        return events[-limit:]
    
    def is_limit_reached(self, session_id: str) -> bool:
        """Check if the user message limit has been reached."""
        usage = self.usage_records.get(session_id)
        if not usage:
            return False
        return usage['user_messages_sent'] >= usage['user_messages_limit']
    
    def is_call_available(self, session_id: str) -> bool:
        """Check if the demo call is still available."""
        usage = self.usage_records.get(session_id)
        if not usage:
            return True
        return usage['call_seconds_used'] < usage['call_seconds_limit']
    
    def _add_event(self, session_id: str, event_type: str, metadata: Dict[str, Any]):
        """Add a usage event to the session's event log."""
        if session_id not in self.usage_events:
            self.usage_events[session_id] = []
        
        self.usage_events[session_id].append({
            'type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': metadata,
        })


# Singleton instance
demo_usage_service = DemoUsageService()

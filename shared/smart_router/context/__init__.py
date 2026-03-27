"""
Smart Router Context Module - Week 35
Context-Aware Routing for improved routing decisions
"""

from .context_manager import ContextManager
from .session_tracker import SessionTracker
from .user_profiler import UserProfiler
from .routing_context import RoutingContext

__all__ = [
    'ContextManager',
    'SessionTracker',
    'UserProfiler',
    'RoutingContext',
]

__version__ = '1.0.0'

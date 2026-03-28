"""
Session Tracker for Smart Router
Session identification, state management, and cross-session linking
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import logging

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session states"""
    ACTIVE = "active"
    IDLE = "idle"
    ENDED = "ended"
    TIMEOUT = "timeout"
    ARCHIVED = "archived"


@dataclass
class Session:
    """Session information"""
    session_id: str
    client_id: str
    user_id: Optional[str]
    state: SessionState
    created_at: datetime
    last_activity: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Session configuration
    IDLE_TIMEOUT = 1800  # 30 minutes
    MAX_SESSION_AGE = 86400  # 24 hours


@dataclass
class SessionAnalytics:
    """Session analytics data"""
    total_sessions: int
    active_sessions: int
    avg_session_duration: float
    avg_turns_per_session: float
    timeout_rate: float


class SessionTracker:
    """
    Tracks session state and provides session management.
    Supports cross-session linking and analytics.
    """
    
    # Session timeouts
    DEFAULT_IDLE_TIMEOUT = 1800  # 30 minutes
    DEFAULT_MAX_AGE = 86400  # 24 hours
    
    def __init__(self, storage_backend: Optional[Any] = None):
        self.storage = storage_backend
        self._sessions: Dict[str, Session] = {}
        self._user_sessions: Dict[str, List[str]] = {}  # user_id -> session_ids
        self._session_counter = 0
        self._initialized = True
    
    def create_session(
        self,
        client_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Session:
        """
        Create a new session.
        
        Args:
            client_id: Client identifier
            user_id: Optional user identifier
            metadata: Optional session metadata
            
        Returns:
            Created Session
        """
        # Generate unique session ID
        self._session_counter += 1
        session_id = self._generate_session_id(client_id, self._session_counter)
        
        session = Session(
            session_id=session_id,
            client_id=client_id,
            user_id=user_id,
            state=SessionState.ACTIVE,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            metadata=metadata or {}
        )
        
        self._sessions[session_id] = session
        
        # Track user sessions
        if user_id:
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = []
            self._user_sessions[user_id].append(session_id)
        
        logger.info(f"Created session {session_id} for client {client_id}")
        return session
    
    def _generate_session_id(self, client_id: str, counter: int) -> str:
        """Generate unique session ID."""
        data = f"{client_id}:{counter}:{datetime.now().isoformat()}"
        hash_val = hashlib.sha256(data.encode()).hexdigest()[:12]
        return f"sess_{hash_val}"
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self._sessions.get(session_id)
    
    def update_activity(
        self,
        session_id: str,
        metadata_update: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update session activity timestamp.
        
        Args:
            session_id: Session identifier
            metadata_update: Optional metadata to merge
            
        Returns:
            True if session was updated
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.last_activity = datetime.now()
        
        if metadata_update:
            session.metadata.update(metadata_update)
        
        # Wake up from idle if needed
        if session.state == SessionState.IDLE:
            session.state = SessionState.ACTIVE
        
        return True
    
    def check_timeouts(self) -> List[str]:
        """
        Check for timed out sessions.
        
        Returns:
            List of timed out session IDs
        """
        now = datetime.now()
        timed_out = []
        
        for session_id, session in self._sessions.items():
            if session.state == SessionState.ENDED:
                continue
            
            # Check idle timeout
            idle_time = (now - session.last_activity).total_seconds()
            if idle_time > self.DEFAULT_IDLE_TIMEOUT:
                session.state = SessionState.TIMEOUT
                timed_out.append(session_id)
                continue
            
            # Check max age
            age = (now - session.created_at).total_seconds()
            if age > self.DEFAULT_MAX_AGE:
                session.state = SessionState.TIMEOUT
                timed_out.append(session_id)
        
        if timed_out:
            logger.info(f"Timed out {len(timed_out)} sessions")
        
        return timed_out
    
    def end_session(self, session_id: str) -> bool:
        """End a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.state = SessionState.ENDED
        logger.info(f"Ended session {session_id}")
        return True
    
    def get_user_sessions(
        self,
        user_id: str,
        include_ended: bool = False
    ) -> List[Session]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User identifier
            include_ended: Include ended sessions
            
        Returns:
            List of Sessions
        """
        session_ids = self._user_sessions.get(user_id, [])
        sessions = []
        
        for sid in session_ids:
            session = self._sessions.get(sid)
            if session:
                if include_ended or session.state != SessionState.ENDED:
                    sessions.append(session)
        
        return sessions
    
    def get_active_sessions(
        self,
        client_id: Optional[str] = None
    ) -> List[Session]:
        """
        Get all active sessions.
        
        Args:
            client_id: Optional client filter
            
        Returns:
            List of active Sessions
        """
        sessions = [
            s for s in self._sessions.values()
            if s.state == SessionState.ACTIVE
        ]
        
        if client_id:
            sessions = [s for s in sessions if s.client_id == client_id]
        
        return sessions
    
    def link_sessions(
        self,
        session_id_1: str,
        session_id_2: str
    ) -> bool:
        """
        Link two sessions (cross-session linking).
        
        Args:
            session_id_1: First session ID
            session_id_2: Second session ID
            
        Returns:
            True if linked successfully
        """
        session1 = self._sessions.get(session_id_1)
        session2 = self._sessions.get(session_id_2)
        
        if not session1 or not session2:
            return False
        
        # Add link in metadata
        if 'linked_sessions' not in session1.metadata:
            session1.metadata['linked_sessions'] = []
        if 'linked_sessions' not in session2.metadata:
            session2.metadata['linked_sessions'] = []
        
        session1.metadata['linked_sessions'].append(session_id_2)
        session2.metadata['linked_sessions'].append(session_id_1)
        
        logger.info(f"Linked sessions {session_id_1} and {session_id_2}")
        return True
    
    def get_linked_sessions(self, session_id: str) -> List[Session]:
        """Get sessions linked to a session."""
        session = self._sessions.get(session_id)
        if not session:
            return []
        
        linked_ids = session.metadata.get('linked_sessions', [])
        return [
            self._sessions[sid]
            for sid in linked_ids
            if sid in self._sessions
        ]
    
    def recover_session(
        self,
        session_id: str
    ) -> Optional[Session]:
        """
        Attempt to recover a timed out session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Recovered Session or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        # Check if recoverable
        if session.state not in [SessionState.TIMEOUT, SessionState.IDLE]:
            return session
        
        # Check recovery window (1 hour)
        recovery_window = 3600
        time_since_activity = (
            datetime.now() - session.last_activity
        ).total_seconds()
        
        if time_since_activity > recovery_window:
            # Too late to recover
            return None
        
        # Recover session
        session.state = SessionState.ACTIVE
        session.last_activity = datetime.now()
        
        logger.info(f"Recovered session {session_id}")
        return session
    
    def get_analytics(
        self,
        client_id: Optional[str] = None
    ) -> SessionAnalytics:
        """
        Get session analytics.
        
        Args:
            client_id: Optional client filter
            
        Returns:
            SessionAnalytics object
        """
        sessions = list(self._sessions.values())
        
        if client_id:
            sessions = [s for s in sessions if s.client_id == client_id]
        
        if not sessions:
            return SessionAnalytics(
                total_sessions=0,
                active_sessions=0,
                avg_session_duration=0,
                avg_turns_per_session=0,
                timeout_rate=0
            )
        
        active = [s for s in sessions if s.state == SessionState.ACTIVE]
        ended = [s for s in sessions if s.state in [SessionState.ENDED, SessionState.TIMEOUT]]
        
        # Calculate average duration
        durations = [
            (s.last_activity - s.created_at).total_seconds()
            for s in ended
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Calculate timeout rate
        timeouts = [s for s in sessions if s.state == SessionState.TIMEOUT]
        timeout_rate = len(timeouts) / len(sessions) if sessions else 0
        
        # Calculate average turns
        turns = [s.metadata.get('turn_count', 0) for s in sessions]
        avg_turns = sum(turns) / len(turns) if turns else 0
        
        return SessionAnalytics(
            total_sessions=len(sessions),
            active_sessions=len(active),
            avg_session_duration=avg_duration,
            avg_turns_per_session=avg_turns,
            timeout_rate=timeout_rate
        )
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up old ended sessions.
        
        Args:
            max_age_hours: Maximum age in hours to keep
            
        Returns:
            Number of sessions cleaned up
        """
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        to_remove = [
            sid for sid, s in self._sessions.items()
            if s.state in [SessionState.ENDED, SessionState.TIMEOUT]
            and s.last_activity < cutoff
        ]
        
        for sid in to_remove:
            del self._sessions[sid]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old sessions")
        
        return len(to_remove)
    
    def is_initialized(self) -> bool:
        """Check if tracker is initialized."""
        return self._initialized
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics."""
        return {
            'total_sessions': len(self._sessions),
            'active_sessions': len([
                s for s in self._sessions.values()
                if s.state == SessionState.ACTIVE
            ]),
            'user_count': len(self._user_sessions),
        }

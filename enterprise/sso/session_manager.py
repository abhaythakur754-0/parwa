"""
Enterprise SSO - Session Manager
Enterprise session management for SSO
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import secrets


class SessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class EnterpriseSession(BaseModel):
    """Enterprise session data"""
    session_id: str
    user_id: str
    client_id: str
    auth_method: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    status: SessionStatus = SessionStatus.ACTIVE
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict()


class SessionManager:
    """
    Manage enterprise sessions for SSO.
    """

    DEFAULT_SESSION_DURATION = timedelta(hours=8)

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.sessions: Dict[str, EnterpriseSession] = {}
        self.user_sessions: Dict[str, List[str]] = {}

    def create_session(
        self,
        user_id: str,
        auth_method: str,
        duration_hours: int = 8,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EnterpriseSession:
        """Create a new session"""
        session_id = secrets.token_urlsafe(32)
        now = datetime.utcnow()

        session = EnterpriseSession(
            session_id=session_id,
            user_id=user_id,
            client_id=self.client_id,
            auth_method=auth_method,
            created_at=now,
            expires_at=now + timedelta(hours=duration_hours),
            metadata=metadata or {}
        )

        self.sessions[session_id] = session

        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = []
        self.user_sessions[user_id].append(session_id)

        return session

    def validate_session(self, session_id: str) -> Optional[EnterpriseSession]:
        """Validate a session"""
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]

        if session.status != SessionStatus.ACTIVE:
            return None

        if datetime.utcnow() > session.expires_at:
            session.status = SessionStatus.EXPIRED
            return None

        # Update last activity
        session.last_activity = datetime.utcnow()
        return session

    def terminate_session(self, session_id: str) -> bool:
        """Terminate a session"""
        if session_id in self.sessions:
            self.sessions[session_id].status = SessionStatus.TERMINATED
            return True
        return False

    def terminate_all_user_sessions(self, user_id: str) -> int:
        """Terminate all sessions for a user"""
        count = 0
        if user_id in self.user_sessions:
            for session_id in self.user_sessions[user_id]:
                if self.terminate_session(session_id):
                    count += 1
        return count

    def get_active_sessions(self) -> List[EnterpriseSession]:
        """Get all active sessions"""
        return [
            s for s in self.sessions.values()
            if s.status == SessionStatus.ACTIVE
        ]

    def cleanup_expired(self) -> int:
        """Clean up expired sessions"""
        now = datetime.utcnow()
        count = 0
        for session in self.sessions.values():
            if session.expires_at < now and session.status == SessionStatus.ACTIVE:
                session.status = SessionStatus.EXPIRED
                count += 1
        return count

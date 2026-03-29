"""
Enterprise Session Manager for Secure Session Handling.

This module provides enterprise-grade session management with
concurrent session limits, session timeout policies, and
multi-device session tracking.
"""

import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Session status."""
    
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    IDLE = "idle"


class SessionType(str, Enum):
    """Session types."""
    
    WEB = "web"
    MOBILE = "mobile"
    API = "api"
    SSO = "sso"


class EnterpriseSession(BaseModel):
    """Enterprise session model."""
    
    session_id: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    user_id: str
    tenant_id: str
    session_type: SessionType = SessionType.WEB
    status: SessionStatus = SessionStatus.ACTIVE
    device_info: Dict[str, str] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=8)
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.status == SessionStatus.ACTIVE and not self.is_expired()


class SessionPolicy(BaseModel):
    """Session policy configuration."""
    
    max_concurrent_sessions: int = 5
    session_timeout_minutes: int = 480  # 8 hours
    idle_timeout_minutes: int = 30
    require_mfa_for_new_device: bool = False
    allowed_device_types: List[str] = Field(default_factory=lambda: ["web", "mobile", "api"])
    enforce_single_session: bool = False


class EnterpriseSessionManager:
    """
    Enterprise session manager for secure session handling.
    
    Features:
    - Concurrent session limits
    - Configurable session timeouts
    - Multi-device session tracking
    - Session revocation
    - Idle timeout detection
    """
    
    def __init__(self, default_policy: Optional[SessionPolicy] = None):
        """
        Initialize session manager.
        
        Args:
            default_policy: Default session policy
        """
        self.default_policy = default_policy or SessionPolicy()
        self._sessions: Dict[str, EnterpriseSession] = {}
        self._user_sessions: Dict[str, List[str]] = {}  # user_id -> [session_ids]
        self._tenant_policies: Dict[str, SessionPolicy] = {}
    
    def create_session(
        self,
        user_id: str,
        tenant_id: str,
        session_type: SessionType = SessionType.WEB,
        device_info: Optional[Dict[str, str]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        policy: Optional[SessionPolicy] = None
    ) -> Optional[EnterpriseSession]:
        """
        Create a new session.
        
        Args:
            user_id: User identifier
            tenant_id: Tenant identifier
            session_type: Type of session
            device_info: Device information
            ip_address: IP address
            user_agent: User agent string
            policy: Optional session policy
            
        Returns:
            Created session or None if limit reached
        """
        policy = policy or self._tenant_policies.get(tenant_id, self.default_policy)
        
        # Check concurrent session limit
        user_session_ids = self._user_sessions.get(user_id, [])
        active_sessions = [
            sid for sid in user_session_ids
            if sid in self._sessions and self._sessions[sid].is_active()
        ]
        
        if len(active_sessions) >= policy.max_concurrent_sessions:
            # Revoke oldest session
            oldest_session_id = min(
                active_sessions,
                key=lambda sid: self._sessions[sid].last_activity
            )
            self.revoke_session(oldest_session_id)
        
        # Enforce single session if required
        if policy.enforce_single_session:
            for sid in active_sessions:
                self.revoke_session(sid)
        
        # Create session
        session = EnterpriseSession(
            user_id=user_id,
            tenant_id=tenant_id,
            session_type=session_type,
            device_info=device_info or {},
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=policy.session_timeout_minutes)
        )
        
        self._sessions[session.session_id] = session
        
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = []
        self._user_sessions[user_id].append(session.session_id)
        
        return session
    
    def get_session(self, session_id: str) -> Optional[EnterpriseSession]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        if session.is_expired():
            session.status = SessionStatus.EXPIRED
            return None
        
        return session
    
    def validate_session(
        self,
        session_id: str,
        tenant_id: Optional[str] = None,
        check_idle: bool = True
    ) -> Dict[str, Any]:
        """
        Validate a session.
        
        Args:
            session_id: Session identifier
            tenant_id: Optional tenant ID to verify
            check_idle: Whether to check idle timeout
            
        Returns:
            Validation result
        """
        session = self._sessions.get(session_id)
        
        result = {
            "valid": False,
            "reason": None,
            "session": None
        }
        
        if not session:
            result["reason"] = "session_not_found"
            return result
        
        # Check expiration
        if session.is_expired():
            session.status = SessionStatus.EXPIRED
            result["reason"] = "session_expired"
            return result
        
        # Check status
        if session.status == SessionStatus.REVOKED:
            result["reason"] = "session_revoked"
            return result
        
        # Check tenant
        if tenant_id and session.tenant_id != tenant_id:
            result["reason"] = "tenant_mismatch"
            return result
        
        # Check idle timeout
        if check_idle:
            policy = self._tenant_policies.get(session.tenant_id, self.default_policy)
            idle_duration = (datetime.now(timezone.utc) - session.last_activity).total_seconds() / 60
            if idle_duration > policy.idle_timeout_minutes:
                session.status = SessionStatus.IDLE
                result["reason"] = "session_idle"
                return result
        
        # Update last activity
        session.last_activity = datetime.now(timezone.utc)
        
        result["valid"] = True
        result["session"] = session
        return result
    
    def refresh_session(
        self,
        session_id: str,
        extend_by_minutes: Optional[int] = None
    ) -> Optional[EnterpriseSession]:
        """
        Refresh a session.
        
        Args:
            session_id: Session identifier
            extend_by_minutes: Minutes to extend (uses policy default if not specified)
            
        Returns:
            Refreshed session or None
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active():
            return None
        
        policy = self._tenant_policies.get(session.tenant_id, self.default_policy)
        extend_by = extend_by_minutes or policy.session_timeout_minutes
        
        session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=extend_by)
        session.last_activity = datetime.now(timezone.utc)
        
        return session
    
    def revoke_session(self, session_id: str) -> bool:
        """
        Revoke a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if revoked
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.status = SessionStatus.REVOKED
        return True
    
    def revoke_all_user_sessions(
        self,
        user_id: str,
        except_session_id: Optional[str] = None
    ) -> int:
        """
        Revoke all sessions for a user.
        
        Args:
            user_id: User identifier
            except_session_id: Session to not revoke
            
        Returns:
            Number of sessions revoked
        """
        session_ids = self._user_sessions.get(user_id, [])
        count = 0
        
        for sid in session_ids:
            if sid != except_session_id:
                if self.revoke_session(sid):
                    count += 1
        
        return count
    
    def get_user_sessions(self, user_id: str) -> List[EnterpriseSession]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of sessions
        """
        session_ids = self._user_sessions.get(user_id, [])
        return [
            self._sessions[sid] 
            for sid in session_ids 
            if sid in self._sessions
        ]
    
    def get_active_sessions(self, user_id: str) -> List[EnterpriseSession]:
        """
        Get active sessions for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of active sessions
        """
        return [s for s in self.get_user_sessions(user_id) if s.is_active()]
    
    def set_tenant_policy(self, tenant_id: str, policy: SessionPolicy) -> None:
        """
        Set session policy for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            policy: Session policy
        """
        self._tenant_policies[tenant_id] = policy
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired() or session.status in [SessionStatus.EXPIRED, SessionStatus.REVOKED]
        ]
        
        for sid in expired:
            session = self._sessions[sid]
            if session.user_id in self._user_sessions:
                if sid in self._user_sessions[session.user_id]:
                    self._user_sessions[session.user_id].remove(sid)
            del self._sessions[sid]
        
        return len(expired)


# Global session manager instance
_session_manager: Optional[EnterpriseSessionManager] = None


def get_session_manager() -> EnterpriseSessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = EnterpriseSessionManager()
    return _session_manager

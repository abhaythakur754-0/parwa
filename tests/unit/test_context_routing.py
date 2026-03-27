"""
Context Routing Unit Tests - Week 35
Tests for Context-Aware Routing
"""

import pytest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from shared.smart_router.context.context_manager import (
    ContextManager, ContextItem, ContextPriority, ConversationContext
)
from shared.smart_router.context.session_tracker import (
    SessionTracker, Session, SessionState, SessionAnalytics
)
from shared.smart_router.context.user_profiler import (
    UserProfiler, UserProfile, UserBehavior, SkillLevel, LanguagePreference
)
from shared.smart_router.context.routing_context import (
    RoutingContext, RoutingDecision, RoutingPriority, ClientContext, TimeSegment
)


class TestContextManager:
    """Tests for Context Manager"""
    
    @pytest.fixture
    def manager(self):
        return ContextManager()
    
    def test_manager_initializes(self, manager):
        """Test: ContextManager initializes correctly"""
        assert manager is not None
        assert manager.is_initialized()
    
    def test_creates_context(self, manager):
        """Test: Creates conversation context"""
        context = manager.create_context(
            session_id="test-session-1",
            client_id="client-123",
            user_id="user-456"
        )
        
        assert context.session_id == "test-session-1"
        assert context.client_id == "client-123"
        assert context.user_id == "user-456"
    
    def test_sets_and_gets_context(self, manager):
        """Test: Sets and gets context values"""
        manager.create_context("test-session-1", "client-123")
        
        manager.set("test-session-1", "user_intent", "check_order_status")
        value = manager.get("test-session-1", "user_intent")
        
        assert value == "check_order_status"
    
    def test_context_prioritization(self, manager):
        """Test: Context prioritization works"""
        manager.create_context("test-session-1", "client-123")
        
        manager.set("test-session-1", "escalation_flag", True)
        manager.set("test-session-1", "greeting_exchanged", True)
        
        prioritized = manager.get_prioritized_context(
            "test-session-1", 
            ContextPriority.HIGH
        )
        
        assert "escalation_flag" in prioritized
        assert "greeting_exchanged" not in prioritized
    
    def test_context_window_management(self, manager):
        """Test: Context window management"""
        context = manager.create_context("test-session-1", "client-123")
        
        # Add more items than max
        for i in range(60):
            manager.set("test-session-1", f"key_{i}", f"value_{i}")
        
        # Should be trimmed
        assert len(context.items) <= context.MAX_ITEMS
    
    def test_context_persistence(self, manager):
        """Test: Context persistence"""
        manager.create_context("test-session-1", "client-123")
        manager.set("test-session-1", "test_key", "test_value")
        
        result = manager.persist("test-session-1")
        assert result is True
    
    def test_multi_turn_context(self, manager):
        """Test: Multi-turn context handling"""
        manager.create_context("test-session-1", "client-123")
        
        manager.set("test-session-1", "intent_1", "check_status")
        manager.set("test-session-1", "intent_2", "request_refund")
        manager.set("test-session-1", "intent_3", "contact_support")
        
        history = manager.get_multi_turn_context("test-session-1", turns=3)
        
        assert len(history) == 3


class TestSessionTracker:
    """Tests for Session Tracker"""
    
    @pytest.fixture
    def tracker(self):
        return SessionTracker()
    
    def test_tracker_initializes(self, tracker):
        """Test: SessionTracker initializes correctly"""
        assert tracker is not None
        assert tracker.is_initialized()
    
    def test_creates_session(self, tracker):
        """Test: Creates session"""
        session = tracker.create_session(
            client_id="client-123",
            user_id="user-456"
        )
        
        assert session.client_id == "client-123"
        assert session.user_id == "user-456"
        assert session.state == SessionState.ACTIVE
    
    def test_identifies_sessions(self, tracker):
        """Test: Identifies sessions"""
        session = tracker.create_session("client-123")
        
        retrieved = tracker.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
    
    def test_session_state_management(self, tracker):
        """Test: Session state management"""
        session = tracker.create_session("client-123")
        
        # Update activity
        tracker.update_activity(session.session_id)
        
        # End session
        tracker.end_session(session.session_id)
        
        ended = tracker.get_session(session.session_id)
        assert ended.state == SessionState.ENDED
    
    def test_cross_session_linking(self, tracker):
        """Test: Cross-session linking"""
        session1 = tracker.create_session("client-123", "user-1")
        session2 = tracker.create_session("client-123", "user-1")
        
        result = tracker.link_sessions(session1.session_id, session2.session_id)
        assert result is True
        
        linked = tracker.get_linked_sessions(session1.session_id)
        assert len(linked) == 1
    
    def test_session_recovery(self, tracker):
        """Test: Session recovery"""
        session = tracker.create_session("client-123")
        
        # Mark as timeout
        session.state = SessionState.TIMEOUT
        
        # Try to recover
        recovered = tracker.recover_session(session.session_id)
        
        # Should recover if within window
        assert recovered is not None
        assert recovered.state == SessionState.ACTIVE
    
    def test_session_analytics(self, tracker):
        """Test: Session analytics"""
        tracker.create_session("client-123")
        tracker.create_session("client-123")
        tracker.create_session("client-456")
        
        analytics = tracker.get_analytics()
        
        assert analytics.total_sessions == 3
        assert analytics.active_sessions == 3
    
    def test_timeout_handling(self, tracker):
        """Test: Session timeout handling"""
        from datetime import datetime, timedelta
        
        session = tracker.create_session("client-123")
        
        # Simulate old activity
        session.last_activity = datetime.now() - timedelta(hours=1)
        
        timed_out = tracker.check_timeouts()
        
        assert session.session_id in timed_out or session.state == SessionState.TIMEOUT


class TestUserProfiler:
    """Tests for User Profiler"""
    
    @pytest.fixture
    def profiler(self):
        return UserProfiler()
    
    def test_profiler_initializes(self, profiler):
        """Test: UserProfiler initializes correctly"""
        assert profiler is not None
        assert profiler.is_initialized()
    
    def test_profiles_user_behavior(self, profiler):
        """Test: Profiles user behavior"""
        profiler.create_profile("user-1", "client-123")
        
        profiler.update_behavior(
            user_id="user-1",
            query="Where is my order?",
            intent="check_order_status",
            channel="web",
            resolved=True
        )
        
        profile = profiler.get_profile("user-1")
        assert profile.behavior.total_queries == 1
        assert profile.behavior.successful_resolutions == 1
    
    def test_learns_preferences(self, profiler):
        """Test: Learns preferences"""
        profiler.create_profile("user-1", "client-123")
        
        profiler.learn_preference("user-1", "language", "en")
        profiler.learn_preference("user-1", "channel", "web")
        
        lang = profiler.get_preference("user-1", "language")
        channel = profiler.get_preference("user-1", "channel")
        
        assert lang == "en"
        assert channel == "web"
    
    def test_interaction_history_analysis(self, profiler):
        """Test: Interaction history analysis"""
        profiler.create_profile("user-1", "client-123")
        
        # Add multiple interactions
        for i in range(5):
            profiler.update_behavior(
                user_id="user-1",
                query=f"Query {i}",
                intent="check_order_status",
                channel="web",
                resolved=True
            )
        
        profile = profiler.get_profile("user-1")
        assert profile.behavior.total_queries == 5
    
    def test_skill_level_estimation(self, profiler):
        """Test: Skill level estimation"""
        profile = profiler.create_profile("user-1", "client-123")
        
        # Beginner with 0 queries
        assert profile.skill_level == SkillLevel.BEGINNER
        
        # Update to intermediate
        for i in range(15):
            profiler.update_behavior(
                user_id="user-1",
                query=f"Query {i}",
                intent="check_status",
                channel="web",
                resolved=True
            )
        
        profile = profiler.get_profile("user-1")
        assert profile.skill_level == SkillLevel.INTERMEDIATE
    
    def test_language_preference_detection(self, profiler):
        """Test: Language preference detection"""
        profiler.create_profile("user-1", "client-123")
        
        # English query
        lang = profiler.detect_language_preference("user-1", "Hello, I need help")
        assert lang == LanguagePreference.ENGLISH
        
        # Spanish query
        lang = profiler.detect_language_preference("user-1", "Hola, necesito ayuda")
        assert lang == LanguagePreference.SPANISH
    
    def test_privacy_respected(self, profiler):
        """Test: Privacy respected"""
        profiler = UserProfiler(privacy_mode=True)
        profiler.create_profile("user-1", "client-123")
        
        # Update with PII
        profiler.update_behavior(
            user_id="user-1",
            query="My email is test@example.com",
            intent="contact",
            channel="web",
            resolved=True
        )
        
        profile = profiler.get_profile("user-1")
        
        # PII should be sanitized
        for query in profile.behavior.last_10_queries:
            assert "test@example.com" not in query


class TestRoutingContext:
    """Tests for Routing Context"""
    
    @pytest.fixture
    def routing_ctx(self):
        return RoutingContext()
    
    def test_routing_context_initializes(self, routing_ctx):
        """Test: RoutingContext initializes correctly"""
        assert routing_ctx is not None
        assert routing_ctx.is_initialized()
    
    def test_makes_context_aware_decisions(self, routing_ctx):
        """Test: Makes context-aware decisions"""
        routing_ctx.register_client("client-123", tier="pro")
        
        decision = routing_ctx.get_routing_decision(
            session_id="session-1",
            client_id="client-123",
            user_id="user-1",
            conversation_context={"user_intent": "check_order_status"}
        )
        
        assert decision.selected_tier is not None
        assert decision.selected_model is not None
        assert decision.confidence > 0
    
    def test_uses_historical_patterns(self, routing_ctx):
        """Test: Uses historical patterns"""
        routing_ctx.register_client("client-123")
        
        # Set historical pattern
        routing_ctx.update_pattern_cache("user-1", {
            "preferred_tier": "heavy"
        })
        
        decision = routing_ctx.get_routing_decision(
            session_id="session-1",
            client_id="client-123",
            user_id="user-1",
            conversation_context={}
        )
        
        assert decision is not None
    
    def test_time_based_routing(self, routing_ctx):
        """Test: Time-based routing"""
        routing_ctx.register_client("client-123")
        
        decision = routing_ctx.get_routing_decision(
            session_id="session-1",
            client_id="client-123",
            user_id=None,
            conversation_context={}
        )
        
        # Should have time segment in context factors
        assert "time_segment" in decision.context_factors
    
    def test_client_specific_context(self, routing_ctx):
        """Test: Client-specific context"""
        routing_ctx.register_client(
            "client-123",
            tier="enterprise",
            sla_level="platinum",
            preferred_models=["high", "junior"]
        )
        
        decision = routing_ctx.get_routing_decision(
            session_id="session-1",
            client_id="client-123",
            user_id=None,
            conversation_context={}
        )
        
        assert decision.context_factors["client_tier"] == "enterprise"
    
    def test_priority_context_handling(self, routing_ctx):
        """Test: Priority context handling"""
        routing_ctx.register_client("client-123", tier="enterprise")
        
        # Critical priority context
        decision = routing_ctx.get_routing_decision(
            session_id="session-1",
            client_id="client-123",
            user_id=None,
            conversation_context={"escalation_flag": True}
        )
        
        assert decision.context_factors["priority"] == "critical"
        assert decision.selected_tier == "heavy"
    
    def test_context_based_fallback(self, routing_ctx):
        """Test: Context-based fallback"""
        routing_ctx.register_client("client-123")
        
        decision = routing_ctx.get_routing_decision(
            session_id="session-1",
            client_id="client-123",
            user_id=None,
            conversation_context={}
        )
        
        # Should have alternatives
        assert len(decision.alternative_routes) > 0


class TestContextRoutingIntegration:
    """Integration tests for context routing"""
    
    def test_full_context_flow(self):
        """Test: Full context flow"""
        manager = ContextManager()
        tracker = SessionTracker()
        profiler = UserProfiler()
        routing_ctx = RoutingContext()
        
        # Create session
        session = tracker.create_session("client-123", "user-1")
        
        # Create context
        context = manager.create_context(session.session_id, "client-123", "user-1")
        
        # Set context values
        manager.set(session.session_id, "user_intent", "check_order_status")
        manager.set(session.session_id, "order_id", "ABC-12345")
        
        # Create user profile
        profiler.create_profile("user-1", "client-123")
        profiler.update_behavior("user-1", "Where is my order?", "check_order_status", "web", True)
        
        # Register client for routing
        routing_ctx.register_client("client-123", tier="pro")
        
        # Make routing decision
        decision = routing_ctx.get_routing_decision(
            session_id=session.session_id,
            client_id="client-123",
            user_id="user-1",
            conversation_context=manager.get_all(session.session_id)
        )
        
        assert decision.selected_tier is not None
        assert decision.selected_model is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

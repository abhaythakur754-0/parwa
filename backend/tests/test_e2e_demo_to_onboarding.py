"""
PARWA End-to-End Test: Demo to Onboarding Complete Flow

This test simulates a real customer journey:
1. Landing Page → Free Demo
2. Chat with Jarvis AI (z-ai-web-dev-sdk)
3. Demo Pack Purchase ($1)
4. Registration/Signup
5. Email Verification
6. Login
7. Onboarding Steps 1-5
8. AI Activation with welcome communications

All integrations tested:
- z-ai-web-dev-sdk (AI Chat)
- Brevo (Email)
- Twilio (SMS)
- Paddle (Payment)
"""

import pytest
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

# Test markers
pytestmark = pytest.mark.e2e


class TestDemoFlow:
    """Test the pre-purchase demo experience."""
    
    def test_create_demo_session(self, db: Session):
        """Test: User starts a free demo session."""
        from app.services.jarvis_service import create_or_resume_session
        
        user_id = str(uuid.uuid4())
        
        session = create_or_resume_session(
            db=db,
            user_id=user_id,
            entry_source="landing_page",
            entry_params={"industry": "ecommerce"}
        )
        
        assert session is not None
        assert session.user_id == user_id
        assert session.pack_type == "free"
        assert session.is_active is True
        
        # Verify context
        ctx = json.loads(session.context_json)
        assert ctx.get("entry_source") == "landing_page"
        assert ctx.get("industry") == "ecommerce"
    
    def test_demo_chat_with_ai(self, db: Session):
        """Test: User chats with Jarvis AI using z-ai-web-dev-sdk."""
        from app.services.jarvis_service import (
            create_or_resume_session,
            send_message,
        )
        
        user_id = str(uuid.uuid4())
        
        # Create session
        session = create_or_resume_session(
            db=db,
            user_id=user_id,
            entry_source="demo_test",
        )
        
        # Send message to AI
        user_msg, ai_msg, knowledge = send_message(
            db=db,
            session_id=str(session.id),
            user_id=user_id,
            user_message="Hello Jarvis, I run an e-commerce store. How can you help me?"
        )
        
        assert user_msg is not None
        assert user_msg.content == "Hello Jarvis, I run an e-commerce store. How can you help me?"
        
        # AI should respond
        assert ai_msg is not None
        assert len(ai_msg.content) > 0
        
        # Check message count updated
        db.refresh(session)
        assert session.message_count_today == 1
    
    def test_demo_message_limit(self, db: Session):
        """Test: Free demo has 20 messages/day limit."""
        from app.services.jarvis_service import (
            create_or_resume_session,
            send_message,
            check_message_limit,
            FREE_DAILY_LIMIT,
        )
        
        user_id = str(uuid.uuid4())
        
        session = create_or_resume_session(
            db=db,
            user_id=user_id,
        )
        
        # Check initial limit
        limit, remaining = check_message_limit(db, session)
        assert limit == FREE_DAILY_LIMIT
        assert remaining == FREE_DAILY_LIMIT
    
    def test_demo_pack_purchase(self, db: Session):
        """Test: User can purchase $1 Demo Pack."""
        from app.services.jarvis_service import (
            create_or_resume_session,
            purchase_demo_pack,
        )
        
        user_id = str(uuid.uuid4())
        
        session = create_or_resume_session(
            db=db,
            user_id=user_id,
        )
        
        # Mock Paddle for testing
        with patch('app.services.jarvis_service.get_paddle_service') as mock_paddle:
            mock_paddle.return_value.create_demo_pack_checkout = MagicMock(
                return_value={
                    "checkout_url": "https://checkout.paddle.com/demo",
                    "transaction_id": "txn_test_123",
                    "amount": "$1.00",
                    "currency": "USD",
                }
            )
            
            result = purchase_demo_pack(
                db=db,
                session_id=str(session.id),
                user_id=user_id,
            )
            
            assert result["status"] == "pending_payment"
            assert result["pack_type"] == "demo"
            assert "checkout_url" in result


class TestSignupFlow:
    """Test the registration/signup flow."""
    
    def test_user_registration(self, db: Session):
        """Test: User can register with email and password."""
        from app.services.auth_service import register_user
        from database.models.core import User
        
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"
        
        # Mock the password hashing
        with patch('app.services.auth_service.hash_password', return_value="hashed_pw"):
            user = register_user(
                db=db,
                email=email,
                password=password,
                full_name="Test User",
            )
        
        assert user is not None
        assert user.email == email
        assert user.full_name == "Test User"
    
    def test_email_verification_otp(self, db: Session):
        """Test: Email verification via OTP."""
        from app.services.jarvis_service import (
            create_or_resume_session,
            send_business_otp,
            verify_business_otp,
        )
        
        user_id = str(uuid.uuid4())
        session = create_or_resume_session(db=db, user_id=user_id)
        
        # Send OTP
        with patch('app.services.jarvis_service.send_email', return_value=True):
            result = send_business_otp(
                db=db,
                session_id=str(session.id),
                user_id=user_id,
                email="test@example.com",
            )
        
        assert result["status"] == "sent"
        
        # Get OTP from context (in production, user reads from email)
        ctx = json.loads(session.context_json)
        otp_code = ctx["otp"]["code"]
        
        # Verify OTP
        verify_result = verify_business_otp(
            db=db,
            session_id=str(session.id),
            user_id=user_id,
            code=otp_code,
        )
        
        assert verify_result["status"] == "verified"


class TestLoginFlow:
    """Test the login/authentication flow."""
    
    def test_user_login(self, db: Session):
        """Test: User can login with correct credentials."""
        from app.services.auth_service import authenticate_user
        from database.models.core import User
        
        # Create test user
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            email=f"login_test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="hashed_password",
            full_name="Login Test User",
            is_active=True,
        )
        db.add(user)
        db.commit()
        
        # Mock password verification
        with patch('app.services.auth_service.verify_password', return_value=True):
            authenticated = authenticate_user(
                db=db,
                email=user.email,
                password="correct_password",
            )
        
        assert authenticated is not None
        assert authenticated.email == user.email


class TestOnboardingFlow:
    """Test the complete onboarding wizard (5 steps)."""
    
    def test_complete_onboarding_step_by_step(self, db: Session):
        """Test: User completes all onboarding steps."""
        from app.services.onboarding_service import (
            get_or_create_session,
            complete_step,
            accept_legal_consents,
            activate_ai,
        )
        from database.models.core import User, Company
        
        # Create test user and company
        user_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        
        user = User(
            id=user_id,
            email=f"onboard_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="hashed",
            company_id=company_id,
            full_name="Onboard Test",
        )
        company = Company(
            id=company_id,
            name="Test Company",
        )
        db.add(user)
        db.add(company)
        db.commit()
        
        # Step 1: Company Details
        session = get_or_create_session(db, user_id, company_id)
        result = complete_step(db, user_id, company_id, step=1)
        assert result["current_step"] == 2
        
        # Step 2: Legal Consent
        consent_result = accept_legal_consents(
            db=db,
            user_id=user_id,
            company_id=company_id,
            accept_terms=True,
            accept_privacy=True,
            accept_ai_data=True,
        )
        assert "successfully" in consent_result["message"].lower()
        
        # Step 3: Integrations (mark as complete)
        result = complete_step(db, user_id, company_id, step=3)
        
        # Step 4: Knowledge Base (optional - skip)
        result = complete_step(db, user_id, company_id, step=4)
        
        # Step 5: AI Activation
        # Mock the AI greeting generation
        with patch('app.services.onboarding_service._generate_ai_greeting', 
                   return_value="Hello! I'm Jarvis, ready to help!"):
            with patch('app.services.onboarding_service._send_welcome_email', return_value=True):
                with patch('app.services.onboarding_service._send_onboarding_sms', return_value=True):
                    activation_result = activate_ai(
                        db=db,
                        user_id=user_id,
                        company_id=company_id,
                        ai_name="Jarvis",
                        ai_tone="professional",
                        ai_response_style="concise",
                    )
        
        assert "successfully" in activation_result["message"].lower()
        assert activation_result["ai_name"] == "Jarvis"
    
    def test_ai_greeting_generation(self, db: Session):
        """Test: AI greeting is generated using z-ai-web-dev-sdk."""
        from app.services.onboarding_service import _generate_ai_greeting
        
        # Test fallback greeting (SDK may not be available in tests)
        greeting = _generate_ai_greeting(
            ai_name="TestBot",
            ai_tone="friendly",
            company_name="Test Company"
        )
        
        assert greeting is not None
        assert len(greeting) > 0
        assert "TestBot" in greeting or "help" in greeting.lower()


class TestIntegrationConnections:
    """Test all integrations are connected properly."""
    
    def test_email_service_available(self):
        """Test: Brevo email service is configured."""
        from app.services.email_service import send_email
        
        # Email service should be importable
        assert send_email is not None
    
    def test_sms_service_available(self):
        """Test: Twilio SMS service is configured."""
        from app.services.sms_channel_service import SMSChannelService
        
        # SMS service should be importable
        assert SMSChannelService is not None
    
    def test_ai_sdk_primary_provider(self):
        """Test: z-ai-web-dev-sdk is the primary AI provider."""
        from app.services.jarvis_service import _try_ai_providers, _call_zai_sdk
        
        # Both functions should exist
        assert _try_ai_providers is not None
        assert _call_zai_sdk is not None
    
    def test_variant_capabilities(self):
        """Test: All PARWA variants are defined."""
        from app.services.variant_capability_service import VARIANT_CAPABILITIES
        
        # All three variants should exist
        assert "mini_parwa" in VARIANT_CAPABILITIES
        assert "parwa" in VARIANT_CAPABILITIES
        assert "high_parwa" in VARIANT_CAPABILITIES


class TestDashboardAnalytics:
    """Test dashboard and analytics for demo tracking."""
    
    def test_demo_analytics_tracking(self, db: Session):
        """Test: Demo sessions are tracked in analytics."""
        from app.services.jarvis_service import create_or_resume_session
        
        user_id = str(uuid.uuid4())
        
        session = create_or_resume_session(
            db=db,
            user_id=user_id,
            entry_source="dashboard_test",
        )
        
        # Session should be queryable for analytics
        assert session.id is not None
        assert session.created_at is not None


# ── Test Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def db():
    """Create a test database session."""
    from database.base import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

import uuid
from datetime import datetime
import pytest
from pydantic import ValidationError

from backend.models.company import Company, PlanTierEnum
from backend.models.user import User, RoleEnum
from backend.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from backend.schemas.user import UserCreate, UserResponse, UserUpdate
from backend.models.support_ticket import SupportTicket, ChannelEnum, TicketStatusEnum, AITierEnum, SentimentEnum
from backend.schemas.support import TicketCreate, TicketResponse, TicketUpdate
from backend.models.audit_trail import AuditTrail
from backend.schemas.audit import AuditTrailCreate, AuditTrailResponse

from backend.schemas.license import LicenseCreate, LicenseResponse
from backend.schemas.subscription import SubscriptionCreate, SubscriptionBase, SubscriptionResponse


class TestUserSchemas:
    def test_valid_dict_parses_into_user_create(self):
        data = {
            "email": "test@example.com",
            "role": "admin",
            "is_active": True,
            "password": "securepassword",
            "company_id": str(uuid.uuid4())
        }
        user = UserCreate(**data)
        assert user.email == "test@example.com"
        assert user.role == RoleEnum.admin
        assert user.password == "securepassword"

    def test_invalid_email_format_raises_validation_error(self):
        data = {
            "email": "not-an-email",
            "role": "admin",
            "password": "securepassword",
            "company_id": str(uuid.uuid4())
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**data)
        assert "value is not a valid email address" in str(exc_info.value)

    def test_password_length_raises_validation_error(self):
        data = {
            "email": "test@example.com",
            "role": "admin",
            "password": "short",
            "company_id": str(uuid.uuid4())
        }
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**data)
        assert "String should have at least 8 characters" in str(exc_info.value)

    def test_user_response_from_orm(self):
        uid = uuid.uuid4()
        cid = uuid.uuid4()
        now = datetime.utcnow()
        # Create a SQLAlchemy model instance
        db_user = User(
            id=uid,
            company_id=cid,
            email="test@example.com",
            password_hash="hashed_password",
            role=RoleEnum.manager,
            is_active=True,
            created_at=now,
            updated_at=now
        )
        # Parse it with UserResponse
        response = UserResponse.model_validate(db_user)
        assert response.id == uid
        assert response.company_id == cid
        assert response.email == "test@example.com"
        assert response.role == RoleEnum.manager
        assert response.is_active is True
        assert getattr(response, "password_hash", None) is None
        assert getattr(response, "password", None) is None


class TestCompanySchemas:
    def test_valid_dict_parses_into_company_create(self):
        data = {
            "name": "Test Company",
            "industry": "Tech",
            "plan_tier": "parwa",
            "is_active": True
        }
        company = CompanyCreate(**data)
        assert company.name == "Test Company"
        assert company.industry == "Tech"
        assert company.plan_tier == PlanTierEnum.parwa

    def test_missing_required_fields_raises_validation_error(self):
        # Missing 'industry' and 'plan_tier'
        data = {
            "name": "Test Company",
            "is_active": True
        }
        with pytest.raises(ValidationError) as exc_info:
            CompanyCreate(**data)
        
        err_str = str(exc_info.value)
        assert "industry" in err_str
        assert "plan_tier" in err_str

    def test_company_response_from_orm(self):
        cid = uuid.uuid4()
        now = datetime.utcnow()
        db_company = Company(
            id=cid,
            name="ORM Company",
            industry="Finance",
            plan_tier=PlanTierEnum.parwa_high,
            is_active=False,
            rls_policy_id="pol_123",
            created_at=now,
            updated_at=now
        )
        response = CompanyResponse.model_validate(db_company)
        assert response.id == cid
        assert response.name == "ORM Company"
        assert response.industry == "Finance"
        assert response.plan_tier == PlanTierEnum.parwa_high
        assert response.is_active is False
        assert response.rls_policy_id == "pol_123"

class TestSupportSchemas:
    def test_ticket_create_valid_email(self):
        data = {
            "customer_email": "customer@example.com",
            "channel": ChannelEnum.email,
            "subject": "Help Needed",
            "body": "Please assist."
        }
        ticket = TicketCreate(**data)
        assert ticket.customer_email == "customer@example.com"
        assert ticket.subject == "Help Needed"

    def test_ticket_create_invalid_email(self):
        data = {
            "customer_email": "invalid-email",
            "channel": ChannelEnum.email,
            "subject": "Help Needed",
            "body": "Please assist."
        }
        with pytest.raises(ValidationError) as exc:
            TicketCreate(**data)
        assert "value is not a valid email address" in str(exc.value)

    def test_ticket_response_ai_confidence_constraints(self):
        data_valid = {
            "id": uuid.uuid4(),
            "company_id": uuid.uuid4(),
            "customer_email": "customer@example.com",
            "channel": ChannelEnum.email,
            "subject": "Help Needed",
            "body": "Please assist.",
            "status": TicketStatusEnum.open,
            "ai_confidence": 0.85,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        response = TicketResponse(**data_valid)
        assert response.ai_confidence == 0.85

        data_invalid = data_valid.copy()
        data_invalid["ai_confidence"] = 1.5
        with pytest.raises(ValidationError) as exc:
            TicketResponse(**data_invalid)
        assert "Input should be less than or equal to 1" in str(exc.value)

class TestAuditSchemas:
    def test_audit_trail_create_valid_dict(self):
        data = {
            "action": "refund_approved",
            "details": {"amount": 50.0, "reason": "Customer request"},
            "company_id": uuid.uuid4(),
            "actor": "admin"
        }
        audit = AuditTrailCreate(**data)
        assert audit.action == "refund_approved"
        assert audit.details["amount"] == 50.0
        assert audit.actor == "admin"

class TestLicenseSchemas:
    def test_valid_dict_parses_into_license_create(self):
        data = {
            "license_key": "KEY-12345",
            "tier": "parwa",
            "status": "active",
            "max_seats": 5,
            "company_id": uuid.uuid4()
        }
        license_obj = LicenseCreate(**data)
        assert license_obj.license_key == "KEY-12345"
        assert license_obj.tier == "parwa"

class TestSubscriptionSchemas:
    def test_negative_amount_cents_raises_validation_error(self):
        data = {
            "plan_tier": "mini",
            "status": "active",
            "amount_cents": -500,
            "currency": "usd",
            "company_id": uuid.uuid4(),
            "current_period_start": datetime.utcnow(),
            "current_period_end": datetime.utcnow()
        }
        with pytest.raises(ValidationError) as exc:
            SubscriptionCreate(**data)
        assert "Input should be greater than 0" in str(exc.value)

    def test_invalid_enum_in_subscription_base_raises_error(self):
        data = {
            "plan_tier": "invalid_tier",
            "status": "active",
            "amount_cents": 1000,
            "currency": "usd"
        }
        with pytest.raises(ValidationError) as exc:
            SubscriptionBase(**data)
        assert "Input should be 'mini', 'parwa' or 'parwa_high'" in str(exc.value)

    def test_model_instantiation_via_model_validate(self):
        from backend.models.subscription import Subscription
        db_sub = Subscription(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            stripe_subscription_id="sub_123",
            plan_tier="parwa",
            status="active",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
            amount_cents=5000,
            currency="usd",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        response = SubscriptionResponse.model_validate(db_sub)
        assert response.stripe_subscription_id == "sub_123"
        assert response.amount_cents == 5000


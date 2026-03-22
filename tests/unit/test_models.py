import pytest
import datetime
import uuid
from sqlalchemy.exc import IntegrityError
from backend.models.company import Company, PlanTierEnum
from backend.models.user import User, RoleEnum
from backend.models.training_data import TrainingData
from backend.models.license import License
from backend.models.subscription import Subscription
from backend.models.support_ticket import SupportTicket, TicketStatusEnum
from backend.models.audit_trail import AuditTrail
from backend.models.compliance_request import ComplianceRequest, ComplianceRequestStatus
from backend.models.sla_breach import SLABreach
from backend.models.usage_log import UsageLog

class TestLicenseModel:
    def test_has_expected_columns(self):
        columns = [c.name for c in License.__table__.columns]
        expected_columns = [
            "id", "company_id", "license_key", "tier", "status", 
            "issued_at", "expires_at", "max_seats", "created_at"
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column {col} in License model"

    def test_is_valid_expired_status(self):
        license = License(
            status="expired", 
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
        )
        assert not license.is_valid()

    def test_is_valid_expired_date(self):
        license = License(
            status="active", 
            expires_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        )
        assert not license.is_valid()

    def test_is_valid_active_and_future_date(self):
        license = License(
            status="active", 
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
        )
        assert license.is_valid()
        
    def test_is_valid_active_no_expiry(self):
        license = License(
            status="active", 
            expires_at=None
        )
        assert license.is_valid()

class TestSubscriptionModel:
    def test_has_expected_columns(self):
        columns = [c.name for c in Subscription.__table__.columns]
        expected_columns = [
            "id", "company_id", "stripe_subscription_id", "plan_tier", "status", 
            "current_period_start", "current_period_end", "amount_cents", "currency", 
            "created_at", "updated_at"
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column {col} in Subscription model"

    def test_is_active_subscription(self):
        sub_active = Subscription(status="active")
        assert sub_active.is_active_subscription() is True
        
        sub_past_due = Subscription(status="past_due")
        assert sub_past_due.is_active_subscription() is False
        
        sub_canceled = Subscription(status="canceled")
        assert sub_canceled.is_active_subscription() is False

class TestSupportTicketModel:
    def test_has_expected_columns(self):
        columns = [c.name for c in SupportTicket.__table__.columns]
        expected_columns = [
            "id", "company_id", "customer_email", "channel", "status", 
            "category", "subject", "body", "ai_recommendation", "ai_confidence", 
            "ai_tier_used", "sentiment", "assigned_to", "resolved_at", "created_at", "updated_at"
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column {col} in SupportTicket model"

    def test_is_pending_approval(self):
        ticket = SupportTicket(status=TicketStatusEnum.pending_approval)
        assert ticket.is_pending_approval() is True
        
        ticket_open = SupportTicket(status=TicketStatusEnum.open)
        assert ticket_open.is_pending_approval() is False
        
    def test_repr_masks_email(self):
        ticket = SupportTicket(customer_email="john.doe@example.com")
        rep = repr(ticket)
        assert "joh***" in rep
        assert "john.doe" not in rep


class TestAuditTrailModel:
    def test_has_expected_columns(self):
        columns = [c.name for c in AuditTrail.__table__.columns]
        expected_columns = [
            "id", "company_id", "ticket_id", "actor", "action", 
            "details", "previous_hash", "entry_hash", "created_at"
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column {col} in AuditTrail model"

    def test_compute_hash_returns_sha256(self):
        trail = AuditTrail(
            actor="admin",
            action="approve_refund",
            details={"amount": 100},
            previous_hash="somehash",
            created_at=datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        )
        h = trail.compute_hash()
        assert len(h) == 64
        assert int(h, 16) is not None

    def test_immutability_hash_changes(self):
        trail = AuditTrail(
            actor="admin",
            action="approve_refund",
            details={"amount": 100},
            previous_hash="hash1",
            created_at=datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        )
        h1 = trail.compute_hash()
        trail.actor = "hacker"
        h2 = trail.compute_hash()
        assert h1 != h2

    def test_hash_chain(self):
        entry1 = AuditTrail(
            actor="admin",
            action="init",
            details={},
            previous_hash=None,
            created_at=datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        )
        entry1.entry_hash = entry1.compute_hash()
        
        entry2 = AuditTrail(
            actor="admin",
            action="follow_up",
            details={},
            previous_hash=entry1.entry_hash,
            created_at=datetime.datetime(2026, 1, 1, 12, 5, 0, tzinfo=datetime.timezone.utc)
        )
        entry2.entry_hash = entry2.compute_hash()
        
        assert entry2.previous_hash == entry1.entry_hash


class TestComplianceRequestModel:
    def test_has_expected_columns(self):
        columns = [c.name for c in ComplianceRequest.__table__.columns]
        expected_columns = [
            "id", "company_id", "request_type", "customer_email", "status", 
            "requested_at", "completed_at", "result_url", "created_at"
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column {col} in ComplianceRequest model"

    def test_is_complete(self):
        req = ComplianceRequest(status=ComplianceRequestStatus.completed)
        assert req.is_complete() is True
        
        req_pending = ComplianceRequest(status=ComplianceRequestStatus.pending)
        assert req_pending.is_complete() is False

    def test_repr_masks_email(self):
        req = ComplianceRequest(customer_email="john.doe@example.com")
        rep = repr(req)
        assert "joh***" in rep
        assert "john.doe" not in rep

class TestSLABreachModel:
    def test_has_expected_columns(self):
        columns = [c.name for c in SLABreach.__table__.columns]
        expected_columns = [
            "id", "company_id", "ticket_id", "breach_phase", "breach_triggered_at", 
            "hours_overdue", "notified_to", "resolved_at", "created_at"
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column {col} in SLABreach model"

    def test_is_resolved(self):
        breach = SLABreach(resolved_at=datetime.datetime.now(datetime.timezone.utc))
        assert breach.is_resolved() is True
        
        breach_open = SLABreach(resolved_at=None)
        assert breach_open.is_resolved() is False

class TestUsageLogModel:
    def test_has_expected_columns(self):
        columns = [c.name for c in UsageLog.__table__.columns]
        expected_columns = [
            "id", "company_id", "log_date", "ai_tier", "request_count", 
            "token_count", "error_count", "avg_latency_ms", "created_at"
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column {col} in UsageLog model"

    def test_request_count_defaults_to_zero(self):
        log = UsageLog(ai_tier="light")
        assert log.request_count == 0
        assert log.token_count == 0
        assert log.error_count == 0

class TestCompanyModel:
    def test_has_expected_columns(self):
        columns = [c.name for c in Company.__table__.columns]
        expected_columns = [
            "id", "name", "industry", "plan_tier", "is_active", 
            "rls_policy_id", "created_at", "updated_at"
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column {col} in Company model"

    def test_plan_tier_validation(self):
        with pytest.raises(ValueError, match="Invalid plan_tier"):
            Company(name="Test Corp", industry="Tech", plan_tier="invalid_tier")

    def test_company_plan_tier_accepts_valid_enum(self):
        c = Company(name="Test Corp", industry="Tech", plan_tier=PlanTierEnum.parwa)
        assert c.plan_tier == PlanTierEnum.parwa

class TestUserModel:
    def test_has_expected_columns(self):
        columns = [c.name for c in User.__table__.columns]
        expected_columns = [
            "id", "company_id", "email", "password_hash", "role", 
            "is_active", "created_at", "updated_at"
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column {col} in User model"

    def test_role_validation(self):
        with pytest.raises(ValueError, match="Invalid role"):
            User(company_id=uuid.uuid4(), email="test@test.com", password_hash="hash", role="invalid_role")
            
    def test_role_accepts_valid_enum(self):
        u = User(company_id=uuid.uuid4(), email="test@test.com", password_hash="hash", role=RoleEnum.admin)
        assert u.role == RoleEnum.admin

    def test_user_company_fk_relationship(self):
        fk_cols = set()
        for fk in getattr(User.__table__.columns, 'company_id').foreign_keys:
            fk_cols.add(fk.target_fullname)
        assert "companies.id" in fk_cols

    def test_user_repr(self):
        uid = uuid.uuid4()
        u = User(id=uid, company_id=uid, email="test@test.com", password_hash="hash", role=RoleEnum.admin)
        rep = repr(u)
        assert str(uid) in rep
        assert "test@test.com" in rep
        assert "admin" in rep

class TestTrainingDataModel:
    def test_has_expected_columns(self):
        columns = [c.name for c in TrainingData.__table__.columns]
        expected_columns = [
            "id", "company_id", "ticket_id", "raw_interaction", 
            "anonymized_interaction", "sentiment_score", "extra_metadata", "created_at"
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column {col} in TrainingData model"

    def test_sentiment_score_validation(self):
        with pytest.raises(ValueError, match="sentiment_score must be between -1 and 1"):
            TrainingData(
                company_id=uuid.uuid4(),
                raw_interaction="test",
                anonymized_interaction="test",
                sentiment_score=1.5
            )

    def test_anonymize_stub(self):
        td = TrainingData()
        assert td.anonymize() == "[ANONYMIZED INTERACTION]"

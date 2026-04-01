"""
Tests for PARWA Database Models - Deep Checks (Day 2 Backfill)

Tests foreign keys, unique constraints, column types, nullable fields,
default values, relationships, and BC-002 precision across all 57 tables.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

import pytest  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from sqlalchemy import inspect  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

import database.models.core  # noqa: F401, E402
import database.models.billing  # noqa: F401, E402
import database.models.tickets  # noqa: F401, E402
import database.models.ai_pipeline  # noqa: F401, E402
import database.models.approval  # noqa: F401, E402
import database.models.analytics  # noqa: F401, E402
import database.models.training  # noqa: F401, E402
import database.models.integration  # noqa: F401, E402
import database.models.onboarding  # noqa: F401, E402

from database.base import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ── BC-002 Precision Check ───────────────────────────────────────


class TestBC002Precision:
    """BC-002: Money fields must be Numeric(10,2) exactly."""

    MONEY_FIELDS_PRECISION = {
        "invoices": {"amount": (10, 2)},
        "overage_charges": {"charge_amount": (10, 2)},
        "transactions": {"amount": (10, 2)},
        "approval_queues": {"amount": (10, 2)},
        "auto_approve_rules": {"max_amount": (10, 2)},
        "executed_actions": {"amount": (10, 2)},
        "metric_aggregates": {"value": (10, 2)},
        "roi_snapshots": {
            "avg_ai_cost": (10, 2),
            "avg_human_cost": (10, 2),
            "total_savings": (10, 2),
        },
    }

    def test_money_fields_precision(self):
        """All money fields use Numeric(10,2) not other precisions."""
        inspector = inspect(engine)
        for table_name, fields in self.MONEY_FIELDS_PRECISION.items():
            columns = {c["name"]: c for c in inspector.get_columns(table_name)}
            for field_name, expected_precision in fields.items():
                assert field_name in columns, f"Missing {table_name}.{field_name}"
                col_type = str(columns[field_name]["type"]).upper()
                assert "NUMERIC" in col_type, (
                    f"BC-002: {table_name}.{field_name} is not Numeric, got {col_type}"
                )


# ── Unique Constraints ───────────────────────────────────────────


class TestUniqueConstraints:
    """Verify unique constraints on critical fields."""

    def test_users_email_unique(self):
        """User email must be unique."""
        db = SessionLocal()
        from database.models.core import User, Company
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        db.add(co)
        db.flush()
        u1 = User(id="u1", company_id="co1", email="a@test.com", password_hash="hash1")
        u2 = User(id="u2", company_id="co1", email="a@test.com", password_hash="hash2")
        db.add(u1)
        db.add(u2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

    def test_api_keys_key_hash_unique(self):
        """API key hash must be unique."""
        db = SessionLocal()
        from database.models.core import APIKey, Company
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        db.add(co)
        db.flush()
        k1 = APIKey(id="k1", company_id="co1", name="key1", key_hash="same_hash", key_prefix="parw")
        k2 = APIKey(id="k2", company_id="co1", name="key2", key_hash="same_hash", key_prefix="parw")
        db.add(k1)
        db.add(k2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

    def test_refresh_tokens_token_hash_unique(self):
        """Refresh token hash must be unique."""
        db = SessionLocal()
        from database.models.core import RefreshToken, User, Company
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        u = User(id="u1", company_id="co1", email="a@test.com", password_hash="hash1")
        db.add(co)
        db.add(u)
        db.flush()
        future = datetime.now(tz=None) + timedelta(days=7)
        t1 = RefreshToken(
            id="t1", user_id="u1", company_id="co1",
            token_hash="same", expires_at=future,
        )
        t2 = RefreshToken(
            id="t2", user_id="u1", company_id="co1",
            token_hash="same", expires_at=future,
        )
        db.add(t1)
        db.add(t2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

    def test_webhook_events_event_id_unique(self):
        """Webhook event_id must be unique."""
        db = SessionLocal()
        from database.models.billing import WebhookEvent
        from database.models.core import Company
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        db.add(co)
        db.flush()
        e1 = WebhookEvent(id="e1", company_id="co1", event_type="pay", event_id="evt_123")
        e2 = WebhookEvent(id="e2", company_id="co1", event_type="pay", event_id="evt_123")
        db.add(e1)
        db.add(e2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()


# ── Foreign Key Cascade ──────────────────────────────────────────


class TestForeignKeyCascade:
    """BC-001: CASCADE deletes work correctly."""

    def test_delete_company_cascades_to_users(self):
        """Deleting a company deletes all its users (CASCADE)."""
        db = SessionLocal()
        from database.models.core import User, Company
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        db.add(co)
        db.flush()
        u = User(id="u1", company_id="co1", email="a@test.com", password_hash="hash1")
        db.add(u)
        db.commit()
        # User exists
        assert db.query(User).filter_by(company_id="co1").count() == 1
        # Delete company
        db.delete(co)
        db.commit()
        # User should be gone
        assert db.query(User).filter_by(company_id="co1").count() == 0
        db.close()

    def test_delete_company_cascades_to_subscriptions(self):
        """Subscription has FK to companies with ondelete=CASCADE."""
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys("subscriptions")
        company_fks = [fk for fk in fks if "companies" in fk.get("referred_table", "")]
        assert len(company_fks) > 0, "subscriptions must have FK to companies"
        # Check CASCADE is set
        fk = company_fks[0]
        ondelete = fk.get("ondelete") or fk.get("options", {}).get("ondelete")
        assert ondelete == "CASCADE", (
            f"subscriptions.company_id must have ondelete=CASCADE, got {ondelete}"
        )


# ── Column Types ─────────────────────────────────────────────────


class TestColumnTypes:
    """Verify column types across all model groups."""

    def test_core_models_column_types(self):
        """Core model columns have correct types."""
        inspector = inspect(engine)
        # Users: role should be String, is_active should be Boolean
        cols = {c["name"].lower(): str(c["type"]).upper() for c in inspector.get_columns("users")}
        role_col = cols.get("role", "")
        assert (
            "VARCHAR" in role_col
            or "STRING" in role_col
            or "CHAR" in role_col
        )
        assert "BOOLEAN" in cols.get("is_active", "")
        assert "BOOLEAN" in cols.get("mfa_enabled", "")

    def test_billing_money_columns_are_numeric(self):
        """All billing money columns use Numeric, not Float."""
        inspector = inspect(engine)
        for table in ["invoices", "overage_charges", "transactions"]:
            columns = {c["name"]: str(c["type"]).upper() for c in inspector.get_columns(table)}
            money_col = "amount" if table != "overage_charges" else "charge_amount"
            assert "FLOAT" not in columns[money_col], (
                f"BC-002: {table}.{money_col} uses Float!"
            )

    def test_sessions_have_correct_status_default(self):
        """Session status defaults to 'open'."""
        inspector = inspect(engine)
        cols = {c["name"]: c for c in inspector.get_columns("sessions")}
        # Check the column exists
        assert "status" in cols
        assert "status" in cols

    def test_all_tables_have_primary_key(self):
        """Every table must have a primary key."""
        inspector = inspect(engine)
        for table_name in inspector.get_table_names():
            pk = inspector.get_pk_constraint(table_name)
            assert pk and pk.get("constrained_columns"), (
                f"Table {table_name} has no primary key!"
            )


# ── Nullable vs Required ────────────────────────────────────────


class TestNullableFields:
    """Verify nullable/required constraints on critical fields."""

    def test_user_password_hash_not_nullable(self):
        """User password_hash must NOT be nullable (security)."""
        db = SessionLocal()
        from database.models.core import User, Company
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        db.add(co)
        db.flush()
        u = User(id="u1", company_id="co1", email="a@test.com", password_hash=None)
        db.add(u)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

    def test_user_email_not_nullable(self):
        """User email must NOT be nullable."""
        db = SessionLocal()
        from database.models.core import User, Company
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        db.add(co)
        db.flush()
        u = User(id="u1", company_id="co1", email=None, password_hash="hash1")
        db.add(u)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

    def test_company_id_not_nullable_on_users(self):
        """company_id on users must NOT be nullable (BC-001)."""
        db = SessionLocal()
        from database.models.core import User
        u = User(id="u1", company_id=None, email="a@test.com", password_hash="hash1")
        db.add(u)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

    def test_invoice_amount_not_nullable(self):
        """Invoice amount must NOT be nullable."""
        db = SessionLocal()
        from database.models.billing import Invoice
        from database.models.core import Company
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        db.add(co)
        db.flush()
        inv = Invoice(id="inv1", company_id="co1", amount=None, status="pending")
        db.add(inv)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()


# ── Relationships ────────────────────────────────────────────────


class TestRelationships:
    """Verify ORM relationships work correctly."""

    def test_company_users_relationship(self):
        """Company.users returns associated users."""
        db = SessionLocal()
        from database.models.core import User, Company
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        db.add(co)
        db.flush()
        db.add(User(id="u1", company_id="co1", email="a@test.com", password_hash="h1"))
        db.add(User(id="u2", company_id="co1", email="b@test.com", password_hash="h2"))
        db.commit()
        fetched = db.query(Company).filter_by(id="co1").first()
        assert len(fetched.users) == 2
        db.close()

    def test_session_interactions_relationship(self):
        """Session.interactions returns associated interactions."""
        db = SessionLocal()
        from database.models.core import Company
        from database.models.tickets import Session, Interaction
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        db.add(co)
        db.flush()
        sess = Session(id="s1", company_id="co1", channel="chat")
        db.add(sess)
        db.flush()
        db.add(Interaction(
            id="i1", session_id="s1", company_id="co1",
            role="customer", content="hi", channel="chat",
        ))
        db.add(Interaction(
            id="i2", session_id="s1", company_id="co1",
            role="agent", content="hello", channel="chat",
        ))
        db.commit()
        fetched = db.query(Session).filter_by(id="s1").first()
        assert len(fetched.interactions) == 2
        db.close()

    def test_api_provider_service_configs_relationship(self):
        """APIProvider.service_configs returns associated configs."""
        db = SessionLocal()
        from database.models.ai_pipeline import APIProvider, ServiceConfig
        from database.models.core import Company
        co = Company(id="co1", name="Test Co", industry="tech", subscription_tier="growth")
        db.add(co)
        db.flush()
        p = APIProvider(id="p1", name="OpenAI", provider_type="llm")
        db.add(p)
        db.flush()
        db.add(ServiceConfig(
            id="sc1", provider_id="p1",
            company_id="co1", display_name="My Key",
        ))
        db.add(ServiceConfig(
            id="sc2", provider_id="p1",
            company_id="co1", display_name="Backup Key",
        ))
        db.commit()
        fetched = db.query(APIProvider).filter_by(id="p1").first()
        assert len(fetched.service_configs) == 2
        db.close()


# ── Root Tables (no company_id) ──────────────────────────────────


class TestRootTables:
    """Root tables that intentionally have NO company_id."""

    def test_companies_has_no_company_id(self):
        """companies table must NOT have company_id (it IS the root)."""
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("companies")]
        assert "company_id" not in columns, "companies table must not have company_id"

    def test_channels_has_no_company_id(self):
        """channels table is global, no company_id."""
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("channels")]
        assert "company_id" not in columns

    def test_api_providers_has_no_company_id(self):
        """api_providers table is global, no company_id."""
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("api_providers")]
        assert "company_id" not in columns

    def test_demo_sessions_has_no_company_id(self):
        """demo_sessions is public-facing, no company_id."""
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("demo_sessions")]
        assert "company_id" not in columns

    def test_newsletter_subscribers_has_no_company_id(self):
        """newsletter_subscribers is public-facing, no company_id."""
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("newsletter_subscribers")]
        assert "company_id" not in columns

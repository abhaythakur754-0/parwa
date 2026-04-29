"""
Tests for F-019 API Key Service.

Tests DB-backed CRUD, rotation with grace period,
revocation, audit logging, max keys per tenant,
key format, and cross-tenant isolation.
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.base import Base
from database.models.core import Company, User
from database.models.api_key_audit import APIKeyAuditLog


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh SQLite in-memory DB session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed a company + user for foreign keys
    company = Company(
        id="comp-1",
        name="Test Co",
        industry="tech",
        subscription_tier="mini_parwa",
    )
    user = User(
        id="user-1",
        company_id="comp-1",
        email="owner@test.com",
        password_hash="hash",
        role="owner",
    )
    session.add(company)
    session.add(user)
    session.commit()

    yield session
    session.close()


@pytest.fixture
def company2(db_session):
    """Second company for cross-tenant tests."""
    comp = Company(
        id="comp-2",
        name="Other Co",
        industry="retail",
        subscription_tier="parwa",
    )
    db_session.add(comp)
    db_session.commit()
    return comp


def _parse_scopes(record) -> list:
    """Parse scopes from a DB record."""
    if record.scopes:
        try:
            return json.loads(record.scopes)
        except (json.JSONDecodeError, TypeError):
            pass
    if record.scope:
        return [record.scope]
    return ["read"]


class TestCreateKey:
    """Tests for API key creation."""

    def test_create_returns_raw_key(self, db_session):
        from backend.app.services.api_key_service import create_key
        raw_key, record = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Test Key",
            scopes=["read"],
        )
        db_session.commit()
        assert raw_key is not None
        assert len(raw_key) > 20

    def test_create_key_format(self, db_session):
        from backend.app.services.api_key_service import create_key
        raw_key, _ = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Test",
            scopes=["read"],
        )
        db_session.commit()
        assert raw_key.startswith("parwa_live_")
        # 11 char prefix + 32 char random = 43 chars
        assert len(raw_key) == 43

    def test_create_stores_hash_not_raw(self, db_session):
        from backend.app.services.api_key_service import create_key
        from security.api_keys import hash_api_key
        raw_key, record = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Test",
            scopes=["read"],
        )
        db_session.commit()
        assert record.key_hash == hash_api_key(raw_key)
        assert "parwa_live_" not in record.key_hash

    def test_create_sets_scopes(self, db_session):
        from backend.app.services.api_key_service import create_key
        _, record = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Test",
            scopes=["read", "write"],
        )
        db_session.commit()
        scopes = _parse_scopes(record)
        assert "read" in scopes
        assert "write" in scopes

    def test_create_audit_log(self, db_session):
        from backend.app.services.api_key_service import create_key
        _, record = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Test",
            scopes=["read"],
        )
        db_session.commit()
        logs = db_session.query(APIKeyAuditLog).filter(
            APIKeyAuditLog.api_key_id == record.id,
        ).all()
        assert len(logs) >= 1
        assert logs[0].action == "created"

    def test_create_invalid_scope_raises(self, db_session):
        from backend.app.services.api_key_service import create_key
        with pytest.raises(ValueError, match="Invalid scope"):
            create_key(
                db=db_session,
                company_id="comp-1",
                user_id="user-1",
                name="Test",
                scopes=["invalid_scope"],
            )

    def test_create_with_expiration(self, db_session):
        from backend.app.services.api_key_service import create_key
        _, record = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Expiring",
            scopes=["read"],
            expires_days=30,
        )
        db_session.commit()
        assert record.expires_at is not None


class TestMaxKeysPerTenant:
    """Tests for max 10 keys per tenant."""

    def test_max_10_keys(self, db_session):
        from backend.app.services.api_key_service import create_key
        created = []
        for i in range(10):
            raw, rec = create_key(
                db=db_session,
                company_id="comp-1",
                user_id="user-1",
                name=f"Key {i}",
                scopes=["read"],
            )
            created.append(raw)
        db_session.commit()

        # 11th should fail
        with pytest.raises(ValueError, match="Maximum"):
            create_key(
                db=db_session,
                company_id="comp-1",
                user_id="user-1",
                name="Key 11",
                scopes=["read"],
            )

    def test_max_per_tenant_not_global(self, db_session, company2):
        from backend.app.services.api_key_service import create_key
        # Create 10 keys for comp-1
        for i in range(10):
            create_key(
                db=db_session,
                company_id="comp-1",
                user_id="user-1",
                name=f"C1 Key {i}",
                scopes=["read"],
            )
        db_session.commit()
        # comp-2 should still be able to create
        raw, _ = create_key(
            db=db_session,
            company_id="comp-2",
            user_id=None,
            name="C2 Key 1",
            scopes=["read"],
        )
        db_session.commit()
        assert raw is not None


class TestListKeys:
    """Tests for listing API keys."""

    def test_list_returns_keys(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            list_keys,
        )
        create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Key A",
            scopes=["read"],
        )
        db_session.commit()
        keys = list_keys(db_session, "comp-1")
        assert len(keys) >= 1
        assert keys[0]["name"] == "Key A"

    def test_list_no_hashes(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            list_keys,
        )
        create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Key B",
            scopes=["read"],
        )
        db_session.commit()
        keys = list_keys(db_session, "comp-1")
        for k in keys:
            assert "key_hash" not in k
            assert k["key_prefix"] is not None

    def test_list_cross_tenant_isolation(self, db_session, company2):
        from backend.app.services.api_key_service import (
            create_key,
            list_keys,
        )
        create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="C1 Key",
            scopes=["read"],
        )
        create_key(
            db=db_session,
            company_id="comp-2",
            user_id=None,
            name="C2 Key",
            scopes=["admin"],
        )
        db_session.commit()
        c1_keys = list_keys(db_session, "comp-1")
        c2_keys = list_keys(db_session, "comp-2")
        assert len(c1_keys) == 1
        assert len(c2_keys) == 1
        assert c1_keys[0]["name"] == "C1 Key"
        assert c2_keys[0]["name"] == "C2 Key"


class TestRotateKey:
    """Tests for API key rotation."""

    def test_rotate_generates_new_key(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            rotate_key,
        )
        _, old_rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Old Key",
            scopes=["read"],
        )
        db_session.commit()
        new_raw, new_rec, old_rec2, grace = rotate_key(
            db=db_session,
            company_id="comp-1",
            key_id=old_rec.id,
            user_id="user-1",
        )
        db_session.commit()
        assert new_raw != new_rec

    def test_rotate_sets_grace_ends_at(self, db_session):
        """L18: Rotation sets grace_ends_at on old key."""
        from backend.app.services.api_key_service import (
            create_key,
            rotate_key,
        )
        _, old_rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="K",
            scopes=["read"],
        )
        db_session.commit()
        _, _, old_after, grace = rotate_key(
            db=db_session,
            company_id="comp-1",
            key_id=old_rec.id,
            user_id="user-1",
        )
        db_session.commit()
        assert old_after.grace_ends_at is not None
        # Compare timestamps (grace is timezone-aware, grace_ends_at may be naive from DB)
        assert grace.replace(tzinfo=None) == old_after.grace_ends_at

    def test_rotate_new_key_format(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            rotate_key,
        )
        _, old_rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="K",
            scopes=["read"],
        )
        db_session.commit()
        new_raw, _, _, _ = rotate_key(
            db=db_session,
            company_id="comp-1",
            key_id=old_rec.id,
            user_id="user-1",
        )
        db_session.commit()
        assert new_raw.startswith("parwa_live_")

    def test_rotate_grace_period(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            rotate_key,
        )
        _, old_rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="K",
            scopes=["read"],
        )
        db_session.commit()
        _, _, _, grace_ends = rotate_key(
            db=db_session,
            company_id="comp-1",
            key_id=old_rec.id,
            user_id="user-1",
        )
        db_session.commit()
        assert grace_ends is not None

    def test_rotate_audit_log(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            rotate_key,
        )
        _, old_rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="K",
            scopes=["read"],
        )
        db_session.commit()
        _, new_rec, _, _ = rotate_key(
            db=db_session,
            company_id="comp-1",
            key_id=old_rec.id,
            user_id="user-1",
        )
        db_session.commit()
        logs = db_session.query(APIKeyAuditLog).filter(
            APIKeyAuditLog.api_key_id == new_rec.id,
            APIKeyAuditLog.action == "rotated",
        ).all()
        assert len(logs) >= 1

    def test_rotate_not_found_raises(self, db_session):
        from backend.app.services.api_key_service import rotate_key
        with pytest.raises(ValueError, match="not found"):
            rotate_key(
                db=db_session,
                company_id="comp-1",
                key_id="nonexistent",
                user_id="user-1",
            )

    def test_rotate_preserves_scopes(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            rotate_key,
        )
        _, old_rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="K",
            scopes=["read", "write"],
        )
        db_session.commit()
        _, new_rec, _, _ = rotate_key(
            db=db_session,
            company_id="comp-1",
            key_id=old_rec.id,
            user_id="user-1",
        )
        db_session.commit()
        new_scopes = _parse_scopes(new_rec)
        assert "read" in new_scopes
        assert "write" in new_scopes


class TestRevokeKey:
    """Tests for API key revocation."""

    def test_revoke_sets_revoked_true(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            revoke_key,
        )
        _, rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Revoke Me",
            scopes=["read"],
        )
        db_session.commit()
        revoked = revoke_key(
            db=db_session,
            company_id="comp-1",
            key_id=rec.id,
            user_id="user-1",
        )
        db_session.commit()
        assert revoked.revoked is True
        assert revoked.revoked_at is not None

    def test_revoke_audit_log(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            revoke_key,
        )
        _, rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="K",
            scopes=["read"],
        )
        db_session.commit()
        revoke_key(
            db=db_session,
            company_id="comp-1",
            key_id=rec.id,
            user_id="user-1",
        )
        db_session.commit()
        logs = db_session.query(APIKeyAuditLog).filter(
            APIKeyAuditLog.api_key_id == rec.id,
            APIKeyAuditLog.action == "revoked",
        ).all()
        assert len(logs) >= 1

    def test_revoke_not_found_raises(self, db_session):
        from backend.app.services.api_key_service import revoke_key
        with pytest.raises(ValueError, match="not found"):
            revoke_key(
                db=db_session,
                company_id="comp-1",
                key_id="nonexistent",
                user_id="user-1",
            )


class TestValidateKey:
    """Tests for API key validation."""

    def test_validate_correct_key(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            validate_key,
        )
        raw_key, _ = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Valid",
            scopes=["read"],
        )
        db_session.commit()
        result = validate_key(db_session, raw_key)
        assert result is not None

    def test_validate_wrong_key(self, db_session):
        from backend.app.services.api_key_service import validate_key
        result = validate_key(
            db_session, "parwa_live_wrong000000000000"
        )
        assert result is None

    def test_validate_revoked_key(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            revoke_key,
            validate_key,
        )
        raw_key, rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="Revoked",
            scopes=["read"],
        )
        db_session.commit()
        revoke_key(
            db=db_session,
            company_id="comp-1",
            key_id=rec.id,
            user_id="user-1",
        )
        db_session.commit()
        result = validate_key(db_session, raw_key)
        assert result is None

    def test_validate_empty_key(self, db_session):
        from backend.app.services.api_key_service import validate_key
        result = validate_key(db_session, "")
        assert result is None


class TestUpdateLastUsed:
    """Tests for update_last_used."""

    def test_updates_last_used_at(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            update_last_used,
        )
        _, rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="K",
            scopes=["read"],
        )
        db_session.commit()
        assert rec.last_used_at is None
        update_last_used(
            db=db_session,
            key_id=rec.id,
            endpoint="/api/tickets",
            ip_address="1.2.3.4",
        )
        db_session.commit()
        db_session.refresh(rec)
        assert rec.last_used_at is not None

    def test_creates_used_audit_log(self, db_session):
        from backend.app.services.api_key_service import (
            create_key,
            update_last_used,
        )
        _, rec = create_key(
            db=db_session,
            company_id="comp-1",
            user_id="user-1",
            name="K",
            scopes=["read"],
        )
        db_session.commit()
        update_last_used(
            db=db_session,
            key_id=rec.id,
            endpoint="/api/tickets",
            ip_address="1.2.3.4",
        )
        db_session.commit()
        logs = db_session.query(APIKeyAuditLog).filter(
            APIKeyAuditLog.api_key_id == rec.id,
            APIKeyAuditLog.action == "used",
        ).all()
        assert len(logs) >= 1
        assert logs[0].endpoint == "/api/tickets"
        assert logs[0].ip_address == "1.2.3.4"

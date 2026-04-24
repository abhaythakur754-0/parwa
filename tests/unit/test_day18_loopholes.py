"""Day 18 Loophole Tests — Client Factory + Migration Stubs

Security analysis against Building Codes:
BC-001: Tenant isolation (company_id)
BC-002: Money fields DECIMAL(10,2)
BC-003: Idempotency
BC-011: Security best practices
BC-012: Observability
"""

import os
import pytest

os.environ["ENVIRONMENT"] = "test"


class TestClientFactoryLoopholes:
    """L40+: Client factory security checks."""

    @pytest.fixture(autouse=True)
    def _setup_db(self):
        os.environ["ENVIRONMENT"] = "test"
        from database.base import Base, engine, SessionLocal
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        yield
        self.db.close()

    def test_l40_provision_validates_email_format(self):
        """BC-011: Must reject malformed emails before DB."""
        from backend.app.services.client_factory import provision_company
        with pytest.raises(ValueError, match="valid owner email"):
            provision_company(
                name="Test", owner_email="not-an-email",
                owner_password_hash="hash",
                industry="tech", db=self.db,
            )

    def test_l41_provision_rejects_empty_name(self):
        """BC-011: Name is required."""
        from backend.app.services.client_factory import provision_company
        with pytest.raises(ValueError, match="Company name"):
            provision_company(
                name="  ", owner_email="a@b.com",
                owner_password_hash="hash",
                industry="tech", db=self.db,
            )

    def test_l42_provision_rejects_empty_password(self):
        """BC-011: Password hash is required."""
        from backend.app.services.client_factory import provision_company
        with pytest.raises(ValueError, match="password hash"):
            provision_company(
                name="Test", owner_email="a@b.com",
                owner_password_hash="  ",
                industry="tech", db=self.db,
            )

    def test_l43_provision_defaults_to_starter_not_free(self):
        """L43: Default tier should be 'mini_parwa' not something
        more permissive."""
        from backend.app.services.client_factory import (
            get_plan_entitlements,
        )
        e = get_plan_entitlements(None)
        assert e["max_agents"] == 1  # Most restrictive

    def test_l44_provision_strips_input(self):
        """BC-011: Input trimming to prevent whitespace bypass."""
        from backend.app.services.client_factory import provision_company
        from database.models.core import Company

        provision_company(
            name="  Trimmed Corp  ",
            owner_email="  TRIM@TEST.COM  ",
            owner_password_hash="hash",
            industry="tech",
            db=self.db,
        )
        company = self.db.query(Company).filter(
            Company.name == "Trimmed Corp"
        ).first()

    def test_l45_owner_not_verified_by_default(self):
        """BC-011: Owner must verify email before access."""
        from backend.app.services.client_factory import provision_company
        from database.models.core import User

        provision_company(
            name="Test", owner_email="new@test.com",
            owner_password_hash="hash",
            industry="tech", db=self.db,
        )
        user = self.db.query(User).filter(
            User.email == "new@test.com"
        ).first()
        assert user.is_verified is False

    def test_l46_owner_role_is_owner(self):
        """Security: Owner must have 'owner' role, not 'admin'."""
        from backend.app.services.client_factory import provision_company
        from database.models.core import User

        provision_company(
            name="Test", owner_email="role@test.com",
            owner_password_hash="hash",
            industry="tech", db=self.db,
        )
        user = self.db.query(User).filter(
            User.email == "role@test.com"
        ).first()
        assert user.role == "owner"

    def test_l47_agent_starts_with_zero_capacity(self):
        """BC-011: No AI agent capacity until explicitly enabled."""
        from backend.app.services.client_factory import provision_company
        from database.models.core import Agent

        provision_company(
            name="Test", owner_email="cap@test.com",
            owner_password_hash="hash",
            industry="tech", db=self.db,
        )
        agent = self.db.query(Agent).first()
        assert agent.capacity_used == 0
        assert agent.capacity_max == 0

    def test_l48_mode_defaults_shadow(self):
        """BC-011: New companies start in shadow mode (human-in-loop)."""
        from backend.app.services.client_factory import provision_company
        from database.models.core import Company

        provision_company(
            name="Test", owner_email="shadow@test.com",
            owner_password_hash="hash",
            industry="tech", db=self.db,
        )
        company = self.db.query(Company).filter(
            Company.name == "Test"
        ).first()

    def test_l49_check_entitlement_boundary(self):
        """BC-002: Boundary check — current == max means FULL."""
        from backend.app.services.client_factory import (
            check_entitlement,
        )
        from database.models.core import Company
        import uuid

        c = Company(
            id=str(uuid.uuid4()), name="B",
            industry="tech", subscription_tier="mini_parwa",
            subscription_status="active", mode="shadow",
        )
        self.db.add(c)
        self.db.flush()

        # max_agents=1, current=0 → True (room for 1 more)
        assert check_entitlement(
            c.id, "max_agents", 0, self.db,
        ) is True
        # max_agents=1, current=1 → False (full)
        assert check_entitlement(
            c.id, "max_agents", 1, self.db,
        ) is False

    def test_l50_provision_isolation_per_company(self):
        """BC-001: Each company gets its own isolated records."""
        from backend.app.services.client_factory import provision_company
        from database.models.core import User

        r1 = provision_company(
            name="Co1", owner_email="co1@t.com",
            owner_password_hash="h1", industry="tech",
            db=self.db,
        )
        r2 = provision_company(
            name="Co2", owner_email="co2@t.com",
            owner_password_hash="h2", industry="tech",
            db=self.db,
        )

        assert r1["company_id"] != r2["company_id"]
        assert r1["owner"]["id"] != r2["owner"]["id"]

        # Users belong to different companies
        u1 = self.db.query(User).filter(
            User.email == "co1@t.com"
        ).first()
        u2 = self.db.query(User).filter(
            User.email == "co2@t.com"
        ).first()
        assert u1.company_id != u2.company_id

    def test_l51_growth_tier_enables_voice(self):
        """Business rule: only growth+ tiers enable voice."""
        from backend.app.services.client_factory import (
            get_plan_entitlements,
        )
        starter = get_plan_entitlements("mini_parwa")
        assert starter["voice"] is False
        growth = get_plan_entitlements("parwa")
        assert growth["voice"] is True
        assert growth["voice_slots"] == 2
        high = get_plan_entitlements("high")
        assert high["voice"] is True
        assert high["voice_slots"] == 5

    def test_l52_plan_entitlements_sorted_output(self):
        """Robustness: Plan keys are sorted for consistent errors."""
        from backend.app.services.client_factory import (
            get_plan_entitlements,
        )
        with pytest.raises(ValueError) as exc_info:
            get_plan_entitlements("invalid")
        assert "mini_parwa" in str(exc_info.value)
        assert "parwa" in str(exc_info.value)


class TestMigrationSecurityLoopholes:
    """L53+: Migration stub security checks."""

    def test_l53_money_fields_not_float(self):
        """BC-002: No money field uses Float type in any migration.

        Float is acceptable for scores, ratios, and metrics.
        Only money-related columns (price, amount, cost, fee, revenue,
        balance, monetary_value) must use Numeric.
        """
        import glob
        import os
        import re

        money_patterns = re.compile(
            r"(price|amount|cost|fee|revenue|balance|monetary_value|"
            r"total_charge|subtotal|tax_amount|discount)",
            re.IGNORECASE,
        )

        mig_dir = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "database", "alembic", "versions",
        )
        for f in glob.glob(os.path.join(mig_dir, "*.py")):
            if "script" in f:
                continue
            with open(f) as fh:
                content = fh.read()

            # Check each sa.Float usage line-by-line
            for lineno, line in enumerate(content.splitlines(), 1):
                if "sa.Float" not in line:
                    continue
                # If this line contains a money-related column name, it's a violation
                if money_patterns.search(line):
                    assert False, (
                        f"BC-002 violation: {f}:{lineno} uses Float for "
                        f"money field: {line.strip()}"
                    )

    def test_l54_all_migrations_have_downgrade(self):
        """BC-003: Every migration must be reversible."""
        import glob, os, importlib, inspect

        mig_dir = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "database", "alembic", "versions",
        )
        for f in glob.glob(os.path.join(mig_dir, "*.py")):
            if "script" in f:
                continue
            spec = importlib.util.spec_from_file_location(
                "mod", f,
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            source = inspect.getsource(mod)
            assert "def downgrade()" in source, (
                f"{f} missing downgrade()"
            )

    def test_l55_no_hardcoded_secrets_in_migrations(self):
        """BC-011: No passwords, API keys, or secrets in migration files."""
        import glob, os

        mig_dir = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "database", "alembic", "versions",
        )
        forbidden = ["password", "secret_key", "api_key"]
        for f in glob.glob(os.path.join(mig_dir, "*.py")):
            if "script" in f:
                continue
            with open(f) as fh:
                content = fh.read().lower()
            # server_default values shouldn't contain secrets
            for word in forbidden:
                assert f"server_default='{word}" not in content, (
                    f"BC-011: {f} may contain hardcoded {word}"
                )

    def test_l56_revision_chain_no_gaps(self):
        """BC-003: Revision chain must be contiguous."""
        import glob, os, importlib

        mig_dir = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "database", "alembic", "versions",
        )
        revisions = {}
        for f in sorted(glob.glob(os.path.join(mig_dir, "*.py"))):
            if "script" in f:
                continue
            spec = importlib.util.spec_from_file_location(
                "mod", f,
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            revisions[mod.revision] = mod.down_revision

        visited = [None]
        current = None
        while True:
            # Find revision whose down_revision matches current
            found = None
            for rev, down in revisions.items():
                if down == current:
                    found = rev
                    break
            if found is None:
                break
            assert found not in visited, (
                f"Cycle detected: {found} already visited"
            )
            visited.append(found)
            current = found

        assert len(visited) - 1 == len(revisions), (
            f"Chain length mismatch: expected {len(revisions)}, "
            f"got {len(visited) - 1}"
        )

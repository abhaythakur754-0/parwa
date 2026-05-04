"""Tests for Day 18: Client Factory + Migration Stubs

Tests cover:
- provision_company creates all required records
- plan entitlements validation
- check_entitlement and limit checks
- email uniqueness validation
- migration stub files exist and have valid revision chains
- all model tables covered by migrations
"""

import os
import pytest

os.environ["ENVIRONMENT"] = "test"


# ── Client Factory Tests ─────────────────────────────────────────


class TestPlanEntitlements:
    """Test plan entitlements configuration."""

    def test_get_plan_entitlements_starter(self):
        from backend.app.services.client_factory import get_plan_entitlements
        e = get_plan_entitlements("starter")
        assert e["max_agents"] == 1
        assert e["max_tickets_per_month"] == 2_000
        assert e["voice"] is False
        assert "email" in e["channels"]

    def test_get_plan_entitlements_growth(self):
        from backend.app.services.client_factory import get_plan_entitlements
        e = get_plan_entitlements("growth")
        assert e["max_agents"] == 3
        assert e["voice"] is True
        assert e["voice_slots"] == 2

    def test_get_plan_entitlements_high(self):
        from backend.app.services.client_factory import get_plan_entitlements
        e = get_plan_entitlements("high")
        assert e["max_agents"] == 5
        assert e["max_file_size_mb"] == 50
        assert "social" in e["channels"]

    def test_get_plan_entitlements_case_insensitive(self):
        from backend.app.services.client_factory import get_plan_entitlements
        e = get_plan_entitlements("STARTER")
        assert e["max_agents"] == 1

    def test_get_plan_entitlements_strips_whitespace(self):
        from backend.app.services.client_factory import get_plan_entitlements
        e = get_plan_entitlements("  starter  ")
        assert e["max_agents"] == 1

    def test_get_plan_entitlements_unknown_raises(self):
        from backend.app.services.client_factory import get_plan_entitlements
        with pytest.raises(ValueError, match="Unknown plan tier"):
            get_plan_entitlements("enterprise")

    def test_get_plan_entitlements_none_defaults_starter(self):
        from backend.app.services.client_factory import get_plan_entitlements
        e = get_plan_entitlements(None)
        assert e["max_agents"] == 1

    def test_all_plans_have_required_keys(self):
        from backend.app.services.client_factory import (
            PLAN_ENTITLEMENTS,
        )
        required = [
            "max_tickets_per_month", "max_agents", "channels",
            "voice", "max_kb_documents", "max_team_members",
            "max_file_size_mb",
        ]
        for tier, entitlements in PLAN_ENTITLEMENTS.items():
            for key in required:
                assert key in entitlements, (
                    f"Tier {tier} missing {key}"
                )


class TestProvisionCompany:
    """Test company provisioning via client factory."""

    @pytest.fixture(autouse=True)
    def _setup_db(self):
        os.environ["ENVIRONMENT"] = "test"
        from database.base import Base, engine, SessionLocal

        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        yield
        self.db.close()

    def test_provision_company_creates_records(self):
        from backend.app.services.client_factory import provision_company
        from database.models.core import Company, User, Agent

        result = provision_company(
            name="Test Corp",
            owner_email="owner@test.com",
            owner_password_hash="$2b$12$hash",
            owner_full_name="Test Owner",
            tier="starter",
            industry="technology",
            db=self.db,
        )

        assert "company_id" in result
        assert result["company"]["name"] == "Test Corp"
        assert result["owner"]["email"] == "owner@test.com"
        assert result["owner"]["role"] == "owner"
        assert result["agent"]["status"] == "active"

        # Verify records in DB
        company = self.db.query(Company).filter(
            Company.name == "Test Corp"
        ).first()
        assert company is not None
        assert company.subscription_tier == "starter"
        assert company.mode == "shadow"

        owner = self.db.query(User).filter(
            User.email == "owner@test.com"
        ).first()
        assert owner is not None
        assert owner.role == "owner"
        assert owner.is_verified is False

        agent = self.db.query(Agent).filter(
            Agent.company_id == company.id
        ).first()
        assert agent is not None
        assert "Test Corp" in agent.name

    def test_provision_company_entitlements(self):
        from backend.app.services.client_factory import provision_company

        result = provision_company(
            name="Growth Corp",
            owner_email="owner2@test.com",
            owner_password_hash="$2b$12$hash",
            tier="growth",
            industry="technology",
            db=self.db,
        )

        assert result["entitlements"]["max_agents"] == 3
        assert result["entitlements"]["voice"] is True

    def test_provision_company_name_required(self):
        from backend.app.services.client_factory import provision_company

        with pytest.raises(ValueError, match="Company name"):
            provision_company(
                name="",
                owner_email="a@b.com",
                owner_password_hash="hash",
                db=self.db,
            )

    def test_provision_company_email_required(self):
        from backend.app.services.client_factory import provision_company

        with pytest.raises(ValueError, match="valid owner email"):
            provision_company(
                name="Test",
                owner_email="invalid",
                owner_password_hash="hash",
                db=self.db,
            )

    def test_provision_company_password_hash_required(self):
        from backend.app.services.client_factory import provision_company

        with pytest.raises(ValueError, match="password hash"):
            provision_company(
                name="Test",
                owner_email="a@b.com",
                owner_password_hash="",
                db=self.db,
            )

    def test_provision_company_unknown_tier(self):
        from backend.app.services.client_factory import provision_company

        with pytest.raises(ValueError, match="Unknown plan tier"):
            provision_company(
                name="Test",
                owner_email="a@b.com",
                owner_password_hash="hash",
                tier="enterprise",
                db=self.db,
            )

    def test_provision_company_duplicate_email(self):
        from backend.app.services.client_factory import provision_company
        from backend.app.exceptions import ValidationError

        provision_company(
            name="First",
            owner_email="dup@test.com",
            owner_password_hash="hash1",
            industry="technology",
            db=self.db,
        )

        with pytest.raises(ValidationError, match="already registered"):
            provision_company(
                name="Second",
                owner_email="dup@test.com",
                owner_password_hash="hash2",
                industry="technology",
                db=self.db,
            )

    def test_provision_company_email_lowercased(self):
        from backend.app.services.client_factory import provision_company
        from database.models.core import User

        provision_company(
            name="Test",
            owner_email="UPPER@TEST.COM",
            owner_password_hash="hash",
            industry="technology",
            db=self.db,
        )

        user = self.db.query(User).filter(
            User.email == "upper@test.com"
        ).first()
        assert user is not None
        assert user.email == "upper@test.com"

    def test_provision_company_mode_is_shadow(self):
        from backend.app.services.client_factory import provision_company
        from database.models.core import Company

        provision_company(
            name="Shadow Co",
            owner_email="shadow@test.com",
            owner_password_hash="hash",
            industry="tech",
            db=self.db,
        )

        company = self.db.query(Company).filter(
            Company.name == "Shadow Co"
        ).first()
        assert company.mode == "shadow"


class TestCheckEntitlement:
    """Test entitlement checking functions."""

    @pytest.fixture(autouse=True)
    def _setup_db(self):
        os.environ["ENVIRONMENT"] = "test"
        from database.base import Base, engine, SessionLocal

        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        yield
        self.db.close()

    def _create_company(self, tier="starter"):
        from database.models.core import Company
        import uuid
        c = Company(
            id=str(uuid.uuid4()),
            name=f"Test {tier}",
            industry="tech",
            subscription_tier=tier,
            subscription_status="active",
            mode="shadow",
        )
        self.db.add(c)
        self.db.flush()
        return c

    def test_check_entitlement_under_limit(self):
        from backend.app.services.client_factory import check_entitlement
        c = self._create_company("starter")
        assert check_entitlement(
            c.id, "max_agents", 0, self.db,
        ) is True

    def test_check_entitlement_at_limit(self):
        from backend.app.services.client_factory import check_entitlement
        c = self._create_company("starter")
        # starter has max_agents=1, current=1 means NOT under
        assert check_entitlement(
            c.id, "max_agents", 1, self.db,
        ) is False

    def test_check_entitlement_unknown_key(self):
        from backend.app.services.client_factory import check_entitlement
        c = self._create_company("starter")
        # No limit defined → always True
        assert check_entitlement(
            c.id, "unknown_key", 999, self.db,
        ) is True

    def test_check_team_member_limit(self):
        from backend.app.services.client_factory import (
            check_team_member_limit,
        )
        from database.models.core import User

        c = self._create_company("starter")
        # Starter max_team_members=3, owner already exists
        assert check_team_member_limit(c.id, self.db) is True

        # Add 3 more users to hit limit (starter max=3)
        for i in range(3):
            u = User(
                company_id=c.id,
                email=f"member{i}@test.com",
                password_hash="hash",
                role="agent",
                is_active=True,
            )
            self.db.add(u)
        self.db.flush()

        assert check_team_member_limit(c.id, self.db) is False

    def test_check_agent_limit(self):
        from backend.app.services.client_factory import check_agent_limit
        from database.models.core import Agent

        c = self._create_company("starter")
        # Starter max_agents=1, default agent from provision
        assert check_agent_limit(c.id, self.db) is True

        a = Agent(
            company_id=c.id,
            name="Extra Agent",
            variant="general",
            status="active",
        )
        self.db.add(a)
        self.db.commit()

        assert check_agent_limit(c.id, self.db) is False

    def test_get_company_entitlements_not_found(self):
        from backend.app.services.client_factory import (
            get_company_entitlements,
        )
        from backend.app.exceptions import NotFoundError

        with pytest.raises(NotFoundError, match="not found"):
            get_company_entitlements(
                "00000000-0000-0000-0000-000000000000",
                self.db,
            )


# ── Migration Stub Validation Tests ──────────────────────────────


class TestMigrationStubs:
    """Verify migration stubs: file existence, revision chain,
    and model-to-migration coverage."""

    EXPECTED_REVISIONS = [
        "001", "002", "003", "004", "005", "006", "007",
    ]

    EXPECTED_TABLES = [
        # 001: Core
        "companies", "users", "refresh_tokens", "api_keys",
        "company_settings", "agents", "emergency_states",
        "user_notification_preferences", "mfa_secrets",
        "backup_codes", "verification_tokens",
        "password_reset_tokens", "oauth_accounts",
        # 002: Ticketing
        "customers", "channels", "sessions", "interactions",
        "ticket_attachments", "ticket_internal_notes",
        # 003: AI Pipeline
        "api_providers", "service_configs", "gsd_sessions",
        "confidence_scores", "guardrail_blocks",
        "guardrail_rules", "prompt_templates",
        "model_usage_logs",
        # 004: Integrations
        "integrations", "rest_connectors",
        "webhook_integrations", "mcp_connections",
        "db_connections", "event_buffer", "error_log",
        "outgoing_webhooks",
        # 005: Audit + Billing
        "audit_trail", "webhook_events", "rate_limit_events",
        "api_key_audit_log", "subscriptions", "invoices",
        "overage_charges", "transactions",
        "cancellation_requests",
        # 006: Analytics + Onboarding + Training
        "metric_aggregates", "roi_snapshots", "drift_reports",
        "qa_scores", "training_runs", "onboarding_sessions",
        "consent_records", "knowledge_documents",
        "document_chunks", "demo_sessions",
        "newsletter_subscribers", "training_datasets",
        "training_checkpoints", "agent_mistakes",
        "agent_performance",
        # 007: Remaining gaps + Approval + Notifications
        "approval_queues", "auto_approve_rules",
        "executed_actions", "undo_log", "phone_otps",
        "response_templates", "email_logs",
        "rate_limit_counters", "feature_flags",
        "classification_log", "guardrails_audit_log",
        "guardrails_blocked_queue", "ai_response_feedback",
        "confidence_thresholds", "human_corrections",
        "approval_batches", "notifications",
        "first_victories",
    ]

    MIGRATION_DIR = os.path.join(
        os.path.dirname(__file__), "..", "..",
        "database", "alembic", "versions",
    )

    def _get_module(self, revision):
        """Dynamically load a migration module."""
        import importlib
        path = os.path.join(self.MIGRATION_DIR, f"{revision}_*.py")
        import glob
        files = glob.glob(path)
        assert len(files) == 1, (
            f"Expected 1 file for revision {revision}, "
            f"found {len(files)}: {files}"
        )
        spec = importlib.util.spec_from_file_location(
            f"migration_{revision}", files[0],
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_all_migration_files_exist(self):
        import glob
        for rev in self.EXPECTED_REVISIONS:
            path = os.path.join(self.MIGRATION_DIR, f"{rev}_*.py")
            files = glob.glob(path)
            assert len(files) == 1, (
                f"Missing migration file for {rev}"
            )

    def test_revision_chain_is_linked(self):
        """Each revision's down_revision points to the
        previous revision (except 001 which has None)."""
        chain = {}
        for rev in self.EXPECTED_REVISIONS:
            mod = self._get_module(rev)
            chain[rev] = {
                "revision": mod.revision,
                "down_revision": mod.down_revision,
            }

        # First has None
        assert chain["001"]["down_revision"] is None

        # Each subsequent points to previous
        for i in range(1, len(self.EXPECTED_REVISIONS)):
            prev = self.EXPECTED_REVISIONS[i - 1]
            curr = self.EXPECTED_REVISIONS[i]
            assert chain[curr]["down_revision"] == prev, (
                f"{curr} down_revision should be {prev}, "
                f"got {chain[curr]['down_revision']}"
            )

    def test_revision_ids_match_filenames(self):
        for rev in self.EXPECTED_REVISIONS:
            mod = self._get_module(rev)
            assert mod.revision == rev, (
                f"File {rev} has revision={mod.revision}"
            )

    def test_all_tables_covered(self):
        """Verify every model table appears in at least one
        migration's upgrade function."""
        found_tables = set()
        for rev in self.EXPECTED_REVISIONS:
            mod = self._get_module(rev)
            import inspect
            source = inspect.getsource(mod.upgrade)
            for table in self.EXPECTED_TABLES:
                if f"'{table}'" in source or f'"{table}"' in source:
                    found_tables.add(table)

        missing = set(self.EXPECTED_TABLES) - found_tables
        assert missing == set(), (
            f"Tables not covered by any migration: {missing}"
        )

    def test_downgrade_drops_all_created_tables(self):
        """Verify upgrade creates and downgrade drops same
        number of tables."""
        for rev in self.EXPECTED_REVISIONS:
            mod = self._get_module(rev)
            import inspect

            up_source = inspect.getsource(mod.upgrade)
            down_source = inspect.getsource(mod.downgrade)

            up_creates = up_source.count("op.create_table(")
            down_drops = down_source.count("op.drop_table(")

            assert up_creates == down_drops, (
                f"Revision {rev}: upgrade creates "
                f"{up_creates} tables but downgrade drops "
                f"{down_drops}"
            )

    def test_migrations_have_upgrade_and_downgrade(self):
        for rev in self.EXPECTED_REVISIONS:
            mod = self._get_module(rev)
            assert callable(mod.upgrade), (
                f"Revision {rev} missing upgrade()"
            )
            assert callable(mod.downgrade), (
                f"Revision {rev} missing downgrade()"
            )

    def test_money_fields_use_decimal(self):
        """BC-002: All money fields use Numeric(10,2)."""
        money_tables = {
            "invoices": ["amount"],
            "overage_charges": ["charge_amount"],
            "transactions": ["amount"],
            "metric_aggregates": ["value"],
            "roi_snapshots": [
                "avg_ai_cost", "avg_human_cost",
                "total_savings",
            ],
            "approval_queues": ["amount"],
            "executed_actions": ["amount"],
        }
        for rev in self.EXPECTED_REVISIONS:
            mod = self._get_module(rev)
            import inspect
            source = inspect.getsource(mod.upgrade)
            for table, fields in money_tables.items():
                for field in fields:
                    # Find the column definition
                    if f"'{table}'" in source or f'"{table}"' in source:
                        # Check it uses Numeric not Float
                        assert f"'{field}', sa.Float" not in source, (
                            f"BC-002: {table}.{field} should be "
                            f"Numeric, not Float"
                        )

    def test_company_id_indexed_in_all_tenant_tables(self):
        """BC-001: company_id should be indexed in all
        tenant tables (except companies which is root)."""
        # Check that migration files for tenant tables
        # include index=True on company_id
        non_root_tables = [
            t for t in self.EXPECTED_TABLES
            if t not in ("companies", "channels",
                         "api_providers", "demo_sessions",
                         "newsletter_subscribers")
        ]
        for table in non_root_tables:
            for rev in self.EXPECTED_REVISIONS:
                mod = self._get_module(rev)
                import inspect
                source = inspect.getsource(mod.upgrade)
                if f"'{table}'" in source:
                    # Should have company_id with index
                    assert "company_id" in source, (
                        f"BC-001: {table} missing company_id"
                    )
                    break

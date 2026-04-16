"""
PARWA Agent Models (Week 14 Day 4 — F-095, F-096)

SQLAlchemy models for AI agent provisioning and dynamic instruction
management. Covers agent lifecycle, setup tracking, version-controlled
instruction sets, A/B testing, and ticket-to-variant assignments.

Tables:
- Agent: AI agent instances with specialty, channels, permissions
- AgentSetupLog: Step-by-step agent setup progress tracking
- InstructionSet: Versioned behavioral instruction collections
- InstructionVersion: Historical instruction versions
- InstructionABTest: A/B tests between two instruction sets
- InstructionABAssignment: Per-ticket A/B variant assignments

Building Codes: BC-001 (multi-tenant), BC-007 (AI model),
               BC-008 (state management), BC-009 (approval)
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Integer, Numeric,
    String, Text, ForeignKey,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enum-like value sets (used by CHECK constraints) ────────────

_AGENT_STATUSES = (
    "'initializing','training','active','paused','deprovisioned','error'"
)
_SETUP_STEP_STATUSES = "'pending','in_progress','completed','failed'"
_INSTRUCTION_STATUSES = "'draft','active','archived'"
_AB_TEST_STATUSES = "'running','completed','cancelled'"
_AB_VARIANTS = "'A','B'"


# ── Agent ───────────────────────────────────────────────────────

class Agent(Base):
    """AI agent instance within a tenant (company).

    Represents a provisioned AI support agent with a defined specialty,
    channel configuration, and permission set. The agent lifecycle
    flows through: initializing → training → active → paused/deprovisioned/error.

    BC-001: Scoped by company_id.
    BC-007: AI model configuration via base_model, model_checkpoint_id.
    BC-009: Financial actions flagged for approval.
    """
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(200), nullable=False)
    # Specialty: billing, returns, technical, general, sales,
    #            onboarding, vip, feedback, custom
    specialty = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    # initializing → training → active → paused/deprovisioned/error
    status = Column(String(20), nullable=False, default="initializing")
    # JSON: {"channels": ["chat", "email", "sms"], "config": {...}}
    channels = Column(Text, default="{}")
    # JSON: {"level": "standard", "permissions": ["read_tickets", ...]}
    permissions = Column(Text, default="{}")
    # AI model references
    model_checkpoint_id = Column(String(36), nullable=True)
    base_model = Column(String(100), nullable=True)
    # Audit
    created_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    activated_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    # ── Relationships ──
    setup_logs = relationship(
        "AgentSetupLog", back_populates="agent",
        cascade="all, delete-orphan",
        order_by="AgentSetupLog.created_at",
    )
    instruction_sets = relationship(
        "InstructionSet", back_populates="agent",
        cascade="all, delete-orphan",
    )
    ab_tests = relationship(
        "InstructionABTest", back_populates="agent",
        cascade="all, delete-orphan",
    )
    creator = relationship("User", foreign_keys=[created_by])
    company = relationship("Company")

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_AGENT_STATUSES})",
            name="ck_agent_status",
        ),
        {"schema": None},
    )


# ── Agent Setup Log ─────────────────────────────────────────────

class AgentSetupLog(Base):
    """Tracks each step of the agent setup process.

    Setup steps include: configuration, training, integration_setup,
    permission_config, testing, activation. Each step can succeed or
    fail independently.

    BC-001: Scoped by company_id.
    BC-008: State management for setup progress.
    """
    __tablename__ = "agent_setup_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Setup step name: configuration, training, integration_setup,
    #                   permission_config, testing, activation
    step = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    # JSON: step-specific configuration data
    configuration = Column(Text, default="{}")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    completed_at = Column(DateTime, nullable=True)

    # ── Relationships ──
    agent = relationship("Agent", back_populates="setup_logs")

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_SETUP_STEP_STATUSES})",
            name="ck_agent_setup_log_status",
        ),
        {"schema": None},
    )


# ── Instruction Set ─────────────────────────────────────────────

class InstructionSet(Base):
    """Versioned collection of behavioral instructions for an agent.

    Each instruction set contains behavioral rules, tone guidelines,
    escalation triggers, response templates, and confidence thresholds.
    Sets go through draft → active → archived lifecycle.

    Publishing an instruction set creates a new InstructionVersion
    entry and the version number increments. Only one version per
    agent can be active at a time (unless an A/B test is running).

    BC-001: Scoped by company_id.
    BC-007: AI model behavioral instructions.
    BC-008: Version-controlled state management.
    """
    __tablename__ = "instruction_sets"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name = Column(String(200), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    # draft → active → archived
    status = Column(String(20), nullable=False, default="draft")
    # JSON: behavioral rules, tone guidelines, escalation triggers,
    #       response templates, confidence thresholds
    instructions = Column(Text, default="{}")
    is_default = Column(Boolean, nullable=False, default=False)
    created_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_at = Column(DateTime, nullable=True)
    change_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())

    # ── Relationships ──
    versions = relationship(
        "InstructionVersion", back_populates="instruction_set",
        cascade="all, delete-orphan",
        order_by="InstructionVersion.version.desc()",
    )
    agent = relationship("Agent", back_populates="instruction_sets")
    creator = relationship("User", foreign_keys=[created_by])
    publisher = relationship("User", foreign_keys=[published_by])

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_INSTRUCTION_STATUSES})",
            name="ck_instruction_set_status",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_instruction_set_version_positive",
        ),
        {"schema": None},
    )


# ── Instruction Version ─────────────────────────────────────────

class InstructionVersion(Base):
    """Historical version of an instruction set.

    Created each time an instruction set is published. Stores a
    snapshot of the instructions JSON and a change summary. Enables
    rollback to previous versions by re-publishing the snapshot.

    BC-007: AI model version tracking.
    BC-008: Full version history with change summaries.
    """
    __tablename__ = "instruction_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    set_id = Column(
        String(36),
        ForeignKey("instruction_sets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    version = Column(Integer, nullable=False)
    # Full JSON snapshot of instructions at this version
    instructions = Column(Text, nullable=False)
    change_summary = Column(Text, nullable=True)
    published_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_at = Column(DateTime, default=lambda: datetime.utcnow())
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # ── Relationships ──
    instruction_set = relationship(
        "InstructionSet", back_populates="versions",
    )
    publisher = relationship("User", foreign_keys=[published_by])

    __table_args__ = (
        CheckConstraint(
            "version >= 1",
            name="ck_instruction_version_positive",
        ),
        {"schema": None},
    )


# ── Instruction A/B Test ────────────────────────────────────────

class InstructionABTest(Base):
    """A/B test comparing two instruction sets for an agent.

    Routes tickets deterministically to variant A or B based on the
    configured traffic split. Tracks CSAT and resolution metrics per
    variant. Auto-completes when statistical significance is reached
    (p < 0.05 with min 100 tickets per variant) or manually stopped.

    Only one active A/B test per agent at a time (HTTP 409 on duplicate).

    BC-001: Scoped by company_id.
    BC-007: AI model optimization via testing.
    BC-008: State management for test lifecycle.
    """
    __tablename__ = "instruction_ab_tests"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    set_a_id = Column(
        String(36),
        ForeignKey("instruction_sets.id", ondelete="SET NULL"),
        nullable=False,
    )
    set_b_id = Column(
        String(36),
        ForeignKey("instruction_sets.id", ondelete="SET NULL"),
        nullable=False,
    )
    # Traffic split percentage for variant A (0-100)
    traffic_split = Column(Integer, nullable=False, default=50)
    success_metric = Column(
        String(50), nullable=False, default="csat",
    )
    duration_days = Column(Integer, nullable=False, default=14)
    # running → completed → cancelled
    status = Column(String(20), nullable=False, default="running")
    winner_id = Column(
        String(36),
        ForeignKey("instruction_sets.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Metrics — variant A
    tickets_a = Column(Integer, nullable=False, default=0)
    csat_a = Column(Numeric(5, 4), nullable=True)
    resolution_a = Column(Numeric(5, 4), nullable=True)
    # Metrics — variant B
    tickets_b = Column(Integer, nullable=False, default=0)
    csat_b = Column(Numeric(5, 4), nullable=True)
    resolution_b = Column(Numeric(5, 4), nullable=True)
    # Timestamps
    started_at = Column(DateTime, default=lambda: datetime.utcnow())
    ended_at = Column(DateTime, nullable=True)

    # ── Relationships ──
    agent = relationship("Agent", back_populates="ab_tests")
    set_a = relationship(
        "InstructionSet", foreign_keys=[set_a_id],
    )
    set_b = relationship(
        "InstructionSet", foreign_keys=[set_b_id],
    )
    winner = relationship("InstructionSet", foreign_keys=[winner_id])
    assignments = relationship(
        "InstructionABAssignment", back_populates="ab_test",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_AB_TEST_STATUSES})",
            name="ck_instruction_ab_test_status",
        ),
        CheckConstraint(
            "traffic_split >= 0 AND traffic_split <= 100",
            name="ck_instruction_ab_test_traffic_split",
        ),
        CheckConstraint(
            "tickets_a >= 0 AND tickets_b >= 0",
            name="ck_instruction_ab_test_tickets_nonneg",
        ),
        CheckConstraint(
            "duration_days >= 1",
            name="ck_instruction_ab_test_duration_positive",
        ),
        {"schema": None},
    )


# ── Instruction A/B Assignment ──────────────────────────────────

class InstructionABAssignment(Base):
    """Per-ticket A/B variant assignment.

    Records which variant (A or B) a ticket was assigned to during
    an A/B test. Used for deterministic routing and metric tracking.

    BC-001: Scoped via ab_test → company.
    BC-008: State management for assignment tracking.
    """
    __tablename__ = "instruction_ab_assignments"

    id = Column(String(36), primary_key=True, default=_uuid)
    test_id = Column(
        String(36),
        ForeignKey("instruction_ab_tests.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    ticket_id = Column(String(36), nullable=False, index=True)
    # A or B
    variant = Column(String(1), nullable=False)
    # The actual instruction set used for this variant
    set_id = Column(
        String(36),
        ForeignKey("instruction_sets.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Outcome metrics (filled after ticket resolution)
    csat_score = Column(Numeric(3, 2), nullable=True)
    resolved = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    # ── Relationships ──
    ab_test = relationship(
        "InstructionABTest", back_populates="assignments",
    )
    instruction_set = relationship("InstructionSet")

    __table_args__ = (
        CheckConstraint(
            f"variant IN ({_AB_VARIANTS})",
            name="ck_instruction_ab_assignment_variant",
        ),
        {"schema": None},
    )

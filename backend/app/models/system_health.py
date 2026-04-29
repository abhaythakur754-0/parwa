"""
PARWA System Health Models (Week 14 Day 2 — Jarvis Command Center)

SQLAlchemy models for the Jarvis Command Center operational features:
- SystemHealthSnapshot: Periodic health snapshots per subsystem
- SystemIncident: State transitions (healthy→degraded→unhealthy)
- ErrorLog: Application error entries for the Error Panel (F-091)
- TrainingDataPoint: Training data from errors (F-092 Train from Error)
- QuickCommandConfig: Per-tenant quick command customization (F-090)

All models use UUID strings as primary keys, consistent with the
PARWA pattern established in database/models/jarvis.py.

Based on: JARVIS_ROADMAP.md v4.0, PARWA_Building_Codes_v1.md
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Integer, String, Text,
)

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enum-like value sets (used by CHECK constraints) ────────────

_HEALTH_STATUSES = "'healthy','degraded','unhealthy','unknown'"
_INCIDENT_SEVERITIES = "'low','medium','high','critical'"
_INCIDENT_STATUSES = "'detected','investigating','resolved','dismissed'"
_ERROR_SEVERITIES = "'debug','info','warning','error','critical'"
_TRAINING_STATUSES = (
    "'create','queued_for_review','approved','rejected','in_dataset','archived'"
)
_TRAINING_SOURCES = "'error_auto','error_manual','feedback','correction'"
_REVIEW_ACTIONS = "'approved','rejected','needs_revision'"
_QUICK_COMMAND_RISK_LEVELS = "'low','medium','high','critical'"


# ── System Health Snapshot ────────────────────────────────────────

class SystemHealthSnapshot(Base):
    __tablename__ = "system_health_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), nullable=False, index=True)
    subsystem = Column(String(100), nullable=False, index=True)
    # 'healthy', 'degraded', 'unhealthy', 'unknown'
    status = Column(String(20), nullable=False)
    latency_ms = Column(Integer, nullable=True)
    # Extra data: provider details, queue depths, etc.
    metadata_json = Column(Text, default="{}")
    recorded_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_HEALTH_STATUSES})",
            name="ck_health_snapshot_status",
        ),
        {"schema": None},
    )


# ── System Incident ──────────────────────────────────────────────

class SystemIncident(Base):
    __tablename__ = "system_incidents"

    id = Column(String(36), primary_key=True, default=_uuid)
    subsystem = Column(String(100), nullable=False, index=True)
    # 'low', 'medium', 'high', 'critical'
    severity = Column(String(20), nullable=False, default="medium")
    # 'detected', 'investigating', 'resolved', 'dismissed'
    status = Column(String(20), nullable=False, default="detected")
    description = Column(Text, nullable=True)
    detected_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        nullable=False,
        index=True,
    )
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"severity IN ({_INCIDENT_SEVERITIES})",
            name="ck_incident_severity",
        ),
        CheckConstraint(
            f"status IN ({_INCIDENT_STATUSES})",
            name="ck_incident_status",
        ),
        {"schema": None},
    )


# ── Error Log ────────────────────────────────────────────────────

class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), nullable=False, index=True)
    error_type = Column(String(200), nullable=False, index=True)
    message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    # 'debug', 'info', 'warning', 'error', 'critical'
    severity = Column(String(20), nullable=False, default="error")
    subsystem = Column(String(100), nullable=True, index=True)
    affected_ticket_id = Column(String(36), nullable=True, index=True)
    affected_agent_id = Column(String(36), nullable=True)
    # Soft delete — preserves in logs
    dismissed = Column(Boolean, nullable=False, default=False)
    dismissed_by = Column(String(36), nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            f"severity IN ({_ERROR_SEVERITIES})",
            name="ck_error_log_severity",
        ),
        {"schema": None},
    )


# ── Training Data Point ──────────────────────────────────────────

class TrainingDataPoint(Base):
    __tablename__ = "training_data_points"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), nullable=False, index=True)
    error_id = Column(String(36), nullable=True, index=True)
    ticket_id = Column(String(36), nullable=True, index=True)
    input_context = Column(Text, nullable=True)
    ai_response = Column(Text, nullable=True)
    expected_response = Column(Text, nullable=True)
    correction_notes = Column(Text, nullable=True)
    intent_label = Column(String(200), nullable=True)
    # 'error_auto', 'error_manual', 'feedback', 'correction'
    source = Column(String(50), nullable=False, default="error_auto")
    # 'create', 'queued_for_review', 'approved', 'rejected', 'in_dataset', 'archived'
    status = Column(String(30), nullable=False, default="queued_for_review")
    created_by = Column(String(36), nullable=True)
    reviewed_by = Column(String(36), nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.utcnow(),
        nullable=False,
        index=True,
    )
    reviewed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"source IN ({_TRAINING_SOURCES})",
            name="ck_training_source",
        ),
        CheckConstraint(
            f"status IN ({_TRAINING_STATUSES})",
            name="ck_training_status",
        ),
        {"schema": None},
    )


# ── Quick Command Config ─────────────────────────────────────────

class QuickCommandConfig(Base):
    __tablename__ = "quick_command_configs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), nullable=False, index=True)
    command_id = Column(String(100), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    custom_label = Column(String(200), nullable=True)
    custom_params_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.utcnow(), nullable=False,
    )

    __table_args__ = (
        {"schema": None},
    )

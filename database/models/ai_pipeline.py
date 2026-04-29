"""
AI Pipeline Models: gsd_sessions, confidence_scores, guardrail_blocks,
guardrail_rules, prompt_templates, model_usage_logs, api_providers,
service_configs.

Source: CORRECTED_PARWA_Complete_Backend_Documentation.md
BC-001: Tables with company_data have company_id.
api_providers is global (no company_id).
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from database.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class APIProvider(Base):
    __tablename__ = "api_providers"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False, unique=True)
    # llm, payment, email, sms, voice
    provider_type = Column(String(50), nullable=False)
    description = Column(Text)
    required_fields = Column(Text, default="[]")
    optional_fields = Column(Text, default="[]")
    default_endpoint = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    service_configs = relationship(
        "ServiceConfig",
        back_populates="provider",
    )


class ServiceConfig(Base):
    __tablename__ = "service_configs"

    id = Column(String(36), primary_key=True, default=_uuid)
    provider_id = Column(String(36), ForeignKey("api_providers.id"))
    company_id = Column(
        String(36),
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )
    display_name = Column(String(255))
    api_key_encrypted = Column(Text)
    api_secret_encrypted = Column(Text)
    endpoint = Column(String(255))
    settings = Column(Text, default="{}")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

    provider = relationship("APIProvider", back_populates="service_configs")


class GSDSession(Base):
    __tablename__ = "gsd_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("tickets.id"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_step = Column(String(100), nullable=False)
    state_data = Column(Text, default="{}")
    status = Column(String(50), default="in_progress")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class ConfidenceScore(Base):
    __tablename__ = "confidence_scores"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("tickets.id"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    overall_score = Column(Numeric(5, 2), nullable=False)
    retrieval_score = Column(Numeric(5, 2))
    intent_score = Column(Numeric(5, 2))
    sentiment_score = Column(Numeric(5, 2))
    context_score = Column(Numeric(5, 2))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class GuardrailBlock(Base):
    __tablename__ = "guardrail_blocks"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("tickets.id"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # harmful, off_topic, hallucination, policy
    block_type = Column(String(50), nullable=False)
    original_response = Column(Text)
    block_reason = Column(Text)
    severity = Column(String(20), default="medium")
    status = Column(String(50), default="pending_review")
    reviewed_by = Column(String(36), ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class GuardrailRule(Base):
    __tablename__ = "guardrail_rules"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    rule_type = Column(String(50), nullable=False)
    pattern = Column(Text, nullable=False)
    action = Column(String(50), nullable=False, default="block")
    severity = Column(String(20), default="medium")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    intent_type = Column(String(100))
    template_text = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())


class ModelUsageLog(Base):
    __tablename__ = "model_usage_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(36), ForeignKey("tickets.id"))
    provider_name = Column(String(100), nullable=False)
    model_name = Column(String(100), nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer)
    status = Column(String(50), nullable=False)
    error_message = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())

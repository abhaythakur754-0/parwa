"""SQLAlchemy models for PARWA backend."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, Float
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    tenant_id = Column(String, index=True, nullable=True)
    role = Column(String, default="owner")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    industry = Column(String, nullable=True)
    onboarding_step = Column(Integer, default=0)
    onboarding_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIVariant(Base):
    __tablename__ = "ai_variants"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    variant_type = Column(String, nullable=False)  # mini, parwa, parwa_high
    status = Column(String, default="active")  # active, paused, scheduled_removal
    ticket_limit = Column(Integer, default=100)
    tickets_used = Column(Integer, default=0)
    ai_pipeline_steps = Column(Text, nullable=True)  # JSON string
    concurrent_ai = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IntegrationCredential(Base):
    __tablename__ = "integration_credentials"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    integration_id = Column(String, nullable=False)
    integration_name = Column(String, nullable=False)
    auth_type = Column(String, nullable=False)  # bearer, header, query, basic, oauth2
    encrypted_data = Column(Text, nullable=False)  # AES-256-GCM encrypted
    status = Column(String, default="active")  # active, disconnected, error
    last_tested_at = Column(DateTime, nullable=True)
    last_4_chars = Column(String, nullable=True)
    rotated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomConnector(Base):
    __tablename__ = "custom_connectors"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    auth_type = Column(String, nullable=False)
    encrypted_auth = Column(Text, nullable=True)
    actions = Column(Text, nullable=True)  # JSON string of action definitions
    source = Column(String, default="custom")
    status = Column(String, default="active")
    test_endpoint = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    action = Column(String, nullable=False)
    actor = Column(String, nullable=True)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    details = Column(Text, nullable=True)  # JSON string
    severity = Column(String, default="info")  # info, warning, error, critical
    checksum = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    category = Column(String, nullable=True)
    severity = Column(String, default="info")
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    action_url = Column(String, nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class FAQEntry(Base):
    __tablename__ = "faq_entries"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KBDocument(Base):
    __tablename__ = "kb_documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    chunk_count = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending, processing, ready, error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OnboardingState(Base):
    __tablename__ = "onboarding_states"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    current_step = Column(Integer, default=0)
    industry = Column(String, nullable=True)
    variant = Column(String, nullable=True)
    legal_accepted = Column(Boolean, default=False)
    integrations = Column(Text, nullable=True)  # JSON array of integration IDs
    kb_uploaded = Column(Boolean, default=False)
    ai_configured = Column(Boolean, default=False)
    payment_done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

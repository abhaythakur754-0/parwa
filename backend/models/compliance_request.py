import uuid
import datetime
import enum
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from backend.app.database import Base

class ComplianceRequestType(str, enum.Enum):
    gdpr_export = "gdpr_export"
    gdpr_delete = "gdpr_delete"
    tcpa_optout = "tcpa_optout"
    hipaa_access = "hipaa_access"

class ComplianceRequestStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class ComplianceRequest(Base):
    """
    Model for GDPR/TCPA data requests from clients.
    """
    __tablename__ = "compliance_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    request_type = Column(Enum(ComplianceRequestType, native_enum=False), nullable=False)
    customer_email = Column(String, nullable=False)
    status = Column(Enum(ComplianceRequestStatus, native_enum=False), nullable=False, default=ComplianceRequestStatus.pending)
    requested_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # result_url must be a pre-signed URL (not a permanent link) - noting expiry requirement
    result_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    def is_complete(self) -> bool:
        """Returns True if status is 'completed'."""
        return self.status == ComplianceRequestStatus.completed

    def __repr__(self) -> str:
        """String representation with masked customer email for GDPR compliance."""
        masked_email = f"{self.customer_email[:3]}***@***" if self.customer_email else "***"
        return f"<ComplianceRequest(id={self.id}, type={self.request_type}, email={masked_email}, status={self.status})>"

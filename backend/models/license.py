"""
SQLAlchemy model for License.
"""
import uuid
import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import UUID
from backend.app.database import Base

class License(Base):
    """
    Model representing a PARWA license key issued to a company.
    """
    __tablename__ = "licenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    license_key = Column(String, unique=True, index=True, nullable=False)
    tier = Column(String, nullable=False)
    status = Column(String, nullable=False)
    issued_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    max_seats = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    
    company = relationship("Company", backref="licenses")

    @validates('tier')
    def validate_tier(self, key: str, value: str) -> str:
        """Ensure tier is one of the valid enum values."""
        if value not in ["mini", "parwa", "parwa_high"]:
            raise ValueError(f"Invalid {key}: {value}")
        return value
        
    @validates('status')
    def validate_status(self, key: str, value: str) -> str:
        """Ensure status is one of the valid enum values."""
        if value not in ["active", "suspended", "expired"]:
            raise ValueError(f"Invalid {key}: {value}")
        return value

    def is_valid(self) -> bool:
        """
        Returns True if status is active and not expired.
        """
        if self.status != "active":
            return False
        if self.expires_at and self.expires_at < datetime.datetime.now(datetime.timezone.utc):
            return False
        return True

    def __repr__(self) -> str:
        """Readable representation of the model."""
        return f"<License {self.license_key} (Tier: {self.tier}, Status: {self.status})>"

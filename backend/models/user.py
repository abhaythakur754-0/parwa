import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates, relationship
from sqlalchemy.sql import func
from backend.app.database import Base


class RoleEnum(enum.Enum):
    admin = "admin"
    manager = "manager"
    viewer = "viewer"


class User(Base):
    """
    SQLAlchemy model representing a platform user (manager, admin).
    """
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Column[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    email: Column[str] = Column(String, unique=True, index=True, nullable=False)
    password_hash: Column[str] = Column(String, nullable=False)
    role: Column[RoleEnum] = Column(Enum(RoleEnum), nullable=False)
    is_active: Column[bool] = Column(Boolean, default=True, nullable=False)
    created_at: Column[datetime] = Column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Column[datetime] = Column(
        DateTime, onupdate=func.now(), default=datetime.utcnow, nullable=False
    )

    # Relationship to Company model
    company = relationship("Company", back_populates="users")

    @validates("email")
    def validate_email(self, key: str, email: str) -> str:
        """
        Validates and lowercases the email address.
        """
        if not email:
            raise ValueError("Email cannot be empty.")
        return email.lower()

    @validates("company_id")
    def validate_company_id(self, key: str, company_id: str | uuid.UUID) -> uuid.UUID:
        """
        Validates that company_id is a valid UUID.
        """
        if isinstance(company_id, uuid.UUID):
            return company_id
        try:
            return uuid.UUID(str(company_id))
        except ValueError:
            raise ValueError("Invalid UUID for company_id.")

    @validates("role")
    def validate_role(self, key: str, role: str | RoleEnum) -> RoleEnum:
        """
        Validates that the role is a valid enum value.
        """
        if isinstance(role, RoleEnum):
            return role
        try:
            return RoleEnum(role)
        except ValueError:
            valid_values = [e.value for e in RoleEnum]
            raise ValueError(f"Invalid role: {role}. Must be one of {valid_values}.")

    def __repr__(self) -> str:
        """
        String representation for debugging.
        """
        return f"<User(id={self.id}, email='{self.email}', role='{self.role.name}')>"

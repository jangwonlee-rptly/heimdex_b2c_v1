"""User model."""

import enum
from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Boolean, Enum, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.models.base import Base


class UserTier(str, enum.Enum):
    """User subscription tier."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    """User account model."""

    __tablename__ = "users"

    user_id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()")
    supabase_user_id = Column(PGUUID(as_uuid=True), nullable=True, unique=True, index=True)  # Supabase Auth user ID
    email = Column(String(255), nullable=False, unique=True, index=True)
    email_verified = Column(Boolean, nullable=False, server_default="false")
    password_hash = Column(String(255), nullable=True)  # Nullable for magic link only users
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    tier = Column(
        Enum(UserTier, name='user_tier', values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default="free"
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    face_profiles = relationship("FaceProfile", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    email_verification_tokens = relationship("EmailVerificationToken", back_populates="user", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="user")

    def __repr__(self):
        return f"<User(user_id={self.user_id}, email={self.email})>"

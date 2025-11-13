"""Authentication-related models."""

from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.models.base import Base


class RefreshToken(Base):
    """Refresh token model for JWT token rotation."""

    __tablename__ = "refresh_tokens"

    token_id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()")
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    revoked = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(token_id={self.token_id}, user_id={self.user_id})>"


class EmailVerificationToken(Base):
    """Email verification token model."""

    __tablename__ = "email_verification_tokens"

    token_id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()")
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    used = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")

    # Relationships
    user = relationship("User", back_populates="email_verification_tokens")

    def __repr__(self):
        return f"<EmailVerificationToken(token_id={self.token_id}, user_id={self.user_id})>"

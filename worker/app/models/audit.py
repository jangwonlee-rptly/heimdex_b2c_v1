"""Audit and rate limiting models."""

from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base


class AuditEvent(Base):
    """Audit event model for security and compliance."""

    __tablename__ = "audit_events"

    event_id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()")
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(127), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    event_metadata = Column("metadata", JSONB, nullable=True)  # Column name 'metadata' in DB, attribute 'event_metadata' in Python
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP", index=True)

    # Relationships
    user = relationship("User", back_populates="audit_events")

    def __repr__(self):
        return f"<AuditEvent(event_id={self.event_id}, event_type={self.event_type})>"


class RateLimit(Base):
    """Rate limit model for per-user and IP-based quotas."""

    __tablename__ = "rate_limits"

    limit_id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()")
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True)
    ip_address = Column(String(45), nullable=True)
    resource = Column(String(127), nullable=False)
    count = Column(Integer, nullable=False, server_default="1")
    window_start = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)

    def __repr__(self):
        return f"<RateLimit(limit_id={self.limit_id}, resource={self.resource}, count={self.count})>"

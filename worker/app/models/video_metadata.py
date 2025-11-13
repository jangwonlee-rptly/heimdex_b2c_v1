"""Video metadata model."""

from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base


class VideoMetadata(Base):
    """Video metadata model for title, description, tags, etc."""

    __tablename__ = "video_metadata"

    video_id = Column(PGUUID(as_uuid=True), ForeignKey("videos.video_id", ondelete="CASCADE"), primary_key=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    tags = Column(JSONB, nullable=True)
    thumbnail_url = Column(String(512), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")

    # Relationships
    video = relationship("Video", back_populates="video_metadata")

    def __repr__(self):
        return f"<VideoMetadata(video_id={self.video_id}, title={self.title})>"

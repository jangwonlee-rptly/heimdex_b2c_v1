"""Video model."""

import enum
from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, BigInteger, Numeric, Text, Enum, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.models.base import Base


class VideoState(str, enum.Enum):
    """Video processing state."""
    UPLOADING = "uploading"
    VALIDATING = "validating"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class Video(Base):
    """Video model."""

    __tablename__ = "videos"

    video_id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()")
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    storage_key = Column(String(512), nullable=False)
    mime_type = Column(String(127), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    duration_s = Column(Numeric(10, 3), nullable=True)
    state = Column(
        Enum(VideoState, name='video_state', values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default="uploading",
        index=True
    )
    error_text = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP", index=True)
    indexed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="videos")
    scenes = relationship("Scene", back_populates="video", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="video", cascade="all, delete-orphan")
    video_metadata = relationship("VideoMetadata", back_populates="video", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Video(video_id={self.video_id}, state={self.state})>"

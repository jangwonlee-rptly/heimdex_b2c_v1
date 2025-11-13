"""Job model for tracking video processing."""

import enum
from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, Float, Text, Enum, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import Base


class JobStage(str, enum.Enum):
    """Job processing stage."""
    UPLOAD_VALIDATE = "upload_validate"
    AUDIO_EXTRACT = "audio_extract"
    ASR_FAST = "asr_fast"
    SCENE_DETECT = "scene_detect"
    ALIGN_MERGE = "align_merge"
    EMBED_TEXT = "embed_text"
    VISION_SAMPLE_FRAMES = "vision_sample_frames"
    VISION_EMBED_FRAMES = "vision_embed_frames"
    VISION_AFFECT_TAGS = "vision_affect_tags"
    FACES_ENROLL_MATCH = "faces_enroll_match"
    SIDECAR_BUILD = "sidecar_build"
    COMMIT = "commit"


class JobState(str, enum.Enum):
    """Job execution state."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """Job model for tracking video processing stages."""

    __tablename__ = "jobs"

    job_id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()")
    video_id = Column(PGUUID(as_uuid=True), ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(
        Enum(JobStage, name='job_stage', values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    state = Column(
        Enum(JobState, name='job_state', values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default="pending",
        index=True
    )
    progress = Column(Float, nullable=False, server_default="0.0")
    error_text = Column(Text, nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    job_metadata = Column("metadata", JSONB, nullable=True)  # Column name 'metadata' in DB, attribute 'job_metadata' in Python

    # Relationships
    video = relationship("Video", back_populates="jobs")

    def __repr__(self):
        return f"<Job(job_id={self.job_id}, stage={self.stage}, state={self.state})>"

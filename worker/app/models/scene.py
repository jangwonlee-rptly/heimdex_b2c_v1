"""Scene model."""

from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Numeric, Text, TIMESTAMP, ForeignKey, Float, Integer, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID, TSVECTOR, JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from app.models.base import Base


class Scene(Base):
    """Scene model - represents a segment of a video."""

    __tablename__ = "scenes"

    scene_id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()")
    video_id = Column(PGUUID(as_uuid=True), ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False, index=True)
    start_s = Column(Numeric(10, 3), nullable=False)
    end_s = Column(Numeric(10, 3), nullable=False)
    transcript = Column(Text, nullable=True)
    tsv = Column(TSVECTOR, nullable=True)
    text_vec = Column(Vector(1152), nullable=True)  # Updated to 1152 from migration 20251111_1530_005
    image_vec = Column(Vector(1152), nullable=True)  # Updated to 1152 from migration 20251111_1530_005
    vision_tags = Column(JSONB, nullable=True)
    sidecar_key = Column(String(512), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")

    # Thumbnail fields (from migration 20251112_0200_006_add_scene_thumbnails.py)
    thumbnail_key = Column(String(512), nullable=True)

    # Relationships
    video = relationship("Video", back_populates="scenes")
    scene_people = relationship("ScenePerson", back_populates="scene", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Scene(scene_id={self.scene_id}, video_id={self.video_id}, start={self.start_s})>"


class ScenePerson(Base):
    """Association table between scenes and face profiles."""

    __tablename__ = "scene_people"

    scene_id = Column(PGUUID(as_uuid=True), ForeignKey("scenes.scene_id", ondelete="CASCADE"), nullable=False)
    person_id = Column(PGUUID(as_uuid=True), ForeignKey("face_profiles.face_profile_id", ondelete="CASCADE"), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    frame_count = Column(Integer, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('scene_id', 'person_id'),
    )

    # Relationships
    scene = relationship("Scene", back_populates="scene_people")
    face_profile = relationship("FaceProfile", back_populates="scene_people")

    def __repr__(self):
        return f"<ScenePerson(scene_id={self.scene_id}, person_id={self.person_id}, confidence={self.confidence})>"

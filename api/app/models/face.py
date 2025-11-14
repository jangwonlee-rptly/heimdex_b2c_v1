"""Face recognition models."""

from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, TIMESTAMP, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from app.models.base import Base

# Import ScenePerson for backward compatibility (defined in scene.py)
# This allows "from app.models.face import ScenePerson" to work
def __getattr__(name):
    if name == "ScenePerson":
        from app.models.scene import ScenePerson
        return ScenePerson
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class FaceProfile(Base):
    """Face profile model for known people."""

    __tablename__ = "face_profiles"

    person_id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()")
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)  # Supabase user ID (no FK)
    name = Column(String(255), nullable=False)
    adaface_vec = Column(Vector(512), nullable=True)
    photo_keys = Column(ARRAY(String), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")

    # Relationships
    scene_people = relationship("ScenePerson", back_populates="face_profile", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FaceProfile(person_id={self.person_id}, name={self.name})>"

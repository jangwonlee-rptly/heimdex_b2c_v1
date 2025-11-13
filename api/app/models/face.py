"""Face recognition models."""

from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, ARRAY
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

    face_profile_id = Column(PGUUID(as_uuid=True), primary_key=True, server_default="uuid_generate_v4()")
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    face_vec = Column(Vector(512), nullable=True)  # Match database column name
    photo_url = Column(String(512), nullable=True)  # Match database column name
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")

    # Relationships
    user = relationship("User", back_populates="face_profiles")
    scene_people = relationship("ScenePerson", back_populates="face_profile", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FaceProfile(face_profile_id={self.face_profile_id}, name={self.name})>"

"""Search API routes for Heimdex B2C."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db import get_db
from app.auth.middleware import AuthUser, get_current_user
from app.models.scene import Scene
from app.models.video import Video
from app.logging_config import logger


router = APIRouter()


# Response models
class SceneResponse(BaseModel):
    """Scene response model matching frontend expectations."""
    id: str = Field(alias="scene_id")
    video_id: str
    start_time: float = Field(alias="start_s")
    end_time: float = Field(alias="end_s")
    transcript: Optional[str] = None
    created_at: str

    class Config:
        populate_by_name = True
        from_attributes = True


class VideoResponse(BaseModel):
    """Video response model."""
    video_id: str
    user_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    duration_s: Optional[float] = None
    size_bytes: int
    mime_type: str
    state: str
    created_at: str
    indexed_at: Optional[str] = None

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """Search result with scene, video, and relevance score."""
    scene: SceneResponse
    video: VideoResponse
    score: float
    highlights: Optional[List[str]] = None


class SearchResponse(BaseModel):
    """Search response with results and metadata."""
    results: List[SearchResult]
    total: int
    query: str


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query text", min_length=1),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    person_id: Optional[str] = Query(None, description="Filter by person ID"),
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search videos using keyword matching on transcripts.

    This endpoint:
    1. Searches scenes using case-insensitive keyword matching on transcripts
    2. Returns matching scenes with their parent videos
    3. Supports pagination and filtering
    """
    logger.info(f"[search] Query: '{q}', user: {current_user.user_id}")

    try:
        # Build search query with keyword matching on transcripts
        # Use ILIKE for case-insensitive pattern matching
        search_pattern = f"%{q}%"

        # Main query joining scenes with videos
        query = (
            select(Scene, Video)
            .join(Video, Scene.video_id == Video.video_id)
            .where(Video.user_id == UUID(current_user.user_id))  # Filter by user
            .where(Video.state == 'indexed')  # Only search indexed videos
            .where(Scene.transcript.ilike(search_pattern))  # Keyword match on transcript
            .order_by(Scene.created_at.desc())  # Most recent first
        )

        # Optional: Filter by person_id (requires face detection)
        if person_id:
            # TODO: Join with scene_people table when face detection is implemented
            logger.warning("[search] person_id filtering not yet implemented")

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        results = result.all()

        # Build response
        search_results = []
        for scene, video in results:
            # Convert scene
            scene_dict = {
                "scene_id": str(scene.scene_id),
                "video_id": str(scene.video_id),
                "start_s": float(scene.start_s),
                "end_s": float(scene.end_s),
                "transcript": scene.transcript,
                "created_at": scene.created_at.isoformat() if scene.created_at else None,
            }

            # Convert video
            video_dict = {
                "video_id": str(video.video_id),
                "user_id": str(video.user_id),
                "title": video.title,
                "description": video.description,
                "duration_s": float(video.duration_s) if video.duration_s else None,
                "size_bytes": video.size_bytes,
                "mime_type": video.mime_type,
                "state": video.state,
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "indexed_at": video.indexed_at.isoformat() if video.indexed_at else None,
            }

            # Create highlights from transcript (optional)
            highlights = []
            if scene.transcript and q.lower() in scene.transcript.lower():
                highlights.append(scene.transcript)

            # Simple scoring: 1.0 for all matches (can be improved later)
            score = 1.0

            search_results.append(
                SearchResult(
                    scene=SceneResponse(**scene_dict),
                    video=VideoResponse(**video_dict),
                    score=score,
                    highlights=highlights if highlights else None,
                )
            )

        logger.info(f"[search] Found {len(search_results)} results (total: {total})")

        return SearchResponse(
            results=search_results,
            total=total,
            query=q,
        )

    except Exception as e:
        logger.error(f"[search] Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

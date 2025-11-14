"""Video upload and management routes."""

from datetime import timedelta
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import AuthUser, get_current_user
from app.config import settings
from app.db import get_db
from app.logging_config import logger
from app.models.video import Video, VideoState
from app.models.video_metadata import VideoMetadata
from app.models.job import Job, JobStage, JobState
from app.models.scene import Scene
from app.storage import StorageClient

router = APIRouter()


# Request/Response Models
class VideoUploadInitRequest(BaseModel):
    """Request to initialize video upload."""
    filename: str = Field(..., description="Original filename")
    mime_type: str = Field(..., description="MIME type (e.g., video/mp4)")
    size_bytes: int = Field(..., ge=1, le=1073741824, description="File size in bytes (max 1GB)")
    title: Optional[str] = Field(None, max_length=255, description="Video title")
    description: Optional[str] = Field(None, description="Video description")


class VideoUploadInitResponse(BaseModel):
    """Response with presigned upload URL."""
    video_id: str
    upload_url: str
    expires_in: int = Field(..., description="URL expiration in seconds")


class VideoUploadCompleteRequest(BaseModel):
    """Request to mark upload as complete and trigger processing."""
    video_id: str


class VideoResponse(BaseModel):
    """Video response model."""
    video_id: str
    user_id: str
    title: Optional[str]
    description: Optional[str]
    mime_type: str
    size_bytes: int
    duration_s: Optional[float]
    state: str
    error_text: Optional[str]
    thumbnail_url: Optional[str]
    created_at: str
    indexed_at: Optional[str]


class VideoListResponse(BaseModel):
    """List of videos."""
    videos: List[VideoResponse]
    total: int


@router.post("/upload/init", response_model=VideoUploadInitResponse, status_code=status.HTTP_201_CREATED)
async def init_video_upload(
    request: VideoUploadInitRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoUploadInitResponse:
    """
    Initialize video upload and get presigned URL.

    This endpoint:
    1. Validates the upload request (size, mime type)
    2. Creates a video record in the database with state=uploading
    3. Generates a presigned URL for direct upload to object storage
    4. Returns the URL to the client

    The client then uploads the video directly to object storage using the presigned URL.
    """
    # Validate MIME type
    allowed_mime_types = [
        "video/mp4",
        "video/quicktime",  # MOV
        "video/x-msvideo",  # AVI
        "video/x-matroska",  # MKV
        "video/webm",
    ]
    if request.mime_type not in allowed_mime_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video type. Allowed types: {', '.join(allowed_mime_types)}"
        )

    # Validate size (max 1GB)
    if request.size_bytes > settings.max_video_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Video size exceeds maximum allowed size of {settings.max_video_size_bytes / (1024**3):.1f} GB"
        )

    # Generate unique storage key
    video_id = uuid4()
    file_extension = request.filename.split(".")[-1] if "." in request.filename else "mp4"
    storage_key = f"videos/{user.supabase_user_id}/{video_id}.{file_extension}"

    # Create video record
    video = Video(
        video_id=video_id,
        user_id=UUID(user.supabase_user_id),
        storage_key=storage_key,
        mime_type=request.mime_type,
        size_bytes=request.size_bytes,
        state=VideoState.UPLOADING,
    )
    db.add(video)

    # Create video metadata if title or description provided
    if request.title or request.description:
        metadata = VideoMetadata(
            video_id=video_id,
            title=request.title or request.filename,
            description=request.description,
        )
        db.add(metadata)

    await db.commit()
    await db.refresh(video)

    logger.info(
        "Initialized video upload",
        video_id=str(video_id),
        user_id=user.supabase_user_id,
        storage_key=storage_key,
        size_bytes=request.size_bytes
    )

    # Generate presigned upload URL
    upload_url = StorageClient.generate_presigned_upload_url(
        bucket=settings.storage_bucket_uploads,
        object_key=storage_key,
        expires=timedelta(minutes=15),
    )

    return VideoUploadInitResponse(
        video_id=str(video_id),
        upload_url=upload_url,
        expires_in=900,  # 15 minutes
    )


@router.post("/upload/complete", status_code=status.HTTP_202_ACCEPTED)
async def complete_video_upload(
    request: VideoUploadCompleteRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark upload as complete and trigger processing pipeline.

    This endpoint:
    1. Verifies the video belongs to the authenticated user
    2. Updates video state to 'validating'
    3. Creates a job to start the processing pipeline
    4. Returns immediately (processing happens asynchronously)
    """
    # Get video record
    stmt = select(Video).where(
        Video.video_id == UUID(request.video_id),
        Video.user_id == UUID(user.supabase_user_id),
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    if video.state != 'uploading':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Video is not in uploading state (current state: {video.state})"
        )

    # Update video state
    video.state = 'validating'

    # Create initial validation job
    validation_job = Job(
        video_id=video.video_id,
        stage='upload_validate',
        state='pending',
    )

    db.add(validation_job)
    await db.commit()

    logger.info(
        "Video upload completed, queued for processing",
        video_id=str(video.video_id),
        user_id=user.supabase_user_id,
        job_id=str(validation_job.job_id)
    )

    # Send job to Dramatiq queue for processing
    try:
        import dramatiq
        from dramatiq.brokers.redis import RedisBroker

        # Configure Redis broker
        redis_url = settings.redis_url
        redis_broker = RedisBroker(url=redis_url)
        dramatiq.set_broker(redis_broker)

        # Create a stub actor that references the worker's process_video task
        # We don't import the actual worker code - just declare the actor exists
        @dramatiq.actor(
            actor_name="process_video",
            queue_name="video_processing",
            broker=redis_broker
        )
        def process_video_stub(video_id_str: str):
            """Stub - actual implementation is in worker container."""
            pass

        # Send the task to the queue
        process_video_stub.send(str(video.video_id))

        logger.info(
            "Sent video processing task to queue",
            video_id=str(video.video_id)
        )
    except Exception as e:
        logger.error(
            "Failed to queue video processing task",
            video_id=str(video.video_id),
            error=str(e)
        )
        # Don't fail the request - video is still uploaded
        pass

    return {
        "video_id": str(video.video_id),
        "state": video.state,
        "message": "Video queued for processing"
    }


@router.get("", response_model=VideoListResponse)
async def list_videos(
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> VideoListResponse:
    """
    List all videos for the authenticated user.

    Returns videos ordered by creation date (newest first).
    Includes thumbnail URL from the first scene of each video.
    """
    # Get total count
    from sqlalchemy import func as sql_func
    count_stmt = select(sql_func.count(Video.video_id)).where(Video.user_id == UUID(user.supabase_user_id))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Get videos with metadata
    stmt = (
        select(Video)
        .options(selectinload(Video.video_metadata))
        .where(Video.user_id == UUID(user.supabase_user_id))
        .order_by(Video.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    videos = result.scalars().all()

    # Get first scene thumbnail for each video
    video_ids = [v.video_id for v in videos]
    thumbnail_map = {}

    if video_ids:
        # Subquery to get the minimum start_s for each video
        from sqlalchemy import func as sql_func
        min_start_subq = (
            select(
                Scene.video_id,
                sql_func.min(Scene.start_s).label('min_start')
            )
            .where(
                Scene.video_id.in_(video_ids),
                Scene.thumbnail_key.isnot(None)
            )
            .group_by(Scene.video_id)
            .subquery()
        )

        # Get the first scene for each video
        scenes_stmt = (
            select(Scene)
            .join(
                min_start_subq,
                (Scene.video_id == min_start_subq.c.video_id) &
                (Scene.start_s == min_start_subq.c.min_start)
            )
        )
        scenes_result = await db.execute(scenes_stmt)
        scenes = scenes_result.scalars().all()

        # Generate presigned URLs for thumbnails
        for scene in scenes:
            if scene.thumbnail_key:
                try:
                    thumbnail_url = StorageClient.generate_presigned_download_url(
                        bucket=settings.storage_bucket_thumbnails,
                        object_key=scene.thumbnail_key,
                        expires=timedelta(hours=1)
                    )
                    thumbnail_map[scene.video_id] = thumbnail_url
                except Exception as e:
                    logger.warning(f"Failed to generate thumbnail URL for video {scene.video_id}: {e}")

    return VideoListResponse(
        videos=[
            VideoResponse(
                video_id=str(v.video_id),
                user_id=str(v.user_id),
                title=v.video_metadata.title if v.video_metadata else None,
                description=v.video_metadata.description if v.video_metadata else None,
                mime_type=v.mime_type,
                size_bytes=v.size_bytes,
                duration_s=float(v.duration_s) if v.duration_s else None,
                state=v.state,
                error_text=v.error_text,
                thumbnail_url=thumbnail_map.get(v.video_id),
                created_at=v.created_at.isoformat(),
                indexed_at=v.indexed_at.isoformat() if v.indexed_at else None,
            )
            for v in videos
        ],
        total=total,
    )


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VideoResponse:
    """Get details for a specific video."""
    stmt = (
        select(Video)
        .options(selectinload(Video.video_metadata))
        .where(
            Video.video_id == UUID(video_id),
            Video.user_id == UUID(user.supabase_user_id),
        )
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    # Get first scene thumbnail
    thumbnail_url = None
    first_scene_stmt = (
        select(Scene)
        .where(
            Scene.video_id == video.video_id,
            Scene.thumbnail_key.isnot(None)
        )
        .order_by(Scene.start_s)
        .limit(1)
    )
    first_scene_result = await db.execute(first_scene_stmt)
    first_scene = first_scene_result.scalar_one_or_none()

    if first_scene and first_scene.thumbnail_key:
        try:
            thumbnail_url = StorageClient.generate_presigned_download_url(
                bucket=settings.storage_bucket_thumbnails,
                object_key=first_scene.thumbnail_key,
                expires=timedelta(hours=1)
            )
        except Exception as e:
            logger.warning(f"Failed to generate thumbnail URL for video {video.video_id}: {e}")

    return VideoResponse(
        video_id=str(video.video_id),
        user_id=str(video.user_id),
        title=video.video_metadata.title if video.video_metadata else None,
        description=video.video_metadata.description if video.video_metadata else None,
        mime_type=video.mime_type,
        size_bytes=video.size_bytes,
        duration_s=float(video.duration_s) if video.duration_s else None,
        state=video.state,
        error_text=video.error_text,
        thumbnail_url=thumbnail_url,
        created_at=video.created_at.isoformat(),
        indexed_at=video.indexed_at.isoformat() if video.indexed_at else None,
    )


@router.get("/{video_id}/status")
async def get_video_status(
    video_id: str,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get processing status for a video.

    Returns the video state and all associated jobs with their progress.
    """
    # Get video
    stmt = select(Video).where(
        Video.video_id == UUID(video_id),
        Video.user_id == UUID(user.supabase_user_id),
    )
    result = await db.execute(stmt)
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    # Get all jobs for this video
    jobs_stmt = (
        select(Job)
        .where(Job.video_id == UUID(video_id))
        .order_by(Job.started_at.desc())
    )
    jobs_result = await db.execute(jobs_stmt)
    jobs = jobs_result.scalars().all()

    return {
        "video_id": str(video.video_id),
        "state": video.state,
        "error_text": video.error_text,
        "jobs": [
            {
                "job_id": str(job.job_id),
                "stage": job.stage,
                "state": job.state,
                "progress": job.progress,
                "error_text": job.error_text,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
            for job in jobs
        ],
    }

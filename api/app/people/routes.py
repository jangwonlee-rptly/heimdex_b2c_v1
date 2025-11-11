"""People/Face Profile API routes for Heimdex B2C."""

from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db import get_db
from app.auth.middleware import AuthUser, get_current_user
from app.models.face import FaceProfile
from app.logging_config import logger


router = APIRouter()


# Request/Response models
class PersonCreate(BaseModel):
    """Request model for creating a face profile."""
    name: str = Field(..., min_length=1, max_length=100, description="Person's name")


class PersonResponse(BaseModel):
    """Response model for face profile."""
    person_id: str
    user_id: str
    name: str
    photo_count: int
    created_at: str

    class Config:
        from_attributes = True


class PeopleListResponse(BaseModel):
    """Response model for list of people."""
    people: List[PersonResponse]
    total: int


@router.get("", response_model=PeopleListResponse)
async def list_people(
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all face profiles (enrolled people) for the current user.

    Returns:
        List of face profiles with metadata
    """
    logger.info(f"[people] Listing face profiles for user: {current_user.user_id}")

    try:
        user_uuid = UUID(current_user.user_id)

        # Query face profiles for user
        query = (
            select(FaceProfile)
            .where(FaceProfile.user_id == user_uuid)
            .order_by(FaceProfile.created_at.desc())
        )

        result = await db.execute(query)
        profiles = result.scalars().all()

        # Build response
        people_list = []
        for profile in profiles:
            people_list.append(
                PersonResponse(
                    person_id=str(profile.person_id),
                    user_id=str(profile.user_id),
                    name=profile.name,
                    photo_count=len(profile.photo_keys) if profile.photo_keys else 0,
                    created_at=profile.created_at.isoformat() if profile.created_at else None,
                )
            )

        logger.info(f"[people] Found {len(people_list)} face profiles")

        return PeopleListResponse(
            people=people_list,
            total=len(people_list),
        )

    except Exception as e:
        logger.error(f"[people] Error listing profiles: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list face profiles: {str(e)}"
        )


@router.post("", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def create_person(
    person: PersonCreate,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new face profile (enroll a person).

    Note: This creates the profile but does not upload photos yet.
    Use POST /people/{person_id}/photos to upload enrollment photos.

    Args:
        person: Person creation data (name)

    Returns:
        Created face profile
    """
    logger.info(f"[people] Creating face profile '{person.name}' for user: {current_user.user_id}")

    try:
        user_uuid = UUID(current_user.user_id)

        # Check if person with same name already exists
        existing_query = (
            select(FaceProfile)
            .where(FaceProfile.user_id == user_uuid)
            .where(FaceProfile.name == person.name)
        )
        existing_result = await db.execute(existing_query)
        existing_profile = existing_result.scalar_one_or_none()

        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Face profile with name '{person.name}' already exists"
            )

        # Create new face profile
        new_profile = FaceProfile(
            person_id=uuid4(),
            user_id=user_uuid,
            name=person.name,
            photo_keys=[],  # Empty initially, photos uploaded separately
            face_vec=None,  # Will be computed when photos are uploaded
            created_at=datetime.utcnow(),
        )

        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)

        logger.info(f"[people] Created face profile: {new_profile.person_id}")

        return PersonResponse(
            person_id=str(new_profile.person_id),
            user_id=str(new_profile.user_id),
            name=new_profile.name,
            photo_count=0,
            created_at=new_profile.created_at.isoformat() if new_profile.created_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[people] Error creating profile: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create face profile: {str(e)}"
        )


@router.get("/{person_id}", response_model=PersonResponse)
async def get_person(
    person_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific face profile by ID.

    Args:
        person_id: Face profile ID (UUID)

    Returns:
        Face profile details
    """
    logger.info(f"[people] Getting face profile: {person_id}")

    try:
        user_uuid = UUID(current_user.user_id)
        person_uuid = UUID(person_id)

        # Query face profile
        query = (
            select(FaceProfile)
            .where(FaceProfile.person_id == person_uuid)
            .where(FaceProfile.user_id == user_uuid)  # Ensure user owns this profile
        )

        result = await db.execute(query)
        profile = result.scalar_one_or_none()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Face profile not found: {person_id}"
            )

        return PersonResponse(
            person_id=str(profile.person_id),
            user_id=str(profile.user_id),
            name=profile.name,
            photo_count=len(profile.photo_keys) if profile.photo_keys else 0,
            created_at=profile.created_at.isoformat() if profile.created_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[people] Error getting profile: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get face profile: {str(e)}"
        )


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a face profile.

    Args:
        person_id: Face profile ID (UUID)

    Returns:
        204 No Content on success
    """
    logger.info(f"[people] Deleting face profile: {person_id}")

    try:
        user_uuid = UUID(current_user.user_id)
        person_uuid = UUID(person_id)

        # Query face profile
        query = (
            select(FaceProfile)
            .where(FaceProfile.person_id == person_uuid)
            .where(FaceProfile.user_id == user_uuid)  # Ensure user owns this profile
        )

        result = await db.execute(query)
        profile = result.scalar_one_or_none()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Face profile not found: {person_id}"
            )

        # Delete profile
        await db.delete(profile)
        await db.commit()

        logger.info(f"[people] Deleted face profile: {person_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[people] Error deleting profile: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete face profile: {str(e)}"
        )


class PhotoUploadRequest(BaseModel):
    """Request model for photo upload initialization."""
    content_type: str = Field(default="image/jpeg", description="MIME type of the photo")


class PhotoUploadResponse(BaseModel):
    """Response model for photo upload initialization."""
    upload_url: str
    photo_key: str


@router.post("/{person_id}/photos", response_model=PhotoUploadResponse)
async def init_person_photo_upload(
    person_id: str,
    request: PhotoUploadRequest,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Initialize photo upload for a person profile.

    Returns a presigned URL for uploading the photo directly to storage.
    After upload, call POST /people/{person_id}/photos/complete to trigger
    face embedding computation.

    Args:
        person_id: Face profile ID (UUID)
        request: Upload request with content_type

    Returns:
        Presigned upload URL and photo storage key
    """
    logger.info(f"[people] Initializing photo upload for person: {person_id}")

    try:
        from app.config import settings

        # Check if face enrollment is enabled
        if not settings.feature_face_enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Face enrollment is not enabled"
            )

        user_uuid = UUID(current_user.user_id)
        person_uuid = UUID(person_id)

        # Verify person exists and belongs to user
        query = (
            select(FaceProfile)
            .where(FaceProfile.person_id == person_uuid)
            .where(FaceProfile.user_id == user_uuid)
        )
        result = await db.execute(query)
        profile = result.scalar_one_or_none()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Face profile not found: {person_id}"
            )

        # Validate content type
        allowed_types = ["image/jpeg", "image/jpg", "image/png"]
        if request.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported content type. Allowed: {', '.join(allowed_types)}"
            )

        # Generate photo storage key
        from datetime import datetime
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        extension = "jpg" if "jpeg" in request.content_type else "png"
        photo_key = f"faces/{current_user.user_id}/{person_id}/photo_{timestamp}.{extension}"

        # Generate presigned upload URL
        from app.storage import StorageClient
        from datetime import timedelta

        upload_url = StorageClient.generate_presigned_upload_url(
            bucket=settings.storage_bucket_uploads,
            object_key=photo_key,
            expires=timedelta(minutes=15)
        )

        logger.info(
            "[people] Generated presigned URL for photo upload",
            person_id=person_id,
            photo_key=photo_key
        )

        return PhotoUploadResponse(
            upload_url=upload_url,
            photo_key=photo_key
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[people] Error initializing photo upload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize photo upload: {str(e)}"
        )


class PhotoCompleteRequest(BaseModel):
    """Request model for completing photo upload."""
    photo_key: str = Field(..., description="Storage key returned from upload init")


@router.post("/{person_id}/photos/complete", status_code=status.HTTP_202_ACCEPTED)
async def complete_person_photo_upload(
    person_id: str,
    request: PhotoCompleteRequest,
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Complete photo upload and trigger face embedding computation.

    This endpoint should be called after successfully uploading the photo
    to the presigned URL. It will:
    1. Add the photo_key to the person's photo_keys array
    2. Queue a background task to compute face embeddings
    3. Update the person's face_vec with the averaged embedding

    Args:
        person_id: Face profile ID (UUID)
        request: Photo completion data with photo_key

    Returns:
        202 Accepted - embedding computation queued
    """
    logger.info(
        f"[people] Completing photo upload for person: {person_id}",
        photo_key=request.photo_key
    )

    try:
        from app.config import settings

        # Check if face enrollment is enabled
        if not settings.feature_face_enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Face enrollment is not enabled"
            )

        user_uuid = UUID(current_user.user_id)
        person_uuid = UUID(person_id)

        # Verify person exists and belongs to user
        query = (
            select(FaceProfile)
            .where(FaceProfile.person_id == person_uuid)
            .where(FaceProfile.user_id == user_uuid)
        )
        result = await db.execute(query)
        profile = result.scalar_one_or_none()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Face profile not found: {person_id}"
            )

        # Verify photo_key belongs to this person
        expected_prefix = f"faces/{current_user.user_id}/{person_id}/"
        if not request.photo_key.startswith(expected_prefix):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Photo key does not belong to this person"
            )

        # Add photo_key to profile
        if profile.photo_keys is None:
            profile.photo_keys = []

        if request.photo_key not in profile.photo_keys:
            profile.photo_keys = profile.photo_keys + [request.photo_key]
            await db.commit()
            await db.refresh(profile)

        # Queue face embedding computation task
        import dramatiq
        from dramatiq.brokers.redis import RedisBroker

        redis_url = settings.redis_url
        redis_broker = RedisBroker(url=redis_url)
        dramatiq.set_broker(redis_broker)

        # Create stub actor for compute_face_embedding
        @dramatiq.actor(
            actor_name="compute_face_embedding",
            queue_name="face_processing",
            broker=redis_broker
        )
        def compute_face_embedding_stub(person_id_str: str):
            """Stub - actual implementation in worker container."""
            pass

        # Send task to queue
        compute_face_embedding_stub.send(str(person_id))

        logger.info(
            "[people] Queued face embedding computation",
            person_id=person_id,
            photo_count=len(profile.photo_keys)
        )

        return {
            "message": "Photo upload completed, face embedding computation queued",
            "person_id": str(profile.person_id),
            "photo_count": len(profile.photo_keys)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[people] Error completing photo upload: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete photo upload: {str(e)}"
        )

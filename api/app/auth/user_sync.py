"""User synchronization between Supabase Auth and local database."""

from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.logging_config import logger


async def get_or_create_user(
    db: AsyncSession,
    supabase_user_id: str,
    email: str,
    email_verified: bool = False,
    display_name: Optional[str] = None,
) -> User:
    """
    Get existing user or create new user from Supabase auth data.

    This function ensures that a local user record exists for every Supabase user.
    It's called after successful authentication to sync the user to local DB.

    Args:
        db: Database session
        supabase_user_id: Supabase Auth user UUID
        email: User email from Supabase
        email_verified: Email verification status from Supabase
        display_name: Optional display name

    Returns:
        User: Local user record (existing or newly created)

    Raises:
        IntegrityError: If database constraints are violated
    """
    # First, try to find user by supabase_user_id
    stmt = select(User).where(User.supabase_user_id == UUID(supabase_user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # User exists, update email verification status if needed
        if user.email_verified != email_verified:
            user.email_verified = email_verified
            await db.commit()
            await db.refresh(user)
            logger.info(
                "Updated user email_verified status",
                user_id=str(user.user_id),
                supabase_user_id=supabase_user_id,
                email_verified=email_verified
            )
        return user

    # User doesn't exist by supabase_user_id, check by email
    # (in case they registered before Supabase integration)
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Link existing user to Supabase
        user.supabase_user_id = UUID(supabase_user_id)
        user.email_verified = email_verified
        if display_name and not user.display_name:
            user.display_name = display_name
        await db.commit()
        await db.refresh(user)
        logger.info(
            "Linked existing user to Supabase",
            user_id=str(user.user_id),
            supabase_user_id=supabase_user_id,
            email=email
        )
        return user

    # Create new user
    try:
        new_user = User(
            supabase_user_id=UUID(supabase_user_id),
            email=email,
            email_verified=email_verified,
            display_name=display_name,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(
            "Created new user from Supabase auth",
            user_id=str(new_user.user_id),
            supabase_user_id=supabase_user_id,
            email=email
        )
        return new_user
    except IntegrityError as e:
        await db.rollback()
        logger.error(
            "Failed to create user - integrity error",
            supabase_user_id=supabase_user_id,
            email=email,
            error=str(e)
        )
        raise


async def get_user_by_supabase_id(db: AsyncSession, supabase_user_id: str) -> Optional[User]:
    """
    Get local user by Supabase user ID.

    Args:
        db: Database session
        supabase_user_id: Supabase Auth user UUID

    Returns:
        User if found, None otherwise
    """
    stmt = select(User).where(User.supabase_user_id == UUID(supabase_user_id))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    """
    Get local user by local user ID.

    Args:
        db: Database session
        user_id: Local user UUID

    Returns:
        User if found, None otherwise
    """
    stmt = select(User).where(User.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

"""Authentication middleware for JWT token verification."""

import jwt
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.logging_config import logger

# Security scheme for extracting Bearer token
security = HTTPBearer()


class AuthUser:
    """Authenticated user context."""

    def __init__(
        self,
        user_id: str,
        supabase_user_id: str,
        email: str,
        email_verified: bool = False,
    ):
        self.user_id = user_id
        self.supabase_user_id = supabase_user_id
        self.email = email
        self.email_verified = email_verified


async def verify_token(token: str) -> dict:
    """Verify Supabase JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Decode JWT using Supabase JWT secret
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",  # Supabase default audience
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AuthUser:
    """Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        Authenticated user context

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials

    # Verify token and get payload
    payload = await verify_token(token)

    # Extract user info from Supabase token
    supabase_user_id = payload.get("sub")
    email = payload.get("email")
    email_verified = payload.get("email_confirmed_at") is not None

    if not supabase_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID",
        )

    # Get or create user in local database
    from app.auth.user_sync import get_or_create_user

    user = await get_or_create_user(
        db=db,
        supabase_user_id=supabase_user_id,
        email=email or "",
        email_verified=email_verified,
        display_name=payload.get("user_metadata", {}).get("display_name"),
    )

    return AuthUser(
        user_id=str(user.user_id),
        supabase_user_id=supabase_user_id,
        email=user.email,
        email_verified=user.email_verified,
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> Optional[AuthUser]:
    """Get current user if authenticated, None otherwise.

    Useful for endpoints that work with or without authentication.

    Args:
        credentials: Optional HTTP Bearer credentials
        db: Database session

    Returns:
        Authenticated user or None
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None

"""Authentication middleware for JWT token verification.

All user data is now stored in Supabase. The middleware extracts user information
directly from the Supabase JWT token without needing a local database lookup.
"""

import jwt
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.logging_config import logger

# Security scheme for extracting Bearer token
security = HTTPBearer()


class AuthUser:
    """Authenticated user context extracted from Supabase JWT token."""

    def __init__(
        self,
        supabase_user_id: str,
        email: str,
        email_verified: bool = False,
        display_name: Optional[str] = None,
        onboarding_completed: bool = False,
        industry: Optional[str] = None,
        job_title: Optional[str] = None,
        email_consent: bool = False,
        tier: str = "free",
    ):
        self.supabase_user_id = supabase_user_id
        self.email = email
        self.email_verified = email_verified
        self.display_name = display_name
        self.onboarding_completed = onboarding_completed
        self.industry = industry
        self.job_title = job_title
        self.email_consent = email_consent
        self.tier = tier


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
) -> AuthUser:
    """Get current authenticated user from JWT token.

    All user data is extracted directly from the Supabase JWT token.
    No local database lookup is needed.

    Args:
        credentials: HTTP Bearer credentials

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

    # Extract user_metadata from JWT token (includes all profile data)
    user_metadata = payload.get("user_metadata", {})
    app_metadata = payload.get("app_metadata", {})

    return AuthUser(
        supabase_user_id=supabase_user_id,
        email=email or "",
        email_verified=email_verified,
        display_name=user_metadata.get("display_name"),
        onboarding_completed=user_metadata.get("onboarding_completed", False),
        industry=user_metadata.get("industry"),
        job_title=user_metadata.get("job_title"),
        email_consent=user_metadata.get("email_consent", False),
        tier=app_metadata.get("tier", "free"),  # Tier in app_metadata for security
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[AuthUser]:
    """Get current user if authenticated, None otherwise.

    Useful for endpoints that work with or without authentication.

    Args:
        credentials: Optional HTTP Bearer credentials

    Returns:
        Authenticated user or None
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

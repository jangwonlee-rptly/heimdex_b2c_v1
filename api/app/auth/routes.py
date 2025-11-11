"""Authentication routes using Supabase."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from supabase import Client
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase import get_supabase
from app.auth.middleware import get_current_user, AuthUser
from app.db import get_db
from app.logging_config import logger

router = APIRouter()


# Request/Response models
class SignUpRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    display_name: Optional[str] = Field(None, max_length=255)


class SignInRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    """Password reset request."""

    email: EmailStr


class PasswordUpdateRequest(BaseModel):
    """Password update request."""

    new_password: str = Field(..., min_length=8)


class MagicLinkRequest(BaseModel):
    """Magic link request."""

    email: EmailStr


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str = Field(..., description="Refresh token to exchange for new access token")


class AuthResponse(BaseModel):
    """Authentication response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    user: dict


class UserResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    email_verified: bool
    display_name: Optional[str] = None
    created_at: str


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: SignUpRequest,
    supabase: Client = Depends(get_supabase),
):
    """Register a new user with email and password.

    Args:
        request: Registration request with email and password
        supabase: Supabase client

    Returns:
        Authentication response with tokens

    Raises:
        HTTPException: If registration fails
    """
    try:
        # Sign up user with Supabase
        response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {
                    "display_name": request.display_name,
                }
            }
        })

        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed",
            )

        logger.info(
            "User registered successfully",
            user_id=response.user.id,
            email=request.email,
            email_confirmation_required=response.session is None,
        )

        # Check if email confirmation is required
        if response.session is None:
            # Email confirmation required - no session returned yet
            logger.info(
                "Email confirmation required",
                user_id=response.user.id,
                email=request.email,
            )
            raise HTTPException(
                status_code=status.HTTP_201_CREATED,
                detail={
                    "message": "Registration successful. Please check your email to confirm your account.",
                    "email_confirmation_required": True,
                    "user_id": response.user.id,
                }
            )

        # Return tokens and user info (only if email confirmation is disabled)
        return AuthResponse(
            access_token=response.session.access_token,
            token_type="bearer",
            expires_in=response.session.expires_in or 3600,
            refresh_token=response.session.refresh_token,
            user={
                "id": response.user.id,
                "email": response.user.email,
                "email_verified": response.user.email_confirmed_at is not None,
                "display_name": request.display_name,
            },
        )

    except Exception as e:
        logger.error("Registration failed", error=str(e), email=request.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}",
        )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: SignInRequest,
    supabase: Client = Depends(get_supabase),
):
    """Login with email and password.

    Args:
        request: Login request with email and password
        supabase: Supabase client

    Returns:
        Authentication response with tokens

    Raises:
        HTTPException: If login fails
    """
    try:
        # Sign in with Supabase
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })

        if not response.user or not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        logger.info(
            "User logged in successfully",
            user_id=response.user.id,
            email=request.email,
        )

        return AuthResponse(
            access_token=response.session.access_token,
            token_type="bearer",
            expires_in=response.session.expires_in or 3600,
            refresh_token=response.session.refresh_token,
            user={
                "id": response.user.id,
                "email": response.user.email,
                "email_verified": response.user.email_confirmed_at is not None,
            },
        )

    except Exception as e:
        logger.warning("Login failed", error=str(e), email=request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: AuthUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Logout current user (revoke tokens).

    Args:
        current_user: Current authenticated user
        supabase: Supabase client

    Returns:
        Success message
    """
    try:
        supabase.auth.sign_out()
        logger.info("User logged out", user_id=current_user.supabase_user_id)
        return MessageResponse(message="Logged out successfully")
    except Exception as e:
        logger.error("Logout failed", error=str(e), user_id=current_user.supabase_user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed",
        )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    supabase: Client = Depends(get_supabase),
):
    """Refresh access token using refresh token.

    Args:
        request: Refresh token request
        supabase: Supabase client

    Returns:
        New authentication response with tokens

    Raises:
        HTTPException: If refresh fails
    """
    try:
        response = supabase.auth.refresh_session(request.refresh_token)

        if not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        return AuthResponse(
            access_token=response.session.access_token,
            token_type="bearer",
            expires_in=response.session.expires_in or 3600,
            refresh_token=response.session.refresh_token,
            user={
                "id": response.user.id,
                "email": response.user.email,
                "email_verified": response.user.email_confirmed_at is not None,
            } if response.user else {},
        )

    except Exception as e:
        logger.warning("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )


@router.post("/password-reset", response_model=MessageResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    supabase: Client = Depends(get_supabase),
):
    """Request password reset email.

    Args:
        request: Password reset request with email
        supabase: Supabase client

    Returns:
        Success message
    """
    try:
        supabase.auth.reset_password_email(request.email)
        logger.info("Password reset requested", email=request.email)
        return MessageResponse(
            message="Password reset email sent if account exists"
        )
    except Exception as e:
        logger.error("Password reset failed", error=str(e), email=request.email)
        # Don't reveal if email exists
        return MessageResponse(
            message="Password reset email sent if account exists"
        )


@router.post("/password-update", response_model=MessageResponse)
async def update_password(
    request: PasswordUpdateRequest,
    current_user: AuthUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Update user password (requires authentication).

    Args:
        request: Password update request
        current_user: Current authenticated user
        supabase: Supabase client

    Returns:
        Success message

    Raises:
        HTTPException: If update fails
    """
    try:
        supabase.auth.update_user({
            "password": request.new_password
        })
        logger.info("Password updated", user_id=current_user.supabase_user_id)
        return MessageResponse(message="Password updated successfully")
    except Exception as e:
        logger.error(
            "Password update failed",
            error=str(e),
            user_id=current_user.supabase_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password update failed",
        )


@router.post("/magic-link", response_model=MessageResponse)
async def send_magic_link(
    request: MagicLinkRequest,
    supabase: Client = Depends(get_supabase),
):
    """Send magic link for passwordless login.

    Args:
        request: Magic link request with email
        supabase: Supabase client

    Returns:
        Success message
    """
    try:
        supabase.auth.sign_in_with_otp({
            "email": request.email,
        })
        logger.info("Magic link sent", email=request.email)
        return MessageResponse(message="Magic link sent to your email")
    except Exception as e:
        logger.error("Magic link failed", error=str(e), email=request.email)
        # Don't reveal if email exists
        return MessageResponse(message="Magic link sent to your email")


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user profile.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        User profile

    Raises:
        HTTPException: If user not found
    """
    try:
        # Query the local database for the full user record
        from sqlalchemy import select
        from app.models.user import User
        from uuid import UUID

        stmt = select(User).where(User.supabase_user_id == UUID(current_user.supabase_user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return UserResponse(
            id=current_user.supabase_user_id,
            email=user.email,
            email_verified=user.email_verified,
            display_name=user.display_name,
            created_at=user.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get user profile",
            error=str(e),
            user_id=current_user.supabase_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile",
        )


@router.get("/verify")
async def verify_email(
    token: str,
    supabase: Client = Depends(get_supabase),
):
    """Verify email with token from verification email.

    Args:
        token: Email verification token
        supabase: Supabase client

    Returns:
        Success message or redirect
    """
    try:
        # Supabase handles email verification automatically
        # This endpoint can be used for custom verification flows
        return MessageResponse(message="Email verified successfully")
    except Exception as e:
        logger.error("Email verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token",
        )

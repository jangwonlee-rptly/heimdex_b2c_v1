"""Supabase client and authentication utilities."""

from typing import Optional
from supabase import create_client, Client
from app.config import settings
from app.logging_config import logger


class SupabaseClient:
    """Singleton Supabase client for authentication and user management."""

    _instance: Optional[Client] = None

    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client instance.

        Returns:
            Supabase client instance
        """
        if cls._instance is None:
            try:
                cls._instance = create_client(
                    supabase_url=settings.supabase_url,
                    supabase_key=settings.supabase_key,
                )
                logger.info(
                    "Supabase client initialized",
                    supabase_url=settings.supabase_url,
                )
            except Exception as e:
                logger.error("Failed to initialize Supabase client", error=str(e))
                raise

        return cls._instance

    @classmethod
    def get_admin_client(cls) -> Client:
        """Get Supabase client with admin privileges.

        Returns:
            Supabase client with service role key

        Raises:
            ValueError: If service role key is not configured
        """
        if not settings.supabase_service_role_key:
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY not configured. "
                "Required for admin operations."
            )

        try:
            admin_client = create_client(
                supabase_url=settings.supabase_url,
                supabase_key=settings.supabase_service_role_key,
            )
            logger.info("Supabase admin client initialized")
            return admin_client
        except Exception as e:
            logger.error("Failed to initialize Supabase admin client", error=str(e))
            raise


def get_supabase() -> Client:
    """Dependency injection helper for FastAPI routes.

    Returns:
        Supabase client instance
    """
    return SupabaseClient.get_client()

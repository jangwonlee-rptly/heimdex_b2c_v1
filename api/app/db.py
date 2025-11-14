"""Database connection and session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from fastapi import HTTPException
from app.config import settings
from app.logging_config import logger

# Convert postgres:// to postgresql+asyncpg://
DATABASE_URL = settings.postgres_url.replace("postgresql://", "postgresql+asyncpg://")

# Create async engine
if settings.debug:
    # NullPool for debug mode - no pooling parameters needed
    engine = create_async_engine(
        DATABASE_URL,
        echo=True,
        poolclass=NullPool,
    )
else:
    # QueuePool for production with connection pooling
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for declarative models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session.

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except HTTPException:
            # HTTPExceptions are application-level errors (auth, validation, etc.)
            # Rollback any uncommitted changes but don't log as database error
            await session.rollback()
            raise
        except Exception as e:
            # Actual database or unexpected errors
            await session.rollback()
            logger.error("Database session error", error=str(e), exc_info=True)
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database connection and create tables if needed."""
    try:
        async with engine.begin() as conn:
            # Test connection
            await conn.execute(text("SELECT 1"))
            logger.info("Database connection established", url=DATABASE_URL.split("@")[1])
    except Exception as e:
        logger.error("Failed to connect to database", error=str(e), exc_info=True)
        raise


async def close_db():
    """Close database connection pool."""
    await engine.dispose()
    logger.info("Database connection closed")

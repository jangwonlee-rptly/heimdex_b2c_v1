"""Main FastAPI application for Heimdex B2C."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import make_asgi_app
from app.config import settings
from app.db import init_db, close_db
from app.logging_config import logger
# Import routers
from app.auth.routes import router as auth_router
from app.video.routes import router as video_router
from app.search.routes import router as search_router
from app.people.routes import router as people_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Heimdex B2C API", version="0.1.0")
    await init_db()
    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Heimdex B2C API")
    await close_db()
    logger.info("Application shutdown complete")


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title="Heimdex B2C API",
    description="Video semantic search platform with open-source models",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.warning(
        "Validation error",
        path=request.url.path,
        errors=exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "features": {
            "vision": settings.feature_vision,
            "face": settings.feature_face,
        }
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Heimdex B2C API",
        "version": "0.1.0",
        "docs": "/docs" if settings.debug else None,
    }


# Mount Prometheus metrics endpoint
if settings.enable_prometheus:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(video_router, prefix="/videos", tags=["Videos"])
app.include_router(search_router, prefix="/search", tags=["Search"])
app.include_router(people_router, prefix="/people", tags=["People"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )

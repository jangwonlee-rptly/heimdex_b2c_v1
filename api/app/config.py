"""Application configuration using Pydantic settings."""

from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    postgres_url: str = Field(..., description="PostgreSQL connection URL")
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "heimdex"
    postgres_user: str = "heimdex"
    postgres_password: str = Field(..., description="PostgreSQL password")

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Object Storage
    storage_backend: Literal["minio", "gcs"] = "minio"
    minio_endpoint: str = "localhost:9000"
    minio_external_endpoint: str = "localhost:9000"  # Endpoint accessible from browser
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False

    # GCS settings (prod)
    gcs_project_id: Optional[str] = None
    gcs_bucket_uploads: str = "heimdex-uploads"
    gcs_bucket_sidecars: str = "heimdex-sidecars"
    gcs_bucket_tmp: str = "heimdex-tmp"

    # Bucket names
    storage_bucket_uploads: str = "uploads"
    storage_bucket_sidecars: str = "sidecars"
    storage_bucket_thumbnails: str = "thumbnails"
    storage_bucket_tmp: str = "tmp"

    # Supabase Authentication (optional for local dev, required for production)
    supabase_url: Optional[str] = Field(None, description="Supabase project URL")
    supabase_key: Optional[str] = Field(None, description="Supabase anon/public key")
    supabase_service_role_key: Optional[str] = Field(None, description="Supabase service role key (for admin operations)")
    supabase_jwt_secret: Optional[str] = Field(None, description="Supabase JWT secret for token verification")

    # Legacy JWT settings (kept for backwards compatibility if needed)
    jwt_secret_key: Optional[str] = Field(None, min_length=32, description="Legacy JWT secret key (min 32 chars)")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_issuer: str = "heimdex-b2c"
    jwt_audience: str = "heimdex-users"

    # Optional RS256 keys
    jwt_private_key_path: Optional[str] = None
    jwt_public_key_path: Optional[str] = None

    # Password hashing (Argon2id) - deprecated, now handled by Supabase
    password_hash_time_cost: int = 2
    password_hash_memory_cost: int = 65536  # 64 MB
    password_hash_parallelism: int = 4

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = "noreply@heimdex.example"
    smtp_password: Optional[str] = None
    smtp_from: str = "Heimdex <noreply@heimdex.example>"
    smtp_tls: bool = True

    # Application URLs
    api_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"

    # Feature Flags
    feature_vision: bool = True
    feature_face: bool = False
    feature_face_licensed: bool = False
    feature_face_enrollment: bool = False  # Enable people profile photo upload
    feature_face_detection: bool = False  # Enable face detection in video processing
    feature_semantic_search: bool = False  # Enable vector similarity search
    feature_email_verification: bool = False

    # Systems-level feature flags for search quality
    feature_search_sys_ann_tuning: bool = False  # Enable HNSW indexes and tuned ANN params
    feature_search_sys_hybrid_rrf: bool = False  # Enable BM25 + vector RRF fusion
    feature_search_sys_canonical_trim: bool = False  # Enable text normalization before embedding
    feature_search_sys_eval: bool = False  # Enable search metrics and golden query evaluation

    # ML Models
    asr_model: Literal["tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "turbo"] = "medium"
    asr_device: Literal["cpu", "cuda"] = "cpu"
    text_model: str = "bge-m3"
    text_embedding_dim: int = 1024
    vision_model: Literal["openclip", "siglip", "siglip2"] = "siglip"
    vision_embedding_dim: int = 1152  # SigLIP so400m has 1152 dimensions
    face_embedding_dim: int = 512

    # Video Processing
    max_video_duration_seconds: int = 600  # 10 minutes
    max_video_size_bytes: int = 1073741824  # 1 GB
    allowed_video_mimes: str = "video/mp4,video/quicktime,video/x-matroska,video/webm"

    @field_validator("allowed_video_mimes")
    @classmethod
    def parse_allowed_mimes(cls, v: str) -> list[str]:
        """Parse comma-separated MIME types into a list."""
        return [mime.strip() for mime in v.split(",")]

    # Rate Limits & Quotas
    free_tier_uploads_per_day: int = 3
    free_tier_search_per_minute: int = 60
    rate_limit_per_ip_requests: int = 100
    rate_limit_per_ip_window_seconds: int = 300  # 5 minutes
    rate_limit_per_user_requests: int = 60
    rate_limit_per_user_window_seconds: int = 60  # 1 minute

    # Search Configuration
    search_max_results: int = 50
    search_default_results: int = 20
    search_text_weight: float = 0.5
    search_vision_weight: float = 0.35
    search_tag_weight: float = 0.15
    search_person_boost: float = 0.3
    signed_url_expire_seconds: int = 600  # 10 minutes

    # ANN Search Tuning (FEATURE_SEARCH_SYS_ANN_TUNING)
    search_ann_ef_search: int = 100  # HNSW query breadth (higher = better recall, slower)
    search_ann_client_topk: int = 200  # Fetch N candidates for re-ranking (topK before fusion)
    search_ann_final_limit: int = 20  # Final results after re-ranking

    # Hybrid Search - RRF Fusion (FEATURE_SEARCH_SYS_HYBRID_RRF)
    search_hybrid_bm25_weight: float = 0.3  # BM25 sparse retrieval weight
    search_hybrid_vector_weight: float = 0.7  # Vector dense retrieval weight
    search_hybrid_rrf_k: int = 60  # RRF constant (typical range: 20-100)

    # Canonical Text Normalization (FEATURE_SEARCH_SYS_CANONICAL_TRIM)
    search_canonical_max_tokens: int = 512  # Max tokens before embedding
    search_canonical_field_order: str = "transcript,tags,persons"  # Field priority for text

    # Observability
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    enable_opentelemetry: bool = False
    otel_exporter_otlp_endpoint: Optional[str] = None
    enable_prometheus: bool = True
    prometheus_port: int = 9090
    sentry_dsn: Optional[str] = None
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.1

    # Development
    debug: bool = False
    reload: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> list[str]:
        """Parse comma-separated origins into a list."""
        return [origin.strip() for origin in v.split(",")]

    # GCP (Production)
    gcp_project_id: Optional[str] = None
    gcp_region: str = "us-central1"
    cloud_sql_connection_name: Optional[str] = None
    secret_manager_project_id: Optional[str] = None

    # Model Paths (Local)
    models_dir: str = "./models"


# Global settings instance
settings = Settings()

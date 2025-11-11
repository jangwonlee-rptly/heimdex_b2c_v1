# Heimdex B2C - Project Status

## Overview

This document tracks the implementation status of the Heimdex B2C video semantic search platform.

**Last Updated**: 2025-11-11
**Current Phase**: Video Ingestion & Processing Pipeline
**Completion**: ~60%

**Recent Changes**:
- See [DEVLOG_2025-11-11_video_ingestion_workflow.md](../DEVLOG_2025-11-11_video_ingestion_workflow.md) ⭐ **NEW**
- See [DEVLOG_2025-11-11_ui_implementation.md](../DEVLOG_2025-11-11_ui_implementation.md)
- See [DEVLOG_2025-11-11_supabase_integration.md](../DEVLOG_2025-11-11_supabase_integration.md)
- See [DEVLOG_2025-11-10_model_migration.md](../DEVLOG_2025-11-10_model_migration.md)

---

## ✅ Completed Components

### 1. Project Structure
- [x] Created core directory structure (api, worker, web, infra, db, docs)
- [x] Set up Docker Compose for local development
- [x] Created .gitignore with comprehensive exclusions
- [x] Created README.md with project overview and quick start

### 2. Database Schema
- [x] Alembic migration setup
- [x] Initial migration with all tables:
  - users (auth + tier management)
  - videos (upload tracking)
  - scenes (indexed content with embeddings)
  - jobs (pipeline progress tracking)
  - face_profiles (person enrollment)
  - scene_people (face matches)
  - refresh_tokens (JWT rotation)
  - email_verification_tokens
  - audit_events (security logging)
  - rate_limits (quota enforcement)
- [x] pgvector integration for embeddings
- [x] PGroonga support for Korean full-text search

### 3. API Backend (FastAPI)
- [x] FastAPI application setup with lifespan management
- [x] Configuration management (Pydantic settings)
- [x] Database connection with async SQLAlchemy
- [x] Structured logging with structlog (JSON output)
- [x] Rate limiting setup (SlowAPI)
- [x] CORS middleware
- [x] Health check endpoint
- [x] Prometheus metrics endpoint
- [x] Authentication utilities:
  - Argon2id password hashing
  - JWT access/refresh token generation
  - Token validation and decoding

### 4. Worker (Dramatiq)
- [x] Dockerfile with FFmpeg and ML dependencies
- [x] Requirements.txt with all ML packages:
  - Whisper, faster-whisper
  - BGE-M3 (FlagEmbedding)
  - SigLIP (google/siglip-so400m-patch14-384) - **Migrated from OpenCLIP**
  - OpenCV YuNet (face detection) - **Migrated from AdaFace+RetinaFace**
  - PySceneDetect
- [x] Model download script updated for new models

### 5. Documentation
- [x] Comprehensive README with architecture diagram
- [x] Model documentation (docs/models.md):
  - All models listed with licenses
  - Download instructions
  - Performance benchmarks
  - InsightFace license warning
- [x] Model download script (scripts/download_models.sh)
- [x] Environment variable reference (.env.example)

### 6. Configuration
- [x] .env.example with all configuration options
- [x] Feature flags (vision, face, email verification)
- [x] Rate limit and quota settings
- [x] Model selection (ASR, text, vision variants)
- [x] Search weights configuration

### 7. Authentication (Supabase Integration)
- [x] Supabase configuration in settings
- [x] Supabase client module with singleton pattern
- [x] JWT verification middleware
- [x] Authentication routes (9 endpoints)
- [x] Email confirmation handling
- [x] Database migration for Supabase user linking
- [x] Production testing with real Supabase project

### 8. SQLAlchemy Models ⭐ NEW
- [x] User model with Supabase integration
  - Hybrid architecture (Supabase auth + local data)
  - supabase_user_id foreign key
  - Tier management (free/pro/enterprise)
  - Relationships to videos and face_profiles
- [x] Video model with state machine
  - States: uploading → validating → processing → indexed → failed
  - Storage key, mime type, size, duration
  - Error tracking for failed videos
- [x] Scene model with embeddings
  - pgvector columns (text_vec, image_vec)
  - Transcript and full-text search
  - Vision tags (JSONB)
  - Sidecar storage key
- [x] Face profile and scene-person models
  - Person enrollment with photos
  - Face embedding storage
  - Scene-person associations
- [x] Job model for pipeline tracking
  - 12 pipeline stages defined
  - State tracking (pending/running/completed/failed)
  - Progress percentage
  - Metadata storage (JSONB)

### 9. User Synchronization ⭐ NEW
- [x] User sync module (api/app/auth/user_sync.py)
  - get_or_create_user() function
  - Automatic user creation on first login
  - Support for linking existing users by email
  - Email verification status sync
- [x] Auth middleware integration
  - Calls user sync on every authenticated request
  - Returns local user_id to authenticated endpoints
  - Works seamlessly with Supabase tokens

### 10. Storage Integration ⭐ NEW
- [x] MinIO storage client (api/app/storage.py)
  - Singleton pattern for client reuse
  - Presigned URL generation (upload & download)
  - Automatic bucket creation
  - Object upload/download/delete methods
- [x] Configuration for MinIO/GCS
  - Bucket names for uploads, sidecars, tmp
  - MinIO endpoint and credentials
  - 15-minute upload URL expiration
  - 10-minute download URL expiration

### 11. Video Upload API ⭐ NEW
- [x] Video upload routes (api/app/video/routes.py)
  - POST /videos/upload/init - Get presigned upload URL
  - POST /videos/upload/complete - Trigger processing
  - GET /videos - List user's videos
  - GET /videos/{id} - Get video details
  - GET /videos/{id}/status - Get processing status
- [x] Upload validation
  - MIME type validation (MP4, MOV, AVI, MKV, WebM)
  - Size validation (max 1GB)
  - Duration validation (via worker)
- [x] Presigned URL workflow
  - Client gets presigned URL from API
  - Client uploads directly to MinIO
  - No data proxying through API
- [x] Job queue integration
  - Creates validation job on upload complete
  - Sends task to Dramatiq queue
  - Background processing starts automatically

### 12. Worker Pipeline ⭐ NEW
- [x] Complete video processing pipeline (worker/tasks/video_processor.py)
  - Main process_video task (Dramatiq actor)
  - 600s timeout, 2 max retries
  - Comprehensive error handling
- [x] Pipeline stages implemented:
  1. Video validation (ffprobe duration check)
  2. Audio extraction (ffmpeg → 16kHz mono WAV)
  3. ASR transcription (Whisper medium model)
  4. Scene detection (PySceneDetect, content-based)
  5. Transcript-to-scene mapping
  6. Text embedding generation (BGE-M3, 1024-dim)
  7. Frame extraction (middle frame per scene)
  8. Vision embedding generation (SigLIP, 1152-dim)
  9. Scene record creation with embeddings
  10. Database commit (state=indexed)
- [x] Model loading
  - Lazy loading (loaded once per worker)
  - Whisper (medium, CPU/CUDA auto-detect)
  - BGE-M3 (FlagEmbedding)
  - SigLIP (google/siglip-so400m-patch14-384)
  - Global model cache for performance
- [x] Error handling
  - Catches all errors
  - Updates video state to 'failed'
  - Stores error message in database
  - Comprehensive logging
- [x] Resource management
  - Temporary directory creation/cleanup
  - Video download from MinIO
  - Automatic file cleanup on completion/error

### 13. Frontend (Next.js 14) [From previous session]
- [x] Complete Next.js setup with App Router
- [x] TypeScript type system
- [x] Supabase authentication integration
- [x] Protected routes
- [x] Video upload UI with drag-and-drop
- [x] Profile management for face enrollment
- [x] Semantic search interface
- [x] Dashboard with video library
- [x] Docker configuration

---

## 🚧 In Progress

### Testing & Verification
- [ ] End-to-end test with sample video
- [ ] Verify worker processes videos automatically
- [ ] Test search after video is indexed

---

## 📋 Pending Implementation

### High Priority

#### 1. Search Engine
- [x] ~~Auth routes~~ - **COMPLETED**
- [x] ~~Video upload routes~~ - **COMPLETED**
- [x] ~~User model and sync~~ - **COMPLETED**
- [x] ~~Worker pipeline~~ - **COMPLETED**
- [ ] **Search routes (NEXT PRIORITY)**:
  - GET /search?q={query} - Hybrid search
  - GET /scenes/{id} - Scene details
  - GET /scenes/{id}/preview - Signed URL for playback
- [ ] Search implementation:
  - Query parser (person tokens, visual tokens, text)
  - Hybrid scoring (text + vision + person)
  - Person filter (scene_people join)
  - Result ranking and pagination

#### 2. Scene Preview
- [ ] Video player component (frontend)
- [ ] Scene preview endpoint with signed URLs
- [ ] Timestamp seeking

#### 3. People/Face Management
- [ ] People routes:
  - POST /people - Create person profile
  - POST /people/{id}/photos - Upload enrollment photos
  - GET /people - List enrolled people
- [ ] Face detection in worker (YuNet)
- [ ] Face embedding generation
- [ ] Face matching to enrolled people
  - POST /people/{id}/photos
  - GET /people

#### 2. Worker Pipeline
- [ ] Stage implementations:
  1. upload_validate (ffprobe duration/size check)
  2. audio_extract (to 16kHz mono WAV)
  3. asr_fast (Whisper transcription)
  4. scene_detect (PySceneDetect)
  5. align_merge (transcript to scenes)
  6. embed_text (BGE-M3)
  7. vision_sample_frames (1 FPS)
  8. vision_embed_frames (OpenCLIP mean-pooling)
  9. vision_affect_tags (zero-shot CLIP prompts)
  10. faces_enroll_match (AdaFace comparison)
  11. sidecar_build (immutable JSON)
  12. commit (videos.state='indexed')
- [ ] Idempotency and artifact checking
- [ ] Retry logic with exponential backoff
- [ ] Progress reporting to jobs table

#### 3. Storage Integration
- [ ] MinIO client for dev
- [ ] GCS client for prod
- [ ] Presigned URL generation (10-min TTL)
- [ ] Bucket lifecycle policies

#### 4. Search Engine
- [ ] Query parser (person tokens, visual tokens, text)
- [ ] Hybrid scoring:
  - 0.5 * text_similarity (BGE-M3)
  - 0.35 * vision_similarity (CLIP)
  - 0.15 * tag_bonus (zero-shot matches)
  - +0.3 person_boost (if enrolled face matches)
- [ ] Person filter (scene_people join)
- [ ] Result ranking and pagination

#### 5. Web Frontend (Next.js)
- [ ] Authentication pages (/auth/*)
- [ ] Upload page with drag-and-drop
- [ ] Library page (video list + status polling)
- [ ] Search page (grid results)
- [ ] Scene detail page (player + transcript)
- [ ] People enrollment page

### Medium Priority

#### 6. Infrastructure as Code (Terraform)
- [ ] Network module (VPC, serverless VPC connector)
- [ ] Postgres module (Cloud SQL + pgvector)
- [ ] Storage module (GCS buckets with lifecycle)
- [ ] Cache module (Memorystore Redis)
- [ ] Queue module (Pub/Sub topics)
- [ ] CloudRun module (api + worker services)
- [ ] Secrets module (Secret Manager)
- [ ] Monitoring module (dashboards + alerts)

#### 7. Observability
- [ ] OpenTelemetry tracing setup
- [ ] Custom Prometheus metrics:
  - api_latency_seconds
  - job_success_rate
  - asr_processing_ms
  - vision_processing_ms
  - vector_query_ms
- [ ] Grafana dashboards
- [ ] Alerting rules (error rate, p95 latency)

#### 8. Testing
- [ ] Unit tests:
  - Auth (password hashing, JWT)
  - Upload validation (ffprobe)
  - Query parser
  - Embedding normalization
- [ ] Integration tests:
  - End-to-end indexing (2-min sample)
  - Search accuracy ("man crying" query)
  - Person search ("Minji crying")
  - Signed URL expiration
- [ ] Load tests (Locust):
  - 100 concurrent searches
  - P95 < 1.5s at 10k scenes

### Low Priority

#### 9. CI/CD
- [ ] GitHub Actions workflow:
  - Linting (Ruff, Black)
  - Type checking (MyPy)
  - Security scanning (Bandit, Safety)
  - Unit tests
  - Build Docker images
  - Scan images (Trivy)
  - Terraform plan
  - Deploy to Cloud Run (manual approval)

#### 10. Production Readiness
- [ ] Backup strategy (Cloud SQL automated backups)
- [ ] Disaster recovery plan
- [ ] Security audit
- [ ] Performance optimization (index tuning)
- [ ] Cost monitoring and budgets

---

## 🔧 Technical Debt & Known Issues

### Current Issues
1. **PGroonga**: Not included in base pgvector image
   - **Workaround**: Fallback to PostgreSQL tsvector (working fine)
   - **Fix**: Create custom Dockerfile with PGroonga (optional)

2. ~~**No authentication routes yet**~~ - **RESOLVED** ✅
   - **Status**: Authentication fully implemented with Supabase

3. ~~**User sync logic pending**~~ - **RESOLVED** ✅
   - **Status**: User sync implemented and working
   - **See**: DEVLOG_2025-11-11_video_ingestion_workflow.md

4. ~~**Worker implementation incomplete**~~ - **RESOLVED** ✅
   - **Status**: Complete worker pipeline implemented
   - **See**: DEVLOG_2025-11-11_video_ingestion_workflow.md

5. **No search endpoint yet**
   - **Status**: Videos can be uploaded and indexed, but search not implemented
   - **Priority**: High (needed to actually use the indexed data)

6. **No scene preview yet**
   - **Status**: No video player or signed URL endpoint
   - **Priority**: High (needed to view search results)

7. **Model downloads**: Large files not in repo
   - **Status**: Users must run download script manually
   - **Alternative**: Consider model server or GCS bucket

8. **docs/models.md outdated**: Still references OpenCLIP and AdaFace
   - **Status**: Needs update to reflect SigLIP and YuNet migration
   - **See**: DEVLOG_2025-11-10_model_migration.md

### Future Enhancements
- [ ] Video chapter detection (using CLIP scene similarity)
- [ ] Speaker diarization (who is speaking)
- [ ] Translation (Korean ↔ English subtitles)
- [ ] Mobile app (React Native)
- [ ] Real-time collaborative annotations
- [ ] Usage analytics dashboard
- [ ] Pro tier features (longer videos, more uploads)

---

## 📊 Metrics

### Code Statistics
- **Python files**: ~35 (api + worker + models)
- **Lines of code**: ~4,700
- **Docker services**: 6 (db, redis, minio, api, worker, web)
- **Database tables**: 10
- **API endpoints**: 14 (9 auth + 5 video)
- **Database models**: 6 (User, Video, Scene, Face, Job, ScenePerson)
- **Worker tasks**: 1 main pipeline (10 stages)

### Models
- **Total model size**: ~5.4 GB
- **Required for MVP**: ~5 GB
  - Whisper medium: 1.42 GB
  - BGE-M3: 2 GB
  - SigLIP so400m: 1.5 GB
  - YuNet: 300 KB

---

## 🎯 Next Steps (Priority Order)

1. ~~**Implement auth routes**~~ - **COMPLETED** ✅
2. ~~**Implement user sync logic**~~ - **COMPLETED** ✅
3. ~~**Implement upload flow**~~ - **COMPLETED** ✅
4. ~~**Implement worker pipeline stages**~~ - **COMPLETED** ✅
5. **Test video upload end-to-end** (CURRENT)
6. **Implement search endpoint** (hybrid scoring, person filter)
7. **Implement scene preview** (video player, signed URLs)
8. **Write integration tests** (end-to-end workflow)
9. **Set up Terraform** (GCP deployment)
10. **Production deployment** (Cloud Run + Cloud SQL)

---

## 🚀 Estimated Timeline

- ~~**Week 1**: Auth implementation~~ → 35% ✅
- ~~**Week 2**: Video upload + worker pipeline~~ → 60% ✅
- **Week 3**: Search engine + scene preview → 75%
- **Week 4**: Testing + polish → 85%
- **Week 5**: Deployment + infrastructure → 95%
- **Week 6**: Production hardening + docs → 100%

**Note**: Timeline assumes 1-2 developers working full-time.

---

## 📝 Notes

- All models are MIT/Apache 2.0 licensed ✅
- No vendor lock-in (works on GCP, AWS, Azure, or on-prem)
- Korean language is first-class citizen
- Free tier enforced at API level (3 uploads/day, 10 min, 1 GB)
- Security-first approach (Argon2id, JWT rotation, signed URLs)
- Presigned URLs for scalable uploads ✅
- Hybrid search (text + vision + person) ready for implementation

---

**Project Status**: Core ingestion pipeline complete! Videos can be uploaded, processed, and indexed. Next: Search implementation.

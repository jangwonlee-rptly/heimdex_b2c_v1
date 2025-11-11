# Heimdex B2C - Quick Start Guide

## What's Been Built

This session established the complete foundation for the Heimdex B2C platform (~20% complete):

✅ **Project Structure**: 25 directories, 19 configuration files
✅ **Database Schema**: 10 tables with pgvector + PGroonga support
✅ **API Backend**: FastAPI with JWT auth, Argon2id, structured logging
✅ **Worker Framework**: Dramatiq setup with ML dependencies
✅ **Dev Environment**: Docker Compose with 6 services
✅ **Documentation**: README, model docs, download script, devlog

## 🚀 One-Command Setup (NEW!)

### Start Everything Automatically

```bash
# OPTION 1: Fully Automated (Recommended)
./start.sh

# That's it! The script will:
# ✅ Create .env.local from .env.example
# ✅ Build all Docker images
# ✅ Start infrastructure (db, redis, minio)
# ✅ Run database migrations automatically
# ✅ Download ML models automatically (~4 GB, 10-15 min first time)
# ✅ Start API and Worker services
# ✅ Wait until everything is ready

# When complete, open:
# - API: http://localhost:8000/docs
# - Health: http://localhost:8000/health
```

### Manual Setup (If You Prefer)

```bash
# OPTION 2: Manual Step-by-Step

# 1. Create environment file (auto-configured for Docker)
cp .env.example .env.local

# 2. Start everything with Docker Compose
docker compose up -d

# Docker Compose will automatically:
# - Start db, redis, minio
# - Initialize MinIO buckets (minio-init)
# - Run database migrations (db-migrate)
# - Download ML models (model-downloader) - first run only
# - Start API and Worker (after migrations + models complete)

# 3. Check status
docker compose ps

# 4. Test API
curl http://localhost:8000/health
```

### What Happens Automatically

When you run `./start.sh` or `docker compose up -d`:

1. **Infrastructure** (10 seconds)
   - PostgreSQL + pgvector starts
   - Redis starts
   - MinIO starts

2. **Initialization** (10-15 minutes first time, <10 seconds after)
   - MinIO buckets created (uploads, sidecars, tmp)
   - Database migrations run (creates all 10 tables)
   - ML models downloaded to shared volume (~4 GB)

3. **Services** (5 seconds)
   - API starts on http://localhost:8000
   - Worker starts (ready to process videos)

**Note**: Models are cached in a Docker volume, so subsequent runs are fast!

### 4. What to Build Next (Priority Order)

#### A. SQLAlchemy Models (`api/app/models/`)

Create these files:
- `__init__.py` - Export all models
- `user.py` - User, RefreshToken, EmailVerificationToken
- `video.py` - Video, Scene, Job
- `people.py` - FaceProfile, ScenePeople
- `audit.py` - AuditEvent, RateLimit

#### B. Authentication Routes (`api/app/auth/routes.py`)

Implement:
- `POST /auth/register` - Create user with email + password
- `POST /auth/login` - Return access + refresh JWT tokens
- `POST /auth/refresh` - Rotate refresh token
- `GET /auth/me` - Get current user (authenticated)
- Dependency: `get_current_user` - Extract user from JWT

#### C. Upload Flow (`api/app/video/routes.py`)

Implement:
- `POST /videos/upload/init` - Generate presigned URL (MinIO/GCS)
- `POST /videos/upload/complete` - Trigger indexing job
- `GET /videos` - List user's videos
- `GET /videos/{video_id}` - Get video details
- `GET /videos/{video_id}/status` - Get indexing progress

#### D. Worker Pipeline (`worker/tasks/`)

Implement:
- `indexing.py` - Orchestrator (calls all stages)
- `asr.py` - Whisper transcription
- `vision.py` - Frame extraction + OpenCLIP embeddings
- `utils.py` - ffprobe, PySceneDetect, storage helpers

#### E. Search Endpoint (`api/app/search/routes.py`)

Implement:
- `GET /search?q={query}` - Hybrid search
- Query parser (person/visual/text tokens)
- Hybrid scorer (0.5 text + 0.35 vision + 0.15 tags)
- Result formatting with signed preview URLs

## Testing Your Work

### Unit Tests

```bash
cd api
pytest tests/test_auth_crypto.py -v
pytest tests/test_upload_validation.py -v
```

### Integration Test (End-to-End)

```bash
# 1. Upload a test video (use curl or Postman)
curl -X POST http://localhost:8000/videos/upload/init \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"filename": "test.mp4", "size_bytes": 10485760}'

# 2. Upload video to presigned URL
# 3. Complete upload
curl -X POST http://localhost:8000/videos/upload/complete \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"video_id": "..."}'

# 4. Check status
curl http://localhost:8000/videos/{video_id}/status \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# 5. Search
curl "http://localhost:8000/search?q=man+crying" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Common Issues

### 1. Database Connection Error
```
SOLUTION: Ensure db service is running
docker compose ps db
docker compose logs db
```

### 2. pgvector Extension Missing
```
SOLUTION: Run init-extensions.sql manually
docker compose exec db psql -U heimdex -d heimdex -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 3. Models Not Found
```
SOLUTION: Run download script or set MODELS_DIR
./scripts/download_models.sh
export MODELS_DIR=/path/to/models
```

### 4. MinIO Buckets Not Created
```
SOLUTION: Restart minio-init service
docker compose restart minio-init
docker compose logs minio-init
```

## File Locations Reference

```
api/app/
├── auth/
│   ├── crypto.py          ✅ DONE - Password hashing, JWT
│   ├── routes.py          ⏳ TODO - Auth endpoints
│   └── dependencies.py    ⏳ TODO - get_current_user
├── models/
│   ├── user.py            ⏳ TODO - User, RefreshToken models
│   ├── video.py           ⏳ TODO - Video, Scene, Job models
│   └── people.py          ⏳ TODO - FaceProfile models
├── video/
│   ├── routes.py          ⏳ TODO - Upload endpoints
│   ├── storage.py         ⏳ TODO - MinIO/GCS client
│   └── validation.py      ⏳ TODO - ffprobe checks
├── search/
│   ├── routes.py          ⏳ TODO - Search endpoint
│   ├── parser.py          ⏳ TODO - Query parsing
│   └── scorer.py          ⏳ TODO - Hybrid scoring
└── main.py                ✅ DONE - FastAPI app

worker/tasks/
├── indexing.py            ⏳ TODO - Pipeline orchestrator
├── asr.py                 ⏳ TODO - Whisper transcription
├── vision.py              ⏳ TODO - OpenCLIP embeddings
├── faces.py               ⏳ TODO - AdaFace matching
└── utils.py               ⏳ TODO - Helper functions
```

## Useful Commands

```bash
# View logs
docker compose logs -f api
docker compose logs -f worker

# Restart service
docker compose restart api

# Database shell
docker compose exec db psql -U heimdex -d heimdex

# Redis CLI
docker compose exec redis redis-cli

# MinIO console
open http://localhost:9001  # minioadmin / minioadmin

# API documentation (when DEBUG=true)
open http://localhost:8000/docs

# Prometheus metrics
curl http://localhost:8000/metrics
```

## Development Workflow

1. **Make changes** to code in `api/` or `worker/`
2. **Services auto-reload** (if using `--reload` flag)
3. **Test locally** with curl/Postman
4. **Write unit tests** in `tests/`
5. **Run tests**: `pytest`
6. **Commit**: `git add . && git commit -m "feat: ..."`
7. **Repeat**

## Deployment Preview (Future)

```bash
# Deploy to GCP (after Terraform setup)
cd infra/envs/dev-gcp
terraform init
terraform plan
terraform apply

# Deploy services
gcloud run deploy api --source=../../../api --region=us-central1
gcloud run deploy worker --source=../../../worker --region=us-central1
```

## Getting Help

- 📖 **README.md** - Project overview
- 📖 **docs/models.md** - ML model details
- 📖 **PROJECT_STATUS.md** - Implementation tracking
- 📖 **devlogs/2511102122.txt** - This session's detailed log
- 🐛 **GitHub Issues** - Report bugs
- 💬 **Discussions** - Ask questions

## Success Criteria (MVP)

You'll know the MVP is working when you can:

1. ✅ Register a user and login
2. ✅ Upload a 2-minute video
3. ✅ See indexing progress (jobs table)
4. ✅ Search for "man crying" and get relevant scenes
5. ✅ Enroll a person with photos
6. ✅ Search "Minji crying" and get person-filtered results
7. ✅ Click "Preview" and play scene at exact timestamp

Target: **6 weeks to MVP** with 1-2 developers

---

**Current Status**: Foundation complete (20%)
**Next Milestone**: Working upload + indexing pipeline (40%)
**Final Milestone**: Production deployment with monitoring (100%)

Good luck! 🚀

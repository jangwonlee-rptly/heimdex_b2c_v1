# Heimdex B2C - Video Semantic Search Platform

Production-grade B2C MVP for video search using **only open-source/open-weights models**.

## Features

- **Authentication**: Supabase Auth (email/password, magic link, OAuth, MFA)
- **Video Upload**: Free tier (≤10 min, ≤1 GB) with drag-and-drop UI
- **Fast Indexing**: ASR (Whisper) + scene detection + vision embeddings
- **Hybrid Search**:
  - Free-text search over transcripts (Korean-first)
  - Visual semantic search ("man crying", "red car at night")
  - Person-based search ("Minji crying" with face enrollment)
- **Scene Preview**: Exact timestamp playback via signed URLs

## Architecture

```
┌─────────┐     ┌─────────┐     ┌──────────┐
│   Web   │────▶│   API   │────▶│  Worker  │
│ Next.js │     │ FastAPI │     │ Dramatiq │
└─────────┘     └─────────┘     └──────────┘
                     │                │
                     ▼                ▼
              ┌──────────┐     ┌──────────┐
              │ Postgres │     │  Redis   │
              │ pgvector │     │  Queue   │
              │ PGroonga │     └──────────┘
              └──────────┘
                     │
                     ▼
              ┌──────────┐
              │  MinIO/  │
              │   GCS    │
              └──────────┘
```

## Tech Stack

### Backend
- **API**: FastAPI 0.104+, Python 3.11
- **Worker**: Dramatiq with Redis broker
- **Database**: PostgreSQL 16 + pgvector + PGroonga
- **Cache**: Redis 7
- **Storage**: MinIO (dev), GCS (prod)

### ML Models (All Open-Source)
- **ASR**: Whisper (small/medium/large-v3) + WhisperX
- **Text Embeddings**: BGE-M3 (1024-dim, multilingual)
- **Vision Embeddings**: OpenCLIP ViT-B/32 or SigLIP-2
- **Face Detection**: RetinaFace or MTCNN
- **Face Recognition**: AdaFace embeddings

### Frontend
- **Framework**: Next.js 14 (App Router)
- **UI**: React, TailwindCSS
- **State**: React Query

### Infrastructure
- **IaC**: Terraform (GCP Cloud Run, Cloud SQL, Memorystore, GCS)
- **Containers**: Docker + Docker Compose
- **Observability**: OpenTelemetry, Prometheus, structured logging

## 🚀 Quick Start

### Setup Steps

#### 1. Configure Supabase

Create a Supabase project and add credentials to `.env.local`:

```bash
# Get these from https://app.supabase.com/project/_/settings/api
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-public-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

#### 2. Start Services

```bash
./start.sh
```

The script will:
- ✅ Create `.env.local` configuration
- ✅ Build all Docker images
- ✅ Start infrastructure (Postgres, Redis, MinIO)
- ✅ Run database migrations automatically
- ✅ Download ML models automatically (~4 GB, first run only)
- ✅ Start API and Worker services
- ✅ Show you service URLs when ready

**First run**: ~20-25 minutes (model download)
**Subsequent runs**: ~30 seconds (cached!)

### Access Services

Once setup completes:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

### Verify It's Working

```bash
curl http://localhost:8000/health
# Returns: {"status":"healthy","version":"0.1.0"}
```

### Prerequisites
- Docker & Docker Compose
- Supabase account (free tier available at https://supabase.com)
- 10 GB free disk space (for models)
- Internet connection (first run only)

📖 **Detailed Guide**: [docs/guides/QUICKSTART.md](docs/guides/QUICKSTART.md)

---

## 📚 Documentation

- **[Quick Start Guide](docs/guides/QUICKSTART.md)** - Get up and running
- **[Setup Guide](docs/guides/SETUP_COMPLETE.md)** - What's automated
- **[Troubleshooting](docs/guides/TROUBLESHOOTING.md)** - Common issues
- **[Quick Reference](docs/reference/QUICK_REFERENCE.txt)** - Command cheatsheet
- **[Models](docs/models.md)** - ML model details
- **[Current Status](CURRENT_STATUS.md)** - What's working right now (~35%) ⭐ NEW
- **[Status](docs/reference/PROJECT_STATUS.md)** - Detailed progress tracking
- **[Auth Summary](docs/AUTH_SUMMARY.md)** - Authentication quick reference ⭐ NEW
- **[Index](docs/INDEX.md)** - Full documentation index

---

### ~~Manual Setup~~ (Automated via `./start.sh`)

<details>
<summary>Click to see old manual steps (now automated)</summary>

5. **Start services** (manual)
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2: Worker
cd worker
pip install -r requirements.txt
dramatiq tasks.indexing

# Terminal 3: Web
cd web
npm install
npm run dev
```

6. **Access the application**
- Web: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)

## Project Structure

```
heimdex_b2c/
├── api/                    # FastAPI backend
│   ├── app/
│   │   ├── auth/          # Authentication (JWT, Argon2id)
│   │   ├── video/         # Upload, validation, signed URLs
│   │   ├── search/        # Hybrid search engine
│   │   ├── models/        # SQLAlchemy models
│   │   ├── db.py          # Database connection
│   │   └── main.py        # FastAPI app
│   ├── requirements.txt
│   └── Dockerfile
├── worker/                 # Background job processing
│   ├── tasks/
│   │   ├── indexing.py    # Video indexing pipeline
│   │   ├── asr.py         # Whisper ASR
│   │   ├── vision.py      # OpenCLIP/SigLIP embeddings
│   │   ├── faces.py       # Face detection & recognition
│   │   └── utils.py       # ffprobe, scene detection
│   ├── requirements.txt
│   └── Dockerfile
├── web/                    # Next.js frontend
│   ├── src/
│   │   ├── app/           # App Router pages
│   │   ├── components/    # React components
│   │   └── lib/           # API client, auth
│   ├── package.json
│   └── Dockerfile
├── db/
│   ├── migrations/        # Alembic migrations
│   └── alembic.ini
├── infra/                 # Terraform IaC
│   ├── modules/
│   │   ├── network/
│   │   ├── postgres/
│   │   ├── storage/
│   │   ├── cloudrun/
│   │   └── monitoring/
│   └── envs/
│       ├── dev-gcp/
│       └── prod/
├── docs/
│   ├── models.md          # Model download & licenses
│   ├── api.md             # API documentation
│   └── deployment.md      # Deployment guide
├── scripts/
│   └── download_models.sh # Model download script
├── docker-compose.yml
├── .env.example
└── README.md
```

## Configuration

Key environment variables (see `.env.example`):

```bash
# Database
POSTGRES_URL=postgresql://user:pass@localhost:5432/heimdex

# Storage
STORAGE_BUCKET=uploads
STORAGE_BUCKET_SIDECARS=sidecars
MINIO_ENDPOINT=localhost:9000  # or GCS

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET_KEY=<generate-random-key>
JWT_ALGORITHM=RS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Feature Flags
FEATURE_VISION=true
FEATURE_FACE=false  # Set false by default (AdaFace OK, but be cautious)
FEATURE_FACE_LICENSED=false  # Must be false unless InsightFace license obtained

# Model Selection
ASR_MODEL=whisper-medium
TEXT_MODEL=bge-m3
VISION_MODEL=openclip  # or siglip2

# Limits
MAX_VIDEO_DURATION_SECONDS=600  # 10 minutes
MAX_VIDEO_SIZE_BYTES=1073741824  # 1 GB
FREE_TIER_UPLOADS_PER_DAY=3
```

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login (email + password)
- `POST /auth/refresh` - Refresh access token
- `POST /auth/magic-link` - Request magic link
- `GET /auth/verify/{token}` - Verify email

### Videos
- `POST /videos/upload/init` - Initialize upload (get presigned URL)
- `POST /videos/upload/complete` - Complete upload (trigger indexing)
- `GET /videos` - List user videos
- `GET /videos/{video_id}` - Get video details
- `GET /videos/{video_id}/status` - Get indexing status

### Search
- `GET /search?q={query}` - Hybrid search (text + vision + person)
- `GET /scenes/{scene_id}` - Get scene details
- `GET /scenes/{scene_id}/preview` - Get signed playback URL

### People (Face Enrollment)
- `POST /people` - Create person profile
- `POST /people/{person_id}/photos` - Upload enrollment photos
- `GET /people` - List enrolled people

## Testing

```bash
# Unit tests
cd api && pytest tests/
cd worker && pytest tests/

# Integration tests
pytest tests/integration/

# Load tests
locust -f tests/load/search_test.py
```

## Deployment

See `docs/deployment.md` for detailed instructions.

```bash
# Deploy to GCP
cd infra/envs/prod
terraform init
terraform plan
terraform apply

# Deploy services
gcloud run deploy api --source=../../api
gcloud run deploy worker --source=../../worker
```

## Rate Limits & Quotas

**Free Tier**:
- 3 uploads per day
- Max 10 minutes per video
- Max 1 GB per video
- 60 searches per minute

## Security

- Supabase Auth (enterprise-grade authentication)
- JWT token verification
- Row-level security (all queries scoped by user_id)
- Strict MIME type validation
- Private object storage with signed URLs (10-min TTL)
- Rate limiting (IP + user-based)
- No PII in logs
- Secrets in Secret Manager (prod) / `.env.local` (dev)

## Model Licenses

See `docs/licenses.md` for detailed license information.

**Summary**:
- Whisper: MIT
- BGE-M3: MIT
- OpenCLIP: MIT
- SigLIP-2: Apache 2.0
- RetinaFace: MIT
- MTCNN: MIT
- AdaFace: MIT
- **InsightFace**: Requires commercial license for commercial use (NOT included by default)

## Performance Targets

- 10-min 1080p video: Index in ≤3-5 minutes (with GPU)
- Vision processing: +60-90s CPU, +20s GPU
- Search latency: P95 ≤1.5s (at 10k scenes)

## Monitoring

Key metrics:
- `api_latency_seconds`
- `error_rate`
- `job_success_rate`
- `queue_backlog`
- `asr_processing_ms`
- `vision_processing_ms`
- `vector_query_ms`
- `index_latency_per_minute_video`

## Contributing

See `CONTRIBUTING.md`

## License

MIT License - See `LICENSE` file

---

**Built with open-source models only. No paid APIs required.**

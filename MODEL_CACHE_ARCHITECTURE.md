# Model Cache Architecture

## Overview

This document describes the optimized model downloading and caching architecture for Heimdex B2C. The system ensures models are downloaded ONCE and shared efficiently across services.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────┐                                      │
│  │ model-downloader   │                                      │
│  │ (init container)   │                                      │
│  ├────────────────────┤                                      │
│  │ • Runs once        │                                      │
│  │ • Downloads models │────────┐                             │
│  │ • Verifies cache   │        │                             │
│  │ • Exits on success │        │                             │
│  └────────────────────┘        │                             │
│                                 │                             │
│                                 ▼                             │
│                         ┌──────────────┐                     │
│                         │ models_cache │ (Docker volume)     │
│                         │   /app/models/.cache/              │
│                         │                                    │
│                         │ ├─ whisper/                        │
│                         │ │  └─ medium.pt (~2.9GB)           │
│                         │ ├─ models--google--siglip.../      │
│                         │ │  └─ model files (~1.6GB)         │
│                         │ └─ face_detection_yunet_...onnx    │
│                         │    (~228KB)                        │
│                         └──────────────┘                     │
│                                 │                             │
│                                 │ (read-only mount)           │
│                                 ▼                             │
│  ┌────────────────────┐                                      │
│  │  model-service     │                                      │
│  │  (inference)       │                                      │
│  ├────────────────────┤                                      │
│  │ • Loads from cache │                                      │
│  │ • OFFLINE MODE     │                                      │
│  │ • Fails fast if    │                                      │
│  │   models missing   │                                      │
│  │ • Serves requests  │                                      │
│  └────────────────────┘                                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Principles

### 1. Single Source of Truth
- **model-downloader** is the ONLY service that downloads models
- All downloads go to the shared `models_cache` Docker volume
- model-service loads from cache (never downloads)

### 2. Unified Cache Configuration
Both services use identical environment variables:

```yaml
HF_HOME: /app/models/.cache          # HuggingFace models
HF_HUB_CACHE: /app/models/.cache     # HuggingFace Hub cache
XDG_CACHE_HOME: /app/models/.cache   # Whisper models
TRANSFORMERS_CACHE: /app/models/.cache # Transformers library
```

### 3. Offline Mode (Production Safety)
model-service runs with:
- `HF_HUB_OFFLINE=1` - Prevents HuggingFace auto-downloads
- `TRANSFORMERS_OFFLINE=1` - Prevents Transformers auto-downloads
- `local_files_only=True` - Enforces cache-only loading
- Read-only volume mount - Prevents accidental writes

### 4. Fail Fast Philosophy
If models are missing from cache:
- model-service exits immediately with clear error message
- NO silent fallback to downloading
- NO degraded mode operation
- Forces resolution of cache/download issues

## Cache Structure

```
/app/models/
└── .cache/
    ├── whisper/                    # Whisper models (OpenAI)
    │   └── medium.pt               # ~2.9GB
    │
    ├── models--BAAI--bge-m3/       # BGE-M3 text embeddings (optional)
    │   ├── snapshots/
    │   └── refs/
    │
    ├── models--google--siglip-so400m-patch14-384/  # SigLIP (vision+text)
    │   ├── snapshots/
    │   │   └── [hash]/
    │   │       ├── model.safetensors  # ~1.6GB
    │   │       ├── preprocessor_config.json
    │   │       └── config.json
    │   └── refs/
    │
    └── face_detection_yunet_2023mar.onnx  # Face detection (~228KB)
```

## Model Download Script

### Verification Logic

The download script (`scripts/download_models.sh`) now includes robust verification:

```bash
# Example: Whisper verification
check_whisper_model() {
    local model_name=$1
    local whisper_cache="${XDG_CACHE_HOME}/whisper"

    if ls "${whisper_cache}"/*"${model_name}"*.pt 1> /dev/null 2>&1; then
        return 0  # Model exists
    fi
    return 1  # Model missing
}
```

### Skip Logic
- Checks if each model exists in cache BEFORE downloading
- Only downloads missing models
- Verifies successful download before proceeding
- On subsequent starts: all models cached → instant exit

## Model Service Loading

### Whisper
```python
cache_dir = os.path.join(os.getenv("XDG_CACHE_HOME"), "whisper")
model = whisper.load_model(model_size, device=device, download_root=cache_dir)
```

### SigLIP (HuggingFace)
```python
model = AutoModel.from_pretrained(
    model_path,
    cache_dir=cache_dir,
    local_files_only=True  # No auto-download
)
```

## Memory Optimization

### Before
- model-service limit: 8GB
- Unclear memory usage
- Potential for OOM

### After
- model-service limit: 6GB (optimized)
- Memory breakdown:
  - Whisper medium: 2.9GB
  - SigLIP so400m: 1.6GB
  - Overhead: 1.5GB
  - **Total: 6GB**

## Startup Time Comparison

### First Start (cold cache)
- model-downloader: 10-15 minutes (downloads models)
- model-service: 2-3 minutes (loads from cache)
- **Total: 12-18 minutes**

### Subsequent Starts (warm cache)
- model-downloader: <5 seconds (verification only)
- model-service: 2-3 minutes (loads from cache)
- **Total: 2-3 minutes**

### Improvement
- ✅ No duplicate downloads
- ✅ Consistent startup time after first run
- ✅ Clear separation of concerns

## Troubleshooting

### Model not found errors

If you see:
```
FileNotFoundError: Whisper medium model not found in cache
```

**Cause**: model-downloader failed or cache path mismatch

**Solution**:
```bash
# Check model-downloader logs
docker compose logs model-downloader

# Verify cache contents
docker compose run --rm --entrypoint /bin/bash model-downloader \
  -c "ls -lh /app/models/.cache/ && du -sh /app/models/.cache/"

# Force re-download
docker compose down -v  # WARNING: Deletes all data
docker compose up
```

### Cache path mismatch

If models download but aren't found:
1. Check environment variables match in both services
2. Verify volume mount paths
3. Check file permissions in cache

### Offline mode errors

If you need to update models:
1. Comment out offline mode in docker-compose.yml:
   ```yaml
   # HF_HUB_OFFLINE: "1"
   # TRANSFORMERS_OFFLINE: "1"
   ```
2. Restart services
3. Re-enable offline mode after update

## Best Practices

### ✅ DO
- Use the verified model-downloader setup
- Keep cache paths consistent
- Monitor cache volume size
- Use read-only mounts in production
- Set memory limits based on actual usage

### ❌ DON'T
- Modify model-service to auto-download
- Use different cache paths
- Skip model verification
- Run without memory limits
- Delete cache volume accidentally

## Monitoring

### Key Metrics
- Cache size: `du -sh /var/lib/docker/volumes/heimdex_b2c_models_cache/_data/`
- Model load time: Check logs for "Loaded in X.XXs"
- Memory usage: `docker stats heimdex-model-service`

### Health Checks
```bash
# Verify models loaded
curl http://localhost:8001/health

# Expected response:
{
  "status": "healthy",
  "models_loaded": ["whisper", "siglip"],
  "device": "cuda",
  "memory_used_gb": 4.5,
  "uptime_seconds": 123
}
```

## Configuration Reference

### Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `MODELS_DIR` | `/app/models` | Base directory for models |
| `ASR_MODEL` | `medium` | Whisper model size |
| `VISION_MODEL_NAME` | `google/siglip-so400m-patch14-384` | Vision model |
| `LOAD_BGE_M3` | `false` | Enable BGE-M3 (optional) |
| `FEATURE_FACE` | `false` | Enable face detection |
| `HF_HOME` | `/app/models/.cache` | HuggingFace cache |
| `XDG_CACHE_HOME` | `/app/models/.cache` | Whisper cache |
| `HF_HUB_OFFLINE` | `1` | Prevent auto-downloads |
| `TRANSFORMERS_OFFLINE` | `1` | Prevent auto-downloads |

## Related Documentation

- [MODEL_SERVICE_IMPLEMENTATION.md](./MODEL_SERVICE_IMPLEMENTATION.md) - Service implementation details
- [devlogs/2511120315.txt](./devlogs/2511120315.txt) - Optimization session notes

## Version History

- **v1.0** (2025-11-12): Initial optimized architecture
  - Unified cache paths
  - Offline mode
  - Fail-fast loading
  - Memory optimization

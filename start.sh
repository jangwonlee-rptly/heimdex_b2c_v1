#!/bin/bash
# Heimdex B2C - One-Command Startup Script
# This script handles all setup automatically

set -e

echo "=========================================="
echo "Heimdex B2C - Automated Startup"
echo "=========================================="
echo ""

# Check if .env.local exists, if not create it from .env.example
if [ ! -f .env.local ]; then
    echo "📝 Creating .env.local from .env.example..."
    cp .env.example .env.local

    # Update connection strings for Docker Compose
    sed -i 's/localhost:5432/db:5432/g' .env.local
    sed -i 's/localhost:6379/redis:6379/g' .env.local
    sed -i 's/localhost:9000/minio:9000/g' .env.local

    echo "✅ .env.local created"
    echo "⚠️  IMPORTANT: Review .env.local and update production secrets before deploying!"
    echo ""
fi

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running"
    echo "   Please start Docker and try again"
    exit 1
fi

echo "🐳 Docker is running"
echo ""

# Build and start all services
echo "🏗️  Building Docker images (this may take a few minutes on first run)..."
docker compose build --parallel

echo ""
echo "🚀 Starting all services..."
echo ""
echo "Services starting:"
echo "  1. db (PostgreSQL + pgvector)"
echo "  2. redis (Queue broker)"
echo "  3. minio (Object storage)"
echo "  4. minio-init (Create buckets)"
echo "  5. db-migrate (Run Alembic migrations)"
echo "  6. model-downloader (Download/verify ML models)"
echo "  7. model-service (Load models for inference)"
echo "  8. api (FastAPI backend)"
echo "  9. worker (Dramatiq worker)"
echo "  10. web (Next.js frontend)"
echo ""
echo "⏳ First run timing:"
echo "   • Model download: 10-15 minutes (Whisper + SigLIP ~4GB)"
echo "   • Model service startup: 2-3 minutes (loading to GPU)"
echo "   • Total first startup: ~15-18 minutes"
echo ""
echo "⚡ Subsequent runs (cached):"
echo "   • Model verification: <5 seconds (skip download)"
echo "   • Model service startup: 2-3 minutes (loading to GPU)"
echo "   • Total startup: ~3 minutes"
echo ""

# Start services with proper dependencies
docker compose up -d

echo ""
echo "⏳ Waiting for all services to be ready..."
echo "   (Migrations and model downloads are running in background)"
echo ""

# Wait for migrations to complete
echo "Waiting for database migrations..."
until [ "$(docker compose ps -a db-migrate --format json 2>/dev/null | grep -o '"State":"exited"')" = '"State":"exited"' ]; do
    sleep 2
done
if docker compose logs db-migrate 2>&1 | grep -q "Migrations complete"; then
    echo "✅ Database migrations completed"
else
    echo "⚠️  Database migrations finished but may have errors. Check logs with: docker compose logs db-migrate"
fi

# Wait for models to download (or verify if already downloaded)
echo "Waiting for model downloader (downloads or verifies models)..."
until [ "$(docker compose ps -a model-downloader --format json 2>/dev/null | grep -o '"State":"exited"')" = '"State":"exited"' ]; do
    sleep 5
    echo "  Still processing models..."
done

# Check the exit status and logs
MODEL_LOGS=$(docker compose logs model-downloader 2>&1)
if echo "$MODEL_LOGS" | grep -q "Model Download Complete"; then
    if echo "$MODEL_LOGS" | grep -q "Already cached, skipping"; then
        echo "✅ Models verified (cached from previous run, ~5 seconds)"
    else
        echo "✅ Models downloaded successfully (~10-15 minutes)"
    fi

    # Show cache size
    CACHE_SIZE=$(echo "$MODEL_LOGS" | grep -o "Total cache size: [^\"]*" | head -1)
    if [ -n "$CACHE_SIZE" ]; then
        echo "   $CACHE_SIZE"
    fi
elif echo "$MODEL_LOGS" | grep -q "Done! 🎉"; then
    echo "✅ Model downloader completed"
else
    echo "⚠️  Model downloader finished but may have errors."
    echo "   Check logs with: docker compose logs model-downloader"
    echo ""
    echo "   Common issues:"
    echo "   • Network connectivity problems"
    echo "   • Insufficient disk space (needs ~8GB)"
    echo "   • HuggingFace rate limiting"
fi

# Wait for model-service to be healthy (loading models to GPU)
echo "Waiting for model service (loading models to GPU, ~2-3 minutes)..."
until curl -s http://localhost:8001/health > /dev/null 2>&1; do
    sleep 5
    echo "  Still loading models..."
done

# Check model-service health
MODEL_SERVICE_HEALTH=$(curl -s http://localhost:8001/health 2>&1)
if echo "$MODEL_SERVICE_HEALTH" | grep -q "healthy"; then
    MODELS_LOADED=$(echo "$MODEL_SERVICE_HEALTH" | grep -o '"models_loaded":\[[^]]*\]' | head -1)
    MEMORY_USED=$(echo "$MODEL_SERVICE_HEALTH" | grep -o '"memory_used_gb":[0-9.]*' | grep -o '[0-9.]*' | head -1)

    echo "✅ Model service ready"
    if [ -n "$MODELS_LOADED" ]; then
        echo "   Models loaded: $MODELS_LOADED"
    fi
    if [ -n "$MEMORY_USED" ]; then
        echo "   GPU memory: ${MEMORY_USED}GB"
    fi
else
    echo "⚠️  Model service started but health check unclear."
    echo "   This is usually fine, continuing..."
fi

# Wait for API to be healthy
echo "Waiting for API to be ready..."
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    sleep 2
done

# Wait for Web to be ready
echo "Waiting for Web UI to be ready..."
until curl -s http://localhost:3000 > /dev/null 2>&1; do
    sleep 2
done

echo ""
echo "=========================================="
echo "✅ Heimdex B2C is ready!"
echo "=========================================="
echo ""
echo "Services:"
echo "  🌐 Web UI:        http://localhost:3000"
echo "  🔌 API:           http://localhost:8000"
echo "  📚 API Docs:      http://localhost:8000/docs"
echo "  🤖 Model Service: http://localhost:8001/health"
echo "  📊 Metrics:       http://localhost:8000/metrics"
echo "  💾 MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:3000 to use the Web UI"
echo "  2. Register a new account or login"
echo "  3. Upload videos and search semantically"
echo "  4. View API docs: http://localhost:8000/docs"
echo "  5. Stop services: docker compose down"
echo ""
echo "To view service status:"
echo "  docker compose ps"
echo ""
echo "To view logs:"
echo "  docker compose logs -f web            # Web UI logs"
echo "  docker compose logs -f api            # API logs"
echo "  docker compose logs -f worker         # Worker logs"
echo "  docker compose logs -f model-service  # Model inference logs"
echo "  docker compose logs model-downloader  # Model download logs (one-time)"
echo "  docker compose logs -f                # All logs"
echo ""
echo "Cache & troubleshooting:"
echo "  • Models cached in: docker volume heimdex_b2c_models_cache"
echo "  • Check cache size: docker compose run --rm --entrypoint /bin/bash model-downloader -c 'du -sh /app/models/.cache/'"
echo "  • Force re-download: docker compose down -v && ./start.sh (⚠️  deletes all data!)"
echo "  • Architecture docs: ./MODEL_CACHE_ARCHITECTURE.md"
echo ""
echo "Happy coding! 🚀"

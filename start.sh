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
echo "  6. model-downloader (Download ML models - 10-15 min first time)"
echo "  7. api (FastAPI backend)"
echo "  8. worker (Dramatiq worker)"
echo "  9. web (Next.js frontend)"
echo ""
echo "⏳ This will take 10-15 minutes on first run (downloading models)..."
echo "    Subsequent runs will be much faster (models are cached)."
echo ""

# Start services with proper dependencies
docker compose up -d

echo ""
echo "⏳ Waiting for all services to be ready..."
echo "   (Migrations and model downloads are running in background)"
echo ""

# Wait for migrations to complete
echo "Waiting for database migrations..."
until [ "$(docker compose ps db-migrate --format json 2>/dev/null | grep -o '"State":"exited"')" = '"State":"exited"' ]; do
    sleep 2
done
if docker compose logs db-migrate 2>&1 | grep -q "Migrations complete"; then
    echo "✅ Database migrations completed"
else
    echo "⚠️  Database migrations finished but may have errors. Check logs with: docker compose logs db-migrate"
fi

# Wait for models to download (or skip if already downloaded)
echo "Waiting for model downloads (this is the slow part on first run)..."
until [ "$(docker compose ps model-downloader --format json 2>/dev/null | grep -o '"State":"exited"')" = '"State":"exited"' ]; do
    sleep 5
    echo "  Still downloading models..."
done
if docker compose logs model-downloader 2>&1 | grep -q -E "(Models already downloaded|Model download complete)"; then
    echo "✅ Model downloads completed"
else
    echo "⚠️  Model downloads finished but may have errors. Check logs with: docker compose logs model-downloader"
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
echo "  docker compose logs -f web      # Web UI logs"
echo "  docker compose logs -f api      # API logs"
echo "  docker compose logs -f worker   # Worker logs"
echo "  docker compose logs -f          # All logs"
echo ""
echo "Happy coding! 🚀"

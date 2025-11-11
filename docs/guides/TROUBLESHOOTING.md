# Troubleshooting Guide

## Common Issues and Solutions

### Issue: "version is obsolete" warning

**Symptom:**
```
WARN[0000] docker-compose.yml: the attribute `version` is obsolete
```

**Solution:**
This is just a warning and can be safely ignored. Docker Compose v2 doesn't require the `version` field.

To remove the warning, you can delete the first line (`version: '3.8'`) from `docker-compose.yml`.

---

### Issue: Web service fails to build

**Symptom:**
```
target web: failed to solve: failed to read dockerfile
```

**Solution:**
The web service is not fully implemented yet. It's now configured with the `web` profile, so it won't start by default.

```bash
# Start without web (default)
docker compose up -d

# Start with web (when implemented)
docker compose --profile web up -d
```

---

### Issue: Models downloading slowly

**Symptom:**
`model-downloader` container takes 10-15 minutes on first run.

**Solution:**
This is normal! ML models are ~4 GB total. Progress can be checked with:

```bash
docker compose logs -f model-downloader
```

Models are cached in a Docker volume, so subsequent runs skip the download.

---

### Issue: Migrations fail

**Symptom:**
```
db-migrate exited with code 1
```

**Solution:**
1. Check database is healthy:
```bash
docker compose ps db
docker compose logs db
```

2. Check migration logs:
```bash
docker compose logs db-migrate
```

3. Manually run migrations:
```bash
docker compose exec db psql -U heimdex -d heimdex -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose restart db-migrate
```

---

### Issue: API won't start

**Symptom:**
API container keeps restarting or exits immediately.

**Solution:**
1. Check if migrations completed:
```bash
docker compose ps db-migrate
```

2. Check API logs:
```bash
docker compose logs api
```

3. Common causes:
   - Missing `.env.local` - Create it: `cp .env.example .env.local`
   - Database not ready - Wait 30 seconds after `docker compose up -d db`
   - Wrong connection string - Check `POSTGRES_HOST=db` in `.env.local`

---

### Issue: Worker won't start

**Symptom:**
Worker container keeps restarting.

**Solution:**
1. Check if models downloaded:
```bash
docker compose logs model-downloader
```

2. Check if Redis is healthy:
```bash
docker compose ps redis
```

3. Check worker logs:
```bash
docker compose logs worker
```

---

### Issue: MinIO buckets not created

**Symptom:**
API logs show "bucket not found" errors.

**Solution:**
1. Check minio-init completed:
```bash
docker compose logs minio-init
```

2. Manually recreate buckets:
```bash
docker compose restart minio-init
```

3. Or create manually in MinIO console:
   - Open http://localhost:9001
   - Login: minioadmin / minioadmin
   - Create buckets: uploads, sidecars, tmp

---

### Issue: Port already in use

**Symptom:**
```
Error: bind: address already in use
```

**Solution:**
1. Check what's using the port:
```bash
# For port 8000 (API)
sudo lsof -i :8000

# For port 5432 (Postgres)
sudo lsof -i :5432
```

2. Stop conflicting service:
```bash
# If it's another Docker container
docker ps
docker stop <container_id>

# If it's a local process
sudo kill <pid>
```

3. Change port in docker-compose.yml:
```yaml
ports:
  - "8001:8000"  # Use 8001 instead of 8000
```

---

### Issue: Out of disk space

**Symptom:**
```
no space left on device
```

**Solution:**
1. Check Docker disk usage:
```bash
docker system df
```

2. Clean up unused images and volumes:
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes (⚠️ Be careful!)
docker volume prune

# Remove everything (⚠️ Nuclear option)
docker system prune -a --volumes
```

---

### Issue: Permission denied

**Symptom:**
```
Permission denied when accessing /app or /tmp
```

**Solution:**
The containers run as non-root user (appuser). Check file permissions:

```bash
# Make sure your code is readable
chmod -R 755 api/ worker/ web/

# Make sure scripts are executable
chmod +x scripts/*.sh
chmod +x start.sh
chmod +x deploy-gcp.sh
```

---

### Issue: Database connection refused

**Symptom:**
```
connection to server at "db" (X.X.X.X), port 5432 failed: Connection refused
```

**Solution:**
1. Services trying to connect before database is ready.
2. Wait for database health check:
```bash
docker compose ps db
```
Should show "healthy" status.

3. Restart dependent services:
```bash
docker compose restart api worker
```

---

## Complete Reset

If everything is broken and you want to start fresh:

```bash
# Stop everything
docker compose down

# Remove volumes (⚠️ This deletes all data!)
docker compose down -v

# Remove images
docker compose down --rmi all

# Start fresh
./start.sh
```

---

## Getting Help

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f db-migrate
docker compose logs -f model-downloader

# Last 100 lines
docker compose logs --tail=100 api
```

### Check service status

```bash
docker compose ps
```

### Execute commands in containers

```bash
# API container
docker compose exec api bash

# Worker container
docker compose exec worker bash

# Database
docker compose exec db psql -U heimdex -d heimdex
```

### Check Docker resources

```bash
# Disk usage
docker system df

# Running containers
docker ps

# All containers
docker ps -a

# Networks
docker network ls

# Volumes
docker volume ls
```

---

## Performance Issues

### Slow API responses

1. Check CPU/memory usage:
```bash
docker stats
```

2. Check worker is running:
```bash
docker compose ps worker
```

3. Check Redis is responding:
```bash
docker compose exec redis redis-cli ping
```

### Slow model downloads

1. Check internet connection
2. Try using different mirror:
   - Edit `scripts/download_models.sh`
   - Add `export HF_ENDPOINT=https://hf-mirror.com`

### High memory usage

1. Reduce worker resources in docker-compose.yml:
```yaml
worker:
  deploy:
    resources:
      limits:
        memory: 4G  # Reduce from 8G
```

2. Use CPU instead of GPU:
```yaml
environment:
  - ASR_DEVICE=cpu
  - VISION_DEVICE=cpu
```

---

## Still Having Issues?

1. Check documentation:
   - `README.md` - Project overview
   - `QUICKSTART.md` - Setup guide
   - `PROJECT_STATUS.md` - Known issues

2. Check logs in detail:
```bash
docker compose logs -f > debug.log
```

3. Check GitHub issues or create a new one with:
   - Output of `docker compose ps`
   - Relevant logs
   - Steps to reproduce
   - Your OS and Docker version

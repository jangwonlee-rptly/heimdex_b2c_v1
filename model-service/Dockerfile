# Model Service Dockerfile
# Platform-agnostic ML inference with CPU/GPU support

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --fix-missing \
    gcc \
    g++ \
    git \
    curl \
    ffmpeg \
    libsndfile1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching)
COPY requirements.txt .

# Install Python dependencies
# Note: torch will auto-detect CPU vs CUDA at runtime
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir git+https://github.com/openai/whisper.git

# Copy application code
COPY app/ ./app/

# Create models directory with proper permissions
RUN mkdir -p /app/models/.cache && \
    chmod -R 777 /app/models

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]

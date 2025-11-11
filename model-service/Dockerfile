# Model Service Dockerfile
# Optimized for production ML inference with GPU support

FROM pytorch/pytorch:2.9.0-cuda12.8-cudnn9-runtime

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
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir git+https://github.com/openai/whisper.git

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]

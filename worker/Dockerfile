FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    zlib1g-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy shared code (model client) first
COPY shared/ /app/shared/

# Copy requirements and install Python dependencies
COPY worker/requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY worker/ .

# Create directories for temporary files and models cache
RUN mkdir -p /tmp/heimdex && \
    chmod 777 /tmp/heimdex && \
    mkdir -p /app/models/.cache && \
    chmod -R 777 /app/models

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /tmp/heimdex
USER appuser

# Run dramatiq worker
CMD ["dramatiq", "tasks.indexing", "tasks.asr", "tasks.vision", "tasks.faces", "--processes", "2", "--threads", "4"]

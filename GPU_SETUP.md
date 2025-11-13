# GPU Setup Guide

This project is **host-agnostic** and runs on:
- ✅ **Mac (ARM64/Apple Silicon)** - CPU only
- ✅ **Linux (x86/ARM64)** - CPU or GPU
- ✅ **Windows WSL2** - CPU or GPU

## Default: CPU Mode (No GPU Required)

By default, the project runs in **CPU mode** and works on any system:

```bash
./start.sh
```

The model service will automatically detect available hardware and use CPU.

## Optional: GPU Acceleration

If you have an NVIDIA GPU and want to accelerate inference:

### Prerequisites

1. **NVIDIA GPU** with CUDA support (Compute Capability 6.0+)
2. **NVIDIA Driver** installed on host
3. **NVIDIA Container Toolkit** (nvidia-docker2):
   ```bash
   # Ubuntu/Debian
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
     sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

   sudo apt-get update
   sudo apt-get install -y nvidia-container-toolkit
   sudo systemctl restart docker
   ```

4. **Verify GPU access**:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
   ```

### Enable GPU Mode

Use the GPU override configuration:

```bash
# Start with GPU support
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

# Or stop and rebuild
docker compose -f docker-compose.yml -f docker-compose.gpu.yml down
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

### Verify GPU Usage

Check if models are loaded on GPU:

```bash
# Check model service health
curl http://localhost:8001/health

# Should show: "device": "cuda"

# Monitor GPU usage
docker exec heimdex-model-service nvidia-smi
```

## Performance Comparison

| Mode | First Startup | Model Load Time | Transcription (1min audio) | Vision Embedding |
|------|--------------|-----------------|---------------------------|------------------|
| **CPU** (Mac M2) | ~15-18 min | 2-3 min | ~30-40 sec | ~2-3 sec |
| **GPU** (RTX 3090) | ~15-18 min | 2-3 min | ~8-12 sec | ~0.5-1 sec |

**Note**: First startup is slow due to model downloads (~4GB). Subsequent runs are much faster (~3 min).

## Troubleshooting

### "nvidia runtime not found"

Install nvidia-container-toolkit (see prerequisites above).

### "could not select device driver"

Ensure NVIDIA driver is installed:
```bash
nvidia-smi  # Should show GPU info
```

### Models still using CPU with GPU enabled

Check Docker GPU access:
```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

If this fails, the issue is with Docker GPU passthrough, not this project.

## Architecture Notes

- **Platform detection**: Dockerfiles use `python:3.11-slim` (works on ARM64 + AMD64)
- **Device auto-detection**: PyTorch automatically detects CUDA availability
- **Graceful fallback**: If GPU requested but unavailable, falls back to CPU
- **No hardcoded dependencies**: All CUDA libs are optional runtime dependencies

## Switching Between Modes

### CPU → GPU
```bash
docker compose down
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

### GPU → CPU
```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml down
docker compose up -d
# or just:
./start.sh
```

No rebuild needed - same images work for both modes!

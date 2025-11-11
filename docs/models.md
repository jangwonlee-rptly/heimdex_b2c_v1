# ML Models for Heimdex B2C

This document describes all open-source ML models used in Heimdex B2C, their licenses, and how to download them.

## Models Overview

| Model | Purpose | Size | License | Commercial Use |
|-------|---------|------|---------|----------------|
| Whisper (small/medium/large-v3) | ASR (Audio Speech Recognition) | 244MB-3GB | MIT | ✅ Yes |
| BGE-M3 | Text embeddings (multilingual) | ~2GB | MIT | ✅ Yes |
| OpenCLIP ViT-B/32 | Vision embeddings (default) | ~350MB | MIT | ✅ Yes |
| SigLIP-2 | Vision embeddings (optional) | ~400MB | Apache 2.0 | ✅ Yes |
| RetinaFace | Face detection | ~1.5MB | MIT | ✅ Yes |
| MTCNN | Face detection (alternative) | ~2MB | MIT | ✅ Yes |
| AdaFace | Face recognition embeddings | ~130MB | MIT | ✅ Yes |

## Download Script

Use the provided script to download all required models:

```bash
./scripts/download_models.sh
```

Or download individual models:

```bash
# ASR - Whisper
python -c "import whisper; whisper.load_model('medium')"

# Text Embeddings - BGE-M3
python -c "from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)"

# Vision - OpenCLIP
python -c "import open_clip; open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')"

# Vision - SigLIP-2 (optional)
huggingface-cli download google/siglip-base-patch16-224 --local-dir ./models/siglip2

# Face Detection - RetinaFace
# Installed via retinaface-pytorch package

# Face Recognition - AdaFace
huggingface-cli download AdaFace/adaface_ir101_webface12m --local-dir ./models/adaface
```

## Detailed Model Information

### 1. Whisper (ASR)

**Repository**: https://github.com/openai/whisper
**License**: MIT
**Paper**: https://arxiv.org/abs/2212.04356

**Variants**:
- `whisper-small`: 244 MB, faster, good for Korean
- `whisper-medium`: 769 MB, balanced accuracy/speed (default)
- `whisper-large-v3`: 3 GB, best accuracy

**Korean Support**: Excellent (trained on multilingual data)

**Installation**:
```bash
pip install openai-whisper
python -c "import whisper; whisper.load_model('medium')"
```

**Usage in Heimdex**:
- Convert audio to 16kHz mono WAV
- Process in 30-60s chunks
- Combine with WhisperX for word-level timestamps

### 2. BGE-M3 (Text Embeddings)

**Repository**: https://github.com/FlagOpen/FlagEmbedding
**License**: MIT
**Paper**: https://arxiv.org/abs/2402.03216

**Features**:
- Multilingual (100+ languages including Korean)
- 1024-dimensional embeddings
- State-of-the-art for semantic search

**Installation**:
```bash
pip install FlagEmbedding
```

**Model Download**:
```python
from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
```

**Usage in Heimdex**:
- Encode transcript text to 1024-dim vectors
- Normalize to unit length
- Store in pgvector for similarity search

### 3. OpenCLIP (Vision Embeddings - Default)

**Repository**: https://github.com/mlfoundations/open_clip
**License**: MIT
**Paper**: https://arxiv.org/abs/2212.07143

**Model**: ViT-B/32 with OpenAI weights

**Installation**:
```bash
pip install open-clip-torch
```

**Model Download**:
```python
import open_clip
model, preprocess_train, preprocess_val = open_clip.create_model_and_transforms(
    'ViT-B-32',
    pretrained='openai'
)
```

**Usage in Heimdex**:
- Extract 512-dim image embeddings from video frames
- Extract text embeddings for zero-shot queries
- Mean-pool frame embeddings per scene

### 4. SigLIP-2 (Vision Embeddings - Optional)

**Repository**: https://huggingface.co/google/siglip-base-patch16-224
**License**: Apache 2.0
**Paper**: https://arxiv.org/abs/2303.15343

**Advantages**:
- Better multilingual grounding (including Korean text in images)
- More efficient training (sigmoid loss)

**Installation**:
```bash
pip install transformers
huggingface-cli download google/siglip-base-patch16-224 --local-dir ./models/siglip2
```

**Usage in Heimdex**:
- Enable with `VISION_MODEL=siglip2`
- Similar usage to OpenCLIP

### 5. RetinaFace (Face Detection)

**Repository**: https://github.com/biubug6/Pytorch_Retinaface
**License**: MIT
**Paper**: https://arxiv.org/abs/1905.00641

**Features**:
- Fast and accurate face detection
- Returns face bounding boxes and 5 landmarks

**Installation**:
```bash
pip install retinaface-pytorch
```

**Usage in Heimdex**:
- Detect faces in video frames
- Extract 112x112 aligned crops for recognition

### 6. MTCNN (Face Detection - Alternative)

**Repository**: https://github.com/ipazc/mtcnn
**License**: MIT
**Paper**: https://arxiv.org/abs/1604.02878

**Installation**:
```bash
pip install mtcnn
```

**Usage in Heimdex**:
- Alternative to RetinaFace
- Good for CPU-only environments

### 7. AdaFace (Face Recognition)

**Repository**: https://github.com/mk-minchul/AdaFace
**License**: MIT
**Paper**: https://arxiv.org/abs/2204.00964

**Features**:
- State-of-the-art face recognition
- 512-dimensional embeddings
- Trained on WebFace12M dataset

**Installation**:
```bash
pip install adaface
```

**Model Download**:
```bash
huggingface-cli download AdaFace/adaface_ir101_webface12m --local-dir ./models/adaface
```

**Usage in Heimdex**:
- Extract embeddings from aligned face crops
- Compare with enrolled person profiles
- Cosine similarity > 0.6 threshold for matches

## IMPORTANT: InsightFace License Notice

**InsightFace** is a popular face recognition library, but its **pretrained models** require a commercial license for commercial use.

**Heimdex B2C does NOT use InsightFace pretrained models by default.**

If you wish to use InsightFace models:
1. Obtain a commercial license from InsightFace
2. Set `FEATURE_FACE_LICENSED=true`
3. Update the face recognition pipeline to use InsightFace models

**Default**: We use AdaFace (MIT license) which is free for commercial use.

## Model Storage

Models are stored locally in:
```
./models/
├── whisper/
├── bge-m3/
├── clip/
├── siglip2/
└── adaface/
```

In production (GCP), models can be:
1. Baked into the container image (increases image size)
2. Downloaded on container startup (slower startup)
3. Loaded from GCS bucket (recommended for large models)

## GPU Support

All models support both CPU and GPU inference:

**CPU Mode** (default):
- Slower but works everywhere
- Recommended for dev/testing

**GPU Mode** (CUDA):
- 5-10x faster for vision/face models
- Requires NVIDIA GPU + CUDA toolkit

**Enable GPU**:
```bash
export ASR_DEVICE=cuda
export TEXT_DEVICE=cuda
export VISION_DEVICE=cuda
export FACE_DEVICE=cuda
```

## Model Performance

**Whisper Medium (CPU)**:
- ~3-5x realtime (10-min video → 2-3 min processing)

**Whisper Medium (GPU)**:
- ~10-20x realtime (10-min video → 30-60s processing)

**BGE-M3**:
- ~100 sentences/sec (CPU)
- ~1000 sentences/sec (GPU)

**OpenCLIP**:
- ~20 images/sec (CPU, batch=1)
- ~200 images/sec (GPU, batch=32)

**AdaFace**:
- ~10 faces/sec (CPU)
- ~100 faces/sec (GPU)

## License Compliance

All models used by default in Heimdex B2C are:
- ✅ Open-source
- ✅ MIT or Apache 2.0 licensed
- ✅ Free for commercial use
- ✅ No attribution required (though appreciated)

**You can use Heimdex B2C commercially without any licensing concerns.**

## References

- OpenAI Whisper: https://github.com/openai/whisper
- BGE-M3: https://github.com/FlagOpen/FlagEmbedding
- OpenCLIP: https://github.com/mlfoundations/open_clip
- SigLIP: https://arxiv.org/abs/2303.15343
- RetinaFace: https://github.com/biubug6/Pytorch_Retinaface
- AdaFace: https://github.com/mk-minchul/AdaFace

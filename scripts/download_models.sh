#!/bin/bash
# Download all ML models for Heimdex B2C
# All models are MIT or Apache 2.0 licensed and free for commercial use

set -e

echo "======================================"
echo "Heimdex B2C Model Download Script"
echo "======================================"
echo ""

# Create models directory
MODELS_DIR="${MODELS_DIR:-./models}"
mkdir -p "$MODELS_DIR"
echo "Models will be downloaded to: $MODELS_DIR"
echo ""

# Check Python availability
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not installed"
    exit 1
fi

# Check if running in virtual environment (recommended)
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not running in a virtual environment"
    echo "   Recommended: python3 -m venv venv && source venv/bin/activate"
    echo ""
fi

# Install required packages
echo "📦 Installing required packages..."
pip install -q --upgrade pip
pip install -q openai-whisper FlagEmbedding transformers huggingface-hub opencv-python

echo "✅ Packages installed"
echo ""

# Download Whisper models
echo "🎤 Downloading Whisper ASR models (MIT License)..."
ASR_MODEL="${ASR_MODEL:-whisper-medium}"
python3 -c "import whisper; print(f'Downloading {whisper.__version__}...'); whisper.load_model('$ASR_MODEL')"
echo "✅ Whisper $ASR_MODEL downloaded"
echo ""

# Download BGE-M3 text embeddings
echo "📝 Downloading BGE-M3 text embeddings (MIT License)..."
python3 -c "
from FlagEmbedding import FlagModel
print('Downloading BAAI/bge-m3...')
# Will cache to HF_HOME or default cache directory
model = FlagModel('BAAI/bge-m3', use_fp16=False)
print('✅ BGE-M3 downloaded')
"
echo ""

# Download SigLIP vision-language model
echo "👁️  Downloading SigLIP vision-language model (Apache 2.0 License)..."
python3 -c "
from transformers import AutoProcessor, AutoModel
print('Downloading google/siglip-so400m-patch14-384...')
# Will cache to HF_HOME or default cache directory
processor = AutoProcessor.from_pretrained('google/siglip-so400m-patch14-384')
model = AutoModel.from_pretrained('google/siglip-so400m-patch14-384')
print('✅ SigLIP so400m-patch14-384 downloaded')
"
echo ""

# Download face detection model
if [ "${FEATURE_FACE:-true}" = "true" ]; then
    echo "👤 Downloading OpenCV YuNet face detection model (Apache 2.0 License)..."

    python3 -c "
from huggingface_hub import hf_hub_download
import os

cache_dir = os.path.join('$MODELS_DIR', 'face_detection')
os.makedirs(cache_dir, exist_ok=True)
print(f'Downloading to {cache_dir}...')

# Download the YuNet face detection model
model_path = hf_hub_download(
    repo_id='opencv/face_detection_yunet',
    filename='face_detection_yunet_2023mar.onnx',
    cache_dir=cache_dir
)
print(f'✅ YuNet face detection model downloaded to {model_path}')
"
    echo ""
fi

# Summary
echo "======================================"
echo "✅ All models downloaded successfully!"
echo "======================================"
echo ""
echo "Downloaded models:"
echo "  - Whisper ($ASR_MODEL) - ASR"
echo "  - BGE-M3 - Text embeddings"
echo "  - SigLIP so400m-patch14-384 - Vision-language model"
if [ "${FEATURE_FACE:-true}" = "true" ]; then
    echo "  - OpenCV YuNet - Face detection"
fi
echo ""
echo "Models directory: $MODELS_DIR"
echo "Total size: $(du -sh $MODELS_DIR 2>/dev/null | cut -f1 || echo 'unknown')"
echo ""
echo "All models are MIT or Apache 2.0 licensed."
echo "✅ Free for commercial use without restrictions."
echo ""
echo "To use these models, set in your .env.local:"
echo "  MODELS_DIR=$MODELS_DIR"
echo ""
echo "Done! 🎉"

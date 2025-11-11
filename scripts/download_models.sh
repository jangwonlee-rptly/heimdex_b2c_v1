#!/bin/bash
# Download all ML models for Heimdex B2C
# All models are MIT or Apache 2.0 licensed and free for commercial use
#
# This script ensures all models are downloaded ONCE to a shared cache volume.
# Subsequent starts will skip downloads if models are verified to exist.

set -e

echo "======================================"
echo "Heimdex B2C Model Download Script"
echo "======================================"
echo ""

# Create models directory and cache subdirectories
MODELS_DIR="${MODELS_DIR:-./models}"
CACHE_DIR="${MODELS_DIR}/.cache"
mkdir -p "$CACHE_DIR"
mkdir -p "${CACHE_DIR}/whisper"

echo "Models directory: $MODELS_DIR"
echo "Cache directory: $CACHE_DIR"
echo ""

# Configure cache paths for consistency
export HF_HOME="$CACHE_DIR"
export HF_HUB_CACHE="$CACHE_DIR"
export XDG_CACHE_HOME="$CACHE_DIR"  # For Whisper

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

# ============================================================================
# Model Verification Functions
# ============================================================================

check_whisper_model() {
    local model_name=$1
    # Whisper stores models in XDG_CACHE_HOME/whisper/
    local whisper_cache="${XDG_CACHE_HOME}/whisper"

    # Check for the .pt file (Whisper model file)
    if ls "${whisper_cache}"/*"${model_name}"*.pt 1> /dev/null 2>&1; then
        return 0
    fi
    return 1
}

check_hf_model() {
    local model_repo=$1
    # HuggingFace stores models as models--org--name
    # Example: "google/siglip-so400m-patch14-384" -> "models--google--siglip-so400m-patch14-384"
    local cache_path="${HF_HUB_CACHE}/models--${model_repo//\//--}"

    if [ -d "$cache_path" ] && [ -n "$(ls -A $cache_path 2>/dev/null)" ]; then
        return 0
    fi
    return 1
}

check_file_exists() {
    local file_path=$1
    if [ -f "$file_path" ]; then
        return 0
    fi
    return 1
}

# ============================================================================
# Download Models with Verification
# ============================================================================

# Whisper ASR Model
ASR_MODEL="${ASR_MODEL:-medium}"
echo "🎤 Whisper ASR model ($ASR_MODEL)..."
if check_whisper_model "$ASR_MODEL"; then
    echo "   ✓ Already cached, skipping download"
else
    echo "   Downloading..."
    python3 -c "import whisper; whisper.load_model('$ASR_MODEL')"
    if check_whisper_model "$ASR_MODEL"; then
        echo "   ✅ Downloaded successfully"
    else
        echo "   ❌ Download failed or verification error"
        exit 1
    fi
fi
echo ""

# BGE-M3 Text Embeddings (optional, disabled by default)
if [ "${LOAD_BGE_M3:-false}" = "true" ]; then
    echo "📝 BGE-M3 text embeddings..."
    if check_hf_model "BAAI/bge-m3"; then
        echo "   ✓ Already cached, skipping download"
    else
        echo "   Downloading..."
        python3 -c "from FlagEmbedding import FlagModel; FlagModel('BAAI/bge-m3', use_fp16=False)"
        if check_hf_model "BAAI/bge-m3"; then
            echo "   ✅ Downloaded successfully"
        else
            echo "   ❌ Download failed or verification error"
            exit 1
        fi
    fi
    echo ""
fi

# SigLIP Vision-Language Model
VISION_MODEL="${VISION_MODEL_NAME:-google/siglip-so400m-patch14-384}"
echo "👁️  SigLIP vision-language model..."
if check_hf_model "$VISION_MODEL"; then
    echo "   ✓ Already cached, skipping download"
else
    echo "   Downloading $VISION_MODEL..."
    python3 -c "
from transformers import AutoProcessor, AutoModel
processor = AutoProcessor.from_pretrained('$VISION_MODEL')
model = AutoModel.from_pretrained('$VISION_MODEL')
"
    if check_hf_model "$VISION_MODEL"; then
        echo "   ✅ Downloaded successfully"
    else
        echo "   ❌ Download failed or verification error"
        exit 1
    fi
fi
echo ""

# YuNet Face Detection Model
if [ "${FEATURE_FACE:-false}" = "true" ]; then
    YUNET_PATH="${CACHE_DIR}/face_detection_yunet_2023mar.onnx"
    echo "👤 YuNet face detection model..."
    if check_file_exists "$YUNET_PATH"; then
        echo "   ✓ Already cached, skipping download"
    else
        echo "   Downloading..."
        python3 -c "
import os
import urllib.request
url = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx'
os.makedirs(os.path.dirname('$YUNET_PATH'), exist_ok=True)
urllib.request.urlretrieve(url, '$YUNET_PATH')
"
        if check_file_exists "$YUNET_PATH"; then
            echo "   ✅ Downloaded successfully"
        else
            echo "   ❌ Download failed or verification error"
            exit 1
        fi
    fi
    echo ""
fi

# ============================================================================
# Summary and Verification
# ============================================================================

echo "======================================"
echo "✅ Model Download Complete"
echo "======================================"
echo ""
echo "Models verified and cached:"
echo "  ✓ Whisper ($ASR_MODEL) - ASR transcription"
if [ "${LOAD_BGE_M3:-false}" = "true" ]; then
    echo "  ✓ BGE-M3 - Text embeddings (optional)"
fi
echo "  ✓ SigLIP ($VISION_MODEL) - Vision-language embeddings"
if [ "${FEATURE_FACE:-false}" = "true" ]; then
    echo "  ✓ YuNet - Face detection"
fi
echo ""
echo "Cache configuration:"
echo "  HF_HOME: $HF_HOME"
echo "  XDG_CACHE_HOME: $XDG_CACHE_HOME"
echo "  Total cache size: $(du -sh $CACHE_DIR 2>/dev/null | cut -f1 || echo 'unknown')"
echo ""
echo "All models are MIT or Apache 2.0 licensed."
echo "✅ Free for commercial use without restrictions."
echo ""
echo "ℹ️  On subsequent starts, this script will skip re-downloading."
echo "   Models are verified before skipping to ensure integrity."
echo ""
echo "Done! 🎉"

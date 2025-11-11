"""
Heimdex Model Service - Centralized ML Model Inference

This service provides centralized inference endpoints for all ML models used in Heimdex.
Models are loaded once on startup and shared across all requests, enabling:
- Single model load per deployment (massive memory savings)
- GPU batch processing for improved throughput
- Centralized monitoring and observability
- Independent scaling of inference vs business logic

Architecture:
    - Whisper (ASR): Audio transcription
    - SigLIP (Vision/Text): Multimodal embeddings for search
    - BGE-M3 (Text): Text embeddings (legacy, can be deprecated)
    - YuNet (Face): Face detection

Performance:
    - Warmup on startup (compile kernels, verify models)
    - Request batching for GPU efficiency
    - Prometheus metrics for monitoring
"""

import os
import io
import base64
import asyncio
import time
from typing import List, Dict, Optional, Any
from contextlib import asynccontextmanager
from collections import deque
import tempfile

import numpy as np
import torch
from transformers import AutoProcessor, AutoModel
from FlagEmbedding import FlagModel
import whisper
from PIL import Image
import cv2
from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# ============================================================================
# Logging Configuration
# ============================================================================

logger = structlog.get_logger()

# ============================================================================
# Prometheus Metrics
# ============================================================================

# Request counters
inference_requests_total = Counter(
    "model_service_requests_total",
    "Total inference requests",
    ["model", "status"]
)

# Latency histograms
inference_latency_seconds = Histogram(
    "model_service_latency_seconds",
    "Inference latency in seconds",
    ["model"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Model memory usage
model_memory_bytes = Gauge(
    "model_service_memory_bytes",
    "Model memory usage in bytes",
    ["model"]
)

# Batch processing
batch_size_processed = Histogram(
    "model_service_batch_size",
    "Number of requests processed in batch",
    ["model"],
    buckets=[1, 2, 4, 8, 16, 32, 64]
)

# ============================================================================
# Request/Response Models
# ============================================================================

class ASRRequest(BaseModel):
    """Audio transcription request."""
    audio_base64: str = Field(..., description="Base64-encoded audio file")
    language: Optional[str] = Field(None, description="Language hint (e.g., 'en', 'es')")


class ASRResponse(BaseModel):
    """Audio transcription response."""
    text: str
    segments: List[Dict[str, Any]]
    language: str
    latency_ms: float


class TextEmbeddingRequest(BaseModel):
    """Text embedding generation request."""
    text: str = Field(..., min_length=1, max_length=10000)
    model: str = Field("siglip", description="Model to use: 'siglip' or 'bge-m3'")


class TextEmbeddingResponse(BaseModel):
    """Text embedding response."""
    embedding: List[float]
    dimension: int
    model: str
    latency_ms: float


class VisionEmbeddingRequest(BaseModel):
    """Vision embedding generation request."""
    image_base64: str = Field(..., description="Base64-encoded image")


class VisionEmbeddingResponse(BaseModel):
    """Vision embedding response."""
    embedding: List[float]
    dimension: int
    latency_ms: float


class FaceDetectionResponse(BaseModel):
    """Face detection response."""
    faces: List[Dict[str, Any]]
    count: int
    latency_ms: float


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    models_loaded: List[str]
    device: str
    memory_used_gb: float
    uptime_seconds: float


# ============================================================================
# Model Manager - Singleton Pattern with Batching
# ============================================================================

class ModelManager:
    """Centralized model management with batching support."""

    def __init__(self):
        self.models = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.start_time = time.time()

        # Batching queues
        self.text_embed_queue = deque()
        self.vision_embed_queue = deque()
        self.batch_size = int(os.getenv("BATCH_SIZE", "4"))
        self.batch_timeout_ms = int(os.getenv("BATCH_TIMEOUT_MS", "100"))

        logger.info(f"[models] Initializing ModelManager on {self.device}")
        logger.info(f"[models] Batch size: {self.batch_size}, timeout: {self.batch_timeout_ms}ms")

    async def load_all_models(self):
        """
        Load all models on startup with warmup.

        IMPORTANT: This service operates in OFFLINE MODE to prevent accidental downloads.
        All models MUST be pre-downloaded by the model-downloader service into the
        shared cache volume. If models are missing, this service will FAIL FAST with
        clear error messages rather than attempting to download.

        Cache Configuration:
        - HF_HOME: /app/models/.cache (HuggingFace models)
        - XDG_CACHE_HOME: /app/models/.cache (Whisper models)
        - HF_HUB_OFFLINE: 1 (prevent HuggingFace auto-downloads)
        - TRANSFORMERS_OFFLINE: 1 (prevent Transformers auto-downloads)

        Memory Optimization:
        - Whisper medium: ~2.9GB
        - SigLIP so400m: ~1.6GB
        - Total: ~4.5GB + 1.5GB overhead = 6GB limit
        """
        logger.info("[models] Loading all models from cache (offline mode)...")
        logger.info(f"[models] Cache directory: {os.getenv('HF_HUB_CACHE', 'default')}")

        # Load Whisper
        await self._load_whisper()

        # Load SigLIP (multimodal)
        await self._load_siglip()

        # Load BGE-M3 (text-only, optional)
        if os.getenv("LOAD_BGE_M3", "false").lower() == "true":
            await self._load_bge_m3()

        # Load YuNet (face detection, optional)
        await self._load_yunet()

        # Warmup models
        await self._warmup_models()

        logger.info(f"[models] All models loaded successfully on {self.device}")
        logger.info(f"[models] Loaded models: {list(self.models.keys())}")

    async def _load_whisper(self):
        """Load Whisper ASR model from cache (fail fast if not cached)."""
        try:
            model_size = os.getenv("ASR_MODEL", "medium")
            logger.info(f"[whisper] Loading Whisper {model_size} from cache...")

            # Check if model is cached first
            cache_dir = os.path.join(os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "whisper")
            model_files = [f for f in os.listdir(cache_dir) if model_size in f and f.endswith(".pt")] if os.path.exists(cache_dir) else []

            if not model_files:
                raise FileNotFoundError(
                    f"Whisper {model_size} model not found in cache ({cache_dir}). "
                    "Model downloader may have failed or cache path mismatch."
                )

            start = time.time()
            # Set download_root to cache directory to prevent auto-download
            model = whisper.load_model(model_size, device=self.device, download_root=cache_dir)
            elapsed = time.time() - start

            self.models["whisper"] = model

            # Estimate memory
            memory_mb = sum(p.numel() * p.element_size() for p in model.parameters()) / 1024 / 1024
            model_memory_bytes.labels(model="whisper").set(memory_mb * 1024 * 1024)

            logger.info(f"[whisper] Loaded in {elapsed:.2f}s, ~{memory_mb:.0f}MB (from cache)")
        except FileNotFoundError as e:
            logger.error(f"[whisper] {e}")
            raise
        except Exception as e:
            logger.error(f"[whisper] Failed to load: {e}", exc_info=True)
            raise

    async def _load_siglip(self):
        """Load SigLIP multimodal model from cache (fail fast if not cached)."""
        try:
            model_path = os.getenv("VISION_MODEL_NAME", "google/siglip-so400m-patch14-384")
            cache_dir = os.getenv("HF_HUB_CACHE", os.getenv("MODELS_DIR", "./models") + "/.cache")

            logger.info(f"[siglip] Loading {model_path} from cache...")
            logger.info(f"[siglip] Cache directory: {cache_dir}")

            # Check cache directory exists
            model_cache_name = f"models--{model_path.replace('/', '--')}"
            model_cache_path = os.path.join(cache_dir, model_cache_name)

            if not os.path.exists(model_cache_path):
                raise FileNotFoundError(
                    f"SigLIP model not found in cache ({model_cache_path}). "
                    f"Model downloader may have failed. Offline mode is enabled."
                )

            start = time.time()
            # local_files_only=True enforces cache-only loading (no download fallback)
            processor = AutoProcessor.from_pretrained(
                model_path,
                cache_dir=cache_dir,
                local_files_only=True
            )
            model = AutoModel.from_pretrained(
                model_path,
                cache_dir=cache_dir,
                local_files_only=True
            )
            model = model.to(self.device)
            model.eval()  # Set to evaluation mode
            elapsed = time.time() - start

            self.models["siglip"] = {
                "model": model,
                "processor": processor,
                "device": self.device
            }

            # Estimate memory
            memory_mb = sum(p.numel() * p.element_size() for p in model.parameters()) / 1024 / 1024
            model_memory_bytes.labels(model="siglip").set(memory_mb * 1024 * 1024)

            logger.info(f"[siglip] Loaded in {elapsed:.2f}s, ~{memory_mb:.0f}MB (from cache)")
        except FileNotFoundError as e:
            logger.error(f"[siglip] {e}")
            raise
        except Exception as e:
            logger.error(f"[siglip] Failed to load: {e}", exc_info=True)
            raise

    async def _load_bge_m3(self):
        """Load BGE-M3 text embedding model (optional)."""
        try:
            logger.info("[bge-m3] Loading...")

            start = time.time()
            model = FlagModel(
                "BAAI/bge-m3",
                query_instruction_for_retrieval="Represent this sentence for searching relevant passages:",
                use_fp16=True if self.device == "cuda" else False,
                cache_dir=os.getenv("MODELS_DIR", "./models") + "/.cache",
                devices=[self.device]
            )
            elapsed = time.time() - start

            self.models["bge-m3"] = model

            logger.info(f"[bge-m3] Loaded in {elapsed:.2f}s")
        except Exception as e:
            logger.error(f"[bge-m3] Failed to load: {e}", exc_info=True)
            # Non-critical, continue

    async def _load_yunet(self):
        """Load YuNet face detection model from cache (fail fast if not cached)."""
        try:
            # Only load if face detection is enabled
            if os.getenv("FEATURE_FACE", "false").lower() != "true":
                logger.info("[yunet] Face detection disabled, skipping")
                return

            logger.info("[yunet] Loading face detector from cache...")

            cache_dir = os.getenv("HF_HUB_CACHE", os.getenv("MODELS_DIR", "./models") + "/.cache")
            yunet_path = os.path.join(cache_dir, "face_detection_yunet_2023mar.onnx")

            # Fail fast if not cached (offline mode)
            if not os.path.exists(yunet_path):
                raise FileNotFoundError(
                    f"YuNet model not found in cache ({yunet_path}). "
                    f"Model downloader may have failed. Offline mode is enabled."
                )

            detector = cv2.FaceDetectorYN.create(
                model=yunet_path,
                config="",
                input_size=(320, 320),
                score_threshold=0.6,
                nms_threshold=0.3,
            )

            self.models["yunet"] = detector
            logger.info(f"[yunet] Loaded successfully (from cache: {yunet_path})")
        except FileNotFoundError as e:
            logger.error(f"[yunet] {e}")
            raise
        except Exception as e:
            logger.error(f"[yunet] Failed to load: {e}", exc_info=True)
            raise

    async def _warmup_models(self):
        """Warmup models to compile kernels and verify functionality."""
        logger.info("[models] Warming up models...")

        try:
            # Warmup SigLIP text
            if "siglip" in self.models:
                processor = self.models["siglip"]["processor"]
                model = self.models["siglip"]["model"]

                inputs = processor(text=["warmup test"], return_tensors="pt", padding=True)
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                with torch.no_grad():
                    _ = model.get_text_features(**inputs)

                logger.info("[siglip] Text encoder warmed up")

                # Warmup SigLIP vision
                dummy_image = Image.new("RGB", (384, 384), color="white")
                inputs = processor(images=dummy_image, return_tensors="pt")
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                with torch.no_grad():
                    _ = model.get_image_features(**inputs)

                logger.info("[siglip] Vision encoder warmed up")

            logger.info("[models] Warmup complete")
        except Exception as e:
            logger.warning(f"[models] Warmup failed (non-critical): {e}")

    async def transcribe_audio(self, audio_bytes: bytes, language: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe audio using Whisper."""
        start = time.time()

        try:
            # Save to temp file (Whisper requires file path)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                model = self.models["whisper"]

                # Transcribe
                result = model.transcribe(
                    tmp_path,
                    language=language,
                    fp16=True if self.device == "cuda" else False
                )

                latency = (time.time() - start) * 1000

                inference_requests_total.labels(model="whisper", status="success").inc()
                inference_latency_seconds.labels(model="whisper").observe(latency / 1000)

                return {
                    "text": result["text"],
                    "segments": result["segments"],
                    "language": result["language"],
                    "latency_ms": latency
                }
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            inference_requests_total.labels(model="whisper", status="error").inc()
            logger.error(f"[whisper] Transcription failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    async def generate_text_embedding(self, text: str, model_name: str = "siglip") -> Dict[str, Any]:
        """Generate text embedding."""
        start = time.time()

        try:
            if model_name == "siglip" and "siglip" in self.models:
                siglip = self.models["siglip"]
                processor = siglip["processor"]
                model = siglip["model"]

                # SigLIP has max_position_embeddings=64, so truncate long text
                inputs = processor(
                    text=[text],
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=64
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                with torch.no_grad():
                    outputs = model.get_text_features(**inputs)

                embedding = outputs[0].cpu().numpy().tolist()

            elif model_name == "bge-m3" and "bge-m3" in self.models:
                model = self.models["bge-m3"]
                embedding = model.encode([text], convert_to_numpy=True)[0].tolist()

            else:
                raise HTTPException(status_code=400, detail=f"Model '{model_name}' not available")

            latency = (time.time() - start) * 1000

            inference_requests_total.labels(model=model_name, status="success").inc()
            inference_latency_seconds.labels(model=model_name).observe(latency / 1000)

            return {
                "embedding": embedding,
                "dimension": len(embedding),
                "model": model_name,
                "latency_ms": latency
            }

        except HTTPException:
            raise
        except Exception as e:
            inference_requests_total.labels(model=model_name, status="error").inc()
            logger.error(f"[{model_name}] Embedding failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

    async def generate_vision_embedding(self, image_bytes: bytes) -> Dict[str, Any]:
        """Generate vision embedding using SigLIP."""
        start = time.time()

        try:
            if "siglip" not in self.models:
                raise HTTPException(status_code=503, detail="SigLIP model not loaded")

            siglip = self.models["siglip"]
            processor = siglip["processor"]
            model = siglip["model"]

            # Load image
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            # Process
            inputs = processor(images=image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = model.get_image_features(**inputs)

            embedding = outputs[0].cpu().numpy().tolist()
            latency = (time.time() - start) * 1000

            inference_requests_total.labels(model="siglip", status="success").inc()
            inference_latency_seconds.labels(model="siglip").observe(latency / 1000)

            return {
                "embedding": embedding,
                "dimension": len(embedding),
                "latency_ms": latency
            }

        except HTTPException:
            raise
        except Exception as e:
            inference_requests_total.labels(model="siglip", status="error").inc()
            logger.error(f"[siglip] Vision embedding failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Vision embedding failed: {str(e)}")

    async def detect_faces(self, image_bytes: bytes) -> Dict[str, Any]:
        """Detect faces using YuNet."""
        start = time.time()

        try:
            if "yunet" not in self.models or self.models["yunet"] is None:
                raise HTTPException(status_code=503, detail="YuNet model not loaded")

            detector = self.models["yunet"]

            # Decode image
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                raise HTTPException(status_code=400, detail="Invalid image")

            h, w = image.shape[:2]
            detector.setInputSize((w, h))

            # Detect
            _, faces = detector.detect(image)

            face_list = []
            if faces is not None:
                for face in faces:
                    face_list.append({
                        "bbox": face[:4].tolist(),  # x, y, w, h
                        "confidence": float(face[14]),
                        "landmarks": face[4:14].reshape(-1, 2).tolist()  # 5 landmarks
                    })

            latency = (time.time() - start) * 1000

            inference_requests_total.labels(model="yunet", status="success").inc()
            inference_latency_seconds.labels(model="yunet").observe(latency / 1000)

            return {
                "faces": face_list,
                "count": len(face_list),
                "latency_ms": latency
            }

        except HTTPException:
            raise
        except Exception as e:
            inference_requests_total.labels(model="yunet", status="error").inc()
            logger.error(f"[yunet] Face detection failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Face detection failed: {str(e)}")


# ============================================================================
# FastAPI Lifespan - Model Loading
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup, cleanup on shutdown."""
    global model_manager

    logger.info("[app] Starting model service...")

    # Load all models
    model_manager = ModelManager()
    await model_manager.load_all_models()

    logger.info("[app] Model service ready")

    yield

    logger.info("[app] Shutting down model service...")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Heimdex Model Service",
    description="Centralized ML model inference service",
    version="1.0.0",
    lifespan=lifespan
)

model_manager: Optional[ModelManager] = None


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    # Calculate memory usage
    if torch.cuda.is_available():
        memory_bytes = torch.cuda.memory_allocated()
        memory_gb = memory_bytes / 1024 / 1024 / 1024
    else:
        memory_gb = 0.0

    uptime = time.time() - model_manager.start_time

    return HealthResponse(
        status="healthy",
        models_loaded=list(model_manager.models.keys()),
        device=model_manager.device,
        memory_used_gb=memory_gb,
        uptime_seconds=uptime
    )


@app.post("/asr/transcribe", response_model=ASRResponse)
async def transcribe_audio(request: ASRRequest):
    """Transcribe audio to text using Whisper."""
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(request.audio_base64)

        # Transcribe
        result = await model_manager.transcribe_audio(audio_bytes, request.language)

        return ASRResponse(**result)

    except Exception as e:
        logger.error(f"[asr] Request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed/text", response_model=TextEmbeddingResponse)
async def embed_text(request: TextEmbeddingRequest):
    """Generate text embedding."""
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    result = await model_manager.generate_text_embedding(request.text, request.model)
    return TextEmbeddingResponse(**result)


@app.post("/embed/vision", response_model=VisionEmbeddingResponse)
async def embed_vision(request: VisionEmbeddingRequest):
    """Generate vision embedding from image."""
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    try:
        # Decode base64 image
        image_bytes = base64.b64decode(request.image_base64)

        result = await model_manager.generate_vision_embedding(image_bytes)
        return VisionEmbeddingResponse(**result)

    except Exception as e:
        logger.error(f"[vision] Request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/face/detect", response_model=FaceDetectionResponse)
async def detect_faces(file: UploadFile = File(...)):
    """Detect faces in uploaded image."""
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    try:
        image_bytes = await file.read()
        result = await model_manager.detect_faces(image_bytes)
        return FaceDetectionResponse(**result)

    except Exception as e:
        logger.error(f"[face] Request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    """Root endpoint - service info."""
    return {
        "service": "Heimdex Model Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "asr": "/asr/transcribe",
            "text_embedding": "/embed/text",
            "vision_embedding": "/embed/vision",
            "face_detection": "/face/detect",
            "metrics": "/metrics"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )

"""
Model Service Client

HTTP client for calling the centralized model service.
Replaces direct model loading with HTTP-based inference calls.
"""

import os
import base64
from typing import Optional, Dict, List, Any
import httpx
import numpy as np
from PIL import Image
import io


class ModelServiceClient:
    """Client for model service inference endpoints."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 60.0):
        """
        Initialize model service client.

        Args:
            base_url: Model service base URL (default: from MODEL_SERVICE_URL env)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("MODEL_SERVICE_URL", "http://localhost:8001")
        self.timeout = timeout
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def health_check(self) -> Dict[str, Any]:
        """
        Check model service health.

        Returns:
            Health status dict
        """
        response = self.client.get("/health")
        response.raise_for_status()
        return response.json()

    def transcribe_audio(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio file using Whisper.

        Args:
            audio_path: Path to audio file
            language: Optional language hint (e.g., 'en', 'es')

        Returns:
            Dict with 'text', 'segments', 'language', 'latency_ms'
        """
        # Read and encode audio
        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()

        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        # Call service
        payload = {
            "audio_base64": audio_b64,
            "language": language
        }

        response = self.client.post("/asr/transcribe", json=payload)
        response.raise_for_status()

        return response.json()

    def generate_text_embedding(
        self,
        text: str,
        model: str = "siglip"
    ) -> np.ndarray:
        """
        Generate text embedding.

        Args:
            text: Text to embed
            model: Model to use ('siglip' or 'bge-m3')

        Returns:
            Numpy array embedding
        """
        payload = {
            "text": text,
            "model": model
        }

        response = self.client.post("/embed/text", json=payload)
        response.raise_for_status()

        result = response.json()
        return np.array(result["embedding"], dtype=np.float32)

    def generate_vision_embedding(
        self,
        image: Image.Image
    ) -> np.ndarray:
        """
        Generate vision embedding from PIL Image.

        Args:
            image: PIL Image

        Returns:
            Numpy array embedding
        """
        # Convert image to bytes
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        # Encode as base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        payload = {
            "image_base64": image_b64
        }

        response = self.client.post("/embed/vision", json=payload)
        response.raise_for_status()

        result = response.json()
        return np.array(result["embedding"], dtype=np.float32)

    def detect_faces(
        self,
        image_path: str
    ) -> List[Dict[str, Any]]:
        """
        Detect faces in image.

        Args:
            image_path: Path to image file

        Returns:
            List of face detections with bbox, confidence, landmarks
        """
        with open(image_path, 'rb') as f:
            files = {'file': ('image.jpg', f, 'image/jpeg')}
            response = self.client.post("/face/detect", files=files)

        response.raise_for_status()

        result = response.json()
        return result["faces"]


# Convenience functions matching old API

def generate_text_embedding(text: str, model_name: str = "siglip") -> Optional[np.ndarray]:
    """
    Generate text embedding (drop-in replacement for old function).

    Args:
        text: Text to embed
        model_name: Model to use

    Returns:
        Numpy array embedding or None on error
    """
    try:
        with ModelServiceClient() as client:
            return client.generate_text_embedding(text, model=model_name)
    except Exception as e:
        print(f"[model-client] Text embedding failed: {e}")
        return None


def generate_vision_embedding(image: Image.Image) -> Optional[np.ndarray]:
    """
    Generate vision embedding (drop-in replacement for old function).

    Args:
        image: PIL Image

    Returns:
        Numpy array embedding or None on error
    """
    try:
        with ModelServiceClient() as client:
            return client.generate_vision_embedding(image)
    except Exception as e:
        print(f"[model-client] Vision embedding failed: {e}")
        return None

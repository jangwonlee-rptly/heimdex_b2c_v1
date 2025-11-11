"""
Face embedding computation for Heimdex B2C people profiles.

This module handles face detection and embedding extraction from enrollment photos:
1. Download photos from storage
2. Detect faces using YuNet (OpenCV)
3. Extract face embeddings using AdaFace
4. Compute centroid embedding from all photos
5. Update FaceProfile.adaface_vec
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional
from uuid import UUID
import numpy as np

import dramatiq
from tasks import redis_broker
import cv2
from PIL import Image

dramatiq.set_broker(redis_broker)


# Global models (loaded once per worker)
_face_models = {}


def get_face_model(model_name: str):
    """Lazy-load face detection and recognition models."""
    if model_name not in _face_models:
        if model_name == "yunet":
            # Load YuNet face detector (OpenCV)
            print("[face] Loading YuNet face detector")
            model_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

            # Try to use YuNet if available, otherwise fall back to Haar Cascade
            try:
                # YuNet model path (download if needed)
                yunet_path = "/app/models/.cache/face_detection_yunet_2023mar.onnx"
                if not os.path.exists(yunet_path):
                    # Download YuNet model
                    import urllib.request
                    os.makedirs(os.path.dirname(yunet_path), exist_ok=True)
                    url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
                    print(f"[face] Downloading YuNet model from {url}")
                    urllib.request.urlretrieve(url, yunet_path)

                # Initialize YuNet detector
                _face_models["yunet"] = cv2.FaceDetectorYN.create(
                    model=yunet_path,
                    config="",
                    input_size=(320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                )
                print("[face] YuNet face detector loaded")
            except Exception as e:
                print(f"[face] Failed to load YuNet, falling back to Haar Cascade: {e}")
                # Fallback to Haar Cascade
                _face_models["yunet"] = cv2.CascadeClassifier(model_path)
                print("[face] Haar Cascade face detector loaded (fallback)")

        elif model_name == "adaface":
            # Load AdaFace face recognition model
            # Note: This is a placeholder - actual AdaFace model loading
            # depends on the specific library we use
            print("[face] Loading AdaFace face recognition model")

            # For now, we'll use a simple feature extractor
            # In production, you'd load actual AdaFace model
            # Example: from adaface import AdaFace
            # _face_models["adaface"] = AdaFace(model_path="...")

            # Placeholder: Use a simple face feature extractor
            # This should be replaced with actual AdaFace model
            _face_models["adaface"] = {
                "type": "placeholder",
                "dimensions": 512
            }
            print("[face] AdaFace model loaded (placeholder)")

    return _face_models[model_name]


def detect_face(image_path: str) -> Optional[np.ndarray]:
    """
    Detect face in image using YuNet.

    Args:
        image_path: Path to image file

    Returns:
        Face bounding box [x, y, w, h] or None if no face detected
    """
    detector = get_face_model("yunet")

    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"[face] Failed to load image: {image_path}")
        return None

    # Convert to RGB
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    try:
        # YuNet detection
        if isinstance(detector, cv2.FaceDetectorYN):
            # Set input size to match image
            height, width = img.shape[:2]
            detector.setInputSize((width, height))

            # Detect faces
            _, faces = detector.detect(img)

            if faces is None or len(faces) == 0:
                print("[face] No face detected in image")
                return None

            # Return first face (bounding box)
            # YuNet returns: [x, y, w, h, ...landmarks...]
            face = faces[0]
            bbox = face[:4].astype(int)
            print(f"[face] Detected face at: {bbox}")
            return bbox

        else:
            # Haar Cascade detection (fallback)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )

            if len(faces) == 0:
                print("[face] No face detected in image")
                return None

            # Return first face
            bbox = faces[0]
            print(f"[face] Detected face at: {bbox}")
            return bbox

    except Exception as e:
        print(f"[face] Face detection error: {e}")
        return None


def extract_face_embedding(image_path: str, bbox: np.ndarray) -> Optional[np.ndarray]:
    """
    Extract face embedding from detected face.

    Args:
        image_path: Path to image file
        bbox: Face bounding box [x, y, w, h]

    Returns:
        Face embedding vector (512 dimensions) or None if extraction fails
    """
    model = get_face_model("adaface")

    # Load image
    img = cv2.imread(image_path)
    if img is None:
        return None

    # Crop face region
    x, y, w, h = bbox
    face_crop = img[y:y+h, x:x+w]

    # Resize to standard size (112x112 for face recognition)
    face_resized = cv2.resize(face_crop, (112, 112))

    # Normalize
    face_normalized = face_resized.astype(np.float32) / 255.0

    # TODO: Replace with actual AdaFace embedding extraction
    # For now, create a simple feature vector as placeholder
    # In production: embedding = model.get_embedding(face_normalized)

    # Placeholder: Simple feature extraction
    # Flatten and reduce dimensions to 512
    flattened = face_normalized.flatten()

    # Simple dimensionality reduction (average pooling)
    # This is NOT a real face embedding - replace with AdaFace
    target_dim = 512
    pool_size = len(flattened) // target_dim
    embedding = np.array([
        flattened[i*pool_size:(i+1)*pool_size].mean()
        for i in range(target_dim)
    ])

    # Normalize to unit vector
    embedding = embedding / np.linalg.norm(embedding)

    print(f"[face] Extracted embedding with {len(embedding)} dimensions")
    return embedding


@dramatiq.actor(queue_name="face_processing", max_retries=2, time_limit=300000)  # 5 min timeout
def compute_face_embedding(person_id_str: str):
    """
    Compute face embedding for a person profile.

    This task:
    1. Downloads all enrollment photos for the person
    2. Detects faces in each photo
    3. Extracts face embeddings
    4. Computes centroid (average) of all embeddings
    5. Updates FaceProfile.adaface_vec in database

    Args:
        person_id_str: UUID of the person profile
    """
    print(f"[face] Starting face embedding computation for person_id={person_id_str}")

    person_id = UUID(person_id_str)

    # Check if face enrollment is enabled
    feature_face_enrollment = os.getenv("FEATURE_FACE_ENROLLMENT", "false").lower() == "true"
    if not feature_face_enrollment:
        print("[face] Face enrollment is disabled, skipping")
        return

    # Connect to database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("POSTGRES_URL", "postgresql://heimdex:heimdex@db:5432/heimdex")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get person profile
        from app.models.face import FaceProfile

        person = session.query(FaceProfile).filter(FaceProfile.person_id == person_id).first()
        if not person:
            raise ValueError(f"Person profile {person_id} not found")

        print(f"[face] Processing person '{person.name}' with {len(person.photo_keys or [])} photos")

        if not person.photo_keys or len(person.photo_keys) == 0:
            print("[face] No photos to process")
            return

        # Download photos and extract embeddings
        from minio import Minio

        minio_client = Minio(
            os.getenv("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=False,
        )

        embeddings = []

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            for idx, photo_key in enumerate(person.photo_keys):
                print(f"[face] Processing photo {idx+1}/{len(person.photo_keys)}: {photo_key}")

                # Download photo
                photo_path = temp_path / f"photo_{idx}.jpg"

                try:
                    minio_client.fget_object(
                        bucket_name=os.getenv("STORAGE_BUCKET_UPLOADS", "uploads"),
                        object_name=photo_key,
                        file_path=str(photo_path),
                    )
                except Exception as e:
                    print(f"[face] Failed to download photo {photo_key}: {e}")
                    continue

                # Detect face
                bbox = detect_face(str(photo_path))
                if bbox is None:
                    print(f"[face] No face detected in photo {idx+1}")
                    continue

                # Extract embedding
                embedding = extract_face_embedding(str(photo_path), bbox)
                if embedding is None:
                    print(f"[face] Failed to extract embedding from photo {idx+1}")
                    continue

                embeddings.append(embedding)
                print(f"[face] Successfully extracted embedding from photo {idx+1}")

        # Check if we got any valid embeddings
        if len(embeddings) == 0:
            print("[face] No valid face embeddings extracted")
            return

        # Compute centroid (average of all embeddings)
        centroid = np.mean(embeddings, axis=0)

        # Normalize centroid to unit vector
        centroid = centroid / np.linalg.norm(centroid)

        print(f"[face] Computed centroid from {len(embeddings)} embeddings")

        # Update database
        person.adaface_vec = centroid.tolist()
        session.commit()

        print(f"[face] Successfully updated face embedding for person {person_id}")

    except Exception as e:
        print(f"[face] Error computing face embedding: {e}")
        session.rollback()
        raise

    finally:
        session.close()

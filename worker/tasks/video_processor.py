"""
Comprehensive video processing pipeline for Heimdex B2C.

This module handles the complete video indexing workflow:
1. Validation (ffprobe)
2. Audio extraction
3. ASR transcription (Whisper)
4. Scene detection (PySceneDetect)
5. Text embedding (BGE-M3)
6. Vision embedding (SigLIP)
7. Sidecar generation
8. Database commit
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from uuid import UUID
import numpy as np

import dramatiq
from tasks import redis_broker
from scenedetect import detect, ContentDetector
import torch
from transformers import AutoTokenizer, AutoModel, AutoProcessor
from FlagEmbedding import FlagModel
import whisper
from PIL import Image
import cv2


dramatiq.set_broker(redis_broker)


# Global models (loaded once per worker)
_models = {}


def get_model(model_name: str):
    """Lazy-load models."""
    if model_name not in _models:
        if model_name == "whisper":
            model_size = os.getenv("ASR_MODEL", "medium")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[worker] Loading Whisper {model_size} on {device}")
            _models["whisper"] = whisper.load_model(model_size, device=device)

        elif model_name == "bge-m3":
            # Use repo ID - HuggingFace will cache to HF_HOME or default cache
            print(f"[worker] Loading BGE-M3 from HuggingFace")
            _models["bge-m3"] = FlagModel(
                "BAAI/bge-m3",
                query_instruction_for_retrieval="Represent this sentence for searching relevant passages:",
                use_fp16=False,
                cache_dir="/app/models/.cache"  # Cache models here
            )

        elif model_name == "siglip":
            model_path = os.getenv("VISION_MODEL_NAME", "google/siglip-so400m-patch14-384")
            print(f"[worker] Loading SigLIP from {model_path}")
            processor = AutoProcessor.from_pretrained(model_path)
            model = AutoModel.from_pretrained(model_path)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = model.to(device)
            _models["siglip"] = {"model": model, "processor": processor, "device": device}

    return _models[model_name]


@dramatiq.actor(queue_name="video_processing", max_retries=2, time_limit=600000)  # 10 min timeout
def process_video(video_id_str: str):
    """
    Main video processing pipeline.

    Args:
        video_id_str: UUID of the video to process

    Flow:
        1. Validate video with ffprobe
        2. Extract audio
        3. Run Whisper ASR
        4. Detect scenes
        5. Generate text embeddings
        6. Generate vision embeddings
        7. Build sidecar
        8. Commit to database
    """
    print(f"[worker] Starting processing for video_id={video_id_str}")

    video_id = UUID(video_id_str)

    # Connect to database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("POSTGRES_URL", "postgresql://heimdex:heimdex@db:5432/heimdex")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get video record
        from app.models.video import Video
        from app.models.scene import Scene
        from app.models.job import Job

        video = session.query(Video).filter(Video.video_id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")

        print(f"[worker] Processing video: {video.storage_key}")

        # Download video from storage
        from minio import Minio
        minio_client = Minio(
            os.getenv("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            secure=False,
        )

        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_path = temp_path / "video.mp4"

            # Download video
            print(f"[worker] Downloading video from {video.storage_key}")
            minio_client.fget_object(
                bucket_name=os.getenv("STORAGE_BUCKET_UPLOADS", "uploads"),
                object_name=video.storage_key,
                file_path=str(video_path),
            )

            # Step 1: Validate with ffprobe
            print(f"[worker] Validating video with ffprobe")
            duration_s = validate_video(str(video_path))
            video.duration_s = duration_s
            video.state = 'processing'
            session.commit()

            # Step 2: Extract audio
            print(f"[worker] Extracting audio")
            audio_path = temp_path / "audio.wav"
            extract_audio(str(video_path), str(audio_path))

            # Step 3: Run Whisper ASR
            print(f"[worker] Running Whisper ASR")
            whisper_model = get_model("whisper")
            transcript_segments = run_whisper(whisper_model, str(audio_path))

            # Step 4: Detect scenes
            print(f"[worker] Detecting scenes")
            scene_timestamps = detect_scenes(str(video_path))

            # Step 5 & 6: Generate embeddings and create scene records
            print(f"[worker] Generating embeddings and creating scene records")
            bge_model = get_model("bge-m3")
            siglip = get_model("siglip")

            for i, (start_s, end_s) in enumerate(scene_timestamps):
                # Find relevant transcript segments
                scene_transcript = get_scene_transcript(transcript_segments, start_s, end_s)

                # Generate text embedding
                text_embedding = None
                if scene_transcript:
                    text_embedding = generate_text_embedding(bge_model, scene_transcript)

                # Generate vision embedding (sample middle frame)
                mid_time = (start_s + end_s) / 2
                frame = extract_frame(str(video_path), mid_time)
                vision_embedding = generate_vision_embedding(siglip, frame)

                # Create scene record
                scene = Scene(
                    video_id=video.video_id,
                    start_s=start_s,
                    end_s=end_s,
                    transcript=scene_transcript,
                    text_vec=text_embedding.tolist() if text_embedding is not None else None,
                    image_vec=vision_embedding.tolist() if vision_embedding is not None else None,
                )
                session.add(scene)

                print(f"[worker] Created scene {i+1}/{len(scene_timestamps)}: {start_s:.1f}s-{end_s:.1f}s")

            # Commit all scenes
            session.commit()

            # Step 7: Update video state to indexed
            video.state = 'indexed'
            video.indexed_at = datetime.utcnow()
            session.commit()

            print(f"[worker] Successfully processed video {video_id}")
            print(f"[worker] Created {len(scene_timestamps)} scenes")

    except Exception as e:
        print(f"[worker] Error processing video {video_id}: {str(e)}")
        import traceback
        traceback.print_exc()

        # Update video state to failed
        try:
            video = session.query(Video).filter(Video.video_id == video_id).first()
            if video:
                video.state = 'failed'
                video.error_text = str(e)
                session.commit()
        except:
            pass

        raise

    finally:
        session.close()


def validate_video(video_path: str) -> float:
    """
    Validate video with ffprobe and return duration.

    Args:
        video_path: Path to video file

    Returns:
        Duration in seconds

    Raises:
        ValueError: If video is invalid
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"Invalid video file: {result.stderr}")

    try:
        duration = float(result.stdout.strip())
    except ValueError:
        raise ValueError("Could not parse video duration")

    return duration


def extract_audio(video_path: str, audio_path: str):
    """
    Extract audio from video as 16kHz mono WAV.

    Args:
        video_path: Path to video file
        audio_path: Output path for audio file
    """
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",  # No video
        "-acodec", "pcm_s16le",  # PCM 16-bit
        "-ar", "16000",  # 16kHz sample rate
        "-ac", "1",  # Mono
        "-y",  # Overwrite output
        audio_path,
    ]

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr.decode()}")


def run_whisper(model, audio_path: str) -> List[Dict]:
    """
    Run Whisper ASR on audio file.

    Args:
        model: Whisper model
        audio_path: Path to audio file

    Returns:
        List of transcript segments with timestamps
    """
    result = model.transcribe(
        audio_path,
        language="ko",  # Korean (change as needed)
        task="transcribe",
        verbose=False,
    )

    return result["segments"]


def detect_scenes(video_path: str, threshold: float = 27.0) -> List[Tuple[float, float]]:
    """
    Detect scene changes in video.

    Args:
        video_path: Path to video file
        threshold: Content detection threshold (lower = more sensitive)

    Returns:
        List of (start_time, end_time) tuples in seconds
    """
    scene_list = detect(video_path, ContentDetector(threshold=threshold))

    # Convert to (start, end) tuples
    scenes = []
    for i, scene in enumerate(scene_list):
        start_s = scene[0].get_seconds()
        end_s = scene[1].get_seconds()
        scenes.append((start_s, end_s))

    # If no scenes detected, treat entire video as one scene
    if not scenes:
        duration = validate_video(video_path)
        scenes = [(0.0, duration)]

    return scenes


def get_scene_transcript(segments: List[Dict], start_s: float, end_s: float) -> str:
    """
    Get transcript for a specific time range.

    Args:
        segments: Whisper transcript segments
        start_s: Scene start time in seconds
        end_s: Scene end time in seconds

    Returns:
        Concatenated transcript text
    """
    scene_text = []
    for segment in segments:
        seg_start = segment["start"]
        seg_end = segment["end"]

        # Check if segment overlaps with scene
        if seg_start < end_s and seg_end > start_s:
            scene_text.append(segment["text"].strip())

    return " ".join(scene_text)


def generate_text_embedding(model, text: str) -> Optional[np.ndarray]:
    """
    Generate text embedding using BGE-M3.

    Args:
        model: BGE-M3 model
        text: Input text

    Returns:
        1024-dim embedding vector
    """
    if not text or not text.strip():
        return None

    embeddings = model.encode([text])
    return embeddings[0]  # Return first (and only) embedding


def extract_frame(video_path: str, timestamp: float) -> Image.Image:
    """
    Extract a single frame from video at given timestamp.

    Args:
        video_path: Path to video file
        timestamp: Time in seconds

    Returns:
        PIL Image
    """
    cap = cv2.VideoCapture(video_path)

    # Set position
    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)

    # Read frame
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError(f"Could not extract frame at {timestamp}s")

    # Convert BGR to RGB
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Convert to PIL Image
    return Image.fromarray(frame_rgb)


def generate_vision_embedding(siglip: Dict, image: Image.Image) -> np.ndarray:
    """
    Generate vision embedding using SigLIP.

    Args:
        siglip: SigLIP model dict
        image: PIL Image

    Returns:
        1152-dim embedding vector
    """
    model = siglip["model"]
    processor = siglip["processor"]
    device = siglip["device"]

    # Process image
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    # Generate embedding
    with torch.no_grad():
        outputs = model.get_image_features(**inputs)

    # Normalize
    embedding = outputs[0].cpu().numpy()
    embedding = embedding / np.linalg.norm(embedding)

    return embedding

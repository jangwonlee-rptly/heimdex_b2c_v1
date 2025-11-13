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
from PIL import Image
import cv2
import sys
sys.path.insert(0, '/app')
from shared.model_client.client import ModelServiceClient


dramatiq.set_broker(redis_broker)


# Global model service client
_model_client = None


def get_model_client() -> ModelServiceClient:
    """Get or create model service client."""
    global _model_client
    if _model_client is None:
        model_service_url = os.getenv("MODEL_SERVICE_URL", "http://model-service:8001")
        print(f"[worker] Connecting to model service: {model_service_url}")
        _model_client = ModelServiceClient(base_url=model_service_url, timeout=600.0)
    return _model_client


def detect_and_match_faces(image: Image.Image, enrolled_profiles: List[Dict]) -> List[Dict]:
    """
    Detect faces in image and match against enrolled profiles using model service.

    Args:
        image: PIL Image to detect faces in
        enrolled_profiles: List of dicts with person_id, name, embedding

    Returns:
        List of matched people with person_id, name, confidence
    """
    # Check if face detection is enabled
    feature_face_detection = os.getenv("FEATURE_FACE_DETECTION", "false").lower() == "true"
    if not feature_face_detection or not enrolled_profiles:
        return []

    try:
        # Save image to temp file for face detection
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            image.save(tmp.name, format="JPEG")
            tmp_path = tmp.name

        try:
            # Call model service for face detection
            client = get_model_client()
            faces = client.detect_faces(tmp_path)
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        if not faces:
            return []

        # Convert PIL Image to OpenCV format for face extraction
        img_np = np.array(image)
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        matched_people = []
        similarity_threshold = float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.6"))

        for face in faces:
            # Extract face bounding box from model service response
            bbox = face.get("bbox", [])
            if len(bbox) < 4:
                continue

            x, y, w, h = [int(v) for v in bbox]

            # Crop and resize face
            face_crop = img_cv[y:y+h, x:x+w]
            face_resized = cv2.resize(face_crop, (112, 112))
            face_normalized = face_resized.astype(np.float32) / 255.0

            # Extract embedding (placeholder - same as face_processor.py)
            flattened = face_normalized.flatten()
            target_dim = 512
            pool_size = len(flattened) // target_dim
            face_embedding = np.array([
                flattened[i*pool_size:(i+1)*pool_size].mean()
                for i in range(target_dim)
            ])
            face_embedding = face_embedding / np.linalg.norm(face_embedding)

            # Match against enrolled profiles
            best_match = None
            best_similarity = 0.0

            for profile in enrolled_profiles:
                if profile["embedding"] is None:
                    continue

                # Compute cosine similarity
                enrolled_embedding = np.array(profile["embedding"])
                similarity = np.dot(face_embedding, enrolled_embedding)

                if similarity > best_similarity and similarity >= similarity_threshold:
                    best_similarity = similarity
                    best_match = profile

            if best_match:
                matched_people.append({
                    "person_id": best_match["person_id"],
                    "name": best_match["name"],
                    "confidence": float(best_similarity)
                })

        return matched_people

    except Exception as e:
        print(f"[worker] Face detection error: {e}")
        import traceback
        traceback.print_exc()
        return []


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
        from app.models.video_metadata import VideoMetadata
        from app.models.scene import Scene
        from app.models.job import Job
        from sqlalchemy.orm import selectinload

        video = session.query(Video).options(selectinload(Video.video_metadata)).filter(Video.video_id == video_id).first()
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

            # Step 3: Run Whisper ASR via model service
            print(f"[worker] Running Whisper ASR via model service")
            client = get_model_client()
            transcript_result = client.transcribe_audio(str(audio_path), language="ko")
            transcript_segments = transcript_result.get("segments", [])

            # Step 4: Detect scenes
            print(f"[worker] Detecting scenes")
            scene_timestamps = detect_scenes(str(video_path))

            # Step 4.5: Load enrolled face profiles for user (if face detection enabled)
            enrolled_profiles = []
            feature_face_detection = os.getenv("FEATURE_FACE_DETECTION", "false").lower() == "true"
            if feature_face_detection:
                from app.models.face import FaceProfile
                profiles = session.query(FaceProfile).filter(
                    FaceProfile.user_id == video.user_id,
                    FaceProfile.adaface_vec.isnot(None)
                ).all()
                enrolled_profiles = [
                    {
                        "person_id": str(p.person_id),
                        "name": p.name,
                        "embedding": p.adaface_vec
                    }
                    for p in profiles
                ]
                print(f"[worker] Loaded {len(enrolled_profiles)} enrolled face profiles")

            # Step 5 & 6: Generate embeddings and create scene records via model service
            print(f"[worker] Generating embeddings and creating scene records via model service")

            # Store scene-to-people mapping for later ScenePerson creation
            scene_people_map = {}
            # Store frames for thumbnail generation after commit
            scene_frames = {}

            for i, (start_s, end_s) in enumerate(scene_timestamps):
                # Find relevant transcript segments
                scene_transcript = get_scene_transcript(transcript_segments, start_s, end_s)

                # Generate text embedding via model service
                # If no transcript, use video title as fallback so scene is still searchable
                text_embedding = None
                video_title = video.video_metadata.title if video.video_metadata else None
                text_for_embedding = scene_transcript if scene_transcript else (video_title or "untitled video")
                if text_for_embedding:
                    text_embedding = client.generate_text_embedding(text_for_embedding, model="siglip")

                # Generate vision embedding (sample multiple frames) via model service
                # Sample 3 frames: 25%, 50%, 75% through the scene for better coverage
                scene_duration = end_s - start_s
                sample_times = [
                    start_s + scene_duration * 0.25,  # 25% through
                    start_s + scene_duration * 0.50,  # 50% through (middle)
                    start_s + scene_duration * 0.75,  # 75% through
                ]

                # Generate embeddings for each sample and average them
                frame_embeddings = []
                for sample_time in sample_times:
                    frame = extract_frame(str(video_path), sample_time)
                    frame_emb = client.generate_vision_embedding(frame)
                    if frame_emb is not None:
                        frame_embeddings.append(frame_emb)

                # Average the embeddings for more robust representation
                if frame_embeddings:
                    vision_embedding = np.mean(frame_embeddings, axis=0).astype(np.float32)
                    # Re-normalize after averaging
                    norm = np.linalg.norm(vision_embedding)
                    if norm > 0:
                        vision_embedding = vision_embedding / norm
                else:
                    vision_embedding = None

                # Use middle frame for thumbnail and face detection
                mid_time = (start_s + end_s) / 2
                frame = extract_frame(str(video_path), mid_time)

                # Store frame for thumbnail generation
                scene_frames[i] = frame

                # Detect faces in frame (if enabled)
                detected_people = detect_and_match_faces(frame, enrolled_profiles)

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

                # Store detected people for this scene (indexed by scene number)
                if detected_people:
                    scene_people_map[i] = detected_people
                    print(f"[worker] Created scene {i+1}/{len(scene_timestamps)}: {start_s:.1f}s-{end_s:.1f}s (detected {len(detected_people)} people)")
                else:
                    print(f"[worker] Created scene {i+1}/{len(scene_timestamps)}: {start_s:.1f}s-{end_s:.1f}s")

            # Commit all scenes
            session.commit()

            # Query committed scenes to get their IDs
            scenes = session.query(Scene).filter(Scene.video_id == video.video_id).all()

            # Step 6.3: Generate and upload thumbnails
            print(f"[worker] Generating and uploading thumbnails for {len(scenes)} scenes")
            for scene_idx, scene in enumerate(scenes):
                if scene_idx in scene_frames:
                    frame = scene_frames[scene_idx]
                    try:
                        thumbnail_key = save_thumbnail(frame, video.video_id, scene.scene_id, minio_client)
                        # Update scene with thumbnail key
                        session.query(Scene).filter(Scene.scene_id == scene.scene_id).update(
                            {"thumbnail_key": thumbnail_key},
                            synchronize_session=False
                        )
                        print(f"[worker] Saved thumbnail for scene {scene_idx + 1}/{len(scenes)}: {thumbnail_key}")
                    except Exception as e:
                        print(f"[worker] Warning: Failed to save thumbnail for scene {scene_idx + 1}: {e}")
                        # Continue processing even if thumbnail fails

            # Commit thumbnail keys
            session.commit()

            # Refresh scenes to get updated thumbnail_key values
            session.expire_all()
            scenes = session.query(Scene).filter(Scene.video_id == video.video_id).all()

            # Step 6.5: Create ScenePerson associations for detected faces
            if scene_people_map:
                from app.models.face import ScenePerson

                print(f"[worker] Creating ScenePerson associations for {len(scene_people_map)} scenes")
                scene_person_count = 0

                for scene_idx, detected_people in scene_people_map.items():
                    scene = scenes[scene_idx]  # scenes are in same order as scene_timestamps

                    for person in detected_people:
                        scene_person = ScenePerson(
                            scene_id=scene.scene_id,
                            person_id=UUID(person["person_id"]),
                            confidence=person["confidence"],
                            frame_count=1  # We only sample one frame per scene
                        )
                        session.add(scene_person)
                        scene_person_count += 1

                session.commit()
                print(f"[worker] Created {scene_person_count} ScenePerson associations")

            # Step 7: Generate and upload sidecars
            print(f"[worker] Generating sidecars for {len(scene_timestamps)} scenes")

            # Build transcript segments map for sidecars
            transcript_segments_serializable = [
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"]
                }
                for seg in transcript_segments
            ]

            for scene in scenes:
                # Query ScenePerson associations for this scene
                from app.models.face import ScenePerson, FaceProfile
                scene_people = session.query(ScenePerson).filter(
                    ScenePerson.scene_id == scene.scene_id
                ).all()

                # Build people list for sidecar
                people_list = []
                for sp in scene_people:
                    person = session.query(FaceProfile).filter(
                        FaceProfile.person_id == sp.person_id
                    ).first()
                    if person:
                        people_list.append({
                            "person_id": str(sp.person_id),
                            "name": person.name,
                            "confidence": sp.confidence,
                            "frame_count": sp.frame_count
                        })

                # Build sidecar JSON
                sidecar = build_sidecar(
                    video=video,
                    scene=scene,
                    transcript_segments=transcript_segments_serializable,
                    people=people_list,
                    language="ko"
                )

                # Upload to storage
                sidecar_key = f"sidecars/{video.user_id}/{video.video_id}/{scene.scene_id}.json"
                upload_sidecar(minio_client, sidecar, sidecar_key)

                # Update scene with sidecar key
                scene.sidecar_key = sidecar_key

                people_str = f" ({len(people_list)} people)" if people_list else ""
                print(f"[worker] Generated sidecar for scene {scene.scene_id}{people_str}")

            # Commit sidecar keys
            session.commit()
            print(f"[worker] Uploaded {len(scenes)} sidecars")

            # Step 8: Update video state to indexed
            video.state = 'indexed'
            video.indexed_at = datetime.utcnow()
            session.commit()

            print(f"[worker] Successfully processed video {video_id}")
            print(f"[worker] Created {len(scene_timestamps)} scenes with sidecars")

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


def save_thumbnail(frame: Image.Image, video_id: UUID, scene_id: UUID, minio_client) -> str:
    """
    Save scene thumbnail to MinIO storage.

    Args:
        frame: PIL Image to save as thumbnail
        video_id: UUID of the video
        scene_id: UUID of the scene
        minio_client: MinIO client instance

    Returns:
        Storage key for the thumbnail (e.g., "video_id/scene_id.webp")
    """
    from io import BytesIO

    # Generate thumbnail key
    thumbnail_key = f"{video_id}/{scene_id}.webp"

    # Resize to 320x180 (16:9 aspect ratio) for efficient storage
    # Maintain aspect ratio and crop if needed
    target_size = (320, 180)

    # Calculate aspect ratios
    img_aspect = frame.width / frame.height
    target_aspect = target_size[0] / target_size[1]

    if img_aspect > target_aspect:
        # Image is wider than target, crop width
        new_height = frame.height
        new_width = int(new_height * target_aspect)
        left = (frame.width - new_width) // 2
        frame = frame.crop((left, 0, left + new_width, frame.height))
    else:
        # Image is taller than target, crop height
        new_width = frame.width
        new_height = int(new_width / target_aspect)
        top = (frame.height - new_height) // 2
        frame = frame.crop((0, top, frame.width, top + new_height))

    # Resize to target size
    thumbnail = frame.resize(target_size, Image.Resampling.LANCZOS)

    # Save as WebP with quality 80 (good balance of size and quality)
    buffer = BytesIO()
    thumbnail.save(buffer, format="WEBP", quality=80)
    buffer.seek(0)

    # Upload to MinIO
    bucket = os.getenv("STORAGE_BUCKET_THUMBNAILS", "thumbnails")

    # Ensure bucket exists
    if not minio_client.bucket_exists(bucket):
        minio_client.make_bucket(bucket)

    minio_client.put_object(
        bucket_name=bucket,
        object_name=thumbnail_key,
        data=buffer,
        length=buffer.getbuffer().nbytes,
        content_type="image/webp"
    )

    return thumbnail_key


def build_sidecar(video, scene, transcript_segments: List[Dict], people: List[Dict] = None, language: str = "ko") -> Dict:
    """
    Build sidecar JSON for a scene.

    Args:
        video: Video model instance
        scene: Scene model instance
        transcript_segments: All transcript segments from Whisper
        people: List of detected people with person_id, name, confidence
        language: Transcript language

    Returns:
        Sidecar dictionary
    """
    # Find transcript segments for this scene
    scene_segments = []
    for seg in transcript_segments:
        seg_start = seg["start"]
        seg_end = seg["end"]
        scene_start = float(scene.start_s)
        scene_end = float(scene.end_s)

        # Check if segment overlaps with scene
        if seg_start < scene_end and seg_end > scene_start:
            scene_segments.append(seg)

    # Build sidecar structure
    sidecar = {
        "video_id": str(video.video_id),
        "scene_id": str(scene.scene_id),
        "start_s": float(scene.start_s),
        "end_s": float(scene.end_s),
        "duration_s": float(scene.end_s - scene.start_s),
        "transcript": {
            "text": scene.transcript or "",
            "segments": scene_segments,
            "language": language
        },
        "embeddings": {
            "text": {
                "model": "google/siglip-so400m-patch14-384",
                "dimensions": 1152,
                "stored_in_db": True,
                "has_embedding": scene.text_vec is not None
            },
            "vision": {
                "model": os.getenv("VISION_MODEL_NAME", "google/siglip-so400m-patch14-384"),
                "dimensions": 1152,
                "stored_in_db": True,
                "has_embedding": scene.image_vec is not None
            }
        },
        "vision_tags": scene.vision_tags or {},
        "people": people or [],  # Detected people in this scene
        "metadata": {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "version": "1.0",
            "processing_info": {
                "asr_model": os.getenv("ASR_MODEL", "medium"),
                "text_model": "siglip",
                "vision_model": "siglip",
                "model_service": "centralized"
            }
        }
    }

    return sidecar


def upload_sidecar(minio_client, sidecar: Dict, sidecar_key: str):
    """
    Upload sidecar JSON to storage.

    Args:
        minio_client: MinIO client instance
        sidecar: Sidecar dictionary
        sidecar_key: Storage key for sidecar
    """
    from io import BytesIO

    # Convert to JSON bytes
    sidecar_json = json.dumps(sidecar, indent=2, ensure_ascii=False)
    sidecar_bytes = sidecar_json.encode('utf-8')

    # Upload to storage
    bucket = os.getenv("STORAGE_BUCKET_SIDECARS", "sidecars")

    # Ensure bucket exists
    if not minio_client.bucket_exists(bucket):
        minio_client.make_bucket(bucket)
        print(f"[worker] Created bucket: {bucket}")

    minio_client.put_object(
        bucket_name=bucket,
        object_name=sidecar_key,
        data=BytesIO(sidecar_bytes),
        length=len(sidecar_bytes),
        content_type="application/json"
    )

    print(f"[worker] Uploaded sidecar: {sidecar_key} ({len(sidecar_bytes)} bytes)")

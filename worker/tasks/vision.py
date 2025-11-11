"""
Vision embedding tasks using SigLIP.

Generates visual embeddings for semantic scene search using google/siglip-so400m-patch14-384.
"""
import dramatiq
from tasks import redis_broker

dramatiq.set_broker(redis_broker)


@dramatiq.actor(queue_name="vision", max_retries=3)
def generate_scene_embeddings(video_id: int, scene_timestamps: list):
    """
    Generate vision embeddings for detected scenes.

    Args:
        video_id: ID of the video
        scene_timestamps: List of scene start times in seconds

    This task:
    1. Extracts keyframes at scene timestamps
    2. Generates embeddings using SigLIP (google/siglip-so400m-patch14-384)
    3. Stores embeddings in pgvector for similarity search
    """
    # TODO: Implement vision embedding generation
    print(f"[vision] Generating embeddings for video_id={video_id}, {len(scene_timestamps)} scenes")
    pass


@dramatiq.actor(queue_name="vision", max_retries=2)
def extract_keyframe(video_path: str, timestamp: float, output_path: str):
    """
    Extract a single keyframe from video at given timestamp.

    Args:
        video_path: Path to video file
        timestamp: Time in seconds
        output_path: Path to save keyframe image

    Returns:
        Path to extracted keyframe
    """
    # TODO: Implement keyframe extraction using ffmpeg
    print(f"[vision] Extracting keyframe at {timestamp}s from {video_path}")
    pass

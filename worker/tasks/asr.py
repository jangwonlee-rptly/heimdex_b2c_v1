"""
Automatic Speech Recognition (ASR) tasks using Whisper.

Handles audio transcription for video indexing.
"""
import dramatiq
from tasks import redis_broker

dramatiq.set_broker(redis_broker)


@dramatiq.actor(queue_name="asr", max_retries=3)
def transcribe_video(video_id: int, video_path: str):
    """
    Transcribe audio from video using Whisper.

    Args:
        video_id: ID of the video
        video_path: Local path to video file

    This task:
    1. Extracts audio from video
    2. Runs Whisper ASR
    3. Stores transcript with timestamps
    4. Generates text embeddings for search
    """
    # TODO: Implement Whisper transcription
    print(f"[asr] Transcribing video_id={video_id}")
    pass


@dramatiq.actor(queue_name="asr", max_retries=2)
def extract_audio(video_path: str, output_path: str):
    """
    Extract audio track from video file.

    Args:
        video_path: Path to input video
        output_path: Path for output audio file

    Returns:
        Path to extracted audio file
    """
    # TODO: Implement audio extraction using ffmpeg
    print(f"[asr] Extracting audio from {video_path}")
    pass

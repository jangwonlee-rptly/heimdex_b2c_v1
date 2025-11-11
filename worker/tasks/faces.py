"""
Face detection and recognition tasks.

Uses OpenCV YuNet (opencv/face_detection_yunet) for face detection.
"""
import dramatiq
from tasks import redis_broker

dramatiq.set_broker(redis_broker)


@dramatiq.actor(queue_name="faces", max_retries=3)
def detect_faces_in_scenes(video_id: int, scene_ids: list):
    """
    Detect faces in video scenes.

    Args:
        video_id: ID of the video
        scene_ids: List of scene IDs to process

    This task:
    1. Loads scene keyframes
    2. Runs face detection
    3. Generates face embeddings
    4. Matches against enrolled people
    5. Stores face detections and matches
    """
    # TODO: Implement face detection
    print(f"[faces] Detecting faces in video_id={video_id}, {len(scene_ids)} scenes")
    pass


@dramatiq.actor(queue_name="faces", max_retries=2)
def enroll_person_face(person_id: int, photo_paths: list):
    """
    Enroll a person's face from reference photos.

    Args:
        person_id: ID of the person
        photo_paths: List of paths to enrollment photos

    This task:
    1. Detects faces in photos
    2. Generates face embeddings
    3. Averages embeddings for robust representation
    4. Stores in database for matching
    """
    # TODO: Implement face enrollment
    print(f"[faces] Enrolling person_id={person_id} with {len(photo_paths)} photos")
    pass

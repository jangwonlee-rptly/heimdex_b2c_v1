#!/usr/bin/env python3
"""
Manually trigger processing for stuck video after fixing the import issue.
Usage: docker compose exec api python trigger_stuck_video.py
"""

import dramatiq
from dramatiq.brokers.redis import RedisBroker
import os

# Video ID that's stuck
VIDEO_ID = "06776a0e-e5a7-4a70-aa28-82d954042f63"

# Configure Redis broker
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_broker = RedisBroker(url=redis_url)
dramatiq.set_broker(redis_broker)

# Create stub actor
@dramatiq.actor(
    actor_name="process_video",
    queue_name="video_processing",
    broker=redis_broker
)
def process_video_stub(video_id_str: str):
    """Stub - actual implementation is in worker container."""
    pass

# Send the task
print(f"Sending video {VIDEO_ID} to processing queue...")
process_video_stub.send(VIDEO_ID)
print("Task sent successfully!")

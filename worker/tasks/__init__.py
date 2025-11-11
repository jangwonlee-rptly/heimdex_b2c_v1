"""
Dramatiq task modules for background processing.
"""
import os
import dramatiq
from dramatiq.brokers.redis import RedisBroker

# Configure Redis broker
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_broker = RedisBroker(url=redis_url)
dramatiq.set_broker(redis_broker)

__all__ = ["redis_broker"]

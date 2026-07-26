import json
import logging
from typing import Optional, Any
import redis
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Redis client. Decode responses to get python strings instead of bytes.
try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
except Exception as e:
    logger.error(f"Failed to initialize Redis client: {e}")
    redis_client = None

def get_cache(key: str) -> Optional[str]:
    """Retrieves a value from Redis with graceful failure."""
    if not redis_client:
        return None
    try:
        return redis_client.get(key)
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        logger.warning(f"Redis get connection error for key {key}: {e}")
        return None

def set_cache(key: str, value: str, ttl: int = 300) -> bool:
    """Sets a value in Redis with a TTL (default 5 minutes) and graceful failure."""
    if not redis_client:
        return False
    try:
        return redis_client.set(key, value, ex=ttl)
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        logger.warning(f"Redis set connection error for key {key}: {e}")
        return False

def delete_cache(key: str) -> bool:
    """Deletes a key from Redis with graceful failure."""
    if not redis_client:
        return False
    try:
        return redis_client.delete(key) > 0
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        logger.warning(f"Redis delete connection error for key {key}: {e}")
        return False

# Domain-specific helpers for Session caching
def get_cached_session(session_id: int) -> Optional[dict]:
    data = get_cache(f"session:{session_id}")
    if data:
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None
    return None

def set_cached_session(session_id: int, session_data: dict) -> None:
    try:
        set_cache(f"session:{session_id}", json.dumps(session_data), ttl=300)
    except Exception as e:
        logger.warning(f"Failed to serialize session {session_id} for cache: {e}")

def invalidate_cached_session(session_id: int) -> None:
    delete_cache(f"session:{session_id}")

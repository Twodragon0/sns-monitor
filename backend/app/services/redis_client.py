"""
Redis client with graceful fallback.
Works without Redis - returns None if unavailable.
"""

import logging

logger = logging.getLogger(__name__)

_redis_client = None
_redis_checked = False


def get_redis():
    """Get Redis client, returns None if unavailable."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client

    _redis_checked = True
    try:
        import redis
        from ..config import Config
        _redis_client = redis.Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=2
        )
        _redis_client.ping()
        logger.info("Redis connected: %s:%s", Config.REDIS_HOST, Config.REDIS_PORT)
    except Exception:
        logger.warning("Redis not available, running without cache")
        _redis_client = None

    return _redis_client

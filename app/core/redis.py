import logging
from typing import Optional
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger("redis_client")

redis_client: Optional[aioredis.Redis] = None

if settings.ENVIRONMENT != "test" and settings.REDIS_URL:
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=2.0,
        )
    except Exception as e:
        logger.warning("Failed to initialize Redis client: %s", e)
        redis_client = None

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Determine storage uri: in test environment use in-memory storage, in production use Redis
storage_uri = "memory://" if settings.ENVIRONMENT == "test" else settings.REDIS_URL

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=storage_uri,
    strategy="moving-window",
)

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context: Argon2 as primary scheme (OWASP recommended), bcrypt as secondary
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a secure cryptographic hash for the given password."""
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, Any],
    role: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT access token with role and jti nonce for replay defense."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),  # Replay attack prevention nonce
        "type": "access",
    }
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token() -> str:
    """Generate a high-entropy cryptographically secure refresh token string."""
    return f"{uuid.uuid4().hex}{uuid.uuid4().hex}"


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token payload. Raises JWTError if invalid."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# In-memory revocation cache for instant lookups & test runs
_revoked_jtis: set = set()


def revoke_access_token(jti: str, ttl_seconds: int = 900) -> None:
    """Blacklist an access token's jti nonce so it cannot be reused (replay defense)."""
    _revoked_jtis.add(jti)
    try:
        if settings.REDIS_URL and settings.ENVIRONMENT != "test":
            import redis
            r = redis.from_url(settings.REDIS_URL)
            r.setex(f"revoked_jti:{jti}", max(1, ttl_seconds), "1")
    except Exception:
        pass


def is_token_revoked(jti: str) -> bool:
    """Verify if an access token's jti nonce has been explicitly revoked."""
    if jti in _revoked_jtis:
        return True
    try:
        if settings.REDIS_URL and settings.ENVIRONMENT != "test":
            import redis
            r = redis.from_url(settings.REDIS_URL)
            if r.exists(f"revoked_jti:{jti}"):
                return True
    except Exception:
        pass
    return False

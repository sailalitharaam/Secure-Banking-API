import uuid
from typing import List, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token, is_token_revoked
from app.db.session import get_db
from app.models.user import User, UserRole

# HTTP Bearer scheme
security_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that extracts and validates the JWT Bearer token and returns the User."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials
    try:
        payload = decode_token(token)
        user_id_str: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")
        if user_id_str is None or token_type != "access":
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)

        # Replay attack and token revocation check
        jti = payload.get("jti")
        if jti and is_token_revoked(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except (JWTError, ValueError):
        raise credentials_exception

    stmt = select(User).where(User.UserID == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    return user


def require_roles(allowed_roles: List[UserRole]):
    """RBAC dependency factory that validates if the authenticated user has one of the required roles."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.Role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker


# Convenient RBAC dependencies
require_bank_admin = require_roles([UserRole.BANK_ADMIN])
require_customer = require_roles([UserRole.CUSTOMER, UserRole.BANK_ADMIN])
require_merchant = require_roles([UserRole.MERCHANT, UserRole.BANK_ADMIN])


def get_client_ip(request: Request) -> str:
    """Extract client real IP handling reverse proxy headers."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


def get_device_fingerprint_from_request(request: Request) -> str:
    """Extract or hash client fingerprint from request headers."""
    fingerprint = request.headers.get("X-Device-Fingerprint")
    if fingerprint:
        return fingerprint
    user_agent = request.headers.get("User-Agent", "default-device-fingerprint")
    accept_lang = request.headers.get("Accept-Language", "en-US")
    import hashlib
    return hashlib.sha256(f"{user_agent}|{accept_lang}".encode("utf-8")).hexdigest()[:32]


def get_client_location(request: Request, ip: str) -> str:
    """Extract or simulate client geographic location from headers or IP address."""
    header_loc = request.headers.get("X-Location")
    if header_loc:
        return header_loc
    if ip.startswith("198.51.100."):
        return "New York, NY, US"
    elif ip.startswith("203.0.113."):
        return "London, England, UK"
    elif ip.startswith("192.168.") or ip in ("127.0.0.1", "localhost", "testclient"):
        return "San Francisco, CA, US"
    return "Simulated Location (GeoIP)"

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.auth_token import AuthToken
from app.models.session import Session
from app.models.user import User, UserRole
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.schemas.user import UserResponse
from app.services.device_service import DeviceService


class AuthService:
    @staticmethod
    async def register_user(db: AsyncSession, payload: UserRegisterRequest) -> UserResponse:
        """Register a new user with secure password hashing."""
        # Check if email is already taken
        stmt = select(User).where(User.Email == payload.Email)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )

        hashed_password = get_password_hash(payload.Password)
        new_user = User(
            Email=payload.Email,
            PasswordHash=hashed_password,
            Role=payload.Role,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return UserResponse.model_validate(new_user)

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        payload: UserLoginRequest,
        client_ip: str,
        client_fingerprint: str,
        location: str = "Unknown",
    ) -> TokenResponse:
        """Verify user credentials, log session/device metadata, and generate token pair."""
        stmt = select(User).where(User.Email == payload.Email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(payload.Password, user.PasswordHash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Record Device and Session metadata
        device_fp = payload.DeviceFingerprint or client_fingerprint
        device_t = payload.DeviceType or "Web Browser"
        await DeviceService.record_device_and_session(
            db=db,
            user_id=user.UserID,
            device_fingerprint=device_fp,
            device_type=device_t,
            ip_address=client_ip,
            location=location,
        )

        # Generate tokens
        access_token = create_access_token(
            subject=user.UserID,
            role=user.Role.value,
        )
        refresh_token_str = create_refresh_token()
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # Store Refresh Token in DB
        auth_token_entry = AuthToken(
            UserID=user.UserID,
            RefreshToken=refresh_token_str,
            IsRevoked=False,
            ExpiresAt=refresh_expires,
        )
        db.add(auth_token_entry)
        await db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
        """Issue a new access token using a valid, non-revoked refresh token."""
        stmt = (
            select(AuthToken, User)
            .join(User, AuthToken.UserID == User.UserID)
            .where(AuthToken.RefreshToken == refresh_token)
        )
        result = await db.execute(stmt)
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        token_record, user = row[0], row[1]
        now = datetime.now(timezone.utc)
        expires_at = (
            token_record.ExpiresAt.replace(tzinfo=timezone.utc)
            if token_record.ExpiresAt.tzinfo is None
            else token_record.ExpiresAt
        )

        if token_record.IsRevoked or expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked or has expired.",
            )

        # Generate fresh Access Token
        new_access_token = create_access_token(
            subject=user.UserID,
            role=user.Role.value,
        )

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    async def logout_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        refresh_token: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> None:
        """Revoke refresh token, blacklist access token jti, and invalidate active sessions."""
        # 1. Blacklist access token jti nonce immediately
        if access_token:
            try:
                from app.core.security import decode_token, revoke_access_token
                payload = decode_token(access_token)
                jti = payload.get("jti")
                exp = payload.get("exp")
                if jti:
                    now_ts = datetime.now(timezone.utc).timestamp()
                    ttl = int(exp - now_ts) if exp else 900
                    revoke_access_token(jti, ttl_seconds=max(1, ttl))
            except Exception:
                pass

        # 2. Revoke refresh token in database
        if refresh_token:
            stmt = (
                update(AuthToken)
                .where(AuthToken.RefreshToken == refresh_token, AuthToken.UserID == user_id)
                .values(IsRevoked=True)
            )
            await db.execute(stmt)

        # 3. Deactivate all active sessions for this user
        session_stmt = (
            update(Session)
            .where(Session.UserID == user_id, Session.IsActive == True)
            .values(IsActive=False)
        )
        await db.execute(session_stmt)
        await db.commit()

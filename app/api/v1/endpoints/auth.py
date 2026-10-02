from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import (
    get_client_ip,
    get_client_location,
    get_current_user,
    get_device_fingerprint_from_request,
    require_bank_admin,
    require_customer,
    require_merchant,
    security_scheme,
)
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User Registration",
    description="Register a new customer, merchant, or admin user with bcrypt/Argon2 password hashing.",
)
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await AuthService.register_user(db=db, payload=payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticate user credentials, log session/device metadata, and generate JWT Access + Refresh tokens.",
)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    client_ip = get_client_ip(request)
    client_fp = get_device_fingerprint_from_request(request)
    client_loc = get_client_location(request, client_ip)
    return await AuthService.authenticate_user(
        db=db,
        payload=payload,
        client_ip=client_ip,
        client_fingerprint=client_fp,
        location=client_loc,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Access Token",
    description="Generate a fresh JWT Access Token using a valid, non-revoked Refresh Token.",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await AuthService.refresh_access_token(db=db, refresh_token=payload.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Invalidate active user session, blacklist access token jti, and revoke refresh tokens.",
)
async def logout(
    payload: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    access_token = credentials.credentials if credentials else None
    await AuthService.logout_user(
        db=db,
        user_id=current_user.UserID,
        refresh_token=payload.refresh_token,
        access_token=access_token,
    )
    return {"message": "Successfully logged out. Session and tokens invalidated."}


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Authenticated User Profile",
    description="Returns current authenticated user details from the validated JWT token.",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get(
    "/customer-route",
    status_code=status.HTTP_200_OK,
    summary="Customer RBAC Protected Route",
    description="Accessible by users holding Customer or Bank Admin role.",
)
async def customer_protected_route(
    current_user: User = Depends(require_customer),
) -> dict:
    return {
        "message": "Access granted to Customer endpoint",
        "user_id": str(current_user.UserID),
        "role": current_user.Role.value,
    }


@router.get(
    "/merchant-route",
    status_code=status.HTTP_200_OK,
    summary="Merchant RBAC Protected Route",
    description="Accessible by users holding Merchant or Bank Admin role.",
)
async def merchant_protected_route(
    current_user: User = Depends(require_merchant),
) -> dict:
    return {
        "message": "Access granted to Merchant endpoint",
        "user_id": str(current_user.UserID),
        "role": current_user.Role.value,
    }


@router.get(
    "/admin-route",
    status_code=status.HTTP_200_OK,
    summary="Bank Admin RBAC Protected Route",
    description="Strictly accessible ONLY by users holding Bank Admin role.",
)
async def admin_protected_route(
    current_user: User = Depends(require_bank_admin),
) -> dict:
    return {
        "message": "Access granted to Bank Admin endpoint",
        "user_id": str(current_user.UserID),
        "role": current_user.Role.value,
    }


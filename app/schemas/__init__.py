"""Pydantic v2 schemas package for requests and responses."""

from app.schemas.user import UserBase, UserCreate, UserResponse, UserRole
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    LogoutRequest,
)
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    PaginatedAccountHistory,
)
from app.schemas.device import DeviceCreate, DeviceResponse
from app.schemas.session import SessionCreate, SessionResponse
from app.schemas.transaction import (
    TransferRequest,
    TransactionResponse,
    RiskScoreResponse,
)
from app.schemas.fraud_alert import (
    FraudAlertResponse,
    AlertListResponse,
    DashboardMetricsResponse,
)

__all__ = [
    "UserBase",
    "UserCreate",
    "UserResponse",
    "UserRole",
    "UserRegisterRequest",
    "UserLoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "LogoutRequest",
    "AccountCreate",
    "AccountResponse",
    "PaginatedAccountHistory",
    "DeviceCreate",
    "DeviceResponse",
    "SessionCreate",
    "SessionResponse",
    "TransferRequest",
    "TransactionResponse",
    "RiskScoreResponse",
    "FraudAlertResponse",
    "AlertListResponse",
    "DashboardMetricsResponse",
]

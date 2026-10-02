import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole


class UserRegisterRequest(BaseModel):
    Email: EmailStr
    Password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    Role: UserRole = Field(default=UserRole.CUSTOMER, description="Role: Customer, Merchant, Bank Admin")


class UserLoginRequest(BaseModel):
    Email: EmailStr
    Password: str
    DeviceFingerprint: Optional[str] = Field(None, description="Client hardware/browser canvas hash")
    DeviceType: Optional[str] = Field("Web Browser", description="Client device category")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None

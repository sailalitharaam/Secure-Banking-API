import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.user import UserRole


class UserBase(BaseModel):
    Email: EmailStr
    Role: UserRole = UserRole.CUSTOMER


class UserCreate(UserBase):
    Password: str


class UserResponse(UserBase):
    UserID: uuid.UUID
    CreatedAt: datetime

    model_config = ConfigDict(from_attributes=True)

import enum
import uuid
from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.device import Device
    from app.models.session import Session
    from app.models.auth_token import AuthToken


class UserRole(str, enum.Enum):
    CUSTOMER = "Customer"
    MERCHANT = "Merchant"
    BANK_ADMIN = "Bank Admin"


class User(Base):
    __tablename__ = "users"

    UserID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    Email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    PasswordHash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    Role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", create_type=True),
        nullable=False,
        default=UserRole.CUSTOMER,
    )
    CreatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    accounts: Mapped[List["Account"]] = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    devices: Mapped[List["Device"]] = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    auth_tokens: Mapped[List["AuthToken"]] = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(UserID={self.UserID}, Email='{self.Email}', Role='{self.Role}')>"

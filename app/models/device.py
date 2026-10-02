import uuid
from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.session import Session


class Device(Base):
    __tablename__ = "devices"

    DeviceID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    UserID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.UserID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    DeviceFingerprint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    DeviceType: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Unknown",
    )
    LastUsedIP: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="127.0.0.1",
    )
    UpdatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="devices")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="device", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Device(DeviceID={self.DeviceID}, UserID={self.UserID}, Fingerprint='{self.DeviceFingerprint}')>"

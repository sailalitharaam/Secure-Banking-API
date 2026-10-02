import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.device import Device


class Session(Base):
    __tablename__ = "sessions"

    SessionID: Mapped[uuid.UUID] = mapped_column(
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
    DeviceID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.DeviceID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    LoginTime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    IPAddress: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    Location: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Unknown",
    )
    IsActive: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    device: Mapped["Device"] = relationship("Device", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session(SessionID={self.SessionID}, UserID={self.UserID}, IsActive={self.IsActive})>"

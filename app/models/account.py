import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime, Enum, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.transaction import Transaction


class AccountType(str, enum.Enum):
    CHECKING = "Checking"
    SAVINGS = "Savings"
    BUSINESS = "Business"


class KYCStatus(str, enum.Enum):
    PENDING = "Pending"
    VERIFIED = "Verified"
    REJECTED = "Rejected"


class Account(Base):
    __tablename__ = "accounts"

    AccountID: Mapped[uuid.UUID] = mapped_column(
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
    AccountType: Mapped[AccountType] = mapped_column(
        Enum(AccountType, name="account_type_enum", create_type=True),
        nullable=False,
        default=AccountType.CHECKING,
    )
    Balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
        default=Decimal("0.00"),
    )
    KYCStatus: Mapped[KYCStatus] = mapped_column(
        Enum(KYCStatus, name="kyc_status_enum", create_type=True),
        nullable=False,
        default=KYCStatus.PENDING,
    )
    CreatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="accounts")
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        back_populates="account",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Account(AccountID={self.AccountID}, UserID={self.UserID}, Balance={self.Balance})>"

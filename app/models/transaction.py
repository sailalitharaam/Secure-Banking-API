import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Enum, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.fraud_alert import FraudAlert


class TransactionType(str, enum.Enum):
    TRANSFER = "Transfer"
    DEPOSIT = "Deposit"
    WITHDRAWAL = "Withdrawal"
    PAYMENT = "Payment"


class TransactionStatus(str, enum.Enum):
    APPROVED = "Approved"
    PENDING = "Pending"
    BLOCKED = "Blocked"


class Transaction(Base):
    __tablename__ = "transactions"

    TransactionID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    AccountID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.AccountID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    Amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    TransactionType: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type_enum", create_type=True),
        nullable=False,
        default=TransactionType.TRANSFER,
    )
    SenderAccount: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    ReceiverAccount: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    Status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status_enum", create_type=True),
        nullable=False,
        default=TransactionStatus.PENDING,
        index=True,
    )
    Timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="transactions")
    fraud_alert: Mapped[Optional["FraudAlert"]] = relationship(
        "FraudAlert",
        back_populates="transaction",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(TransactionID={self.TransactionID}, "
            f"AccountID={self.AccountID}, Amount={self.Amount}, Status='{self.Status}')>"
        )

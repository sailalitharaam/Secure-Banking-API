import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING
from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.transaction import Transaction


class AlertLevel(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class AlertDecision(str, enum.Enum):
    APPROVED = "Approved"
    STEP_UP_REQUIRED = "Step-Up Required"
    BLOCKED = "Blocked"


class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    AlertID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    TransactionID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.TransactionID", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    RiskScore: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
    )
    AlertLevel: Mapped[AlertLevel] = mapped_column(
        Enum(AlertLevel, name="alert_level_enum", create_type=True),
        nullable=False,
        default=AlertLevel.LOW,
        index=True,
    )
    Decision: Mapped[AlertDecision] = mapped_column(
        Enum(AlertDecision, name="alert_decision_enum", create_type=True),
        nullable=False,
        default=AlertDecision.APPROVED,
        index=True,
    )
    Explanations: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    CreatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="fraud_alert")

    def __repr__(self) -> str:
        return (
            f"<FraudAlert(AlertID={self.AlertID}, TransactionID={self.TransactionID}, "
            f"RiskScore={self.RiskScore}, AlertLevel='{self.AlertLevel}', Decision='{self.Decision}')>"
        )

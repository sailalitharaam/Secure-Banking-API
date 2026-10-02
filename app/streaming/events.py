import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class TransactionCreatedEvent(BaseModel):
    """Event published when a transfer or transaction is initiated."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "TRANSACTION_CREATED"
    transaction_id: str
    account_id: str
    user_id: str
    amount: float
    sender_account: str
    receiver_account: str
    device_fingerprint: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FraudAlertEvent(BaseModel):
    """Event emitted when ML pipeline completes risk scoring."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "FRAUD_ALERT_GENERATED"
    alert_id: str
    transaction_id: str
    risk_score: float
    alert_level: str
    decision: str
    explanations: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

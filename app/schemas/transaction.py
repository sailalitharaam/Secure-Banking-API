import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.transaction import TransactionType as TransactionTypeEnum, TransactionStatus as TransactionStatusEnum
from app.models.fraud_alert import AlertLevel as AlertLevelEnum, AlertDecision


class TransferRequest(BaseModel):
    SenderAccountID: uuid.UUID = Field(..., description="Source account ID for the transfer")
    ReceiverAccountID: uuid.UUID = Field(..., description="Destination account ID for the transfer")
    Amount: Decimal = Field(..., gt=Decimal("0.00"), description="Transfer amount must be greater than 0")
    Description: Optional[str] = Field(None, max_length=255)


class TransactionResponse(BaseModel):
    TransactionID: uuid.UUID
    AccountID: uuid.UUID
    Amount: Decimal
    TransactionType: TransactionTypeEnum
    SenderAccount: str
    ReceiverAccount: str
    Status: TransactionStatusEnum
    Timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskScoreResponse(BaseModel):
    TransactionID: uuid.UUID
    RiskScore: float = Field(..., ge=0.0, le=100.0, description="Risk score bounded between 0 and 100")
    AlertLevel: AlertLevelEnum
    Decision: AlertDecision
    Explanations: Optional[Dict[str, Any]] = None
    Timestamp: datetime


class VerifyOTPRequest(BaseModel):
    otp_code: str = Field(..., min_length=4, max_length=8, description="6-digit verification passcode")

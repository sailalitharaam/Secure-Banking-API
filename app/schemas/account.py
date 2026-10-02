import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.account import AccountType as AccountTypeEnum, KYCStatus as KYCStatusEnum
from app.schemas.transaction import TransactionResponse


class AccountCreate(BaseModel):
    AccountType: AccountTypeEnum = Field(default=AccountTypeEnum.CHECKING, description="Checking, Savings, Business")
    InitialDeposit: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), description="Initial funding amount")
    KYCStatus: Optional[KYCStatusEnum] = Field(default=KYCStatusEnum.VERIFIED, description="KYC status: Pending, Verified, Rejected")


class AccountResponse(BaseModel):
    AccountID: uuid.UUID
    UserID: uuid.UUID
    AccountType: AccountTypeEnum
    Balance: Decimal
    KYCStatus: KYCStatusEnum
    CreatedAt: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAccountHistory(BaseModel):
    account_id: uuid.UUID
    balance: Decimal
    total_transactions: int
    page: int
    page_size: int
    transactions: List[TransactionResponse]

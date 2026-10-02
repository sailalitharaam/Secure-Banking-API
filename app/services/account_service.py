import uuid
from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, KYCStatus
from app.models.transaction import Transaction
from app.models.user import User, UserRole
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    PaginatedAccountHistory,
)
from app.schemas.transaction import TransactionResponse


class AccountService:
    @staticmethod
    async def create_account(
        db: AsyncSession,
        user_id: uuid.UUID,
        payload: AccountCreate,
    ) -> AccountResponse:
        """Create a new account for the specified user."""
        account = Account(
            UserID=user_id,
            AccountType=payload.AccountType,
            Balance=payload.InitialDeposit,
            KYCStatus=payload.KYCStatus or KYCStatus.VERIFIED,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return AccountResponse.model_validate(account)

    @staticmethod
    async def get_accounts(
        db: AsyncSession,
        current_user: User,
    ) -> List[AccountResponse]:
        """Fetch all accounts belonging to the current user (or all accounts if Bank Admin)."""
        stmt = select(Account)
        if current_user.Role != UserRole.BANK_ADMIN:
            stmt = stmt.where(Account.UserID == current_user.UserID)

        result = await db.execute(stmt)
        accounts = result.scalars().all()
        return [AccountResponse.model_validate(acc) for acc in accounts]

    @staticmethod
    async def get_account_by_id(
        db: AsyncSession,
        account_id: uuid.UUID,
        current_user: User,
    ) -> Account:
        """Fetch an account by ID, verifying user ownership unless Bank Admin."""
        stmt = select(Account).where(Account.AccountID == account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found.",
            )

        if current_user.Role != UserRole.BANK_ADMIN and account.UserID != current_user.UserID:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not own this account.",
            )

        return account

    @staticmethod
    async def get_account_history(
        db: AsyncSession,
        account_id: uuid.UUID,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedAccountHistory:
        """Fetch paginated transaction history for an account."""
        account = await AccountService.get_account_by_id(db, account_id, current_user)

        # Count total transactions for this account
        account_id_str = str(account_id)
        count_stmt = (
            select(func.count())
            .select_from(Transaction)
            .where(
                (Transaction.AccountID == account_id)
                | (Transaction.SenderAccount == account_id_str)
                | (Transaction.ReceiverAccount == account_id_str)
            )
        )
        total_count = (await db.execute(count_stmt)).scalar() or 0

        # Query paginated transactions
        stmt = (
            select(Transaction)
            .where(
                (Transaction.AccountID == account_id)
                | (Transaction.SenderAccount == account_id_str)
                | (Transaction.ReceiverAccount == account_id_str)
            )
            .order_by(Transaction.Timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        transactions = result.scalars().all()

        return PaginatedAccountHistory(
            account_id=account.AccountID,
            balance=account.Balance,
            total_transactions=total_count,
            page=page,
            page_size=page_size,
            transactions=[TransactionResponse.model_validate(tx) for tx in transactions],
        )

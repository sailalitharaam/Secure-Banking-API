import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    PaginatedAccountHistory,
)
from app.services.account_service import AccountService

router = APIRouter()


@router.get(
    "",
    response_model=List[AccountResponse],
    status_code=status.HTTP_200_OK,
    summary="List User Accounts",
    description="Retrieve all bank accounts associated with the authenticated user (or all accounts if Admin).",
)
async def list_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AccountResponse]:
    return await AccountService.get_accounts(db=db, current_user=current_user)


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open Bank Account",
    description="Create a new bank account (Checking, Savings, Business) with an optional initial balance.",
)
async def create_account(
    payload: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    return await AccountService.create_account(db=db, user_id=current_user.UserID, payload=payload)


@router.get(
    "/{id}",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Account by ID",
    description="Retrieve account details and current balance. Enforces strict ownership check (accessible only by account owner or Bank Admin).",
)
async def get_account_by_id(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    account = await AccountService.get_account_by_id(db=db, account_id=id, current_user=current_user)
    return AccountResponse.model_validate(account)


@router.get(
    "/{id}/history",
    response_model=PaginatedAccountHistory,
    status_code=status.HTTP_200_OK,
    summary="Get Account Transaction History",
    description="Retrieve paginated transaction records and current balance for a specified account.",
)
async def get_account_history(
    id: uuid.UUID,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedAccountHistory:
    return await AccountService.get_account_history(
        db=db,
        account_id=id,
        current_user=current_user,
        page=page,
        page_size=page_size,
    )

import uuid
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_client_ip,
    get_current_user,
    get_device_fingerprint_from_request,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.transaction import (
    RiskScoreResponse,
    TransactionResponse,
    TransferRequest,
    VerifyOTPRequest,
)
from app.services.alert_service import AlertService
from app.services.mitigation_service import MitigationService
from app.services.transaction_service import TransactionService

router = APIRouter()


@router.post(
    "/transfer",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Atomic Fund Transfer",
    description="Transfer funds between two accounts using pessimistic database row locking to prevent race conditions.",
)
async def transfer_funds(
    request: Request,
    payload: TransferRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    client_ip = get_client_ip(request)
    client_fp = get_device_fingerprint_from_request(request)
    return await TransactionService.transfer_funds(
        db=db,
        current_user=current_user,
        payload=payload,
        client_ip=client_ip,
        device_fingerprint=client_fp,
    )


@router.get(
    "/{id}/risk-score",
    response_model=RiskScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Transaction Risk Score",
    description="Fetch real-time fraud risk score (0-100), alert level, and SHAP decision explanations for a transaction.",
)
async def get_transaction_risk_score(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RiskScoreResponse:
    return await AlertService.get_risk_score(db=db, transaction_id=id, current_user=current_user)


@router.post(
    "/{id}/verify-otp",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Step-Up Authentication OTP",
    description="Verify one-time passcode for transactions flagged for step-up authentication to release transfer.",
)
async def verify_step_up_otp(
    id: uuid.UUID,
    payload: VerifyOTPRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    tx = await MitigationService.verify_step_up_otp(
        db=db,
        transaction_id=id,
        otp_code=payload.otp_code,
        current_user=current_user,
    )
    return TransactionResponse.model_validate(tx)


from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_bank_admin
from app.db.session import get_db
from app.models.fraud_alert import AlertLevel, FraudAlert
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.fraud_alert import DashboardMetricsResponse, FraudAlertResponse
from app.schemas.transaction import TransactionResponse
from app.services.alert_service import AlertService
from app.services.mitigation_service import MitigationService

router = APIRouter()


@router.get(
    "/dashboard/transactions",
    response_model=List[TransactionResponse],
    status_code=status.HTTP_200_OK,
    summary="Admin Transaction Feed",
    description="Real-time transaction monitoring feed for bank compliance and fraud analysts.",
)
async def get_dashboard_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    admin_user: User = Depends(require_bank_admin),
    db: AsyncSession = Depends(get_db),
) -> List[TransactionResponse]:
    stmt = select(Transaction).order_by(Transaction.Timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    transactions = result.scalars().all()
    return [TransactionResponse.model_validate(tx) for tx in transactions]


@router.get(
    "/dashboard/alerts",
    response_model=List[FraudAlertResponse],
    status_code=status.HTTP_200_OK,
    summary="Admin Active High-Risk Alert Queue",
    description="Active high and medium risk alert queue with SHAP explanation breakdowns.",
)
async def get_dashboard_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    admin_user: User = Depends(require_bank_admin),
    db: AsyncSession = Depends(get_db),
) -> List[FraudAlertResponse]:
    stmt = (
        select(FraudAlert)
        .where(FraudAlert.AlertLevel.in_([AlertLevel.HIGH, AlertLevel.MEDIUM]))
        .order_by(FraudAlert.CreatedAt.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    return [FraudAlertResponse.model_validate(a) for a in alerts]


@router.get(
    "/dashboard/metrics",
    response_model=DashboardMetricsResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin ML Performance Metrics",
    description="Live model performance stats (Precision, Recall, F1, False Positive Rate) and operational throughput.",
)
async def get_dashboard_metrics(
    admin_user: User = Depends(require_bank_admin),
    db: AsyncSession = Depends(get_db),
) -> DashboardMetricsResponse:
    return await AlertService.get_dashboard_metrics(db=db)


@router.get(
    "/dashboard/audit-trail",
    response_model=List[dict],
    status_code=status.HTTP_200_OK,
    summary="Admin Mitigation Audit Trail",
    description="Inspection trail of automated mitigation actions (high risk blocks, step-up challenges, refunds).",
)
async def get_dashboard_audit_trail(
    admin_user: User = Depends(require_bank_admin),
) -> List[dict]:
    return MitigationService.get_audit_trail()


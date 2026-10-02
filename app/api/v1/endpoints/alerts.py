from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_bank_admin
from app.db.session import get_db
from app.models.fraud_alert import AlertLevel
from app.models.user import User
from app.schemas.fraud_alert import AlertListResponse
from app.services.alert_service import AlertService

router = APIRouter()


@router.get(
    "",
    response_model=AlertListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Fraud Alerts (Admin Only)",
    description="Retrieve paginated queue of high and medium risk transactions flagged by the ML pipeline.",
)
async def list_fraud_alerts(
    level: Optional[AlertLevel] = Query(None, description="Filter by risk alert level (Low, Medium, High)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    admin_user: User = Depends(require_bank_admin),
    db: AsyncSession = Depends(get_db),
) -> AlertListResponse:
    return await AlertService.get_alerts(
        db=db,
        level=level,
        page=page,
        page_size=page_size,
    )

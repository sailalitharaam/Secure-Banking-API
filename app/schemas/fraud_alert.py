import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.fraud_alert import AlertLevel as AlertLevelEnum, AlertDecision


class FraudAlertResponse(BaseModel):
    AlertID: uuid.UUID
    TransactionID: uuid.UUID
    RiskScore: float
    AlertLevel: AlertLevelEnum
    Decision: AlertDecision
    Explanations: Optional[Dict[str, Any]] = None
    CreatedAt: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    alerts: List[FraudAlertResponse]


class DashboardMetricsResponse(BaseModel):
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    total_transactions_analyzed: int
    total_alerts_generated: int
    high_risk_blocked_count: int
    step_up_required_count: int

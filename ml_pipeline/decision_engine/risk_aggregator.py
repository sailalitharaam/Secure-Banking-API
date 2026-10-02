from typing import Tuple
from app.models.fraud_alert import AlertDecision, AlertLevel
from ml_pipeline.config import RISK_THRESHOLD_HIGH, RISK_THRESHOLD_LOW


class RiskAggregator:
    """Aggregates supervised and unsupervised model outputs into a unified risk score (0-100) and mitigation action."""

    def __init__(
        self,
        supervised_weight: float = 0.65,
        anomaly_weight: float = 0.35,
        threshold_low: float = RISK_THRESHOLD_LOW,
        threshold_high: float = RISK_THRESHOLD_HIGH,
    ) -> None:
        self.supervised_weight = supervised_weight
        self.anomaly_weight = anomaly_weight
        self.threshold_low = threshold_low
        self.threshold_high = threshold_high

    def aggregate(
        self,
        supervised_prob: float,
        anomaly_score: float,
    ) -> Tuple[float, AlertLevel, AlertDecision]:
        """Calculates 0-100 risk score and derives alert level and decision.

        Returns:
            Tuple of (risk_score, alert_level, decision)
        """
        # Combine probabilities weighted: [0.0 - 1.0] -> [0.0 - 100.0]
        combined = (self.supervised_weight * supervised_prob) + (self.anomaly_weight * anomaly_score)
        risk_score = round(float(combined * 100.0), 2)
        risk_score = max(0.0, min(100.0, risk_score))

        if risk_score < self.threshold_low:
            level = AlertLevel.LOW
            decision = AlertDecision.APPROVED
        elif risk_score <= self.threshold_high:
            level = AlertLevel.MEDIUM
            decision = AlertDecision.STEP_UP_REQUIRED
        else:
            level = AlertLevel.HIGH
            decision = AlertDecision.BLOCKED

        return risk_score, level, decision

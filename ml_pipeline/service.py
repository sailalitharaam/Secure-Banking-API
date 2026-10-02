import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.models.fraud_alert import AlertDecision, AlertLevel
from ml_pipeline.config import ISOLATION_FOREST_PATH, XGBOOST_MODEL_PATH
from ml_pipeline.decision_engine.risk_aggregator import RiskAggregator
from ml_pipeline.explainability.shap_explainer import FraudSHAPExplainer
from ml_pipeline.features.feature_engine import FeatureEngine
from ml_pipeline.models.isolation_forest import IsolationForestModel
from ml_pipeline.models.xgboost_model import XGBoostFraudModel

logger = logging.getLogger(__name__)


class MLRiskScoringService:
    """End-to-end Machine Learning Risk Scoring Service.

    Orchestrates feature extraction, dual-model scoring (XGBoost + Isolation Forest),
    risk aggregation (0-100), automated mitigation decision, and SHAP explainability.
    """

    def __init__(self) -> None:
        self.feature_engine = FeatureEngine()
        self.xgb_model = XGBoostFraudModel(XGBOOST_MODEL_PATH)
        self.iso_model = IsolationForestModel(ISOLATION_FOREST_PATH)
        self.aggregator = RiskAggregator()
        self.explainer = FraudSHAPExplainer(self.xgb_model)

    def score_transaction(
        self,
        amount: float,
        user_history_amounts: Optional[List[float]] = None,
        login_timestamps_24h: Optional[List[Any]] = None,
        last_login_distance_km: Optional[float] = None,
        last_login_elapsed_hours: Optional[float] = None,
        is_known_device: bool = True,
    ) -> Dict[str, Any]:
        """Compute real-time fraud risk score and mitigation decision for a transaction."""
        # 1. Feature extraction
        feature_dict = self.feature_engine.extract_features(
            amount=amount,
            user_history_amounts=user_history_amounts,
            login_timestamps_24h=login_timestamps_24h,
            last_login_distance_km=last_login_distance_km,
            last_login_elapsed_hours=last_login_elapsed_hours,
            is_known_device=is_known_device,
        )
        feature_array = self.feature_engine.to_feature_array(feature_dict)

        # 2. Model inferences
        supervised_prob = float(self.xgb_model.predict_proba(feature_array)[0])
        anomaly_score = float(self.iso_model.score_anomaly(feature_array)[0])

        # 3. Decision aggregation
        risk_score, alert_level, decision = self.aggregator.aggregate(
            supervised_prob=supervised_prob,
            anomaly_score=anomaly_score,
        )

        # 4. Explainability (SHAP attributions)
        shap_explanations = self.explainer.explain(
            feature_array=feature_array,
            feature_dict=feature_dict,
        )

        return {
            "risk_score": risk_score,
            "alert_level": alert_level,
            "decision": decision,
            "supervised_probability": round(supervised_prob, 4),
            "anomaly_score": round(anomaly_score, 4),
            "explanations": shap_explanations,
        }


# Global singleton instance
ml_service = MLRiskScoringService()

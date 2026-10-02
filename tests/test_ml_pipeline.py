import pytest
from app.models.fraud_alert import AlertDecision, AlertLevel
from ml_pipeline.decision_engine.risk_aggregator import RiskAggregator
from ml_pipeline.explainability.shap_explainer import FraudSHAPExplainer
from ml_pipeline.features.feature_engine import FeatureEngine
from ml_pipeline.models.isolation_forest import IsolationForestModel
from ml_pipeline.models.xgboost_model import XGBoostFraudModel


def test_feature_engine_extraction():
    engine = FeatureEngine()
    features = engine.extract_features(
        amount=1500.0,
        user_history_amounts=[100.0, 120.0, 110.0, 95.0, 105.0],
        last_login_distance_km=1200.0,
        last_login_elapsed_hours=1.0,  # 1200 km/h = impossible flight
        is_known_device=False,
    )
    assert features["amount"] == 1500.0
    assert features["amount_z_score"] > 3.0  # Significant deviation
    assert features["geo_velocity"] == 1200.0
    assert features["is_new_device"] == 1.0


def test_risk_aggregator_thresholds():
    aggregator = RiskAggregator(supervised_weight=0.5, anomaly_weight=0.5)

    # Low risk
    score_low, level_low, decision_low = aggregator.aggregate(supervised_prob=0.1, anomaly_score=0.2)
    assert score_low < 30.0
    assert level_low == AlertLevel.LOW
    assert decision_low == AlertDecision.APPROVED

    # Medium risk
    score_med, level_med, decision_med = aggregator.aggregate(supervised_prob=0.5, anomaly_score=0.5)
    assert 30.0 <= score_med <= 70.0
    assert level_med == AlertLevel.MEDIUM
    assert decision_med == AlertDecision.STEP_UP_REQUIRED

    # High risk
    score_high, level_high, decision_high = aggregator.aggregate(supervised_prob=0.9, anomaly_score=0.8)
    assert score_high > 70.0
    assert level_high == AlertLevel.HIGH
    assert decision_high == AlertDecision.BLOCKED


def test_shap_explanations_output():
    engine = FeatureEngine()
    features = engine.extract_features(
        amount=5000.0,
        user_history_amounts=[50.0, 60.0, 45.0],
        last_login_distance_km=2500.0,
        last_login_elapsed_hours=0.5,
        is_known_device=False,
    )
    feature_arr = engine.to_feature_array(features)

    explainer = FraudSHAPExplainer(model=None)
    explanation = explainer.explain(feature_arr, features)

    assert "top_reasons" in explanation
    assert len(explanation["top_reasons"]) > 0
    reasons_text = " ".join(explanation["top_reasons"])
    assert "transfer amount" in reasons_text.lower() or "device" in reasons_text.lower()

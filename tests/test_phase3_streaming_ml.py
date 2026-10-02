import asyncio
import datetime
import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.account import Account, AccountType
from app.models.fraud_alert import AlertDecision, AlertLevel, FraudAlert
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User, UserRole
from app.streaming.events import TransactionCreatedEvent
from app.streaming.publisher import event_publisher
from ml_pipeline.decision_engine.risk_aggregator import RiskAggregator
from ml_pipeline.explainability.shap_explainer import FraudSHAPExplainer
from ml_pipeline.features.feature_engine import FeatureEngine, haversine_distance
from ml_pipeline.models.isolation_forest import IsolationForestModel
from ml_pipeline.models.xgboost_model import XGBoostFraudModel
from ml_pipeline.service import ml_service
from workers.streaming_consumer import process_transaction_event


# ==============================================================================
# 1. BANK-17, 18, 19: FEATURE ENGINEERING ENGINE & REDIS CACHING
# ==============================================================================

def test_haversine_distance_calculation():
    """Test Haversine distance formula for detecting geographic velocity."""
    # Coordinates: New York (40.7128, -74.0060) to London (51.5074, -0.1278) ~ 5570 km
    dist = haversine_distance(40.7128, -74.0060, 51.5074, -0.1278)
    assert 5500.0 < dist < 5650.0


def test_feature_engine_metrics_and_impossible_travel():
    """Test feature engine derived features: z-score, velocity, device flags."""
    engine = FeatureEngine()
    features = engine.extract_features(
        amount=2500.0,
        user_history_amounts=[100.0, 110.0, 105.0, 95.0, 100.0],
        login_timestamps_24h=[
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2),
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5),
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=12),
        ],
        last_login_distance_km=1800.0,
        last_login_elapsed_hours=1.5,  # 1200 km/h -> impossible commercial travel
        is_known_device=False,
    )

    assert features["amount"] == 2500.0
    assert features["amount_z_score"] > 3.0  # Spike above average
    assert features["login_frequency_24h"] == 3.0
    assert features["geo_velocity"] == 1200.0  # 1800 km / 1.5 h
    assert features["is_new_device"] == 1.0


def test_feature_engine_caching():
    """Test caching rolling user statistics in FeatureEngine for sub-millisecond lookup."""
    engine = FeatureEngine()
    user_id = str(uuid.uuid4())

    # Cache stats
    engine.cache_user_stats(user_id, mean_val=350.0, std_val=45.0)
    cached = engine.get_cached_user_stats(user_id)
    assert cached is not None
    assert cached[0] == 350.0
    assert cached[1] == 45.0

    # Extract features using cached stats
    features = engine.extract_features(amount=440.0, user_id=user_id)
    # z = (440 - 350) / 45 = 2.0
    assert abs(features["amount_z_score"] - 2.0) < 0.01


# ==============================================================================
# 2. BANK-20 to 25: DUAL ML RISK PIPELINE & DECISION AGGREGATOR
# ==============================================================================

def test_dual_model_risk_scoring():
    """Test dual-model ML scoring service combining supervised and unsupervised models."""
    res = ml_service.score_transaction(
        amount=150.0,
        user_history_amounts=[140.0, 160.0, 150.0, 145.0],
        last_login_distance_km=10.0,
        last_login_elapsed_hours=2.0,
        is_known_device=True,
    )
    assert "risk_score" in res
    assert 0.0 <= res["risk_score"] <= 100.0
    assert res["alert_level"] in [AlertLevel.LOW, AlertLevel.MEDIUM, AlertLevel.HIGH]
    assert res["decision"] in [AlertDecision.APPROVED, AlertDecision.STEP_UP_REQUIRED, AlertDecision.BLOCKED]
    assert "supervised_probability" in res
    assert "anomaly_score" in res
    assert "explanations" in res


def test_risk_aggregator_decision_matrix():
    """Test policy decision boundaries (Low < 30, Medium 30-70, High > 70)."""
    aggregator = RiskAggregator(supervised_weight=0.6, anomaly_weight=0.4)

    # Low Risk (< 30) -> Approved
    score_low, level_low, dec_low = aggregator.aggregate(supervised_prob=0.1, anomaly_score=0.15)
    assert score_low < 30.0
    assert level_low == AlertLevel.LOW
    assert dec_low == AlertDecision.APPROVED

    # Medium Risk (30 - 70) -> Step-Up Required
    score_med, level_med, dec_med = aggregator.aggregate(supervised_prob=0.55, anomaly_score=0.50)
    assert 30.0 <= score_med <= 70.0
    assert level_med == AlertLevel.MEDIUM
    assert dec_med == AlertDecision.STEP_UP_REQUIRED

    # High Risk (> 70) -> Blocked
    score_high, level_high, dec_high = aggregator.aggregate(supervised_prob=0.85, anomaly_score=0.80)
    assert score_high > 70.0
    assert level_high == AlertLevel.HIGH
    assert dec_high == AlertDecision.BLOCKED


# ==============================================================================
# 3. BANK-26: SHAP EXPLAINABILITY ATTRIBUTION
# ==============================================================================

def test_shap_feature_explanations():
    """Test generation of plain-English reason statements from feature attribution."""
    explainer = FraudSHAPExplainer(model=None)
    engine = FeatureEngine()
    features = engine.extract_features(
        amount=10000.0,
        user_history_amounts=[100.0, 120.0, 110.0],
        last_login_distance_km=3000.0,
        last_login_elapsed_hours=1.0,
        is_known_device=False,
    )
    arr = engine.to_feature_array(features)
    explanation = explainer.explain(arr, features)

    assert "top_reasons" in explanation
    assert len(explanation["top_reasons"]) >= 2
    reasons_str = " ".join(explanation["top_reasons"]).lower()
    assert "amount" in reasons_str
    assert "device" in reasons_str or "travel" in reasons_str or "velocity" in reasons_str


# ==============================================================================
# 4. BANK-15 & 16: STREAMING PIPELINE & FRAUD_ALERT DATABASE PERSISTENCE
# ==============================================================================

@pytest.mark.asyncio
async def test_streaming_event_publish_on_transfer(client: AsyncClient, customer_headers: dict):
    """Test that POST /transactions/transfer triggers event emission."""
    acc1 = (await client.post("/accounts", json={"AccountType": "Checking", "InitialDeposit": "2000.00"}, headers=customer_headers)).json()
    acc2 = (await client.post("/accounts", json={"AccountType": "Savings", "InitialDeposit": "100.00"}, headers=customer_headers)).json()

    transfer_payload = {
        "SenderAccountID": acc1["AccountID"],
        "ReceiverAccountID": acc2["AccountID"],
        "Amount": "250.00",
        "Description": "Streaming test transfer",
    }

    # Intercept published events
    published_events = []
    original_publish = event_publisher.publish_event

    async def mock_publish(topic_or_queue: str, message: dict):
        published_events.append((topic_or_queue, message))
        return True

    event_publisher.publish_event = mock_publish
    try:
        res = await client.post("/transactions/transfer", json=transfer_payload, headers=customer_headers)
        assert res.status_code == 201

        # Check that event was published to Kafka/RabbitMQ transaction topic
        assert len(published_events) >= 1
        topic, event_data = published_events[0]
        assert topic == settings.KAFKA_TRANSACTION_TOPIC
        assert event_data["event_type"] == "TRANSACTION_CREATED"
        assert event_data["transaction_id"] == res.json()["TransactionID"]
        assert float(event_data["amount"]) == 250.00
    finally:
        event_publisher.publish_event = original_publish


@pytest.mark.asyncio
async def test_streaming_consumer_processing_and_fraud_alert_persistence(
    client: AsyncClient,
    customer_headers: dict,
    db_session: AsyncSession,
):
    """Test streaming consumer worker: receives event, runs ML pipeline, updates tx status, persists FRAUD_ALERT."""
    # 1. Setup accounts and transaction
    acc1 = (await client.post("/accounts", json={"AccountType": "Checking", "InitialDeposit": "1000.00"}, headers=customer_headers)).json()
    acc2 = (await client.post("/accounts", json={"AccountType": "Savings", "InitialDeposit": "50.00"}, headers=customer_headers)).json()

    tx = (await client.post("/transactions/transfer", json={
        "SenderAccountID": acc1["AccountID"],
        "ReceiverAccountID": acc2["AccountID"],
        "Amount": "100.00",
    }, headers=customer_headers)).json()

    tx_id = tx["TransactionID"]

    # 2. Simulate streaming consumer worker processing this transaction event
    event_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "TRANSACTION_CREATED",
        "transaction_id": tx_id,
        "account_id": acc1["AccountID"],
        "user_id": acc1["UserID"],
        "amount": 100.0,
        "sender_account": acc1["AccountID"],
        "receiver_account": acc2["AccountID"],
        "device_fingerprint": "known-fp",
    }

    alert = await process_transaction_event(event_payload, db=db_session)
    assert alert is not None
    assert alert.TransactionID == uuid.UUID(tx_id)
    assert 0.0 <= alert.RiskScore <= 100.0
    assert alert.AlertLevel in [AlertLevel.LOW, AlertLevel.MEDIUM, AlertLevel.HIGH]
    assert alert.Decision in [AlertDecision.APPROVED, AlertDecision.STEP_UP_REQUIRED, AlertDecision.BLOCKED]
    assert alert.Explanations is not None

    # 3. Query via REST API: GET /transactions/{id}/risk-score
    risk_api_res = await client.get(f"/transactions/{tx_id}/risk-score", headers=customer_headers)
    assert risk_api_res.status_code == 200
    risk_data = risk_api_res.json()
    assert risk_data["TransactionID"] == tx_id
    assert risk_data["RiskScore"] == alert.RiskScore
    assert risk_data["AlertLevel"] == alert.AlertLevel.value
    assert risk_data["Decision"] == alert.Decision.value
    assert "top_reasons" in risk_data["Explanations"]

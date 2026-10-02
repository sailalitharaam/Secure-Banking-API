import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
DATA_DIR = BASE_DIR / "data"

ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

XGBOOST_MODEL_PATH = ARTIFACTS_DIR / "xgboost_fraud_model.json"
ISOLATION_FOREST_PATH = ARTIFACTS_DIR / "isolation_forest_model.joblib"
SCALER_PATH = ARTIFACTS_DIR / "feature_scaler.joblib"
SHAP_BACKGROUND_PATH = ARTIFACTS_DIR / "shap_background.joblib"

# Feature Names
FEATURE_NAMES = [
    "amount",
    "amount_z_score",
    "login_frequency_24h",
    "geo_velocity",
    "is_new_device",
    "hour_of_day",
    "day_of_week",
]

# Risk Aggregator Thresholds
RISK_THRESHOLD_LOW = 30.0
RISK_THRESHOLD_HIGH = 70.0

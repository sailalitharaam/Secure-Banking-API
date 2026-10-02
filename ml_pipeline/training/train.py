import logging
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
from imblearn.over_sampling import SMOTE

from ml_pipeline.config import (
    ISOLATION_FOREST_PATH,
    XGBOOST_MODEL_PATH,
    ARTIFACTS_DIR,
)
from ml_pipeline.models.xgboost_model import XGBoostFraudModel
from ml_pipeline.models.isolation_forest import IsolationForestModel
from ml_pipeline.training.dataset_generator import generate_synthetic_fraud_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_training_pipeline() -> None:
    """Execute complete end-to-end training pipeline for supervised and unsupervised fraud models."""
    logger.info("Starting ML Fraud Detection training pipeline...")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate imbalanced synthetic dataset
    logger.info("Generating realistic transaction dataset with 4% fraud ratio...")
    X, y = generate_synthetic_fraud_dataset(n_samples=10000, fraud_ratio=0.04)

    X_train, X_test, y_train, y_test = train_test_split(
        X.values, y.values, test_size=0.2, random_state=42, stratify=y.values
    )
    logger.info("Training set size: %d | Test set size: %d", len(X_train), len(X_test))

    # 2. Resample training data using SMOTE to handle extreme class imbalance
    logger.info("Applying SMOTE oversampling to balance minority fraud class...")
    smote = SMOTE(random_state=42)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)
    logger.info("Resampled training set size: %d", len(X_train_resampled))

    # 3. Train Supervised XGBoost Classifier
    logger.info("Training XGBoost Classifier...")
    xgb_model = XGBoostFraudModel()
    xgb_model.train(X_train_resampled, y_train_resampled, eval_set=[(X_test, y_test)])
    xgb_model.save(XGBOOST_MODEL_PATH)

    # Evaluate XGBoost
    y_pred_proba = xgb_model.predict_proba(X_test)
    y_pred = (y_pred_proba >= 0.5).astype(int)
    auc_score = roc_auc_score(y_test, y_pred_proba)
    logger.info("XGBoost ROC-AUC Score: %.4f", auc_score)
    logger.info("\nClassification Report:\n%s", classification_report(y_test, y_pred))

    # 4. Train Unsupervised Isolation Forest Anomaly Detector (fit on legitimate transactions)
    logger.info("Training Isolation Forest on legitimate transactions baseline...")
    X_train_normal = X_train[y_train == 0]
    iso_model = IsolationForestModel()
    iso_model.train(X_train_normal, contamination=0.03)
    iso_model.save(ISOLATION_FOREST_PATH)

    logger.info("All model artifacts saved successfully to %s", ARTIFACTS_DIR)


if __name__ == "__main__":
    run_training_pipeline()

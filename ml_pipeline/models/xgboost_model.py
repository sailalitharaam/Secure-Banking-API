import logging
from pathlib import Path
from typing import Optional, Union
import numpy as np

logger = logging.getLogger(__name__)


class XGBoostFraudModel:
    """Supervised XGBoost model for binary fraud classification."""

    def __init__(self, model_path: Optional[Union[str, Path]] = None) -> None:
        self.model = None
        self.model_path = Path(model_path) if model_path else None
        if self.model_path and self.model_path.exists():
            self.load(self.model_path)

    def train(self, X: np.ndarray, y: np.ndarray, eval_set: Optional[tuple] = None) -> None:
        """Train XGBoost classifier."""
        import xgboost as xgb

        self.model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.08,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=1.0,  # Training is already balanced with SMOTE
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X, y, eval_set=eval_set, verbose=False)
        logger.info("XGBoost fraud model training completed.")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict fraud probabilities [0.0 - 1.0]."""
        if self.model is not None:
            # Predict probability of fraud (class 1)
            probs = self.model.predict_proba(X)
            return probs[:, 1]

        # Heuristic baseline fallback if model file hasn't been generated yet
        logger.debug("XGBoost model not loaded; using baseline heuristic fallback.")
        results = []
        for row in X:
            amount_z = row[1] if len(row) > 1 else 0.0
            is_new_dev = row[4] if len(row) > 4 else 0.0
            score = 0.05
            if amount_z > 3.0:
                score += 0.45
            elif amount_z > 2.0:
                score += 0.25
            if is_new_dev > 0.5:
                score += 0.35
            results.append(min(score, 0.99))
        return np.array(results)

    def save(self, path: Union[str, Path]) -> None:
        """Save model to JSON format."""
        if self.model:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.model.save_model(str(path))
            logger.info("Saved XGBoost model to %s", path)

    def load(self, path: Union[str, Path]) -> None:
        """Load model from file."""
        import xgboost as xgb

        path = Path(path)
        if path.exists():
            self.model = xgb.XGBClassifier()
            self.model.load_model(str(path))
            logger.info("Loaded XGBoost model from %s", path)
        else:
            logger.warning("XGBoost model file not found at %s", path)

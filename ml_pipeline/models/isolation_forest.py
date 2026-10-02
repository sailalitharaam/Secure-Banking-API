import logging
from pathlib import Path
from typing import Optional, Union
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)


class IsolationForestModel:
    """Unsupervised Isolation Forest model for zero-day anomaly and outlier detection."""

    def __init__(self, model_path: Optional[Union[str, Path]] = None) -> None:
        self.model: Optional[IsolationForest] = None
        self.model_path = Path(model_path) if model_path else None
        if self.model_path and self.model_path.exists():
            self.load(self.model_path)

    def train(self, X: np.ndarray, contamination: float = 0.03) -> None:
        """Fit Isolation Forest on baseline transaction feature vectors."""
        self.model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            max_features=1.0,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X)
        logger.info("Isolation Forest anomaly detector training completed.")

    def score_anomaly(self, X: np.ndarray) -> np.ndarray:
        """Compute anomaly score scaled from 0.0 (normal) to 1.0 (highly anomalous)."""
        if self.model is not None:
            # decision_function gives negative scores for outliers, positive for inliers
            raw_scores = self.model.decision_function(X)
            # Map into [0.0, 1.0] where 1.0 means highly anomalous
            # Typicall range of decision_function is ~ [-0.5, 0.5]
            anomaly_scores = 0.5 - (raw_scores * 0.8)
            return np.clip(anomaly_scores, 0.0, 1.0)

        # Baseline heuristic fallback
        logger.debug("Isolation Forest model not loaded; using baseline heuristic fallback.")
        results = []
        for row in X:
            geo_vel = row[3] if len(row) > 3 else 0.0
            score = 0.05
            if geo_vel > 800.0:  # Impossible travel (> 800 km/h)
                score += 0.65
            elif geo_vel > 200.0:
                score += 0.25
            results.append(min(score, 0.99))
        return np.array(results)

    def save(self, path: Union[str, Path]) -> None:
        """Save Isolation Forest model with joblib."""
        if self.model:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, str(path))
            logger.info("Saved Isolation Forest model to %s", path)

    def load(self, path: Union[str, Path]) -> None:
        """Load Isolation Forest model with joblib."""
        path = Path(path)
        if path.exists():
            self.model = joblib.load(str(path))
            logger.info("Loaded Isolation Forest model from %s", path)
        else:
            logger.warning("Isolation Forest model file not found at %s", path)

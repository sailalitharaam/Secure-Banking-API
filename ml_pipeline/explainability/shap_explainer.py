import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from ml_pipeline.config import FEATURE_NAMES

logger = logging.getLogger(__name__)


class FraudSHAPExplainer:
    """Computes SHAP (SHapley Additive exPlanations) feature attributions for risk scores."""

    def __init__(self, model: Optional[Any] = None) -> None:
        self.model = model
        self.explainer = None
        if self.model is not None:
            self._init_explainer()

    def _init_explainer(self) -> None:
        """Initialize SHAP TreeExplainer if model is available."""
        try:
            import shap
            underlying = getattr(self.model, "model", self.model)
            if underlying is not None and not isinstance(underlying, type(self.model)):
                self.explainer = shap.TreeExplainer(underlying)
            elif underlying is not None and hasattr(underlying, "predict"):
                self.explainer = shap.TreeExplainer(underlying)
        except Exception as e:
            logger.warning("SHAP TreeExplainer could not be initialized (%s); fallback will be used.", e)
            self.explainer = None

    def explain(self, feature_array: np.ndarray, feature_dict: Dict[str, float]) -> Dict[str, Any]:
        """Generate top influential factors and human-readable explanation sentences."""
        if self.explainer is None and self.model is not None:
            self._init_explainer()

        explanations: List[str] = []
        feature_importance: Dict[str, float] = {}

        if self.explainer is not None:
            try:
                shap_values = self.explainer.shap_values(feature_array)
                # Handle binary classification output shape
                if isinstance(shap_values, list) and len(shap_values) > 1:
                    vals = shap_values[1][0]
                elif len(shap_values.shape) > 1:
                    vals = shap_values[0]
                else:
                    vals = shap_values

                for idx, name in enumerate(FEATURE_NAMES):
                    val = float(vals[idx])
                    feature_importance[name] = round(val, 4)
            except Exception as e:
                logger.debug("SHAP explanation calculation failed (%s); using heuristic attributions.", e)

        # Rule-based human-readable explanations
        amount_z = feature_dict.get("amount_z_score", 0.0)
        if amount_z > 3.0:
            explanations.append(f"Unusually large transfer amount ({amount_z:.1f}x historical standard deviation)")
        elif amount_z > 1.5:
            explanations.append("Transfer amount moderately higher than account average")

        if feature_dict.get("is_new_device", 0.0) > 0.5:
            explanations.append("Transaction initiated from a previously unrecognized device fingerprint")

        geo_vel = feature_dict.get("geo_velocity", 0.0)
        if geo_vel > 800.0:
            explanations.append(f"Suspicious geographic velocity ({geo_vel:.0f} km/h) indicates impossible travel")
        elif geo_vel > 250.0:
            explanations.append("Rapid location change detected between consecutive sessions")

        login_freq = feature_dict.get("login_frequency_24h", 0.0)
        if login_freq > 8.0:
            explanations.append(f"Abnormally high login velocity ({int(login_freq)} sessions in last 24h)")

        if not explanations:
            explanations.append("Transaction behavioral pattern aligns with normal account history")

        return {
            "top_reasons": explanations,
            "feature_attribution": feature_importance,
            "raw_features": feature_dict,
        }

import datetime
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from ml_pipeline.config import FEATURE_NAMES


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on the earth in kilometers."""
    r = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


class FeatureEngine:
    """Extracts behavioral, temporal, and anomaly-detection features from transaction and user metadata,
    leveraging Redis caching for sub-millisecond retrieval.
    """

    def __init__(self, redis_client: Optional[Any] = None) -> None:
        self.redis = redis_client
        self._local_cache: Dict[str, Any] = {}

    def extract_features(
        self,
        amount: float,
        user_history_amounts: Optional[List[float]] = None,
        login_timestamps_24h: Optional[List[datetime.datetime]] = None,
        last_login_distance_km: Optional[float] = None,
        last_login_elapsed_hours: Optional[float] = None,
        is_known_device: bool = True,
        timestamp: Optional[datetime.datetime] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, float]:
        """Extract a structured feature vector dictionary."""
        dt = timestamp or datetime.datetime.now(datetime.timezone.utc)

        # 1. Amount z-score: (amount - mean) / std
        # First attempt fast lookup from Redis cache if user_id is provided
        cached_stats = self.get_cached_user_stats(user_id) if user_id else None
        if cached_stats:
            mean_val, std_val = cached_stats
            amount_z_score = (amount - mean_val) / std_val
        elif user_history_amounts and len(user_history_amounts) >= 3:
            mean_val = float(np.mean(user_history_amounts))
            std_val = float(np.std(user_history_amounts))
            if std_val < 1e-4:
                std_val = 1.0
            amount_z_score = (amount - mean_val) / std_val
            if user_id:
                self.cache_user_stats(user_id, mean_val, std_val)
        else:
            # Baseline assumptions for new user / account
            amount_z_score = (amount - 200.0) / 150.0

        # 2. Login frequency in past 24 hours
        if user_id and not login_timestamps_24h:
            login_frequency_24h = float(self.get_cached_login_frequency(user_id))
        else:
            login_frequency_24h = float(len(login_timestamps_24h)) if login_timestamps_24h else 1.0

        # 3. Geo-velocity: speed (km/h) between consecutive logins (detecting impossible travel)
        if last_login_distance_km is not None and last_login_elapsed_hours is not None:
            elapsed = max(0.01, last_login_elapsed_hours)
            geo_velocity = float(last_login_distance_km / elapsed)
        else:
            geo_velocity = 0.0

        # 4. Is new device flag: 1.0 if not known, 0.0 if known
        is_new_device = 0.0 if is_known_device else 1.0

        # 5. Temporal features
        hour_of_day = float(dt.hour)
        day_of_week = float(dt.weekday())

        return {
            "amount": float(amount),
            "amount_z_score": float(np.clip(amount_z_score, -5.0, 15.0)),
            "login_frequency_24h": login_frequency_24h,
            "geo_velocity": float(np.clip(geo_velocity, 0.0, 3000.0)),
            "is_new_device": is_new_device,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
        }

    def get_cached_user_stats(self, user_id: str) -> Optional[Tuple[float, float]]:
        """Fetch cached (mean, std) for user from Redis or local memory."""
        if self.redis:
            try:
                data = self.redis.hgetall(f"user:{user_id}:stats")
                if data and b"mean" in data and b"std" in data:
                    return float(data[b"mean"]), float(data[b"std"])
            except Exception:
                pass
        return self._local_cache.get(f"user:{user_id}:stats")

    def cache_user_stats(self, user_id: str, mean_val: float, std_val: float) -> None:
        """Cache user transaction stats in Redis with 1-hour TTL."""
        if self.redis:
            try:
                self.redis.hset(f"user:{user_id}:stats", mapping={"mean": str(mean_val), "std": str(std_val)})
                self.redis.expire(f"user:{user_id}:stats", 3600)
            except Exception:
                pass
        self._local_cache[f"user:{user_id}:stats"] = (mean_val, std_val)

    def get_cached_login_frequency(self, user_id: str) -> int:
        """Get 24h login frequency from Redis."""
        if self.redis:
            try:
                count = self.redis.get(f"user:{user_id}:login_count_24h")
                if count:
                    return int(count)
            except Exception:
                pass
        return self._local_cache.get(f"user:{user_id}:login_count_24h", 1)

    def to_feature_array(self, feature_dict: Dict[str, float]) -> np.ndarray:
        """Convert a feature dictionary into ordered numpy array matching FEATURE_NAMES."""
        return np.array([[feature_dict[name] for name in FEATURE_NAMES]], dtype=np.float32)

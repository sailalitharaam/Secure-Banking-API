import numpy as np
import pandas as pd
from typing import Tuple

from ml_pipeline.config import FEATURE_NAMES


def generate_synthetic_fraud_dataset(
    n_samples: int = 5000,
    fraud_ratio: float = 0.04,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.Series]:
    """Generate a realistic synthetic banking transactions dataset with imbalanced fraud labels."""
    np.random.seed(random_state)
    n_fraud = int(n_samples * fraud_ratio)
    n_legit = n_samples - n_fraud

    # --- Legitimate Transactions ---
    legit_amount = np.random.gamma(shape=2.0, scale=80.0, size=n_legit) + 5.0
    legit_amount_z = (legit_amount - 165.0) / 110.0
    legit_login_freq = np.random.poisson(lam=1.8, size=n_legit) + 1.0
    legit_geo_vel = np.random.exponential(scale=15.0, size=n_legit)
    legit_is_new_device = np.random.binomial(n=1, p=0.08, size=n_legit)
    legit_hour = np.random.randint(6, 23, size=n_legit)
    legit_day = np.random.randint(0, 7, size=n_legit)

    df_legit = pd.DataFrame({
        "amount": legit_amount,
        "amount_z_score": legit_amount_z,
        "login_frequency_24h": legit_login_freq,
        "geo_velocity": legit_geo_vel,
        "is_new_device": legit_is_new_device,
        "hour_of_day": legit_hour,
        "day_of_week": legit_day,
        "is_fraud": 0,
    })

    # --- Fraud Transactions ---
    # Fraud patterns: unusually high amounts, unusual hours (midnight-4am), impossible travel, new devices
    fraud_amount = np.random.gamma(shape=5.0, scale=350.0, size=n_fraud) + 400.0
    fraud_amount_z = (fraud_amount - 165.0) / 110.0
    fraud_login_freq = np.random.poisson(lam=5.5, size=n_fraud) + 2.0
    fraud_geo_vel = np.random.uniform(300.0, 1500.0, size=n_fraud)  # impossible flight travel
    fraud_is_new_device = np.random.binomial(n=1, p=0.75, size=n_fraud)
    fraud_hour = np.random.choice([0, 1, 2, 3, 4, 23], size=n_fraud)
    fraud_day = np.random.randint(0, 7, size=n_fraud)

    df_fraud = pd.DataFrame({
        "amount": fraud_amount,
        "amount_z_score": fraud_amount_z,
        "login_frequency_24h": fraud_login_freq,
        "geo_velocity": fraud_geo_vel,
        "is_new_device": fraud_is_new_device,
        "hour_of_day": fraud_hour,
        "day_of_week": fraud_day,
        "is_fraud": 1,
    })

    # Combine and shuffle
    df = pd.concat([df_legit, df_fraud], ignore_index=True)
    df = df.sample(frac=1.0, random_state=random_state).reset_index(drop=True)

    X = df[FEATURE_NAMES]
    y = df["is_fraud"]

    return X, y

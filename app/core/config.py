from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General Settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "Secure Banking API & AI Fraud Pipeline"
    API_V1_STR: str = "/api/v1"

    # Security & JWT Tokens
    JWT_SECRET_KEY: str = "default-insecure-secret-key-change-in-production-1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # PostgreSQL Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "banking_user"
    POSTGRES_PASSWORD: str = "banking_secure_pass"
    POSTGRES_DB: str = "banking_db"
    DATABASE_URL: str = "postgresql+asyncpg://banking_user:banking_secure_pass@localhost:5432/banking_db"
    DATABASE_URL_SYNC: str = "postgresql://banking_user:banking_secure_pass@localhost:5432/banking_db"

    # Redis Cache & Rate Limiting
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    # Rate Limiting
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # Streaming & Event Bus
    STREAMING_BROKER_TYPE: str = "kafka"  # "kafka" or "rabbitmq"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TRANSACTION_TOPIC: str = "banking.transactions.v1"
    KAFKA_ALERTS_TOPIC: str = "banking.fraud.alerts.v1"
    KAFKA_CONSUMER_GROUP: str = "fraud-scoring-group"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_TRANSACTION_QUEUE: str = "banking.transactions.queue"

    # Machine Learning & Fraud Pipeline Config
    ML_MODEL_DIR: str = "ml_pipeline/artifacts"
    XGBOOST_MODEL_FILE: str = "xgboost_fraud_model.json"
    ISOLATION_FOREST_FILE: str = "isolation_forest_model.joblib"
    SHAP_BACKGROUND_DATA_FILE: str = "shap_background.joblib"

    # Risk Thresholds
    RISK_THRESHOLD_LOW: float = 30.0
    RISK_THRESHOLD_HIGH: float = 70.0

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:5173",
    ]


settings = Settings()

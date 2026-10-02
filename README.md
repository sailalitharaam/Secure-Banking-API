# Secure Banking API & AI Fraud Pipeline

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io/)
[![XGBoost](https://img.shields.io/badge/ML-XGBoost%20%7C%20SHAP-orange.svg)](https://xgboost.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

A high-performance Secure Banking REST API integrated with an asynchronous event-driven real-time AI/ML Fraud Detection & Risk Mitigation pipeline.

---

## Repository Scaffolding & Directory Tree

```
secure_banking_api/
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore file
├── ARCHITECTURE.md               # Complete architecture, ER diagram & ML design
├── README.md                     # Setup, running, and testing guide
├── Dockerfile                    # Multi-stage production container
├── docker-compose.yml            # PostgreSQL, Redis, Kafka, FastAPI, and Worker services
├── requirements.txt              # Production and testing dependencies
├── alembic.ini                   # Database migrations configuration
├── alembic/                      # Alembic migration scripts and env
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── app/                          # Core FastAPI Application
│   ├── __init__.py
│   ├── main.py                   # App entrypoint, CORS, rate limiter, lifespan
│   ├── core/
│   │   ├── config.py             # Pydantic Settings
│   │   ├── security.py           # Bcrypt/Argon2 hashing & JWT creation/verification
│   │   ├── dependencies.py       # DB, auth & RBAC (Customer, Merchant, Bank Admin)
│   │   └── rate_limiter.py       # Redis slowapi rate limiter
│   ├── db/
│   │   ├── base.py               # DeclarativeBase & ORM model registration
│   │   └── session.py            # Async SQLAlchemy engine & session factory
│   ├── models/                   # 7-Entity Relational Database Schema
│   │   ├── user.py               # USER entity
│   │   ├── account.py            # ACCOUNT entity
│   │   ├── device.py             # DEVICE entity
│   │   ├── session.py            # SESSION entity
│   │   ├── auth_token.py         # AUTH_TOKEN entity
│   │   ├── transaction.py        # TRANSACTION entity
│   │   └── fraud_alert.py        # FRAUD_ALERT entity
│   ├── schemas/                  # Pydantic v2 Request & Response schemas
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── account.py
│   │   ├── device.py
│   │   ├── session.py
│   │   ├── transaction.py
│   │   └── fraud_alert.py
│   ├── services/                 # Business Logic & Atomic DB Operations
│   │   ├── auth_service.py       # Registration, login, token refresh, logout
│   │   ├── account_service.py    # Account management & paginated history
│   │   ├── transaction_service.py# Atomic transfer with row-level locking
│   │   ├── device_service.py     # Device fingerprinting & session tracking
│   │   └── alert_service.py      # Fraud queries & dashboard metrics
│   ├── api/                      # REST API Endpoints
│   │   └── v1/
│   │       ├── router.py
│   │       └── endpoints/
│   │           ├── auth.py       # /auth/register, login, refresh, logout
│   │           ├── accounts.py   # /accounts, /accounts/{id}/history
│   │           ├── transactions.py # /transactions/transfer, /transactions/{id}/risk-score
│   │           ├── alerts.py     # /alerts (Admin only)
│   │           └── admin.py      # /admin/dashboard/transactions, alerts, metrics
│   └── streaming/                # Event-Driven Messaging
│       ├── events.py             # TransactionCreatedEvent, FraudAlertEvent
│       └── publisher.py          # Kafka / RabbitMQ asynchronous publisher
├── ml_pipeline/                  # Machine Learning & Fraud Risk Engine
│   ├── config.py                 # ML paths and risk thresholds
│   ├── features/
│   │   └── feature_engine.py     # amount_z_score, login_frequency_24h, geo_velocity, is_new_device
│   ├── models/
│   │   ├── xgboost_model.py      # Supervised XGBoost classifier
│   │   └── isolation_forest.py   # Unsupervised Isolation Forest anomaly detector
│   ├── explainability/
│   │   └── shap_explainer.py     # TreeSHAP feature attribution & plain English reasons
│   ├── decision_engine/
│   │   └── risk_aggregator.py    # 0-100 score aggregation, Low/Medium/High policy rules
│   ├── training/
│   │   ├── dataset_generator.py  # Realistic synthetic fraud dataset generator
│   │   └── train.py              # Training pipeline with SMOTE oversampling
│   └── service.py                # Standalone ML Risk Scoring Service
├── workers/                      # Real-Time Event Consumers
│   └── streaming_consumer.py     # Kafka consumer worker running real-time ML risk scoring
└── tests/                        # Automated Test Suites
    ├── conftest.py               # Async DB fixtures and auth tokens
    ├── test_auth.py              # Auth, login, session, and token revocation tests
    ├── test_accounts.py          # Account management & history tests
    ├── test_transactions.py      # Atomic transfers & locking tests
    ├── test_ml_pipeline.py       # ML features, scoring, and SHAP tests
    ├── test_security_owasp.py    # OWASP API Top 10 security verification tests
    └── locustfile.py             # Locust load testing script (p95 < 1s)
```

---

## Quickstart Guide

### 1. Configure Environment
```bash
cp .env.example .env
```

### 2. Run with Docker Compose
To spin up PostgreSQL, Redis, Kafka, the FastAPI API server, and the Streaming Worker:
```bash
docker compose up -d --build
```
* Interactive API Documentation (Swagger): `http://localhost:8000/docs`
* ReDoc API Documentation: `http://localhost:8000/redoc`

### 3. Local Development Setup (Without Docker)

#### Install Dependencies:
```bash
pip install -r requirements.txt
```

#### Run Database Migrations:
```bash
alembic upgrade head
```

#### Train Fraud ML Models:
```bash
python -m ml_pipeline.training.train
```

#### Start FastAPI API Server:
```bash
uvicorn app.main:app --reload --port 8000
```

#### Start Real-Time Streaming Worker:
```bash
python -m workers.streaming_consumer
```

---

## Running the Automated Test Suite

### Run Pytest:
```bash
pytest tests/ -v
```

### Run Load Testing with Locust:
```bash
locust -f tests/locustfile.py --host=http://localhost:8000
```
Open `http://localhost:8089` in your browser to configure simulated concurrent users and ramp-up rate.

---

## 7 Core Database Entities

1. **USER**: `UserID` (PK), `Email`, `PasswordHash`, `Role` (Customer, Merchant, Bank Admin), `CreatedAt`.
2. **ACCOUNT**: `AccountID` (PK), `UserID` (FK), `AccountType`, `Balance`, `KYCStatus`, `CreatedAt`.
3. **DEVICE**: `DeviceID` (PK), `UserID` (FK), `DeviceFingerprint`, `DeviceType`, `LastUsedIP`, `UpdatedAt`.
4. **SESSION**: `SessionID` (PK), `UserID` (FK), `DeviceID` (FK), `LoginTime`, `IPAddress`, `Location`, `IsActive`.
5. **AUTH_TOKEN**: `TokenID` (PK), `UserID` (FK), `RefreshToken`, `IsRevoked`, `ExpiresAt`.
6. **TRANSACTION**: `TransactionID` (PK), `AccountID` (FK), `Amount`, `TransactionType`, `SenderAccount`, `ReceiverAccount`, `Status` (Approved, Pending, Blocked), `Timestamp`.
7. **FRAUD_ALERT**: `AlertID` (PK), `TransactionID` (FK), `RiskScore` (0-100), `AlertLevel` (Low, Medium, High), `Decision` (Approved, Step-Up Required, Blocked), `Explanations` (JSON), `CreatedAt`.

---

## Core REST API Specification

* `POST /auth/register` - User registration with Argon2/bcrypt password hashing.
* `POST /auth/login` - User login; generates JWT Access Token + Refresh Token, records Session/Device metadata.
* `POST /auth/refresh` - Refresh access token using valid refresh token.
* `POST /auth/logout` - Invalidate session & revoke refresh token.
* `GET /accounts` & `POST /accounts` - Fetch user accounts & open new accounts.
* `GET /accounts/{id}/history` - Paginated account transaction history.
* `POST /transactions/transfer` - Atomic fund transfer with transactional locking (`with_for_update()`).
* `GET /transactions/{id}/risk-score` - Fetch fraud risk score for a given transaction.
* `GET /alerts` - Retrieve flagged high/medium risk transactions (Admin only).
* `GET /admin/dashboard/transactions` - Real-time transaction monitoring feed.
* `GET /admin/dashboard/alerts` - Active alert queue with SHAP explanations.
* `GET /admin/dashboard/metrics` - Live precision, recall, F1, and false positive metrics.

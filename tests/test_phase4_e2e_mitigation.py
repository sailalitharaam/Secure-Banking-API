import datetime
import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, AccountType, KYCStatus
from app.models.fraud_alert import AlertDecision, AlertLevel, FraudAlert
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User, UserRole
from app.services.mitigation_service import MitigationService, _in_memory_otp_cache
from app.streaming.events import TransactionCreatedEvent
from app.streaming.publisher import event_publisher
from workers.streaming_consumer import process_transaction_event


# Helper to create an account for testing
async def _create_test_account(
    db: AsyncSession,
    user: User,
    balance: Decimal = Decimal("10000.00"),
    account_type: AccountType = AccountType.CHECKING,
) -> Account:
    acc = Account(
        AccountID=uuid.uuid4(),
        UserID=user.UserID,
        AccountType=account_type,
        Balance=balance,
        KYCStatus=KYCStatus.VERIFIED,
    )
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    return acc


# ==============================================================================
# 1. BANK-27 to 30: AUTOMATED MITIGATION & STEP-UP OTP E2E
# ==============================================================================

@pytest.mark.asyncio
async def test_e2e_low_risk_transfer_auto_approved(
    client: AsyncClient,
    db_session: AsyncSession,
    customer_user: User,
    customer_headers: dict,
):
    """E2E Flow: Normal Low-Risk transfer (< 30) is automatically approved and persisted."""
    acc_sender = await _create_test_account(db_session, customer_user, balance=Decimal("1500.00"))
    acc_receiver = await _create_test_account(db_session, customer_user, balance=Decimal("200.00"), account_type=AccountType.SAVINGS)

    # 1. Post Transfer via API
    transfer_payload = {
        "SenderAccountID": str(acc_sender.AccountID),
        "ReceiverAccountID": str(acc_receiver.AccountID),
        "Amount": 45.00,
        "Description": "Weekly groceries",
    }
    resp = await client.post(
        "/api/v1/transactions/transfer",
        json=transfer_payload,
        headers={**customer_headers, "X-Device-Fingerprint": "known_device_browser_123"},
    )
    assert resp.status_code == 201
    tx_data = resp.json()
    tx_id = uuid.UUID(tx_data["TransactionID"])

    # 2. Consume Event via Async Streaming Consumer (simulating worker picking up event from queue)
    event_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "TRANSACTION_CREATED",
        "transaction_id": str(tx_id),
        "account_id": str(acc_sender.AccountID),
        "user_id": str(customer_user.UserID),
        "amount": 45.0,
        "sender_account": str(acc_sender.AccountID),
        "receiver_account": str(acc_receiver.AccountID),
        "device_fingerprint": "known_device_browser_123",
    }
    alert = await process_transaction_event(event_payload, db=db_session)

    assert alert is not None
    assert alert.AlertLevel == AlertLevel.LOW
    assert alert.RiskScore < 30.0
    assert alert.Decision == AlertDecision.APPROVED

    # 3. Check DB Transaction Status updated to APPROVED
    tx_stmt = select(Transaction).where(Transaction.TransactionID == tx_id)
    tx_record = (await db_session.execute(tx_stmt)).scalar_one()
    assert tx_record.Status == TransactionStatus.APPROVED

    # 4. Check Risk Score API
    risk_resp = await client.get(
        f"/api/v1/transactions/{tx_id}/risk-score",
        headers=customer_headers,
    )
    assert risk_resp.status_code == 200
    risk_data = risk_resp.json()
    assert risk_data["Decision"] == "Approved"
    assert risk_data["AlertLevel"] == "Low"


@pytest.mark.asyncio
async def test_e2e_medium_risk_step_up_otp_flow(
    client: AsyncClient,
    db_session: AsyncSession,
    customer_user: User,
    customer_headers: dict,
):
    """E2E Flow: Medium-risk transfer (30-70) triggers Step-Up OTP challenge.

    User verifies OTP to release transfer to APPROVED.
    """
    acc_sender = await _create_test_account(db_session, customer_user, balance=Decimal("5000.00"))
    acc_receiver = await _create_test_account(db_session, customer_user, balance=Decimal("100.00"), account_type=AccountType.SAVINGS)

    # 1. Post Transfer via API
    resp = await client.post(
        "/api/v1/transactions/transfer",
        json={
            "SenderAccountID": str(acc_sender.AccountID),
            "ReceiverAccountID": str(acc_receiver.AccountID),
            "Amount": 1200.00,
            "Description": "New laptop purchase",
        },
        headers={**customer_headers, "X-Device-Fingerprint": "unrecognized_device_laptop"},
    )
    assert resp.status_code == 201
    tx_id = uuid.UUID(resp.json()["TransactionID"])

    # 2. Simulate streaming worker applying mitigation with Medium Risk
    mitigation_res = await MitigationService.apply_mitigation(
        db=db_session,
        transaction_id=tx_id,
        account_id=acc_sender.AccountID,
        amount=1200.00,
        decision=AlertDecision.STEP_UP_REQUIRED,
        alert_level=AlertLevel.MEDIUM,
        risk_score=52.5,
        explanations={"reason": "Transfer from new device; elevated amount."},
    )
    # Persist FraudAlert record
    alert = FraudAlert(
        TransactionID=tx_id,
        RiskScore=52.5,
        AlertLevel=AlertLevel.MEDIUM,
        Decision=AlertDecision.STEP_UP_REQUIRED,
        Explanations={"reason": "Transfer from new device; elevated amount."},
    )
    db_session.add(alert)
    await db_session.commit()

    assert mitigation_res["action"] == "STEP_UP_CHALLENGE"
    assert mitigation_res["target_status"] == TransactionStatus.PENDING
    otp_code = mitigation_res["otp_code"]
    assert otp_code is not None

    # Verify transaction is held in PENDING state
    tx_stmt = select(Transaction).where(Transaction.TransactionID == tx_id)
    tx_record = (await db_session.execute(tx_stmt)).scalar_one()
    assert tx_record.Status == TransactionStatus.PENDING

    # 3. Invalid OTP attempt fails
    bad_otp_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/verify-otp",
        json={"otp_code": "000000"},
        headers=customer_headers,
    )
    assert bad_otp_resp.status_code == 400
    assert "Invalid or expired OTP" in bad_otp_resp.json()["detail"]

    # 4. Valid OTP verification releases the transfer
    verify_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/verify-otp",
        json={"otp_code": otp_code},
        headers=customer_headers,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["Status"] == "Approved"

    # 5. Database confirmation
    await db_session.refresh(tx_record)
    assert tx_record.Status == TransactionStatus.APPROVED

    await db_session.refresh(alert)
    assert alert.Decision == AlertDecision.APPROVED
    assert "Customer verified identity via Step-Up OTP" in alert.Explanations["step_up_resolution"]


@pytest.mark.asyncio
async def test_e2e_high_risk_auto_block_and_refund(
    client: AsyncClient,
    db_session: AsyncSession,
    customer_user: User,
    customer_headers: dict,
):
    """E2E Flow: High-risk anomaly (> 70) is auto-blocked, sender refunded, and audit logged."""
    initial_balance = Decimal("25000.00")
    transfer_amount = Decimal("15000.00")
    acc_sender = await _create_test_account(db_session, customer_user, balance=initial_balance)
    acc_receiver = await _create_test_account(db_session, customer_user, balance=Decimal("500.00"), account_type=AccountType.BUSINESS)

    # 1. Post Transfer via API (balance drops to 10,000)
    resp = await client.post(
        "/api/v1/transactions/transfer",
        json={
            "SenderAccountID": str(acc_sender.AccountID),
            "ReceiverAccountID": str(acc_receiver.AccountID),
            "Amount": float(transfer_amount),
            "Description": "Emergency wire transfer overseas",
        },
        headers={
            **customer_headers,
            "X-Forwarded-For": "203.0.113.88",
            "X-Device-Fingerprint": "completely_foreign_fp_8899",
        },
    )
    assert resp.status_code == 201
    tx_id = uuid.UUID(resp.json()["TransactionID"])

    # Verify balance was debited before scoring
    await db_session.refresh(acc_sender)
    assert acc_sender.Balance == initial_balance - transfer_amount

    # 2. Worker executes mitigation with High Risk (>70)
    mitigation_res = await MitigationService.apply_mitigation(
        db=db_session,
        transaction_id=tx_id,
        account_id=acc_sender.AccountID,
        amount=float(transfer_amount),
        decision=AlertDecision.BLOCKED,
        alert_level=AlertLevel.HIGH,
        risk_score=94.5,
        explanations={
            "amount_z_score": "Spike of 8.4x standard deviation",
            "geo_velocity": "Impossible velocity: 1400 km/h",
        },
    )
    # Persist FraudAlert
    alert = FraudAlert(
        TransactionID=tx_id,
        RiskScore=94.5,
        AlertLevel=AlertLevel.HIGH,
        Decision=AlertDecision.BLOCKED,
        Explanations={"amount_z_score": "Spike of 8.4x standard deviation"},
    )
    db_session.add(alert)
    await db_session.commit()

    assert mitigation_res["action"] == "AUTO_BLOCK_AND_REFUND"
    assert mitigation_res["target_status"] == TransactionStatus.BLOCKED
    assert mitigation_res["refund_processed"] is True

    # 3. Verify sender balance was safely restored!
    await db_session.refresh(acc_sender)
    assert acc_sender.Balance == initial_balance

    # 4. Verify transaction status is BLOCKED in DB
    tx_stmt = select(Transaction).where(Transaction.TransactionID == tx_id)
    tx_record = (await db_session.execute(tx_stmt)).scalar_one()
    assert tx_record.Status == TransactionStatus.BLOCKED

    # 5. Verify attempting OTP on BLOCKED transaction fails
    otp_fail_resp = await client.post(
        f"/api/v1/transactions/{tx_id}/verify-otp",
        json={"otp_code": "123456"},
        headers=customer_headers,
    )
    assert otp_fail_resp.status_code == 400
    assert "blocked" in otp_fail_resp.json()["detail"].lower()

    # 6. Verify audit trail has recorded the block
    audit_trail = MitigationService.get_audit_trail()
    assert len(audit_trail) > 0
    latest_audit = audit_trail[-1]
    assert latest_audit["event"] == "HIGH_RISK_TRANSACTION_BLOCKED"
    assert latest_audit["transaction_id"] == str(tx_id)
    assert latest_audit["refunded"] is True


# ==============================================================================
# 2. BANK-31 to 34: ADMIN DASHBOARD MONITORING & METRICS
# ==============================================================================

@pytest.mark.asyncio
async def test_admin_dashboard_transactions_feed(
    client: AsyncClient,
    admin_headers: dict,
    customer_headers: dict,
):
    """Admin feed returns transactions; Customers receive 403 Forbidden."""
    # Customer forbidden
    resp_cust = await client.get("/api/v1/admin/dashboard/transactions", headers=customer_headers)
    assert resp_cust.status_code == 403

    # Admin authorized
    resp_admin = await client.get("/api/v1/admin/dashboard/transactions?limit=10", headers=admin_headers)
    assert resp_admin.status_code == 200
    assert isinstance(resp_admin.json(), list)


@pytest.mark.asyncio
async def test_admin_dashboard_alerts_queue_with_shap(
    client: AsyncClient,
    db_session: AsyncSession,
    customer_user: User,
    admin_headers: dict,
    customer_headers: dict,
):
    """Admin alert queue displays active high/medium alerts with SHAP explanation breakdowns."""
    # Customer forbidden
    resp_cust = await client.get("/api/v1/admin/dashboard/alerts", headers=customer_headers)
    assert resp_cust.status_code == 403

    # Seed an alert with SHAP explanations
    acc = await _create_test_account(db_session, customer_user)
    tx = Transaction(
        AccountID=acc.AccountID,
        Amount=Decimal("8500.00"),
        TransactionType=TransactionType.TRANSFER,
        SenderAccount=str(acc.AccountID),
        ReceiverAccount=str(uuid.uuid4()),
        Status=TransactionStatus.BLOCKED,
    )
    db_session.add(tx)
    await db_session.flush()

    alert = FraudAlert(
        TransactionID=tx.TransactionID,
        RiskScore=88.0,
        AlertLevel=AlertLevel.HIGH,
        Decision=AlertDecision.BLOCKED,
        Explanations={
            "top_risk_factors": [
                "Unusual transaction amount ($8,500.00)",
                "Unrecognized hardware device fingerprint",
            ]
        },
    )
    db_session.add(alert)
    await db_session.commit()

    # Admin queries alerts queue
    resp_admin = await client.get("/api/v1/admin/dashboard/alerts?limit=5", headers=admin_headers)
    assert resp_admin.status_code == 200
    alerts = resp_admin.json()
    assert len(alerts) >= 1
    found = any(a["TransactionID"] == str(tx.TransactionID) for a in alerts)
    assert found is True


@pytest.mark.asyncio
async def test_admin_dashboard_live_metrics(
    client: AsyncClient,
    admin_headers: dict,
    customer_headers: dict,
):
    """Admin dashboard live model metrics (Precision, Recall, F1, FPR)."""
    # Customer forbidden
    resp_cust = await client.get("/api/v1/admin/dashboard/metrics", headers=customer_headers)
    assert resp_cust.status_code == 403

    # Admin authorized
    resp_admin = await client.get("/api/v1/admin/dashboard/metrics", headers=admin_headers)
    assert resp_admin.status_code == 200
    metrics = resp_admin.json()

    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0
    assert 0.0 <= metrics["f1_score"] <= 1.0
    assert 0.0 <= metrics["false_positive_rate"] <= 1.0
    assert "total_transactions_analyzed" in metrics
    assert "total_alerts_generated" in metrics


@pytest.mark.asyncio
async def test_admin_dashboard_audit_trail_access(
    client: AsyncClient,
    admin_headers: dict,
    customer_headers: dict,
):
    """Admin can query audit logs for high-risk automated mitigation actions."""
    # Customer forbidden
    resp_cust = await client.get("/api/v1/admin/dashboard/audit-trail", headers=customer_headers)
    assert resp_cust.status_code == 403

    # Admin authorized
    resp_admin = await client.get("/api/v1/admin/dashboard/audit-trail", headers=admin_headers)
    assert resp_admin.status_code == 200
    assert isinstance(resp_admin.json(), list)

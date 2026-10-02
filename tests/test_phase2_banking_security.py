import asyncio
import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.security import create_access_token, decode_token
from app.models.account import Account, AccountType, KYCStatus
from app.models.auth_token import AuthToken
from app.models.device import Device
from app.models.session import Session
from app.models.transaction import Transaction
from app.models.user import User, UserRole


# ==============================================================================
# 1. BANK-8: ACCOUNT MANAGEMENT ENDPOINTS & OWNERSHIP ENFORCEMENT
# ==============================================================================

@pytest.mark.asyncio
async def test_create_account_with_kyc(client: AsyncClient, customer_headers: dict):
    """Test account creation with specified KYC status and initial deposit."""
    payload = {
        "AccountType": "Checking",
        "InitialDeposit": "2500.50",
        "KYCStatus": "Verified",
    }
    response = await client.post("/accounts", json=payload, headers=customer_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["AccountType"] == "Checking"
    assert data["KYCStatus"] == "Verified"
    assert float(data["Balance"]) == 2500.50
    assert "AccountID" in data


@pytest.mark.asyncio
async def test_get_account_by_id_strict_ownership(
    client: AsyncClient,
    customer_headers: dict,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """Test GET /accounts/{id} strictly enforces account ownership."""
    # 1. Customer creates an account
    create_res = await client.post(
        "/accounts",
        json={"AccountType": "Savings", "InitialDeposit": "1500.00"},
        headers=customer_headers,
    )
    acc_id = create_res.json()["AccountID"]

    # 2. Account owner queries their account -> 200 OK
    owner_res = await client.get(f"/accounts/{acc_id}", headers=customer_headers)
    assert owner_res.status_code == 200
    assert owner_res.json()["AccountID"] == acc_id
    assert float(owner_res.json()["Balance"]) == 1500.00

    # 3. Create a second customer (unauthorized actor)
    other_user = User(
        UserID=uuid.uuid4(),
        Email="other_customer@bank.com",
        PasswordHash="hashed",
        Role=UserRole.CUSTOMER,
    )
    db_session.add(other_user)
    await db_session.commit()
    other_token = create_access_token(subject=other_user.UserID, role=other_user.Role.value)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # 4. Unauthorized customer attempts to view the account -> 403 Forbidden
    unauthorized_res = await client.get(f"/accounts/{acc_id}", headers=other_headers)
    assert unauthorized_res.status_code == 403
    assert "Access denied: You do not own this account" in unauthorized_res.json()["detail"]

    # 5. Bank Admin queries the account -> 200 OK (elevated oversight)
    admin_res = await client.get(f"/accounts/{acc_id}", headers=admin_headers)
    assert admin_res.status_code == 200
    assert admin_res.json()["AccountID"] == acc_id


@pytest.mark.asyncio
async def test_get_account_by_id_not_found(client: AsyncClient, customer_headers: dict):
    """Test querying a non-existent account ID returns 404 Not Found."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/accounts/{fake_id}", headers=customer_headers)
    assert response.status_code == 404
    assert "Account not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_account_history_pagination(client: AsyncClient, customer_headers: dict):
    """Test paginated account transaction history."""
    acc_res = await client.post(
        "/accounts",
        json={"AccountType": "Checking", "InitialDeposit": "5000.00"},
        headers=customer_headers,
    )
    acc_id = acc_res.json()["AccountID"]

    history_res = await client.get(f"/accounts/{acc_id}/history?page=1&page_size=10", headers=customer_headers)
    assert history_res.status_code == 200
    data = history_res.json()
    assert data["account_id"] == acc_id
    assert float(data["balance"]) == 5000.00
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert isinstance(data["transactions"], list)


# ==============================================================================
# 2. BANK-9: ATOMIC FUND TRANSFERS WITH DATABASE ROW-LEVEL LOCKING
# ==============================================================================

@pytest.mark.asyncio
async def test_atomic_transfer_success(client: AsyncClient, customer_headers: dict):
    """Test atomic transfer balances update correctly and record immutable transaction."""
    # Create sender ($1000) and receiver ($200) accounts
    sender_acc = (
        await client.post("/accounts", json={"AccountType": "Checking", "InitialDeposit": "1000.00"}, headers=customer_headers)
    ).json()
    receiver_acc = (
        await client.post("/accounts", json={"AccountType": "Savings", "InitialDeposit": "200.00"}, headers=customer_headers)
    ).json()

    transfer_payload = {
        "SenderAccountID": sender_acc["AccountID"],
        "ReceiverAccountID": receiver_acc["AccountID"],
        "Amount": "350.00",
        "Description": "Rent payment",
    }
    tx_res = await client.post("/transactions/transfer", json=transfer_payload, headers=customer_headers)
    assert tx_res.status_code == 201
    tx_data = tx_res.json()
    assert float(tx_data["Amount"]) == 350.00
    assert tx_data["SenderAccount"] == sender_acc["AccountID"]
    assert tx_data["ReceiverAccount"] == receiver_acc["AccountID"]
    assert tx_data["Status"] in ["Pending", "Approved"]

    # Verify atomic balances after transfer
    sender_updated = (await client.get(f"/accounts/{sender_acc['AccountID']}", headers=customer_headers)).json()
    receiver_updated = (await client.get(f"/accounts/{receiver_acc['AccountID']}", headers=customer_headers)).json()
    assert float(sender_updated["Balance"]) == 650.00
    assert float(receiver_updated["Balance"]) == 550.00


@pytest.mark.asyncio
async def test_transfer_insufficient_funds_rejected(client: AsyncClient, customer_headers: dict):
    """Test transfer fails safely if balance is insufficient, balances untouched."""
    sender_acc = (
        await client.post("/accounts", json={"AccountType": "Checking", "InitialDeposit": "100.00"}, headers=customer_headers)
    ).json()
    receiver_acc = (
        await client.post("/accounts", json={"AccountType": "Savings", "InitialDeposit": "50.00"}, headers=customer_headers)
    ).json()

    transfer_payload = {
        "SenderAccountID": sender_acc["AccountID"],
        "ReceiverAccountID": receiver_acc["AccountID"],
        "Amount": "500.00",  # Exceeds 100.00
    }
    tx_res = await client.post("/transactions/transfer", json=transfer_payload, headers=customer_headers)
    assert tx_res.status_code == 400
    assert "Insufficient funds" in tx_res.json()["detail"]

    # Verify balances remained unchanged
    sender_check = (await client.get(f"/accounts/{sender_acc['AccountID']}", headers=customer_headers)).json()
    assert float(sender_check["Balance"]) == 100.00


@pytest.mark.asyncio
async def test_transfer_self_account_rejected(client: AsyncClient, customer_headers: dict):
    """Test transferring to the exact same account is rejected."""
    sender_acc = (
        await client.post("/accounts", json={"AccountType": "Checking", "InitialDeposit": "500.00"}, headers=customer_headers)
    ).json()

    transfer_payload = {
        "SenderAccountID": sender_acc["AccountID"],
        "ReceiverAccountID": sender_acc["AccountID"],
        "Amount": "50.00",
    }
    tx_res = await client.post("/transactions/transfer", json=transfer_payload, headers=customer_headers)
    assert tx_res.status_code == 400
    assert "different" in tx_res.json()["detail"]


@pytest.mark.asyncio
async def test_transfer_unowned_source_account_rejected(
    client: AsyncClient,
    customer_headers: dict,
    db_session: AsyncSession,
):
    """Test user cannot initiate a transfer debiting someone else's account."""
    # Another user's account
    other_user = User(UserID=uuid.uuid4(), Email="victim@bank.com", PasswordHash="h", Role=UserRole.CUSTOMER)
    db_session.add(other_user)
    await db_session.commit()
    other_token = create_access_token(subject=other_user.UserID, role=other_user.Role.value)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    victim_acc = (
        await client.post("/accounts", json={"AccountType": "Checking", "InitialDeposit": "10000.00"}, headers=other_headers)
    ).json()

    attacker_acc = (
        await client.post("/accounts", json={"AccountType": "Savings", "InitialDeposit": "10.00"}, headers=customer_headers)
    ).json()

    # Customer attempts to transfer from victim's account to attacker's account
    fraud_payload = {
        "SenderAccountID": victim_acc["AccountID"],
        "ReceiverAccountID": attacker_acc["AccountID"],
        "Amount": "1000.00",
    }
    fraud_res = await client.post("/transactions/transfer", json=fraud_payload, headers=customer_headers)
    assert fraud_res.status_code == 403
    assert "Unauthorized: You do not own the source account" in fraud_res.json()["detail"]


# ==============================================================================
# 3. BANK-13: DEVICE FINGERPRINT, IP, AND GEOLOCATION SESSION TRACKING
# ==============================================================================

@pytest.mark.asyncio
async def test_device_and_session_auto_population(client: AsyncClient, db_session: AsyncSession):
    """Test that /auth/login captures fingerprint, IP, and geolocation, populating DEVICE & SESSION records."""
    email = "device_track_user@bank.com"
    password = "TrackPassword123!"
    reg_res = await client.post(
        "/auth/register",
        json={"Email": email, "Password": password, "Role": "Customer"},
    )
    user_id = uuid.UUID(reg_res.json()["UserID"])

    # Login with custom device fingerprint and forwarded IP headers
    login_headers = {
        "X-Forwarded-For": "198.51.100.88",
        "X-Device-Fingerprint": "canvas-fp-unique-998877",
        "X-Location": "London, England, UK",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
    }
    login_res = await client.post(
        "/auth/login",
        json={"Email": email, "Password": password, "DeviceType": "iPhone 14"},
        headers=login_headers,
    )
    assert login_res.status_code == 200

    # 1. Verify DEVICE record in database
    dev_stmt = select(Device).where(Device.UserID == user_id)
    device = (await db_session.execute(dev_stmt)).scalar_one_or_none()
    assert device is not None
    assert device.DeviceFingerprint == "canvas-fp-unique-998877"
    assert device.DeviceType == "iPhone 14"
    assert device.LastUsedIP == "198.51.100.88"

    # 2. Verify SESSION record in database
    sess_stmt = select(Session).where(Session.UserID == user_id, Session.IsActive == True)
    session_record = (await db_session.execute(sess_stmt)).scalar_one_or_none()
    assert session_record is not None
    assert session_record.DeviceID == device.DeviceID
    assert session_record.IPAddress == "198.51.100.88"
    assert session_record.Location == "London, England, UK"
    assert session_record.IsActive is True


# ==============================================================================
# 4. BANK-14: TOKEN REVOCATION (LOGOUT & JTI NONCE BLACKLISTING)
# ==============================================================================

@pytest.mark.asyncio
async def test_token_revocation_on_logout(client: AsyncClient, db_session: AsyncSession):
    """Test that POST /auth/logout immediately revokes the JWT access token (via JTI) and the DB refresh token."""
    email = "revoketest@bank.com"
    password = "RevokePassword123!"
    await client.post("/auth/register", json={"Email": email, "Password": password, "Role": "Customer"})

    login_res = await client.post("/auth/login", json={"Email": email, "Password": password})
    tokens = login_res.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    auth_header = {"Authorization": f"Bearer {access_token}"}

    # Verify access token works initially
    me_before = await client.get("/auth/me", headers=auth_header)
    assert me_before.status_code == 200

    # Perform logout
    logout_res = await client.post("/auth/logout", json={"refresh_token": refresh_token}, headers=auth_header)
    assert logout_res.status_code == 200
    assert "Successfully logged out" in logout_res.json()["message"]

    # 1. Immediate rejection of the revoked access token (JTI blacklist check)
    me_after = await client.get("/auth/me", headers=auth_header)
    assert me_after.status_code == 401
    assert "Token has been revoked" in me_after.json()["detail"]

    # 2. Immediate rejection of refresh token rotation
    refresh_attempt = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_attempt.status_code == 401
    assert "revoked or has expired" in refresh_attempt.json()["detail"]

    # 3. Database refresh token flag is marked IsRevoked = True
    token_record = (
        await db_session.execute(select(AuthToken).where(AuthToken.RefreshToken == refresh_token))
    ).scalar_one_or_none()
    assert token_record is not None
    assert token_record.IsRevoked is True


# ==============================================================================
# 5. BANK-11: REDIS RATE LIMITING (5 REQ/MIN ON /auth/login)
# ==============================================================================

@pytest.mark.asyncio
async def test_login_rate_limiting_exceeded(client: AsyncClient):
    """Test that the 5 req/min rate limit on /auth/login returns 429 Too Many Requests on the 6th call."""
    # Temporarily enable the limiter specifically for this rate limit test
    limiter.enabled = True
    try:
        email = "ratelimit_user@bank.com"
        password = "Password123!"
        await client.post("/auth/register", json={"Email": email, "Password": password, "Role": "Customer"})

        # Send 5 requests from the same test client IP (within 1 minute)
        for i in range(5):
            res = await client.post(
                "/auth/login",
                json={"Email": email, "Password": password},
                headers={"X-Forwarded-For": "10.99.88.77"},
            )
            assert res.status_code == 200, f"Request {i+1} failed unexpectedly with status {res.status_code}"

        # The 6th request from the same IP must be throttled with HTTP 429
        throttled_res = await client.post(
            "/auth/login",
            json={"Email": email, "Password": password},
            headers={"X-Forwarded-For": "10.99.88.77"},
        )
        assert throttled_res.status_code == 429
        assert "Too Many Requests" in throttled_res.text or "Rate limit exceeded" in throttled_res.text
    finally:
        # Restore disabled state for remaining tests
        limiter.enabled = False

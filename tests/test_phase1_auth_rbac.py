import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, decode_token, verify_password
from app.models.auth_token import AuthToken
from app.models.device import Device
from app.models.session import Session
from app.models.user import User, UserRole


# ==============================================================================
# 1. USER REGISTRATION TESTS (Argon2/bcrypt hashing, validation, uniqueness)
# ==============================================================================

@pytest.mark.asyncio
async def test_user_registration_customer(client: AsyncClient, db_session: AsyncSession):
    """Test successful customer registration with password hashing."""
    payload = {
        "Email": "alice.customer@securebank.com",
        "Password": "StrongPassword123!",
        "Role": "Customer",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["Email"] == "alice.customer@securebank.com"
    assert data["Role"] == "Customer"
    assert "UserID" in data
    assert "Password" not in data
    assert "PasswordHash" not in data

    # Verify password in DB is cryptographically hashed with Argon2/bcrypt
    user_id = uuid.UUID(data["UserID"])
    user = (await db_session.execute(select(User).where(User.UserID == user_id))).scalar_one()
    assert user.PasswordHash != "StrongPassword123!"
    assert verify_password("StrongPassword123!", user.PasswordHash) is True


@pytest.mark.asyncio
async def test_user_registration_merchant_and_admin(client: AsyncClient):
    """Test registration with Merchant and Bank Admin roles."""
    # Merchant
    res_m = await client.post(
        "/auth/register",
        json={"Email": "merchant@shop.com", "Password": "MerchantPassword123!", "Role": "Merchant"},
    )
    assert res_m.status_code == 201
    assert res_m.json()["Role"] == "Merchant"

    # Bank Admin
    res_a = await client.post(
        "/auth/register",
        json={"Email": "compliance@bank.com", "Password": "AdminPassword123!", "Role": "Bank Admin"},
    )
    assert res_a.status_code == 201
    assert res_a.json()["Role"] == "Bank Admin"


@pytest.mark.asyncio
async def test_user_registration_input_validation(client: AsyncClient):
    """Test input validation for invalid email and weak/short password."""
    # Invalid email format
    res_bad_email = await client.post(
        "/auth/register",
        json={"Email": "not-an-email", "Password": "ValidPassword123!", "Role": "Customer"},
    )
    assert res_bad_email.status_code == 422

    # Password shorter than 8 characters
    res_short_pass = await client.post(
        "/auth/register",
        json={"Email": "user@example.com", "Password": "short", "Role": "Customer"},
    )
    assert res_short_pass.status_code == 422


@pytest.mark.asyncio
async def test_user_registration_duplicate_email_fails(client: AsyncClient):
    """Test that registering an already existing email returns 400 Bad Request."""
    payload = {
        "Email": "duplicate@example.com",
        "Password": "Password123!",
        "Role": "Customer",
    }
    res1 = await client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


# ==============================================================================
# 2. USER LOGIN TESTS (JWT 15m expiration, Device & Session recording, Refresh Token)
# ==============================================================================

@pytest.mark.asyncio
async def test_user_login_valid_credentials(client: AsyncClient, db_session: AsyncSession):
    """Test valid login issues 15-min JWT, saves Refresh Token, and records Device/Session."""
    email = "login_success@example.com"
    password = "CorrectPassword123!"
    await client.post(
        "/auth/register",
        json={"Email": email, "Password": password, "Role": "Customer"},
    )

    login_payload = {
        "Email": email,
        "Password": password,
        "DeviceFingerprint": "device-canvas-fingerprint-abc",
        "DeviceType": "Mobile iOS",
    }
    response = await client.post(
        "/auth/login",
        json=login_payload,
        headers={"X-Forwarded-For": "198.51.100.42", "User-Agent": "TestMobileApp/1.0"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 15 * 60  # 15 minutes

    # Inspect Access Token claims
    payload = decode_token(data["access_token"])
    assert payload["role"] == "Customer"
    assert payload["type"] == "access"
    assert "jti" in payload
    assert "exp" in payload

    # Verify expiration claim is approximately 15 minutes from now
    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    expected_exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    time_diff = abs((exp_time - expected_exp).total_seconds())
    assert time_diff < 10.0  # within 10 seconds tolerance

    # Verify Refresh Token is saved in PostgreSQL database
    user_id = uuid.UUID(payload["sub"])
    token_stmt = select(AuthToken).where(AuthToken.RefreshToken == data["refresh_token"])
    token_record = (await db_session.execute(token_stmt)).scalar_one_or_none()
    assert token_record is not None
    assert token_record.UserID == user_id
    assert token_record.IsRevoked is False
    expires_at = (
        token_record.ExpiresAt.replace(tzinfo=timezone.utc)
        if token_record.ExpiresAt.tzinfo is None
        else token_record.ExpiresAt
    )
    assert expires_at > datetime.now(timezone.utc)

    # Verify DEVICE record was created
    device_stmt = select(Device).where(Device.UserID == user_id)
    device_record = (await db_session.execute(device_stmt)).scalar_one_or_none()
    assert device_record is not None
    assert device_record.DeviceFingerprint == "device-canvas-fingerprint-abc"
    assert device_record.DeviceType == "Mobile iOS"

    # Verify SESSION record was created and active
    session_stmt = select(Session).where(Session.UserID == user_id, Session.IsActive == True)
    session_record = (await db_session.execute(session_stmt)).scalar_one_or_none()
    assert session_record is not None
    assert session_record.DeviceID == device_record.DeviceID
    assert session_record.IPAddress == "198.51.100.42"


@pytest.mark.asyncio
async def test_user_login_invalid_password(client: AsyncClient):
    """Test login with wrong password returns 401 Unauthorized."""
    email = "wrong_pass_user@example.com"
    await client.post(
        "/auth/register",
        json={"Email": email, "Password": "CorrectPassword123!", "Role": "Customer"},
    )

    response = await client.post(
        "/auth/login",
        json={"Email": email, "Password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_user_login_nonexistent_user(client: AsyncClient):
    """Test login with non-existent email returns 401 Unauthorized."""
    response = await client.post(
        "/auth/login",
        json={"Email": "nonexistent@example.com", "Password": "SomePassword123!"},
    )
    assert response.status_code == 401


# ==============================================================================
# 3. TOKEN EXPIRATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_access_token_expiration(client: AsyncClient, customer_user: User):
    """Test that an expired JWT access token is rejected with 401 Unauthorized."""
    # Craft an already expired token (expired 5 minutes ago)
    expired_token = create_access_token(
        subject=customer_user.UserID,
        role=customer_user.Role.value,
        expires_delta=timedelta(minutes=-5),
    )

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_token_expiration(client: AsyncClient, customer_user: User, db_session: AsyncSession):
    """Test that an expired refresh token in DB cannot be used to rotate access tokens."""
    # Insert an expired refresh token
    expired_rf = "expired-refresh-token-uuid-12345"
    db_token = AuthToken(
        UserID=customer_user.UserID,
        RefreshToken=expired_rf,
        IsRevoked=False,
        ExpiresAt=datetime.now(timezone.utc) - timedelta(days=1),  # Expired yesterday
    )
    db_session.add(db_token)
    await db_session.commit()

    response = await client.post("/auth/refresh", json={"refresh_token": expired_rf})
    assert response.status_code == 401
    assert "revoked or has expired" in response.json()["detail"]


# ==============================================================================
# 4. ROLE-BASED ACCESS CONTROL (RBAC) & UNAUTHORIZED ACCESS ATTEMPTS
# ==============================================================================

@pytest.mark.asyncio
async def test_unauthorized_access_without_token(client: AsyncClient):
    """Test that accessing protected endpoints without an Authorization header returns 401."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rbac_customer_access(client: AsyncClient, customer_headers: dict):
    """Test Customer can access customer route, but is blocked from admin route."""
    # Customer accessing /auth/customer-route -> Allowed (200)
    res_cust = await client.get("/auth/customer-route", headers=customer_headers)
    assert res_cust.status_code == 200
    assert res_cust.json()["role"] == "Customer"

    # Customer accessing /auth/admin-route -> Blocked (403 Forbidden)
    res_admin = await client.get("/auth/admin-route", headers=customer_headers)
    assert res_admin.status_code == 403
    assert "Operation not permitted" in res_admin.json()["detail"]

    # Customer accessing /alerts -> Blocked (403 Forbidden)
    res_alerts = await client.get("/alerts", headers=customer_headers)
    assert res_alerts.status_code == 403


@pytest.mark.asyncio
async def test_rbac_merchant_access(client: AsyncClient, db_session: AsyncSession):
    """Test Merchant can access merchant route, but is blocked from admin route."""
    merchant = User(
        UserID=uuid.uuid4(),
        Email="merchant_test@store.com",
        PasswordHash="hashed_pw",
        Role=UserRole.MERCHANT,
    )
    db_session.add(merchant)
    await db_session.commit()

    token = create_access_token(subject=merchant.UserID, role=merchant.Role.value)
    merchant_headers = {"Authorization": f"Bearer {token}"}

    # Merchant accessing /auth/merchant-route -> Allowed (200)
    res_merch = await client.get("/auth/merchant-route", headers=merchant_headers)
    assert res_merch.status_code == 200
    assert res_merch.json()["role"] == "Merchant"

    # Merchant accessing /auth/admin-route -> Blocked (403 Forbidden)
    res_admin = await client.get("/auth/admin-route", headers=merchant_headers)
    assert res_admin.status_code == 403


@pytest.mark.asyncio
async def test_rbac_bank_admin_access(client: AsyncClient, admin_headers: dict):
    """Test Bank Admin has elevated access to admin, merchant, and customer routes."""
    # Bank Admin accessing /auth/admin-route -> Allowed (200)
    res_admin = await client.get("/auth/admin-route", headers=admin_headers)
    assert res_admin.status_code == 200
    assert res_admin.json()["role"] == "Bank Admin"

    # Bank Admin accessing /auth/customer-route -> Allowed (200)
    res_cust = await client.get("/auth/customer-route", headers=admin_headers)
    assert res_cust.status_code == 200

    # Bank Admin accessing /auth/merchant-route -> Allowed (200)
    res_merch = await client.get("/auth/merchant-route", headers=admin_headers)
    assert res_merch.status_code == 200

    # Bank Admin accessing /alerts -> Allowed (200)
    res_alerts = await client.get("/alerts", headers=admin_headers)
    assert res_alerts.status_code == 200

import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_owasp_unauthenticated_request_rejected(client: AsyncClient):
    """OWASP API2: Broken Authentication - Unauthenticated access rejected with 401."""
    response = await client.get("/accounts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_owasp_broken_object_level_authorization(client: AsyncClient, customer_headers: dict, db_session):
    """OWASP API1: BOLA/IDOR - User cannot access another user's account history."""
    # Create another user and account
    other_user = User(
        UserID=uuid.uuid4(),
        Email="otheruser@example.com",
        PasswordHash="hashed",
        Role=UserRole.CUSTOMER,
    )
    db_session.add(other_user)
    await db_session.commit()

    other_token = create_access_token(subject=other_user.UserID, role=other_user.Role.value)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # Other user creates an account
    acc_res = await client.post(
        "/accounts",
        json={"AccountType": "Checking", "InitialDeposit": "5000.00"},
        headers=other_headers,
    )
    other_account_id = acc_res.json()["AccountID"]

    # Customer 1 attempts to query other user's account history
    bola_attempt = await client.get(
        f"/accounts/{other_account_id}/history",
        headers=customer_headers,
    )
    assert bola_attempt.status_code == 403
    assert "Access denied" in bola_attempt.json()["detail"]


@pytest.mark.asyncio
async def test_owasp_function_level_authorization_admin_protection(
    client: AsyncClient,
    customer_headers: dict,
    admin_headers: dict,
):
    """OWASP API5: Broken Function Level Authorization - Customer cannot access /alerts."""
    # Customer tries to access Admin alerts endpoint -> 403 Forbidden
    cust_res = await client.get("/alerts", headers=customer_headers)
    assert cust_res.status_code == 403

    # Bank Admin accesses /alerts -> 200 OK
    admin_res = await client.get("/alerts", headers=admin_headers)
    assert admin_res.status_code == 200


@pytest.mark.asyncio
async def test_owasp_sqli_payload_sanitized(client: AsyncClient):
    """OWASP API8: Security Misconfiguration / Injection - SQL Injection payload rejected safely."""
    sqli_payload = {
        "Email": "admin' OR '1'='1' --",
        "Password": "Password123!",
        "Role": "Customer",
    }
    # Fast-fails Pydantic EmailStr validation or parameterized query
    res = await client.post("/auth/register", json=sqli_payload)
    assert res.status_code == 422  # Pydantic EmailStr validation failure

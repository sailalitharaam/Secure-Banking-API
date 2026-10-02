import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    payload = {
        "Email": "newuser@example.com",
        "Password": "SecurePassword123!",
        "Role": "Customer",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["Email"] == "newuser@example.com"
    assert data["Role"] == "Customer"
    assert "UserID" in data


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(client: AsyncClient):
    payload = {
        "Email": "dupuser@example.com",
        "Password": "SecurePassword123!",
        "Role": "Customer",
    }
    # First registration
    res1 = await client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with duplicate email
    res2 = await client.post("/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_login_success_and_token_generation(client: AsyncClient):
    # Register first
    email = "logintest@example.com"
    password = "CorrectPassword123!"
    await client.post(
        "/auth/register",
        json={"Email": email, "Password": password, "Role": "Customer"},
    )

    # Login
    login_payload = {
        "Email": email,
        "Password": password,
        "DeviceFingerprint": "test-device-fp-999",
        "DeviceType": "Test Browser",
    }
    response = await client.post("/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password_fails(client: AsyncClient):
    email = "wrongpass@example.com"
    await client.post(
        "/auth/register",
        json={"Email": email, "Password": "RealPassword123!", "Role": "Customer"},
    )

    response = await client.post(
        "/auth/login",
        json={"Email": email, "Password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_token_refresh(client: AsyncClient):
    email = "refreshtest@example.com"
    password = "Password123!"
    await client.post(
        "/auth/register",
        json={"Email": email, "Password": password, "Role": "Customer"},
    )
    login_res = await client.post(
        "/auth/login",
        json={"Email": email, "Password": password},
    )
    refresh_token = login_res.json()["refresh_token"]

    # Refresh
    refresh_res = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_logout_revokes_token(client: AsyncClient):
    email = "logouttest@example.com"
    password = "Password123!"
    await client.post(
        "/auth/register",
        json={"Email": email, "Password": password, "Role": "Customer"},
    )
    login_res = await client.post(
        "/auth/login",
        json={"Email": email, "Password": password},
    )
    tokens = login_res.json()
    auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Logout
    logout_res = await client.post(
        "/auth/logout",
        headers=auth_headers,
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout_res.status_code == 200

    # Refresh attempt with revoked token must fail
    fail_res = await client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert fail_res.status_code == 401

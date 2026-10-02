import uuid
import pytest
from httpx import AsyncClient
from app.models.user import User


@pytest.mark.asyncio
async def test_create_account_success(client: AsyncClient, customer_headers: dict):
    payload = {
        "AccountType": "Checking",
        "InitialDeposit": "500.00",
    }
    response = await client.post("/accounts", json=payload, headers=customer_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["AccountType"] == "Checking"
    assert float(data["Balance"]) == 500.00
    assert "AccountID" in data


@pytest.mark.asyncio
async def test_list_accounts(client: AsyncClient, customer_headers: dict):
    # Create two accounts
    await client.post("/accounts", json={"AccountType": "Checking", "InitialDeposit": "100.00"}, headers=customer_headers)
    await client.post("/accounts", json={"AccountType": "Savings", "InitialDeposit": "250.00"}, headers=customer_headers)

    response = await client.get("/accounts", headers=customer_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_get_account_history(client: AsyncClient, customer_headers: dict):
    acc_res = await client.post(
        "/accounts",
        json={"AccountType": "Checking", "InitialDeposit": "1000.00"},
        headers=customer_headers,
    )
    acc_id = acc_res.json()["AccountID"]

    history_res = await client.get(f"/accounts/{acc_id}/history", headers=customer_headers)
    assert history_res.status_code == 200
    data = history_res.json()
    assert data["account_id"] == acc_id
    assert "transactions" in data
    assert "total_transactions" in data

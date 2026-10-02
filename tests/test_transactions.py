import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_transfer_funds_success(client: AsyncClient, customer_headers: dict):
    # Setup two accounts
    acc1_res = await client.post(
        "/accounts",
        json={"AccountType": "Checking", "InitialDeposit": "1000.00"},
        headers=customer_headers,
    )
    acc1_id = acc1_res.json()["AccountID"]

    acc2_res = await client.post(
        "/accounts",
        json={"AccountType": "Savings", "InitialDeposit": "100.00"},
        headers=customer_headers,
    )
    acc2_id = acc2_res.json()["AccountID"]

    # Transfer 250.00
    transfer_payload = {
        "SenderAccountID": acc1_id,
        "ReceiverAccountID": acc2_id,
        "Amount": "250.00",
        "Description": "Test fund transfer",
    }
    tx_res = await client.post("/transactions/transfer", json=transfer_payload, headers=customer_headers)
    assert tx_res.status_code == 201
    tx_data = tx_res.json()
    assert float(tx_data["Amount"]) == 250.00
    assert tx_data["SenderAccount"] == acc1_id
    assert tx_data["ReceiverAccount"] == acc2_id

    # Check updated balances
    acc1_history = await client.get(f"/accounts/{acc1_id}/history", headers=customer_headers)
    acc2_history = await client.get(f"/accounts/{acc2_id}/history", headers=customer_headers)
    assert float(acc1_history.json()["balance"]) == 750.00
    assert float(acc2_history.json()["balance"]) == 350.00


@pytest.mark.asyncio
async def test_transfer_insufficient_funds_fails(client: AsyncClient, customer_headers: dict):
    acc1_res = await client.post(
        "/accounts",
        json={"AccountType": "Checking", "InitialDeposit": "50.00"},
        headers=customer_headers,
    )
    acc2_res = await client.post(
        "/accounts",
        json={"AccountType": "Savings", "InitialDeposit": "10.00"},
        headers=customer_headers,
    )

    transfer_payload = {
        "SenderAccountID": acc1_res.json()["AccountID"],
        "ReceiverAccountID": acc2_res.json()["AccountID"],
        "Amount": "500.00",  # Exceeds 50.00 balance
    }
    tx_res = await client.post("/transactions/transfer", json=transfer_payload, headers=customer_headers)
    assert tx_res.status_code == 400
    assert "Insufficient funds" in tx_res.json()["detail"]


@pytest.mark.asyncio
async def test_transfer_to_self_account_fails(client: AsyncClient, customer_headers: dict):
    acc1_res = await client.post(
        "/accounts",
        json={"AccountType": "Checking", "InitialDeposit": "500.00"},
        headers=customer_headers,
    )
    acc_id = acc1_res.json()["AccountID"]

    transfer_payload = {
        "SenderAccountID": acc_id,
        "ReceiverAccountID": acc_id,
        "Amount": "50.00",
    }
    tx_res = await client.post("/transactions/transfer", json=transfer_payload, headers=customer_headers)
    assert tx_res.status_code == 400
    assert "different" in tx_res.json()["detail"]


@pytest.mark.asyncio
async def test_get_transaction_risk_score(client: AsyncClient, customer_headers: dict):
    acc1 = (await client.post("/accounts", json={"AccountType": "Checking", "InitialDeposit": "1000.00"}, headers=customer_headers)).json()
    acc2 = (await client.post("/accounts", json={"AccountType": "Savings", "InitialDeposit": "100.00"}, headers=customer_headers)).json()

    tx = (await client.post("/transactions/transfer", json={
        "SenderAccountID": acc1["AccountID"],
        "ReceiverAccountID": acc2["AccountID"],
        "Amount": "100.00",
    }, headers=customer_headers)).json()

    risk_res = await client.get(f"/transactions/{tx['TransactionID']}/risk-score", headers=customer_headers)
    assert risk_res.status_code == 200
    risk_data = risk_res.json()
    assert "RiskScore" in risk_data
    assert "AlertLevel" in risk_data
    assert "Decision" in risk_data

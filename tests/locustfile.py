import random
import uuid
from locust import HttpUser, between, task


class BankingApiUser(HttpUser):
    """Simulates high-concurrency bank customer interactions and fund transfers."""

    wait_time = between(0.1, 0.5)
    token = None
    account_ids = []

    def on_start(self):
        """Register and authenticate user, then initialize source & destination accounts."""
        email = f"loadtest_{uuid.uuid4().hex[:8]}@securebank.com"
        password = "LoadTestPassword123!"

        # 1. Register
        reg_resp = self.client.post(
            "/auth/register",
            json={"Email": email, "Password": password, "Role": "Customer"},
        )

        # 2. Login
        login_resp = self.client.post(
            "/auth/login",
            json={"Email": email, "Password": password, "DeviceFingerprint": "locust-client"},
        )
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("access_token")
            headers = {"Authorization": f"Bearer {self.token}"}

            # 3. Create two accounts for transfers
            acc1 = self.client.post(
                "/accounts",
                json={"AccountType": "Checking", "InitialDeposit": "50000.00"},
                headers=headers,
            )
            acc2 = self.client.post(
                "/accounts",
                json={"AccountType": "Savings", "InitialDeposit": "1000.00"},
                headers=headers,
            )
            if acc1.status_code == 201 and acc2.status_code == 201:
                self.account_ids = [acc1.json()["AccountID"], acc2.json()["AccountID"]]

    @task(3)
    def view_accounts(self):
        """Read account balances."""
        if not self.token:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get("/accounts", headers=headers, name="/accounts [GET]")

    @task(5)
    def transfer_funds(self):
        """Execute atomic fund transfer with ML fraud scoring trigger."""
        if not self.token or len(self.account_ids) < 2:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "SenderAccountID": self.account_ids[0],
            "ReceiverAccountID": self.account_ids[1],
            "Amount": str(round(random.uniform(10.0, 300.0), 2)),
            "Description": "Locust load test transfer",
        }
        with self.client.post(
            "/transactions/transfer",
            json=payload,
            headers=headers,
            catch_response=True,
            name="/transactions/transfer [POST]",
        ) as response:
            if response.status_code == 201:
                response.success()
            else:
                response.failure(f"Transfer failed with status {response.status_code}")

    @task(2)
    def check_account_history(self):
        """Fetch paginated transaction history."""
        if not self.token or not self.account_ids:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get(
            f"/accounts/{self.account_ids[0]}/history",
            headers=headers,
            name="/accounts/{id}/history [GET]",
        )

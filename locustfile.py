import random
import uuid
from locust import HttpUser, between, task


class BankingCustomerUser(HttpUser):
    """Simulates realistic concurrent banking customer traffic.

    Tests latency target: p95 < 1s under concurrent transfer and query loads.
    """

    wait_time = between(0.1, 0.5)
    host = "http://localhost:8000"

    def on_start(self):
        """Register and authenticate user to obtain JWT token and account IDs."""
        self.email = f"loadtest_{uuid.uuid4().hex[:8]}@example.com"
        self.password = "LoadTestP@ss123"
        self.headers = {
            "User-Agent": "LocustLoadAgent/1.0",
            "X-Forwarded-For": f"198.51.100.{random.randint(1, 254)}",
            "X-Device-Fingerprint": f"device_fp_{uuid.uuid4().hex[:12]}",
        }

        # 1. Register User
        reg_resp = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "role": "Customer",
            },
            headers=self.headers,
        )
        if reg_resp.status_code == 201:
            self.user_id = reg_resp.json().get("UserID")
        else:
            self.user_id = None

        # 2. Login
        login_resp = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": self.email,
                "password": self.password,
            },
            headers=self.headers,
        )
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("access_token")
            self.auth_headers = {
                **self.headers,
                "Authorization": f"Bearer {self.token}",
            }
        else:
            self.auth_headers = self.headers

        # 3. Create Primary Checking Account with $50,000 balance
        acc1_resp = self.client.post(
            "/api/v1/accounts",
            json={
                "account_type": "Checking",
                "initial_deposit": 50000.00,
            },
            headers=self.auth_headers,
        )
        self.acc1_id = acc1_resp.json().get("AccountID") if acc1_resp.status_code == 201 else None

        # 4. Create Secondary Savings Account with $10,000 balance
        acc2_resp = self.client.post(
            "/api/v1/accounts",
            json={
                "account_type": "Savings",
                "initial_deposit": 10000.00,
            },
            headers=self.auth_headers,
        )
        self.acc2_id = acc2_resp.json().get("AccountID") if acc2_resp.status_code == 201 else None
        self.recent_tx_ids = []

    @task(5)
    def execute_transfer(self):
        """Execute atomic fund transfer with row-level locks and streaming ML event dispatch."""
        if not self.acc1_id or not self.acc2_id:
            return

        amount = round(random.uniform(5.0, 150.0), 2)
        payload = {
            "SenderAccountID": self.acc1_id,
            "ReceiverAccountID": self.acc2_id,
            "Amount": amount,
            "Description": "Locust load test transfer",
        }

        with self.client.post(
            "/api/v1/transactions/transfer",
            json=payload,
            headers=self.auth_headers,
            catch_response=True,
        ) as response:
            if response.status_code in [200, 201]:
                tx_data = response.json()
                tx_id = tx_data.get("TransactionID")
                if tx_id:
                    self.recent_tx_ids.append(tx_id)
                response.success()
            else:
                response.failure(f"Transfer failed with status {response.status_code}: {response.text}")

    @task(3)
    def query_risk_score(self):
        """Query real-time AI risk score and explainability."""
        if not self.recent_tx_ids:
            return
        tx_id = random.choice(self.recent_tx_ids)
        self.client.get(
            f"/api/v1/transactions/{tx_id}/risk-score",
            headers=self.auth_headers,
            name="/api/v1/transactions/[id]/risk-score",
        )

    @task(2)
    def fetch_account_history(self):
        """Query paginated transaction ledger history."""
        if not self.acc1_id:
            return
        self.client.get(
            f"/api/v1/accounts/{self.acc1_id}/history?page=1&page_size=20",
            headers=self.auth_headers,
            name="/api/v1/accounts/[id]/history",
        )


class BankAdminUser(HttpUser):
    """Simulates Bank Administrator monitoring transactions, alerts, and model metrics."""

    wait_time = between(0.5, 1.5)
    host = "http://localhost:8000"

    def on_start(self):
        """Authenticate as Bank Admin."""
        self.email = f"admin_{uuid.uuid4().hex[:8]}@securebank.internal"
        self.password = "AdminSuperSecur3!"
        self.headers = {"User-Agent": "LocustAdminAgent/1.0"}

        # Register Admin
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "role": "Bank Admin",
            },
            headers=self.headers,
        )

        # Login
        login_resp = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": self.email,
                "password": self.password,
            },
            headers=self.headers,
        )
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("access_token")
            self.auth_headers = {
                **self.headers,
                "Authorization": f"Bearer {self.token}",
            }
        else:
            self.auth_headers = self.headers

    @task(3)
    def monitor_live_metrics(self):
        """Admin dashboard: live ML model precision, recall, F1, and alert throughput."""
        self.client.get(
            "/api/v1/admin/dashboard/metrics",
            headers=self.auth_headers,
            name="/api/v1/admin/dashboard/metrics",
        )

    @task(2)
    def view_transaction_feed(self):
        """Admin dashboard: real-time transaction monitoring feed."""
        self.client.get(
            "/api/v1/admin/dashboard/transactions?limit=25",
            headers=self.auth_headers,
            name="/api/v1/admin/dashboard/transactions",
        )

    @task(2)
    def inspect_active_alerts(self):
        """Admin dashboard: active high-risk alerts with SHAP explanation breakdowns."""
        self.client.get(
            "/api/v1/admin/dashboard/alerts?limit=25",
            headers=self.auth_headers,
            name="/api/v1/admin/dashboard/alerts",
        )

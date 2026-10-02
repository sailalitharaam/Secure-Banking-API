from fastapi import APIRouter

from app.api.v1.endpoints import accounts, admin, alerts, auth, transactions

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Session"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["Account Management"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Banking Transactions"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Fraud Alerts"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin & Risk Dashboard"])

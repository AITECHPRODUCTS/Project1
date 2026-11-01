from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.middleware import FinancialSandboxMiddleware


def make_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(FinancialSandboxMiddleware)

    @app.post("/api/merchant/offers")
    async def create_offer(payload: dict):
        return {"accepted": payload}

    @app.post("/api/finance/payouts")
    async def payout_operation():
        return {"executed": True}

    return TestClient(app)


def test_program_minimum_payout_and_schedule_are_policy_metadata_not_payment_actions():
    with make_client() as client:
        response = client.post("/api/merchant/offers", json={
            "name": "Merchant program",
            "minimum_payout_amount": "20.00",
            "payout_schedule": "monthly",
        })
        assert response.status_code == 200, response.text
        assert response.json()["accepted"]["minimum_payout_amount"] == "20.00"


def test_financial_operations_and_recipient_fields_remain_blocked():
    with make_client() as client:
        for payload in (
            {"payment_method": "bank transfer"},
            {"bank_account": "123"},
            {"action": "release payout"},
        ):
            response = client.post("/api/merchant/offers", json=payload)
            assert response.status_code == 403
            assert response.json()["code"] == "FINANCIAL_SANDBOX_BLOCK"

        response = client.post("/api/finance/payouts", json={})
        assert response.status_code == 403
        assert response.json()["code"] == "FINANCIAL_SANDBOX_BLOCK"

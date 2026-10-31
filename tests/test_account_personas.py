from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.schemas import RegisterRequest


def test_public_registration_requires_exactly_one_supported_persona():
    publisher = RegisterRequest(
        email="publisher@example.test",
        password="PublisherPassword123",
        account_type="affiliate_publisher",
    )
    merchant = RegisterRequest(
        email="merchant@example.test",
        password="MerchantPassword123",
        account_type="merchant_product_owner",
    )
    assert publisher.account_type == "affiliate_publisher"
    assert merchant.account_type == "merchant_product_owner"

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="admin@example.test",
            password="NotForPublicAdmin123",
            account_type="platform_admin",
        )
    missing_persona_password = "Missing" + "Persona123"
    with pytest.raises(ValidationError):
        RegisterRequest(email="missing@example.test", password=missing_persona_password)


def test_workspace_owner_permission_does_not_grant_the_other_business_persona():
    publisher_guard = main.require_account_type("affiliate_publisher")
    merchant_guard = main.require_account_type("merchant_product_owner")
    publisher_owner = {
        "user_id": "publisher-1",
        "account_type": "affiliate_publisher",
        "workspace_role": "owner",
        "is_admin": False,
    }
    merchant_owner = {
        "user_id": "merchant-1",
        "account_type": "merchant_product_owner",
        "workspace_role": "owner",
        "is_admin": False,
    }

    assert asyncio.run(publisher_guard(user=publisher_owner)) is publisher_owner
    assert asyncio.run(merchant_guard(user=merchant_owner)) is merchant_owner
    with pytest.raises(HTTPException) as denied:
        asyncio.run(merchant_guard(user=publisher_owner))
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as denied:
        asyncio.run(publisher_guard(user=merchant_owner))
    assert denied.value.status_code == 403


def test_platform_super_admin_can_access_both_persona_surfaces():
    publisher_guard = main.require_account_type("affiliate_publisher")
    merchant_guard = main.require_account_type("merchant_product_owner")
    admin = {
        "user_id": "platform-admin",
        "account_type": "platform_admin",
        "workspace_role": "owner",
        "is_admin": True,
    }
    assert asyncio.run(publisher_guard(user=admin)) is admin
    assert asyncio.run(merchant_guard(user=admin)) is admin


def test_opposite_persona_is_denied_by_business_api_routes():
    async def no_database():
        yield None

    principals_and_paths = [
        (
            {
                "user_id": "publisher-1",
                "account_type": "affiliate_publisher",
                "workspace_role": "owner",
                "is_admin": False,
            },
            "/api/merchant/offers",
        ),
        (
            {
                "user_id": "merchant-1",
                "account_type": "merchant_product_owner",
                "workspace_role": "owner",
                "is_admin": False,
            },
            "/api/marketplace/offers",
        ),
    ]

    for principal, path in principals_and_paths:
        async def override_auth(user=principal):
            return user

        main.app.dependency_overrides[main.require_auth] = override_auth
        main.app.dependency_overrides[main.get_session] = no_database
        try:
            with TestClient(main.app) as client:
                response = client.get(path)
            assert response.status_code == 403, response.text()
        finally:
            main.app.dependency_overrides.pop(main.require_auth, None)
            main.app.dependency_overrides.pop(main.get_session, None)

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import main
from backend.schemas import GuaranteeDraftRequest
from backend.services.guarantee_draft import build_guarantee_draft


TERMS = "The merchant terms provide a 30-day money-back refund period for eligible new subscribers. Requests must be submitted to support with the order number. Consumed digital goods are excluded."


def request(**overrides):
    data = {
        "product_name": "Creator Toolkit",
        "guarantee_type": "refund",
        "duration_days": 30,
        "eligibility": "New subscribers with an eligible first purchase",
        "exclusions": ["Consumed digital goods"],
        "claim_process": "Contact merchant support with the order number during the stated period",
        "merchant_terms_text": TERMS,
        "source_url": "https://merchant.example/terms",
    }
    data.update(overrides)
    return data


def test_builder_uses_only_supplied_terms_and_marks_claim_unverified():
    result = build_guarantee_draft(**request())
    assert "30-day refund" in result["draft_copy"]
    assert "New subscribers with an eligible first purchase" in result["draft_copy"]
    assert "Consumed digital goods" in result["draft_copy"]
    assert result["duration_found_in_terms"] is True
    assert result["guarantee_type_found_in_terms"] is True
    assert result["terms_verified"] is False
    assert result["merchant_terms_status"] == "operator_supplied_not_independently_verified"
    assert result["requires_review"] is True
    assert result["publishing_started"] is False


def test_builder_refuses_invented_duration_or_guarantee_type():
    with pytest.raises(ValueError, match="duration is not explicitly present"):
        build_guarantee_draft(**request(duration_days=60))
    with pytest.raises(ValueError, match="do not mention this guarantee type"):
        build_guarantee_draft(**request(guarantee_type="replacement"))


def test_builder_does_not_claim_no_exclusions_when_none_were_supplied():
    result = build_guarantee_draft(**request(exclusions=[]))
    assert "No exclusions were supplied" in result["draft_copy"]
    assert "do not imply that the merchant has no exclusions" in result["draft_copy"]


def test_request_rejects_private_source_and_missing_terms():
    with pytest.raises(ValidationError):
        GuaranteeDraftRequest(**request(source_url="http://127.0.0.1/terms"))
    with pytest.raises(ValidationError):
        GuaranteeDraftRequest(**request(merchant_terms_text="No details."))


def test_api_persists_review_only_guarantee_copy(monkeypatch):
    def fake_builder(**kwargs):
        assert kwargs["duration_days"] == 30
        return {
            "product_name": "Creator Toolkit",
            "guarantee_type": "refund",
            "duration_days": 30,
            "eligibility": "Eligible new subscribers",
            "exclusions": ["Consumed digital goods"],
            "claim_process": "Contact support",
            "source_url": "https://merchant.example/terms",
            "draft_copy": "Draft only: supplied 30-day refund terms, not verified.",
            "merchant_terms_status": "operator_supplied_not_independently_verified",
            "duration_found_in_terms": True,
            "guarantee_type_found_in_terms": True,
            "terms_verified": False,
            "requires_review": True,
            "publishing_started": False,
            "note": "Review official terms.",
        }
    monkeypatch.setattr(main,"build_guarantee_draft_service",fake_builder)
    with TestClient(main.app) as client:
        response=client.post("/api/landing/guarantee-draft",json=request())
    assert response.status_code==201,response.text
    result=response.json()
    assert result["asset_id"]
    assert result["terms_verified"] is False
    assert result["requires_review"] is True
    assert result["publishing_started"] is False


def test_api_rejects_absent_guarantee_period():
    with TestClient(main.app) as client:
        response=client.post("/api/landing/guarantee-draft",json=request(duration_days=30,merchant_terms_text="No duration or guarantee appears in these terms."))
    assert response.status_code==422

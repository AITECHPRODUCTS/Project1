from __future__ import annotations
import pytest
from backend.services.analytics_utils import ab_test_generator,conversion_tracker
from backend.services.integration_registry import build_network_registry
from backend.services.offer_intelligence import compute_offer_metrics
from backend.services.url_safety import validate_public_http_url
from backend.adapters.webhook import AggregatorWebhookAdapter
from backend.schemas import CampaignCreateRequest,ConversionRequest,LeadCaptureRequest
def test_utm_parser_preserves_click_and_source_fields():
 data=conversion_tracker("https://example.com/?utm_source=reddit&utm_campaign=april&utm_content=hook-a&subid=click-123")
 assert data["utm_source"]=="reddit" and data["utm_campaign"]=="april" and data["click_id"]=="click-123"
def test_utm_parser_accepts_query_string():
 assert conversion_tracker("?utm_medium=social")["utm_medium"]=="social"
def test_ab_assignment_is_stable_for_same_visitor_before_sample_threshold():
 a=ab_test_generator("Headline A","Headline B",visitor_id="visitor-1",experiment_key="test")
 b=ab_test_generator("Headline A","Headline B",visitor_id="visitor-1",experiment_key="test")
 assert a["variant"]==b["variant"] and a["assignment_method"]=="stable_hash_split"
def test_ab_assignment_rejects_invalid_conversion_count():
 with pytest.raises(ValueError):ab_test_generator("A","B",visitor_id="x",experiment_key="test",conversions_a=2,impressions_a=1)
def test_unknown_epc_remains_unknown_not_invented():
 result=compute_offer_metrics({"reward_type":"one-time","reward_value":"20"})
 assert result["epc"] is None and result["conversion_rate"] is None
def test_epc_uses_actual_revenue_and_click_denominator():
 result=compute_offer_metrics({"gravity_score":4,"reward_type":"recurring"},clicks=20,conversions=2,total_revenue=50)
 assert result["epc"]==2.5 and result["conversion_rate"]==.1 and result["recurring_commission"] is True
def test_registry_does_not_infer_provider_authorization():
 config={"networks":{"openaffiliate":{"enabled":True,"adapter":"openaffiliate"},"clickbank":{"enabled":False,"adapter":"clickbank"},"unknown":{"enabled":True,"adapter":"scraper"}}}
 result=build_network_registry(config,environ={})
 by={x["provider_id"]:x for x in result["items"]}
 assert by["openaffiliate"]["status"]=="configured_not_health_checked"
 assert by["openaffiliate"]["write_access_verified"] is False
 assert by["clickbank"]["status"]=="catalogued_disabled"
 assert by["unknown"]["status"]=="not_implemented"
def test_signed_webhook_requires_unique_external_id():
 adapter=AggregatorWebhookAdapter("demo","x"*32)
 assert adapter.parse_conversion({"event_id":"evt-1","commission":1})["external_event_id"]=="evt-1"
 with pytest.raises(ValueError):adapter.parse_conversion({"commission":1})
@pytest.mark.asyncio
async def test_url_safety_rejects_localhost_without_network():
 with pytest.raises(ValueError):await validate_public_http_url("http://localhost/admin")
 with pytest.raises(ValueError):await validate_public_http_url("http://127.0.0.1/")
def test_campaign_url_schema_has_safe_default_publish_setting():
 row=CampaignCreateRequest(name="Test campaign",niche="fitness",primary_destination="https://example.com")
 assert row.auto_publish is False and row.max_daily_spend==0
def test_conversion_currency_is_bounded():
 row=ConversionRequest(network="test",external_event_id="event-1",currency="usd")
 assert row.currency=="usd"
def test_lead_capture_requires_explicit_consent_value():
 with pytest.raises(Exception):LeadCaptureRequest(email="a@example.com",consent=False,lead_magnet="Guide",audience="Beginners")



@pytest.mark.parametrize(
    "measurement_kwargs",
    [
        {"clicks": -1},
        {"clicks": 1.5},
        {"conversions": -1},
        {"clicks": 4, "conversions": 1.5},
        {"clicks": 4, "conversions": True},
        {"total_revenue": -0.01},
        {"total_revenue": float("nan")},
        {"total_revenue": float("inf")},
        {"total_revenue": True},
        {"gravity_weight": float("nan")},
        {"gravity_weight": float("inf")},
        {"gravity_weight": True},
    ],
)
def test_offer_metric_inputs_reject_invalid_measurements(measurement_kwargs):
    with pytest.raises(ValueError):
        compute_offer_metrics({"reward_type": "one-time"}, **measurement_kwargs)


@pytest.mark.parametrize("gravity", [-1, float("nan"), float("inf"), "nan", "invalid", True])
def test_invalid_offer_gravity_is_reported_as_unknown(gravity):
    result = compute_offer_metrics({"gravity_score": gravity})
    assert result["gravity_score"] is None
    assert result["normalized_gravity"] is None


def test_offer_metrics_preserve_valid_zero_and_unknown_measurements():
    measured = compute_offer_metrics({}, clicks=3, conversions=0, total_revenue=0)
    assert measured["epc"] == 0
    assert measured["conversion_rate"] == 0
    assert measured["measurement_basis"]["clicks"] == 3

    unknown = compute_offer_metrics({}, clicks=0, conversions=0, total_revenue=0)
    assert unknown["epc"] is None
    assert unknown["conversion_rate"] is None

from __future__ import annotations

from datetime import datetime, timezone

from backend.schemas import LeadCaptureRequest
from backend.services.s4_s5_landing import render_workspace_landing_page
from backend.services.utm_attribution import (
    lead_attribution_summary,
    merge_lead_attribution_metadata,
    normalize_utm_attribution,
)


def test_utm_normalization_is_allowlisted_bounded_and_drops_controls_and_email_pii():
    normalized = normalize_utm_attribution({
        "utm_source": "  weekly\nnewsletter  ",
        "utm_medium": "email",
        "utm_campaign": "c" * 240,
        "utm_term": "person@example.com",
        "utm_id": "not-an-allowed-field",
    })

    assert normalized["utm_source"] == "weeklynewsletter"
    assert normalized["utm_medium"] == "email"
    assert len(normalized["utm_campaign"]) == 200
    assert "utm_term" not in normalized
    assert "utm_id" not in normalized


def test_attribution_preserves_first_touch_updates_last_touch_and_ignores_empty_updates():
    first_at = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    second_at = datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc)
    metadata = {"existing_application_metadata": {"keep": True}}
    metadata = merge_lead_attribution_metadata(
        metadata,
        {"utm_source": "newsletter", "utm_campaign": "october_guide", "other": "ignored"},
        observed_at=first_at,
    )
    metadata = merge_lead_attribution_metadata(
        metadata,
        {"utm_source": "paid-social", "utm_medium": "paid", "utm_campaign": "november_guide"},
        observed_at=second_at,
    )

    summary = lead_attribution_summary(metadata)
    assert summary["first_touch"] == {
        "utm_source": "newsletter",
        "utm_campaign": "october_guide",
    }
    assert summary["last_touch"] == {
        "utm_source": "paid-social",
        "utm_medium": "paid",
        "utm_campaign": "november_guide",
    }
    assert summary["last_touch_at"] == second_at.isoformat()
    assert metadata["existing_application_metadata"] == {"keep": True}

    unchanged = merge_lead_attribution_metadata(metadata, {"utm_id": "ignored"}, observed_at=second_at)
    assert unchanged == metadata


def test_lead_capture_schema_normalizes_campaign_fields():
    payload = LeadCaptureRequest(
        email="creator@example.test",
        consent=True,
        lead_magnet="Starter guide",
        audience="Independent creators",
        utm_source=" weekly newsletter ",
        utm_medium="email",
        utm_campaign="creator_launch",
    )
    assert payload.utm_source == "weekly newsletter"
    assert payload.utm_medium == "email"
    assert payload.utm_campaign == "creator_launch"


def test_landing_renderer_emits_only_escaped_allowlisted_utm_fields():
    html = render_workspace_landing_page(
        headline="A practical resource",
        subheadline="A clear, evidence-first guide.",
        benefit_bullets=["Compare options"],
        privacy_url="https://example.invalid/privacy",
        workspace_token="opaque.signed.token",
        utm_attribution={
            "utm_source": "newsletter & partners",
            "utm_content": 'variant "<safe>"',
            "utm_id": "untracked",
        },
    )

    assert 'name="utm_source" value="newsletter &amp; partners"' in html
    assert 'name="utm_content" value="variant &quot;&lt;safe&gt;&quot;"' in html
    assert 'name="utm_id"' not in html

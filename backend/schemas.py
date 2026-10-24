from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class WorkflowStartRequest(BaseModel):
    workflow_name: str = Field(default="full_flywheel", max_length=180)
    execution_mode: Literal["FULL_AUTONOMOUS", "SEMI_AUTONOMOUS", "MANUAL_OVERRIDE"] | None = None
    state: dict[str, Any] = Field(default_factory=dict)


class ResumeRequest(BaseModel):
    verification_code: str = Field(min_length=1, max_length=512)


class NicheFinderRequest(BaseModel):
    candidates: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    top_n: int = Field(default=10, ge=1, le=50)


class CompetitorRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=10)


class TrendRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=10, ge=1, le=25)


class BlogRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=400)
    product: dict[str, Any] | None = None
    canonical_url: str | None = Field(default=None, max_length=2048)
    minimum_words: int = Field(default=1500, ge=1500, le=2500)


class SocialPostRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=400)
    hooks: list[dict[str, Any]] = Field(min_length=1, max_length=20)
    platform: str = Field(default="x", max_length=60)


class CampaignCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=300)
    niche: str = Field(min_length=2, max_length=200)
    primary_destination: str = Field(min_length=8, max_length=2048)
    fallback_destination: str | None = None
    tracking_parameter: str = Field(default="subid", min_length=1, max_length=80)
    disclosure_text: str = Field(default="Disclosure: I may earn a commission from qualifying purchases.", max_length=1200)
    auto_publish: bool = False
    max_daily_spend: float = Field(default=0, ge=0, le=1_000_000)


class ConversionRequest(BaseModel):
    network: str = Field(min_length=1, max_length=100)
    external_event_id: str = Field(min_length=1, max_length=255)
    click_id: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    hook: str | None = None
    revenue: float = Field(default=0, ge=0)
    commission: float = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    status: str = Field(default="pending", max_length=60)
    url: str | None = None
    event_json: dict[str, Any] = Field(default_factory=dict)


class LeadCaptureRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    consent: bool
    lead_magnet: str = Field(min_length=2, max_length=300)
    audience: str = Field(min_length=2, max_length=500)
    offer: dict[str, Any] = Field(default_factory=dict)
    consent_source: str = Field(default="website_form", max_length=180)
    duration_days: int = Field(default=5, ge=5, le=7)


class VideoRequest(BaseModel):
    script: str = Field(min_length=10, max_length=10000)
    broll_query: str = Field(min_length=2, max_length=200)
    voice: str = Field(default="en-US-AriaNeural", max_length=100)
    captions: bool = True


class LandingPageRequest(BaseModel):
    headline: str = Field(min_length=3, max_length=250)
    subheadline: str = Field(min_length=3, max_length=800)
    benefit_bullets: list[str] = Field(min_length=1, max_length=8)
    form_action: str = Field(default="/api/public/leads/capture", max_length=300)
    privacy_url: str = Field(min_length=8, max_length=2048)
    affiliate_disclosure: str | None = Field(default=None, max_length=1200)
    lead_magnet: str = Field(default="Free resource", min_length=2, max_length=300)
    audience: str = Field(default="website subscriber", min_length=2, max_length=500)


class CMSPublishRequest(BaseModel):
    provider: Literal["wordpress", "ghost"]
    title: str = Field(min_length=3, max_length=300)
    article_html: str = Field(min_length=30, max_length=500000)
    canonical_url: str = Field(min_length=8, max_length=2048)
    status: Literal["draft", "publish"] = "draft"
    tags: list[str] = Field(default_factory=list, max_length=20)
    disclosure: str = Field(default="Disclosure: I may earn a commission from qualifying purchases through affiliate links.", max_length=1200)


class PayoutThresholdCreateRequest(BaseModel):
    network: str = Field(min_length=1, max_length=150)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    minimum_threshold: float = Field(ge=0, le=1_000_000)
    reported_balance: float = Field(default=0, ge=0, le=1_000_000)
    reconciliation_note: str = Field(default="", max_length=4000)

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str) -> str:
        return value.upper()


class FundsReceivedRequest(BaseModel):
    funds_received_at: datetime
    reconciliation_note: str = Field(default="", max_length=4000)


class ROASEvaluationRequest(BaseModel):
    campaign_id: str = Field(min_length=1, max_length=255)
    spend: float = Field(ge=0, le=1_000_000_000)
    commission: float = Field(ge=0, le=1_000_000_000)
    threshold: float = Field(default=1.2, ge=0, le=1000)


class SocialPublishRequest(BaseModel):
    platform: Literal["reddit", "pinterest"]
    post: dict[str, Any]
    publish_at: datetime | None = None


class ContentResearchBriefRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=400)
    urls: list[str] = Field(min_length=1, max_length=10)

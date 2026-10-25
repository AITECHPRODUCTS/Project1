from __future__ import annotations

import ipaddress

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=1024)
    workspace_name: str = Field(default="My workspace", min_length=2, max_length=160)


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)


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
    workspace_token: str | None = Field(default=None, max_length=1024)
    duration_days: int = Field(default=5, ge=5, le=7)

    @field_validator("consent")
    @classmethod
    def require_explicit_consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Explicit email consent is required")
        return value


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


class ABTestAssignmentRequest(BaseModel):
    experiment_key: str = Field(min_length=1, max_length=180)
    visitor_id: str = Field(min_length=1, max_length=255)
    headline_a: str = Field(min_length=1, max_length=500)
    headline_b: str = Field(min_length=1, max_length=500)

    @field_validator("experiment_key", "visitor_id", "headline_a", "headline_b")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be blank")
        return normalized


class ExperimentEventRequest(BaseModel):
    experiment_key: str = Field(min_length=1, max_length=180)
    visitor_id: str = Field(min_length=1, max_length=255)
    event_id: str = Field(min_length=1, max_length=255)
    event_type: Literal["impression", "conversion"]

    @field_validator("experiment_key", "visitor_id", "event_id")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be blank")
        return normalized


class CommissionEvidenceReviewRequest(BaseModel):
    decision: Literal[
        "matched_to_conversion",
        "not_a_match",
        "needs_review",
        "rejected_as_unreliable",
    ]
    candidate_conversion_id: str | None = Field(default=None, min_length=1, max_length=36)
    note: str = Field(default="", max_length=4000)



AdPlatform = Literal[
    "google_search",
    "google_display",
    "meta",
    "instagram",
    "tiktok",
    "youtube_shorts",
    "pinterest",
    "reddit",
    "quora",
    "x",
    "linkedin",
    "snapchat",
    "native",
]


class AdCampaignPlanRequest(BaseModel):
    campaign_name: str | None = Field(default=None, min_length=2, max_length=160)
    niche: str = Field(min_length=2, max_length=200)
    audience: str = Field(min_length=2, max_length=400)
    region: str = Field(default="Global", min_length=2, max_length=120)
    objective: Literal["traffic", "leads", "sales", "awareness"] = "traffic"
    product_name: str | None = Field(default=None, min_length=2, max_length=200)
    product_summary: str | None = Field(default=None, max_length=2000)
    product_facts_for_review: list[str] = Field(default_factory=list, max_length=20)
    evidence_urls: list[str] = Field(default_factory=list, max_length=10)
    landing_page_url: str | None = Field(default=None, max_length=2048)
    platforms: list[AdPlatform] = Field(
        default_factory=lambda: ["meta", "google_search", "tiktok"],
        min_length=1,
        max_length=10,
    )
    variants_per_platform: int = Field(default=3, ge=1, le=5)
    daily_budget_usd: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        le=Decimal("1000000.00"),
        max_digits=10,
        decimal_places=2,
    )
    affiliate_disclosure: str = Field(
        default="Disclosure: I may earn a commission from qualifying purchases.",
        min_length=12,
        max_length=1200,
    )

    @field_validator("platforms")
    @classmethod
    def deduplicate_platforms(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("product_facts_for_review")
    @classmethod
    def validate_product_facts(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item and item.strip()]
        if any(len(item) > 2000 for item in normalized):
            raise ValueError("Each product fact must be at most 2000 characters")
        return normalized

    @field_validator("evidence_urls")
    @classmethod
    def validate_evidence_urls(cls, value: list[str]) -> list[str]:
        from urllib.parse import urlparse

        normalized: list[str] = []
        for item in value:
            url = item.strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("Evidence URLs must be absolute HTTP(S) URLs")
            if parsed.username or parsed.password:
                raise ValueError("Evidence URLs may not contain credentials")
            if parsed.hostname.lower().rstrip(".") in {"localhost", "localhost.localdomain"}:
                raise ValueError("Localhost evidence URLs are not allowed")
            normalized.append(url)
        return normalized

    @field_validator("landing_page_url")
    @classmethod
    def validate_landing_page_url(cls, value: str | None) -> str | None:
        from urllib.parse import urlparse

        if value is None or not value.strip():
            return None
        url = value.strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Landing page URL must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password:
            raise ValueError("Landing page URL may not contain credentials")
        if parsed.hostname.lower().rstrip(".") in {"localhost", "localhost.localdomain"}:
            raise ValueError("Localhost landing page URLs are not allowed")
        return url

    @field_validator("affiliate_disclosure")
    @classmethod
    def require_affiliate_disclosure(cls, value: str) -> str:
        normalized = value.strip()
        lowered = normalized.lower()
        if "affiliate" not in lowered and "commission" not in lowered:
            raise ValueError("Affiliate promotions require a clear affiliate or commission disclosure")
        return normalized


class AdPerformanceObservationRequest(BaseModel):
    campaign_plan_id: str | None = Field(default=None, min_length=1, max_length=36)
    platform: AdPlatform
    creative_id: str = Field(min_length=1, max_length=180)
    source_type: Literal["manual_report", "provider_export", "provider_api"] = "manual_report"
    source_reference_url: str | None = Field(default=None, max_length=2048)
    impressions: int = Field(default=0, ge=0, le=1_000_000_000_000)
    clicks: int = Field(default=0, ge=0, le=1_000_000_000_000)
    conversions: int = Field(default=0, ge=0, le=1_000_000_000_000)
    spend_usd: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), max_digits=12, decimal_places=2)
    commission_usd: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    observed_at: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a three-letter alphabetic code")
        return normalized

    @field_validator("source_reference_url")
    @classmethod
    def validate_source_reference_url(cls, value: str | None) -> str | None:
        from urllib.parse import urlparse

        if value is None or not value.strip():
            return None
        url = value.strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Source reference must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password:
            raise ValueError("Source reference URLs may not contain credentials")
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Local/private source references are not allowed")
        return url

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ROASEvaluationRequest(BaseModel):
    campaign_id: str = Field(min_length=1, max_length=255)
    spend: float = Field(ge=0, le=1_000_000_000)
    commission: float = Field(ge=0, le=1_000_000_000)
    threshold: float = Field(default=1.2, ge=0, le=1000)


class SocialPublishRequest(BaseModel):
    platform: Literal["reddit", "pinterest"]
    post: dict[str, Any]
    publish_at: datetime | None = None



class ContentAtomizeRequest(BaseModel):
    source_title: str = Field(min_length=3, max_length=500)
    source_body: str = Field(min_length=80, max_length=20000)
    platforms: list[Literal["blog", "linkedin", "x", "x_thread", "reddit", "pinterest", "tiktok", "youtube_shorts", "email"]] = Field(min_length=1, max_length=9)
    source_urls: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("source_title", "source_body")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value must not be blank")
        return normalized

    @field_validator("platforms")
    @classmethod
    def require_unique_platforms(cls, value: list[str]) -> list[str]:
        if not value or len(set(value)) != len(value):
            raise ValueError("Choose one or more unique target platforms")
        return value

    @field_validator("source_urls")
    @classmethod
    def validate_source_urls(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(url.strip() for url in value))
        for url in normalized:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("Source references must be absolute HTTP(S) URLs")
            if parsed.username or parsed.password:
                raise ValueError("Source reference URLs may not contain credentials")
            host = parsed.hostname.lower().rstrip(".")
            if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
                raise ValueError("Local/private source references are not allowed")
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError("Private, loopback, link-local, multicast or reserved source reference hosts are not allowed")
        return normalized


class ContentResearchBriefRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=400)
    urls: list[str] = Field(min_length=1, max_length=10)

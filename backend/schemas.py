from __future__ import annotations

import ipaddress
import json
import re

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Literal
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.services.consent_ledger import (
    EMAIL_MARKETING_CONSENT_PURPOSE,
    EMAIL_MARKETING_CONSENT_TEXT,
    EMAIL_MARKETING_CONSENT_VERSION,
)


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
    confirm_live_publish: bool = False
    state: dict[str, Any] = Field(default_factory=dict)


class ResumeRequest(BaseModel):
    verification_code: str = Field(min_length=1, max_length=512)


class NicheFinderRequest(BaseModel):
    candidates: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    top_n: int = Field(default=10, ge=1, le=50)


class CompetitorRequest(BaseModel):
    urls: list[Annotated[str, Field(min_length=8, max_length=2048)]] = Field(min_length=1, max_length=10)


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
    revenue: Decimal = Field(default=Decimal("0"), ge=0)
    commission: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    status: str = Field(default="pending", max_length=60)
    url: str | None = None
    event_json: dict[str, Any] = Field(default_factory=dict)




class EmailAutomationCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=10, max_length=3000)
    version: str = Field(default="1.0.0", min_length=5, max_length=40)
    entry_step_id: str = Field(min_length=1, max_length=64)
    target_jurisdictions: list[str] = Field(default_factory=list, max_length=50)
    nodes: list[dict[str, Any]] = Field(min_length=2, max_length=30)

    @field_validator("name", "description", "version", "entry_step_id")
    @classmethod
    def normalize_email_automation_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator("target_jurisdictions")
    @classmethod
    def normalize_email_automation_jurisdictions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
        if len(normalized) > 50 or any(not re.fullmatch(r"(?:[A-Z]{2}(?:-[A-Z0-9]{1,6})?|EU|EEA|GLOBAL)", value) for value in normalized):
            raise ValueError("Use ISO-style jurisdiction codes or EU, EEA, GLOBAL")
        return normalized


class EmailAutomationReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    confirm_graph_reviewed: bool = False
    reviewer_notes: str = Field(default="", max_length=4000)

    @field_validator("reviewer_notes")
    @classmethod
    def normalize_email_automation_notes(cls, value: str) -> str:
        return value.strip()


class EmailAutomationSimulationRequest(BaseModel):
    purchased: bool = False
    engaged: bool = False
    consent_granted: bool = True
    unsubscribed: bool = False


class LeadCaptureRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    consent: bool
    lead_magnet: str = Field(min_length=2, max_length=300)
    audience: str = Field(min_length=2, max_length=500)
    offer: dict[str, Any] = Field(default_factory=dict)
    consent_source: str = Field(default="website_form", max_length=180)
    consent_text: str = Field(default=EMAIL_MARKETING_CONSENT_TEXT, min_length=10, max_length=1000)
    consent_version: str = Field(default=EMAIL_MARKETING_CONSENT_VERSION, min_length=1, max_length=80)
    consent_purpose: Literal["email_marketing"] = EMAIL_MARKETING_CONSENT_PURPOSE
    resubscribe_confirmed: bool = False
    workspace_token: str | None = Field(default=None, max_length=1024)
    email_automation_id: str | None = Field(default=None, min_length=36, max_length=36)
    duration_days: int = Field(default=5, ge=5, le=7)
    utm_source: str | None = Field(default=None, max_length=120)
    utm_medium: str | None = Field(default=None, max_length=80)
    utm_campaign: str | None = Field(default=None, max_length=200)
    utm_content: str | None = Field(default=None, max_length=200)
    utm_term: str | None = Field(default=None, max_length=160)

    @field_validator("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", mode="before")
    @classmethod
    def normalize_utm_value(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, (str, int, float)):
            raise ValueError("UTM attribution values must be plain text")
        normalized = "".join(character for character in str(value) if character.isprintable()).strip()
        return normalized or None

    @field_validator("consent")
    @classmethod
    def require_explicit_consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Explicit email consent is required")
        return value

    @field_validator("consent_text")
    @classmethod
    def require_canonical_consent_text(cls, value: str) -> str:
        if value != EMAIL_MARKETING_CONSENT_TEXT:
            raise ValueError("Consent wording does not match the currently approved text")
        return value

    @field_validator("consent_version")
    @classmethod
    def require_current_consent_version(cls, value: str) -> str:
        if value != EMAIL_MARKETING_CONSENT_VERSION:
            raise ValueError("Consent policy version is not current")
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


class LandingPagePublishRequest(BaseModel):
    confirm_public_publish: bool = False


class CMSPublishRequest(BaseModel):
    provider: Literal["wordpress", "ghost"]
    target_jurisdictions: list[str] = Field(default_factory=list, max_length=50)
    title: str = Field(min_length=3, max_length=300)
    article_html: str = Field(min_length=30, max_length=500000)
    canonical_url: str = Field(min_length=8, max_length=2048)
    status: Literal["draft", "publish"] = "draft"
    confirm_live_publish: bool = False
    tags: list[str] = Field(default_factory=list, max_length=20)
    disclosure: str = Field(default="Disclosure: I may earn a commission from qualifying purchases through affiliate links.", max_length=1200)

    @field_validator("target_jurisdictions")
    @classmethod
    def normalize_cms_target_jurisdictions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
        if any(not re.fullmatch(r"(?:[A-Z]{2}(?:-[A-Z0-9]{1,6})?|EU|EEA|GLOBAL)", value) for value in normalized):
            raise ValueError("Use ISO-style country/subdivision codes or EU, EEA, GLOBAL")
        return normalized


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



class CommissionProjectionProgramRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    reward_type: Literal["cps_one_time", "cps_recurring", "cpl", "cpa"]
    commission_type: Literal["percentage", "fixed"]
    commission_value: Decimal = Field(gt=Decimal("0"), le=Decimal("1000000000"), allow_inf_nan=False)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    average_order_value: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("1000000000"), allow_inf_nan=False)
    recurring_paid_months: int | None = Field(default=None, ge=1, le=120)

    @field_validator("name")
    @classmethod
    def normalize_program_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Program name must not be blank")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_program_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("commission_value", "average_order_value")
    @classmethod
    def require_supported_decimal_precision(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if not value.is_finite():
            raise ValueError("Commission inputs must be finite decimal amounts")
        if value.quantize(Decimal("0.000001")) != value:
            raise ValueError("Commission inputs support at most six meaningful decimal places")
        return value

    @model_validator(mode="after")
    def validate_payout_terms(self) -> "CommissionProjectionProgramRequest":
        if self.commission_type == "percentage":
            if self.reward_type not in {"cps_one_time", "cps_recurring"}:
                raise ValueError("Percentage commissions are only supported for CPS programs")
            if self.commission_value > Decimal("100"):
                raise ValueError("Percentage commission cannot exceed 100")
            if self.average_order_value is None:
                raise ValueError("Average order value is required for percentage commissions")
        elif self.average_order_value is not None:
            raise ValueError("Average order value must be omitted for fixed commissions")

        if self.reward_type == "cps_recurring":
            if self.recurring_paid_months is None:
                raise ValueError("Recurring paid months are required for recurring CPS programs")
        elif self.recurring_paid_months is not None:
            raise ValueError("Recurring paid months are only valid for recurring CPS programs")
        return self


class CommissionCalculatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monthly_visitors: int = Field(strict=True, ge=0, le=1_000_000_000)
    click_through_rate_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"), allow_inf_nan=False)
    affiliate_conversion_rate_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"), allow_inf_nan=False)
    programs: list[CommissionProjectionProgramRequest] = Field(min_length=1, max_length=10)

    @field_validator("click_through_rate_pct", "affiliate_conversion_rate_pct")
    @classmethod
    def validate_rate_precision(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Rate assumptions must be finite")
        if value.quantize(Decimal("0.000001")) != value:
            raise ValueError("Rate assumptions support at most six meaningful decimal places")
        return value


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

    @field_validator("topic")
    @classmethod
    def normalize_research_topic(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Topic must not be blank")
        return normalized

    @field_validator("urls")
    @classmethod
    def validate_research_source_urls(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
        if not normalized or len(normalized) > 10:
            raise ValueError("Provide between one and ten distinct public source URLs")
        for url in normalized:
            if len(url) > 2048:
                raise ValueError("Each source URL must be at most 2048 characters")
            try:
                parsed = urlparse(url)
                host = (parsed.hostname or "").lower().rstrip(".")
                _ = parsed.port
            except ValueError as exc:
                raise ValueError("Provide valid absolute public HTTP(S) URLs") from exc
            if parsed.scheme.lower() not in {"http", "https"} or not host:
                raise ValueError("Provide valid absolute public HTTP(S) URLs")
            if parsed.username or parsed.password:
                raise ValueError("Source URLs containing credentials are not allowed")
            if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".test", ".home", ".lan", ".corp")):
                raise ValueError("Local/private source hostnames are not allowed")
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError("Private, loopback, link-local, multicast or reserved source IPs are not allowed")
        return normalized


class ContentAngleCandidateRequest(BaseModel):
    angle: str = Field(min_length=5, max_length=600)
    description: str = Field(default="", max_length=1200)
    evidence_facts: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("angle")
    @classmethod
    def normalize_angle(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Angle must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("evidence_facts")
    @classmethod
    def normalize_evidence_facts(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip() for item in value if item and item.strip()))
        if any(len(item) > 1200 for item in normalized):
            raise ValueError("Each evidence note must be at most 1200 characters")
        return normalized


class ContentAngleRankRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=400)
    audience: str = Field(default="", max_length=400)
    candidates: list[ContentAngleCandidateRequest] = Field(min_length=1, max_length=30)

    @field_validator("topic", "audience")
    @classmethod
    def normalize_context(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized and value:
            raise ValueError("Context must not be blank")
        return normalized


class PurpleCowAlternativeRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    positioning_statement: str = Field(min_length=5, max_length=600)
    evidence_note: str = Field(default="", max_length=800)

    @field_validator("name", "positioning_statement", "evidence_note")
    @classmethod
    def normalize_alternative_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized and value:
            raise ValueError("Alternative text must not be blank")
        return normalized


class PurpleCowAuditRequest(BaseModel):
    offer_name: str = Field(min_length=2, max_length=200)
    target_audience: str = Field(min_length=2, max_length=400)
    positioning_statement: str = Field(min_length=5, max_length=600)
    alternatives: list[PurpleCowAlternativeRequest] = Field(min_length=1, max_length=10)
    evidence_notes: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("offer_name", "target_audience", "positioning_statement")
    @classmethod
    def normalize_required_positioning_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Positioning context must not be blank")
        return normalized

    @field_validator("alternatives")
    @classmethod
    def require_distinct_alternatives(cls, value: list[PurpleCowAlternativeRequest]) -> list[PurpleCowAlternativeRequest]:
        seen: set[str] = set()
        normalized: list[PurpleCowAlternativeRequest] = []
        for item in value:
            key = item.name.casefold().strip()
            if key not in seen:
                seen.add(key)
                normalized.append(item)
        if not normalized:
            raise ValueError("At least one distinct alternative is required")
        return normalized

    @field_validator("evidence_notes")
    @classmethod
    def normalize_evidence_notes(cls, value: list[str]) -> list[str]:
        notes = list(dict.fromkeys(item.strip() for item in value if item and item.strip()))
        if any(len(item) > 1200 for item in notes):
            raise ValueError("Each evidence note must be at most 1200 characters")
        return notes


class SEOAuditRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)

    @field_validator("url")
    @classmethod
    def validate_public_http_url(cls, value: str) -> str:
        normalized = value.strip()
        try:
            parsed = urlparse(normalized)
            host = (parsed.hostname or "").lower().rstrip(".")
        except ValueError as exc:
            raise ValueError("Provide a valid absolute public HTTP(S) URL") from exc
        if parsed.scheme not in {"http", "https"} or not host:
            raise ValueError("Provide a valid absolute public HTTP(S) URL")
        if parsed.username or parsed.password:
            raise ValueError("URLs containing credentials are not allowed")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Local/private hostnames are not allowed")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private, loopback, link-local, multicast or reserved URL hosts are not allowed")
        return normalized


class InfographicRequest(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    subtitle: str = Field(default="", max_length=180)
    audience: str = Field(default="", max_length=120)
    key_points: list[str] = Field(min_length=3, max_length=6)
    source_urls: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("title", "subtitle", "audience")
    @classmethod
    def normalize_infographic_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized and value:
            raise ValueError("Text must not be blank")
        return normalized

    @field_validator("key_points")
    @classmethod
    def normalize_infographic_points(cls, value: list[str]) -> list[str]:
        points = list(dict.fromkeys(" ".join(item.split()) for item in value if item and item.strip()))
        if not 3 <= len(points) <= 6:
            raise ValueError("Provide between three and six distinct infographic points")
        if any(len(item) > 220 for item in points):
            raise ValueError("Each infographic point must be at most 220 characters")
        return points

    @field_validator("source_urls")
    @classmethod
    def validate_infographic_source_urls(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip() for item in value if item and item.strip()))
        for url in normalized:
            if len(url) > 2048:
                raise ValueError("Each source reference URL must be at most 2048 characters")
            try:
                parsed = urlparse(url)
                host = (parsed.hostname or "").lower().rstrip(".")
            except ValueError as exc:
                raise ValueError("Source references must be valid absolute HTTP(S) URLs") from exc
            if parsed.scheme not in {"http", "https"} or not host:
                raise ValueError("Source references must be valid absolute HTTP(S) URLs")
            if parsed.username or parsed.password:
                raise ValueError("Source reference URLs may not contain credentials")
            if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
                raise ValueError("Local/private source reference hosts are not allowed")
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError("Private, loopback, link-local, multicast or reserved source reference hosts are not allowed")
        return normalized


class GuaranteeDraftRequest(BaseModel):
    product_name: str = Field(min_length=2, max_length=200)
    guarantee_type: Literal["refund", "replacement", "repair", "trial", "service_credit", "other"]
    duration_days: int = Field(ge=1, le=3650)
    eligibility: str = Field(min_length=5, max_length=800)
    exclusions: list[str] = Field(default_factory=list, max_length=10)
    claim_process: str = Field(min_length=5, max_length=800)
    merchant_terms_text: str = Field(min_length=30, max_length=6000)
    source_url: str | None = Field(default=None, max_length=2048)

    @field_validator("product_name", "eligibility", "claim_process", "merchant_terms_text")
    @classmethod
    def normalize_guarantee_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Guarantee draft fields must not be blank")
        return normalized

    @field_validator("exclusions")
    @classmethod
    def normalize_guarantee_exclusions(cls, value: list[str]) -> list[str]:
        exclusions = list(dict.fromkeys(" ".join(item.split()) for item in value if item and item.strip()))
        if any(len(item) > 500 for item in exclusions):
            raise ValueError("Each exclusion must be at most 500 characters")
        return exclusions

    @field_validator("source_url")
    @classmethod
    def validate_guarantee_source_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        try:
            parsed = urlparse(normalized)
            host = (parsed.hostname or "").lower().rstrip(".")
        except ValueError as exc:
            raise ValueError("Provide a valid absolute public HTTP(S) source URL") from exc
        if parsed.scheme not in {"http", "https"} or not host:
            raise ValueError("Source URL must be absolute HTTP(S)")
        if parsed.username or parsed.password:
            raise ValueError("Source URLs may not contain credentials")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Local/private source hosts are not allowed")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private, loopback, link-local, multicast or reserved source hosts are not allowed")
        return normalized


class CategoryDesignRequest(BaseModel):
    niche: str = Field(min_length=3, max_length=160)
    target_audience: str = Field(min_length=2, max_length=300)
    topic_candidates: list[str] = Field(min_length=3, max_length=15)
    existing_categories: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("niche", "target_audience")
    @classmethod
    def normalize_category_context(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Niche and target audience must not be blank")
        return normalized

    @field_validator("topic_candidates")
    @classmethod
    def normalize_topic_candidates(cls, value: list[str]) -> list[str]:
        topics = list(dict.fromkeys(" ".join(item.split()) for item in value if item and item.strip()))
        if not 3 <= len(topics) <= 15:
            raise ValueError("Provide between three and fifteen distinct topic candidates")
        if any(len(topic) > 120 for topic in topics):
            raise ValueError("Each topic candidate must be at most 120 characters")
        return topics

    @field_validator("existing_categories")
    @classmethod
    def normalize_existing_categories(cls, value: list[str]) -> list[str]:
        categories = list(dict.fromkeys(" ".join(item.split()) for item in value if item and item.strip()))
        if len(categories) > 30 or any(len(category) > 120 for category in categories):
            raise ValueError("Supply at most 30 existing category names of up to 120 characters each")
        return categories


def _validate_content_decay_public_url(value: str) -> str:
    normalized = value.strip()
    try:
        parsed = urlparse(normalized)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Provide a valid absolute public HTTP(S) URL") from exc
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Provide a valid absolute public HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
        raise ValueError("Local/private hostnames are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private, loopback, link-local, multicast or reserved URL hosts are not allowed")
    return normalized


def _content_decay_origin(value: str) -> tuple[str, str, int]:
    parsed = urlparse(value)
    scheme = parsed.scheme.lower()
    return (scheme, (parsed.hostname or "").lower().rstrip("."), parsed.port or (443 if scheme == "https" else 80))


class AffiliatePortfolioProgram(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    affiliate_url: str | None = Field(default=None, max_length=2048)
    reward_type: Literal["cps_recurring", "cps_one_time", "cps_lifetime", "cpl", "cpc", "other"] = "other"
    reward_value: str = Field(default="", max_length=160)
    monthly_revenue: float | None = Field(default=None, ge=0, le=1_000_000_000_000)
    monthly_clicks: int | None = Field(default=None, ge=0, le=1_000_000_000_000)
    niche: str = Field(default="", max_length=200)
    status: Literal["active", "paused", "new", "considering"] = "active"
    effort_hours_week: float | None = Field(default=None, ge=0, le=168)

    @field_validator("name", "reward_value", "niche")
    @classmethod
    def normalize_portfolio_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("affiliate_url")
    @classmethod
    def validate_affiliate_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        try:
            parsed = urlparse(normalized)
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Provide a valid public HTTP(S) affiliate URL") from exc
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            raise ValueError("Provide a public HTTP(S) affiliate URL without credentials")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Local/private affiliate URLs are not accepted")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private, loopback, link-local, multicast or reserved affiliate URL hosts are not accepted")
        return normalized


class MultiProgramManagerRequest(BaseModel):
    programs: list[AffiliatePortfolioProgram] = Field(min_length=1, max_length=30)
    goal: Literal["maximize_revenue", "diversify", "reduce_risk", "find_gaps"] = "maximize_revenue"
    budget_hours: float = Field(default=10, gt=0, le=80)

    @field_validator("programs")
    @classmethod
    def require_unique_program_names(cls, value: list[AffiliatePortfolioProgram]) -> list[AffiliatePortfolioProgram]:
        names = [" ".join(item.name.split()).casefold() for item in value]
        if len(names) != len(set(names)):
            raise ValueError("Each affiliate program must have a unique name")
        return value


class TrafficSourceBreakdown(BaseModel):
    direct: float | None = Field(default=None, ge=0, le=100)
    search: float | None = Field(default=None, ge=0, le=100)
    social: float | None = Field(default=None, ge=0, le=100)
    referral: float | None = Field(default=None, ge=0, le=100)
    paid: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_source_shares(self) -> "TrafficSourceBreakdown":
        values = [self.direct, self.search, self.social, self.referral, self.paid]
        supplied = [value for value in values if value is not None]
        if len(supplied) == len(values) and not 90 <= sum(supplied) <= 110:
            raise ValueError("Complete traffic-source shares must total 100% (allowing 10 points of rounding)")
        if supplied and sum(supplied) > 105:
            raise ValueError("Supplied traffic-source percentages cannot total over 105%")
        return self


class TrafficDomainRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=253)
    global_rank: int | None = Field(default=None, ge=1, le=1_000_000_000_000)
    country_rank: int | None = Field(default=None, ge=1, le=1_000_000_000_000)
    country: str = Field(default="", max_length=100)
    monthly_visits: int | None = Field(default=None, ge=0, le=1_000_000_000_000)
    visits_trend: Literal["growing", "stable", "declining", "unknown"] = "unknown"
    pages_per_visit: float | None = Field(default=None, ge=0, le=1000)
    avg_duration_seconds: int | None = Field(default=None, ge=0, le=86_400)
    bounce_rate: float | None = Field(default=None, ge=0, le=100)
    traffic_sources: TrafficSourceBreakdown = Field(default_factory=TrafficSourceBreakdown)
    provider_note: str = Field(default="", max_length=400)

    @field_validator("domain")
    @classmethod
    def normalize_traffic_domain(cls, value: str) -> str:
        candidate = value.strip()
        if "://" not in candidate:
            candidate = "https://" + candidate
        try:
            parsed = urlparse(candidate)
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Provide a public domain without credentials or a port") from exc
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password or port is not None:
            raise ValueError("Provide a public domain without credentials or a port")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("Enter a domain only, without a path, query or fragment")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Private/local domains are not accepted")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private, loopback, link-local, multicast or reserved IP addresses are not accepted")
        if "." not in host or " " in host or ".." in host or host.startswith(".") or host.endswith("."):
            raise ValueError("Provide a fully qualified public domain")
        return host

    @field_validator("country", "provider_note")
    @classmethod
    def normalize_traffic_text(cls, value: str) -> str:
        return " ".join(value.split())


class TrafficAnalysisRequest(BaseModel):
    domains: list[TrafficDomainRequest] = Field(min_length=1, max_length=5)
    focus: Literal["affiliate", "competitor", "advertiser"] = "affiliate"
    compare: bool | None = None

    @field_validator("domains")
    @classmethod
    def require_unique_domains(cls, value: list[TrafficDomainRequest]) -> list[TrafficDomainRequest]:
        domains = [item.domain.casefold() for item in value]
        if len(domains) != len(set(domains)):
            raise ValueError("Each domain must appear only once")
        return value


class ContentMoatCompetitorRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=253)
    pages_on_topic: int = Field(ge=0, le=100_000)
    content_quality: Literal["thin", "average", "deep"] = "average"
    freshness: Literal["stale", "recent", "actively_updated"] = "recent"
    evidence_note: str = Field(default="", max_length=400)

    @field_validator("domain")
    @classmethod
    def normalize_public_competitor_domain(cls, value: str) -> str:
        candidate = value.strip()
        if "://" not in candidate:
            candidate = "https://" + candidate
        try:
            parsed = urlparse(candidate)
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Provide a valid public competitor domain without credentials or a port") from exc
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password or port is not None:
            raise ValueError("Provide a valid public competitor domain without credentials or a port")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("Enter a domain only, without a path, query or fragment")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Private/local competitor domains are not accepted")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private, loopback, link-local, multicast or reserved IP addresses are not accepted")
        if "." not in host or " " in host or ".." in host or host.startswith(".") or host.endswith("."):
            raise ValueError("Provide a fully qualified public competitor domain")
        return host

    @field_validator("evidence_note")
    @classmethod
    def normalize_evidence_note(cls, value: str) -> str:
        return " ".join(value.split())


class ContentMoatRequest(BaseModel):
    niche: str = Field(min_length=3, max_length=200)
    hub_keyword: str = Field(default="", max_length=200)
    your_current_pages: int = Field(default=0, ge=0, le=100_000)
    publishing_capacity: Literal["1/week", "2/week", "3/week", "5/week"] = "2/week"
    competitors: list[ContentMoatCompetitorRequest] = Field(min_length=1, max_length=5)

    @field_validator("niche", "hub_keyword")
    @classmethod
    def normalize_moat_context(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized and value:
            raise ValueError("Context must not be blank")
        return normalized

    @field_validator("competitors")
    @classmethod
    def require_distinct_competitors(cls, value: list[ContentMoatCompetitorRequest]) -> list[ContentMoatCompetitorRequest]:
        domains = [item.domain.casefold() for item in value]
        if len(set(domains)) != len(domains):
            raise ValueError("Each competitor domain must be unique")
        return value


class ContentDecayPageRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    title: str = Field(default="", max_length=300)
    publish_date: date | None = None
    last_updated: date | None = None
    target_keyword: str = Field(default="", max_length=200)
    previous_clicks: int | None = Field(default=None, ge=0, le=1_000_000_000_000)
    current_clicks: int | None = Field(default=None, ge=0, le=1_000_000_000_000)
    previous_impressions: int | None = Field(default=None, ge=0, le=1_000_000_000_000)
    current_impressions: int | None = Field(default=None, ge=0, le=1_000_000_000_000)
    previous_avg_position: float | None = Field(default=None, ge=1, le=10_000)
    current_avg_position: float | None = Field(default=None, ge=1, le=10_000)
    contains_affiliate_links: bool | None = None
    revenue_impact: Literal["high", "medium", "low", "unknown"] = "unknown"
    outdated_elements: list[str] = Field(default_factory=list, max_length=10)
    competitor_refresh_observed: bool | None = None
    competitor_note: str = Field(default="", max_length=800)
    serp_displacement_observed: bool | None = None
    refresh_effort_hours: float | None = Field(default=None, gt=0, le=160)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _validate_content_decay_public_url(value)

    @field_validator("title", "target_keyword", "competitor_note")
    @classmethod
    def normalize_optional_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("outdated_elements")
    @classmethod
    def normalize_outdated_elements(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(" ".join(item.split()) for item in value if item and item.strip()))
        if any(len(item) > 400 for item in normalized):
            raise ValueError("Each outdated-content note must be at most 400 characters")
        return normalized

    @model_validator(mode="after")
    def validate_comparison_pairs_and_dates(self) -> "ContentDecayPageRequest":
        for label, previous, current in (
            ("clicks", self.previous_clicks, self.current_clicks),
            ("impressions", self.previous_impressions, self.current_impressions),
            ("average position", self.previous_avg_position, self.current_avg_position),
        ):
            if (previous is None) != (current is None):
                raise ValueError(f"Previous and current {label} values must be supplied together")
        if self.publish_date and self.last_updated and self.last_updated < self.publish_date:
            raise ValueError("Last-updated date cannot be earlier than publish date")
        return self


class ContentDecayRequest(BaseModel):
    site_url: str = Field(min_length=8, max_length=2048)
    timeframe: Literal["30d", "90d", "6m", "1y"] = "90d"
    pages: list[ContentDecayPageRequest] = Field(min_length=1, max_length=30)

    @field_validator("site_url")
    @classmethod
    def validate_site_url(cls, value: str) -> str:
        return _validate_content_decay_public_url(value)

    @field_validator("pages")
    @classmethod
    def reject_duplicate_urls(cls, value: list[ContentDecayPageRequest]) -> list[ContentDecayPageRequest]:
        urls = [page.url.rstrip("/") for page in value]
        if len(set(urls)) != len(urls):
            raise ValueError("Each content page URL must be unique")
        return value

    @model_validator(mode="after")
    def enforce_site_origin(self) -> "ContentDecayRequest":
        expected = _content_decay_origin(self.site_url)
        if any(_content_decay_origin(page.url) != expected for page in self.pages):
            raise ValueError("All content page URLs must share the same public origin as site_url")
        return self


class InternalLinkingRequest(BaseModel):
    urls: list[str] = Field(min_length=2, max_length=12)
    max_suggestions_per_page: int = Field(default=5, ge=1, le=10)

    @field_validator("urls")
    @classmethod
    def validate_same_origin_public_urls(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip() for item in value if item and item.strip()))
        if len(normalized) < 2:
            raise ValueError("Supply at least two distinct public page URLs")
        if len(normalized) > 12:
            raise ValueError("At most twelve page URLs may be analyzed at once")

        origins: set[tuple[str, str, int]] = set()
        for url in normalized:
            if len(url) > 2048:
                raise ValueError("Each URL must be at most 2048 characters")
            try:
                parsed = urlparse(url)
                host = (parsed.hostname or "").lower().rstrip(".")
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
            except ValueError as exc:
                raise ValueError("Provide valid absolute HTTP(S) URLs") from exc
            if parsed.scheme not in {"http", "https"} or not host:
                raise ValueError("Provide valid absolute HTTP(S) URLs")
            if parsed.username or parsed.password:
                raise ValueError("URLs containing credentials are not allowed")
            if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
                raise ValueError("Local/private hostnames are not allowed")
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError("Private, loopback, link-local, multicast or reserved hosts are not allowed")
            origins.add((parsed.scheme.lower(), host, port))

        if len(origins) != 1:
            raise ValueError("All supplied pages must share the same public HTTP(S) origin")
        return normalized


class ProprietaryDatasetRequest(BaseModel):
    """Controls for a review-required dataset snapshot from the experiment ledger."""

    dataset_name: str = Field(
        default="Proprietary experiment learning candidates",
        min_length=3,
        max_length=180,
    )
    min_impressions: int = Field(default=100, ge=1, le=1_000_000)
    min_conversions: int = Field(default=5, ge=1, le=100_000)
    max_assignments: int = Field(default=5000, ge=1, le=10_000)
    max_events: int = Field(default=50000, ge=1, le=100_000)


class WebinarAgendaItem(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=700)

    @field_validator("title")
    @classmethod
    def agenda_title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Agenda title must not be blank")
        return value


class WebinarCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=10, max_length=600)
    description: str = Field(min_length=30, max_length=8000)
    host_name: str = Field(min_length=2, max_length=200)
    host_bio: str | None = Field(default=None, max_length=3000)
    start_at: datetime
    end_at: datetime
    timezone_name: str = Field(default="UTC", min_length=1, max_length=100)
    registration_deadline: datetime | None = None
    capacity: int | None = Field(default=None, ge=1, le=1_000_000)
    agenda_items: list[WebinarAgendaItem] = Field(default_factory=list, max_length=20)
    privacy_policy_url: str = Field(min_length=8, max_length=2048)
    consent_text: str = Field(min_length=12, max_length=1200,
        default="I agree that my registration details may be used to administer this webinar.")
    affiliate_disclosure: str | None = Field(default=None, max_length=1200)

    @field_validator("title", "summary", "description", "host_name", "consent_text")
    @classmethod
    def required_webinar_text_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value

    @field_validator("timezone_name")
    @classmethod
    def valid_timezone_name(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        value = value.strip()
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone_name must be a valid IANA timezone") from exc
        return value

    @field_validator("privacy_policy_url")
    @classmethod
    def valid_privacy_url(cls, value: str) -> str:
        parts = urlparse(value.strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise ValueError("privacy_policy_url must be an absolute HTTP(S) URL without credentials")
        return value.strip()

    @model_validator(mode="after")
    def valid_event_window(self):
        for name in ("start_at", "end_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must include a timezone offset")
        if self.start_at >= self.end_at:
            raise ValueError("end_at must be after start_at")
        if self.start_at <= datetime.now(timezone.utc):
            raise ValueError("start_at must be in the future")
        if self.registration_deadline is not None:
            if self.registration_deadline.tzinfo is None or self.registration_deadline.utcoffset() is None:
                raise ValueError("registration_deadline must include a timezone offset")
            if self.registration_deadline > self.start_at:
                raise ValueError("registration_deadline cannot be after start_at")
        return self


class WebinarRegistrationRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=5, max_length=320)
    consent: bool
    marketing_consent: bool = False

    @field_validator("full_name")
    @classmethod
    def normalized_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Full name must not be blank")
        return value

    @field_validator("email")
    @classmethod
    def normalized_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("consent")
    @classmethod
    def require_registration_consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Explicit registration consent is required")
        return value


class ProgramApplicationComplianceAnswers(BaseModel):
    affiliate_disclosure_ready: bool = False
    program_traffic_terms_reviewed: bool = False
    geography_restrictions_reviewed: bool = False
    privacy_and_consent_controls_ready: bool = False
    claims_substantiation_process_ready: bool = False


class ProgramApplicationCreateRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=160)
    program_name: str = Field(min_length=2, max_length=240)
    program_url: str = Field(min_length=8, max_length=2048)
    publisher_website_url: str = Field(min_length=8, max_length=2048)
    audience_description: str = Field(min_length=30, max_length=3000)
    monthly_visitors: int | None = Field(default=None, ge=0, le=1_000_000_000)
    traffic_sources: list[Literal["seo", "blog", "organic_social", "paid_search", "paid_social", "email_opt_in", "video", "influencer", "community", "referral", "other"]] = Field(min_length=1, max_length=11)
    promotion_channels: list[Literal["website", "blog", "newsletter", "social", "video", "search_ads", "social_ads", "comparison_content", "community", "other"]] = Field(min_length=1, max_length=10)
    primary_regions: list[str] = Field(min_length=1, max_length=30)
    promotion_plan: str = Field(min_length=80, max_length=6000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=10)
    compliance_answers: ProgramApplicationComplianceAnswers = Field(default_factory=ProgramApplicationComplianceAnswers)

    @field_validator("provider", "program_name", "audience_description", "promotion_plan")
    @classmethod
    def normalize_application_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field must not be blank")
        return normalized

    @field_validator("program_url", "publisher_website_url")
    @classmethod
    def validate_application_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Application URLs must be absolute HTTP(S) URLs without embedded credentials")
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Local or internal URLs are not valid application destinations")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private or reserved IP addresses are not valid application destinations")
        return value.strip()

    @field_validator("evidence_urls")
    @classmethod
    def validate_application_evidence_urls(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip() for value in values))
        for value in normalized:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Evidence references must be absolute HTTP(S) URLs without embedded credentials")
            host = parsed.hostname.lower().rstrip(".")
            if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
                raise ValueError("Local or internal evidence URLs are not allowed")
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError("Private or reserved evidence URLs are not allowed")
        return normalized

    @field_validator("primary_regions")
    @classmethod
    def normalize_regions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip().upper() for value in values if value and value.strip()))
        if not normalized or any(len(value) > 80 for value in normalized):
            raise ValueError("Provide one or more non-empty regions of at most 80 characters")
        return normalized

    @field_validator("traffic_sources", "promotion_channels")
    @classmethod
    def require_unique_options(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Choose each source/channel only once")
        return values


class ProgramApplicationReviewRequest(BaseModel):
    decision: Literal["approve_for_manual_handoff", "reject"]
    reviewer_notes: str = Field(default="", max_length=3000)

    @field_validator("reviewer_notes")
    @classmethod
    def normalize_reviewer_notes(cls, value: str) -> str:
        return value.strip()


class MerchantOfferCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=240)
    product_url: str = Field(min_length=8, max_length=2048)
    description: str = Field(min_length=30, max_length=6000)
    category: str = Field(min_length=2, max_length=160)
    commission_type: Literal["percentage", "fixed", "recurring_percentage", "recurring_fixed", "cpa", "cpl"]
    commission_value: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    commission_currency: str = Field(default="USD", min_length=3, max_length=3)
    terms_version: str = Field(min_length=1, max_length=120)
    commission_terms_url: str = Field(min_length=8, max_length=2048)
    seller_authorization_url: str = Field(min_length=8, max_length=2048)
    allowed_regions: list[str] = Field(min_length=1, max_length=50)
    restricted_traffic_sources: list[str] = Field(default_factory=list, max_length=30)
    affiliate_disclosure: str = Field(min_length=12, max_length=1200)

    @field_validator("name", "description", "category", "terms_version", "affiliate_disclosure")
    @classmethod
    def normalize_merchant_offer_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value

    @field_validator("product_url", "commission_terms_url", "seller_authorization_url")
    @classmethod
    def validate_merchant_offer_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("URLs must be absolute HTTP(S) URLs without embedded credentials")
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Local or internal URLs are not valid evidence references")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private or reserved IP addresses are not valid destinations")
        return value.strip()

    @field_validator("commission_currency")
    @classmethod
    def normalize_merchant_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", normalized):
            raise ValueError("Currency must be a three-letter ISO currency code")
        return normalized

    @field_validator("allowed_regions")
    @classmethod
    def normalize_merchant_regions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip().upper() for value in values if value and value.strip()))
        if not normalized or any(len(value) > 80 for value in normalized):
            raise ValueError("Provide one or more non-empty region identifiers")
        return normalized

    @field_validator("restricted_traffic_sources")
    @classmethod
    def normalize_merchant_traffic_sources(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip().lower() for value in values if value and value.strip()))
        if any(len(value) > 80 for value in normalized):
            raise ValueError("Traffic-source identifiers must be at most 80 characters")
        return normalized

    @model_validator(mode="after")
    def validate_commission_range(self):
        if self.commission_type in {"percentage", "recurring_percentage"} and self.commission_value > Decimal("100"):
            raise ValueError("Percentage commission cannot exceed 100")
        return self


class MerchantOfferReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "suspend"]
    seller_authorization_verified: bool = False
    commission_terms_verified: bool = False
    reviewer_notes: str = Field(default="", max_length=3000)

    @field_validator("reviewer_notes")
    @classmethod
    def normalize_merchant_review_notes(cls, value: str) -> str:
        return value.strip()


class MerchantOfferTermSnapshotCreateRequest(BaseModel):
    terms_version: str = Field(min_length=1, max_length=120)
    commission_type: Literal["percentage", "fixed", "recurring_percentage", "recurring_fixed", "cpa", "cpl"]
    commission_value: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    commission_currency: str = Field(default="USD", min_length=3, max_length=3)
    cookie_days: int | None = Field(default=None, ge=0, le=3650)
    attribution_window_days: int | None = Field(default=None, ge=0, le=3650)
    allowed_regions: list[str] = Field(min_length=1, max_length=50)
    restricted_traffic_sources: list[str] = Field(default_factory=list, max_length=30)
    source_url: str | None = Field(default=None, min_length=8, max_length=2048)
    evidence_type: Literal["operator_observed", "merchant_claim", "network_reported", "manual_import"] = "operator_observed"
    evidence_excerpt: str = Field(default="", max_length=4000)
    observed_at: datetime | None = None

    @field_validator("terms_version")
    @classmethod
    def normalize_term_snapshot_version(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Terms version must not be blank")
        return normalized

    @field_validator("commission_currency")
    @classmethod
    def normalize_term_snapshot_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", normalized):
            raise ValueError("Currency must be a three-letter ISO currency code")
        return normalized

    @field_validator("allowed_regions")
    @classmethod
    def normalize_term_snapshot_regions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip().upper() for value in values if value and value.strip()))
        if not normalized or any(len(value) > 80 for value in normalized):
            raise ValueError("Provide one or more non-empty region identifiers")
        return normalized

    @field_validator("restricted_traffic_sources")
    @classmethod
    def normalize_term_snapshot_traffic(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip().lower() for value in values if value and value.strip()))
        if any(len(value) > 80 for value in normalized):
            raise ValueError("Traffic-source identifiers must be at most 80 characters")
        return normalized

    @field_validator("source_url")
    @classmethod
    def validate_term_snapshot_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Evidence URL must be absolute HTTP(S) without embedded credentials")
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Local or internal URLs are not valid evidence references")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private or reserved IP addresses are not valid evidence references")
        return value.strip()

    @field_validator("evidence_excerpt")
    @classmethod
    def normalize_term_evidence_excerpt(cls, value: str) -> str:
        return value.strip()

    @field_validator("observed_at")
    @classmethod
    def require_aware_term_observation_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_term_snapshot_commission_range(self):
        if self.commission_type in {"percentage", "recurring_percentage"} and self.commission_value > Decimal("100"):
            raise ValueError("Percentage commission cannot exceed 100")
        return self


class MerchantOfferTermEvidenceReviewRequest(BaseModel):
    decision: Literal["no_material_change", "material_change_found", "source_unreliable"]
    reviewer_notes: str = Field(min_length=10, max_length=3000)

    @field_validator("reviewer_notes")
    @classmethod
    def normalize_terms_evidence_review_notes(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 10:
            raise ValueError("Reviewer notes must contain at least 10 non-whitespace characters")
        return normalized


class MarketplaceApplicationCreateRequest(BaseModel):
    publisher_website_url: str = Field(min_length=8, max_length=2048)
    audience_description: str = Field(min_length=30, max_length=3000)
    traffic_sources: list[Literal["seo", "blog", "organic_social", "paid_search", "paid_social", "email_opt_in", "video", "influencer", "community", "referral", "other"]] = Field(min_length=1, max_length=11)
    intended_regions: list[str] = Field(min_length=1, max_length=50)
    promotion_plan: str = Field(min_length=80, max_length=6000)
    offer_terms_reviewed: bool = False
    traffic_restrictions_reviewed: bool = False
    affiliate_disclosure_ready: bool = False
    contact_sharing_consent: bool = False

    @field_validator("publisher_website_url")
    @classmethod
    def validate_marketplace_publisher_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Publisher website must be an absolute HTTP(S) URL without embedded credentials")
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Local or internal publisher URLs are not valid")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private or reserved publisher URLs are not valid")
        return value.strip()

    @field_validator("audience_description", "promotion_plan")
    @classmethod
    def normalize_marketplace_application_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field must not be blank")
        return normalized

    @field_validator("traffic_sources")
    @classmethod
    def normalize_marketplace_traffic_sources(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip().lower() for value in values if value and value.strip()))
        if not normalized or any(len(value) > 80 for value in normalized):
            raise ValueError("Choose one or more valid traffic-source identifiers")
        return normalized

    @field_validator("intended_regions")
    @classmethod
    def normalize_marketplace_regions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip().upper() for value in values if value and value.strip()))
        if not normalized or any(len(value) > 80 for value in normalized):
            raise ValueError("Provide one or more non-empty region identifiers")
        return normalized

    @field_validator("offer_terms_reviewed", "traffic_restrictions_reviewed", "affiliate_disclosure_ready", "contact_sharing_consent")
    @classmethod
    def require_marketplace_readiness_attestations(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Offer terms, traffic restrictions, disclosure readiness and contact-sharing consent are required")
        return value


class MarketplaceApplicationReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reviewer_notes: str = Field(default="", max_length=3000)

    @field_validator("reviewer_notes")
    @classmethod
    def normalize_marketplace_review_notes(cls, value: str) -> str:
        return value.strip()


class AdBudgetGuardrailCreateRequest(BaseModel):
    daily_spend_cap_usd: Decimal = Field(gt=0, le=Decimal("1000000.00"), max_digits=12, decimal_places=2)
    campaign_spend_cap_usd: Decimal = Field(gt=0, le=Decimal("10000000.00"), max_digits=12, decimal_places=2)
    minimum_roas: Decimal = Field(default=Decimal("1.20"), ge=0, le=Decimal("100.0000"), max_digits=8, decimal_places=4)
    maximum_cpa_usd: Decimal | None = Field(default=None, gt=0, le=Decimal("1000000.00"), max_digits=12, decimal_places=2)
    minimum_verified_impressions: int = Field(default=1000, ge=1, le=1_000_000)
    minimum_verified_clicks: int = Field(default=30, ge=1, le=100_000)
    minimum_verified_conversions: int = Field(default=3, ge=1, le=100_000)

    @model_validator(mode="after")
    def campaign_cap_not_below_daily_cap(self):
        if self.campaign_spend_cap_usd < self.daily_spend_cap_usd:
            raise ValueError("Campaign spend cap must be at least the daily spend cap")
        return self


class AdGuardrailResetRequest(BaseModel):
    confirm_reset: bool = False
    reason: str = Field(min_length=20, max_length=2000)

    @field_validator("reason")
    @classmethod
    def normalize_reset_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 20:
            raise ValueError("Provide a specific reset rationale of at least 20 characters")
        return normalized


class SignedAdPerformanceWebhookPayload(BaseModel):
    """Normalized event sent by a configured trusted collector after platform-side verification."""
    provider_event_id: str = Field(min_length=1, max_length=255)
    campaign_plan_id: str = Field(min_length=1, max_length=36)
    platform: AdPlatform
    creative_id: str = Field(min_length=1, max_length=180)
    source_reference_url: str | None = Field(default=None, max_length=2048)
    impressions: int = Field(default=0, ge=0, le=1_000_000_000_000)
    clicks: int = Field(default=0, ge=0, le=1_000_000_000_000)
    conversions: int = Field(default=0, ge=0, le=1_000_000_000_000)
    spend_usd: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    commission_usd: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    observed_at: datetime
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("provider_event_id", "campaign_plan_id", "creative_id")
    @classmethod
    def normalize_signed_event_identifiers(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Identifier must not be blank")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_signed_ad_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", normalized):
            raise ValueError("Currency must be a three-letter alphabetic code")
        return normalized

    @field_validator("observed_at")
    @classmethod
    def require_signed_event_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include an explicit timezone offset")
        return value.astimezone(timezone.utc)

    @field_validator("source_reference_url")
    @classmethod
    def validate_signed_source_reference(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        try:
            parsed = urlparse(normalized)
            host = (parsed.hostname or "").lower().rstrip(".")
        except ValueError as exc:
            raise ValueError("Source reference must be a valid public HTTP(S) URL") from exc
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            raise ValueError("Source reference must be an absolute HTTP(S) URL without credentials")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Local/private source references are not allowed")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private, loopback, link-local, multicast or reserved source references are not allowed")
        return normalized

# Evidence-backed, human-reviewed jurisdiction compliance assessments.
ComplianceActivity = Literal[
    "affiliate_promotion",
    "content_publish",
    "paid_media",
    "email_marketing",
    "lead_capture",
    "tracking_analytics",
    "merchant_marketplace",
]


class JurisdictionComplianceRuleEvidence(BaseModel):
    """One cited source record; this is evidence for review, not an automated legal conclusion."""

    jurisdiction_code: str = Field(min_length=2, max_length=12)
    category: str = Field(min_length=2, max_length=80)
    source_title: str = Field(min_length=3, max_length=300)
    source_url: str = Field(min_length=12, max_length=2048)
    rule_summary: str = Field(min_length=20, max_length=4000)
    effective_date: date | None = None
    reviewed_at: datetime
    reviewer_attestation: bool = False

    @field_validator("jurisdiction_code")
    @classmethod
    def normalize_evidence_jurisdiction(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"(?:[A-Z]{2}(?:-[A-Z0-9]{1,6})?|EU|EEA|GLOBAL)", normalized):
            raise ValueError("Use an ISO-style country/subdivision code or EU, EEA, GLOBAL")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_evidence_category(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,79}", normalized):
            raise ValueError("Evidence category must be a lowercase identifier")
        return normalized

    @field_validator("source_title", "rule_summary")
    @classmethod
    def normalize_evidence_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Evidence text must not be blank")
        return normalized

    @field_validator("source_url")
    @classmethod
    def require_public_https_source(cls, value: str) -> str:
        normalized = value.strip()
        try:
            parsed = urlparse(normalized)
            host = (parsed.hostname or "").lower().rstrip(".")
        except ValueError as exc:
            raise ValueError("Evidence source must be a valid HTTPS URL") from exc
        if parsed.scheme.lower() != "https" or not host or parsed.username or parsed.password:
            raise ValueError("Evidence sources must use absolute HTTPS URLs without credentials")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
            raise ValueError("Local/private evidence sources are not allowed")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Evidence sources cannot use private, loopback, link-local or reserved IP addresses")
        return normalized

    @field_validator("reviewed_at")
    @classmethod
    def require_explicit_evidence_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Evidence reviewed_at must include an explicit timezone offset")
        return value.astimezone(timezone.utc)


class JurisdictionComplianceAssessmentCreateRequest(BaseModel):
    activity: ComplianceActivity
    channels: list[str] = Field(min_length=1, max_length=50)
    jurisdictions: list[str] = Field(min_length=1, max_length=50)
    rule_evidence: list[JurisdictionComplianceRuleEvidence] = Field(default_factory=list, max_length=1000)
    operator_notes: str = Field(default="", max_length=4000)

    @field_validator("channels")
    @classmethod
    def normalize_compliance_channels(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(value).strip().lower() for value in values if str(value).strip()))
        if not normalized or any(not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,59}", value) for value in normalized):
            raise ValueError("Choose one or more valid channel identifiers")
        return normalized

    @field_validator("jurisdictions")
    @classmethod
    def normalize_compliance_jurisdictions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
        if not normalized or any(not re.fullmatch(r"(?:[A-Z]{2}(?:-[A-Z0-9]{1,6})?|EU|EEA|GLOBAL)", value) for value in normalized):
            raise ValueError("Target jurisdictions must use ISO-style country/subdivision codes or EU, EEA, GLOBAL")
        return normalized

    @field_validator("operator_notes")
    @classmethod
    def normalize_compliance_operator_notes(cls, value: str) -> str:
        return value.strip()


class JurisdictionComplianceAssessmentReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    confirm_scope_reviewed: bool = False
    reviewer_notes: str = Field(default="", max_length=4000)

    @field_validator("reviewer_notes")
    @classmethod
    def normalize_compliance_reviewer_notes(cls, value: str) -> str:
        return value.strip()



# Governed skill packaging. These schemas describe contracts; instructions remain declarative data.
SkillStage = Literal["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]


class SkillPackageFixture(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    input: Any
    expected_output: Any

    @field_validator("name")
    @classmethod
    def normalize_fixture_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Fixture name must not be blank")
        return normalized


class SkillPackageCreateRequest(BaseModel):
    skill_id: str = Field(min_length=3, max_length=140)
    display_name: str = Field(min_length=3, max_length=180)
    version: str = Field(min_length=5, max_length=40)
    description: str = Field(min_length=10, max_length=3000)
    stage: SkillStage
    runtime_handler: Literal[
        "none",
        "content.extractive_summary",
        "research.keyword_extract",
        "research.offer_metrics",
        "research.commission_calculator",
        "research.offer_term_change_review",
        "ads.guardrail_review",
        "analytics.roas_calculator",
    ] = "none"
    capabilities: list[str] = Field(min_length=1, max_length=50)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    instructions_markdown: str = Field(min_length=20, max_length=50000)
    test_cases: list[SkillPackageFixture] = Field(min_length=1, max_length=50)

    @field_validator("skill_id")
    @classmethod
    def normalize_skill_id(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(?:[/-][a-z0-9]+)*", normalized):
            raise ValueError("Use a lowercase skill identifier such as analytics/offer-ranker")
        return normalized

    @field_validator("display_name", "description", "instructions_markdown")
    @classmethod
    def normalize_skill_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Skill text must not be blank")
        return normalized

    @field_validator("version")
    @classmethod
    def validate_skill_semver(cls, value: str) -> str:
        normalized = value.strip()
        if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?", normalized):
            raise ValueError("Use semantic versioning such as 1.0.0 or 1.0.0-rc.1")
        return normalized

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(value).strip().lower() for value in values if str(value).strip()))
        if not normalized or any(not re.fullmatch(r"[a-z][a-z0-9_.:-]{1,119}", value) for value in normalized):
            raise ValueError("Capabilities must be lowercase identifiers such as content.draft or analytics.read")
        return normalized


class SkillPackageExecuteRequest(BaseModel):
    input: dict[str, Any] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_bounded_json_input(self) -> "SkillPackageExecuteRequest":
        try:
            encoded = json.dumps(self.input, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("Runtime input must contain finite JSON values only") from exc
        if len(encoded.encode("utf-8")) > 32 * 1024:
            raise ValueError("Runtime input exceeds the 32 KiB execution limit")
        return self


class SkillPackageReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    confirm_contract_reviewed: bool = False
    reviewer_notes: str = Field(default="", max_length=4000)

    @field_validator("reviewer_notes")
    @classmethod
    def normalize_skill_review_notes(cls, value: str) -> str:
        return value.strip()

# Evidence-aware, disclosure-forward bio-link pages.
class BioLinkItem(BaseModel):
    label: str = Field(min_length=2, max_length=120)
    url: str = Field(min_length=10, max_length=2048)
    description: str = Field(default="", max_length=240)
    is_affiliate: bool = False

    @field_validator("label", "description")
    @classmethod
    def normalize_bio_link_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("url")
    @classmethod
    def validate_bio_link_destination(cls, value: str) -> str:
        normalized = value.strip()
        try:
            parsed = urlparse(normalized)
            host = (parsed.hostname or "").lower().rstrip(".")
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("Link destination must be a valid absolute HTTP(S) URL") from exc
        if parsed.scheme.lower() not in {"http", "https"} or not host or parsed.username or parsed.password:
            raise ValueError("Link destination must be absolute HTTP(S) without credentials")
        if host in {"localhost", "localhost.localdomain"} or host.endswith(
            (".localhost", ".local", ".internal", ".test", ".home", ".lan", ".corp")
        ):
            raise ValueError("Local/private hostnames cannot be bio-link destinations")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("Private, loopback, link-local, multicast or reserved IP destinations are not allowed")
        return normalized


class BioLinkPageCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    headline: str = Field(min_length=3, max_length=240)
    subheadline: str = Field(default="", max_length=500)
    links: list[BioLinkItem] = Field(min_length=1, max_length=50)
    affiliate_disclosure: str = Field(default="", max_length=1200)
    footer_note: str = Field(default="", max_length=600)

    @field_validator("title", "headline", "subheadline", "affiliate_disclosure", "footer_note")
    @classmethod
    def normalize_bio_page_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_disclosure_for_affiliate_links(self):
        if any(item.is_affiliate for item in self.links) and len(self.affiliate_disclosure.strip()) < 10:
            raise ValueError("Add a clear affiliate disclosure before creating a page with affiliate links")
        return self


class BioLinkPublishRequest(BaseModel):
    provider: Literal["wordpress", "ghost"]
    target_jurisdictions: list[str] = Field(default_factory=list, max_length=50)
    canonical_url: str = Field(min_length=8, max_length=2048)
    status: Literal["draft", "publish"] = "draft"
    confirm_live_publish: bool = False
    tags: list[str] = Field(default_factory=list, max_length=20)
    disclosure: str = Field(default="Disclosure: This page may contain affiliate links; I may earn a commission from qualifying purchases.", max_length=1200)

    @field_validator("target_jurisdictions")
    @classmethod
    def normalize_bio_publish_jurisdictions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
        if any(not re.fullmatch(r"(?:[A-Z]{2}(?:-[A-Z0-9]{1,6})?|EU|EEA|GLOBAL)", value) for value in normalized):
            raise ValueError("Use ISO-style country/subdivision codes or EU, EEA, GLOBAL")
        return normalized

    @field_validator("tags")
    @classmethod
    def normalize_bio_publish_tags(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))[:20]

DistributionChannel = Literal[
    "meta", "facebook", "instagram", "tiktok", "youtube", "youtube_shorts",
    "pinterest", "reddit", "quora", "x", "linkedin", "telegram",
    "whatsapp_business", "wordpress", "ghost", "email",
]


class DistributionQueueCreateRequest(BaseModel):
    content_asset_id: str = Field(min_length=36, max_length=36)
    channel: DistributionChannel
    scheduled_at: datetime | None = None

    @field_validator("scheduled_at")
    @classmethod
    def require_future_timezone_aware_schedule(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Scheduled distribution time must include a timezone")
        normalized = value.astimezone(timezone.utc)
        if normalized <= datetime.now(timezone.utc):
            raise ValueError("Scheduled distribution time must be in the future")
        return normalized


class DistributionQueueApproveRequest(BaseModel):
    confirm_content_review: bool = False
    target_jurisdictions: list[str] = Field(min_length=1, max_length=50)
    reviewer_note: str = Field(default="", max_length=4000)

    @field_validator("target_jurisdictions")
    @classmethod
    def normalize_distribution_jurisdictions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
        if not normalized or any(
            not re.fullmatch(r"(?:[A-Z]{2}(?:-[A-Z0-9]{1,6})?|EU|EEA|GLOBAL)", value)
            for value in normalized
        ):
            raise ValueError("Use ISO-style country/subdivision codes or EU, EEA, GLOBAL")
        return normalized


class DistributionQueueCancelRequest(BaseModel):
    confirm_cancel: bool = False


class GitHubPagesDeployRequest(BaseModel):
    """Deploy only an existing, generated bio-link asset to the server-configured target."""
    asset_id: str = Field(min_length=1, max_length=36)
    target_jurisdictions: list[str] = Field(min_length=1, max_length=50)
    confirm_live_publish: bool = False

    @field_validator("target_jurisdictions")
    @classmethod
    def normalize_github_pages_jurisdictions(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
        if not normalized or any(not re.fullmatch(r"(?:[A-Z]{2}(?:-[A-Z0-9]{1,6})?|EU|EEA|GLOBAL)", value) for value in normalized):
            raise ValueError("Choose target jurisdictions using ISO-style country/subdivision codes or EU, EEA, GLOBAL")
        return normalized


from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import event, Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, Session, mapped_column
from backend.database import Base
from backend.tenancy import TenantScopedMixin

JSON_VALUE = JSON

def new_id() -> str: return str(uuid.uuid4())

class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("network", "external_id", name="uq_offer_network_external"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    network: Mapped[str] = mapped_column(String(100), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(500), index=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    reward_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reward_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cookie_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    traffic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    gravity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized_gravity: Mapped[float | None] = mapped_column(Float, nullable=True)
    epc: Mapped[float | None] = mapped_column(Float, nullable=True)
    conversion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    recurring_commission: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_stars: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Campaign(TenantScopedMixin, Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(300), index=True)
    niche: Mapped[str] = mapped_column(String(200), index=True)
    primary_destination: Mapped[str] = mapped_column(Text)
    fallback_destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    tracking_parameter: Mapped[str] = mapped_column(String(80), default="subid")
    disclosure_text: Mapped[str] = mapped_column(Text, default="")
    auto_publish: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_daily_spend: Mapped[float] = mapped_column(Float, default=0.0)
    primary_healthy: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    fallback_healthy: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    health_last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ClickEvent(TenantScopedMixin, Base):
    __tablename__ = "click_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    click_id: Mapped[str] = mapped_column(String(80), unique=True, default=lambda: uuid.uuid4().hex, index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    destination_url: Mapped[str] = mapped_column(Text)
    chosen_destination: Mapped[str] = mapped_column(Text, default="")
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    utm_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

class ExperimentAssignment(TenantScopedMixin, Base):
    __tablename__ = "experiment_assignments"
    __table_args__ = (
        Index(
            "uq_experiment_assignment_workspace_key_visitor",
            "workspace_id", "experiment_key", "visitor_id", unique=True,
        ),
        Index(
            "ix_experiment_assignment_workspace_key_variant",
            "workspace_id", "experiment_key", "variant",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    experiment_key: Mapped[str] = mapped_column(String(180))
    visitor_id: Mapped[str] = mapped_column(String(255))
    variant: Mapped[str] = mapped_column(String(1))
    headline_a: Mapped[str] = mapped_column(Text)
    headline_b: Mapped[str] = mapped_column(Text)
    assigned_headline: Mapped[str] = mapped_column(Text)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExperimentEvent(TenantScopedMixin, Base):
    __tablename__ = "experiment_events"
    __table_args__ = (
        Index("uq_experiment_event_workspace_event_id", "workspace_id", "event_id", unique=True),
        Index(
            "ix_experiment_event_workspace_assignment_type",
            "workspace_id", "assignment_id", "event_type",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experiment_assignments.id", ondelete="CASCADE")
    )
    event_id: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversion(TenantScopedMixin, Base):
    __tablename__ = "conversions"
    __table_args__ = (Index("uq_conversion_workspace_network_external_event", "workspace_id", "network", "external_event_id", unique=True), Index("ix_conversion_campaign_created", "click_id", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    network: Mapped[str] = mapped_column(String(100), index=True)
    external_event_id: Mapped[str] = mapped_column(String(255))
    click_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    utm_source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(300), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(500), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(60), default="pending", index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

class ConversionLedgerEntry(TenantScopedMixin, Base):
    """Append-only, currency-safe observation of a conversion or commission adjustment."""

    __tablename__ = "conversion_ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "network", "external_event_id",
            name="uq_conv_ledger_ws_network_event",
        ),
        Index("ix_conv_ledger_ws_created", "workspace_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    network: Mapped[str] = mapped_column(String(100), index=True)
    external_event_id: Mapped[str] = mapped_column(String(255))
    click_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    entry_type: Mapped[str] = mapped_column(String(40))
    original_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    revenue_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), index=True)
    status: Mapped[str] = mapped_column(String(60), index=True)
    evidence_status: Mapped[str] = mapped_column(String(40), index=True)
    source_event_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


@event.listens_for(Session, "before_flush")
def _guard_conversion_ledger_append_only(session: Session, flush_context, instances) -> None:
    """Prevent accidental ORM edits/deletes to historical money observations."""
    for entity in (*session.dirty, *session.deleted):
        if isinstance(entity, ConversionLedgerEntry):
            raise ValueError("Conversion ledger entries are append-only")


class WorkflowRun(TenantScopedMixin, Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow_name: Mapped[str] = mapped_column(String(180), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    execution_mode: Mapped[str] = mapped_column(String(40), default="SEMI_AUTONOMOUS")
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PausedSession(TenantScopedMixin, Base):
    __tablename__ = "paused_sessions"
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_name: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(40), default="paused", index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    required_action: Mapped[str] = mapped_column(String(100), default="verification")
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AuditLog(TenantScopedMixin, Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(320), default="system")
    action: Mapped[str] = mapped_column(String(180), index=True)
    resource_type: Mapped[str] = mapped_column(String(100), default="system")
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(80), default="ok")
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

class ContentAsset(TenantScopedMixin, Base):
    __tablename__ = "content_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_type: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(60), default="draft", index=True)
    source_urls: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class UserAccount(Base):
    __tablename__ = "user_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: Any) -> None:
        # SQLAlchemy column defaults are applied on INSERT/flush, not at object
        # construction. Set the least-privilege defaults immediately so code
        # cannot observe a newly-created account as an indeterminate admin.
        kwargs.setdefault("is_admin", False)
        kwargs.setdefault("is_active", True)
        super().__init__(**kwargs)

class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("user_accounts.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership_workspace_user"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(60), default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Lead(TenantScopedMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (Index("uq_leads_workspace_email", "workspace_id", "email", unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), index=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consent_source: Mapped[str] = mapped_column(String(180), default="website_form")
    lead_magnet: Mapped[str] = mapped_column(String(300), default="")
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    engaged: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ScheduledEmail(TenantScopedMixin, Base):
    __tablename__ = "scheduled_emails"
    __table_args__ = (
        UniqueConstraint("lead_id", "sequence_day", name="uq_scheduled_email_lead_day"),
        Index("ix_scheduled_email_workspace_claim", "workspace_id", "status", "claimed_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    sequence_day: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(500))
    body_html: Mapped[str] = mapped_column(Text)
    body_text: Mapped[str] = mapped_column(Text)
    condition_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(60), default="scheduled", index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class MailCommission(TenantScopedMixin, Base):
    __tablename__ = "mail_commissions"
    __table_args__ = (Index("uq_mail_commissions_workspace_message", "workspace_id", "message_id", unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(String(500), index=True)
    network: Mapped[str] = mapped_column(String(150), index=True)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(80), default="pending_verification", index=True)
    email_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parsed_subject: Mapped[str] = mapped_column(String(500), default="")
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class PayoutThreshold(TenantScopedMixin, Base):
    __tablename__ = "payout_thresholds"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    network: Mapped[str] = mapped_column(String(150), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    minimum_threshold: Mapped[float] = mapped_column(Float, default=0.0)
    reported_balance: Mapped[float] = mapped_column(Float, default=0.0)
    threshold_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    threshold_reached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    funds_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciliation_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class PerformanceMemory(TenantScopedMixin, Base):
    __tablename__ = "performance_memories"
    __table_args__ = (Index("uq_performance_memory_workspace_key", "workspace_id", "memory_key", unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    memory_key: Mapped[str] = mapped_column(String(64), index=True)
    hook: Mapped[str] = mapped_column(Text)
    conversion_count: Mapped[int] = mapped_column(Integer, default=0)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    commission_recorded: Mapped[float] = mapped_column(Float, default=0.0)
    source_networks: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(40), default="candidate", index=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ResourceUsage(TenantScopedMixin, Base):
    __tablename__ = "resource_usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    niche: Mapped[str] = mapped_column(String(200), index=True, default="general")
    provider: Mapped[str] = mapped_column(String(120), default="unknown")
    model: Mapped[str] = mapped_column(String(300), default="unknown")
    prompt_tokens_estimated: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens_reserved: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens_actual: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens_actual: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="reserved", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdCampaignPlanRecord(TenantScopedMixin, Base):
    """Persist generated ad plans as tenant-scoped, draft-only planning records."""

    __tablename__ = "ad_campaign_plans"
    __table_args__ = (
        Index("ix_ad_campaign_plans_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_name: Mapped[str] = mapped_column(String(160))
    niche: Mapped[str] = mapped_column(String(200), index=True)
    audience: Mapped[str] = mapped_column(String(400))
    region: Mapped[str] = mapped_column(String(120))
    objective: Mapped[str] = mapped_column(String(40))
    platforms_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    daily_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AdPerformanceObservation(TenantScopedMixin, Base):
    """Store reported ad metrics without implying provider verification or execution authority."""

    __tablename__ = "ad_performance_observations"
    __table_args__ = (
        Index(
            "ix_ad_performance_observations_workspace_plan_creative",
            "workspace_id",
            "campaign_plan_id",
            "creative_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("ad_campaign_plans.id", ondelete="SET NULL", name="fk_ad_perf_obs_campaign_plan"),
        nullable=True,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(40), index=True)
    creative_id: Mapped[str] = mapped_column(String(180), index=True)
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    source_reference_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    spend_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    commission_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    evidence_status: Mapped[str] = mapped_column(String(40), default="operator_supplied_unverified", index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


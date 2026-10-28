from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import event, Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, false, func
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
        if isinstance(entity, LeadConsentEvent):
            raise ValueError("Lead consent events are append-only")


class WorkflowRun(TenantScopedMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_status_lease_expiry", "status", "lease_expires_at"),
        Index("ix_workflow_runs_workspace_status_lease_expiry", "workspace_id", "status", "lease_expires_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow_name: Mapped[str] = mapped_column(String(180), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    execution_mode: Mapped[str] = mapped_column(String(40), default="SEMI_AUTONOMOUS")
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
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
    verification_response_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
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

class ExternalAction(TenantScopedMixin, Base):
    """Durable idempotency registry for provider writes made with global credentials."""

    __tablename__ = "external_actions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "action_type", "idempotency_key",
            name="uq_external_action_ws_type_key",
        ),
        Index("ix_external_actions_workspace_status_created", "workspace_id", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    action_type: Mapped[str] = mapped_column(String(100))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="in_progress", index=True)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    remote_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


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
    email_consent_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_source: Mapped[str] = mapped_column(String(180), default="website_form")
    lead_magnet: Mapped[str] = mapped_column(String(300), default="")
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    engaged: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class LeadConsentEvent(TenantScopedMixin, Base):
    """Append-only evidence of email-marketing consent grants and withdrawals.

    lead_id intentionally has no FK: privacy deletion of a lead must not cascade
    away the audit evidence. The retained identifier is a pseudonymous internal
    UUID; a governed unlink/retention process remains a release requirement.
    """

    __tablename__ = "lead_consent_events"
    __table_args__ = (
        Index(
            "ix_lead_consent_workspace_lead_created",
            "workspace_id", "lead_id", "created_at",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(80), nullable=False)
    consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(180), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False, default="email")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EmailConsentConfirmation(TenantScopedMixin, Base):
    """One-time confirmation request. Only the SHA-256 token hash is persisted."""
    __tablename__ = "email_consent_confirmations"
    __table_args__ = (
        Index("ix_email_consent_workspace_lead_created", "workspace_id", "lead_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending_delivery", index=True)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(180), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


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
        UniqueConstraint(
            "workspace_id", "platform", "provider_event_id",
            name="uq_ad_perf_observation_workspace_platform_event",
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
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_signature_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
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


class JurisdictionComplianceAssessment(TenantScopedMixin, Base):
    """Workspace-scoped evidence record for human-reviewed jurisdiction compliance decisions."""
    __tablename__ = "jurisdiction_compliance_assessments"
    __table_args__ = (
        Index("ix_compliance_assessments_workspace_status", "workspace_id", "status"),
        Index("ix_compliance_assessments_workspace_activity", "workspace_id", "activity"),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    activity: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    channels_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    jurisdictions_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    rule_evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    coverage_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(320), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )



class SkillPackage(TenantScopedMixin, Base):
    """Versioned, reviewable declarative skill package; stored instructions are never executed as code."""
    __tablename__ = "skill_packages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "skill_id", "version", name="uq_skill_packages_workspace_skill_version"),
        Index("ix_skill_packages_workspace_status_created", "workspace_id", "status", "created_at"),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    skill_id: Mapped[str] = mapped_column(String(140), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    capabilities_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    input_schema_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict, nullable=False)
    output_schema_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict, nullable=False)
    instructions_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    fixtures_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    validation_report_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict, nullable=False)
    package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(320), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AdBudgetGuardrail(TenantScopedMixin, Base):
    """Persist spend limits and a fail-closed stop latch for a draft ad plan."""
    __tablename__ = "ad_budget_guardrails"
    __table_args__ = (
        UniqueConstraint("workspace_id", "campaign_plan_id", name="uq_ad_budget_guardrails_workspace_plan"),
        Index("ix_ad_budget_guardrails_workspace_stop", "workspace_id", "kill_switch_engaged", "stop_latched"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_plan_id: Mapped[str] = mapped_column(
        ForeignKey("ad_campaign_plans.id", ondelete="CASCADE", name="fk_ad_budget_guardrails_campaign_plan"),
        nullable=False, index=True,
    )
    daily_spend_cap_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    campaign_spend_cap_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    minimum_roas: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    maximum_cpa_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    minimum_verified_impressions: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    minimum_verified_clicks: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    minimum_verified_conversions: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    kill_switch_engaged: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    stop_latched: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_evaluation_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(320), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )



class WebinarEvent(TenantScopedMixin, Base):
    """Workspace-owned webinar registration page and current registration policy."""
    __tablename__ = "webinar_events"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_webinar_events_public_id"),
        Index("ix_webinar_events_workspace_status_start", "workspace_id", "status", "start_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    public_id: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(600), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    host_name: Mapped[str] = mapped_column(String(200), nullable=False)
    host_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(100), nullable=False)
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agenda_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VALUE, default=list)
    privacy_policy_url: Mapped[str] = mapped_column(Text, nullable=False)
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)
    affiliate_disclosure: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WebinarRegistration(TenantScopedMixin, Base):
    """Consent-recorded registration; does not imply an external webinar account exists."""
    __tablename__ = "webinar_registrations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "webinar_id", "email",
            name="uq_webinar_registrations_workspace_event_email",
        ),
        Index("ix_webinar_registrations_workspace_webinar_created", "workspace_id", "webinar_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    webinar_id: Mapped[str] = mapped_column(
        ForeignKey("webinar_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consent_text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    consent_source: Mapped[str] = mapped_column(String(100), default="webinar_registration_page")
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AffiliateProgramApplication(TenantScopedMixin, Base):
    """Workspace-owned affiliate application packet; provider submission is never implied."""
    __tablename__ = "affiliate_program_applications"
    __table_args__ = (
        Index("ix_program_applications_workspace_status_created", "workspace_id", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    program_name: Mapped[str] = mapped_column(String(240), nullable=False)
    program_url: Mapped[str] = mapped_column(Text, nullable=False)
    publisher_website_url: Mapped[str] = mapped_column(Text, nullable=False)
    audience_description: Mapped[str] = mapped_column(Text, nullable=False)
    monthly_visitors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    traffic_sources_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    promotion_channels_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    primary_regions_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    promotion_plan: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_urls_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list)
    compliance_answers_json: Mapped[dict[str, bool]] = mapped_column(JSON_VALUE, default=dict)
    readiness_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_submission_status: Mapped[str] = mapped_column(String(40), default="not_configured")
    provider_application_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MerchantOffer(TenantScopedMixin, Base):
    """Internally reviewed merchant offer; never implies affiliate-network approval."""
    __tablename__ = "merchant_offers"
    __table_args__ = (
        Index("ix_merchant_offers_workspace_status_created", "workspace_id", "status", "created_at"),
        Index("ix_merchant_offers_workspace_name", "workspace_id", "name"),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_by: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    commission_type: Mapped[str] = mapped_column(String(40), nullable=False)
    commission_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    commission_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    terms_version: Mapped[str] = mapped_column(String(120), nullable=False)
    commission_terms_url: Mapped[str] = mapped_column(Text, nullable=False)
    seller_authorization_url: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_regions_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    restricted_traffic_sources_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    affiliate_disclosure: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    terms_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seller_authorization_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activation_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    affiliate_network_approval_status: Mapped[str] = mapped_column(
        String(40), default="not_configured", nullable=False
    )
    marketplace_listed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MerchantOfferTermSnapshot(TenantScopedMixin, Base):
    """Append-only, explicitly unverified snapshot of merchant-offer terms."""
    __tablename__ = "merchant_offer_term_snapshots"
    __table_args__ = (
        Index(
            "ix_merchant_offer_terms_workspace_offer_captured",
            "workspace_id", "merchant_offer_id", "captured_at",
        ),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_offer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchant_offers.id", ondelete="RESTRICT"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    terms_version: Mapped[str] = mapped_column(String(120), nullable=False)
    commission_type: Mapped[str] = mapped_column(String(40), nullable=False)
    commission_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    commission_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cookie_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attribution_window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_regions_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    restricted_traffic_sources_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    terms_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    change_status: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_fields_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    changes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    provenance_status: Mapped[str] = mapped_column(String(40), default="operator_supplied_unverified", nullable=False)
    provider_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    source_content_fetched: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    created_by: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)



class MerchantOfferTermEvidenceFetch(TenantScopedMixin, Base):
    """Append-only result of one explicit, bounded public terms-source retrieval attempt."""
    __tablename__ = "merchant_offer_term_evidence_fetches"
    __table_args__ = (
        Index(
            "ix_merchant_offer_evidence_fetch_scope_time",
            "workspace_id", "merchant_offer_id", "term_snapshot_id", "fetched_at",
        ),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_offer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchant_offers.id", ondelete="RESTRICT"), nullable=False
    )
    term_snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchant_offer_term_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetch_status: Mapped[str] = mapped_column(String(40), nullable=False)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    response_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_change_status: Mapped[str] = mapped_column(String(40), default="not_comparable", server_default="'not_comparable'", nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), default="not_required", server_default="'not_required'", nullable=False)
    review_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    text_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    etag: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    provider_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(320), nullable=False)


class MarketplaceApplication(TenantScopedMixin, Base):
    """Publisher application to an internally reviewed marketplace offer; not a network application."""
    __tablename__ = "marketplace_applications"
    __table_args__ = (
        UniqueConstraint("workspace_id", "merchant_offer_id", name="uq_marketplace_application_publisher_offer"),
        Index("ix_marketplace_apps_workspace_status_created", "workspace_id", "status", "created_at"),
        Index("ix_marketplace_apps_merchant_status_created", "merchant_workspace_id", "status", "created_at"),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    merchant_offer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchant_offers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    applicant_email: Mapped[str] = mapped_column(String(320), nullable=False)
    publisher_website_url: Mapped[str] = mapped_column(Text, nullable=False)
    audience_description: Mapped[str] = mapped_column(Text, nullable=False)
    traffic_sources_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    intended_regions_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    promotion_plan: Mapped[str] = mapped_column(Text, nullable=False)
    compliance_answers_json: Mapped[dict[str, bool]] = mapped_column(JSON_VALUE, default=dict, nullable=False)
    terms_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending_review", nullable=False, index=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DistributionQueueItem(TenantScopedMixin, Base):
    """Immutable content snapshot awaiting human review and separate provider dispatch."""

    __tablename__ = "distribution_queue_items"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_distribution_queue_workspace_key"),
        Index("ix_distribution_queue_workspace_status_schedule", "workspace_id", "status", "scheduled_at"),
        Index("ix_distribution_queue_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("content_assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_asset_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_body: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_urls_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    channel: Mapped[str] = mapped_column(String(80), nullable=False)
    target_jurisdictions_json: Mapped[list[str]] = mapped_column(JSON_VALUE, default=list, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending_review", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(320), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

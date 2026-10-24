from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base

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

class Campaign(Base):
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

class ClickEvent(Base):
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

class Conversion(Base):
    __tablename__ = "conversions"
    __table_args__ = (UniqueConstraint("network", "external_event_id", name="uq_conversion_network_external_event"), Index("ix_conversion_campaign_created", "click_id", "created_at"))
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

class WorkflowRun(Base):
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

class PausedSession(Base):
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

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(320), default="system")
    action: Mapped[str] = mapped_column(String(180), index=True)
    resource_type: Mapped[str] = mapped_column(String(100), default="system")
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(80), default="ok")
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

class ContentAsset(Base):
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
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consent_source: Mapped[str] = mapped_column(String(180), default="website_form")
    lead_magnet: Mapped[str] = mapped_column(String(300), default="")
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    engaged: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ScheduledEmail(Base):
    __tablename__ = "scheduled_emails"
    __table_args__ = (UniqueConstraint("lead_id", "sequence_day", name="uq_scheduled_email_lead_day"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    sequence_day: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(500))
    body_html: Mapped[str] = mapped_column(Text)
    body_text: Mapped[str] = mapped_column(Text)
    condition_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(60), default="scheduled", index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class MailCommission(Base):
    __tablename__ = "mail_commissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    network: Mapped[str] = mapped_column(String(150), index=True)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(80), default="pending_verification", index=True)
    email_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parsed_subject: Mapped[str] = mapped_column(String(500), default="")
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class PayoutThreshold(Base):
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

class ResourceUsage(Base):
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

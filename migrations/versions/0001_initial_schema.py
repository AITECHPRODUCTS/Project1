"""Initial schema baseline with explicit Alembic operations."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "offers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("network", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("category", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reward_type", sa.String(100), nullable=True),
        sa.Column("reward_value", sa.String(100), nullable=True),
        sa.Column("cookie_days", sa.Integer(), nullable=True),
        sa.Column("traffic_score", sa.Float(), nullable=True),
        sa.Column("gravity_score", sa.Float(), nullable=True),
        sa.Column("normalized_gravity", sa.Float(), nullable=True),
        sa.Column("epc", sa.Float(), nullable=True),
        sa.Column("conversion_rate", sa.Float(), nullable=True),
        sa.Column("recurring_commission", sa.Boolean(), nullable=True),
        sa.Column("source_stars", sa.Float(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("network", "external_id", name="uq_offer_network_external"),
    )
    op.create_index("ix_offers_network", "offers", ["network"])
    op.create_index("ix_offers_name", "offers", ["name"])
    op.create_index("ix_offers_category", "offers", ["category"])

    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("niche", sa.String(200), nullable=False),
        sa.Column("primary_destination", sa.Text(), nullable=False),
        sa.Column("fallback_destination", sa.Text(), nullable=True),
        sa.Column("tracking_parameter", sa.String(80), nullable=False),
        sa.Column("disclosure_text", sa.Text(), nullable=False),
        sa.Column("auto_publish", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("max_daily_spend", sa.Float(), nullable=False),
        sa.Column("primary_healthy", sa.Boolean(), nullable=True),
        sa.Column("fallback_healthy", sa.Boolean(), nullable=True),
        sa.Column("health_last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("health_last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_campaigns_name", "campaigns", ["name"])
    op.create_index("ix_campaigns_niche", "campaigns", ["niche"])

    op.create_table(
        "user_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_accounts_email", "user_accounts", ["email"], unique=True)

    op.create_table(
        "click_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("click_id", sa.String(80), nullable=False),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("destination_url", sa.Text(), nullable=False),
        sa.Column("chosen_destination", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("user_agent_hash", sa.String(64), nullable=True),
        sa.Column("utm_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_click_events_click_id", "click_events", ["click_id"], unique=True)
    op.create_index("ix_click_events_campaign_id", "click_events", ["campaign_id"])
    op.create_index("ix_click_events_created_at", "click_events", ["created_at"])

    op.create_table(
        "conversions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("network", sa.String(100), nullable=False),
        sa.Column("external_event_id", sa.String(255), nullable=False),
        sa.Column("click_id", sa.String(80), nullable=True),
        sa.Column("utm_source", sa.String(300), nullable=True),
        sa.Column("utm_medium", sa.String(300), nullable=True),
        sa.Column("utm_campaign", sa.String(500), nullable=True),
        sa.Column("utm_content", sa.String(500), nullable=True),
        sa.Column("hook", sa.Text(), nullable=True),
        sa.Column("revenue", sa.Float(), nullable=False),
        sa.Column("commission", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("network", "external_event_id", name="uq_conversion_network_external_event"),
    )
    op.create_index("ix_conversions_network", "conversions", ["network"])
    op.create_index("ix_conversions_click_id", "conversions", ["click_id"])
    op.create_index("ix_conversions_status", "conversions", ["status"])
    op.create_index("ix_conversions_created_at", "conversions", ["created_at"])
    op.create_index("ix_conversion_campaign_created", "conversions", ["click_id", "created_at"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_name", sa.String(180), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("execution_mode", sa.String(40), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_workflow_runs_workflow_name", "workflow_runs", ["workflow_name"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    op.create_index("ix_workflow_runs_created_at", "workflow_runs", ["created_at"])

    op.create_table(
        "paused_sessions",
        sa.Column("session_id", sa.String(36), primary_key=True),
        sa.Column("workflow_name", sa.String(180), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("required_action", sa.String(100), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_paused_sessions_status", "paused_sessions", ["status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor", sa.String(320), nullable=False),
        sa.Column("action", sa.String(180), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("outcome", sa.String(80), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "content_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("source_urls", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_content_assets_asset_type", "content_assets", ["asset_type"])
    op.create_index("ix_content_assets_status", "content_assets", ["status"])

    op.create_table(
        "leads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_source", sa.String(180), nullable=False),
        sa.Column("lead_magnet", sa.String(300), nullable=False),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("engaged", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_leads_email", "leads", ["email"], unique=True)

    op.create_table(
        "scheduled_emails",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lead_id", sa.String(36), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("sequence_day", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("condition_json", sa.JSON(), nullable=False),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("lead_id", "sequence_day", name="uq_scheduled_email_lead_day"),
    )
    op.create_index("ix_scheduled_emails_lead_id", "scheduled_emails", ["lead_id"])
    op.create_index("ix_scheduled_emails_send_at", "scheduled_emails", ["send_at"])
    op.create_index("ix_scheduled_emails_status", "scheduled_emails", ["status"])

    op.create_table(
        "mail_commissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("message_id", sa.String(500), nullable=False),
        sa.Column("network", sa.String(150), nullable=False),
        sa.Column("commission", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("email_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parsed_subject", sa.String(500), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_mail_commissions_message_id", "mail_commissions", ["message_id"], unique=True)
    op.create_index("ix_mail_commissions_network", "mail_commissions", ["network"])
    op.create_index("ix_mail_commissions_status", "mail_commissions", ["status"])

    op.create_table(
        "payout_thresholds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("network", sa.String(150), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("minimum_threshold", sa.Float(), nullable=False),
        sa.Column("reported_balance", sa.Float(), nullable=False),
        sa.Column("threshold_reached", sa.Boolean(), nullable=False),
        sa.Column("threshold_reached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("funds_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciliation_note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_payout_thresholds_network", "payout_thresholds", ["network"])

    op.create_table(
        "resource_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("niche", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("model", sa.String(300), nullable=False),
        sa.Column("prompt_tokens_estimated", sa.Integer(), nullable=False),
        sa.Column("output_tokens_reserved", sa.Integer(), nullable=False),
        sa.Column("input_tokens_actual", sa.Integer(), nullable=False),
        sa.Column("output_tokens_actual", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_resource_usage_niche", "resource_usage", ["niche"])
    op.create_index("ix_resource_usage_status", "resource_usage", ["status"])
    op.create_index("ix_resource_usage_created_at", "resource_usage", ["created_at"])


def downgrade() -> None:
    for name, table in [
        ("ix_resource_usage_created_at", "resource_usage"),
        ("ix_resource_usage_status", "resource_usage"),
        ("ix_resource_usage_niche", "resource_usage"),
        ("ix_payout_thresholds_network", "payout_thresholds"),
        ("ix_mail_commissions_status", "mail_commissions"),
        ("ix_mail_commissions_network", "mail_commissions"),
        ("ix_mail_commissions_message_id", "mail_commissions"),
        ("ix_scheduled_emails_status", "scheduled_emails"),
        ("ix_scheduled_emails_send_at", "scheduled_emails"),
        ("ix_scheduled_emails_lead_id", "scheduled_emails"),
        ("ix_leads_email", "leads"),
        ("ix_content_assets_status", "content_assets"),
        ("ix_content_assets_asset_type", "content_assets"),
        ("ix_audit_logs_created_at", "audit_logs"),
        ("ix_audit_logs_action", "audit_logs"),
        ("ix_paused_sessions_status", "paused_sessions"),
        ("ix_workflow_runs_created_at", "workflow_runs"),
        ("ix_workflow_runs_status", "workflow_runs"),
        ("ix_workflow_runs_workflow_name", "workflow_runs"),
        ("ix_conversion_campaign_created", "conversions"),
        ("ix_conversions_created_at", "conversions"),
        ("ix_conversions_status", "conversions"),
        ("ix_conversions_click_id", "conversions"),
        ("ix_conversions_network", "conversions"),
        ("ix_click_events_created_at", "click_events"),
        ("ix_click_events_campaign_id", "click_events"),
        ("ix_click_events_click_id", "click_events"),
        ("ix_campaigns_niche", "campaigns"),
        ("ix_campaigns_name", "campaigns"),
        ("ix_offers_category", "offers"),
        ("ix_offers_name", "offers"),
        ("ix_offers_network", "offers"),
        ("ix_user_accounts_email", "user_accounts"),
    ]:
        op.drop_index(name, table_name=table)
    for table in [
        "resource_usage", "payout_thresholds", "mail_commissions", "scheduled_emails",
        "leads", "content_assets", "audit_logs", "paused_sessions", "workflow_runs",
        "conversions", "click_events", "campaigns", "user_accounts", "offers",
    ]:
        op.drop_table(table)

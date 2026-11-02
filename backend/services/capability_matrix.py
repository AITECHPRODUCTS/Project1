from __future__ import annotations

import os
from typing import Any
from backend.config import Settings


CAPABILITY_STATUSES = {
    "automatic",
    "automatic_after_one_time_authorization",
    "approval_required",
    "partially_available",
    "manual_provider_flow",
    "not_supported",
    "not_configured",
}


def _item(
    capability_id: str,
    title: str,
    status: str,
    reason: str,
    *,
    prerequisites: list[str] | None = None,
    external_write: bool = False,
) -> dict[str, Any]:
    if status not in CAPABILITY_STATUSES:
        raise ValueError(f"Invalid capability status: {status}")
    return {
        "id": capability_id,
        "title": title,
        "status": status,
        "reason": reason,
        "prerequisites": prerequisites or [],
        "external_side_effect": external_write,
    }


def build_capability_matrix(settings: Settings, registry: dict[str, Any]) -> dict[str, Any]:
    """Report product-level automation limits without inferring authorization from config."""
    model_ready = (
        settings.llm_backend == "openai_compatible" and bool(settings.openai_api_key)
    ) or (
        settings.llm_backend == "local_transformers" and bool(settings.local_model_path)
    )
    mail_ready = bool(settings.resend_api_key and settings.resend_from_email)
    wp_ready = bool(
        os.getenv("WORDPRESS_SITE_URL")
        and os.getenv("WORDPRESS_USERNAME")
        and os.getenv("WORDPRESS_APPLICATION_PASSWORD")
    )
    ghost_ready = bool(os.getenv("GHOST_SITE_URL") and os.getenv("GHOST_ADMIN_API_KEY"))
    cms_ready = (wp_ready or ghost_ready) and settings.cms_publish_execute
    pinterest_ready = bool(settings.pinterest_access_token)
    reddit_ready = bool(settings.reddit_access_token)
    providers = {x["provider_id"]: x for x in registry.get("items", [])}
    offer_status = providers.get("openaffiliate", {}).get("status", "not_configured")
    if offer_status == "production_verified":
        offer_state = "automatic_after_one_time_authorization"
        offer_reason = "Offer lookup can run through a provider verified for this environment."
    elif offer_status == "configured_not_health_checked":
        offer_state = "partially_available"
        offer_reason = "A directory adapter is configured, but this environment has not passed a live health/contract check; current offer data and account access are not verified."
    else:
        offer_state = "not_configured"
        offer_reason = "No verified offer discovery provider is available in this environment."

    social_ready = pinterest_ready or reddit_ready
    actions = [
        _item(
            "internal_campaign_planning",
            "Campaign planning and drafts",
            "automatic",
            "Internal planning can be persisted; no external publication or spend is performed.",
        ),
        _item(
            "offer_discovery",
            "Affiliate offer discovery",
            offer_state,
            offer_reason,
            prerequisites=["Provider terms review", "Live read-only contract and freshness test"],
        ),
        _item(
            "affiliate_program_approval",
            "Applying to an affiliate program and obtaining approval",
            "manual_provider_flow",
            "Applications, identity checks, KYC and merchant approval remain provider-controlled.",
            prerequisites=["User-authorized account", "Provider-specific application and required disclosures"],
            external_write=True,
        ),
        _item(
            "content_generation",
            "AI-generated content drafts",
            "automatic_after_one_time_authorization" if model_ready else "not_configured",
            "A configured model can generate drafts; offline mode only emits explicitly labeled development drafts."
            if model_ready else "Configure and verify an approved OpenAI-compatible or local model before relying on AI generation.",
            prerequisites=["Model provider configured", "Source/claim review before publication"],
        ),
        _item(
            "seo_blog_drafts",
            "SEO article drafts and structured metadata",
            "automatic_after_one_time_authorization" if model_ready else "not_configured",
            "Draft generation is available only when the model and required source evidence are available; publishing remains separate.",
            prerequisites=["Validated source URLs", "Disclosure", "Human factual review"],
        ),
        _item(
            "vertical_video",
            "Vertical video rendering",
            "automatic_after_one_time_authorization" if settings.pexels_api_key else "not_configured",
            "Requires licensed B-roll source access and installed FFmpeg/MoviePy/TTS dependencies; rendered assets still need rights and quality review.",
            prerequisites=["PEXELS_API_KEY", "Asset/license review", "Renderer dependency check"],
        ),
        _item(
            "landing_page_draft",
            "Landing page and consent form draft",
            "automatic",
            "The local HTML draft generator works without publishing to an external CMS.",
            prerequisites=["Privacy notice URL", "Accurate disclosure", "Explicit consent language"],
        ),
        _item(
            "consented_lead_capture",
            "Consent-based lead capture and email queue",
            "automatic_after_one_time_authorization",
            "The local queue requires explicit consent; sending remains disabled until a delivery provider is verified.",
            prerequisites=["Explicit consent", "Privacy notice", "Unsubscribe and suppression handling"],
        ),
        _item(
            "email_delivery",
            "Email sequence delivery",
            "approval_required" if mail_ready else "not_configured",
            "Provider credentials alone are not proof of sender verification or deliverability; unsuppressed consent is checked per send.",
            prerequisites=["Verified sending domain", "Resend API key/from identity", "Consent and unsubscribe checks"],
            external_write=True,
        ),
        _item(
            "social_publishing",
            "External social publication",
            "approval_required" if social_ready and not settings.publishing_dry_run else (
                "not_configured" if not social_ready else "approval_required"
            ),
            "Drafts default to dry-run. Each platform requires approved scopes, policy validation, budget/rate limits and remote success evidence.",
            prerequisites=["Authorized provider account", "Supported write scope", "Per-content approval", "Idempotency and remote ID"],
            external_write=True,
        ),
        _item(
            "cms_publishing",
            "WordPress/Ghost publishing",
            "approval_required" if cms_ready else "not_configured",
            "CMS publishing is not inferred from a URL. Actual writes require a configured CMS credential and CMS_PUBLISH_EXECUTE=true.",
            prerequisites=["Authorized CMS credentials", "CMS_PUBLISH_EXECUTE=true", "Draft preview and policy gate"],
            external_write=True,
        ),
        _item(
            "commission_reporting",
            "Provider commission reports",
            "not_configured",
            "Current authenticated report adapters have not been verified against a real affiliate account in this environment.",
            prerequisites=["Provider-approved API scope", "Live schema/pagination/refund test", "Currency/reversal reconciliation"],
        ),
        _item(
            "attribution",
            "First-party click tracking and signed conversion intake",
            "automatic_after_one_time_authorization",
            "Local click IDs and signed webhook intake are implemented; live provider postbacks and end-to-end attribution still require contract tests.",
            prerequisites=["Tracking HMAC secret", "Provider event IDs", "Privacy/retention review"],
        ),
        _item(
            "paid_media",
            "Paid advertising and campaign edits",
            "approval_required" if settings.ad_automation_execute else "not_configured",
            "Paid campaign mutations are disabled unless explicitly enabled; no live ad-account write verification is recorded.",
            prerequisites=["Authorized ad account", "Spend ceiling", "Stop-loss and kill-switch test", "Per-action audit"],
            external_write=True,
        ),
        _item(
            "payout_transfer",
            "Bank transfers and payouts",
            "manual_provider_flow",
            "The product records reported commission/payout observations only; it does not initiate transfers or claim cash receipt.",
            prerequisites=["Owner executes transfer outside the product", "Statement reconciliation"],
            external_write=True,
        ),
        _item(
            "model_finetuning",
            "Proprietary model fine-tuning and promoted LoRA model",
            "not_supported",
            "The current branch can load an operator-supplied local model/adapter; a full governed dataset, training, held-out evaluation and promotion/rollback pipeline is not yet implemented.",
            prerequisites=["Licensed/consented training data", "Tenant separation", "Held-out evaluation", "Artifact provenance and rollback"],
        ),
        _item(
            "performance_learning",
            "Evidence-backed performance memory",
            "approval_required",
            "The learner stores only observed, sufficiently sampled performance hypotheses; promotion to production behavior requires review and validation.",
            prerequisites=["Verified conversions", "Minimum sample count", "Independent test or experiment"],
        ),
        _item(
            "merchant_affiliate_approval",
            "Merchant approval of affiliate applications",
            "approval_required",
            "Merchant-side review needs an authorized merchant workspace and an explicit decision. No external network approval is inferred.",
            prerequisites=["Verified merchant authority", "Versioned terms", "Decision audit trail"],
            external_write=True,
        ),
        _item(
            "super_admin_operations",
            "Platform-wide Super Admin and tenant operations",
            "partially_available",
            "Implemented foundations include audited tenant suspend/reinstate, a global pause for registry-gated provider writes, and read-only platform overview, workflow, provider-readiness and audit views. Worker/queue heartbeats, dead-letter recovery, retention/deletion, incident operations, and complete platform RBAC, health and release controls remain incomplete.",
            prerequisites=["Separate platform-admin identity", "Audited least-privilege controls", "Tenant isolation tests", "Worker/queue and dead-letter operations", "Retention and incident runbooks"],
        ),
    ]
    provider_items = []
    for row in registry.get("items", []):
        status = row.get("status")
        if status == "production_verified":
            capability_status = "automatic_after_one_time_authorization"
        elif status == "contract_tested":
            capability_status = "approval_required"
        elif status == "configured_not_health_checked":
            capability_status = "partially_available"
        elif row.get("adapter") in {"catalog_only", "unknown"} or status == "not_implemented":
            capability_status = "manual_provider_flow"
        else:
            capability_status = "not_configured"
        provider_items.append({
            "provider_id": row.get("provider_id"),
            "display_name": row.get("display_name"),
            "status": capability_status,
            "registry_status": status,
            "adapter": row.get("adapter"),
            "reason": row.get("reason"),
            "external_side_effect": bool(row.get("publish_content") or row.get("write_access_verified")),
        })
    return {
        "statuses": sorted(CAPABILITY_STATUSES),
        "counts": {
            state: sum(1 for item in actions if item["status"] == state)
            for state in sorted(CAPABILITY_STATUSES)
        },
        "items": actions,
        "provider_items": provider_items,
        "global_policy": (
            "No integration is considered connected from configuration alone. All publication, "
            "email delivery, affiliate applications and paid-media changes must pass provider "
            "authorization, policy, budget, idempotency, audit and remote-success gates."
        ),
    }

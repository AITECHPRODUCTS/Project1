from __future__ import annotations
import asyncio,base64,hashlib,hmac,json,logging,re,secrets,time
import csv
import io
import httpx
from uuid import UUID
from contextlib import asynccontextmanager
from html import escape as html_escape
from html.parser import HTMLParser
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qsl,urlencode,urlparse,urlunparse
from typing import Any, Literal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter,Depends,FastAPI,HTTPException,Query,Request,WebSocket,WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse,JSONResponse,RedirectResponse,Response
from pwdlib import PasswordHash
from sqlalchemy import and_,func,or_,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware
from pydantic import ValidationError
from backend.tenancy import WorkspaceContextMiddleware, get_workspace_id, set_workspace_id, workspace_scope
from backend.config import get_settings
from backend.core.events import hub
from backend.core.middleware import CSRFMiddleware, FinancialSandboxMiddleware
from backend.core.state_machine import runner
from backend.database import SessionLocal,close_db,get_session,init_db
from backend.models import ProviderOrderObservation,ProviderAccountConnection,ExternalAction,SkillPackage,AdBudgetGuardrail,JurisdictionComplianceAssessment,MarketplaceApplication,MerchantOffer,MerchantOfferTermSnapshot,MerchantOfferTermEvidenceFetch,AffiliateProgramApplication,AdCampaignPlanRecord,AdPerformanceObservation,AuditLog,Campaign,ClickEvent,ContentAsset,Conversion,ConversionLedgerEntry,EmailConsentConfirmation,EmailDeliveryEvent,ExperimentAssignment,ExperimentEvent,Lead,LeadConsentEvent,MailCommission,Offer,PayoutThreshold,PausedSession,PlatformExecutionControl,ScheduledEmail,UserAccount,WorkflowRun,WebinarEvent,WebinarRegistration,Workspace,WorkspaceMembership,WorkspaceInvitation,DistributionQueueItem,OfferShortlist,OfferShortlistItem,OfferQualificationReview
from backend.adapters.webhook import AggregatorWebhookAdapter
from backend.adapters.ad_performance_webhook import AdPerformanceWebhookAdapter
from backend.services.resend_email_events import (
    AmbiguousResendMessageError,
    ConflictingResendEventError,
    UnmatchedResendMessageError,
    is_resend_webhook_secret_configured,
    process_resend_email_event,
    verify_resend_webhook_signature,
)
from backend.schemas import ClickBankOrderImportRequest,ClickBankConnectionCreateRequest,EmailAutomationCreateRequest,EmailAutomationReviewRequest,EmailAutomationSimulationRequest,GitHubPagesDeployRequest,BioLinkPageCreateRequest,BioLinkPublishRequest,SkillPackageCreateRequest,SkillPackageExecuteRequest,SkillPackageReviewRequest,AdBudgetGuardrailCreateRequest,AdGuardrailResetRequest,JurisdictionComplianceAssessmentCreateRequest,JurisdictionComplianceAssessmentReviewRequest,MarketplaceApplicationCreateRequest,MarketplaceApplicationReviewRequest,MerchantOfferCreateRequest,MerchantOfferReviewRequest,MerchantOfferTermSnapshotCreateRequest,MerchantOfferTermEvidenceReviewRequest,ProgramApplicationCreateRequest,ProgramApplicationReviewRequest,ABTestAssignmentRequest,AdCampaignPlanRequest,AdPerformanceObservationRequest,SignedAdPerformanceWebhookPayload,BlogRequest,ComparisonPostRequest,ListiclePostRequest,ComparisonPostReviewRequest,ContentResearchBriefRequest,CampaignCreateRequest,CMSPublishRequest,CompetitorRequest,CommissionEvidenceReviewRequest,CommissionCalculatorRequest,ContentAngleRankRequest,ContentAtomizeRequest,SEOAuditRequest,InternalLinkingRequest,InfographicRequest,GuaranteeDraftRequest,CategoryDesignRequest,ContentDecayRequest,ContentMoatRequest,TrafficAnalysisRequest,MultiProgramManagerRequest,PurpleCowAuditRequest,ConversionRequest,ExperimentEventRequest,FundsReceivedRequest,LandingPageRequest,LandingPagePublishRequest,LeadCaptureRequest,LoginRequest,RegisterRequest,WorkspaceCreateRequest,WorkspaceInvitationCreateRequest,WorkspaceInvitationAcceptRequest,WorkspaceLifecycleActionRequest,PlatformExecutionControlChangeRequest,NicheFinderRequest,PayoutThresholdCreateRequest,ProprietaryDatasetRequest,WebinarCreateRequest,WebinarRegistrationRequest,ResumeRequest,SocialPostRequest,TrendRequest,VideoRequest,WorkflowStartRequest,DistributionQueueCreateRequest,DistributionQueueApproveRequest,DistributionQueueCancelRequest,OfferShortlistCreateRequest,OfferShortlistItemCreateRequest,OfferQualificationReviewRequest
from backend.services.analytics_utils import ab_test_generator,conversion_tracker
from backend.services.ad_manager import evaluate_roas
from backend.services.ad_planner import generate_ad_campaign_plan
from backend.services.ad_performance import summarize_ad_performance
from backend.services.ad_guardrails import evaluate_ad_budget_guardrail
from backend.services.jurisdiction_compliance import ASSESSMENT_VALIDITY_DAYS,evidence_coverage,find_current_assessment,normalize_jurisdictions,required_categories
from backend.services.compliance_source_catalog import get_compliance_source_catalog
from backend.services.content_angle_ranker import rank_content_angles as rank_content_angles_service
from backend.services.infographic_generator import build_infographic as build_infographic_service
from backend.services.guarantee_draft import build_guarantee_draft as build_guarantee_draft_service
from backend.services.category_designer import design_category_taxonomy as design_category_taxonomy_service
from backend.services.content_decay_detector import build_content_decay_report as build_content_decay_report_service
from backend.services.content_moat_calculator import analyze_content_moat as analyze_content_moat_service
from backend.services.traffic_analyzer import analyze_traffic_domains as analyze_traffic_domains_service
from backend.services.multi_program_manager import manage_program_portfolio as manage_program_portfolio_service
from backend.services.seo_audit import audit_public_page as audit_public_page_service
from backend.services.internal_linking import recommend_internal_links as recommend_internal_links_service
from backend.services.purple_cow_audit import audit_purple_cow_positioning as audit_purple_cow_positioning_service
from backend.services.github_pages_deployer import GitHubPagesConfigurationError,deploy_github_pages_html,github_pages_readiness,verify_github_pages_html
from backend.services.bio_link_page import build_bio_link_page
from backend.services.skill_packager import build_skill_package,validate_skill_value
from backend.services.skill_runtime import SUPPORTED_RUNTIME_HANDLERS,execute_skill_handler
from backend.services.skill_finder import find_skills as find_skills_service
from backend.services.proprietary_data_generator import build_proprietary_dataset as build_proprietary_dataset_service
from backend.services.cms_publisher import publish_article
from backend.services.external_action_registry import EXTERNAL_IDEMPOTENCY_KEY_RE, claim_external_action as _claim_external_action, external_action_failure_status as _external_action_failure_status, finish_external_action as _finish_external_action
from backend.services.email_delivery import ConsentConfirmationDeliveryUnavailable,capture_lead_and_schedule,confirm_email_consent,resend_email_consent_confirmation,send_due_emails,unsubscribe_lead
from backend.services.email_automation_builder import build_email_automation,simulate_email_automation
from backend.services.integration_registry import build_network_registry
from backend.services.clickbank_accounts import (
    ClickBankAccessError, ClickBankProviderUnavailable, StoredCredentialError,
    decrypt_clickbank_api_key, encrypt_clickbank_api_key,
    fingerprint_clickbank_api_key, verify_clickbank_api_key, fetch_clickbank_quickstats, fetch_clickbank_order_counts, fetch_clickbank_order_transactions,
)
from backend.services.capability_matrix import build_capability_matrix
from backend.services.offer_intelligence import compute_offer_metrics
from backend.services.offer_term_snapshots import compare_offer_terms
from backend.services.resource_budget import status as budget_status
from backend.services.s1_research import competitor_spy,monopoly_niche_finder,trending_content_scout
from backend.services.s2_s3_content import content_research_brief as content_research_brief_service,affiliate_blog_builder,keyword_cluster_architect,tiktok_script_writer,viral_post_writer
from backend.services.comparison_post_writer import build_comparison_post as comparison_post_writer_service
from backend.services.listicle_writer import build_listicle_post as listicle_writer_service
from backend.services.comparison_draft_revisions import reserve_comparison_revision_number, reserve_content_revision_number
from backend.services.comparison_integrity import build_source_snapshot_manifest, evaluate_comparison_integrity, sha256_text, source_snapshot_manifest_sha256, comparison_evidence_payload_sha256
from backend.services.source_freshness import evaluate_source_freshness
from backend.services.s4_s5_landing import email_drip_sequence,grand_slam_offer_generator,render_workspace_landing_page,social_media_scheduler,squeeze_page_builder,value_ladder_architect
from backend.services.utm_attribution import UTM_FIELD_LIMITS, lead_attribution_summary, normalize_utm_attribution
from backend.services.s6_s8_analytics import self_improver_loop
from backend.services.tracking_service import choose_destination,destination_healthy,record_click_and_resolve,verify_click_signature
from backend.services.url_safety import open_public_http_response, read_limited_response, validate_public_http_url
from backend.services.video_engine import render_vertical_video
from backend.tools.affiliate_api import client as openaffiliate_client
from backend.workflows import LABELS,resolve_steps
from ai_memory.ingester import ingest as ingest_doctrine

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger=logging.getLogger("affiliate_os");settings=get_settings();password_hash=PasswordHash.recommended();scheduler=AsyncIOScheduler(timezone="UTC")

def utcnow():return datetime.now(timezone.utc)
def issue_workspace_token(workspace_id: str | None, purpose: str, ttl_seconds: int = 7 * 24 * 3600) -> str | None:
    if not workspace_id:
        return None
    secret = settings.tracking_hmac_secret or settings.app_session_secret
    payload = {"workspace_id": workspace_id, "purpose": purpose, "expires_at": int(time.time()) + ttl_seconds}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_workspace_token(token: str | None, purpose: str) -> str | None:
    if not token or len(token) > 1024 or "." not in token:
        return None
    encoded, supplied = token.rsplit(".", 1)
    secret = settings.tracking_hmac_secret or settings.app_session_secret
    expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        return None
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(decoded)
        workspace_id = str(payload["workspace_id"])
        if payload.get("purpose") != purpose or int(payload.get("expires_at", 0)) < int(time.time()):
            return None
        return workspace_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (value[:90].strip("-") or "workspace")


async def ensure_workspace_membership(
    db: AsyncSession,
    account: UserAccount,
    preferred_name: str | None = None,
) -> WorkspaceMembership:
    membership = await db.scalar(
        select(WorkspaceMembership)
        .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
        .where(
            WorkspaceMembership.user_id == account.id,
            WorkspaceMembership.is_active.is_(True),
            Workspace.lifecycle_state == "active",
        )
        .order_by(WorkspaceMembership.created_at.asc())
    )
    if membership is not None:
        return membership

    # Do not silently provision a replacement workspace to bypass a suspended
    # or revoked tenant membership. Only a genuinely new account is auto-created.
    existing_membership_id = await db.scalar(
        select(WorkspaceMembership.id).where(WorkspaceMembership.user_id == account.id).limit(1)
    )
    if existing_membership_id is not None:
        raise HTTPException(403, "No active workspace is available for this account; contact a Platform Super Admin.")

    base_name = preferred_name or f"{account.email.split('@', 1)[0][:100]} workspace"
    workspace = Workspace(
        name=base_name[:160],
        slug=f"{_slugify(base_name)}-{secrets.token_hex(4)}",
        owner_user_id=account.id,
        lifecycle_state="active",
    )
    db.add(workspace)
    await db.flush()
    membership = WorkspaceMembership(workspace_id=workspace.id, user_id=account.id, role="owner", is_active=True)
    db.add(membership)
    await db.flush()
    return membership

async def bootstrap_admin():
    if not settings.initial_admin_email or not settings.initial_admin_password:
        if settings.app_env == "production":
            raise RuntimeError("Production requires initial admin credentials")
        async with SessionLocal() as db:
            dev_workspace = await db.scalar(select(Workspace).where(Workspace.slug == "local-development", Workspace.lifecycle_state == "active"))
            if dev_workspace is None:
                db.add(Workspace(name="Local development", slug="local-development", owner_user_id=None))
                await db.commit()
        logger.warning("No administrator configured; local-development workspace is enabled only outside production")
        return
    async with SessionLocal() as db:
        account = await db.scalar(select(UserAccount).where(UserAccount.email == settings.initial_admin_email.lower()))
        if account is None:
            account = UserAccount(
                email=settings.initial_admin_email.lower(),
                password_hash=password_hash.hash(settings.initial_admin_password),
                is_admin=True,
                is_active=True,
            )
            db.add(account)
            await db.flush()
        else:
            account.is_admin = True
            account.is_active = True
        try:
            await ensure_workspace_membership(db, account, "Platform administrator workspace")
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
            logger.warning("Bootstrap admin has no active workspace; platform-admin restoration is required")
        await db.commit()
async def _background_workspace_ids() -> list[str]:
 # This is the only intentionally unscoped tenant enumeration in the scheduler.
 # All tenant data reads/writes happen afterward inside a concrete workspace scope.
 with workspace_scope(None):
  async with SessionLocal() as db:
   return list(
    (await db.scalars(
     select(Workspace.id)
     .where(Workspace.slug != "legacy-quarantine", Workspace.lifecycle_state == "active")
     .order_by(Workspace.created_at.asc())
    )).all()
   )


async def _workspace_is_active(workspace_id: str) -> bool:
 # Recheck at the point of work because an admin can suspend a tenant after
 # the scheduler took its initial snapshot of active workspace IDs.
 with workspace_scope(None):
  async with SessionLocal() as db:
   workspace = await db.get(Workspace, workspace_id)
   return workspace is not None and workspace.lifecycle_state == "active"


async def campaign_health_job():
 for workspace_id in await _background_workspace_ids():
  if not await _workspace_is_active(workspace_id):
   continue
  try:
   with workspace_scope(workspace_id):
    async with SessionLocal() as db:
     rows=list((await db.scalars(
      select(Campaign).where(Campaign.is_active.is_(True)).limit(100)
     )).all())
     for item in rows:
      ok,code,error=await destination_healthy(item.primary_destination)
      item.primary_healthy=ok
      item.health_last_checked_at=utcnow()
      item.health_last_error=None if ok else (error or f"HTTP {code}")[:1000]
      if item.fallback_destination:
       item.fallback_healthy=(await destination_healthy(item.fallback_destination))[0]
     await db.commit()
  except Exception:
   logger.exception("Campaign health worker failed for workspace %s",str(workspace_id)[:8])


async def learning_job():
 try:
  for workspace_id in await _background_workspace_ids():
   if not await _workspace_is_active(workspace_id):
    continue
   with workspace_scope(workspace_id):
    async with SessionLocal() as db:
     result=await self_improver_loop(db,lookback_days=30,workspace_id=workspace_id)
     logger.info("Performance-memory workspace %s: %s",workspace_id[:8],result)
 except Exception:
  logger.exception("Performance-memory job failed")


async def email_job():
 for workspace_id in await _background_workspace_ids():
  if not await _workspace_is_active(workspace_id):
   continue
  try:
   with workspace_scope(workspace_id):
    async with SessionLocal() as db:
     result=await send_due_emails(db,workspace_id=workspace_id)
     logger.info(
      "Email worker workspace %s: sent=%s attempted=%s skipped=%s outbound_blocked=%s block_code=%s",
      str(workspace_id)[:8],
      result.get("sent", 0),
      result.get("attempted", 0),
      result.get("skipped", 0),
      result.get("outbound_actions_blocked", False),
      result.get("blocked_code"),
     )
  except Exception:
   logger.exception("Email sender worker failed for workspace %s",str(workspace_id)[:8])


async def threshold_job():
 for workspace_id in await _background_workspace_ids():
  if not await _workspace_is_active(workspace_id):
   continue
  try:
   with workspace_scope(workspace_id):
    async with SessionLocal() as db:
     rows=list((await db.scalars(select(PayoutThreshold))).all())
     now=utcnow()
     for row in rows:
      reached=float(row.reported_balance or 0)>=float(row.minimum_threshold or 0)
      if reached and not row.threshold_reached:
       row.threshold_reached=True
       row.threshold_reached_at=now
      elif not reached:
       row.threshold_reached=False
       row.threshold_reached_at=None
     await db.commit()
  except Exception:
   logger.exception("Payout threshold worker failed for workspace %s",str(workspace_id)[:8])
async def ad_guardrail_monitor_job() -> dict[str, int]:
 """Periodically evaluate non-latched guardrails; this job never calls ad providers."""
 summary = {"workspaces_processed": 0, "guardrails_evaluated": 0, "guardrails_latched": 0, "guardrails_failed": 0}
 for workspace_id in await _background_workspace_ids():
  if not await _workspace_is_active(workspace_id):
   continue
  try:
   with workspace_scope(workspace_id):
    async with SessionLocal() as db:
     policy_ids = list((await db.scalars(
      select(AdBudgetGuardrail.id)
      .where(AdBudgetGuardrail.stop_latched.is_(False))
      .order_by(AdBudgetGuardrail.created_at.asc())
     )).all())
   for guardrail_id in policy_ids:
    try:
     with workspace_scope(workspace_id):
      async with SessionLocal() as db:
       row = await db.scalar(select(AdBudgetGuardrail).where(
        AdBudgetGuardrail.id == guardrail_id,
        AdBudgetGuardrail.workspace_id == workspace_id,
       ).with_for_update())
       if row is None or row.stop_latched:
        continue
       plan = await db.scalar(select(AdCampaignPlanRecord).where(
        AdCampaignPlanRecord.id == row.campaign_plan_id,
        AdCampaignPlanRecord.workspace_id == workspace_id,
       ))
       if plan is None:
        logger.warning("Ad guardrail %s skipped: plan missing in workspace %s", guardrail_id[:8], workspace_id[:8])
        continue
       observations = list((await db.scalars(
        select(AdPerformanceObservation)
        .where(
         AdPerformanceObservation.workspace_id == workspace_id,
         AdPerformanceObservation.campaign_plan_id == plan.id,
        )
        .order_by(AdPerformanceObservation.observed_at.asc())
       )).all())
       now = utcnow()
       previous_status = str((row.last_evaluation_json or {}).get("status") or "")
       evaluation = evaluate_ad_budget_guardrail(
        policy=row,
        observations=observations,
        now=now,
        plan_daily_budget_usd=Decimal(plan.daily_budget_usd or 0),
       )
       row.last_evaluated_at = now
       row.last_evaluation_json = evaluation
       breached = bool(evaluation.get("breaches"))
       if breached:
        row.stop_latched = True
        row.kill_switch_engaged = True
       if row.stop_latched:
        row.kill_switch_engaged = True
       if previous_status != evaluation.get("status") or breached:
        db.add(AuditLog(
         workspace_id=workspace_id,
         actor="system:ad_guardrail_monitor",
         action="ads.guardrail.scheduled_evaluation",
         resource_type="ad_budget_guardrail",
         resource_id=row.id,
         outcome=evaluation.get("status", "unknown"),
         details_json={
          "breaches": evaluation.get("breaches", []),
          "verified_observation_count": evaluation.get("verified_observation_count", 0),
          "reported_observation_count": evaluation.get("reported_observation_count", 0),
          "kill_switch_engaged": row.kill_switch_engaged,
          "stop_latched": row.stop_latched,
          "provider_action_executed": False,
         },
        ))
       await db.commit()
       summary["guardrails_evaluated"] += 1
       if breached:
        summary["guardrails_latched"] += 1
    except Exception:
     summary["guardrails_failed"] += 1
     logger.exception("Ad guardrail monitor failed for workspace %s, policy %s", workspace_id[:8], guardrail_id[:8])
   summary["workspaces_processed"] += 1
  except Exception:
   summary["guardrails_failed"] += 1
   logger.exception("Ad guardrail monitor failed for workspace %s", str(workspace_id)[:8])
 logger.info("Ad guardrail monitor summary: %s", summary)
 return summary


@asynccontextmanager
async def lifespan(app:FastAPI):
 await init_db()
 await hub.start(settings.redis_url)
 await bootstrap_admin()
 runner.set_resolver(resolve_steps)
 recovered=await runner.recover_interrupted()
 paused=await runner.recover_paused()
 await runner.start_recovery_worker()
 logger.info("Recovered interrupted workflows: %s; paused sessions: %s",recovered,paused)
 scheduler.add_job(campaign_health_job,CronTrigger(minute="*/10"),id="campaign-health",replace_existing=True,max_instances=1)
 scheduler.add_job(learning_job,CronTrigger(hour=3,minute=15),id="learning",replace_existing=True,max_instances=1)
 scheduler.add_job(email_job,"interval",minutes=5,id="email-send",replace_existing=True,max_instances=1)
 scheduler.add_job(threshold_job,CronTrigger(day_of_week="mon",hour=4),id="thresholds",replace_existing=True,max_instances=1)
 scheduler.add_job(ad_guardrail_monitor_job,"interval",minutes=5,id="ad-guardrails",replace_existing=True,max_instances=1,coalesce=True,misfire_grace_time=300);scheduler.start()
 yield
 await runner.stop_recovery_worker()
 scheduler.shutdown(wait=False);await hub.stop();await close_public_rate_limiter();await close_db()
docs_url="/docs" if settings.app_env != "production" else None
redoc_url="/redoc" if settings.app_env != "production" else None
openapi_url="/openapi.json" if settings.app_env != "production" else None
app=FastAPI(title=settings.app_name,version="0.1.0",description="Evidence-first RAG-backed affiliate marketing operations OS",lifespan=lifespan,docs_url=docs_url,redoc_url=redoc_url,openapi_url=openapi_url)
app.add_middleware(FinancialSandboxMiddleware)
# SessionMiddleware must wrap CSRFMiddleware so the latter can validate the signed session cookie.
app.add_middleware(CSRFMiddleware)
app.add_middleware(WorkspaceContextMiddleware)
app.add_middleware(SessionMiddleware,secret_key=settings.app_session_secret,session_cookie="affiliate_os_session",max_age=43200,same_site="lax",https_only=settings.app_env=="production")
app.add_middleware(CORSMiddleware,allow_origins=settings.allowed_origins,allow_credentials=True,allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type","Idempotency-Key","X-Affiliate-Signature","X-CSRF-Token"])

async def require_auth(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if settings.app_env != "production" and not settings.initial_admin_email and not settings.api_access_token:
        workspace = await db.scalar(select(Workspace).where(Workspace.slug == "local-development", Workspace.lifecycle_state == "active"))
        user = {
            "email": "local-development",
            "is_admin": True,
            "user_id": "local",
            "workspace_id": workspace.id if workspace else None,
            "workspace_role": "owner",
        }
        if user["workspace_id"]:
            set_workspace_id(str(user["workspace_id"]))
        return user

    user = request.session.get("user") if hasattr(request, "session") else None
    if isinstance(user, dict):
        user = dict(user)
        workspace_id = user.get("workspace_id")
        user_id = user.get("user_id")
        if settings.app_env == "production" and (not workspace_id or not user_id):
            raise HTTPException(403, "Select an authorized workspace before using workspace data")
        if workspace_id and user_id and user_id != "local":
            # Session cookies are signed, but their authorization fields can become
            # stale after account suspension or platform-admin revocation. Re-read
            # the authoritative account row on every authenticated workspace request.
            account = await db.get(UserAccount, str(user_id))
            if account is None or not bool(account.is_active):
                request.session.clear()
                raise HTTPException(403, "Account is inactive or no longer available")
            user["email"] = account.email
            user["is_admin"] = bool(account.is_admin)

            workspace = await db.get(Workspace, str(workspace_id))
            if workspace is None or getattr(workspace, "lifecycle_state", "active") != "active":
                request.session.clear()
                raise HTTPException(403, "Workspace is suspended or unavailable; contact a Platform Super Admin.")

            membership = await db.scalar(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.workspace_id == str(workspace_id),
                    WorkspaceMembership.user_id == str(user_id),
                    WorkspaceMembership.is_active.is_(True),
                )
            )
            if membership is None:
                request.session.clear()
                raise HTTPException(403, "Workspace membership is no longer active")
            user["workspace_role"] = membership.role
            request.session["user"] = user
            set_workspace_id(str(workspace_id))
        return user

    auth = request.headers.get("authorization", "")
    if settings.api_access_token and auth.startswith("Bearer ") and hmac.compare_digest(auth[7:].strip(), settings.api_access_token):
        raise HTTPException(
            403,
            "A static API token is not workspace-scoped. Use a signed workspace session or implement a dedicated workspace API credential.",
        )
    raise HTTPException(401, "Authentication required")


async def require_admin(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    if not user.get("is_admin") and user.get("workspace_role") not in {"owner", "admin"}:
        raise HTTPException(403, "Workspace owner/admin permission required")
    return user


async def require_platform_admin(user: dict[str, Any] = Depends(require_auth)) -> dict[str, Any]:
    """Require the explicit global platform-admin flag; workspace roles never imply it."""
    if user.get("is_admin") is not True:
        raise HTTPException(403, "Platform Super Admin permission required")
    return user


async def _record_external_publish_audit(
    db: AsyncSession,
    *,
    user: dict[str, Any],
    workspace_id: str,
    action: str,
    platform: str,
    outcome: str,
    remote_id: str | int | None = None,
    error_type: str | None = None,
) -> None:
    details: dict[str, Any] = {
        "platform": platform[:80],
        "live_execution_enabled": not settings.publishing_dry_run,
    }
    if error_type:
        details["error_type"] = error_type[:120]
    with workspace_scope(workspace_id):
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or user.get("user_id") or "unknown")[:320],
            action=action[:180],
            resource_type="external_publication",
            resource_id=str(remote_id)[:255] if remote_id is not None else None,
            outcome=outcome[:80],
            details_json=details,
        ))
        await db.commit()


@app.get("/health")
async def health():
    """Liveness probe; intentionally independent of downstream service health."""
    return {"status": "ok", "service": "affiliate-os-api", "time": utcnow().isoformat()}


@app.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_session)):
    """Return ready only when the API can execute a basic database query."""
    try:
        await db.execute(select(1))
    except Exception as exc:
        # Never expose driver messages, DSNs, usernames, or query details to callers.
        logger.warning("Database readiness check failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=503, detail="service_not_ready") from None
    return {
        "status": "ready",
        "service": "affiliate-os-api",
        "dependencies": {"database": "ok"},
    }
@app.post("/api/auth/register", status_code=201)
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_session)):
    await public_rate_limit(request)
    email = payload.email.strip().lower()
    minimum = 14 if settings.app_env == "production" else 12
    if len(payload.password) < minimum:
        raise HTTPException(422, f"Password must contain at least {minimum} characters")
    if await db.scalar(select(UserAccount.id).where(UserAccount.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    account = UserAccount(
        email=email,
        password_hash=password_hash.hash(payload.password),
        is_admin=False,
        is_active=True,
    )
    db.add(account)
    try:
        await db.flush()
        membership = await ensure_workspace_membership(db, account, payload.workspace_name)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Account registration conflicted with an existing account") from exc
    request.session.clear()
    request.session["user"] = {
        "email": account.email,
        "is_admin": False,
        "user_id": account.id,
        "workspace_id": membership.workspace_id,
        "workspace_role": membership.role,
    }
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    return {"authenticated": True, "user": request.session["user"], "csrf_token": request.session["csrf_token"]}


@app.post("/api/auth/login")
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_session)):
    await public_rate_limit(request)
    account = await db.scalar(
        select(UserAccount).where(
            UserAccount.email == payload.email.strip().lower(),
            UserAccount.is_active.is_(True),
        )
    )
    if account is None or not password_hash.verify(payload.password, account.password_hash):
        raise HTTPException(401, "Invalid email or password")
    account.last_login_at = utcnow()
    membership = await ensure_workspace_membership(db, account)
    await db.commit()
    request.session.clear()
    request.session["user"] = {
        "email": account.email,
        "is_admin": account.is_admin,
        "user_id": account.id,
        "workspace_id": membership.workspace_id,
        "workspace_role": membership.role,
    }
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    return {"authenticated": True, "user": request.session["user"], "csrf_token": request.session["csrf_token"]}


@app.post("/api/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return {"authenticated": False}


@app.get("/api/auth/me")
async def whoami(request: Request, user: dict[str, Any] = Depends(require_auth)):
    csrf_token = str(request.session.get("csrf_token") or "") if hasattr(request, "session") else ""
    return {"authenticated": True, "user": user, "csrf_token": csrf_token}

api=APIRouter(prefix="/api",dependencies=[Depends(require_auth)])
@api.get("/workspaces")
async def list_workspaces(user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    user_id = user.get("user_id")
    if not user_id or user_id == "local":
        active = await db.get(Workspace, user.get("workspace_id")) if user.get("workspace_id") else None
        return {"active_workspace_id": active.id if active else None, "data":[{"id":active.id,"name":active.name,"slug":active.slug,"role":"owner"}] if active else []}
    rows = (await db.execute(
        select(Workspace, WorkspaceMembership)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user_id, WorkspaceMembership.is_active.is_(True))
        .order_by(Workspace.created_at.asc())
    )).all()
    return {
        "active_workspace_id": user.get("workspace_id"),
        "data": [{"id": workspace.id, "name": workspace.name, "slug": workspace.slug, "role": membership.role,
                  "is_active": membership.is_active, "lifecycle_state": workspace.lifecycle_state,
                  "suspended_at": workspace.suspended_at.isoformat() if workspace.suspended_at else None,
                  "created_at": workspace.created_at.isoformat() if workspace.created_at else None}
                 for workspace, membership in rows],
    }


@api.get("/workspaces/current")
async def current_workspace(user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    workspace_id = user.get("workspace_id")
    workspace = await db.get(Workspace, workspace_id) if workspace_id else None
    if workspace is None:
        raise HTTPException(404, "No active workspace")
    return {"id": workspace.id, "name": workspace.name, "slug": workspace.slug, "role": user.get("workspace_role"),
            "lifecycle_state": workspace.lifecycle_state,
            "is_platform_admin": bool(user.get("is_admin"))}


@api.post("/workspaces", status_code=201)
async def create_workspace(payload: WorkspaceCreateRequest, request: Request,
                           user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    user_id = user.get("user_id")
    if not user_id or user_id == "local":
        raise HTTPException(403, "Create a registered account before adding a persistent workspace")
    workspace = Workspace(
        name=payload.name.strip(),
        slug=f"{_slugify(payload.name)}-{secrets.token_hex(4)}",
        owner_user_id=user_id,
        lifecycle_state="active",
    )
    db.add(workspace)
    await db.flush()
    membership = WorkspaceMembership(workspace_id=workspace.id, user_id=user_id, role="owner", is_active=True)
    db.add(membership)
    await db.commit()
    updated_user = dict(user)
    updated_user["workspace_id"] = workspace.id
    updated_user["workspace_role"] = membership.role
    request.session["user"] = updated_user
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    return {"id": workspace.id, "name": workspace.name, "slug": workspace.slug, "role": membership.role,
            "csrf_token": request.session["csrf_token"]}


@api.post("/workspaces/{workspace_id}/switch")
async def switch_workspace(workspace_id: str, request: Request,
                           user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    user_id = user.get("user_id")
    if not user_id or user_id == "local":
        raise HTTPException(403, "Workspace switching requires a registered account")
    membership = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.is_active.is_(True),
        )
    )
    if membership is None:
        raise HTTPException(404, "Workspace not found or membership inactive")
    workspace = await db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(404, "Workspace not found")
    if workspace.lifecycle_state != "active":
        raise HTTPException(409, "Workspace is suspended and cannot be selected")
    updated_user = dict(user)
    updated_user["workspace_id"] = workspace.id
    updated_user["workspace_role"] = membership.role
    request.session["user"] = updated_user
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    return {"active_workspace_id": workspace.id, "name": workspace.name, "role": membership.role,
            "csrf_token": request.session["csrf_token"]}


def _workspace_invitation_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _workspace_invitation_status(invitation: WorkspaceInvitation, now: datetime) -> str:
    if invitation.accepted_at is not None:
        return "accepted"
    if invitation.revoked_at is not None:
        return "revoked"
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return "expired" if expires_at <= now else "pending"


async def _workspace_invitation_manager_context(user: dict[str, Any], db: AsyncSession) -> Workspace:
    # Platform-admin status alone does not grant authority over a customer workspace.
    if not user.get("user_id") or user.get("user_id") == "local":
        raise HTTPException(403, "A registered account is required for workspace invitations")
    if user.get("workspace_role") not in {"owner", "admin"}:
        raise HTTPException(403, "Workspace owner/admin permission required")
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "An active workspace is required")
    workspace = await db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(404, "Workspace not found")
    if workspace.lifecycle_state != "active":
        raise HTTPException(409, "Workspace is suspended and cannot manage invitations")
    return workspace


@api.get("/workspaces/invitations")
async def list_workspace_invitations(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace = await _workspace_invitation_manager_context(user, db)
    now = datetime.now(timezone.utc)
    rows = (await db.scalars(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.workspace_id == workspace.id)
        .order_by(WorkspaceInvitation.created_at.desc())
        .limit(100)
    )).all()
    return {
        "data": [{
            "id": row.id, "email": row.email, "role": row.role,
            "status": _workspace_invitation_status(row, now),
            "created_at": _workspace_invitation_iso(row.created_at),
            "expires_at": _workspace_invitation_iso(row.expires_at),
            "accepted_at": _workspace_invitation_iso(row.accepted_at),
            "revoked_at": _workspace_invitation_iso(row.revoked_at),
        } for row in rows],
        "delivery": "manual_link_only",
        "note": "Invitation email is not sent by this endpoint; share a new invitation link securely.",
    }


@api.post("/workspaces/invitations", status_code=201)
async def create_workspace_invitation(
    payload: WorkspaceInvitationCreateRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace = await _workspace_invitation_manager_context(user, db)
    role = str(user.get("workspace_role") or "")
    if payload.role == "admin" and role != "owner":
        raise HTTPException(403, "Only the workspace owner can invite an administrator")
    now = datetime.now(timezone.utc)
    account = await db.scalar(select(UserAccount).where(func.lower(UserAccount.email) == payload.email))
    if account is not None:
        member = await db.scalar(select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == account.id,
        ))
        if member is not None and member.is_active:
            raise HTTPException(409, "This account is already an active workspace member")
    duplicate = await db.scalar(select(WorkspaceInvitation).where(
        WorkspaceInvitation.workspace_id == workspace.id,
        WorkspaceInvitation.email == payload.email,
        WorkspaceInvitation.accepted_at.is_(None),
        WorkspaceInvitation.revoked_at.is_(None),
        WorkspaceInvitation.expires_at > now,
    ))
    if duplicate is not None:
        raise HTTPException(409, "A pending invitation already exists for this email")
    raw_token = secrets.token_urlsafe(32)
    invitation = WorkspaceInvitation(
        workspace_id=workspace.id,
        email=payload.email,
        role=payload.role,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        invited_by_user_id=str(user["user_id"]),
        expires_at=now + timedelta(hours=payload.expires_in_hours),
    )
    db.add(invitation)
    await db.flush()
    with workspace_scope(workspace.id):
        db.add(AuditLog(
            workspace_id=workspace.id,
            actor=str(user.get("email") or user.get("user_id") or "unknown")[:320],
            action="workspace.invitation.created",
            resource_type="workspace_invitation",
            resource_id=invitation.id,
            outcome="created",
            details_json={"email": invitation.email, "role": invitation.role, "expires_at": _workspace_invitation_iso(invitation.expires_at)},
        ))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "Invitation could not be created; check for a duplicate invitation") from None
    return {
        "id": invitation.id, "email": invitation.email, "role": invitation.role,
        "expires_at": _workspace_invitation_iso(invitation.expires_at), "token": raw_token,
        "delivery": "manual_link_only",
        "notice": "This is a one-time invitation token. Share the link only with the intended recipient; no email was sent.",
    }


@api.post("/workspaces/invitations/{invitation_id}/revoke")
async def revoke_workspace_invitation(
    invitation_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace = await _workspace_invitation_manager_context(user, db)
    invitation = await db.scalar(select(WorkspaceInvitation).where(
        WorkspaceInvitation.id == invitation_id,
        WorkspaceInvitation.workspace_id == workspace.id,
    ))
    if invitation is None:
        raise HTTPException(404, "Invitation not found in the active workspace")
    status = _workspace_invitation_status(invitation, datetime.now(timezone.utc))
    if status == "accepted":
        raise HTTPException(409, "An accepted invitation cannot be revoked")
    if status == "revoked":
        raise HTTPException(409, "Invitation is already revoked")
    invitation.revoked_at = datetime.now(timezone.utc)
    with workspace_scope(workspace.id):
        db.add(AuditLog(
            workspace_id=workspace.id,
            actor=str(user.get("email") or user.get("user_id") or "unknown")[:320],
            action="workspace.invitation.revoked",
            resource_type="workspace_invitation",
            resource_id=invitation.id,
            outcome="revoked",
            details_json={"email": invitation.email, "role": invitation.role},
        ))
        await db.commit()
    return {"id": invitation.id, "status": "revoked"}


@api.post("/workspaces/invitations/accept")
async def accept_workspace_invitation(
    payload: WorkspaceInvitationAcceptRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    user_id = user.get("user_id")
    if not user_id or user_id == "local":
        raise HTTPException(403, "Sign in with a registered account to accept this invitation")
    account = await db.get(UserAccount, user_id)
    if account is None or not account.is_active:
        raise HTTPException(403, "Account is inactive or no longer available")
    digest = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    invitation = await db.scalar(select(WorkspaceInvitation).where(
        WorkspaceInvitation.token_hash == digest,
    ).with_for_update())
    if invitation is None:
        raise HTTPException(404, "Invitation token is invalid")
    status = _workspace_invitation_status(invitation, datetime.now(timezone.utc))
    if status == "accepted":
        raise HTTPException(409, "Invitation has already been accepted")
    if status == "revoked":
        raise HTTPException(410, "Invitation has been revoked")
    if status == "expired":
        raise HTTPException(410, "Invitation has expired")
    if account.email.strip().casefold() != invitation.email:
        raise HTTPException(403, "Sign in with the email address this invitation was issued to")
    workspace = await db.get(Workspace, invitation.workspace_id)
    if workspace is None or workspace.lifecycle_state != "active":
        raise HTTPException(409, "Invited workspace is suspended or unavailable")
    membership = await db.scalar(select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace.id,
        WorkspaceMembership.user_id == account.id,
    ))
    if membership is not None and membership.is_active:
        raise HTTPException(409, "This account is already an active workspace member")
    if membership is None:
        membership = WorkspaceMembership(workspace_id=workspace.id, user_id=account.id, role=invitation.role, is_active=True)
        db.add(membership)
    else:
        membership.role = invitation.role
        membership.is_active = True
    invitation.accepted_at = datetime.now(timezone.utc)
    updated_user = dict(user)
    updated_user.update({
        "user_id": account.id, "email": account.email,
        "workspace_id": workspace.id, "workspace_role": membership.role,
        "is_admin": account.is_admin is True,
    })
    request.session["user"] = updated_user
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    with workspace_scope(workspace.id):
        db.add(AuditLog(
            workspace_id=workspace.id,
            actor=account.email[:320],
            action="workspace.invitation.accepted",
            resource_type="workspace_invitation",
            resource_id=invitation.id,
            outcome="accepted",
            details_json={"email": account.email.casefold(), "role": membership.role},
        ))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            request.session.clear()
            raise HTTPException(409, "Invitation was already accepted or membership already exists") from None
    return {
        "invitation_id": invitation.id, "active_workspace_id": workspace.id,
        "workspace_name": workspace.name, "role": membership.role,
        "csrf_token": request.session["csrf_token"],
    }




def _provider_connection_payload(row: ProviderAccountConnection) -> dict[str, Any]:
    return {
        "id": row.id, "provider_id": row.provider_id, "status": row.status,
        "account_nicknames": list(row.account_nicknames_json or []),
        "capabilities": list(row.capabilities_json or []),
        "permissions_verified": ["API Order Read"] if "quickstats.accounts.read" in (row.capabilities_json or []) else [],
        "credential_present": bool(row.credential_ciphertext),
        "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
        "last_error_code": row.last_error_code,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _provider_connection_workspace(user: dict[str, Any]) -> str:
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before managing provider accounts.")
    return workspace_id


@api.get("/provider-connections")
async def list_provider_connections(user: dict[str, Any] = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    workspace_id = _provider_connection_workspace(user)
    with workspace_scope(workspace_id):
        rows = (await db.scalars(select(ProviderAccountConnection)
            .where(ProviderAccountConnection.workspace_id == workspace_id)
            .order_by(ProviderAccountConnection.created_at.desc(), ProviderAccountConnection.id.desc()))).all()
    return {"data": [_provider_connection_payload(row) for row in rows]}


@api.post("/provider-connections/clickbank", status_code=201)
async def connect_clickbank_account(payload: ClickBankConnectionCreateRequest, user: dict[str, Any] = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    workspace_id = _provider_connection_workspace(user)
    api_key = payload.api_key.get_secret_value()
    try:
        fingerprint = fingerprint_clickbank_api_key(api_key)
    except StoredCredentialError:
        raise HTTPException(503, "Provider credential encryption is not configured. Contact the platform operator.") from None
    with workspace_scope(workspace_id):
        existing = await db.scalar(select(ProviderAccountConnection).where(
            ProviderAccountConnection.workspace_id == workspace_id,
            ProviderAccountConnection.provider_id == "clickbank",
            ProviderAccountConnection.credential_fingerprint == fingerprint,
            ProviderAccountConnection.status != "disconnected",
        ))
    if existing is not None:
        raise HTTPException(409, "This ClickBank API key is already connected to the active workspace.")
    try:
        accounts = await verify_clickbank_api_key(api_key)
        encrypted = encrypt_clickbank_api_key(api_key)
    except ClickBankAccessError as exc:
        raise HTTPException(422, str(exc)) from None
    except ClickBankProviderUnavailable as exc:
        raise HTTPException(502, str(exc)) from None
    except StoredCredentialError:
        raise HTTPException(503, "Provider credential encryption is not configured. Contact the platform operator.") from None

    row = ProviderAccountConnection(
        workspace_id=workspace_id, provider_id="clickbank", status="connected_read_only",
        credential_ciphertext=encrypted, credential_fingerprint=fingerprint, credential_key_version=1,
        account_nicknames_json=accounts, capabilities_json=["quickstats.accounts.read"],
        created_by_user_id=str(user.get("user_id") or "")[:36] or None, last_checked_at=utcnow(),
    )
    with workspace_scope(workspace_id):
        db.add(row)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id, actor=str(user.get("email") or "workspace-operator")[:320],
            action="integration.provider_account_connected", resource_type="provider_account_connection",
            resource_id=row.id, outcome="connected_read_only",
            details_json={"provider_id":"clickbank","verified_endpoint":"quickstats/accounts",
                          "verified_permission":"API Order Read","account_count":len(accounts),"credential_encrypted":True},
        ))
        try:
            await db.commit()
            await db.refresh(row)
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "This ClickBank API key is already connected to the active workspace.") from None
    return _provider_connection_payload(row)


@api.post("/provider-connections/{connection_id}/test")
async def test_provider_account_connection(connection_id: str, user: dict[str, Any] = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    workspace_id = _provider_connection_workspace(user)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(ProviderAccountConnection).where(
            ProviderAccountConnection.id == connection_id, ProviderAccountConnection.workspace_id == workspace_id))
    if row is None:
        raise HTTPException(404, "Provider connection not found in the active workspace.")
    if row.status == "disconnected" or not row.credential_ciphertext:
        raise HTTPException(409, "This provider connection is disconnected. Connect it again to restore access.")
    try:
        api_key = decrypt_clickbank_api_key(row.credential_ciphertext, row.credential_key_version)
    except StoredCredentialError:
        outcome, status_code, detail = "credential_decryption_failed", 503, "Stored ClickBank credentials cannot be decrypted. Reconnect the account."
    else:
        try:
            accounts = await verify_clickbank_api_key(api_key)
            outcome, status_code, detail = "connected_read_only", 200, ""
        except ClickBankAccessError:
            outcome, status_code, detail = "credential_or_permission_rejected", 422, "ClickBank rejected the read-only account check. Verify the API key and API Order Read permission."
        except ClickBankProviderUnavailable:
            outcome, status_code, detail = "provider_unavailable", 502, "ClickBank could not complete the account verification request. Try again later."
    with workspace_scope(workspace_id):
        row.last_checked_at = utcnow()
        row.last_error_code = None if outcome == "connected_read_only" else outcome
        row.status = "connected_read_only" if outcome == "connected_read_only" else "degraded"
        if outcome == "connected_read_only":
            row.account_nicknames_json = accounts
            row.capabilities_json = ["quickstats.accounts.read"]
        db.add(AuditLog(
            workspace_id=workspace_id, actor=str(user.get("email") or "workspace-operator")[:320],
            action="integration.provider_account_tested", resource_type="provider_account_connection",
            resource_id=row.id, outcome=outcome, details_json={"provider_id":row.provider_id},
        ))
        await db.commit()
        await db.refresh(row)
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=detail)
    return _provider_connection_payload(row)


@api.get("/provider-connections/{connection_id}/quickstats")
async def clickbank_provider_quickstats(
    connection_id: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    account: str | None = Query(default=None, min_length=1, max_length=100),
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = _provider_connection_workspace(user)
    if start_date > end_date:
        raise HTTPException(422, "start_date must be on or before end_date.")
    if end_date > date.today():
        raise HTTPException(422, "end_date cannot be in the future.")
    if (end_date - start_date).days > 365:
        raise HTTPException(422, "Quickstats date ranges are limited to 366 inclusive days.")

    with workspace_scope(workspace_id):
        row = await db.scalar(select(ProviderAccountConnection).where(
            ProviderAccountConnection.id == connection_id,
            ProviderAccountConnection.workspace_id == workspace_id,
        ))
    if row is None:
        raise HTTPException(404, "Provider connection not found in the active workspace.")
    if row.provider_id != "clickbank" or row.status == "disconnected" or not row.credential_ciphertext:
        raise HTTPException(409, "An active ClickBank read-only connection is required.")
    if account and account.casefold() not in {name.casefold() for name in (row.account_nicknames_json or [])}:
        raise HTTPException(404, "The selected account nickname is not linked to this provider connection.")

    try:
        api_key = decrypt_clickbank_api_key(row.credential_ciphertext, row.credential_key_version)
        report = await fetch_clickbank_quickstats(
            api_key, start_date=start_date, end_date=end_date, account=account,
        )
    except StoredCredentialError:
        with workspace_scope(workspace_id):
            row.status = "degraded"
            row.last_error_code = "credential_decryption_failed"
            row.last_checked_at = utcnow()
            await db.commit()
        raise HTTPException(503, "Stored ClickBank credentials cannot be decrypted. Reconnect the account.") from None
    except ClickBankAccessError as exc:
        with workspace_scope(workspace_id):
            row.status = "degraded"
            row.last_error_code = "credential_or_permission_rejected"
            row.last_checked_at = utcnow()
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=str(user.get("email") or "workspace-operator")[:320],
                action="integration.provider_quickstats_read",
                resource_type="provider_account_connection",
                resource_id=row.id,
                outcome="permission_rejected",
                details_json={"provider_id":"clickbank","start_date":start_date.isoformat(),"end_date":end_date.isoformat(),"account":account},
            ))
            await db.commit()
        raise HTTPException(422, str(exc)) from None
    except ClickBankProviderUnavailable as exc:
        with workspace_scope(workspace_id):
            row.last_checked_at = utcnow()
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=str(user.get("email") or "workspace-operator")[:320],
                action="integration.provider_quickstats_read",
                resource_type="provider_account_connection",
                resource_id=row.id,
                outcome="provider_unavailable",
                details_json={"provider_id":"clickbank","start_date":start_date.isoformat(),"end_date":end_date.isoformat(),"account":account},
            ))
            await db.commit()
        raise HTTPException(502, str(exc)) from None

    with workspace_scope(workspace_id):
        row.last_checked_at = utcnow()
        row.last_error_code = None
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "workspace-operator")[:320],
            action="integration.provider_quickstats_read",
            resource_type="provider_account_connection",
            resource_id=row.id,
            outcome="provider_reported",
            details_json={
                "provider_id":"clickbank",
                "start_date":start_date.isoformat(),
                "end_date":end_date.isoformat(),
                "account":account,
                "daily_record_count":len(report["daily"]),
                "evidence_type":"provider_reported_aggregate",
            },
        ))
        await db.commit()
    return {
        "provider_id":"clickbank",
        "evidence_type":"provider_reported_aggregate",
        "metric_scope":"sales_refunds_chargebacks_not_affiliate_commission_or_payout",
        "period":{"start_date":start_date.isoformat(),"end_date":end_date.isoformat()},
        **report,
    }


@api.get("/provider-connections/{connection_id}/order-counts")
async def clickbank_provider_order_counts(
    connection_id: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    account: str = Query(..., min_length=1, max_length=100),
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = _provider_connection_workspace(user)
    if start_date > end_date:
        raise HTTPException(422, "start_date must be on or before end_date.")
    if end_date > date.today():
        raise HTTPException(422, "end_date cannot be in the future.")
    if (end_date - start_date).days > 365:
        raise HTTPException(422, "Orders count date ranges are limited to 366 inclusive days.")

    with workspace_scope(workspace_id):
        row = await db.scalar(select(ProviderAccountConnection).where(
            ProviderAccountConnection.id == connection_id,
            ProviderAccountConnection.workspace_id == workspace_id,
        ))
    if row is None:
        raise HTTPException(404, "Provider connection not found in the active workspace.")
    if row.provider_id != "clickbank" or row.status == "disconnected" or not row.credential_ciphertext:
        raise HTTPException(409, "An active ClickBank read-only connection is required.")
    if account.casefold() not in {name.casefold() for name in (row.account_nicknames_json or [])}:
        raise HTTPException(404, "The selected affiliate nickname is not linked to this provider connection.")

    try:
        api_key = decrypt_clickbank_api_key(row.credential_ciphertext, row.credential_key_version)
        report = await fetch_clickbank_order_counts(
            api_key, account=account, start_date=start_date, end_date=end_date,
        )
    except StoredCredentialError:
        with workspace_scope(workspace_id):
            row.status = "degraded"
            row.last_error_code = "credential_decryption_failed"
            row.last_checked_at = utcnow()
            await db.commit()
        raise HTTPException(503, "Stored ClickBank credentials cannot be decrypted. Reconnect the account.") from None
    except ClickBankAccessError as exc:
        with workspace_scope(workspace_id):
            row.last_checked_at = utcnow()
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=str(user.get("email") or "workspace-operator")[:320],
                action="integration.provider_order_counts_read",
                resource_type="provider_account_connection",
                resource_id=row.id,
                outcome="permission_rejected",
                details_json={
                    "provider_id":"clickbank",
                    "account":account,
                    "start_date":start_date.isoformat(),
                    "end_date":end_date.isoformat(),
                },
            ))
            await db.commit()
        raise HTTPException(422, str(exc)) from None
    except ClickBankProviderUnavailable as exc:
        with workspace_scope(workspace_id):
            row.last_checked_at = utcnow()
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=str(user.get("email") or "workspace-operator")[:320],
                action="integration.provider_order_counts_read",
                resource_type="provider_account_connection",
                resource_id=row.id,
                outcome="provider_unavailable",
                details_json={
                    "provider_id":"clickbank",
                    "account":account,
                    "start_date":start_date.isoformat(),
                    "end_date":end_date.isoformat(),
                },
            ))
            await db.commit()
        raise HTTPException(502, str(exc)) from None

    with workspace_scope(workspace_id):
        row.last_checked_at = utcnow()
        row.last_error_code = None
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "workspace-operator")[:320],
            action="integration.provider_order_counts_read",
            resource_type="provider_account_connection",
            resource_id=row.id,
            outcome="provider_reported",
            details_json={
                "provider_id":"clickbank",
                "account":account,
                "start_date":start_date.isoformat(),
                "end_date":end_date.isoformat(),
                "evidence_type":"provider_reported_transaction_counts",
            },
        ))
        await db.commit()
    return {
        "provider_id":"clickbank",
        "evidence_type":"provider_reported_transaction_counts",
        "metric_scope":"affiliate_sale_refund_chargeback_counts_not_commission_or_payout_amounts",
        "period":{"start_date":start_date.isoformat(),"end_date":end_date.isoformat()},
        **report,
    }



@api.post("/provider-connections/{connection_id}/orders/import")
async def import_clickbank_order_transactions(
    connection_id: str,
    payload: ClickBankOrderImportRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = _provider_connection_workspace(user)
    if payload.start_date > payload.end_date:
        raise HTTPException(422, "start_date must be on or before end_date.")
    if payload.end_date > date.today():
        raise HTTPException(422, "end_date cannot be in the future.")
    if (payload.end_date - payload.start_date).days > 365:
        raise HTTPException(422, "Orders date ranges are limited to 366 inclusive days.")

    with workspace_scope(workspace_id):
        connection = await db.scalar(select(ProviderAccountConnection).where(
            ProviderAccountConnection.id == connection_id,
            ProviderAccountConnection.workspace_id == workspace_id,
        ))
    if connection is None:
        raise HTTPException(404, "Provider connection not found in the active workspace.")
    if connection.provider_id != "clickbank" or connection.status == "disconnected" or not connection.credential_ciphertext:
        raise HTTPException(409, "An active ClickBank read-only connection is required.")
    if payload.account.casefold() not in {name.casefold() for name in (connection.account_nicknames_json or [])}:
        raise HTTPException(404, "The selected affiliate nickname is not linked to this provider connection.")

    try:
        api_key = decrypt_clickbank_api_key(connection.credential_ciphertext, connection.credential_key_version)
        report = await fetch_clickbank_order_transactions(
            api_key,
            account=payload.account,
            start_date=payload.start_date,
            end_date=payload.end_date,
            start_page=payload.start_page,
            max_pages=payload.max_pages,
        )
    except StoredCredentialError:
        with workspace_scope(workspace_id):
            connection.status = "degraded"
            connection.last_error_code = "credential_decryption_failed"
            connection.last_checked_at = utcnow()
            await db.commit()
        raise HTTPException(503, "Stored ClickBank credentials cannot be decrypted. Reconnect the account.") from None
    except ClickBankAccessError as exc:
        with workspace_scope(workspace_id):
            connection.last_checked_at = utcnow()
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=str(user.get("email") or "workspace-operator")[:320],
                action="integration.provider_order_transactions_read",
                resource_type="provider_account_connection",
                resource_id=connection.id,
                outcome="permission_rejected",
                details_json={
                    "provider_id":"clickbank",
                    "account":payload.account,
                    "start_date":payload.start_date.isoformat(),
                    "end_date":payload.end_date.isoformat(),
                },
            ))
            await db.commit()
        raise HTTPException(422, str(exc)) from None
    except ClickBankProviderUnavailable as exc:
        with workspace_scope(workspace_id):
            connection.last_checked_at = utcnow()
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=str(user.get("email") or "workspace-operator")[:320],
                action="integration.provider_order_transactions_read",
                resource_type="provider_account_connection",
                resource_id=connection.id,
                outcome="provider_unavailable",
                details_json={
                    "provider_id":"clickbank",
                    "account":payload.account,
                    "start_date":payload.start_date.isoformat(),
                    "end_date":payload.end_date.isoformat(),
                },
            ))
            await db.commit()
        raise HTTPException(502, str(exc)) from None

    transactions = report["transactions"]
    # A match requires the exact app-generated click ID, same workspace and TID campaign.
    click_id_candidates = sorted({
        item["tracking_click_id_candidate"] for item in transactions
        if isinstance(item.get("tracking_click_id_candidate"), str)
        and re.fullmatch(r"[0-9a-f]{32}", item["tracking_click_id_candidate"])
    })
    click_created_at: dict[str, datetime] = {}
    if click_id_candidates:
        with workspace_scope(workspace_id):
            click_rows = (await db.execute(
                select(ClickEvent.click_id, ClickEvent.created_at)
                .join(Campaign, Campaign.id == ClickEvent.campaign_id)
                .where(
                    ClickEvent.workspace_id == workspace_id,
                    Campaign.workspace_id == workspace_id,
                    Campaign.tracking_parameter == "tid",
                    ClickEvent.click_id.in_(click_id_candidates),
                    ClickEvent.chosen_destination != "",
                )
            )).all()
        click_created_at = {row[0]: row[1] for row in click_rows}

    for item in transactions:
        candidate = item.get("tracking_click_id_candidate")
        matched_click_id = None
        clicked_at = click_created_at.get(candidate) if isinstance(candidate, str) else None
        if clicked_at is not None:
            try:
                transaction_at = datetime.fromisoformat(str(item["transaction_time"]).replace("Z", "+00:00"))
                transaction_at = transaction_at.replace(tzinfo=timezone.utc) if transaction_at.tzinfo is None else transaction_at.astimezone(timezone.utc)
                clicked_at = clicked_at.replace(tzinfo=timezone.utc) if clicked_at.tzinfo is None else clicked_at.astimezone(timezone.utc)
                if clicked_at <= transaction_at <= clicked_at + timedelta(days=60):
                    matched_click_id = candidate
            except (KeyError, TypeError, ValueError, OverflowError):
                matched_click_id = None
        item["click_id"] = matched_click_id
        item["attribution_status"] = "matched_clickbank_tid" if matched_click_id else "not_matched"

    event_keys = list({item["event_key"] for item in transactions})
    existing_pairs: set[tuple[str, str]] = set()
    if event_keys:
        with workspace_scope(workspace_id):
            existing_rows = (await db.execute(
                select(ProviderOrderObservation.event_key, ProviderOrderObservation.source_fingerprint).where(
                    ProviderOrderObservation.workspace_id == workspace_id,
                    ProviderOrderObservation.connection_id == connection.id,
                    ProviderOrderObservation.event_key.in_(event_keys),
                )
            )).all()
            existing_pairs = {(item[0], item[1]) for item in existing_rows}

    imported: list[dict[str, Any]] = []
    duplicate_count = 0
    for item in transactions:
        identity = (item["event_key"], item["source_fingerprint"])
        if identity in existing_pairs:
            duplicate_count += 1
            continue
        existing_pairs.add(identity)
        observation = ProviderOrderObservation(
            workspace_id=workspace_id,
            connection_id=connection.id,
            provider_id="clickbank",
            event_key=item["event_key"],
            source_fingerprint=item["source_fingerprint"],
            click_id=item.get("click_id"),
            attribution_status=item.get("attribution_status", "not_matched"),
            account_nickname=item["account_nickname"],
            receipt=item["receipt"],
            transaction_time=item["transaction_time"],
            transaction_type=item["transaction_type"],
            role="AFFILIATE",
            vendor_nickname=item.get("vendor_nickname"),
            affiliate_nickname=item.get("affiliate_nickname"),
            currency=item.get("currency"),
            item_number=item.get("item_number"),
            line_item_type=item.get("line_item_type"),
            product_title=item.get("product_title"),
            account_amount=Decimal(item["account_amount"]) if item.get("account_amount") is not None else None,
            customer_amount=Decimal(item["customer_amount"]) if item.get("customer_amount") is not None else None,
            line_item_status=item.get("line_item_status"),
            recurring=item.get("recurring"),
            shippable=item.get("shippable"),
            evidence_status="provider_reported_unreconciled",
        )
        db.add(observation)
        imported.append(item)

    transaction_counts: dict[str, int] = {}
    for item in imported:
        transaction_counts[item["transaction_type"]] = transaction_counts.get(item["transaction_type"], 0) + 1

    with workspace_scope(workspace_id):
        connection.last_checked_at = utcnow()
        connection.last_error_code = None
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "workspace-operator")[:320],
            action="integration.provider_order_transactions_imported",
            resource_type="provider_account_connection",
            resource_id=connection.id,
            outcome="provider_reported_unreconciled",
            details_json={
                "provider_id":"clickbank",
                "account":payload.account,
                "start_date":payload.start_date.isoformat(),
                "end_date":payload.end_date.isoformat(),
                "pages_retrieved":report["pages_retrieved"],
                "has_more":report["has_more"],
                "source_order_count":report["source_order_count"],
                "normalized_line_item_count":len(transactions),
                "imported_count":len(imported),
                "duplicate_count":duplicate_count,
                "tracking_id_candidate_count":len(click_id_candidates),
                "matched_click_count":sum(item.get("attribution_status") == "matched_clickbank_tid" for item in imported),
                "unmatched_tracking_id_count":sum(bool(item.get("tracking_click_id_candidate")) and item.get("attribution_status") != "matched_clickbank_tid" for item in imported),
                "attribution_window_days":60,
                "transaction_counts":transaction_counts,
                "skipped_unidentified_count":report["skipped_unidentified_count"],
                "skipped_scope_count":report["skipped_scope_count"],
                "pii_stored":False,
            },
        ))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, "A matching order observation was imported concurrently. Retry the same date range to reconcile duplicates.") from None

    records = [{
        **{key: value for key, value in item.items() if key != "tracking_click_id_candidate"},
        "evidence_status":"provider_reported_unreconciled",
    } for item in imported]
    return {
        "provider_id":"clickbank",
        "evidence_type":"provider_reported_order_observations",
        "financial_semantics":"provider_account_amount_is_unreconciled_evidence_not_confirmed_commission_or_payout",
        "pii_stored":False,
        "period":{"start_date":payload.start_date.isoformat(),"end_date":payload.end_date.isoformat()},
        "account":payload.account,
        "pages_retrieved":report["pages_retrieved"],
        "source_order_count":report["source_order_count"],
        "skipped_unidentified_count":report["skipped_unidentified_count"],
        "skipped_scope_count":report["skipped_scope_count"],
        "imported_count":len(imported),
        "duplicate_count":duplicate_count,
        "matched_click_count":sum(item.get("attribution_status") == "matched_clickbank_tid" for item in imported),
        "unmatched_tracking_id_count":sum(bool(item.get("tracking_click_id_candidate")) and item.get("attribution_status") != "matched_clickbank_tid" for item in imported),
        "has_more":report["has_more"],
        "next_page":report["next_page"],
        "transactions":records,
        "note":"These are PII-minimized provider-reported affiliate transaction observations. A ClickBank TID match links an order to a local click only; it is not commission reconciliation, confirmed earnings or payout evidence. Account amounts remain unreconciled.",
    }


@api.delete("/provider-connections/{connection_id}")
async def disconnect_provider_account(connection_id: str, user: dict[str, Any] = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    workspace_id = _provider_connection_workspace(user)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(ProviderAccountConnection).where(
            ProviderAccountConnection.id == connection_id, ProviderAccountConnection.workspace_id == workspace_id))
        if row is None:
            raise HTTPException(404, "Provider connection not found in the active workspace.")
        row.status = "disconnected"
        row.credential_ciphertext = None
        row.credential_fingerprint = None
        row.last_error_code = None
        db.add(AuditLog(
            workspace_id=workspace_id, actor=str(user.get("email") or "workspace-operator")[:320],
            action="integration.provider_account_disconnected", resource_type="provider_account_connection",
            resource_id=row.id, outcome="disconnected",
            details_json={"provider_id":row.provider_id,"stored_credential_removed":True,"provider_key_revoked_remotely":False},
        ))
        await db.commit()
    return {"id":row.id,"provider_id":row.provider_id,"status":"disconnected","credential_present":False,
            "provider_key_revoked_remotely":False,
            "detail":"The saved credential was removed from OmniAffiliateOS. Revoke the API key separately in ClickBank API Management."}


@api.get("/integrations")
async def integration_registry(user: dict[str, Any] = Depends(require_platform_admin)):
    # Provider readiness is deployment-wide configuration state; do not disclose
    # it to anonymous visitors or ordinary workspace members.
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before viewing global provider configuration")
    return build_network_registry(settings.load_yaml())


@api.get("/skills/find")
async def skills_find(
    q: str = Query(min_length=2, max_length=120),
    stage: str | None = Query(default=None, max_length=2),
    status: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=10, ge=1, le=30),
    user: dict[str, Any] = Depends(require_auth),
):
    """Search the repository skill inventory without claiming the skills are production-ready."""
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before searching the skill inventory")
    try:
        return find_skills_service(query=q, stage=stage, status=status, limit=limit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, "Skill parity inventory is not packaged in this deployment") from exc





def _skill_package_dict(row: SkillPackage, *, include_contract: bool = True) -> dict[str, Any]:
    result = {
        "id": row.id,
        "skill_id": row.skill_id,
        "display_name": row.display_name,
        "version": row.version,
        "description": row.description,
        "stage": row.stage,
        "runtime_handler": row.runtime_handler or "none",
        "capabilities": list(row.capabilities_json or []),
        "validation_report": dict(row.validation_report_json or {}),
        "package_sha256": row.package_sha256,
        "status": row.status,
        "created_by": row.created_by,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "reviewer_notes": row.reviewer_notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "execution_boundary": (
            "Allowlisted built-in handler executes deterministic local logic; package Markdown is never executed and no external action is authorized."
            if row.runtime_handler and row.runtime_handler != "none"
            else "Declarative package only; instructions are not executed and approval does not authorize external actions."
        ),
    }
    if include_contract:
        result.update({
            "input_schema": dict(row.input_schema_json or {}),
            "output_schema": dict(row.output_schema_json or {}),
            "instructions_markdown": row.instructions_markdown,
            "test_cases": list(row.fixtures_json or []),
        })
    return result


@api.get("/skills/packages")
async def list_skill_packages(
    limit: int = Query(default=100, ge=1, le=200),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing skill packages")
    with workspace_scope(workspace_id):
        rows = list((await db.scalars(
            select(SkillPackage)
            .where(SkillPackage.workspace_id == workspace_id)
            .order_by(SkillPackage.created_at.desc())
            .limit(limit)
        )).all())
    return {"count": len(rows), "data": [_skill_package_dict(row, include_contract=False) for row in rows]}


@api.post("/skills/packages", status_code=201)
async def create_skill_package(
    payload: SkillPackageCreateRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating skill packages")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    package_payload = payload.model_dump(mode="json")
    try:
        built = build_skill_package(package_payload)
    except ValueError as exc:
        raise HTTPException(422, {"code": "SKILL_CONTRACT_SCHEMA_INVALID", "message": str(exc)}) from exc
    report = built["validation_report"]
    initial_status = "review_required" if report["all_fixtures_passed"] else "draft"
    with workspace_scope(workspace_id):
        existing = await db.scalar(select(SkillPackage.id).where(
            SkillPackage.workspace_id == workspace_id,
            SkillPackage.skill_id == payload.skill_id,
            SkillPackage.version == payload.version,
        ))
        if existing:
            raise HTTPException(409, "This skill identifier and version already exists in the active workspace")
        row = SkillPackage(
            workspace_id=workspace_id,
            skill_id=payload.skill_id,
            display_name=payload.display_name,
            version=payload.version,
            description=payload.description,
            stage=payload.stage,
            runtime_handler=payload.runtime_handler,
            capabilities_json=payload.capabilities,
            input_schema_json=payload.input_schema,
            output_schema_json=payload.output_schema,
            instructions_markdown=payload.instructions_markdown,
            fixtures_json=[case.model_dump(mode="json") for case in payload.test_cases],
            validation_report_json=report,
            package_sha256=built["package_sha256"],
            status=initial_status,
            created_by=actor,
        )
        db.add(row)
        try:
            await db.flush()
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=actor,
                action="skill_package.created",
                resource_type="skill_package",
                resource_id=row.id,
                outcome=initial_status,
                details_json={
                    "skill_id": row.skill_id,
                    "version": row.version,
                    "package_sha256": row.package_sha256,
                    "fixtures_passed": report["fixtures_passed"],
                    "fixtures_failed": report["fixtures_failed"],
                    "declarative_only": True,
                },
            ))
            await db.commit()
            await db.refresh(row)
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(409, "This skill identifier and version already exists in the active workspace") from exc
    return _skill_package_dict(row)


@api.get("/skills/packages/{package_id}")
async def get_skill_package(
    package_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing skill packages")
    with workspace_scope(workspace_id):
        row = await db.scalar(select(SkillPackage).where(
            SkillPackage.id == package_id,
            SkillPackage.workspace_id == workspace_id,
        ))
    if row is None:
        raise HTTPException(404, "Skill package not found in the active workspace")
    return _skill_package_dict(row)


@api.post("/skills/packages/{package_id}/execute")
async def execute_skill_package(
    package_id: str,
    payload: SkillPackageExecuteRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before executing a skill package")
    with workspace_scope(workspace_id):
        row = await db.scalar(select(SkillPackage).where(
            SkillPackage.id == package_id,
            SkillPackage.workspace_id == workspace_id,
        ))
    if row is None:
        raise HTTPException(404, "Skill package not found in the active workspace")
    if row.status != "approved":
        raise HTTPException(409, "Only an approved skill package can be executed")
    runtime_handler = str(row.runtime_handler or "none")
    if runtime_handler == "none" or runtime_handler not in SUPPORTED_RUNTIME_HANDLERS:
        raise HTTPException(409, "This package has no supported built-in runtime handler")

    package_manifest = {
        "skill_id": row.skill_id,
        "display_name": row.display_name,
        "version": row.version,
        "description": row.description,
        "stage": row.stage,
        "runtime_handler": runtime_handler,
        "capabilities": list(row.capabilities_json or []),
        "input_schema": dict(row.input_schema_json or {}),
        "output_schema": dict(row.output_schema_json or {}),
        "instructions_markdown": row.instructions_markdown,
        "test_cases": list(row.fixtures_json or []),
    }
    try:
        rebuilt = build_skill_package(package_manifest)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(409, "Stored skill package failed integrity validation; create a reviewed new version") from exc
    if rebuilt["package_sha256"] != row.package_sha256:
        raise HTTPException(409, "Stored skill package checksum no longer matches its immutable contract")
    input_errors = validate_skill_value(payload.input, row.input_schema_json, path="input")
    if input_errors:
        raise HTTPException(422, {
            "code": "SKILL_RUNTIME_INPUT_INVALID",
            "message": "Runtime input does not match the package input schema",
            "errors": input_errors[:20],
        })
    try:
        output = execute_skill_handler(runtime_handler, payload.input)
    except ValueError as exc:
        raise HTTPException(422, "Runtime input could not be processed by the selected handler") from exc
    output_errors = validate_skill_value(output, row.output_schema_json, path="output")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    if output_errors:
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="skill_package.execution_failed",
            resource_type="skill_package",
            resource_id=row.id,
            outcome="output_contract_violation",
            details_json={"runtime_handler": runtime_handler, "package_sha256": row.package_sha256, "error_count": len(output_errors)},
        ))
        await db.commit()
        raise HTTPException(500, "Built-in handler output failed the reviewed contract; no external action was taken")

    canonical_input = json.dumps(payload.input, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    canonical_output = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    db.add(AuditLog(
        workspace_id=workspace_id,
        actor=actor,
        action="skill_package.executed",
        resource_type="skill_package",
        resource_id=row.id,
        outcome="executed",
        details_json={
            "skill_id": row.skill_id,
            "version": row.version,
            "runtime_handler": runtime_handler,
            "package_sha256": row.package_sha256,
            "input_sha256": hashlib.sha256(canonical_input).hexdigest(),
            "output_sha256": hashlib.sha256(canonical_output).hexdigest(),
            "external_actions_executed": False,
            "skill_instructions_executed": False,
        },
    ))
    await db.commit()
    return {
        "status": "executed",
        "package_id": row.id,
        "skill_id": row.skill_id,
        "version": row.version,
        "runtime_handler": runtime_handler,
        "package_sha256": row.package_sha256,
        "result": output,
        "deterministic": True,
        "skill_instructions_executed": False,
        "external_actions_executed": False,
        "requires_human_approval_for_external_actions": True,
    }


@api.post("/skills/packages/{package_id}/review")
async def review_skill_package(
    package_id: str,
    payload: SkillPackageReviewRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing skill packages")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        row = await db.scalar(select(SkillPackage).where(
            SkillPackage.id == package_id,
            SkillPackage.workspace_id == workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Skill package not found in the active workspace")
        if row.status in {"approved", "rejected"}:
            raise HTTPException(409, "Reviewed skill packages are immutable; create a new version to change the contract")
        if payload.decision == "approve":
            if payload.confirm_contract_reviewed is not True:
                raise HTTPException(409, "Approval requires confirm_contract_reviewed=true after reviewing the manifest and fixtures")
            if row.validation_report_json.get("all_fixtures_passed") is not True:
                raise HTTPException(409, {
                    "code": "SKILL_CONTRACT_FIXTURES_FAILED",
                    "message": "Fix all input/output contract fixtures before approving this package version.",
                    "validation_report": row.validation_report_json,
                })
            row.status = "approved"
            outcome = "human_review_approved"
        else:
            row.status = "rejected"
            outcome = "human_review_rejected"
        row.reviewed_by = actor
        row.reviewed_at = utcnow()
        row.reviewer_notes = payload.reviewer_notes or None
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="skill_package.reviewed",
            resource_type="skill_package",
            resource_id=row.id,
            outcome=outcome,
            details_json={
                "skill_id": row.skill_id,
                "version": row.version,
                "package_sha256": row.package_sha256,
                "fixtures_passed": row.validation_report_json.get("fixtures_passed", 0),
                "fixtures_failed": row.validation_report_json.get("fixtures_failed", 0),
                "declarative_only": True,
                "external_action_authorized": False,
            },
        ))
        await db.commit()
        await db.refresh(row)
    return _skill_package_dict(row)


@api.post("/learning/proprietary-dataset", status_code=201)
async def generate_proprietary_dataset(
    payload: ProprietaryDatasetRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Persist a review-only dataset snapshot from the active workspace experiment ledger."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before generating a learning dataset")
    workspace_id = str(workspace_id)
    assignments = list((await db.scalars(
        select(ExperimentAssignment)
        .where(ExperimentAssignment.workspace_id == workspace_id)
        .order_by(ExperimentAssignment.assigned_at.desc())
        .limit(payload.max_assignments)
    )).all())
    events = list((await db.scalars(
        select(ExperimentEvent)
        .where(ExperimentEvent.workspace_id == workspace_id)
        .order_by(ExperimentEvent.occurred_at.desc())
        .limit(payload.max_events)
    )).all())
    dataset = build_proprietary_dataset_service(
        assignments, events,
        min_impressions=payload.min_impressions,
        min_conversions=payload.min_conversions,
    )
    eligible_rows = [row for row in dataset["rows"] if row["eligible_for_human_review"]]
    jsonl_body = "\n".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in eligible_rows
    )
    source_truncated = len(assignments) >= payload.max_assignments or len(events) >= payload.max_events
    asset = ContentAsset(
        workspace_id=workspace_id,
        asset_type="proprietary_training_dataset",
        title=payload.dataset_name,
        body=jsonl_body,
        status="review_required",
        source_urls=[],
        metadata_json={
            "dataset_version": dataset["dataset_version"],
            "dataset_format": dataset["dataset_format"],
            "source": "workspace_experiment_event_ledger",
            "summary": dataset["summary"],
            "thresholds": dataset["thresholds"],
            "eligible_rows_persisted": len(eligible_rows),
            "source_truncated": source_truncated,
            "visitor_identifiers_included": False,
            "provider_attested": False,
            "training_started": False,
            "model_updated": False,
            "requires_human_review": True,
        },
    )
    db.add(asset)
    await db.flush()
    db.add(AuditLog(
        workspace_id=workspace_id,
        actor=str(user.get("email") or "unknown"),
        action="learning.proprietary_dataset.generated",
        resource_type="content_asset",
        resource_id=asset.id,
        outcome="review_required",
        details_json={
            "eligible_rows_persisted": len(eligible_rows),
            "candidate_rows": len(dataset["rows"]),
            "excluded_low_sample": dataset["summary"]["excluded_low_sample"],
            "excluded_data_quality": dataset["summary"]["excluded_data_quality"],
            "source_truncated": source_truncated,
            "training_started": False,
            "model_updated": False,
        },
    ))
    await db.commit()
    dataset.update({
        "asset_id": asset.id,
        "asset_title": asset.title,
        "asset_status": asset.status,
        "eligible_rows_persisted": len(eligible_rows),
        "source_truncated": source_truncated,
        "publishing_started": False,
    })
    return dataset


@api.get("/capabilities")
async def capabilities(user: dict[str, Any] = Depends(require_platform_admin)):
    # This matrix reports global model, email, CMS and social credential
    # presence; expose it only to the platform operator with an active workspace.
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before viewing global capability configuration")
    registry = build_network_registry(settings.load_yaml())
    return build_capability_matrix(settings, registry)

@api.get("/status")
async def status(user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
 workspace_id = user.get("workspace_id")
 if not workspace_id:
  raise HTTPException(403, "Select an authorized workspace before viewing status")
 with workspace_scope(str(workspace_id)):
  clicks = int(await db.scalar(select(func.count(ClickEvent.id))) or 0)
  events = int(await db.scalar(select(func.count(Conversion.id))) or 0)
  commission = float(await db.scalar(select(func.coalesce(func.sum(Conversion.commission), 0.0))) or 0)
  recent = list((await db.scalars(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(6))).all())
 path = Path(settings.chroma_persist_dir)
 indexed = path.exists() and any(path.glob("**/*"))
 model_configured = (settings.llm_backend == "openai_compatible" and bool(settings.openai_api_key)) or (settings.llm_backend == "local_transformers" and bool(settings.local_model_path))
 return {"app_name":settings.app_name,"environment":settings.app_env,"execution_mode":settings.execution_mode,"stage_count":8,"stages":[{"id":k,"label":v} for k,v in LABELS.items()],"knowledge_index_available":indexed,"api_model_configured":model_configured,"email_delivery_configured":bool(settings.resend_api_key and settings.resend_from_email),"video_rendering_available":bool(settings.pexels_api_key),"publishing_dry_run":settings.publishing_dry_run,"ad_automation_execute":settings.ad_automation_execute,"clicks":clicks,"conversion_events":events,"commission_recorded":round(commission,2),"recent_workflows":[{"session_id":x.id,"name":x.workflow_name,"status":x.status,"current_step":x.current_step,"created_at":x.created_at.isoformat() if x.created_at else None} for x in recent]}

@api.get("/flywheel/status")
async def flywheel_status(user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
 workspace_id = user.get("workspace_id")
 if not workspace_id:
  raise HTTPException(403, "Select an authorized workspace before viewing workflow status")
 with workspace_scope(str(workspace_id)):
  run = await db.scalar(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()))
 if not run:
  return {"active_session":None,"stages":[{"id":k,"label":v,"status":"idle"} for k,v in LABELS.items()]}
 states=(run.state_json or {}).get("stages",{});stages=[{"id":k,"label":v,"status":states.get(k,{}).get("status","pending"),"error":states.get(k,{}).get("error")} for k,v in LABELS.items()]
 stage_keys=list(LABELS);active=None
 if run.status=="paused" and run.current_step<len(stage_keys):active=stage_keys[run.current_step];stages[run.current_step]["status"]="waiting_for_human"
 elif run.status=="running" and run.current_step<len(stage_keys):active=stage_keys[run.current_step];stages[run.current_step]["status"]="running"
 control=(run.state_json or {}).get("control",{})
 return {"active_session":run.id,"workflow_name":run.workflow_name,"workflow_status":run.status,"cancel_requested":isinstance(control,dict) and control.get("cancel_requested") is True,"current_step":run.current_step,"active_stage":active,"execution_mode":run.execution_mode,"stages":stages}
@api.post("/workflows/run",status_code=202)
async def start_workflow(
    payload: WorkflowStartRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before starting a workflow")
    state = dict(payload.state)
    raw_metadata = state.get("metadata")
    metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
    has_publish_requests = bool(state.get("publish_requests"))
    supplied_publish_key = str(request.headers.get("Idempotency-Key") or "").strip()
    if has_publish_requests and not settings.publishing_dry_run:
        if user.get("is_admin") is not True:
            raise HTTPException(403, "Platform Super Admin permission required for live workflow publishing")
        if payload.confirm_live_publish is not True:
            raise HTTPException(409, "Live workflow publishing requires confirm_live_publish=true from an authorized operator")
        if not EXTERNAL_IDEMPOTENCY_KEY_RE.fullmatch(supplied_publish_key):
            raise HTTPException(428, "A valid Idempotency-Key header is required for live workflow publishing")
    # Never trust authorization or idempotency metadata supplied inside client workflow state.
    metadata.update({
        "workspace_id": str(workspace_id),
        "initiated_by": str(user.get("email") or user.get("user_id") or "unknown")[:320],
        "platform_admin_authorized": user.get("is_admin") is True,
        "live_publish_confirmed": payload.confirm_live_publish is True and user.get("is_admin") is True,
        "workflow_publish_idempotency_key": supplied_publish_key or None,
    })
    state["metadata"] = metadata
    try:
        with workspace_scope(str(workspace_id)):
            sid = await runner.start(payload.workflow_name, state, resolve_steps(payload.workflow_name), payload.execution_mode)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"session_id": sid, "status": "queued", "workflow_name": payload.workflow_name,
            "execution_mode": payload.execution_mode or settings.execution_mode,
            "status_url": f"/api/workflows/{sid}"}

@api.get("/workflows/{session_id}")
async def workflow_status(session_id: str, user: dict[str, Any] = Depends(require_auth)):
 workspace_id = user.get("workspace_id")
 if not workspace_id:
  raise HTTPException(403, "Select an authorized workspace before viewing a workflow")
 data = await runner.status(session_id, workspace_id=str(workspace_id))
 if data is None:
  raise HTTPException(404, "Workflow session not found")
 return data

@api.post("/workflows/{session_id}/cancel")
async def cancel_workflow(session_id: str, user: dict[str, Any] = Depends(require_auth)):
 workspace_id = user.get("workspace_id")
 if not workspace_id:
  raise HTTPException(403, "Select an authorized workspace before cancelling a workflow")
 try:
  with workspace_scope(str(workspace_id)):
   return await runner.request_cancel(
    session_id,
    workspace_id=str(workspace_id),
    actor=str(user.get("email") or user.get("user_id") or "operator"),
   )
 except KeyError as exc:
  raise HTTPException(404, "Workflow session not found") from exc
 except ValueError as exc:
  raise HTTPException(409, str(exc)) from exc

@api.post("/resume/{session_id}")
async def resume(session_id: str, payload: ResumeRequest, user: dict[str, Any] = Depends(require_auth)):
 workspace_id = user.get("workspace_id")
 if not workspace_id:
  raise HTTPException(403, "Select an authorized workspace before resuming a workflow")
 try:
  with workspace_scope(str(workspace_id)):
   return await runner.resume(
    session_id,
    payload.verification_code,
    workspace_id=str(workspace_id),
    actor=str(user.get("email") or user.get("user_id") or "operator"),
   )
 except KeyError as exc:
  raise HTTPException(404, "Workflow session not found") from exc
 except ValueError as exc:
  raise HTTPException(409, str(exc)) from exc
@api.post("/knowledge/ingest", dependencies=[Depends(require_platform_admin)])
async def knowledge_ingest():
 try:return {"status":"indexed",**await asyncio.to_thread(ingest_doctrine,settings.skills_root,Path(settings.chroma_persist_dir),settings.embedding_model,1200,180)}
 except FileNotFoundError as exc:raise HTTPException(400,str(exc)) from exc
 except Exception as exc:logger.exception("RAG ingest failed");raise HTTPException(500,f"RAG ingest failed: {type(exc).__name__}: {str(exc)[:200]}") from exc
@api.get("/knowledge/status")
async def knowledge_status():
 path=Path(settings.chroma_persist_dir)
 return {"available":path.exists() and any(path.glob("**/*")),"storage_configured":bool(settings.chroma_persist_dir),"collection":"affiliate_doctrine","required_references":["offer-frameworks.md","platform-rules.md","seo-strategy.md","social-data-providers.md"]}
@api.get("/offers")
async def offers(
    q: str | None = Query(default=None, min_length=1, max_length=100),
    network: str | None = Query(default=None, min_length=1, max_length=100),
    category: str | None = Query(default=None, min_length=1, max_length=200),
    reward_type: str | None = Query(default=None, min_length=1, max_length=100),
    recurring_commission: bool | None = None,
    min_cookie_days: int | None = Query(default=None, ge=0, le=2_147_483_647),
    provider_claimed_verified: bool | None = None,
    sort_by: Literal[
        "name", "network", "cookie_days", "traffic_score", "gravity_score",
        "epc", "conversion_rate", "source_stars", "updated_at",
    ] | None = None,
    sort_order: Literal["asc", "desc"] = "asc",
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    """Search the persisted shared offer catalog without implying provider authentication."""
    stmt = select(Offer)
    normalized_q = q.strip() if q else ""
    if normalized_q:
        pattern = f"%{normalized_q}%"
        stmt = stmt.where(or_(
            Offer.name.ilike(pattern),
            Offer.description.ilike(pattern),
            Offer.category.ilike(pattern),
        ))
    if network:
        stmt = stmt.where(func.lower(Offer.network) == network.strip().lower())
    if category:
        stmt = stmt.where(Offer.category.ilike(f"%{category.strip()}%"))
    if reward_type:
        stmt = stmt.where(func.lower(Offer.reward_type) == reward_type.strip().lower())
    if recurring_commission is not None:
        stmt = stmt.where(Offer.recurring_commission.is_(recurring_commission))
    if min_cookie_days is not None:
        stmt = stmt.where(Offer.cookie_days >= min_cookie_days)
    if provider_claimed_verified is not None:
        stmt = stmt.where(Offer.verified.is_(provider_claimed_verified))

    total_count = int(await db.scalar(select(func.count()).select_from(stmt.subquery()) ) or 0)
    if sort_by is None:
        ordering = (Offer.verified.desc(), Offer.name.asc())
    else:
        sort_column = getattr(Offer, sort_by)
        # Keep the ORDER BY expression in a one-item tuple. Expanding a bare
        # SQLAlchemy expression with *ordering invokes its unsupported __getitem__.
        ordering = (
            sort_column.asc().nullslast(),
        ) if sort_order == "asc" else (
            sort_column.desc().nullslast(),
        )
    rows = list((await db.scalars(
        stmt.order_by(*ordering).offset(offset).limit(limit)
    )).all())
    return {
        "count": len(rows),
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "data": [
            {
                "id": offer.id,
                "network": offer.network,
                "external_id": offer.external_id,
                "name": offer.name,
                "url": offer.url,
                "category": offer.category,
                "description": offer.description,
                "reward_type": offer.reward_type,
                "reward_value": offer.reward_value,
                "cookie_days": offer.cookie_days,
                "traffic_score": offer.traffic_score,
                "gravity_score": offer.gravity_score,
                "normalized_gravity": offer.normalized_gravity,
                "epc": offer.epc,
                "conversion_rate": offer.conversion_rate,
                "recurring_commission": offer.recurring_commission,
                "source_stars": offer.source_stars,
                "verified": offer.verified,
                "verification_basis": (
                    "provider_claimed_unattested"
                    if offer.verified
                    else "provider_not_verified_or_unknown"
                ),
                "source_url": offer.source_url,
                "updated_at": offer.updated_at.isoformat() if offer.updated_at else None,
            }
            for offer in rows
        ],
    }

@api.get("/offers/qualification-queue")
async def offer_qualification_queue(
    status: Literal["needs_review", "not_reviewed", "pending_review", "needs_evidence", "qualified", "rejected", "deferred", "all"] = "needs_review",
    offset: int = Query(default=0, ge=0, le=100_000),
    limit: int = Query(default=50, ge=1, le=100),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Show shared catalog offers with this workspace's independent manual review state."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing offer qualification")
    join_clause = and_(OfferQualificationReview.offer_id == Offer.id,
                       OfferQualificationReview.workspace_id == str(workspace_id))
    stmt = select(Offer, OfferQualificationReview).outerjoin(OfferQualificationReview, join_clause)
    if status == "needs_review":
        stmt = stmt.where(or_(OfferQualificationReview.id.is_(None),
            OfferQualificationReview.status.in_(["pending_review", "needs_evidence", "deferred"])))
    elif status == "not_reviewed":
        stmt = stmt.where(OfferQualificationReview.id.is_(None))
    elif status != "all":
        stmt = stmt.where(OfferQualificationReview.status == status)
    total_count = int(await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    pairs = (await db.execute(stmt.order_by(Offer.name.asc(), Offer.id.asc()).offset(offset).limit(limit))).all()
    data = []
    for offer, review in pairs:
        data.append({
            "offer": {"id": offer.id, "network": offer.network, "external_id": offer.external_id, "name": offer.name,
                "category": offer.category, "description": offer.description, "url": offer.url, "cookie_days": offer.cookie_days,
                "reward_type": offer.reward_type, "reward_value": offer.reward_value, "epc": offer.epc,
                "conversion_rate": offer.conversion_rate,
                "verification_basis": "provider_claimed_unattested" if offer.verified else "provider_not_verified_or_unknown"},
            "qualification": {"status": review.status if review else "not_reviewed",
                "account_eligibility": review.account_eligibility if review else "unknown",
                "geography_fit": review.geography_fit if review else "unknown",
                "traffic_source_fit": review.traffic_source_fit if review else "unknown",
                "terms_review": review.terms_review if review else "unknown",
                "landing_page_review": review.landing_page_review if review else "unknown",
                "disclosure_review": review.disclosure_review if review else "unknown",
                "evidence_urls": review.evidence_urls if review and isinstance(review.evidence_urls, list) else [],
                "notes": review.notes if review else "", "policy_version": review.policy_version if review else "manual-review-v1",
                "reviewed_by": review.reviewed_by if review else None,
                "reviewed_at": review.reviewed_at.isoformat() if review and review.reviewed_at else None,
                "evidence_basis": "operator_supplied_unverified", "affiliate_network_approval_implied": False},
        })
    return {"count": len(data), "total_count": total_count, "offset": offset, "limit": limit,
        "status_filter": status, "data": data,
        "note": "Qualification decisions are workspace-specific operator reviews, not provider verification or affiliate-network approval."}


@api.post("/offers/{offer_id}/qualification")
async def save_offer_qualification(
    offer_id: str,
    payload: OfferQualificationReviewRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Persist a workspace operator's qualification checklist and review decision."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before saving offer qualification")
    if str(user.get("workspace_role") or "").lower() not in {"owner", "admin"}:
        raise HTTPException(403, "Only workspace owners and admins may record offer qualification decisions")
    offer = await db.scalar(select(Offer).where(Offer.id == offer_id))
    if offer is None:
        raise HTTPException(404, "Catalog offer not found")
    review = await db.scalar(select(OfferQualificationReview).where(
        OfferQualificationReview.workspace_id == str(workspace_id), OfferQualificationReview.offer_id == offer.id))
    if review is None:
        review = OfferQualificationReview(workspace_id=str(workspace_id), offer_id=offer.id)
        db.add(review)
    review.status = payload.status
    review.account_eligibility = payload.account_eligibility
    review.geography_fit = payload.geography_fit
    review.traffic_source_fit = payload.traffic_source_fit
    review.terms_review = payload.terms_review
    review.landing_page_review = payload.landing_page_review
    review.disclosure_review = payload.disclosure_review
    review.evidence_urls = payload.evidence_urls
    review.notes = payload.notes
    review.policy_version = payload.policy_version
    review.reviewed_by = str(user.get("email") or user.get("user_id") or "workspace-operator")[:320]
    review.reviewed_at = datetime.now(timezone.utc)
    try:
        await db.commit()
        await db.refresh(review)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "A concurrent qualification review changed this offer; reload and retry") from exc
    return {"offer_id": offer.id, "status": review.status, "account_eligibility": review.account_eligibility,
        "geography_fit": review.geography_fit, "traffic_source_fit": review.traffic_source_fit,
        "terms_review": review.terms_review, "landing_page_review": review.landing_page_review,
        "disclosure_review": review.disclosure_review, "evidence_urls": review.evidence_urls, "notes": review.notes,
        "policy_version": review.policy_version, "reviewed_by": review.reviewed_by,
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "evidence_basis": "operator_supplied_unverified", "affiliate_network_approval_implied": False,
        "activation_allowed": False}


@api.get("/offers/shortlists")
async def list_offer_shortlists(user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    """List only the active workspace's saved offer shortlists."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing saved offer lists")
    rows = list((await db.scalars(select(OfferShortlist).where(
        OfferShortlist.workspace_id == str(workspace_id)
    ).order_by(OfferShortlist.updated_at.desc(), OfferShortlist.name.asc()).limit(100))).all())
    result = []
    for row in rows:
        count = int(await db.scalar(select(func.count()).select_from(OfferShortlistItem).where(
            OfferShortlistItem.workspace_id == str(workspace_id), OfferShortlistItem.shortlist_id == row.id
        )) or 0)
        result.append({"id": row.id, "name": row.name, "description": row.description, "item_count": count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None})
    return {"count": len(result), "limit": 100, "data": result}


@api.post("/offers/shortlists", status_code=201)
async def create_offer_shortlist(payload: OfferShortlistCreateRequest, user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    """Create a workspace-owned shortlist; no provider-side action is performed."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating a saved offer list")
    row = OfferShortlist(workspace_id=str(workspace_id), name=payload.name, description=payload.description)
    db.add(row)
    try:
        await db.commit()
        await db.refresh(row)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "A saved offer list with this name already exists in the workspace") from exc
    return {"id": row.id, "name": row.name, "description": row.description, "item_count": 0,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None}


@api.get("/offers/shortlists/{shortlist_id}")
async def get_offer_shortlist(shortlist_id: str, user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    """Return a saved list with current catalog facts and explicit unknowns."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing a saved offer list")
    row = await db.scalar(select(OfferShortlist).where(OfferShortlist.id == shortlist_id, OfferShortlist.workspace_id == str(workspace_id)))
    if row is None:
        raise HTTPException(404, "Saved offer list not found")
    pairs = (await db.execute(select(OfferShortlistItem, Offer).join(Offer, Offer.id == OfferShortlistItem.offer_id).where(
        OfferShortlistItem.workspace_id == str(workspace_id), OfferShortlistItem.shortlist_id == row.id
    ).order_by(OfferShortlistItem.created_at.asc(), Offer.name.asc()))).all()
    items = []
    for item, offer in pairs:
        items.append({"item_id": item.id, "note": item.note, "added_at": item.created_at.isoformat() if item.created_at else None,
            "offer": {"id": offer.id, "network": offer.network, "external_id": offer.external_id, "name": offer.name,
                "url": offer.url, "category": offer.category, "description": offer.description, "reward_type": offer.reward_type,
                "reward_value": offer.reward_value, "cookie_days": offer.cookie_days, "traffic_score": offer.traffic_score,
                "gravity_score": offer.gravity_score, "normalized_gravity": offer.normalized_gravity, "epc": offer.epc,
                "conversion_rate": offer.conversion_rate, "recurring_commission": offer.recurring_commission,
                "source_stars": offer.source_stars,
                "verification_basis": "provider_claimed_unattested" if offer.verified else "provider_not_verified_or_unknown",
                "source_url": offer.source_url}})
    return {"id": row.id, "name": row.name, "description": row.description, "count": len(items), "items": items,
        "created_at": row.created_at.isoformat() if row.created_at else None, "updated_at": row.updated_at.isoformat() if row.updated_at else None}


@api.post("/offers/shortlists/{shortlist_id}/items", status_code=201)
async def add_offer_to_shortlist(shortlist_id: str, payload: OfferShortlistItemCreateRequest, user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before saving an offer")
    shortlist = await db.scalar(select(OfferShortlist).where(OfferShortlist.id == shortlist_id, OfferShortlist.workspace_id == str(workspace_id)))
    if shortlist is None:
        raise HTTPException(404, "Saved offer list not found")
    offer = await db.scalar(select(Offer).where(Offer.id == payload.offer_id))
    if offer is None:
        raise HTTPException(404, "Catalog offer not found")
    item = OfferShortlistItem(workspace_id=str(workspace_id), shortlist_id=shortlist.id, offer_id=offer.id, note=payload.note)
    db.add(item)
    try:
        await db.commit()
        await db.refresh(item)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "This offer is already in the saved list") from exc
    return {"id": item.id, "shortlist_id": shortlist.id, "offer_id": offer.id, "note": item.note,
        "created_at": item.created_at.isoformat() if item.created_at else None}


@api.delete("/offers/shortlists/{shortlist_id}/items/{offer_id}")
async def remove_offer_from_shortlist(shortlist_id: str, offer_id: str, user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before editing a saved offer list")
    item = await db.scalar(select(OfferShortlistItem).where(OfferShortlistItem.workspace_id == str(workspace_id),
        OfferShortlistItem.shortlist_id == shortlist_id, OfferShortlistItem.offer_id == offer_id))
    if item is None:
        raise HTTPException(404, "Saved offer item not found")
    await db.delete(item)
    await db.commit()
    return {"deleted": True, "shortlist_id": shortlist_id, "offer_id": offer_id}


@api.delete("/offers/shortlists/{shortlist_id}")
async def delete_offer_shortlist(shortlist_id: str, user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before deleting a saved offer list")
    row = await db.scalar(select(OfferShortlist).where(OfferShortlist.id == shortlist_id, OfferShortlist.workspace_id == str(workspace_id)))
    if row is None:
        raise HTTPException(404, "Saved offer list not found")
    items = list((await db.scalars(select(OfferShortlistItem).where(
        OfferShortlistItem.workspace_id == str(workspace_id), OfferShortlistItem.shortlist_id == row.id))).all())
    for item in items:
        await db.delete(item)
    await db.delete(row)
    await db.commit()
    return {"deleted": True, "id": shortlist_id}


@api.get("/integrations/openaffiliate/sync-status")
async def openaffiliate_sync_status(
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    """Return the latest OpenAffiliate sync audit outcome for the active operator workspace."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing catalog sync status")
    audit = await db.scalar(
        select(AuditLog).where(
            AuditLog.workspace_id == str(workspace_id),
            AuditLog.action == "offers.sync",
            AuditLog.resource_type == "offer_registry",
        ).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)
    )
    note = (
        "This is an audited local sync outcome, not independent provider identity, account eligibility, "
        "source authenticity or offer-approval evidence."
    )
    if audit is None:
        return {
            "provider": "openaffiliate",
            "state": "never_synced",
            "last_attempt_at": None,
            "created": None,
            "updated": None,
            "registry_total": None,
            "requested_limit": None,
            "query_supplied": False,
            "error_type": None,
            "source_attestation_verified": False,
            "note": note,
        }
    details = audit.details_json if isinstance(audit.details_json, dict) else {}

    def count_or_unknown(value: Any) -> int | None:
        return value if type(value) is int and value >= 0 else None

    state = audit.outcome if audit.outcome in {"completed", "failed"} else "unknown"
    return {
        "provider": "openaffiliate",
        "state": state,
        "last_attempt_at": audit.created_at.isoformat() if audit.created_at else None,
        "created": count_or_unknown(details.get("created")),
        "updated": count_or_unknown(details.get("updated")),
        "registry_total": count_or_unknown(details.get("registry_total")),
        "requested_limit": count_or_unknown(details.get("requested_limit")),
        "query_supplied": details.get("query_supplied") is True,
        "error_type": str(details["error_type"])[:120] if isinstance(details.get("error_type"), str) else None,
        "source_attestation_verified": False,
        "note": note,
    }


@api.get("/integrations/openaffiliate/sync-history")
async def openaffiliate_sync_history(
    limit: int = Query(default=10, ge=1, le=50),
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    """Return a bounded, sanitized history of OpenAffiliate sync audit outcomes for one workspace."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing catalog sync history")
    rows = list((await db.scalars(
        select(AuditLog).where(
            AuditLog.workspace_id == str(workspace_id),
            AuditLog.action == "offers.sync",
            AuditLog.resource_type == "offer_registry",
        ).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    )).all())

    def count_or_unknown(value: Any) -> int | None:
        return value if type(value) is int and value >= 0 else None

    items = []
    for audit in rows:
        details = audit.details_json if isinstance(audit.details_json, dict) else {}
        items.append({
            "state": audit.outcome if audit.outcome in {"completed", "failed"} else "unknown",
            "attempted_at": audit.created_at.isoformat() if audit.created_at else None,
            "created": count_or_unknown(details.get("created")),
            "updated": count_or_unknown(details.get("updated")),
            "registry_total": count_or_unknown(details.get("registry_total")),
            "requested_limit": count_or_unknown(details.get("requested_limit")),
            "query_supplied": details.get("query_supplied") is True,
            "error_type": str(details["error_type"])[:120] if isinstance(details.get("error_type"), str) else None,
            "source_attestation_verified": False,
        })
    return {
        "provider": "openaffiliate",
        "count": len(items),
        "limit": limit,
        "source_attestation_verified": False,
        "note": (
            "History contains local sync audit outcomes only. It is not evidence of independent provider identity, "
            "account eligibility, source authenticity or offer approval."
        ),
        "items": items,
    }


@api.post("/offers/sync")
async def offers_sync(
    q: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    # Offer rows form the shared catalog (Offer is intentionally not tenant-scoped).
    # Only a platform admin may refresh this global registry from a remote provider.
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before synchronizing the global offer registry")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    owner_workspace_id = str(workspace_id)
    try:
        data = await openaffiliate_client.fetch_programs(q=q, limit=limit)
    except Exception as exc:
        with workspace_scope(owner_workspace_id):
            db.add(AuditLog(
                workspace_id=owner_workspace_id,
                actor=actor,
                action="offers.sync",
                resource_type="offer_registry",
                outcome="failed",
                details_json={
                    "provider": "openaffiliate",
                    "error_type": type(exc).__name__[:120],
                    "requested_limit": limit,
                    "query_supplied": bool(q),
                },
            ))
            await db.commit()
        raise HTTPException(502, f"OpenAffiliate error: {type(exc).__name__}: {str(exc)[:200]}") from exc

    created = updated = 0
    try:
        # This catalog is global rather than workspace-owned; queries are over the
        # unique (network, external_id) identity, and rows remain evidence-tagged
        # with provider-supplied verification/metrics only.
        for item in data["data"]:
            external_id = str(item.get("slug") or item.get("id") or "")
            if not external_id:
                continue
            row = await db.scalar(
                select(Offer).where(
                    Offer.network == "openaffiliate",
                    Offer.external_id == external_id,
                )
            )
            if row is None:
                row = Offer(network="openaffiliate", external_id=external_id, name=item["name"])
                db.add(row)
                created += 1
            else:
                updated += 1
            row.name = item["name"]
            row.url = item.get("url")
            row.category = item.get("category")
            row.description = item.get("description", "")
            row.reward_type = item.get("reward_type")
            row.reward_value = item.get("reward_value")
            row.cookie_days = item.get("cookie_days")
            row.traffic_score = item.get("traffic_score")
            row.source_stars = item.get("stars_count")
            provider_verified = item.get("verified")
            # Provider verification is trusted only when the adapter supplied an
            # actual JSON boolean. Truthy strings such as "false" must not grant
            # a positive verification badge.
            row.verified = provider_verified if isinstance(provider_verified, bool) else False
            raw = item.get("raw") or {}
            row.source_url = raw.get("source_url") if isinstance(raw, dict) else None
            metrics = compute_offer_metrics({
                "reward_type": row.reward_type,
                "reward_value": row.reward_value,
                "gravity_score": raw.get("gravity_score", raw.get("gravity")),
            })
            row.gravity_score = metrics["gravity_score"]
            row.normalized_gravity = metrics["normalized_gravity"]
            row.epc = metrics["epc"]
            row.conversion_rate = metrics["conversion_rate"]
            row.recurring_commission = metrics["recurring_commission"]
            row.metadata_json = {"tags": item.get("tags", [])}
        await db.commit()
    except Exception:
        await db.rollback()
        with workspace_scope(owner_workspace_id):
            db.add(AuditLog(
                workspace_id=owner_workspace_id,
                actor=actor,
                action="offers.sync",
                resource_type="offer_registry",
                outcome="failed",
                details_json={
                    "provider": "openaffiliate",
                    "error_type": "CatalogPersistenceError",
                    "requested_limit": limit,
                    "query_supplied": bool(q),
                },
            ))
            await db.commit()
        raise

    with workspace_scope(owner_workspace_id):
        db.add(AuditLog(
            workspace_id=owner_workspace_id,
            actor=actor,
            action="offers.sync",
            resource_type="offer_registry",
            outcome="completed",
            details_json={
                "provider": "openaffiliate",
                "created": created,
                "updated": updated,
                "registry_total": data.get("registry_total"),
                "requested_limit": limit,
                "query_supplied": bool(q),
            },
        ))
        await db.commit()
    return {
        "created": created,
        "updated": updated,
        "registry_total": data.get("registry_total"),
        "traffic_score_note": "Unknown unless upstream actually supplies the field.",
    }
@api.post("/automation/multi-program-manager", status_code=201)
async def automation_multi_program_manager(
    payload: MultiProgramManagerRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Analyze supplied affiliate metrics and save a review-only weekly plan."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing your affiliate portfolio")
    try:
        generated = manage_program_portfolio_service(
            programs=[program.model_dump(mode="python") for program in payload.programs],
            goal=payload.goal,
            budget_hours=payload.budget_hours,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    with workspace_scope(str(workspace_id)):
        asset = ContentAsset(
            workspace_id=str(workspace_id),
            asset_type="affiliate_portfolio_review",
            title=f"Affiliate portfolio review — {generated['portfolio']['total_programs']} program(s)",
            body=json.dumps(generated, ensure_ascii=False, sort_keys=True),
            status="draft",
            source_urls=[item["affiliate_url"] for item in generated["programs"] if item.get("affiliate_url")],
            metadata_json={
                "multi_program_manager_version": "1",
                "goal": payload.goal,
                "budget_hours": generated["weekly_plan"]["total_hours"],
                "program_count": generated["portfolio"]["total_programs"],
                "metrics_source": "operator_supplied_unverified",
                "requires_review": True,
                "program_mutations_started": False,
            },
        )
        db.add(asset)
        await db.commit()
    return {**generated, "asset_id": asset.id}





def _merchant_offer_dict(row: MerchantOffer) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "product_url": row.product_url,
        "description": row.description,
        "category": row.category,
        "commission_type": row.commission_type,
        "commission_value": format(Decimal(row.commission_value), "f"),
        "commission_currency": row.commission_currency,
        "terms_version": row.terms_version,
        "commission_terms_url": row.commission_terms_url,
        "seller_authorization_url": row.seller_authorization_url,
        "allowed_regions": row.allowed_regions_json or [],
        "restricted_traffic_sources": row.restricted_traffic_sources_json or [],
        "affiliate_disclosure": row.affiliate_disclosure,
        "status": row.status,
        "terms_verified": row.terms_verified is True,
        "seller_authorization_verified": row.seller_authorization_verified is True,
        "activation_allowed": row.activation_allowed is True,
        "reviewer_notes": row.reviewer_notes,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "affiliate_network_approval_status": row.affiliate_network_approval_status,
        "marketplace_listed": row.marketplace_listed is True,
        "affiliate_network_approved": False,
        "provider_submission_performed": False,
    }



MAX_MERCHANT_TERMS_SOURCE_BYTES = 1_500_000
MERCHANT_TERMS_FETCH_TIMEOUT_SECONDS = 8.0
MERCHANT_TERMS_TEXT_TYPES = {"text/html", "application/xhtml+xml", "text/plain"}


class _MerchantTermsTextExtractor(HTMLParser):
    """Extract readable page text without executing or preserving script/style content."""

    _SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "iframe", "template"}
    _SEPARATOR_TAGS = {
        "address", "article", "blockquote", "br", "dd", "div", "dl", "dt", "h1", "h2",
        "h3", "h4", "h5", "h6", "li", "ol", "p", "section", "td", "th", "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif self._skip_depth == 0 and tag in self._SEPARATOR_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif self._skip_depth == 0 and tag in self._SEPARATOR_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def _extract_merchant_terms_text(body: bytes, content_type: str) -> str:
    decoded = body.decode("utf-8", errors="replace")
    if content_type in {"text/html", "application/xhtml+xml"}:
        parser = _MerchantTermsTextExtractor()
        parser.feed(decoded)
        parser.close()
        decoded = parser.text()
    decoded = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", decoded)
    return re.sub(r"\s+", " ", decoded).strip()[:3000]


def _merchant_term_evidence_fetch_dict(row: MerchantOfferTermEvidenceFetch) -> dict[str, Any]:
    return {
        "id": row.id,
        "merchant_offer_id": row.merchant_offer_id,
        "term_snapshot_id": row.term_snapshot_id,
        "source_url": row.source_url,
        "fetch_status": row.fetch_status,
        "http_status_code": row.http_status_code,
        "content_type": row.content_type,
        "response_bytes": row.response_bytes,
        "content_sha256": row.content_sha256,
        "previous_content_sha256": row.previous_content_sha256,
        "content_change_status": row.content_change_status,
        "review_status": row.review_status,
        "review_decision": row.review_decision,
        "review_notes": row.review_notes,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "requires_human_review": row.content_change_status == "content_changed" and row.review_status == "pending_review",
        "text_excerpt": row.text_excerpt,
        "etag": row.etag,
        "last_modified": row.last_modified,
        "error_code": row.error_code,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
        "provider_verified": row.provider_verified is True,
        "requested_by": row.requested_by,
    }


async def _fetch_merchant_terms_source(source_url: str) -> dict[str, Any]:
    """Make one explicitly requested, bounded HTTPS GET without following redirects."""
    result: dict[str, Any] = {
        "fetch_status": "network_error",
        "http_status_code": None,
        "content_type": None,
        "response_bytes": None,
        "content_sha256": None,
        "text_excerpt": "",
        "etag": None,
        "last_modified": None,
        "error_code": None,
    }
    if urlparse(source_url).scheme.lower() != "https":
        result.update(fetch_status="blocked_target", error_code="https_required")
        return result

    request_headers = {
        "Accept": "text/html, application/xhtml+xml, text/plain;q=0.9",
        "User-Agent": "OmniAffiliateOS-TermEvidence/1.0",
    }
    try:
        async with open_public_http_response(
            source_url,
            method="GET",
            headers=request_headers,
            timeout=MERCHANT_TERMS_FETCH_TIMEOUT_SECONDS,
        ) as response:
            result["http_status_code"] = int(response.status_code)
            raw_content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            result["content_type"] = raw_content_type[:160] or None
            result["etag"] = (response.headers.get("etag") or "")[:500] or None
            result["last_modified"] = (response.headers.get("last-modified") or "")[:200] or None

            if 300 <= response.status_code < 400:
                result.update(fetch_status="redirect_blocked", error_code="redirect_not_followed")
                return result
            if response.status_code < 200 or response.status_code >= 300:
                result.update(fetch_status="http_error", error_code="upstream_http_error")
                return result
            if raw_content_type not in MERCHANT_TERMS_TEXT_TYPES:
                result.update(fetch_status="unsupported_content_type", error_code="text_content_required")
                return result

            try:
                body = await read_limited_response(
                    response, max_bytes=MAX_MERCHANT_TERMS_SOURCE_BYTES, raw=False
                )
            except ValueError as exc:
                if "exceeds byte limit" in str(exc).casefold():
                    result.update(fetch_status="too_large", error_code="response_too_large")
                else:
                    result.update(fetch_status="invalid_response", error_code="invalid_response_length")
                return result

            text_excerpt = _extract_merchant_terms_text(body, raw_content_type)
            result.update(
                fetch_status="fetched" if text_excerpt else "empty_content",
                response_bytes=len(body),
                content_sha256=hashlib.sha256(body).hexdigest(),
                text_excerpt=text_excerpt,
                error_code=None if text_excerpt else "no_readable_text",
            )
            return result
    except ValueError as exc:
        message = str(exc).casefold()
        if any(token in message for token in ("private", "loopback", "link-local", "reserved", "local hostname", "blocked")):
            result.update(fetch_status="blocked_target", error_code="public_destination_rejected")
        elif "timeout" in message or "dns lookup failed" in message or "no addresses" in message:
            result.update(fetch_status="network_error", error_code="dns_or_timeout_error")
        else:
            result.update(fetch_status="blocked_target", error_code="public_destination_rejected")
        return result
    except (httpx.HTTPError, TimeoutError):
        result.update(fetch_status="network_error", error_code="request_or_timeout_error")
        return result
    except Exception:
        # Do not put exception text or provider-controlled response content in logs or API errors.
        result.update(fetch_status="network_error", error_code="unexpected_fetch_error")
        return result


def _merchant_offer_term_snapshot_dict(row: MerchantOfferTermSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "merchant_offer_id": row.merchant_offer_id,
        "sequence_number": row.sequence_number,
        "terms_version": row.terms_version,
        "commission_type": row.commission_type,
        "commission_value": format(Decimal(row.commission_value), "f"),
        "commission_currency": row.commission_currency,
        "cookie_days": row.cookie_days,
        "attribution_window_days": row.attribution_window_days,
        "allowed_regions": row.allowed_regions_json or [],
        "restricted_traffic_sources": row.restricted_traffic_sources_json or [],
        "source_url": row.source_url,
        "evidence_type": row.evidence_type,
        "evidence_excerpt": row.evidence_excerpt,
        "observed_at": row.observed_at.isoformat() if row.observed_at else None,
        "captured_at": row.captured_at.isoformat() if row.captured_at else None,
        "terms_sha256": row.terms_sha256,
        "change_status": row.change_status,
        "changed_fields": row.changed_fields_json or [],
        "changes": row.changes_json or [],
        "requires_revalidation": bool(row.changed_fields_json),
        "provenance_status": row.provenance_status,
        "provider_verified": row.provider_verified is True,
        "source_content_fetched": row.source_content_fetched is True,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@api.post("/merchant/offers", status_code=201)
async def create_merchant_offer(
    payload: MerchantOfferCreateRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Create a workspace-owned merchant offer draft; no external listing or affiliate-network approval occurs."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating a merchant offer")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = MerchantOffer(
            workspace_id=workspace_id,
            created_by=str(user.get("email") or "unknown")[:320],
            name=payload.name,
            product_url=payload.product_url,
            description=payload.description,
            category=payload.category,
            commission_type=payload.commission_type,
            commission_value=payload.commission_value,
            commission_currency=payload.commission_currency,
            terms_version=payload.terms_version,
            commission_terms_url=payload.commission_terms_url,
            seller_authorization_url=payload.seller_authorization_url,
            allowed_regions_json=payload.allowed_regions,
            restricted_traffic_sources_json=payload.restricted_traffic_sources,
            affiliate_disclosure=payload.affiliate_disclosure,
            status="draft",
            terms_verified=False,
            seller_authorization_verified=False,
            activation_allowed=False,
            affiliate_network_approval_status="not_configured",
        )
        db.add(row)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "unknown"),
            action="merchant.offer.created",
            resource_type="merchant_offer",
            resource_id=row.id,
            outcome="draft",
            details_json={
                "commission_type": row.commission_type,
                "currency": row.commission_currency,
                "terms_verified": False,
                "seller_authorization_verified": False,
                "activation_allowed": False,
                "affiliate_network_approval_status": "not_configured",
            },
        ))
        await db.commit()
        await db.refresh(row)
    return _merchant_offer_dict(row)


@api.get("/merchant/offers")
async def list_merchant_offers(
    limit: int = Query(default=100, ge=1, le=300),
    status: str | None = Query(default=None, max_length=40),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before listing merchant offers")
    valid_statuses = {"draft", "submitted_for_review", "approved", "rejected", "suspended"}
    if status is not None and status not in valid_statuses:
        raise HTTPException(422, "Unsupported merchant offer status filter")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        query = select(MerchantOffer).where(MerchantOffer.workspace_id == workspace_id)
        if status is not None:
            query = query.where(MerchantOffer.status == status)
        rows = list((await db.scalars(query.order_by(MerchantOffer.created_at.desc()).limit(limit))).all())
    return {"count": len(rows), "data": [_merchant_offer_dict(row) for row in rows]}


@api.post("/merchant/offers/{offer_id}/term-snapshots", status_code=201)
async def capture_merchant_offer_term_snapshot(
    offer_id: str,
    payload: MerchantOfferTermSnapshotCreateRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Persist operator-entered term evidence and invalidate approvals when material terms change."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before recording offer term evidence")
    workspace_id = str(workspace_id)
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        offer = await db.scalar(select(MerchantOffer).where(
            MerchantOffer.id == offer_id,
            MerchantOffer.workspace_id == workspace_id,
        ).with_for_update())
        if offer is None:
            raise HTTPException(404, "Merchant offer not found in the active workspace")

        latest = await db.scalar(select(MerchantOfferTermSnapshot).where(
            MerchantOfferTermSnapshot.workspace_id == workspace_id,
            MerchantOfferTermSnapshot.merchant_offer_id == offer.id,
        ).order_by(
            MerchantOfferTermSnapshot.sequence_number.desc(),
            MerchantOfferTermSnapshot.captured_at.desc(),
            MerchantOfferTermSnapshot.created_at.desc(),
            MerchantOfferTermSnapshot.id.desc(),
        ).limit(1))

        current_terms = {
            "terms_version": payload.terms_version,
            "commission_type": payload.commission_type,
            "commission_value": payload.commission_value,
            "commission_currency": payload.commission_currency,
            "cookie_days": payload.cookie_days,
            "attribution_window_days": payload.attribution_window_days,
            "allowed_regions": payload.allowed_regions,
            "restricted_traffic_sources": payload.restricted_traffic_sources,
        }
        previous_terms = ({
            "terms_version": latest.terms_version,
            "commission_type": latest.commission_type,
            "commission_value": latest.commission_value,
            "commission_currency": latest.commission_currency,
            "cookie_days": latest.cookie_days,
            "attribution_window_days": latest.attribution_window_days,
            "allowed_regions": latest.allowed_regions_json or [],
            "restricted_traffic_sources": latest.restricted_traffic_sources_json or [],
        } if latest is not None else {
            "terms_version": offer.terms_version,
            "commission_type": offer.commission_type,
            "commission_value": offer.commission_value,
            "commission_currency": offer.commission_currency,
            "cookie_days": None,
            "attribution_window_days": None,
            "allowed_regions": offer.allowed_regions_json or [],
            "restricted_traffic_sources": offer.restricted_traffic_sources_json or [],
        })
        report = compare_offer_terms(
            previous_terms,
            current_terms,
            has_previous_snapshot=latest is not None,
        )
        previous_offer_status = offer.status
        if report["requires_revalidation"]:
            offer.terms_verified = False
            offer.activation_allowed = False
            offer.marketplace_listed = False
            if offer.status == "approved":
                offer.status = "suspended"
            elif offer.status == "submitted_for_review":
                offer.status = "draft"

        snapshot = MerchantOfferTermSnapshot(
            workspace_id=workspace_id,
            merchant_offer_id=offer.id,
            sequence_number=(latest.sequence_number + 1 if latest is not None else 1),
            terms_version=report["current_terms"]["terms_version"],
            commission_type=report["current_terms"]["commission_type"],
            commission_value=Decimal(report["current_terms"]["commission_value"]),
            commission_currency=report["current_terms"]["commission_currency"],
            cookie_days=report["current_terms"]["cookie_days"],
            attribution_window_days=report["current_terms"]["attribution_window_days"],
            allowed_regions_json=report["current_terms"]["allowed_regions"],
            restricted_traffic_sources_json=report["current_terms"]["restricted_traffic_sources"],
            source_url=payload.source_url or offer.commission_terms_url,
            evidence_type=payload.evidence_type,
            evidence_excerpt=payload.evidence_excerpt,
            observed_at=payload.observed_at or utcnow(),
            terms_sha256=report["terms_sha256"],
            change_status=report["change_status"],
            changed_fields_json=report["changed_fields"],
            changes_json=report["changes"],
            provenance_status="operator_supplied_unverified",
            provider_verified=False,
            source_content_fetched=False,
            created_by=actor,
        )
        db.add(snapshot)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="merchant.offer.terms_snapshot_captured",
            resource_type="merchant_offer",
            resource_id=offer.id,
            outcome=report["change_status"],
            details_json={
                "snapshot_id": snapshot.id,
                "terms_sha256": report["terms_sha256"],
                "changed_fields": report["changed_fields"],
                "requires_revalidation": report["requires_revalidation"],
                "previous_offer_status": previous_offer_status,
                "current_offer_status": offer.status,
                "provider_verified": False,
                "source_content_fetched": False,
            },
        ))
        await db.commit()
        await db.refresh(snapshot)
        await db.refresh(offer)

    return {
        **_merchant_offer_term_snapshot_dict(snapshot),
        "requires_revalidation": report["requires_revalidation"],
        "offer_status": offer.status,
        "terms_verified": offer.terms_verified is True,
        "activation_allowed": offer.activation_allowed is True,
        "marketplace_listed": offer.marketplace_listed is True,
    }


@api.get("/merchant/offers/{offer_id}/term-snapshots")
async def list_merchant_offer_term_snapshots(
    offer_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """List immutable term snapshots visible to the active workspace."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing offer term evidence")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        offer = await db.scalar(select(MerchantOffer).where(
            MerchantOffer.id == offer_id,
            MerchantOffer.workspace_id == workspace_id,
        ))
        if offer is None:
            raise HTTPException(404, "Merchant offer not found in the active workspace")
        rows = list((await db.scalars(select(MerchantOfferTermSnapshot).where(
            MerchantOfferTermSnapshot.workspace_id == workspace_id,
            MerchantOfferTermSnapshot.merchant_offer_id == offer.id,
        ).order_by(
            MerchantOfferTermSnapshot.sequence_number.desc(),
            MerchantOfferTermSnapshot.captured_at.desc(),
            MerchantOfferTermSnapshot.created_at.desc(),
            MerchantOfferTermSnapshot.id.desc(),
        ).limit(limit))).all())
    return {"count": len(rows), "data": [_merchant_offer_term_snapshot_dict(row) for row in rows]}


@api.post("/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetch-evidence", status_code=201)
async def fetch_merchant_offer_terms_evidence(
    offer_id: str,
    snapshot_id: str,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Fetch a cited HTTPS page on explicit request; never verify or approve the offer automatically."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before fetching offer evidence")
    workspace_id = str(workspace_id)
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        offer = await db.scalar(select(MerchantOffer).where(
            MerchantOffer.id == offer_id,
            MerchantOffer.workspace_id == workspace_id,
        ))
        if offer is None:
            raise HTTPException(404, "Merchant offer not found in the active workspace")
        snapshot = await db.scalar(select(MerchantOfferTermSnapshot).where(
            MerchantOfferTermSnapshot.id == snapshot_id,
            MerchantOfferTermSnapshot.workspace_id == workspace_id,
            MerchantOfferTermSnapshot.merchant_offer_id == offer.id,
        ))
        if snapshot is None:
            raise HTTPException(404, "Term snapshot not found in the active workspace")
        source_url = snapshot.source_url
        previous_hash = await db.scalar(select(MerchantOfferTermEvidenceFetch.content_sha256).where(
            MerchantOfferTermEvidenceFetch.workspace_id == workspace_id,
            MerchantOfferTermEvidenceFetch.merchant_offer_id == offer.id,
            MerchantOfferTermEvidenceFetch.term_snapshot_id == snapshot.id,
            MerchantOfferTermEvidenceFetch.content_sha256.is_not(None),
        ).order_by(
            MerchantOfferTermEvidenceFetch.fetched_at.desc(),
            MerchantOfferTermEvidenceFetch.id.desc(),
        ).limit(1))
        # Do not hold a database read transaction open while contacting an external server.
        await db.rollback()

    result = await _fetch_merchant_terms_source(source_url)
    current_hash = result["content_sha256"]
    if current_hash is None:
        content_change_status = "not_comparable"
    elif previous_hash is None:
        content_change_status = "baseline_recorded"
    elif current_hash == previous_hash:
        content_change_status = "unchanged"
    else:
        content_change_status = "content_changed"
    with workspace_scope(workspace_id):
        row = MerchantOfferTermEvidenceFetch(
            workspace_id=workspace_id,
            merchant_offer_id=offer_id,
            term_snapshot_id=snapshot_id,
            source_url=source_url,
            fetch_status=result["fetch_status"],
            http_status_code=result["http_status_code"],
            content_type=result["content_type"],
            response_bytes=result["response_bytes"],
            content_sha256=result["content_sha256"],
            previous_content_sha256=previous_hash,
            content_change_status=content_change_status,
            review_status="pending_review" if content_change_status == "content_changed" else "not_required",
            text_excerpt=result["text_excerpt"],
            etag=result["etag"],
            last_modified=result["last_modified"],
            error_code=result["error_code"],
            fetched_at=utcnow(),
            provider_verified=False,
            requested_by=actor,
        )
        db.add(row)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="merchant.offer.terms_source_fetch_attempted",
            resource_type="merchant_offer",
            resource_id=offer_id,
            outcome=result["fetch_status"],
            details_json={
                "snapshot_id": snapshot_id,
                "fetch_record_id": row.id,
                "http_status_code": result["http_status_code"],
                "content_type": result["content_type"],
                "response_bytes": result["response_bytes"],
                "content_sha256": result["content_sha256"],
                "previous_content_sha256": previous_hash,
                "content_change_status": content_change_status,
                "requires_human_review": content_change_status == "content_changed",
                "provider_verified": False,
                "offer_approval_changed": False,
            },
        ))
        await db.commit()
        await db.refresh(row)
    return _merchant_term_evidence_fetch_dict(row)


@api.get("/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetches")
async def list_merchant_offer_terms_evidence_fetches(
    offer_id: str,
    snapshot_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """List bounded fetch-attempt evidence for one workspace-owned terms snapshot."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing offer evidence fetches")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        offer = await db.scalar(select(MerchantOffer).where(
            MerchantOffer.id == offer_id,
            MerchantOffer.workspace_id == workspace_id,
        ))
        if offer is None:
            raise HTTPException(404, "Merchant offer not found in the active workspace")
        snapshot = await db.scalar(select(MerchantOfferTermSnapshot).where(
            MerchantOfferTermSnapshot.id == snapshot_id,
            MerchantOfferTermSnapshot.workspace_id == workspace_id,
            MerchantOfferTermSnapshot.merchant_offer_id == offer.id,
        ))
        if snapshot is None:
            raise HTTPException(404, "Term snapshot not found in the active workspace")
        rows = list((await db.scalars(select(MerchantOfferTermEvidenceFetch).where(
            MerchantOfferTermEvidenceFetch.workspace_id == workspace_id,
            MerchantOfferTermEvidenceFetch.merchant_offer_id == offer.id,
            MerchantOfferTermEvidenceFetch.term_snapshot_id == snapshot.id,
        ).order_by(
            MerchantOfferTermEvidenceFetch.fetched_at.desc(),
            MerchantOfferTermEvidenceFetch.id.desc(),
        ).limit(limit))).all())
    return {"count": len(rows), "data": [_merchant_term_evidence_fetch_dict(row) for row in rows]}


@api.post("/merchant/offers/{offer_id}/term-snapshots/{snapshot_id}/fetches/{fetch_id}/review")
async def review_merchant_offer_terms_source_change(
    offer_id: str,
    snapshot_id: str,
    fetch_id: str,
    payload: MerchantOfferTermEvidenceReviewRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Record an independent human decision for changed source content."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing source evidence")
    workspace_id = str(workspace_id)
    reviewer = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        offer = await db.scalar(select(MerchantOffer).where(
            MerchantOffer.id == offer_id,
            MerchantOffer.workspace_id == workspace_id,
        ).with_for_update())
        if offer is None:
            raise HTTPException(404, "Merchant offer not found in the active workspace")
        snapshot = await db.scalar(select(MerchantOfferTermSnapshot).where(
            MerchantOfferTermSnapshot.id == snapshot_id,
            MerchantOfferTermSnapshot.workspace_id == workspace_id,
            MerchantOfferTermSnapshot.merchant_offer_id == offer.id,
        ))
        if snapshot is None:
            raise HTTPException(404, "Term snapshot not found in the active workspace")
        fetch_row = await db.scalar(select(MerchantOfferTermEvidenceFetch).where(
            MerchantOfferTermEvidenceFetch.id == fetch_id,
            MerchantOfferTermEvidenceFetch.workspace_id == workspace_id,
            MerchantOfferTermEvidenceFetch.merchant_offer_id == offer.id,
            MerchantOfferTermEvidenceFetch.term_snapshot_id == snapshot.id,
        ).with_for_update())
        if fetch_row is None:
            raise HTTPException(404, "Evidence fetch record not found in the active workspace")
        if fetch_row.content_change_status != "content_changed":
            raise HTTPException(409, "Only source-content changes require this review action")
        if fetch_row.review_status != "pending_review":
            raise HTTPException(409, "This source-content change has already been reviewed")
        if reviewer.strip().casefold() in {
            (offer.created_by or "").strip().casefold(),
            (snapshot.created_by or "").strip().casefold(),
        }:
            raise HTTPException(403, "A different workspace owner/admin must review the offer creator's source change")

        previous_offer_status = offer.status
        fetch_row.review_decision = payload.decision
        fetch_row.review_notes = payload.reviewer_notes
        fetch_row.reviewed_by = reviewer
        fetch_row.reviewed_at = utcnow()
        if payload.decision == "no_material_change":
            fetch_row.review_status = "reviewed_no_material_change"
        elif payload.decision == "material_change_found":
            fetch_row.review_status = "material_change_found"
            offer.terms_verified = False
            offer.activation_allowed = False
            offer.marketplace_listed = False
            if offer.status == "approved":
                offer.status = "suspended"
            elif offer.status == "submitted_for_review":
                offer.status = "draft"
        else:
            fetch_row.review_status = "source_unreliable"
            offer.terms_verified = False
            offer.activation_allowed = False
            offer.marketplace_listed = False
            if offer.status == "approved":
                offer.status = "suspended"
            elif offer.status == "submitted_for_review":
                offer.status = "draft"

        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=reviewer,
            action="merchant.offer.terms_source_change_reviewed",
            resource_type="merchant_offer",
            resource_id=offer.id,
            outcome=fetch_row.review_status,
            details_json={
                "snapshot_id": snapshot.id,
                "fetch_record_id": fetch_row.id,
                "review_decision": payload.decision,
                "review_notes": payload.reviewer_notes,
                "previous_offer_status": previous_offer_status,
                "current_offer_status": offer.status,
                "terms_verified": offer.terms_verified is True,
                "activation_allowed": offer.activation_allowed is True,
                "marketplace_listed": offer.marketplace_listed is True,
            },
        ))
        await db.commit()
        await db.refresh(fetch_row)
        await db.refresh(offer)
    return {
        **_merchant_term_evidence_fetch_dict(fetch_row),
        "offer_status": offer.status,
        "terms_verified": offer.terms_verified is True,
        "activation_allowed": offer.activation_allowed is True,
        "marketplace_listed": offer.marketplace_listed is True,
    }




@api.post("/merchant/offers/{offer_id}/submit")
async def submit_merchant_offer(
    offer_id: str,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Submit an offer packet for a different workspace owner/admin to review."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before submitting a merchant offer")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(MerchantOffer).where(
            MerchantOffer.id == offer_id,
            MerchantOffer.workspace_id == workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Merchant offer not found in the active workspace")
        if row.status != "draft":
            raise HTTPException(409, "Only a draft merchant offer can be submitted; create a new draft to replace a reviewed packet")
        blockers = []
        if not row.product_url:
            blockers.append("product_url_required")
        if not row.commission_terms_url or not row.terms_version:
            blockers.append("commission_terms_evidence_required")
        if not row.seller_authorization_url:
            blockers.append("seller_authorization_evidence_required")
        if len((row.affiliate_disclosure or "").strip()) < 12:
            blockers.append("affiliate_disclosure_required")
        if blockers:
            raise HTTPException(409, {"message": "Merchant offer is not ready for review", "blockers": blockers})
        row.status = "submitted_for_review"
        row.activation_allowed = False
        db.add(AuditLog(
            workspace_id=workspace_id, actor=str(user.get("email") or "unknown"),
            action="merchant.offer.submitted", resource_type="merchant_offer", resource_id=row.id,
            outcome=row.status,
            details_json={"evidence_references_present": True, "source_content_independently_fetched": False,
                          "activation_allowed": False, "affiliate_network_approved": False},
        ))
        await db.commit()
        await db.refresh(row)
    return _merchant_offer_dict(row)


@api.post("/merchant/offers/{offer_id}/review")
async def review_merchant_offer(
    offer_id: str,
    payload: MerchantOfferReviewRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Human review within the workspace; internal approval is not an external network approval."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing a merchant offer")
    workspace_id = str(workspace_id)
    reviewer = str(user.get("email") or "unknown")[:320]
    with workspace_scope(workspace_id):
        row = await db.scalar(select(MerchantOffer).where(
            MerchantOffer.id == offer_id,
            MerchantOffer.workspace_id == workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Merchant offer not found in the active workspace")
        if row.created_by.strip().casefold() == reviewer.strip().casefold():
            raise HTTPException(403, "A different workspace owner/admin must review the offer creator's packet")
        if payload.decision in {"approve", "reject"} and row.status != "submitted_for_review":
            raise HTTPException(409, "Only a submitted merchant offer can be approved or rejected")
        if payload.decision == "suspend" and row.status != "approved":
            raise HTTPException(409, "Only an internally approved offer can be suspended")
        if payload.decision == "approve":
            if payload.seller_authorization_verified is not True or payload.commission_terms_verified is not True:
                raise HTTPException(409, "Approval requires explicit seller-authorization and commission-terms verification")
            if not row.seller_authorization_url or not row.commission_terms_url or len(row.affiliate_disclosure.strip()) < 12:
                raise HTTPException(409, "Seller evidence, commission terms and affiliate disclosure must be present")
            row.status = "approved"
            row.seller_authorization_verified = True
            row.terms_verified = True
            row.activation_allowed = True
        elif payload.decision == "reject":
            row.status = "rejected"
            row.activation_allowed = False
            row.seller_authorization_verified = False
            row.terms_verified = False
        else:
            row.status = "suspended"
            row.activation_allowed = False
            row.marketplace_listed = False
        row.reviewer_notes = payload.reviewer_notes
        row.reviewed_by = reviewer
        row.reviewed_at = datetime.now(timezone.utc)
        row.affiliate_network_approval_status = "not_configured"
        db.add(AuditLog(
            workspace_id=workspace_id, actor=reviewer,
            action="merchant.offer.reviewed", resource_type="merchant_offer", resource_id=row.id,
            outcome=row.status,
            details_json={
                "decision": payload.decision,
                "seller_authorization_verified": row.seller_authorization_verified,
                "commission_terms_verified": row.terms_verified,
                "activation_allowed": row.activation_allowed,
                "affiliate_network_approval_status": "not_configured",
                "affiliate_network_approved": False,
            },
        ))
        await db.commit()
        await db.refresh(row)
    return _merchant_offer_dict(row)





def _marketplace_offer_public_dict(row: MerchantOffer) -> dict[str, Any]:
    """Return only fields intended for discovery; hide seller authorization and internal review notes."""
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "category": row.category,
        "commission_type": row.commission_type,
        "commission_value": format(Decimal(row.commission_value), "f"),
        "commission_currency": row.commission_currency,
        "terms_version": row.terms_version,
        "commission_terms_url": row.commission_terms_url,
        "allowed_regions": row.allowed_regions_json or [],
        "restricted_traffic_sources": row.restricted_traffic_sources_json or [],
        "affiliate_disclosure": row.affiliate_disclosure,
        "marketplace_listed": row.marketplace_listed is True,
        "internal_status": row.status,
        "affiliate_network_approval_status": row.affiliate_network_approval_status,
        "affiliate_network_approved": False,
        "provider_submission_performed": False,
    }


def _marketplace_application_dict(row: MarketplaceApplication) -> dict[str, Any]:
    snapshot = row.terms_snapshot_json or {}
    return {
        "id": row.id,
        "merchant_offer_id": row.merchant_offer_id,
        "merchant_workspace_id": row.merchant_workspace_id,
        "publisher_workspace_id": row.workspace_id,
        "offer_name": str(snapshot.get("name") or "Marketplace offer"),
        "terms_snapshot": snapshot,
        "applicant_email": row.applicant_email,
        "publisher_website_url": row.publisher_website_url,
        "audience_description": row.audience_description,
        "traffic_sources": row.traffic_sources_json or [],
        "intended_regions": row.intended_regions_json or [],
        "promotion_plan": row.promotion_plan,
        "compliance_answers": row.compliance_answers_json or {},
        "status": row.status,
        "reviewer_notes": row.reviewer_notes,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "provider_submission_status": "not_configured",
        "affiliate_network_approved": False,
        "provider_submission_performed": False,
    }


@api.post("/merchant/offers/{offer_id}/list")
async def list_merchant_offer_in_marketplace(
    offer_id: str,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """List an internally approved offer on this application's marketplace, not on an external network."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before listing a merchant offer")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(MerchantOffer).where(
            MerchantOffer.id == offer_id,
            MerchantOffer.workspace_id == workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Merchant offer not found in the active workspace")
        if row.status != "approved" or row.activation_allowed is not True:
            raise HTTPException(409, "Only an internally approved offer with activation enabled can be listed")
        if row.terms_verified is not True or row.seller_authorization_verified is not True:
            raise HTTPException(409, "Verified merchant terms and seller authorization are required")
        row.marketplace_listed = True
        db.add(AuditLog(
            workspace_id=workspace_id, actor=str(user.get("email") or "unknown"),
            action="merchant.offer.marketplace_listed", resource_type="merchant_offer", resource_id=row.id,
            outcome="listed",
            details_json={"marketplace_listing": True, "external_provider_write": False,
                          "affiliate_network_approval_status": "not_configured"},
        ))
        await db.commit()
        await db.refresh(row)
    return _merchant_offer_dict(row)


@api.post("/merchant/offers/{offer_id}/unlist")
async def unlist_merchant_offer_from_marketplace(
    offer_id: str,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before unlisting a merchant offer")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(MerchantOffer).where(
            MerchantOffer.id == offer_id,
            MerchantOffer.workspace_id == workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Merchant offer not found in the active workspace")
        row.marketplace_listed = False
        db.add(AuditLog(
            workspace_id=workspace_id, actor=str(user.get("email") or "unknown"),
            action="merchant.offer.marketplace_unlisted", resource_type="merchant_offer", resource_id=row.id,
            outcome="unlisted",
            details_json={"marketplace_listing": False, "external_provider_write": False},
        ))
        await db.commit()
        await db.refresh(row)
    return _merchant_offer_dict(row)


@api.get("/marketplace/offers")
async def list_published_marketplace_offers(
    limit: int = Query(default=100, ge=1, le=200),
    category: str | None = Query(default=None, max_length=160),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Read the explicitly listed, internally approved catalog across workspaces."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before browsing marketplace offers")
    workspace_id = str(workspace_id)
    with workspace_scope(None):
        query = select(MerchantOffer).where(
            MerchantOffer.marketplace_listed.is_(True),
            MerchantOffer.status == "approved",
            MerchantOffer.activation_allowed.is_(True),
            MerchantOffer.terms_verified.is_(True),
            MerchantOffer.seller_authorization_verified.is_(True),
            MerchantOffer.workspace_id != workspace_id,
        )
        if category:
            query = query.where(MerchantOffer.category == category.strip())
        rows = list((await db.scalars(query.order_by(MerchantOffer.created_at.desc()).limit(limit))).all())
    return {
        "count": len(rows),
        "data": [_marketplace_offer_public_dict(row) for row in rows],
        "note": "Only merchant-approved internal listings are shown. Listings do not imply external affiliate-network authorization or approval.",
    }


@api.post("/marketplace/offers/{offer_id}/applications", status_code=201)
async def create_marketplace_application(
    offer_id: str,
    payload: MarketplaceApplicationCreateRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    publisher_workspace_id = user.get("workspace_id")
    if not publisher_workspace_id:
        raise HTTPException(403, "Select an authorized publisher workspace before applying")
    publisher_workspace_id = str(publisher_workspace_id)
    with workspace_scope(None):
        offer = await db.scalar(select(MerchantOffer).where(
            MerchantOffer.id == offer_id,
            MerchantOffer.marketplace_listed.is_(True),
            MerchantOffer.status == "approved",
            MerchantOffer.activation_allowed.is_(True),
            MerchantOffer.terms_verified.is_(True),
            MerchantOffer.seller_authorization_verified.is_(True),
        ))
        if offer is None:
            raise HTTPException(404, "Marketplace offer is not listed or is no longer eligible")
        merchant_workspace_id = str(offer.workspace_id)
        if merchant_workspace_id == publisher_workspace_id:
            raise HTTPException(409, "A workspace cannot apply to its own merchant offer")
        # Enforce merchant terms server-side before persisting the publisher application.
        allowed_regions = {
            str(value).strip().upper()
            for value in (offer.allowed_regions_json or [])
            if str(value).strip()
        }
        if not allowed_regions:
            raise HTTPException(409, {
                "code": "OFFER_REGIONS_NOT_CONFIGURED",
                "message": "The merchant has not configured eligible regions; ask the merchant to update the offer before applying.",
            })
        disallowed_regions = sorted(set(payload.intended_regions) - allowed_regions)
        if disallowed_regions:
            raise HTTPException(422, {
                "code": "OFFER_REGION_RESTRICTION",
                "message": "Your intended regions include regions not allowed by the merchant.",
                "disallowed_regions": disallowed_regions,
                "allowed_regions": sorted(allowed_regions),
            })
        def normalize_traffic_source(value: str) -> str:
            return re.sub(r"[\s-]+", "_", str(value).strip().lower())
        restricted_sources = {
            normalize_traffic_source(value)
            for value in (offer.restricted_traffic_sources_json or [])
            if str(value).strip()
        }
        conflicting_sources = sorted({
            normalize_traffic_source(value)
            for value in payload.traffic_sources
            if normalize_traffic_source(value) in restricted_sources
        })
        if conflicting_sources:
            raise HTTPException(422, {
                "code": "OFFER_TRAFFIC_RESTRICTION",
                "message": "Your selected traffic sources conflict with merchant restrictions.",
                "restricted_selected_sources": conflicting_sources,
            })
        snapshot = {
            "id": offer.id,
            "name": offer.name,
            "category": offer.category,
            "commission_type": offer.commission_type,
            "commission_value": format(Decimal(offer.commission_value), "f"),
            "commission_currency": offer.commission_currency,
            "terms_version": offer.terms_version,
            "commission_terms_url": offer.commission_terms_url,
            "allowed_regions": list(offer.allowed_regions_json or []),
            "restricted_traffic_sources": list(offer.restricted_traffic_sources_json or []),
            "affiliate_disclosure": offer.affiliate_disclosure,
            "terms_verified": True,
            "seller_authorization_verified": True,
        }
    with workspace_scope(publisher_workspace_id):
        existing = await db.scalar(select(MarketplaceApplication).where(
            MarketplaceApplication.workspace_id == publisher_workspace_id,
            MarketplaceApplication.merchant_offer_id == offer_id,
        ))
        if existing is not None:
            raise HTTPException(409, "This publisher workspace already has an application record for the offer")
        row = MarketplaceApplication(
            workspace_id=publisher_workspace_id,
            merchant_workspace_id=merchant_workspace_id,
            merchant_offer_id=offer_id,
            applicant_email=str(user.get("email") or "unknown")[:320],
            publisher_website_url=payload.publisher_website_url,
            audience_description=payload.audience_description,
            traffic_sources_json=payload.traffic_sources,
            intended_regions_json=payload.intended_regions,
            promotion_plan=payload.promotion_plan,
            compliance_answers_json={
                "offer_terms_reviewed": payload.offer_terms_reviewed,
                "traffic_restrictions_reviewed": payload.traffic_restrictions_reviewed,
                "affiliate_disclosure_ready": payload.affiliate_disclosure_ready,
                "contact_sharing_consent": payload.contact_sharing_consent,
            },
            terms_snapshot_json=snapshot,
            status="pending_review",
        )
        db.add(row)
        await db.flush()
        db.add(AuditLog(
            workspace_id=publisher_workspace_id, actor=str(user.get("email") or "unknown"),
            action="marketplace.application.created", resource_type="marketplace_application",
            resource_id=row.id, outcome="pending_review",
            details_json={"merchant_offer_id": offer_id, "merchant_workspace_id": merchant_workspace_id,
                          "terms_version": snapshot["terms_version"], "provider_submission_performed": False,
                          "contact_sharing_consent": True},
        ))
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(409, "This publisher workspace already has an application record for the offer") from exc
        await db.refresh(row)
    return _marketplace_application_dict(row)


@api.get("/marketplace/applications")
async def list_publisher_marketplace_applications(
    limit: int = Query(default=100, ge=1, le=300),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized publisher workspace before listing applications")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        rows = list((await db.scalars(
            select(MarketplaceApplication)
            .where(MarketplaceApplication.workspace_id == workspace_id)
            .order_by(MarketplaceApplication.created_at.desc())
            .limit(limit)
        )).all())
    return {"count": len(rows), "data": [_marketplace_application_dict(row) for row in rows]}


@api.get("/merchant/applications")
async def list_merchant_incoming_applications(
    response: Response,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
    status: str | None = Query(default=None, max_length=40),
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    merchant_workspace_id = user.get("workspace_id")
    if not merchant_workspace_id:
        raise HTTPException(403, "Select an authorized merchant workspace before listing applications")
    merchant_workspace_id = str(merchant_workspace_id)
    valid_statuses = {"pending_review", "approved", "rejected"}
    if status is not None and status not in valid_statuses:
        raise HTTPException(422, "Unsupported marketplace application status")
    # Incoming applications intentionally cross publisher workspaces but can only
    # reference merchant offers belonging to the selected, authorized merchant.
    with workspace_scope(None):
        query = select(MarketplaceApplication).where(
            MarketplaceApplication.merchant_workspace_id == merchant_workspace_id
        )
        if status is not None:
            query = query.where(MarketplaceApplication.status == status)
        total_count = int(
            await db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
        )
        rows = list((await db.scalars(
            query.order_by(MarketplaceApplication.created_at.desc(), MarketplaceApplication.id.desc())
            .limit(limit)
            .offset(offset)
        )).all())
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Cookie"
    return {
        "count": len(rows),
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "status_filter": status or "all",
        "data": [_marketplace_application_dict(row) for row in rows],
    }


@api.post("/merchant/applications/{application_id}/review")
async def review_incoming_marketplace_application(
    application_id: str,
    payload: MarketplaceApplicationReviewRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    merchant_workspace_id = user.get("workspace_id")
    if not merchant_workspace_id:
        raise HTTPException(403, "Select an authorized merchant workspace before reviewing applications")
    merchant_workspace_id = str(merchant_workspace_id)
    reviewer = str(user.get("email") or "unknown")[:320]
    with workspace_scope(None):
        row = await db.scalar(select(MarketplaceApplication).where(
            MarketplaceApplication.id == application_id,
            MarketplaceApplication.merchant_workspace_id == merchant_workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Marketplace application not found for a merchant offer owned by this workspace")
        if row.status != "pending_review":
            raise HTTPException(409, "Only pending marketplace applications can be reviewed")
        publisher_workspace_id = str(row.workspace_id)
        with workspace_scope(publisher_workspace_id):
            row.status = "approved" if payload.decision == "approve" else "rejected"
            row.reviewer_notes = payload.reviewer_notes
            row.reviewed_by = reviewer
            row.reviewed_at = datetime.now(timezone.utc)
            db.add(AuditLog(
                workspace_id=publisher_workspace_id, actor=reviewer,
                action="marketplace.application.reviewed", resource_type="marketplace_application",
                resource_id=row.id, outcome=row.status,
                details_json={
                    "decision": payload.decision,
                    "merchant_workspace_id": merchant_workspace_id,
                    "merchant_offer_id": row.merchant_offer_id,
                    "external_affiliate_network_approval": False,
                    "provider_submission_performed": False,
                },
            ))
            await db.commit()
            await db.refresh(row)
    return _marketplace_application_dict(row)

def _program_application_readiness(evidence_urls: list[str], compliance_answers: dict[str, bool]) -> dict[str, Any]:
    required = {
        "affiliate_disclosure_ready": "affiliate_disclosure_not_confirmed",
        "program_traffic_terms_reviewed": "program_traffic_terms_not_reviewed",
        "geography_restrictions_reviewed": "geography_restrictions_not_reviewed",
        "privacy_and_consent_controls_ready": "privacy_and_consent_controls_not_confirmed",
        "claims_substantiation_process_ready": "claims_substantiation_process_not_confirmed",
    }
    blockers = [reason for key, reason in required.items() if compliance_answers.get(key) is not True]
    if not evidence_urls:
        blockers.append("official_program_terms_evidence_required")
    return {
        "ready_for_human_review": not blockers,
        "blockers": blockers,
        "evidence_count": len(evidence_urls),
        "provider_verified": False,
        "provider_submission_status": "not_configured",
    }


def _program_application_dict(row: AffiliateProgramApplication) -> dict[str, Any]:
    return {
        "id": row.id, "provider": row.provider, "program_name": row.program_name,
        "program_url": row.program_url, "publisher_website_url": row.publisher_website_url,
        "audience_description": row.audience_description, "monthly_visitors": row.monthly_visitors,
        "traffic_sources": row.traffic_sources_json or [],
        "promotion_channels": row.promotion_channels_json or [],
        "primary_regions": row.primary_regions_json or [], "promotion_plan": row.promotion_plan,
        "evidence_urls": row.evidence_urls_json or [], "compliance_answers": row.compliance_answers_json or {},
        "readiness": row.readiness_json or {}, "status": row.status, "reviewer_notes": row.reviewer_notes,
        "reviewed_by": row.reviewed_by, "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "provider_submission_status": row.provider_submission_status,
        "provider_application_id": row.provider_application_id, "provider_approved": False,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@api.post("/research/program-applications", status_code=201)
async def create_program_application(payload: ProgramApplicationCreateRequest, user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    """Create a workspace-owned application packet; no provider submission is performed."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating a program application")
    workspace_id = str(workspace_id)
    compliance = payload.compliance_answers.model_dump()
    readiness = _program_application_readiness(payload.evidence_urls, compliance)
    status = "review_required" if readiness["ready_for_human_review"] else "draft"
    with workspace_scope(workspace_id):
        row = AffiliateProgramApplication(
            workspace_id=workspace_id, provider=payload.provider, program_name=payload.program_name,
            program_url=payload.program_url, publisher_website_url=payload.publisher_website_url,
            audience_description=payload.audience_description, monthly_visitors=payload.monthly_visitors,
            traffic_sources_json=payload.traffic_sources, promotion_channels_json=payload.promotion_channels,
            primary_regions_json=payload.primary_regions, promotion_plan=payload.promotion_plan,
            evidence_urls_json=payload.evidence_urls, compliance_answers_json=compliance,
            readiness_json=readiness, status=status, provider_submission_status="not_configured",
        )
        db.add(row)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id, actor=str(user.get("email") or "unknown"),
            action="research.program_application.created", resource_type="affiliate_program_application",
            resource_id=row.id, outcome=status,
            details_json={"provider": row.provider, "program_name": row.program_name,
                "ready_for_human_review": readiness["ready_for_human_review"], "blockers": readiness["blockers"],
                "provider_submission_status": "not_configured", "provider_submission_performed": False},
        ))
        await db.commit()
        await db.refresh(row)
    result = _program_application_dict(row)
    result.update({"provider_submission_performed": False, "manual_handoff_only": True})
    return result


@api.get("/research/program-applications")
async def list_program_applications(limit: int = Query(default=100, ge=1, le=300), status: str | None = Query(default=None, max_length=40), user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before listing program applications")
    workspace_id = str(workspace_id)
    allowed = {"draft", "review_required", "approved_for_manual_handoff", "rejected"}
    if status is not None and status not in allowed:
        raise HTTPException(422, "Unsupported application status filter")
    with workspace_scope(workspace_id):
        query = select(AffiliateProgramApplication).where(AffiliateProgramApplication.workspace_id == workspace_id)
        if status is not None:
            query = query.where(AffiliateProgramApplication.status == status)
        rows = list((await db.scalars(query.order_by(AffiliateProgramApplication.created_at.desc()).limit(limit))).all())
    return {"count": len(rows), "data": [_program_application_dict(row) for row in rows]}


@api.post("/research/program-applications/{application_id}/review")
async def review_program_application(application_id: str, payload: ProgramApplicationReviewRequest, user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    """Internal human review only; this never submits to or claims approval by a network."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing a program application")
    if user.get("workspace_role") not in {"owner", "admin"} and user.get("is_admin") is not True:
        raise HTTPException(403, "Workspace owner/admin review permission is required")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(AffiliateProgramApplication).where(
            AffiliateProgramApplication.id == application_id,
            AffiliateProgramApplication.workspace_id == workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Program application not found in the active workspace")
        if row.status == "rejected":
            raise HTTPException(409, "A rejected application packet cannot be approved; create a new packet")
        if payload.decision == "approve_for_manual_handoff":
            if not (row.readiness_json or {}).get("ready_for_human_review"):
                raise HTTPException(409, "Complete compliance checks and add official program terms evidence before approval")
            row.status = "approved_for_manual_handoff"
        else:
            row.status = "rejected"
        row.reviewer_notes = payload.reviewer_notes
        row.reviewed_by = str(user.get("email") or "unknown")
        row.reviewed_at = datetime.now(timezone.utc)
        db.add(AuditLog(
            workspace_id=workspace_id, actor=row.reviewed_by, action="research.program_application.reviewed",
            resource_type="affiliate_program_application", resource_id=row.id, outcome=row.status,
            details_json={"decision": payload.decision, "readiness_passed": bool((row.readiness_json or {}).get("ready_for_human_review")),
                "provider_submission_status": row.provider_submission_status, "provider_submission_performed": False, "provider_approved": False},
        ))
        await db.commit()
        await db.refresh(row)
    result = _program_application_dict(row)
    result.update({"provider_submission_performed": False, "manual_handoff_only": True})
    return result


@api.post("/research/traffic-analyzer", status_code=201)
async def research_traffic_analyzer(
    payload: TrafficAnalysisRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Score and compare operator-supplied traffic metrics without claiming a live provider lookup."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before analyzing traffic")
    try:
        generated = analyze_traffic_domains_service(
            domains=[domain.model_dump(mode="python") for domain in payload.domains],
            focus=payload.focus,
            compare=payload.compare,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    with workspace_scope(str(workspace_id)):
        asset = ContentAsset(
            workspace_id=str(workspace_id),
            asset_type="traffic_analysis_draft",
            title=f"Traffic analysis — {len(payload.domains)} supplied domain(s)",
            body=json.dumps(generated, ensure_ascii=False, sort_keys=True),
            status="draft",
            source_urls=[],
            metadata_json={
                "traffic_analyzer_version": "1",
                "focus": payload.focus,
                "domains_analyzed": len(generated["domains_analyzed"]),
                "provider_connected": False,
                "external_search_performed": False,
                "requires_review": True,
                "publishing_started": False,
            },
        )
        db.add(asset)
        await db.commit()
    return {**generated, "asset_id": asset.id}



@api.post("/research/commission-calculator", status_code=201)
async def create_commission_projection(
    payload: CommissionCalculatorRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Persist a review-only commission projection from explicit assumptions; no provider action."""
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before estimating commissions")
    await workspace_generation_rate_limit(request, workspace_id)
    try:
        assumptions = payload.model_dump(mode="json", exclude_none=True)
        generated = execute_skill_handler("research.commission_calculator", assumptions)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        asset = ContentAsset(
            workspace_id=workspace_id,
            asset_type="commission_projection",
            title=f"Commission projection — {len(payload.programs)} program(s) — {generated['currency_comparison']}",
            body=json.dumps(generated, ensure_ascii=False, sort_keys=True),
            status="draft",
            source_urls=[],
            metadata_json={
                "schema_version": 1,
                "assumptions": assumptions,
                "program_count": len(payload.programs),
                "currency_comparison": generated["currency_comparison"],
                "provider_metrics_verified": False,
                "earnings_guaranteed": False,
                "external_provider_calls_made": False,
                "money_transferred": False,
                "requires_human_review": True,
                "publishing_started": False,
            },
        )
        db.add(asset)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="research.commission_projection.created",
            resource_type="content_asset",
            resource_id=asset.id,
            outcome="draft",
            details_json={
                "program_count": len(payload.programs),
                "currency": generated["currency_comparison"],
                "input_provenance": "caller_supplied_assumptions",
                "provider_metrics_verified": False,
                "external_provider_calls_made": False,
                "money_transferred": False,
                "publishing_started": False,
            },
        ))
        await db.commit()
        await db.refresh(asset)

    return {
        **generated,
        "asset_id": asset.id,
        "asset_status": asset.status,
        "requires_review": True,
        "publishing_started": False,
    }



@api.get("/research/commission-projections")
async def list_commission_projections(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=10000),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Return only the active workspace's saved, review-required commission projection drafts."""
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing commission projections")

    with workspace_scope(workspace_id):
        base_query = select(ContentAsset).where(
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "commission_projection",
        )
        total = await db.scalar(select(func.count()).select_from(base_query.subquery()))
        rows = (await db.scalars(
            base_query.order_by(ContentAsset.created_at.desc(), ContentAsset.id.desc())
            .limit(limit)
            .offset(offset)
        )).all()

    items = []
    for asset in rows:
        try:
            calculated = json.loads(asset.body)
        except (json.JSONDecodeError, TypeError):
            # A malformed historical record is not silently presented as a valid result.
            calculated = None
        if not isinstance(calculated, dict):
            calculated = None
        items.append({
            "asset_id": asset.id,
            "title": asset.title,
            "asset_status": asset.status,
            "created_at": asset.created_at.isoformat() if asset.created_at else None,
            "requires_review": True,
            "publishing_started": False,
            "assumptions": (asset.metadata_json or {}).get("assumptions", {}),
            "result": ({
                **calculated,
                "asset_id": asset.id,
                "asset_status": asset.status,
                "requires_review": True,
                "publishing_started": False,
            } if calculated is not None else None),
        })
    return {"count": int(total or 0), "limit": limit, "offset": offset, "items": items}


@api.post("/research/content-moat", status_code=201)
async def research_content_moat(
    payload: ContentMoatRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Calculate a content investment benchmark using operator-supplied competitor counts."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before calculating a content moat")
    try:
        generated = analyze_content_moat_service(
            niche=payload.niche,
            hub_keyword=payload.hub_keyword,
            your_current_pages=payload.your_current_pages,
            publishing_capacity=payload.publishing_capacity,
            competitors=[item.model_dump(mode="python") for item in payload.competitors],
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    with workspace_scope(str(workspace_id)):
        asset = ContentAsset(
            workspace_id=str(workspace_id),
            asset_type="content_moat_report",
            title=f"Content moat report — {generated['niche'][:180]}",
            body=json.dumps(generated, ensure_ascii=False, sort_keys=True),
            status="draft",
            source_urls=[],
            metadata_json={
                "content_moat_calculator_version": "1",
                "competitors_analyzed": generated["competitors_analyzed"],
                "competitor_data_verified": False,
                "search_volume_validated": False,
                "publishing_started": False,
                "requires_review": True,
            },
        )
        db.add(asset)
        await db.commit()
    return {**generated, "asset_id": asset.id}


@api.post("/research/content-decay", status_code=201)
async def research_content_decay(
    payload: ContentDecayRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Create and persist a review-only refresh queue from operator-supplied observations."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing content decay")
    try:
        generated = build_content_decay_report_service(
            site_url=payload.site_url,
            timeframe=payload.timeframe,
            pages=[page.model_dump(mode="python") for page in payload.pages],
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    with workspace_scope(str(workspace_id)):
        asset = ContentAsset(
            workspace_id=str(workspace_id),
            asset_type="content_decay_report",
            title=f"Content decay review — {generated['site'][:180]}",
            body=json.dumps(generated, ensure_ascii=False, sort_keys=True),
            status="draft",
            source_urls=[page.url for page in payload.pages],
            metadata_json={
                "content_decay_detector_version": "1",
                "timeframe": payload.timeframe,
                "pages_analyzed": generated["pages_analyzed"],
                "pages_decaying": generated["pages_decaying"],
                "search_console_connected": False,
                "competitor_data_checked": False,
                "requires_review": True,
                "publishing_started": False,
            },
        )
        db.add(asset)
        await db.commit()
    return {**generated, "asset_id": asset.id}


@api.post("/research/category-design", status_code=201)
async def research_category_design(
    payload: CategoryDesignRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Save a read-only taxonomy proposal from supplied topic candidates."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before designing categories")
    try:
        generated = design_category_taxonomy_service(
            niche=payload.niche,
            target_audience=payload.target_audience,
            topic_candidates=payload.topic_candidates,
            existing_categories=payload.existing_categories,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    with workspace_scope(str(workspace_id)):
        asset = ContentAsset(
            workspace_id=str(workspace_id),
            asset_type="category_taxonomy_draft",
            title=f"{generated['root_category']} category taxonomy draft",
            body=json.dumps(generated, ensure_ascii=False, sort_keys=True),
            status="draft",
            source_urls=[],
            metadata_json={
                "category_design_version": "1",
                "category_count": generated["category_count"],
                "search_volume_validated": False,
                "taxonomy_evaluated": False,
                "requires_review": True,
            },
        )
        db.add(asset)
        await db.commit()
    return {**generated, "asset_id": asset.id}


@api.post("/research/purple-cow-audit")
async def research_purple_cow_audit(payload: PurpleCowAuditRequest, user: dict[str, Any] = Depends(require_auth)):
    """Review a proposed position against operator-supplied alternatives only."""
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before running a differentiation audit")
    try:
        return audit_purple_cow_positioning_service(
            offer_name=payload.offer_name,
            target_audience=payload.target_audience,
            positioning_statement=payload.positioning_statement,
            alternatives=[item.model_dump() for item in payload.alternatives],
            evidence_notes=payload.evidence_notes,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@api.post("/research/seo-audit")
async def research_seo_audit(
    payload: SEOAuditRequest,
    user: dict[str, Any] = Depends(require_auth),
):
    """Audit one public page without crawling, publishing or asserting ranking outcomes."""
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before running an SEO audit")
    try:
        return await audit_public_page_service(payload.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.warning("Public page SEO audit failed (%s)", type(exc).__name__)
        raise HTTPException(502, "The public page could not be safely fetched or analyzed") from exc


@api.post("/research/internal-links")
async def research_internal_links(
    payload: InternalLinkingRequest,
    user: dict[str, Any] = Depends(require_auth),
):
    """Suggest internal links across user-supplied pages without crawling or mutating the site."""
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before analyzing internal links")
    try:
        return await recommend_internal_links_service(
            urls=payload.urls,
            max_suggestions_per_page=payload.max_suggestions_per_page,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.warning("Internal link analysis failed (%s)", type(exc).__name__)
        raise HTTPException(502, "The supplied public pages could not be safely analyzed") from exc


@api.post("/research/niches")
async def research_niches(p:NicheFinderRequest):return {"results":monopoly_niche_finder(p.candidates,top_n=p.top_n)}
@api.post("/research/competitors")
async def research_competitors(
    payload: CompetitorRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before fetching competitor pages")
    _validate_generation_payload_size(payload)
    await workspace_generation_rate_limit(request, str(workspace_id))
    with workspace_scope(str(workspace_id)):
        return {"results": await competitor_spy(payload.urls)}
@api.post("/research/trends")
async def research_trends(p:TrendRequest):return await trending_content_scout(p.query,limit=p.limit)
@api.post("/content/social")
async def social_content(
    payload: SocialPostRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before generating social content")
    _validate_generation_payload_size(payload)
    await workspace_generation_rate_limit(request, str(workspace_id))
    with workspace_scope(str(workspace_id)):
        return await viral_post_writer(payload.topic, payload.hooks, payload.platform)


@api.post("/content/tiktok-script")
async def tiktok_content(
    payload: SocialPostRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before generating a video script")
    _validate_generation_payload_size(payload)
    await workspace_generation_rate_limit(request, str(workspace_id))
    with workspace_scope(str(workspace_id)):
        return await tiktok_script_writer(payload.topic, payload.hooks)


@api.post("/content/keywords")
async def keywords(
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before clustering keywords")
    items = payload.get("keywords")
    if (
        not isinstance(items, list)
        or len(items) < 50
        or len(items) > 500
        or any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in items)
    ):
        raise HTTPException(422, "keywords must contain 50-500 non-empty strings of at most 500 characters")
    _validate_generation_payload_size(payload, limit_bytes=256 * 1024)
    await workspace_generation_rate_limit(request, str(workspace_id))
    with workspace_scope(str(workspace_id)):
        return keyword_cluster_architect(items)

@api.post("/content/angles/rank")
async def content_angle_rank(
    payload: ContentAngleRankRequest,
    user: dict[str, Any] = Depends(require_auth),
):
    """Rank draft angles; never treats the score as a conversion or revenue forecast."""
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before ranking content angles")
    try:
        return rank_content_angles_service(
            topic=payload.topic,
            audience=payload.audience,
            candidates=[item.model_dump() for item in payload.candidates],
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@api.post("/content/infographic", status_code=201)
async def create_infographic(
    payload: InfographicRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Persist a deterministic, review-only SVG infographic in the active workspace."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating an infographic")
    try:
        generated = build_infographic_service(
            title=payload.title,
            subtitle=payload.subtitle,
            audience=payload.audience,
            key_points=payload.key_points,
            source_urls=payload.source_urls,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    with workspace_scope(str(workspace_id)):
        asset = ContentAsset(
            workspace_id=str(workspace_id),
            asset_type="infographic_svg",
            title=generated["title"],
            body=generated["svg"],
            status="draft",
            source_urls=generated["source_urls"],
            metadata_json={
                "infographic_generator_version": "1",
                "width": generated["width"],
                "height": generated["height"],
                "format": generated["format"],
                "card_count": len(generated["cards"]),
                "requires_review": True,
                "external_image_provider_used": False,
            },
        )
        db.add(asset)
        await db.commit()
    return {**generated, "asset_id": asset.id}


@api.post("/content/atomize")
async def atomize_content_route(
    payload: ContentAtomizeRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Create reviewable platform-native drafts from one source asset."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before atomizing content")

    from backend.services.content_atomizer import atomize_content

    try:
        generated = await atomize_content(
            source_title=payload.source_title,
            source_body=payload.source_body,
            platforms=payload.platforms,
            source_urls=payload.source_urls,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    assets = []
    with workspace_scope(str(workspace_id)):
        for atom in generated["atoms"]:
            asset = ContentAsset(
                workspace_id=str(workspace_id),
                asset_type=f"repurposed_{atom['platform']}",
                title=atom["title"],
                body=atom["content"],
                status="draft",
                source_urls=payload.source_urls,
                metadata_json={
                    "content_atomizer_version": "1",
                    "source_title": payload.source_title,
                    "platform": atom["platform"],
                    "hook": atom["hook"],
                    "cta": atom["cta"],
                    "affiliate_disclosure": atom["affiliate_disclosure"],
                    "source_facts": atom["source_facts"],
                    "claims_to_verify": atom["claims_to_verify"],
                    "provider": generated["provider"],
                    "requires_review": True,
                },
            )
            db.add(asset)
            assets.append(asset)
        await db.commit()

    return {
        "source_title": payload.source_title,
        "asset_count": len(assets),
        "asset_ids": [asset.id for asset in assets],
        "atoms": generated["atoms"],
        "source_urls": payload.source_urls,
        "provider": generated["provider"],
        "rag_sources": generated.get("rag_sources", []),
        "requires_review": True,
        "publishing_started": False,
    }


@api.post("/content/research-brief", status_code=201)
async def create_content_research_brief(
    payload: ContentResearchBriefRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before generating a research brief")
    _validate_generation_payload_size(payload)
    await workspace_generation_rate_limit(request, workspace_id)
    try:
        result = await content_research_brief_service(payload.topic, payload.urls)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, {
            "code": "RESEARCH_SOURCES_UNAVAILABLE",
            "message": str(exc),
            "provider_calls_made": 0,
        }) from exc

    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    source_snapshots = []
    for source in result.get("sources", []):
        if not isinstance(source, dict):
            continue
        source_snapshots.append({
            "source_id": str(source.get("source_id") or "")[:20],
            "url": str(source.get("url") or "")[:2048],
            "title": str(source.get("title") or "")[:300],
            "status": str(source.get("status") or "unknown")[:40],
            "http_status": source.get("http_status"),
            "content_type": str(source.get("content_type") or "")[:120],
            "fetched_at": source.get("fetched_at"),
            "excerpt_sha256": source.get("excerpt_sha256"),
            "excerpt": str(source.get("excerpt") or "")[:4000],
            "statistics_seen_in_source": list(source.get("statistics_seen_in_source") or [])[:25],
            "error_type": source.get("error_type"),
            "detail": source.get("detail"),
        })
    claim_summary = dict(result.get("claim_ledger_summary") or {})
    metadata = {
        "schema_version": 1,
        "topic": result["topic"],
        "provider": result.get("provider", "unknown"),
        "rag_sources": result.get("rag_sources", []),
        "source_snapshots": source_snapshots,
        "source_count": len(result.get("source_urls") or []),
        "observed_statistics": result.get("observed_statistics", [])[:250],
        "claim_ledger": result.get("claim_ledger", [])[:80],
        "claim_ledger_summary": claim_summary,
        "claim_ledger_parse_status": result.get("claim_ledger_parse_status", "unknown"),
        "requires_review": True,
        "source_currentness_verified": False,
        "claim_truth_independently_verified": False,
        "legal_approval_granted": False,
        "publishing_started": False,
        "created_by": actor,
    }
    with workspace_scope(workspace_id):
        asset = ContentAsset(
            workspace_id=workspace_id,
            asset_type="content_research_brief",
            title=str(result["topic"])[:500],
            body=str(result.get("brief") or ""),
            status="draft",
            source_urls=list(result.get("source_urls") or []),
            metadata_json=metadata,
        )
        db.add(asset)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="content_research_brief.created",
            resource_type="content_asset",
            resource_id=asset.id,
            outcome="draft",
            details_json={
                "source_count": metadata["source_count"],
                "claim_count": claim_summary.get("claim_count", 0),
                "quote_match_count": claim_summary.get("quote_match_count", 0),
                "unmatched_claim_count": claim_summary.get("unmatched_claim_count", 0),
                "claim_ledger_parse_status": metadata["claim_ledger_parse_status"],
                "source_currentness_verified": False,
                "claim_truth_independently_verified": False,
                "publishing_started": False,
            },
        ))
        await db.commit()
        await db.refresh(asset)
    result["asset_id"] = asset.id
    result["asset_status"] = asset.status
    result["execution_boundary"] = (
        "Workspace-owned draft only. Quote matching verifies exact text presence in the fetched snapshot, "
        "not factual truth, currentness, legal approval or publication readiness."
    )
    return result


@api.post("/content/blog")
async def blog(
    payload: BlogRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before generating blog content")
    owner_workspace_id = str(workspace_id)
    with workspace_scope(owner_workspace_id):
        result = await affiliate_blog_builder(
            payload.topic,
            product=payload.product,
            canonical_url=payload.canonical_url,
            minimum_words=payload.minimum_words,
        )
        asset = ContentAsset(
            workspace_id=owner_workspace_id,
            asset_type="affiliate_blog",
            title=result["title"],
            body=result["html"],
            status="draft",
            source_urls=result["rag_sources"],
            metadata_json={
                "word_count": result["word_count"],
                "schema_types": result["schema_types"],
                "provider": result["provider"],
            },
        )
        db.add(asset)
        await db.commit()
        result["asset_id"] = asset.id
        return result
@api.post("/content/comparison-post", status_code=201)
async def create_comparison_post(
    payload: ComparisonPostRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Create an immutable workspace comparison draft or a new revision of a saved draft."""
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before generating a comparison article")
    _validate_generation_payload_size(payload)
    await workspace_generation_rate_limit(request, workspace_id)

    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    revision_parent: ContentAsset | None = None
    revision_parent_id: str | None = None
    revision_number = 1
    revision_root_asset_id: str | None = None
    if payload.revision_of_asset_id:
        with workspace_scope(workspace_id):
            revision_parent = await db.scalar(select(ContentAsset).where(
                ContentAsset.id == payload.revision_of_asset_id,
                ContentAsset.workspace_id == workspace_id,
                ContentAsset.asset_type == "comparison_post",
            ).with_for_update())
        if revision_parent is None:
            raise HTTPException(404, "Revision source was not found in this workspace")
        if revision_parent.status != "draft":
            raise HTTPException(409, "Only a saved draft can be revised; the original asset was not changed")
        revision_parent_id = revision_parent.id
        parent_metadata = revision_parent.metadata_json if isinstance(revision_parent.metadata_json, dict) else {}
        revision_root_asset_id = str(parent_metadata.get("revision_root_asset_id") or revision_parent.id)
        # Release the parent read lock before the atomic sequence allocation. The
        # sequence row, rather than this content row, serializes concurrent revisions.
        await db.commit()
        try:
            revision_number = await reserve_comparison_revision_number(
                db,
                workspace_id=workspace_id,
                root_asset_id=revision_root_asset_id,
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        with workspace_scope(workspace_id):
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=actor,
                action="content_comparison_post.revision_reserved",
                resource_type="content_asset",
                resource_id=revision_root_asset_id,
                outcome="reserved",
                details_json={
                    "revision_number": revision_number,
                    "revision_of_asset_id": revision_parent_id,
                    "revision_root_asset_id": revision_root_asset_id,
                    "generation_completed": False,
                },
            ))
            # Commit the reservation before model/network I/O. Failed generations
            # leave an auditable gap rather than reusing a revision number.
            await db.commit()

    try:
        result = await comparison_post_writer_service(
            topic=payload.topic,
            audience=payload.audience,
            products=[product.model_dump() for product in payload.products],
            decision_criteria=payload.decision_criteria,
            affiliate_disclosure=payload.affiliate_disclosure,
            minimum_words=payload.minimum_words,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.exception("Comparison article generation failed")
        raise HTTPException(
            502,
            {"code": "COMPARISON_DRAFT_GENERATION_FAILED", "message": "Comparison draft generation failed; no draft was saved."},
        ) from exc

    html_body = str(result.get("html") or "")
    persisted_content_sha256 = sha256_text(html_body)
    raw_snapshots = result.get("source_snapshots")
    source_snapshots = raw_snapshots[:10] if isinstance(raw_snapshots, list) else []
    source_snapshot_manifest = build_source_snapshot_manifest(source_snapshots)
    snapshot_manifest_sha256 = source_snapshot_manifest_sha256(source_snapshot_manifest)

    asset_metadata = {
        "schema_version": 1,
        "content_sha256": persisted_content_sha256,
        "source_snapshot_manifest": source_snapshot_manifest,
        "source_snapshot_manifest_sha256": snapshot_manifest_sha256,
        "asset_title": str(result["title"])[:500],
        "source_urls": result["source_urls"] if isinstance(result.get("source_urls"), list) else [],
        "topic": payload.topic,
        "audience": payload.audience,
        "affiliate_disclosure": payload.affiliate_disclosure,
        "revision_number": revision_number,
        "revision_of_asset_id": revision_parent_id,
        "revision_root_asset_id": revision_root_asset_id,
        "products": result["products"],
        "decision_criteria": result["decision_criteria"],
        "comparison_table": result["comparison_table"],
        "unknown_fact_count": result["unknown_fact_count"],
        "word_count": result["word_count"],
        "minimum_word_target": result["minimum_word_target"],
        "minimum_word_target_met": result["minimum_word_target_met"],
        "evidence_status": result.get("evidence_status", "operator_supplied_unverified"),
        "product_facts_independently_verified": False,
        "external_product_sources_fetched": bool(result.get("external_product_sources_fetched", False)),
        "source_snapshots": source_snapshots,
        "fact_evidence": result.get("fact_evidence", [])[:60],
        "evidence_summary": result.get("evidence_summary", {}),
        "review_status": "pending_review",
        "review_history": [],
        "reviewed_at": None,
        "reviewed_by": None,
        "reviewer_role": None,
        "reviewer_notes": None,
        "reviewed_content_sha256": None,
        "requires_review": True,
        "publishing_started": False,
        "model_provider": result["provider"],
    }
    with workspace_scope(workspace_id):
        asset = ContentAsset(
            workspace_id=workspace_id,
            asset_type="comparison_post",
            title=str(result["title"])[:500],
            body=html_body,
            status="draft",
            source_urls=result["source_urls"],
            metadata_json=asset_metadata,
        )
        db.add(asset)
        await db.flush()
        root_id = revision_root_asset_id or asset.id
        if asset_metadata["revision_root_asset_id"] is None:
            # Assign a new dict rather than mutating the same JSON object already
            # attached to the ORM instance; SQLAlchemy then persists the root ID.
            asset.metadata_json = {**asset_metadata, "revision_root_asset_id": root_id}
        persisted_metadata = dict(asset.metadata_json) if isinstance(asset.metadata_json, dict) else dict(asset_metadata)
        evidence_payload_digest = comparison_evidence_payload_sha256(persisted_metadata)
        asset.metadata_json = {**persisted_metadata, "evidence_payload_sha256": evidence_payload_digest}
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="content_comparison_post.revised" if revision_parent_id else "content_comparison_post.created",
            resource_type="content_asset",
            resource_id=asset.id,
            outcome="draft",
            details_json={
                "product_count": result["product_count"],
                "decision_criteria_count": len(result["decision_criteria"]),
                "unknown_fact_count": result["unknown_fact_count"],
                "evidence_status": result.get("evidence_status", "operator_supplied_unverified"),
                "source_snapshots_fetched": (result.get("evidence_summary") or {}).get("source_snapshots_fetched", 0),
                "exact_text_match_count": (result.get("evidence_summary") or {}).get("exact_text_match_count", 0),
                "exact_text_not_found_count": (result.get("evidence_summary") or {}).get("exact_text_not_found_count", 0),
                "content_sha256": persisted_content_sha256,
                "source_snapshot_manifest_sha256": snapshot_manifest_sha256,
                "evidence_payload_sha256": evidence_payload_digest,
                "revision_number": revision_number,
                "revision_of_asset_id": revision_parent_id,
                "revision_root_asset_id": root_id,
                "product_facts_independently_verified": False,
                "publishing_started": False,
            },
        ))
        await db.commit()
        await db.refresh(asset)
    result["asset_id"] = asset.id
    result["asset_status"] = asset.status
    result["source_freshness"] = evaluate_source_freshness(result.get("source_snapshots"), result.get("source_urls") or [])
    result["can_approve"] = str(user.get("workspace_role") or "").lower() in {"owner", "admin"} and bool(result["source_freshness"]["approval_allowed"])
    result["topic"] = payload.topic
    result["audience"] = payload.audience
    result["affiliate_disclosure"] = payload.affiliate_disclosure
    result["revision_number"] = revision_number
    result["revision_of_asset_id"] = revision_parent_id
    result["revision_root_asset_id"] = root_id
    result["content_sha256"] = persisted_content_sha256
    result["content_integrity_status"] = "verified"
    result["source_snapshot_integrity_status"] = "verified"
    result["evidence_payload_sha256"] = evidence_payload_digest
    result["evidence_payload_integrity_status"] = "verified"
    result["integrity_review_blocked"] = False
    result["review_block_reason"] = None
    result["review_status"] = "pending_review"
    result["review_history"] = []
    result["reviewed_by"] = None
    result["reviewed_at"] = None
    result["reviewer_role"] = None
    result["reviewer_notes"] = None
    result["requires_review"] = True
    result["can_review"] = str(user.get("workspace_role") or "").lower() in {"owner", "admin"}
    result["execution_boundary"] = (
        "Workspace-owned review draft. Revisions create a new asset and preserve the prior draft. Public sources are fetched "
        "through the pinned transport into bounded snapshots. Exact text matches establish text presence only, not factual truth, "
        "currentness, eligibility, compliance approval or publication readiness."
    )
    return result


@api.get("/content/comparison-posts")
async def list_comparison_posts(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """List only the active workspace's saved comparison drafts."""
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace to view comparison drafts")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Cookie"
    with workspace_scope(workspace_id):
        predicate = (
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "comparison_post",
        )
        total = int(await db.scalar(select(func.count(ContentAsset.id)).where(*predicate)) or 0)
        rows = list((await db.scalars(
            select(ContentAsset)
            .where(*predicate)
            .order_by(ContentAsset.created_at.desc(), ContentAsset.id.desc())
            .offset(offset)
            .limit(limit)
        )).all())
    items = []
    for row in rows:
        metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        products = metadata.get("products") if isinstance(metadata.get("products"), list) else []
        evidence_summary = metadata.get("evidence_summary") if isinstance(metadata.get("evidence_summary"), dict) else {}
        items.append({
            "asset_id": row.id,
            "title": row.title,
            "asset_status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "revision_number": metadata.get("revision_number", 1),
            "revision_of_asset_id": metadata.get("revision_of_asset_id"),
            "revision_root_asset_id": metadata.get("revision_root_asset_id") or row.id,
            "word_count": metadata.get("word_count", 0),
            "product_count": len(products),
            "unknown_fact_count": metadata.get("unknown_fact_count", 0),
            "evidence_status": metadata.get("evidence_status", "unknown"),
            "source_snapshots_fetched": evidence_summary.get("source_snapshots_fetched", 0),
            "review_status": str(metadata.get("review_status") or "pending_review"),
            "reviewed_at": metadata.get("reviewed_at"),
            "reviewed_by": metadata.get("reviewed_by"),
            "can_review": str(user.get("workspace_role") or "").lower() in {"owner", "admin"},
            "requires_review": bool(metadata.get("requires_review", True)),
            "publishing_started": False,
        })
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@api.get("/content/comparison-posts/{asset_id}")
async def get_comparison_post(
    asset_id: str,
    response: Response,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Return a saved comparison only when it belongs to the active workspace."""
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace to open comparison drafts")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Cookie"
    with workspace_scope(workspace_id):
        row = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "comparison_post",
        ))
        creation_audit = None
        if row is not None:
            creation_audit = await db.scalar(select(AuditLog).where(
                AuditLog.workspace_id == workspace_id,
                AuditLog.resource_type == "content_asset",
                AuditLog.resource_id == asset_id,
                AuditLog.action.in_(("content_comparison_post.created", "content_comparison_post.revised")),
            ).limit(1))
    if row is None:
        raise HTTPException(404, "Comparison draft was not found in this workspace")
    metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
    integrity_metadata = dict(metadata)
    integrity_metadata["asset_title"] = row.title
    integrity_metadata["source_urls"] = row.source_urls if isinstance(row.source_urls, list) else []
    integrity = evaluate_comparison_integrity(
        row.body,
        integrity_metadata,
        creation_audit.details_json if creation_audit is not None and isinstance(creation_audit.details_json, dict) else None,
    )
    products = metadata.get("products") if isinstance(metadata.get("products"), list) else []
    decision_criteria = metadata.get("decision_criteria") if isinstance(metadata.get("decision_criteria"), list) else []
    comparison_table = metadata.get("comparison_table") if isinstance(metadata.get("comparison_table"), list) else []
    source_snapshots = metadata.get("source_snapshots") if isinstance(metadata.get("source_snapshots"), list) else []
    fact_evidence = metadata.get("fact_evidence") if isinstance(metadata.get("fact_evidence"), list) else []
    evidence_summary = metadata.get("evidence_summary") if isinstance(metadata.get("evidence_summary"), dict) else {}
    source_freshness = evaluate_source_freshness(source_snapshots, row.source_urls if isinstance(row.source_urls, list) else [])
    minimum_word_target = int(metadata.get("minimum_word_target") or 0)
    minimum_word_target_met = bool(metadata.get("minimum_word_target_met", False))
    word_count = int(metadata.get("word_count") or 0)
    saved_topic = str(metadata.get("topic") or row.title.removesuffix(" — Product Comparison"))[:400]
    saved_audience = str(metadata.get("audience") or "")[:300]
    saved_disclosure = str(metadata.get("affiliate_disclosure") or "Disclosure: This article may contain affiliate links. I may earn a commission from qualifying purchases.")[:1200]
    saved_review_status = str(metadata.get("review_status") or "pending_review")
    is_workspace_reviewer = str(user.get("workspace_role") or "").lower() in {"owner", "admin"}
    integrity_review_blocked = not bool(integrity["integrity_verified"])
    review_block_reason = None if not integrity_review_blocked else (
        "Saved article, source evidence, or structured comparison metadata no longer matches its creation-time integrity baseline. "
        "Create a new revision before editorial review."
    )
    try:
        revision_number = max(1, min(100000, int(metadata.get("revision_number") or 1)))
    except (TypeError, ValueError):
        revision_number = 1
    return {
        "asset_id": row.id,
        "asset_status": row.status,
        "title": row.title,
        "topic": saved_topic,
        "audience": saved_audience,
        "affiliate_disclosure": saved_disclosure,
        "revision_number": revision_number,
        "revision_of_asset_id": metadata.get("revision_of_asset_id"),
        "revision_root_asset_id": metadata.get("revision_root_asset_id") or row.id,
        "html": row.body,
        "word_count": word_count,
        "minimum_word_target": minimum_word_target,
        "minimum_word_target_met": minimum_word_target_met,
        "word_count_warning": None if minimum_word_target_met else (
            f"Saved draft has {word_count} words, below {minimum_word_target}; expand and review before publishing."
        ),
        "product_count": len(products),
        "products": products,
        "decision_criteria": decision_criteria,
        "comparison_table": comparison_table,
        "unknown_fact_count": metadata.get("unknown_fact_count", 0),
        "source_urls": row.source_urls if isinstance(row.source_urls, list) else [],
        "source_snapshots": source_snapshots[:10],
        "fact_evidence": fact_evidence[:60],
        "evidence_summary": evidence_summary,
        "source_freshness": source_freshness,
        "evidence_status": metadata.get("evidence_status", "unknown"),
        "product_facts_independently_verified": False,
        "external_product_sources_fetched": bool(metadata.get("external_product_sources_fetched", False)),
        "content_sha256": integrity["actual_content_sha256"],
        "content_integrity_status": integrity["content_integrity_status"],
        "source_snapshot_integrity_status": integrity["source_snapshot_integrity_status"],
        "evidence_payload_sha256": integrity["actual_evidence_payload_sha256"],
        "evidence_payload_integrity_status": integrity["evidence_payload_integrity_status"],
        "integrity_review_blocked": integrity_review_blocked,
        "review_block_reason": review_block_reason,
        "review_status": saved_review_status,
        "review_history": (metadata.get("review_history") if isinstance(metadata.get("review_history"), list) else [])[-25:],
        "reviewed_at": metadata.get("reviewed_at"),
        "reviewed_by": metadata.get("reviewed_by"),
        "reviewer_role": metadata.get("reviewer_role"),
        "reviewer_notes": metadata.get("reviewer_notes"),
        "is_workspace_reviewer": is_workspace_reviewer,
        "can_review": is_workspace_reviewer and row.status == "draft" and saved_review_status == "pending_review" and bool(integrity["integrity_verified"]),
        "can_approve": is_workspace_reviewer and row.status == "draft" and saved_review_status == "pending_review" and bool(integrity["integrity_verified"]) and bool(source_freshness["approval_allowed"]),
        "requires_review": bool(metadata.get("requires_review", True)),
        "publishing_started": False,
        "provider_write_access_verified": False,
        "provider": str(metadata.get("model_provider") or "unreported")[:100],
        "execution_boundary": (
            "Workspace-owned review draft. Public-source snapshots preserve captured wording only; they do not establish "
            "factual truth, currentness, eligibility, compliance approval or publication readiness. No publishing was started."
        ),
    }


@api.post("/content/comparison-posts/{asset_id}/review")
async def review_comparison_post(
    asset_id: str,
    payload: ComparisonPostReviewRequest,
    response: Response,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Record one owner/admin editorial decision for this exact saved draft revision.

    This is an editorial review record only. It never publishes content or approves
    merchant claims, affiliate eligibility, legal compliance, or provider access.
    """
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing a comparison draft")
    reviewer_role = str(user.get("workspace_role") or "").lower()
    if reviewer_role not in {"owner", "admin"}:
        raise HTTPException(403, "Only workspace owners and admins may review comparison drafts")

    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Cookie"
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        row = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "comparison_post",
        ).with_for_update())
        creation_audit = None
        if row is not None:
            creation_audit = await db.scalar(select(AuditLog).where(
                AuditLog.workspace_id == workspace_id,
                AuditLog.resource_type == "content_asset",
                AuditLog.resource_id == asset_id,
                AuditLog.action.in_(("content_comparison_post.created", "content_comparison_post.revised")),
            ).limit(1))
        if row is None:
            raise HTTPException(404, "Comparison draft was not found in this workspace")
        if row.status != "draft":
            raise HTTPException(409, "Only a saved draft revision can receive an editorial review")
        metadata = dict(row.metadata_json) if isinstance(row.metadata_json, dict) else {}
        metadata["asset_title"] = row.title
        metadata["source_urls"] = row.source_urls if isinstance(row.source_urls, list) else []
        review_status = str(metadata.get("review_status") or "pending_review")
        if review_status != "pending_review":
            raise HTTPException(
                409,
                "This immutable draft revision already has a review decision; create a new revision before reviewing again.",
            )
        integrity = evaluate_comparison_integrity(
            row.body,
            metadata,
            creation_audit.details_json if creation_audit is not None and isinstance(creation_audit.details_json, dict) else None,
        )
        if not integrity["integrity_verified"]:
            raise HTTPException(
                409,
                "Saved article, source evidence, or structured comparison metadata does not match its creation-time integrity baseline; create a new revision before review.",
            )
        content_sha256 = integrity["actual_content_sha256"]
        if not hmac.compare_digest(content_sha256, payload.expected_content_sha256):
            raise HTTPException(409, "The saved draft content changed; reload it and review the current content hash")
        if payload.decision == "approve" and payload.confirm_editorial_reviewed is not True:
            raise HTTPException(409, "Approval requires confirm_editorial_reviewed=true after reviewing the saved article")
        source_freshness = evaluate_source_freshness(metadata.get("source_snapshots"), row.source_urls if isinstance(row.source_urls, list) else [])
        if payload.decision == "approve" and not source_freshness["approval_allowed"]:
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=actor,
                action="content_comparison_post.approval_blocked",
                resource_type="content_asset",
                resource_id=row.id,
                outcome="source_evidence_not_current",
                details_json={"code": "SOURCE_EVIDENCE_NOT_CURRENT", "freshness_status": source_freshness["status"], "source_count": source_freshness["source_count"], "fresh_count": source_freshness["fresh_count"], "blocked_count": source_freshness["blocked_count"], "content_sha256": content_sha256, "publishing_started": False},
            ))
            await db.commit()
            raise HTTPException(409, {
                "code": "SOURCE_EVIDENCE_NOT_CURRENT",
                "message": "Editorial approval is blocked because supplied source evidence is stale or incomplete. Create a new revision to refresh evidence before approval.",
                "source_freshness": source_freshness,
            })

        next_status = {
            "approve": "approved",
            "request_changes": "changes_requested",
            "reject": "rejected",
        }[payload.decision]
        reviewed_at = datetime.now(timezone.utc).isoformat()
        try:
            revision_number = max(1, min(100000, int(metadata.get("revision_number") or 1)))
        except (TypeError, ValueError):
            revision_number = 1
        prior_history = metadata.get("review_history")
        history = list(prior_history) if isinstance(prior_history, list) else []
        history.append({
            "decision": payload.decision,
            "review_status": next_status,
            "reviewed_by": actor,
            "reviewer_role": reviewer_role,
            "reviewer_notes": payload.reviewer_notes or None,
            "reviewed_at": reviewed_at,
            "content_sha256": content_sha256,
            "revision_number": revision_number,
            "external_publication_started": False,
        })
        metadata.update({
            "review_status": next_status,
            "review_history": history[-25:],
            "reviewed_at": reviewed_at,
            "reviewed_by": actor,
            "reviewer_role": reviewer_role,
            "reviewer_notes": payload.reviewer_notes or None,
            "reviewed_content_sha256": content_sha256,
            "requires_review": False,
            "publishing_started": False,
        })
        row.metadata_json = metadata
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="content_comparison_post.reviewed",
            resource_type="content_asset",
            resource_id=row.id,
            outcome="editorial_" + next_status,
            details_json={
                "decision": payload.decision,
                "review_status": next_status,
                "reviewer_role": reviewer_role,
                "revision_number": revision_number,
                "content_sha256": content_sha256,
                "source_snapshot_manifest_sha256": metadata.get("source_snapshot_manifest_sha256"),
                "evidence_payload_sha256": metadata.get("evidence_payload_sha256"),
                "evidence_payload_integrity_verified": True,
                "content_integrity_verified": True,
                "source_snapshot_integrity_verified": True,
                "source_freshness_status": source_freshness["status"],
                "source_freshness_policy_version": source_freshness["policy_version"],
                "source_freshness_approval_allowed": source_freshness["approval_allowed"],
                "product_facts_independently_verified": False,
                "affiliate_eligibility_verified": False,
                "external_publication_started": False,
                "publishing_started": False,
            },
        ))
        try:
            await db.commit()
            await db.refresh(row)
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(409, "A concurrent review changed this draft; reload and inspect its review status") from exc

    return {
        "asset_id": row.id,
        "asset_status": row.status,
        "review_status": next_status,
        "review_history": metadata["review_history"],
        "reviewed_at": reviewed_at,
        "reviewed_by": actor,
        "reviewer_role": reviewer_role,
        "reviewer_notes": payload.reviewer_notes or None,
        "content_sha256": content_sha256,
        "content_integrity_status": "verified",
        "source_snapshot_integrity_status": "verified",
        "evidence_payload_sha256": integrity["actual_evidence_payload_sha256"],
        "evidence_payload_integrity_status": "verified",
        "source_freshness": source_freshness,
        "integrity_review_blocked": False,
        "requires_review": False,
        "publishing_started": False,
        "external_publication_started": False,
        "product_facts_independently_verified": False,
        "affiliate_eligibility_verified": False,
        "provider_write_access_verified": False,
        "publication_authorized": False,
        "editorial_review_only": True,
        "execution_boundary": (
            "This decision records a human editorial review of the exact saved draft hash. It does not verify product facts, "
            "merchant identity, currentness, affiliate eligibility, legal compliance, provider authorization, or publication readiness."
        ),
    }


def _listicle_evidence_payload_sha256(metadata: dict[str, Any]) -> str:
    payload = {
        "asset_title": metadata.get("asset_title"),
        "source_urls": metadata.get("source_urls") or [],
        "products": metadata.get("products") or [],
        "products_featured": metadata.get("products_featured") or [],
        "evaluation_criteria": metadata.get("evaluation_criteria") or [],
        "fact_evidence": metadata.get("fact_evidence") or [],
        "evidence_summary": metadata.get("evidence_summary") or {},
        "source_snapshot_manifest_sha256": metadata.get("source_snapshot_manifest_sha256"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _listicle_integrity_flags(asset: ContentAsset, creation_audit: AuditLog | None) -> list[str]:
    metadata = asset.metadata_json if isinstance(asset.metadata_json, dict) else {}
    flags: list[str] = []
    if metadata.get("asset_title") != asset.title:
        flags.append("asset_title_mismatch")
    if metadata.get("content_sha256") != sha256_text(str(asset.body or "")):
        flags.append("content_sha256_mismatch")
    if list(asset.source_urls or []) != list(metadata.get("source_urls") or []):
        flags.append("source_urls_mismatch")
    source_snapshots = metadata.get("source_snapshots") if isinstance(metadata.get("source_snapshots"), list) else []
    for snapshot in source_snapshots:
        if not isinstance(snapshot, dict) or snapshot.get("status") != "fetched":
            continue
        expected_excerpt_hash = hashlib.sha256(str(snapshot.get("excerpt") or "").encode("utf-8")).hexdigest()
        if snapshot.get("excerpt_sha256") != expected_excerpt_hash:
            flags.append("source_excerpt_hash_mismatch")
            break
    manifest = build_source_snapshot_manifest(source_snapshots[:10])
    manifest_hash = source_snapshot_manifest_sha256(manifest)
    if metadata.get("source_snapshot_manifest") != manifest:
        flags.append("source_snapshot_manifest_mismatch")
    if metadata.get("source_snapshot_manifest_sha256") != manifest_hash:
        flags.append("source_snapshot_manifest_sha256_mismatch")
    if metadata.get("evidence_payload_sha256") != _listicle_evidence_payload_sha256(metadata):
        flags.append("evidence_payload_sha256_mismatch")
    if creation_audit is None:
        flags.append("creation_audit_missing")
    else:
        audit_details = creation_audit.details_json if isinstance(creation_audit.details_json, dict) else {}
        if audit_details.get("content_sha256") != metadata.get("content_sha256"):
            flags.append("creation_audit_content_hash_mismatch")
        if audit_details.get("source_snapshot_manifest_sha256") != metadata.get("source_snapshot_manifest_sha256"):
            flags.append("creation_audit_source_manifest_mismatch")
        if audit_details.get("evidence_payload_sha256") != metadata.get("evidence_payload_sha256"):
            flags.append("creation_audit_evidence_payload_mismatch")
    return list(dict.fromkeys(flags))


async def _audit_listicle_integrity_block(
    db: AsyncSession,
    *,
    workspace_id: str,
    actor: str,
    asset_id: str,
    flags: list[str],
) -> None:
    db.add(AuditLog(
        workspace_id=workspace_id,
        actor=actor[:320],
        action="content_listicle_post.integrity_blocked",
        resource_type="content_asset",
        resource_id=asset_id,
        outcome="blocked",
        details_json={"integrity_flags": flags[:12], "review_or_detail_blocked": True, "publishing_started": False},
    ))
    await db.commit()


@api.post("/content/listicle", status_code=201)
async def create_listicle_post(
    payload: ListiclePostRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Create a workspace-persisted listicle draft with public snapshot and literal fact evidence."""
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before generating a listicle")
    _validate_generation_payload_size(payload)
    await workspace_generation_rate_limit(request, workspace_id)

    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    revision_parent_id: str | None = None
    revision_number = 1
    revision_root_asset_id: str | None = None
    if payload.revision_of_asset_id:
        with workspace_scope(workspace_id):
            revision_parent = await db.scalar(select(ContentAsset).where(
                ContentAsset.id == payload.revision_of_asset_id,
                ContentAsset.workspace_id == workspace_id,
                ContentAsset.asset_type == "listicle_post",
            ).with_for_update())
            if revision_parent is None:
                raise HTTPException(404, "Revision source was not found in this workspace")
            if revision_parent.status != "draft":
                raise HTTPException(409, "Only a saved draft can be revised; the original asset was not changed")
            parent_metadata = revision_parent.metadata_json if isinstance(revision_parent.metadata_json, dict) else {}
            parent_audit = await db.scalar(select(AuditLog).where(
                AuditLog.workspace_id == workspace_id,
                AuditLog.action.in_(("content_listicle_post.created", "content_listicle_post.revised")),
                AuditLog.resource_type == "content_asset",
                AuditLog.resource_id == revision_parent.id,
            ).limit(1))
            integrity_flags = _listicle_integrity_flags(revision_parent, parent_audit)
            if integrity_flags:
                await _audit_listicle_integrity_block(
                    db,
                    workspace_id=workspace_id,
                    actor=actor,
                    asset_id=revision_parent.id,
                    flags=integrity_flags,
                )
                raise HTTPException(409, {
                    "code": "LISTICLE_INTEGRITY_CHECK_FAILED",
                    "message": "The saved listicle failed its integrity check; revise only after recovering an intact draft.",
                    "integrity_flags": integrity_flags,
                })
            revision_parent_id = revision_parent.id
            revision_root_asset_id = str(parent_metadata.get("revision_root_asset_id") or revision_parent.id)

        # Release the parent row lock before reserving the root-scoped revision number.
        await db.commit()
        try:
            revision_number = await reserve_content_revision_number(
                db,
                workspace_id=workspace_id,
                root_asset_id=revision_root_asset_id,
                asset_type="listicle_post",
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        with workspace_scope(workspace_id):
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=actor,
                action="content_listicle_post.revision_reserved",
                resource_type="content_asset",
                resource_id=revision_root_asset_id,
                outcome="reserved",
                details_json={
                    "revision_number": revision_number,
                    "revision_of_asset_id": revision_parent_id,
                    "revision_root_asset_id": revision_root_asset_id,
                    "generation_completed": False,
                    "publishing_started": False,
                },
            ))
            # Commit reservation before model/network I/O; failures leave an auditable gap.
            await db.commit()
    try:
        result = await listicle_writer_service(
            topic=payload.topic,
            audience=payload.audience,
            target_keyword=payload.target_keyword,
            products=[product.model_dump() for product in payload.products],
            evaluation_criteria=payload.evaluation_criteria,
            affiliate_disclosure=payload.affiliate_disclosure,
            minimum_words=payload.minimum_words,
            tone=payload.tone,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.exception("Listicle draft generation failed")
        raise HTTPException(
            502,
            {"code": "LISTICLE_DRAFT_GENERATION_FAILED", "message": "Listicle draft generation failed; no draft was saved."},
        ) from exc

    html_body = str(result.get("html") or "")
    content_digest = sha256_text(html_body)
    snapshots = result.get("source_snapshots") if isinstance(result.get("source_snapshots"), list) else []
    source_snapshots = snapshots[:10]
    source_manifest = build_source_snapshot_manifest(source_snapshots)
    source_manifest_digest = source_snapshot_manifest_sha256(source_manifest)
    source_urls = result.get("source_urls") if isinstance(result.get("source_urls"), list) else []
    metadata = {
        "schema_version": 1,
        "asset_title": str(result["title"])[:500],
        "content_sha256": content_digest,
        "source_urls": source_urls,
        "source_snapshot_manifest": source_manifest,
        "source_snapshot_manifest_sha256": source_manifest_digest,
        "topic": payload.topic,
        "audience": payload.audience,
        "affiliate_disclosure": payload.affiliate_disclosure,
        "tone": payload.tone,
        "revision_number": revision_number,
        "revision_of_asset_id": revision_parent_id,
        "revision_root_asset_id": revision_root_asset_id,
        "target_keyword": result.get("target_keyword"),
        "slug": result.get("slug"),
        "meta_description": result.get("meta_description"),
        "format": result.get("format", "listicle"),
        "word_count_warning": result.get("word_count_warning"),
        "provider": str(result.get("provider") or "unreported")[:100],
        "products": result.get("products", []),
        "products_featured": result.get("products_featured", []),
        "evaluation_criteria": result.get("evaluation_criteria", payload.evaluation_criteria),
        "source_snapshots": source_snapshots,
        "fact_evidence": result.get("fact_evidence", [])[:120],
        "evidence_summary": result.get("evidence_summary", {}),
        "evidence_status": result.get("evidence_status", "operator_supplied_unverified"),
        "product_facts_independently_verified": False,
        "external_product_sources_fetched": bool(result.get("external_product_sources_fetched", False)),
        "word_count": result.get("word_count", 0),
        "minimum_word_target": result.get("minimum_word_target", payload.minimum_words),
        "minimum_word_target_met": result.get("minimum_word_target_met", False),
        "model_provider": str(result.get("provider") or "unreported")[:100],
        "review_status": "pending_review",
        "review_history": [],
        "reviewed_at": None,
        "reviewed_by": None,
        "reviewer_role": None,
        "reviewer_notes": None,
        "reviewed_content_sha256": None,
        "requires_review": True,
        "publishing_started": False,
    }
    metadata["evidence_payload_sha256"] = _listicle_evidence_payload_sha256(metadata)
    with workspace_scope(workspace_id):
        asset = ContentAsset(
            workspace_id=workspace_id,
            asset_type="listicle_post",
            title=str(result["title"])[:500],
            body=html_body,
            status="draft",
            source_urls=source_urls,
            metadata_json=metadata,
        )
        db.add(asset)
        await db.flush()
        root_asset_id = revision_root_asset_id or asset.id
        if metadata["revision_root_asset_id"] is None:
            # Reassign a fresh JSON object so SQLAlchemy persists the root ID.
            metadata = {**metadata, "revision_root_asset_id": root_asset_id}
            asset.metadata_json = metadata
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="content_listicle_post.revised" if revision_parent_id else "content_listicle_post.created",
            resource_type="content_asset",
            resource_id=asset.id,
            outcome="draft",
            details_json={
                "product_count": result["product_count"],
                "source_snapshots_fetched": (result.get("evidence_summary") or {}).get("source_snapshots_fetched", 0),
                "exact_text_match_count": (result.get("evidence_summary") or {}).get("exact_text_match_count", 0),
                "exact_text_not_found_count": (result.get("evidence_summary") or {}).get("exact_text_not_found_count", 0),
                "content_sha256": content_digest,
                "source_snapshot_manifest_sha256": source_manifest_digest,
                "evidence_payload_sha256": metadata["evidence_payload_sha256"],
                "revision_number": revision_number,
                "revision_of_asset_id": revision_parent_id,
                "revision_root_asset_id": root_asset_id,
                "publishing_started": False,
            },
        ))
        await db.commit()
        await db.refresh(asset)
    result["asset_id"] = asset.id
    result["asset_status"] = asset.status
    result["topic"] = payload.topic
    result["audience"] = payload.audience
    result["affiliate_disclosure"] = payload.affiliate_disclosure
    result["tone"] = payload.tone
    result["revision_number"] = revision_number
    result["revision_of_asset_id"] = revision_parent_id
    result["revision_root_asset_id"] = root_asset_id
    result["content_sha256"] = content_digest
    result["source_snapshot_manifest_sha256"] = source_manifest_digest
    result["evidence_payload_sha256"] = metadata["evidence_payload_sha256"]
    result["content_integrity_status"] = "verified"
    result["review_status"] = "pending_review"
    result["review_history"] = []
    result["reviewed_by"] = None
    result["reviewed_at"] = None
    result["reviewer_role"] = None
    result["reviewer_notes"] = None
    result["can_review"] = str(user.get("workspace_role") or "").lower() in {"owner", "admin"}
    result["source_freshness"] = evaluate_source_freshness(source_snapshots, source_urls)
    result["can_approve"] = result["can_review"] and bool(result["source_freshness"]["approval_allowed"])
    return result


@api.get("/content/listicles")
async def list_listicle_posts(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before listing listicle drafts")
    response.headers["Cache-Control"] = "no-store"
    with workspace_scope(workspace_id):
        condition = and_(
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "listicle_post",
        )
        total = int(await db.scalar(select(func.count()).select_from(ContentAsset).where(condition)) or 0)
        rows = list((await db.scalars(
            select(ContentAsset).where(condition)
            .order_by(ContentAsset.created_at.desc(), ContentAsset.id.desc())
            .limit(limit).offset(offset)
        )).all())
    items = []
    for row in rows:
        metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        body_hash_matches = metadata.get("content_sha256") == sha256_text(str(row.body or ""))
        items.append({
            "asset_id": row.id,
            "title": row.title,
            "asset_status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "product_count": len(metadata.get("products_featured") or []),
            "word_count": int(metadata.get("word_count") or 0),
            "evidence_status": metadata.get("evidence_status", "unknown"),
            "review_status": metadata.get("review_status", "pending_review"),
            "content_sha256": metadata.get("content_sha256"),
            "content_integrity_status": "verified" if body_hash_matches else "mismatch",
            "revision_number": metadata.get("revision_number", 1),
            "revision_of_asset_id": metadata.get("revision_of_asset_id"),
            "revision_root_asset_id": metadata.get("revision_root_asset_id") or row.id,
            "publishing_started": False,
        })
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@api.get("/content/listicles/{asset_id}")
async def get_listicle_post(
    asset_id: str,
    response: Response,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before opening a listicle draft")
    response.headers["Cache-Control"] = "no-store"
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        asset = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "listicle_post",
        ))
        if asset is None:
            raise HTTPException(404, "Listicle draft was not found in this workspace")
        creation_audit = await db.scalar(select(AuditLog).where(
            AuditLog.workspace_id == workspace_id,
            AuditLog.action.in_(("content_listicle_post.created", "content_listicle_post.revised")),
            AuditLog.resource_type == "content_asset",
            AuditLog.resource_id == asset.id,
        ).limit(1))
        flags = _listicle_integrity_flags(asset, creation_audit)
        if flags:
            await _audit_listicle_integrity_block(
                db, workspace_id=workspace_id, actor=actor, asset_id=asset.id, flags=flags
            )
            raise HTTPException(409, {
                "code": "LISTICLE_INTEGRITY_CHECK_FAILED",
                "message": "Saved listicle content or evidence no longer matches its creation baseline; retrieval and editorial review are blocked.",
                "integrity_flags": flags,
            })
        metadata = dict(asset.metadata_json)
    source_freshness = evaluate_source_freshness(metadata.get("source_snapshots"), metadata.get("source_urls") or [])
    can_review = str(user.get("workspace_role") or "").lower() in {"owner", "admin"}
    can_approve = can_review and asset.status == "draft" and metadata.get("review_status", "pending_review") == "pending_review" and bool(source_freshness["approval_allowed"])
    return {
        "asset_id": asset.id,
        "asset_status": asset.status,
        "title": asset.title,
        "html": asset.body,
        **{key: metadata.get(key) for key in (
            "slug", "meta_description", "topic", "audience", "affiliate_disclosure", "tone", "target_keyword", "products",
            "products_featured", "evaluation_criteria", "source_urls", "source_snapshots",
            "fact_evidence", "evidence_summary", "evidence_status", "word_count",
            "minimum_word_target", "minimum_word_target_met", "word_count_warning", "provider",
            "review_status", "review_history", "reviewed_at", "reviewed_by", "reviewer_role",
            "reviewer_notes", "publishing_started", "requires_review", "content_sha256",
            "revision_number", "revision_of_asset_id", "revision_root_asset_id",
            "source_snapshot_manifest_sha256", "evidence_payload_sha256",
        )},
        "content_integrity_status": "verified",
        "source_freshness": source_freshness,
        "can_review": can_review,
        "can_approve": can_approve,
        "execution_boundary": "Draft only; source text is not truth verification and editorial approval does not authorize publishing.",
    }


@api.post("/content/listicles/{asset_id}/review")
async def review_listicle_post(
    asset_id: str,
    payload: ComparisonPostReviewRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    role = str(user.get("workspace_role") or "").lower()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing a listicle")
    if role not in {"owner", "admin"}:
        raise HTTPException(403, "Only workspace owners and admins may review listicle drafts")
    if payload.decision == "approve" and payload.confirm_editorial_reviewed is not True:
        raise HTTPException(422, "Confirm that you reviewed the article and its source/fact evidence before approval")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        asset = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "listicle_post",
        ).with_for_update())
        if asset is None:
            raise HTTPException(404, "Listicle draft was not found in this workspace")
        metadata = dict(asset.metadata_json) if isinstance(asset.metadata_json, dict) else {}
        creation_audit = await db.scalar(select(AuditLog).where(
            AuditLog.workspace_id == workspace_id,
            AuditLog.action.in_(("content_listicle_post.created", "content_listicle_post.revised")),
            AuditLog.resource_type == "content_asset",
            AuditLog.resource_id == asset.id,
        ).limit(1))
        flags = _listicle_integrity_flags(asset, creation_audit)
        if flags:
            await _audit_listicle_integrity_block(
                db, workspace_id=workspace_id, actor=actor, asset_id=asset.id, flags=flags
            )
            raise HTTPException(409, {
                "code": "LISTICLE_INTEGRITY_CHECK_FAILED",
                "message": "Saved listicle content or evidence no longer matches its creation baseline; editorial review is blocked.",
                "integrity_flags": flags,
            })
        if sha256_text(str(asset.body or "")) != payload.expected_content_sha256:
            raise HTTPException(409, "The reviewed listicle changed; reload it and review the current saved draft")
        if metadata.get("review_status", "pending_review") != "pending_review":
            raise HTTPException(409, "This immutable draft already has an editorial decision; create a new draft to make changes")
        source_freshness = evaluate_source_freshness(metadata.get("source_snapshots"), metadata.get("source_urls") or [])
        if payload.decision == "approve" and not source_freshness["approval_allowed"]:
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=actor,
                action="content_listicle_post.approval_blocked",
                resource_type="content_asset",
                resource_id=asset.id,
                outcome="source_evidence_not_current",
                details_json={"code": "SOURCE_EVIDENCE_NOT_CURRENT", "freshness_status": source_freshness["status"], "source_count": source_freshness["source_count"], "fresh_count": source_freshness["fresh_count"], "blocked_count": source_freshness["blocked_count"], "content_sha256": payload.expected_content_sha256, "publishing_started": False},
            ))
            await db.commit()
            raise HTTPException(409, {
                "code": "SOURCE_EVIDENCE_NOT_CURRENT",
                "message": "Editorial approval is blocked because supplied source evidence is stale or incomplete. Create a new revision to refresh evidence before approval.",
                "source_freshness": source_freshness,
            })
        reviewed_at = utcnow()
        review_status = {
            "approve": "approved",
            "request_changes": "changes_requested",
            "reject": "rejected",
        }[payload.decision]
        history = list(metadata.get("review_history") or [])
        history.append({
            "decision": payload.decision,
            "review_status": review_status,
            "reviewed_by": actor,
            "reviewer_role": role,
            "reviewer_notes": payload.reviewer_notes or None,
            "reviewed_at": reviewed_at.isoformat(),
            "content_sha256": payload.expected_content_sha256,
            "external_publication_started": False,
        })
        updated = {
            **metadata,
            "review_status": review_status,
            "review_history": history[-20:],
            "reviewed_at": reviewed_at.isoformat(),
            "reviewed_by": actor,
            "reviewer_role": role,
            "reviewer_notes": payload.reviewer_notes or None,
            "reviewed_content_sha256": payload.expected_content_sha256,
            "publishing_started": False,
        }
        asset.metadata_json = updated
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="content_listicle_post.reviewed",
            resource_type="content_asset",
            resource_id=asset.id,
            outcome=review_status,
            details_json={
                "decision": payload.decision,
                "review_status": review_status,
                "content_sha256": payload.expected_content_sha256,
                "evidence_payload_sha256": metadata.get("evidence_payload_sha256"),
                "reviewer_role": role,
                "source_freshness_status": source_freshness["status"],
                "source_freshness_policy_version": source_freshness["policy_version"],
                "source_freshness_approval_allowed": source_freshness["approval_allowed"],
                "external_publication_started": False,
            },
        ))
        await db.commit()
        await db.refresh(asset)
    return {
        "asset_id": asset.id,
        "asset_status": asset.status,
        "review_status": review_status,
        "source_freshness": source_freshness,
        "revision_number": (asset.metadata_json or {}).get("revision_number", 1) if isinstance(asset.metadata_json, dict) else 1,
        "revision_of_asset_id": (asset.metadata_json or {}).get("revision_of_asset_id") if isinstance(asset.metadata_json, dict) else None,
        "revision_root_asset_id": ((asset.metadata_json or {}).get("revision_root_asset_id") or asset.id) if isinstance(asset.metadata_json, dict) else asset.id,
        "reviewed_by": actor,
        "reviewed_at": reviewed_at.isoformat(),
        "content_sha256": payload.expected_content_sha256,
        "publishing_started": False,
        "execution_boundary": "Editorial approval only. No affiliate network, ad platform, CMS, or social provider action was executed.",
    }


@api.post("/content/video")
async def video(
    payload: VideoRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before rendering video")
    _validate_generation_payload_size(payload)
    await workspace_generation_rate_limit(request, str(workspace_id), video=True)
    with workspace_scope(str(workspace_id)):
        return await render_vertical_video(
            payload.script,
            broll_query=payload.broll_query,
            voice=payload.voice,
            captions=payload.captions,
        )


@api.post("/landing/offer")
async def landing_offer(
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before generating an offer")
    _validate_generation_payload_size(payload)
    product = payload.get("product") or {}
    audience = str(payload.get("audience") or "")
    main_problem = str(payload.get("main_problem") or "")
    if not isinstance(product, dict) or len(audience) > 1000 or len(main_problem) > 2000:
        raise HTTPException(422, "Offer inputs exceed the supported limits")
    await workspace_generation_rate_limit(request, str(workspace_id))
    with workspace_scope(str(workspace_id)):
        return await grand_slam_offer_generator(product, audience, main_problem)


@api.post("/landing/value-ladder")
async def landing_ladder(
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before generating a value ladder")
    _validate_generation_payload_size(payload)
    audience = str(payload.get("audience") or "")
    product = payload.get("product") or {}
    assets = payload.get("deliverable_assets")
    if not isinstance(product, dict) or len(audience) > 1000:
        raise HTTPException(422, "Value-ladder inputs exceed the supported limits")
    await workspace_generation_rate_limit(request, str(workspace_id))
    with workspace_scope(str(workspace_id)):
        return await value_ladder_architect(audience, product, assets)
@api.post("/landing/guarantee-draft", status_code=201)
async def landing_guarantee_draft(
    payload: GuaranteeDraftRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Save a guarantee-copy draft based on explicit operator-supplied merchant terms."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before drafting guarantee copy")
    try:
        generated = build_guarantee_draft_service(
            product_name=payload.product_name,
            guarantee_type=payload.guarantee_type,
            duration_days=payload.duration_days,
            eligibility=payload.eligibility,
            exclusions=payload.exclusions,
            claim_process=payload.claim_process,
            merchant_terms_text=payload.merchant_terms_text,
            source_url=payload.source_url,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    with workspace_scope(str(workspace_id)):
        asset = ContentAsset(
            workspace_id=str(workspace_id),
            asset_type="guarantee_terms_draft",
            title=f"{generated['product_name']} guarantee wording draft",
            body=generated["draft_copy"],
            status="draft",
            source_urls=[payload.source_url] if payload.source_url else [],
            metadata_json={
                "guarantee_draft_version": "1",
                "guarantee_type": generated["guarantee_type"],
                "duration_days": generated["duration_days"],
                "merchant_terms_status": generated["merchant_terms_status"],
                "source_terms_sha256": hashlib.sha256(payload.merchant_terms_text.encode("utf-8")).hexdigest(),
                "terms_verified": False,
                "requires_review": True,
                "publishing_started": False,
            },
        )
        db.add(asset)
        await db.commit()
    return {**generated, "asset_id": asset.id}



def _webinar_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _webinar_iso(value: datetime | None) -> str | None:
    return _webinar_utc(value).isoformat() if value is not None else None


@api.post("/webinars", status_code=201)
async def create_webinar(payload: WebinarCreateRequest, user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating a webinar")
    if user.get("workspace_role") not in {"owner", "admin"} and user.get("is_admin") is not True:
        raise HTTPException(403, "Workspace owner/admin approval is required to create a public webinar page")
    workspace_id = str(workspace_id)
    public_id = secrets.token_urlsafe(24)
    with workspace_scope(workspace_id):
        row = WebinarEvent(
            workspace_id=workspace_id, public_id=public_id, title=payload.title,
            summary=payload.summary, description=payload.description, host_name=payload.host_name,
            host_bio=payload.host_bio, start_at=payload.start_at, end_at=payload.end_at,
            timezone_name=payload.timezone_name, registration_deadline=payload.registration_deadline,
            capacity=payload.capacity, agenda_json=[item.model_dump() for item in payload.agenda_items],
            privacy_policy_url=payload.privacy_policy_url, consent_text=payload.consent_text,
            affiliate_disclosure=payload.affiliate_disclosure, status="draft",
        )
        db.add(row)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id, actor=str(user.get("email") or "unknown"),
            action="webinar.registration_page.created", resource_type="webinar_event",
            resource_id=row.id, outcome="draft",
            details_json={"public_id": public_id, "capacity_limited": payload.capacity is not None,
                          "external_webinar_provider": "not_configured", "public_registration_open": False},
        ))
        await db.commit()
    return {"id": row.id, "public_id": row.public_id, "title": row.title, "status": row.status,
            "public_path": f"/webinar/{row.public_id}", "start_at": _webinar_iso(row.start_at),
            "end_at": _webinar_iso(row.end_at), "timezone_name": row.timezone_name,
            "registration_deadline": _webinar_iso(row.registration_deadline), "capacity": row.capacity,
            "public_registration_open": False, "external_webinar_provider": "not_configured",
            "confirmation_email_sent": False}


@api.get("/webinars")
async def list_webinars(limit: int = Query(default=100, ge=1, le=300), user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before listing webinars")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        rows = list((await db.scalars(select(WebinarEvent).where(WebinarEvent.workspace_id == workspace_id).order_by(WebinarEvent.start_at.asc()).limit(limit))).all())
        result = []
        for row in rows:
            count = await db.scalar(select(func.count(WebinarRegistration.id)).where(
                WebinarRegistration.workspace_id == workspace_id, WebinarRegistration.webinar_id == row.id))
            result.append({"id": row.id, "public_id": row.public_id, "title": row.title, "status": row.status,
                "start_at": _webinar_iso(row.start_at), "end_at": _webinar_iso(row.end_at),
                "timezone_name": row.timezone_name, "capacity": row.capacity,
                "registration_count": int(count or 0), "public_path": f"/webinar/{row.public_id}",
                "external_webinar_provider": "not_configured"})
    return {"count": len(result), "data": result}


@api.post("/webinars/{webinar_id}/open")
async def open_webinar_registrations(webinar_id: str, user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before opening registrations")
    if user.get("workspace_role") not in {"owner", "admin"} and user.get("is_admin") is not True:
        raise HTTPException(403, "Workspace owner/admin approval is required to open registrations")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(WebinarEvent).where(WebinarEvent.id == webinar_id, WebinarEvent.workspace_id == workspace_id))
        if row is None:
            raise HTTPException(404, "Webinar not found in the active workspace")
        if row.status == "closed":
            raise HTTPException(409, "A closed webinar cannot be reopened; create a new registration page")
        if _webinar_utc(row.start_at) <= datetime.now(timezone.utc):
            raise HTTPException(409, "Webinar start time has passed")
        if row.registration_deadline and _webinar_utc(row.registration_deadline) <= datetime.now(timezone.utc):
            raise HTTPException(409, "Registration deadline has passed")
        row.status = "open"
        db.add(AuditLog(workspace_id=workspace_id, actor=str(user.get("email") or "unknown"),
            action="webinar.registration_page.opened", resource_type="webinar_event",
            resource_id=row.id, outcome="public_registration_open",
            details_json={"public_id": row.public_id, "external_provider_write": False}))
        await db.commit()
        return {"id": row.id, "public_id": row.public_id, "status": row.status,
                "public_path": f"/webinar/{row.public_id}", "external_provider_write": False}


@api.post("/webinars/{webinar_id}/close")
async def close_webinar_registrations(webinar_id: str, user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before closing registrations")
    if user.get("workspace_role") not in {"owner", "admin"} and user.get("is_admin") is not True:
        raise HTTPException(403, "Workspace owner/admin approval is required to close registrations")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(WebinarEvent).where(WebinarEvent.id == webinar_id, WebinarEvent.workspace_id == workspace_id))
        if row is None:
            raise HTTPException(404, "Webinar not found in the active workspace")
        row.status = "closed"
        db.add(AuditLog(workspace_id=workspace_id, actor=str(user.get("email") or "unknown"),
            action="webinar.registration_page.closed", resource_type="webinar_event",
            resource_id=row.id, outcome="registrations_closed", details_json={"public_id": row.public_id}))
        await db.commit()
        return {"id": row.id, "public_id": row.public_id, "status": row.status, "public_registration_open": False}


@api.post("/landing/page")
async def landing_page(
    payload: LandingPageRequest,
    user: dict[str, Any] = Depends(require_auth),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before issuing a landing page token")
    owner_workspace_id = str(workspace_id)
    with workspace_scope(owner_workspace_id):
        html = squeeze_page_builder(
            headline=payload.headline,
            subheadline=payload.subheadline,
            benefit_bullets=payload.benefit_bullets,
            form_action=payload.form_action,
            privacy_url=payload.privacy_url,
            affiliate_disclosure=payload.affiliate_disclosure,
            lead_magnet=payload.lead_magnet,
            audience=payload.audience,
            workspace_token=issue_workspace_token(owner_workspace_id, "lead_capture"),
        )
    return HTMLResponse(html)




def _landing_page_summary(row: ContentAsset) -> dict[str, Any]:
    metadata = dict(row.metadata_json or {})
    published = row.status == "published"
    return {
        "id": row.id,
        "title": row.title,
        "status": row.status,
        "public_url": metadata.get("public_url") if published else None,
        "preview_url": "/api/landing/pages/" + row.id + "/preview",
        "requires_review": not published,
        "publishing_started": published,
        "privacy_url": metadata.get("privacy_url"),
        "lead_magnet": metadata.get("lead_magnet"),
        "audience": metadata.get("audience"),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _render_saved_landing_page(
    row: ContentAsset, *, utm_attribution: dict[str, Any] | None = None
) -> str:
    metadata = dict(row.metadata_json or {})
    return render_workspace_landing_page(
        headline=row.title,
        subheadline=str(metadata.get("subheadline") or ""),
        benefit_bullets=[str(item) for item in metadata.get("benefit_bullets", []) if str(item).strip()],
        privacy_url=str(metadata.get("privacy_url") or ""),
        affiliate_disclosure=metadata.get("affiliate_disclosure"),
        lead_magnet=str(metadata.get("lead_magnet") or "Free resource"),
        audience=str(metadata.get("audience") or "website subscriber"),
        workspace_token=issue_workspace_token(str(row.workspace_id), "lead_capture"),
        utm_attribution=utm_attribution,
    )


@api.get("/landing/pages")
async def list_landing_pages(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing landing pages")
    with workspace_scope(workspace_id):
        rows = list((await db.scalars(
            select(ContentAsset)
            .where(
                ContentAsset.workspace_id == workspace_id,
                ContentAsset.asset_type == "landing_page",
            )
            .order_by(ContentAsset.created_at.desc())
            .limit(100)
        )).all())
    return {"count": len(rows), "data": [_landing_page_summary(row) for row in rows]}


@api.post("/landing/pages", status_code=201)
async def create_landing_page_draft(
    payload: LandingPageRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating a landing-page draft")
    if payload.form_action != "/api/public/leads/capture":
        raise HTTPException(422, "Persisted landing pages must use the consent-gated lead-capture endpoint")

    asset_id = secrets.token_hex(18)
    metadata = {
        "schema_version": 1,
        "subheadline": payload.subheadline,
        "benefit_bullets": [str(item) for item in payload.benefit_bullets],
        "privacy_url": payload.privacy_url,
        "affiliate_disclosure": payload.affiliate_disclosure,
        "lead_magnet": payload.lead_magnet,
        "audience": payload.audience,
        "created_by": str(user.get("email") or "unknown")[:320],
        "requires_review": True,
        "external_publication_started": False,
    }
    # Store token-free HTML; preview/public requests get a freshly signed token.
    html = render_workspace_landing_page(
        headline=payload.headline,
        subheadline=payload.subheadline,
        benefit_bullets=payload.benefit_bullets,
        privacy_url=payload.privacy_url,
        affiliate_disclosure=payload.affiliate_disclosure,
        lead_magnet=payload.lead_magnet,
        audience=payload.audience,
        workspace_token=None,
    )
    with workspace_scope(workspace_id):
        row = ContentAsset(
            id=asset_id,
            workspace_id=workspace_id,
            asset_type="landing_page",
            title=payload.headline,
            body=html,
            status="draft",
            source_urls=[payload.privacy_url],
            metadata_json=metadata,
        )
        db.add(row)
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "unknown")[:320],
            action="landing_page.draft_created",
            resource_type="content_asset",
            resource_id=asset_id,
            outcome="draft",
            details_json={
                "headline": payload.headline[:250],
                "privacy_url": payload.privacy_url,
                "requires_review": True,
                "external_publication_started": False,
            },
        ))
        await db.commit()
        await db.refresh(row)
        return _landing_page_summary(row)


@api.get("/landing/pages/{asset_id}/preview", response_class=HTMLResponse)
async def preview_landing_page(
    asset_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before previewing a landing page")
    with workspace_scope(workspace_id):
        row = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "landing_page",
        ))
    if row is None:
        raise HTTPException(404, "Landing page not found in the active workspace")
    return HTMLResponse(_render_saved_landing_page(row), headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Robots-Tag": "noindex",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'",
    })


@api.post("/landing/pages/{asset_id}/publish")
async def publish_landing_page(
    asset_id: str,
    payload: LandingPagePublishRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before publishing a landing page")
    if str(user.get("workspace_role") or "") not in {"owner", "admin"}:
        raise HTTPException(403, "Only a workspace owner or admin may approve public landing-page publication")
    if payload.confirm_public_publish is not True:
        raise HTTPException(409, "Public landing-page publication requires explicit confirmation")

    with workspace_scope(workspace_id):
        row = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "landing_page",
        ))
        if row is None:
            raise HTTPException(404, "Landing page not found in the active workspace")
        if row.status == "published":
            return _landing_page_summary(row)
        if row.status != "draft":
            raise HTTPException(409, "Only a draft landing page can be published")
        metadata = dict(row.metadata_json or {})
        public_url = settings.app_public_url.rstrip("/") + "/p/" + row.id
        metadata.update({
            "public_url": public_url,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "published_by": str(user.get("email") or "unknown")[:320],
            "requires_review": False,
            "external_publication_started": True,
        })
        row.metadata_json = metadata
        row.status = "published"
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "unknown")[:320],
            action="landing_page.published",
            resource_type="content_asset",
            resource_id=row.id,
            outcome="published",
            details_json={
                "public_url": public_url,
                "explicit_confirmation": True,
                "external_publication_started": True,
            },
        ))
        await db.commit()
        await db.refresh(row)
        return _landing_page_summary(row)


@api.post("/landing/pages/{asset_id}/unpublish")
async def unpublish_landing_page(
    asset_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before unpublishing a landing page")
    if str(user.get("workspace_role") or "") not in {"owner", "admin"}:
        raise HTTPException(403, "Only a workspace owner or admin may unpublish a landing page")

    with workspace_scope(workspace_id):
        row = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "landing_page",
        ))
        if row is None:
            raise HTTPException(404, "Landing page not found in the active workspace")
        if row.status == "draft":
            return _landing_page_summary(row)
        if row.status != "published":
            raise HTTPException(409, "Only a published landing page can be unpublished")
        metadata = dict(row.metadata_json or {})
        metadata.pop("public_url", None)
        metadata.update({
            "unpublished_at": datetime.now(timezone.utc).isoformat(),
            "unpublished_by": str(user.get("email") or "unknown")[:320],
            "requires_review": True,
            "external_publication_started": False,
        })
        row.metadata_json = metadata
        row.status = "draft"
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "unknown")[:320],
            action="landing_page.unpublished",
            resource_type="content_asset",
            resource_id=row.id,
            outcome="unpublished",
            details_json={"public_url": None, "external_publication_started": False},
        ))
        await db.commit()
        await db.refresh(row)
        return _landing_page_summary(row)


@app.get("/p/{asset_id}", response_class=HTMLResponse, include_in_schema=False)
async def public_landing_page(
    asset_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    await public_rate_limit(request)
    row = await db.scalar(select(ContentAsset).where(
        ContentAsset.id == asset_id,
        ContentAsset.asset_type == "landing_page",
        ContentAsset.status == "published",
    ))
    if row is None:
        raise HTTPException(404, "Landing page not found")
    return HTMLResponse(
        _render_saved_landing_page(row, utm_attribution=normalize_utm_attribution(request.query_params)),
        headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'",
    })



@api.post("/landing/email-drip")
async def drip(payload: dict[str, Any]):
    return {
        "sequence": email_drip_sequence(
            audience=str(payload.get("audience") or ""),
            lead_magnet=str(payload.get("lead_magnet") or ""),
            affiliate_offer=payload.get("affiliate_offer") or {},
            duration_days=int(payload.get("duration_days", 5)),
        )
    }


@api.post("/social/publish")
async def social_publish(
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    # Current provider tokens are global configuration, not workspace-owned credentials.
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before social publishing")
    platform = str(payload.get("platform") or "").strip().lower()
    post = dict(payload.get("post") or {})
    live = not settings.publishing_dry_run
    if live and payload.get("confirm_live_publish") is not True:
        raise HTTPException(409, "Live publishing requires confirm_live_publish=true from an authorized operator")
    owner_workspace_id = str(workspace_id)
    action_id: str | None = None
    target_jurisdictions: list[str] = []
    if live:
        supplied_key = str(request.headers.get("Idempotency-Key") or "").strip()
        if not EXTERNAL_IDEMPOTENCY_KEY_RE.fullmatch(supplied_key):
            raise HTTPException(428, "A valid Idempotency-Key header is required for live social publishing")
        try:
            target_jurisdictions = normalize_jurisdictions(payload.get("target_jurisdictions") or [])
        except ValueError as exc:
            raise HTTPException(422, {
                "code": "TARGET_JURISDICTIONS_REQUIRED",
                "message": "Live publishing requires explicit target_jurisdictions.",
            }) from exc
        action_id, replay = await _claim_external_action(
            db, workspace_id=owner_workspace_id, action_type="social_publish",
            provider=platform or "unknown", idempotency_key=supplied_key,
            request_payload={"platform": platform, "post": post, "target_jurisdictions": target_jurisdictions},
        )
        if replay is not None:
            await _record_external_publish_audit(
                db, user=user, workspace_id=owner_workspace_id,
                action="social_publish_idempotency_replay", platform=platform or "unknown",
                outcome="replayed", remote_id=replay.get("remote_id"),
            )
            return replay
    if live:
        try:
            await _require_live_compliance_approval(
                db, workspace_id=owner_workspace_id, activity="content_publish",
                jurisdictions=target_jurisdictions, channel=platform,
                actor=str(user.get("email") or user.get("user_id") or "unknown"), action="social_publish",
            )
        except HTTPException as exc:
            if action_id:
                await _finish_external_action(
                    db, workspace_id=owner_workspace_id, action_id=action_id,
                    status="failed", error_type="ComplianceApprovalRequired",
                )
            raise exc
    try:
        with workspace_scope(owner_workspace_id):
            result = await social_media_scheduler(platform, post)
    except Exception as exc:
        action_outcome = _external_action_failure_status(exc)
        if action_id:
            try:
                await _finish_external_action(
                    db, workspace_id=owner_workspace_id, action_id=action_id,
                    status=action_outcome, error_type=type(exc).__name__,
                )
            except Exception:
                logger.exception("Could not persist social action outcome for workspace %s", owner_workspace_id[:8])
        await _record_external_publish_audit(
            db, user=user, workspace_id=owner_workspace_id, action="social_publish",
            platform=platform or "unknown",
            outcome="outcome_unknown" if action_outcome == "unknown" else "failed",
            error_type=type(exc).__name__,
        )
        raise
    if action_id:
        await _finish_external_action(db, workspace_id=owner_workspace_id, action_id=action_id, status="completed", result=result)
    await _record_external_publish_audit(
        db, user=user, workspace_id=owner_workspace_id, action="social_publish",
        platform=platform or "unknown", outcome=str(result.get("status") or "unknown"),
        remote_id=result.get("remote_id"),
    )
    return result
_public_hits: dict[str, list[float]] = {}
_public_lock = asyncio.Lock()
_public_rate_limit_redis: Any | None = None
_public_rate_limit_redis_lock = asyncio.Lock()
_RATE_LIMIT_WINDOW_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
return count
"""


def _rate_limit_key(bucket: str, identity: str) -> str:
    # Never store a raw client IP or workspace identifier in Redis keys.
    digest = hashlib.sha256(identity.encode("utf-8", "replace")).hexdigest()
    return f"omni-affiliate-os:rate-limit:v1:{bucket}:{digest}"


async def _get_public_rate_limit_redis():
    global _public_rate_limit_redis
    if _public_rate_limit_redis is not None:
        return _public_rate_limit_redis
    async with _public_rate_limit_redis_lock:
        if _public_rate_limit_redis is None:
            from redis.asyncio import Redis

            _public_rate_limit_redis = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
    return _public_rate_limit_redis


async def close_public_rate_limiter() -> None:
    global _public_rate_limit_redis
    client = _public_rate_limit_redis
    _public_rate_limit_redis = None
    if client is not None:
        close = getattr(client, "aclose", None) or getattr(client, "close", None)
        if close is not None:
            result = close()
            if asyncio.iscoroutine(result):
                await result


async def _consume_rate_limit(
    *,
    bucket: str,
    identity: str,
    limit: int,
    window_seconds: int,
    detail: str,
) -> None:
    key = _rate_limit_key(bucket, identity)
    if settings.app_env == "production":
        try:
            client = await _get_public_rate_limit_redis()
            count = int(await client.eval(_RATE_LIMIT_WINDOW_SCRIPT, 1, key, window_seconds))
        except Exception as exc:
            # Do not fall back to per-process limits in production: multiple workers
            # would otherwise multiply the effective quota and defeat abuse controls.
            logger.error("Distributed rate limiting unavailable: %s", type(exc).__name__)
            raise HTTPException(503, "Request protection is temporarily unavailable; retry later") from exc
        if count > limit:
            raise HTTPException(429, detail)
        return

    # Local/test mode keeps a deterministic in-memory implementation so unit tests
    # and developer setups do not require Redis. Production never uses this fallback.
    now = time.monotonic()
    async with _public_lock:
        recent = [stamp for stamp in _public_hits.get(key, []) if now - stamp < window_seconds]
        if len(recent) >= limit:
            _public_hits[key] = recent
            raise HTTPException(429, detail)
        recent.append(now)
        _public_hits[key] = recent
        if len(_public_hits) > 5000:
            for stale_key in list(_public_hits)[:1000]:
                stamps = _public_hits.get(stale_key, [])
                if not stamps or now - stamps[-1] >= 3600:
                    _public_hits.pop(stale_key, None)


async def public_rate_limit(request: Request) -> None:
    # Use the direct ASGI peer address. X-Forwarded-For is intentionally ignored
    # unless a trusted-proxy deployment explicitly normalizes request.client.host.
    ip = request.client.host if request.client else "unknown"
    await _consume_rate_limit(
        bucket="public-ip",
        identity=ip,
        limit=20,
        window_seconds=3600,
        detail="Signup rate limit exceeded",
    )


async def workspace_generation_rate_limit(
    request: Request,
    workspace_id: str,
    *,
    video: bool = False,
) -> None:
    ip = request.client.host if request.client else "unknown"
    await _consume_rate_limit(
        bucket="generation-ip",
        identity=ip,
        limit=60,
        window_seconds=3600,
        detail="Content generation rate limit exceeded for this client",
    )
    await _consume_rate_limit(
        bucket="generation-workspace",
        identity=workspace_id,
        limit=20,
        window_seconds=3600,
        detail="Workspace content generation budget exceeded",
    )
    if video:
        await _consume_rate_limit(
            bucket="video-ip",
            identity=ip,
            limit=5,
            window_seconds=3600,
            detail="Video rendering rate limit exceeded for this client",
        )
        await _consume_rate_limit(
            bucket="video-workspace",
            identity=workspace_id,
            limit=3,
            window_seconds=3600,
            detail="Workspace video rendering budget exceeded",
        )


def _validate_generation_payload_size(payload: Any, *, limit_bytes: int = 65536) -> None:
    if hasattr(payload, "model_dump_json"):
        serialized = payload.model_dump_json()
    else:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(serialized.encode("utf-8")) > limit_bytes:
        raise HTTPException(413, "Generation request exceeds the configured payload size limit")

async def create_lead(
    payload: LeadCaptureRequest,
    db: AsyncSession,
    *,
    workspace_id: str,
):
    owner_workspace_id = str(workspace_id).strip() if workspace_id else ""
    if not owner_workspace_id:
        raise HTTPException(403, "An authorized workspace is required to capture a lead")
    try:
        with workspace_scope(owner_workspace_id):
            return await capture_lead_and_schedule(
                db,
                email_address=payload.email,
                consent=payload.consent,
                lead_magnet=payload.lead_magnet,
                audience=payload.audience,
                offer=payload.offer,
                consent_source=payload.consent_source,
                consent_text=payload.consent_text,
                consent_version=payload.consent_version,
                consent_purpose=payload.consent_purpose,
                resubscribe_confirmed=payload.resubscribe_confirmed,
                email_automation_id=payload.email_automation_id,
                workspace_id=owner_workspace_id,
                utm_attribution=normalize_utm_attribution({
                    name: getattr(payload, name) for name in UTM_FIELD_LIMITS
                }),
            )
    except ConsentConfirmationDeliveryUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@api.post("/leads/capture", status_code=201)
async def lead_capture(
    payload: LeadCaptureRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before capturing a lead")
    result = await create_lead(payload, db, workspace_id=str(workspace_id))
    if result.get("status") == "confirmation_delivery_failed":
        return JSONResponse(status_code=503, content=result)
    if result.get("status") in {"confirmation_pending", "confirmation_delivery_pending", "confirmation_already_pending"}:
        return JSONResponse(status_code=202, content=result)
    if int(result.get("emails_scheduled", 0) or 0) == 0:
        return JSONResponse(status_code=202, content=result)
    return result


@api.get("/leads/{lead_id}/consent-events")
async def lead_consent_events(
    lead_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Read-only, workspace-scoped history of recorded consent changes."""
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing consent history")
    with workspace_scope(workspace_id):
        lead = await db.scalar(select(Lead.id).where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
        ))
        if lead is None:
            raise HTTPException(404, "Lead not found in the active workspace")
        rows = list((await db.scalars(
            select(LeadConsentEvent)
            .where(
                LeadConsentEvent.workspace_id == workspace_id,
                LeadConsentEvent.lead_id == lead_id,
            )
            .order_by(LeadConsentEvent.observed_at.asc(), LeadConsentEvent.created_at.asc())
            .limit(250)
        )).all())
    return {
        "lead_id": lead_id,
        "count": len(rows),
        "read_only": True,
        "data": [
            {
                "id": row.id,
                "event_type": row.event_type,
                "purpose": row.purpose,
                "consent_text": row.consent_text,
                "policy_version": row.policy_version,
                "source": row.source,
                "channel": row.channel,
                "metadata": row.metadata_json or {},
                "observed_at": row.observed_at.isoformat() if row.observed_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }



@api.get("/leads/{lead_id}/email-delivery-events")
async def lead_email_delivery_events(
    lead_id: str,
    limit: int = Query(default=100, ge=1, le=250),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Return bounded, PII-minimized Resend event history for an owned lead."""
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing email delivery history")
    with workspace_scope(workspace_id):
        lead = await db.scalar(select(Lead.id).where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
        ))
        if lead is None:
            raise HTTPException(404, "Lead not found in the active workspace")
        rows = list((await db.scalars(
            select(EmailDeliveryEvent)
            .where(
                EmailDeliveryEvent.workspace_id == workspace_id,
                EmailDeliveryEvent.lead_id == lead_id,
            )
            .order_by(EmailDeliveryEvent.received_at.desc(), EmailDeliveryEvent.id.desc())
            .limit(limit)
        )).all())
    safe_metadata_fields = {"recipient_count", "bounce_type", "bounce_subtype"}
    return {
        "lead_id": lead_id,
        "count": len(rows),
        "limit": limit,
        "read_only": True,
        "data": [
            {
                "id": row.id,
                "provider": row.provider,
                "event_type": row.event_type,
                "outcome": row.outcome,
                "event_created_at": row.event_created_at.isoformat() if row.event_created_at else None,
                "received_at": row.received_at.isoformat() if row.received_at else None,
                "metadata": {
                    key: value
                    for key, value in (row.metadata_json or {}).items()
                    if key in safe_metadata_fields
                },
            }
            for row in rows
        ],
    }

@app.post("/api/public/leads/capture", status_code=201)
async def public_lead_capture(request: Request, db: AsyncSession = Depends(get_session)):
    await public_rate_limit(request)
    body = await request.body()
    if len(body) > 32 * 1024:
        raise HTTPException(413, "Lead capture request exceeds the 32 KiB size limit")
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        raw = await request.json()
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        raw = dict(form)
    else:
        raise HTTPException(415, "Submit JSON or an HTML form")
    consent = raw.get("consent")
    raw["consent"] = consent is True or str(consent or "").lower() in {"1", "true", "yes", "on"}
    try:
        payload = LeadCaptureRequest.model_validate(raw)
    except Exception as exc:
        raise HTTPException(422, "Signup form contains invalid fields") from exc
    workspace_id = verify_workspace_token(payload.workspace_token, "lead_capture")
    if not workspace_id:
        raise HTTPException(403, "A valid workspace landing token is required for public lead capture")
    with workspace_scope(workspace_id):
        result = await create_lead(payload, db, workspace_id=workspace_id)

    state = str(result.get("status") or "")
    scheduled = int(result.get("emails_scheduled", 0) or 0)
    if "application/json" in request.headers.get("accept", ""):
        if state == "confirmation_delivery_failed":
            return JSONResponse(status_code=503, content=result)
        if state in {"confirmation_pending", "confirmation_delivery_pending", "confirmation_already_pending"}:
            return JSONResponse(status_code=202, content=result)
        if scheduled == 0:
            return JSONResponse(status_code=202, content=result)
        return JSONResponse(status_code=201, content=result)

    if state == "confirmation_delivery_failed":
        title = "We couldn't send the confirmation email"
        message = "No marketing emails were queued. Please try again later or contact the workspace owner."
        status_code = 503
    elif state == "confirmation_pending":
        title = "Check your email to confirm"
        message = "We sent a confirmation link. No marketing email sequence will be sent until you confirm your address."
        status_code = 202
    elif state == "confirmation_delivery_pending":
        title = "Your confirmation is being processed"
        message = "No marketing email sequence has been queued. Please check your email shortly before submitting again."
        status_code = 202
    elif state == "confirmation_already_pending":
        title = "A confirmation is already pending"
        message = "This new signup was not queued. No second confirmation email was sent; confirm the existing request or retry this signup after five minutes."
        status_code = 202
    elif scheduled > 0:
        title = "You're on the list"
        message = "Your consent-based email sequence was queued."
        status_code = 201
    else:
        title = "Signup received"
        message = "Your signup was received, but no email sequence was queued."
        status_code = 202

    return HTMLResponse(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html_escape(title)}</title></head>"
        "<body style='font-family:system-ui;background:#f8fafc;padding:48px;color:#1e293b'>"
        f"<h1>{html_escape(title)}</h1><p>{html_escape(message)}</p></body></html>",
        status_code=status_code,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"},
    )

@app.get("/api/public/webinars/{public_id}")
async def public_webinar_page(public_id: str, db: AsyncSession = Depends(get_session)):
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,80}", public_id):
        raise HTTPException(404, "Webinar registration page not found")
    with workspace_scope(None):
        row = await db.scalar(select(WebinarEvent).where(WebinarEvent.public_id == public_id))
    if row is None or row.status != "open":
        raise HTTPException(404, "Webinar registration page not found")
    if _webinar_utc(row.start_at) <= datetime.now(timezone.utc):
        raise HTTPException(410, "Registration is closed because the webinar has started")
    if row.registration_deadline and _webinar_utc(row.registration_deadline) <= datetime.now(timezone.utc):
        raise HTTPException(410, "Webinar registration deadline has passed")
    with workspace_scope(str(row.workspace_id)):
        registered = await db.scalar(select(func.count(WebinarRegistration.id)).where(
            WebinarRegistration.workspace_id == str(row.workspace_id), WebinarRegistration.webinar_id == row.id))
    count = int(registered or 0)
    if row.capacity is not None and count >= row.capacity:
        raise HTTPException(410, "Webinar registration is full")
    return {"public_id": row.public_id, "title": row.title, "summary": row.summary,
        "description": row.description, "host_name": row.host_name, "host_bio": row.host_bio,
        "start_at": _webinar_iso(row.start_at), "end_at": _webinar_iso(row.end_at),
        "timezone_name": row.timezone_name, "registration_deadline": _webinar_iso(row.registration_deadline),
        "agenda_items": row.agenda_json or [], "privacy_policy_url": row.privacy_policy_url,
        "consent_text": row.consent_text, "affiliate_disclosure": row.affiliate_disclosure,
        "capacity": row.capacity, "registration_count": count,
        "remaining_spots": max(0, row.capacity - count) if row.capacity is not None else None,
        "registration_open": True, "external_webinar_provider": "not_configured", "confirmation_email_sent": False}


@app.post("/api/public/webinars/{public_id}/register", status_code=201)
async def public_webinar_register(public_id: str, request: Request, db: AsyncSession = Depends(get_session)):
    await public_rate_limit(request)
    body = await request.body()
    if len(body) > 16 * 1024:
        raise HTTPException(413, "Webinar registration request exceeds the 16 KiB size limit")
    if "application/json" not in request.headers.get("content-type", "").lower():
        raise HTTPException(415, "Submit a JSON webinar registration form")
    try:
        payload = WebinarRegistrationRequest.model_validate(json.loads(body))
    except Exception as exc:
        raise HTTPException(422, "Webinar registration contains invalid fields or consent") from exc
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,80}", public_id):
        raise HTTPException(404, "Webinar registration page not found")
    with workspace_scope(None):
        candidate = await db.scalar(select(WebinarEvent).where(WebinarEvent.public_id == public_id))
    if candidate is None or not candidate.workspace_id:
        raise HTTPException(404, "Webinar registration page not found")
    workspace_id = str(candidate.workspace_id)
    now = datetime.now(timezone.utc)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(WebinarEvent).where(WebinarEvent.id == candidate.id, WebinarEvent.public_id == public_id).with_for_update())
        if row is None or row.status != "open":
            raise HTTPException(404, "Webinar registration page not found")
        if _webinar_utc(row.start_at) <= now:
            raise HTTPException(410, "Registration is closed because the webinar has started")
        if row.registration_deadline and _webinar_utc(row.registration_deadline) <= now:
            raise HTTPException(410, "Webinar registration deadline has passed")
        existing = await db.scalar(select(WebinarRegistration).where(
            WebinarRegistration.workspace_id == workspace_id, WebinarRegistration.webinar_id == row.id,
            WebinarRegistration.email == payload.email))
        if existing is not None:
            return JSONResponse(
                status_code=200,
                content={"registration_id": existing.id, "status": "already_registered",
                         "confirmation_email_sent": False, "email_delivery": "not_configured"},
            )
        count = await db.scalar(select(func.count(WebinarRegistration.id)).where(
            WebinarRegistration.workspace_id == workspace_id, WebinarRegistration.webinar_id == row.id))
        if row.capacity is not None and int(count or 0) >= row.capacity:
            raise HTTPException(409, "Webinar registration capacity has been reached")
        registration = WebinarRegistration(
            workspace_id=workspace_id, webinar_id=row.id, email=payload.email, full_name=payload.full_name,
            consent_at=now, consent_text_snapshot=row.consent_text, consent_source="webinar_registration_page",
            marketing_consent=payload.marketing_consent)
        db.add(registration)
        await db.flush()
        db.add(AuditLog(workspace_id=workspace_id, actor="public_webinar_registrant",
            action="webinar.registration.created", resource_type="webinar_registration",
            resource_id=registration.id, outcome="registered",
            details_json={"webinar_id": row.id, "public_id": row.public_id, "consent_recorded": True,
                "marketing_consent": payload.marketing_consent, "email_confirmation_sent": False}))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            existing = await db.scalar(select(WebinarRegistration).where(
                WebinarRegistration.workspace_id == workspace_id, WebinarRegistration.webinar_id == row.id,
                WebinarRegistration.email == payload.email))
            if existing is not None:
                return JSONResponse(
                    status_code=200,
                    content={"registration_id": existing.id, "status": "already_registered",
                             "confirmation_email_sent": False, "email_delivery": "not_configured"},
                )
            raise HTTPException(409, "Registration could not be persisted safely")
        return {"registration_id": registration.id, "status": "registered", "consent_recorded": True,
            "marketing_consent": registration.marketing_consent, "confirmation_email_sent": False,
            "email_delivery": "not_configured", "external_webinar_provider": "not_configured"}


MAX_LEAD_EXPORT_ROWS = 10_000


def _workspace_lead_filter(workspace_id: str, search: str | None):
    """Apply the same workspace boundary and allowlisted global-search rules everywhere."""
    filters = [Lead.workspace_id == str(workspace_id)]
    search_term = (search or "").strip()
    if search_term:
        search_pattern = f"%{search_term}%"
        attribution_search = [
            Lead.metadata_json["attribution"][touch][field].as_string().ilike(search_pattern)
            for touch in ("first_touch", "last_touch")
            for field in UTM_FIELD_LIMITS
        ]
        filters.append(or_(
            Lead.email.ilike(search_pattern),
            Lead.lead_magnet.ilike(search_pattern),
            *attribution_search,
        ))
    return and_(*filters)


def _lead_csv_cell(value: Any) -> str:
    """Prevent spreadsheet formula execution in exported text cells."""
    text_value = "" if value is None else str(value)
    if text_value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text_value
    return text_value


async def _audit_lead_csv_export(
    db: AsyncSession,
    *,
    workspace_id: str,
    user: dict[str, Any],
    outcome: str,
    matching_rows: int,
    search_supplied: bool,
) -> None:
    """Audit export attempts without persisting searched PII or the search term."""
    with workspace_scope(workspace_id):
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or user.get("user_id") or "unknown")[:320],
            action="leads.export_csv",
            resource_type="lead_export",
            outcome=outcome[:80],
            details_json={
                "format": "csv",
                "matching_rows": matching_rows,
                "row_limit": MAX_LEAD_EXPORT_ROWS,
                "search_supplied": bool(search_supplied),
                "search_value_recorded": False,
                "lead_values_recorded": False,
            },
        ))
        await db.commit()


@api.get("/leads/export.csv")
async def export_leads_csv(
    search: str | None = Query(default=None, max_length=120),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before exporting leads")
    lead_filter = _workspace_lead_filter(workspace_id, search)
    total_count = int(await db.scalar(
        select(func.count(Lead.id)).where(lead_filter)
    ) or 0)
    if total_count > MAX_LEAD_EXPORT_ROWS:
        await _audit_lead_csv_export(
            db, workspace_id=workspace_id, user=user, outcome="rejected_row_limit",
            matching_rows=total_count, search_supplied=bool((search or "").strip()),
        )
        raise HTTPException(
            413,
            f"Export matches {total_count} leads; the CSV safety limit is {MAX_LEAD_EXPORT_ROWS}. Narrow the global search and retry.",
        )

    rows = list((await db.scalars(
        select(Lead).where(lead_filter)
        .order_by(Lead.created_at.desc(), Lead.id.asc())
        .limit(MAX_LEAD_EXPORT_ROWS + 1)
    )).all())
    if len(rows) > MAX_LEAD_EXPORT_ROWS:
        await _audit_lead_csv_export(
            db, workspace_id=workspace_id, user=user, outcome="rejected_row_limit",
            matching_rows=len(rows), search_supplied=bool((search or "").strip()),
        )
        raise HTTPException(
            413,
            f"Export exceeds the CSV safety limit of {MAX_LEAD_EXPORT_ROWS} leads. Narrow the global search and retry.",
        )

    first_fields = [f"first_touch_{field}" for field in UTM_FIELD_LIMITS]
    last_fields = [f"last_touch_{field}" for field in UTM_FIELD_LIMITS]
    columns = [
        "lead_id", "email", "lead_magnet", "consented_at",
        "email_consent_confirmed_at", "consent_source", "unsubscribed", "purchased",
        *first_fields, *last_fields, "last_touch_at",
    ]
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(columns)
    for row in rows:
        attribution = lead_attribution_summary(row.metadata_json)
        first_touch = attribution.get("first_touch")
        last_touch = attribution.get("last_touch")
        first_touch = first_touch if isinstance(first_touch, dict) else {}
        last_touch = last_touch if isinstance(last_touch, dict) else {}
        values = [
            row.id,
            row.email,
            row.lead_magnet,
            row.consent_at.isoformat() if row.consent_at else "",
            row.email_consent_confirmed_at.isoformat() if row.email_consent_confirmed_at else "",
            row.consent_source,
            str(row.unsubscribed_at is not None).lower(),
            str(row.purchased_at is not None).lower(),
            *[first_touch.get(field, "") for field in UTM_FIELD_LIMITS],
            *[last_touch.get(field, "") for field in UTM_FIELD_LIMITS],
            attribution.get("last_touch_at") or "",
        ]
        writer.writerow([_lead_csv_cell(value) for value in values])

    await _audit_lead_csv_export(
        db, workspace_id=workspace_id, user=user, outcome="completed",
        matching_rows=len(rows), search_supplied=bool((search or "").strip()),
    )
    file_date = utcnow().date().isoformat()
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="omni-affiliate-leads-{file_date}.csv"',
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


MAX_LEAD_DATA_EXPORT_ITEMS = 1_000


async def _audit_lead_data_export(
    db: AsyncSession,
    *,
    workspace_id: str,
    lead_id: str,
    user: dict[str, Any],
    outcome: str,
    collection_counts: dict[str, int],
    rejected_collections: list[str] | None = None,
) -> None:
    """Record an export attempt without copying email, consent text or export values into the audit log."""
    opaque_resource_id = hashlib.sha256(
        f"{workspace_id}:{lead_id}".encode("utf-8")
    ).hexdigest()[:32]
    with workspace_scope(workspace_id):
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or user.get("user_id") or "unknown")[:320],
            action="leads.export_data_json",
            resource_type="lead_data_export",
            resource_id=opaque_resource_id,
            outcome=outcome[:80],
            details_json={
                "format": "json",
                "collection_limit": MAX_LEAD_DATA_EXPORT_ITEMS,
                "collection_counts": collection_counts,
                "rejected_collections": sorted(rejected_collections or []),
                "lead_id_recorded": False,
                "lead_email_recorded": False,
                "export_values_recorded": False,
            },
        ))
        await db.commit()


@api.get("/leads/{lead_id}/data-export.json")
async def export_lead_data_json(
    lead_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Download a workspace-scoped copy of one lead record and its consent/email activity."""
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before exporting lead data")

    with workspace_scope(workspace_id):
        lead = await db.scalar(select(Lead).where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
        ))
        if lead is None:
            raise HTTPException(404, "Lead not found in the active workspace")

        consent_events = list((await db.scalars(
            select(LeadConsentEvent).where(
                LeadConsentEvent.workspace_id == workspace_id,
                LeadConsentEvent.lead_id == lead_id,
            ).order_by(
                LeadConsentEvent.observed_at.asc(),
                LeadConsentEvent.created_at.asc(),
            ).limit(MAX_LEAD_DATA_EXPORT_ITEMS + 1)
        )).all())
        delivery_events = list((await db.scalars(
            select(EmailDeliveryEvent).where(
                EmailDeliveryEvent.workspace_id == workspace_id,
                EmailDeliveryEvent.lead_id == lead_id,
            ).order_by(
                EmailDeliveryEvent.received_at.asc(),
                EmailDeliveryEvent.id.asc(),
            ).limit(MAX_LEAD_DATA_EXPORT_ITEMS + 1)
        )).all())
        scheduled_emails = list((await db.scalars(
            select(ScheduledEmail).where(
                ScheduledEmail.workspace_id == workspace_id,
                ScheduledEmail.lead_id == lead_id,
            ).order_by(
                ScheduledEmail.created_at.asc(),
                ScheduledEmail.sequence_day.asc(),
            ).limit(MAX_LEAD_DATA_EXPORT_ITEMS + 1)
        )).all())
        confirmations = list((await db.scalars(
            select(EmailConsentConfirmation).where(
                EmailConsentConfirmation.workspace_id == workspace_id,
                EmailConsentConfirmation.lead_id == lead_id,
            ).order_by(
                EmailConsentConfirmation.created_at.asc(),
            ).limit(MAX_LEAD_DATA_EXPORT_ITEMS + 1)
        )).all())

    related = {
        "consent_events": consent_events,
        "email_delivery_events": delivery_events,
        "scheduled_email_activity": scheduled_emails,
        "email_consent_confirmations": confirmations,
    }
    collection_counts = {name: len(rows) for name, rows in related.items()}
    rejected = [
        name for name, rows in related.items()
        if len(rows) > MAX_LEAD_DATA_EXPORT_ITEMS
    ]
    if rejected:
        await _audit_lead_data_export(
            db,
            workspace_id=workspace_id,
            lead_id=lead_id,
            user=user,
            outcome="rejected_row_limit",
            collection_counts=collection_counts,
            rejected_collections=rejected,
        )
        raise HTTPException(
            413,
            "Lead data export exceeds the safety limit in one or more collections; no partial export was created.",
        )

    generated_at = datetime.now(timezone.utc)
    package = {
        "format": "omni-affiliate-lead-data",
        "format_version": "1.0",
        "generated_at": generated_at.isoformat(),
        "scope_note": "This package contains the stored lead record and associated consent, delivery-event and email-scheduling metadata. It excludes email bodies, provider tokens, raw webhook payloads and payload checksums.",
        "lead": {
            "id": lead.id,
            "email": lead.email,
            "lead_magnet": lead.lead_magnet,
            "consent_at": lead.consent_at.isoformat() if lead.consent_at else None,
            "email_consent_confirmed_at": lead.email_consent_confirmed_at.isoformat() if lead.email_consent_confirmed_at else None,
            "consent_source": lead.consent_source,
            "unsubscribed_at": lead.unsubscribed_at.isoformat() if lead.unsubscribed_at else None,
            "email_suppressed_at": lead.email_suppressed_at.isoformat() if lead.email_suppressed_at else None,
            "email_suppression_reason": lead.email_suppression_reason,
            "purchased_at": lead.purchased_at.isoformat() if lead.purchased_at else None,
            "engaged": bool(lead.engaged),
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "metadata": lead.metadata_json or {},
        },
        "consent_events": [
            {
                "id": row.id,
                "event_type": row.event_type,
                "purpose": row.purpose,
                "consent_text": row.consent_text,
                "policy_version": row.policy_version,
                "source": row.source,
                "channel": row.channel,
                "metadata": row.metadata_json or {},
                "observed_at": row.observed_at.isoformat() if row.observed_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in consent_events
        ],
        "email_delivery_events": [
            {
                "id": row.id,
                "provider": row.provider,
                "provider_event_id": row.provider_event_id,
                "provider_message_id": row.provider_message_id,
                "event_type": row.event_type,
                "outcome": row.outcome,
                "event_created_at": row.event_created_at.isoformat() if row.event_created_at else None,
                "received_at": row.received_at.isoformat() if row.received_at else None,
                "metadata": row.metadata_json or {},
            }
            for row in delivery_events
        ],
        "scheduled_email_activity": [
            {
                "id": row.id,
                "sequence_day": row.sequence_day,
                "send_at": row.send_at.isoformat() if row.send_at else None,
                "status": row.status,
                "attempts": row.attempts,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in scheduled_emails
        ],
        "email_consent_confirmations": [
            {
                "id": row.id,
                "status": row.status,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "sent_at": row.sent_at.isoformat() if row.sent_at else None,
                "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
                "superseded_at": row.superseded_at.isoformat() if row.superseded_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in confirmations
        ],
    }
    await _audit_lead_data_export(
        db,
        workspace_id=workspace_id,
        lead_id=lead_id,
        user=user,
        outcome="completed",
        collection_counts=collection_counts,
    )
    return Response(
        content=json.dumps(package, ensure_ascii=False, separators=(",", ":")),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="omni-affiliate-lead-data-{generated_at.date().isoformat()}.json"',
            "Cache-Control": "no-store, private",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@api.get("/leads")
async def leads(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100000),
    search: str | None = Query(default=None, max_length=120),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing leads")
    lead_filter = _workspace_lead_filter(str(workspace_id), search)
    total_count = int(await db.scalar(
        select(func.count(Lead.id)).where(lead_filter)
    ) or 0)
    rows = list((await db.scalars(
        select(Lead).where(lead_filter)
        .order_by(Lead.created_at.desc(), Lead.id.asc())
        .limit(limit)
        .offset(offset)
    )).all())
    return {
        "count": len(rows),
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "data": [
            {"id": x.id, "email": x.email, "lead_magnet": x.lead_magnet,
             "consented_at": x.consent_at.isoformat(),
             "email_consent_confirmed_at": x.email_consent_confirmed_at.isoformat() if x.email_consent_confirmed_at else None,
             "consent_source": x.consent_source,
             "email_suppressed_at": x.email_suppressed_at.isoformat() if x.email_suppressed_at else None,
             "email_suppression_reason": x.email_suppression_reason,
             "unsubscribed": x.unsubscribed_at is not None,
             "purchased": x.purchased_at is not None,
             "attribution": lead_attribution_summary(x.metadata_json)}
            for x in rows
        ],
    }




def _email_automation_dict(row: ContentAsset, *, include_graph: bool = True) -> dict[str, Any]:
    metadata = dict(row.metadata_json or {})
    result = {
        "id": row.id,
        "name": str(metadata.get("name") or row.title),
        "description": str(metadata.get("description") or ""),
        "version": str(metadata.get("version") or ""),
        "status": row.status,
        "entry_step_id": str(metadata.get("entry_step_id") or ""),
        "target_jurisdictions": list(metadata.get("target_jurisdictions") or []),
        "node_count": int(metadata.get("node_count") or 0),
        "validation_report": dict(metadata.get("validation_report") or {}),
        "graph_sha256": str(metadata.get("graph_sha256") or ""),
        "created_by": metadata.get("created_by"),
        "reviewed_by": metadata.get("reviewed_by"),
        "reviewed_at": metadata.get("reviewed_at"),
        "reviewer_notes": metadata.get("reviewer_notes"),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "execution_boundary": "Branching graph is persisted and can be simulated; no email is queued or sent by these routes. Existing consent/unsubscribe controls remain separate.",
    }
    if include_graph:
        try:
            result["graph"] = json.loads(row.body)
        except (json.JSONDecodeError, TypeError):
            result["graph"] = None
    return result


@api.get("/email/automations")
async def list_email_automations(
    limit: int = Query(default=100, ge=1, le=200),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing email automations")
    with workspace_scope(workspace_id):
        rows = list((await db.scalars(
            select(ContentAsset).where(
                ContentAsset.workspace_id == workspace_id,
                ContentAsset.asset_type == "email_automation",
            ).order_by(ContentAsset.created_at.desc()).limit(limit)
        )).all())
    return {"count": len(rows), "data": [_email_automation_dict(row, include_graph=False) for row in rows]}


@api.post("/email/automations", status_code=201)
async def create_email_automation(
    payload: EmailAutomationCreateRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating email automations")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    try:
        built = build_email_automation(payload.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(422, {"code": "EMAIL_AUTOMATION_GRAPH_INVALID", "message": str(exc)}) from exc
    with workspace_scope(workspace_id):
        existing = list((await db.scalars(select(ContentAsset).where(
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "email_automation",
        ).limit(200))).all())
        if any(
            str((item.metadata_json or {}).get("name") or "").casefold() == payload.name.casefold()
            and str((item.metadata_json or {}).get("version") or "") == payload.version
            for item in existing
        ):
            raise HTTPException(409, "This email automation name and version already exists in the active workspace")
        metadata = {
            "schema_version": 1,
            "name": built["graph"]["name"],
            "description": built["graph"]["description"],
            "version": built["graph"]["version"],
            "entry_step_id": built["graph"]["entry_step_id"],
            "target_jurisdictions": list(built["graph"].get("target_jurisdictions") or []),
            "node_count": len(built["graph"]["nodes"]),
            "graph_sha256": built["sha256"],
            "validation_report": built["validation_report"],
            "review_required": True,
            "created_by": actor,
            "reviewed_by": None,
            "reviewed_at": None,
            "reviewer_notes": None,
            "execution_mode": "simulation_only",
        }
        row = ContentAsset(
            workspace_id=workspace_id,
            asset_type="email_automation",
            title=built["graph"]["name"],
            body=json.dumps(built["graph"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            status="review_required",
            source_urls=[],
            metadata_json=metadata,
        )
        db.add(row)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id, actor=actor,
            action="email_automation.created", resource_type="content_asset",
            resource_id=row.id, outcome="review_required",
            details_json={
                "version": built["graph"]["version"],
                "graph_sha256": built["sha256"],
                "node_count": metadata["node_count"],
                "side_effects_performed": False,
            },
        ))
        await db.commit()
        await db.refresh(row)
    return _email_automation_dict(row)


async def _get_workspace_email_automation(db: AsyncSession, workspace_id: str, automation_id: str) -> ContentAsset:
    with workspace_scope(workspace_id):
        row = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == automation_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "email_automation",
        ))
    if row is None:
        raise HTTPException(404, "Email automation not found in the active workspace")
    return row


@api.get("/email/automations/{automation_id}")
async def get_email_automation(
    automation_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing email automations")
    return _email_automation_dict(await _get_workspace_email_automation(db, workspace_id, automation_id))


@api.post("/email/automations/{automation_id}/simulate")
async def simulate_saved_email_automation(
    automation_id: str,
    payload: EmailAutomationSimulationRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before simulating email automations")
    row = await _get_workspace_email_automation(db, workspace_id, automation_id)
    try:
        graph = json.loads(row.body)
        result = simulate_email_automation(graph, **payload.model_dump())
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(409, "Stored graph is invalid; create a new version before simulation") from exc
    return {
        "automation_id": row.id,
        "automation_status": row.status,
        "simulation": result,
        "provider_calls_made": 0,
        "messages_scheduled": 0,
        "messages_sent": 0,
    }


@api.post("/email/automations/{automation_id}/review")
async def review_email_automation(
    automation_id: str,
    payload: EmailAutomationReviewRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing email automations")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    row = await _get_workspace_email_automation(db, workspace_id, automation_id)
    metadata = dict(row.metadata_json or {})
    if row.status in {"approved", "rejected"}:
        raise HTTPException(409, "Reviewed automation versions are immutable; create a new version to change the graph")
    try:
        graph = json.loads(row.body)
        built = build_email_automation(graph)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(409, "Stored graph is invalid; create a new version before review") from exc
    if payload.decision == "approve":
        if not built["graph"].get("target_jurisdictions"):
            raise HTTPException(409, "Set at least one target jurisdiction before approving an automation for possible delivery")
        if payload.confirm_graph_reviewed is not True:
            raise HTTPException(409, "Approval requires confirm_graph_reviewed=true after reviewing every branch and message")
        if built["sha256"] != metadata.get("graph_sha256"):
            raise HTTPException(409, "Graph checksum changed; create a new version before approval")
        row.status = "approved"
        outcome = "human_review_approved"
    else:
        row.status = "rejected"
        outcome = "human_review_rejected"
    now = utcnow()
    metadata["reviewed_by"] = actor
    metadata["reviewed_at"] = now.isoformat()
    metadata["reviewer_notes"] = payload.reviewer_notes or None
    metadata["review_required"] = False
    metadata["validation_report"] = built["validation_report"]
    row.metadata_json = metadata
    db.add(AuditLog(
        workspace_id=workspace_id, actor=actor,
        action="email_automation.reviewed", resource_type="content_asset",
        resource_id=row.id, outcome=outcome,
        details_json={
            "version": metadata.get("version"),
            "graph_sha256": metadata.get("graph_sha256"),
            "side_effects_performed": False,
            "runtime_activated": False,
        },
    ))
    await db.commit()
    await db.refresh(row)
    return _email_automation_dict(row)


@api.get("/email/queue")
async def email_queue(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing the email queue")
    rows = list((await db.scalars(
        select(ScheduledEmail).where(ScheduledEmail.workspace_id == str(workspace_id))
        .order_by(ScheduledEmail.send_at.desc()).limit(250)
    )).all())
    return {"count": len(rows), "data": [
        {"id": x.id, "lead_id": x.lead_id, "day": x.sequence_day, "subject": x.subject,
         "send_at": x.send_at.isoformat(), "status": x.status, "attempts": x.attempts,
         "last_error": x.last_error}
        for x in rows
    ]}


@api.post("/email/worker/run", dependencies=[Depends(require_admin)])
async def email_worker(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before running the email worker")
    return await send_due_emails(db, workspace_id=str(workspace_id))
@api.post("/analytics/conversions")
async def conversion_create(
    payload: ConversionRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before recording a conversion")
    network = payload.network.strip().lower()
    owner_workspace_id = str(workspace_id)
    with workspace_scope(owner_workspace_id):
        existing = await db.scalar(
            select(Conversion.id).where(
                Conversion.workspace_id == owner_workspace_id,
                Conversion.network == network,
                Conversion.external_event_id == payload.external_event_id,
            )
        )
        if existing:
            return {"status": "duplicate_ignored", "id": existing}
        utm = conversion_tracker(payload.url or "")
        click_id = payload.click_id or utm["click_id"]
        row = Conversion(
            workspace_id=owner_workspace_id, network=network,
            external_event_id=payload.external_event_id, click_id=click_id,
            utm_source=payload.utm_source or utm["utm_source"],
            utm_medium=payload.utm_medium or utm["utm_medium"],
            utm_campaign=payload.utm_campaign or utm["utm_campaign"],
            utm_content=payload.utm_content or utm["utm_content"],
            hook=payload.hook or payload.utm_content or utm["utm_content"],
            revenue=float(payload.revenue), commission=float(payload.commission),
            currency=payload.currency.upper(), status=payload.status.lower(),
            event_json=payload.event_json,
        )
        ledger_row = ConversionLedgerEntry(
            workspace_id=owner_workspace_id, network=network,
            external_event_id=payload.external_event_id, click_id=click_id,
            entry_type="conversion", commission_amount=payload.commission,
            revenue_amount=payload.revenue, currency=payload.currency.upper(),
            status=payload.status.lower(), evidence_status="api_submitted_unverified",
            source_event_json=payload.event_json, observed_at=utcnow(),
        )
        db.add(row)
        db.add(ledger_row)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            existing = await db.scalar(
                select(Conversion.id).where(
                    Conversion.workspace_id == owner_workspace_id,
                    Conversion.network == network,
                    Conversion.external_event_id == payload.external_event_id,
                )
            )
            if existing:
                return {"status": "duplicate_ignored", "id": existing}
            raise HTTPException(409, "Conversion could not be persisted idempotently")
        return {"status": "recorded", "id": row.id, "utm": utm}
@api.post("/analytics/track")
async def track(payload: dict[str, Any]):
    raw = payload.get("url") or payload.get("query")
    if not isinstance(raw, str) or not raw.strip():
        raise HTTPException(422, "url or query must be a non-empty string")
    if len(raw) > 8192:
        raise HTTPException(413, "Tracking input exceeds the supported length")
    return conversion_tracker(raw)
@api.post("/analytics/ab-test")
async def ab_test(
    payload: ABTestAssignmentRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Persist one stable visitor assignment and analyze only recorded events."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before assigning an experiment variant")
    workspace_id = str(workspace_id)

    try:
        proposed = ab_test_generator(
            payload.headline_a,
            payload.headline_b,
            visitor_id=payload.visitor_id,
            experiment_key=payload.experiment_key,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    assignment_query = select(ExperimentAssignment).where(
        ExperimentAssignment.workspace_id == workspace_id,
        ExperimentAssignment.experiment_key == payload.experiment_key,
        ExperimentAssignment.visitor_id == payload.visitor_id,
    )
    assignment = await db.scalar(assignment_query)
    if assignment and (
        assignment.headline_a != payload.headline_a or assignment.headline_b != payload.headline_b
    ):
        raise HTTPException(409, "This experiment key is already bound to different headlines; use a new key")

    if assignment is None:
        assignment = ExperimentAssignment(
            workspace_id=workspace_id,
            experiment_key=payload.experiment_key,
            visitor_id=payload.visitor_id,
            variant=proposed["variant"],
            headline_a=payload.headline_a,
            headline_b=payload.headline_b,
            assigned_headline=proposed["headline"],
        )
        db.add(assignment)
        from sqlalchemy.exc import IntegrityError
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            assignment = await db.scalar(assignment_query)
            if assignment is None:
                raise HTTPException(409, "Could not safely persist experiment assignment")

    assignment_id = assignment.id
    event_totals = await db.execute(
        select(
            ExperimentAssignment.variant,
            ExperimentEvent.event_type,
            func.count(ExperimentEvent.id),
        )
        .join(ExperimentEvent, ExperimentEvent.assignment_id == ExperimentAssignment.id)
        .where(
            ExperimentAssignment.workspace_id == workspace_id,
            ExperimentAssignment.experiment_key == payload.experiment_key,
            ExperimentEvent.workspace_id == workspace_id,
        )
        .group_by(ExperimentAssignment.variant, ExperimentEvent.event_type)
    )
    totals = {
        "A": {"impressions": 0, "conversions": 0},
        "B": {"impressions": 0, "conversions": 0},
    }
    for variant, event_type, count in event_totals.all():
        if variant in totals and event_type in {"impression", "conversion"}:
            totals[variant]["impressions" if event_type == "impression" else "conversions"] = int(count)

    result = ab_test_generator(
        payload.headline_a,
        payload.headline_b,
        visitor_id=payload.visitor_id,
        experiment_key=payload.experiment_key,
        conversions_a=totals["A"]["conversions"],
        impressions_a=totals["A"]["impressions"],
        conversions_b=totals["B"]["conversions"],
        impressions_b=totals["B"]["impressions"],
    )
    result.update({
        "assignment_id": assignment_id,
        "variant": assignment.variant,
        "headline": assignment.assigned_headline,
        "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
        "counts_source": "persisted_experiment_events",
        "event_ingest_path": "/api/analytics/ab-test/event",
    })
    return result


@api.post("/analytics/ab-test/event")
async def record_ab_test_event(
    payload: ExperimentEventRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Record an idempotent impression/conversion event for a persisted assignment."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before recording experiment events")
    workspace_id = str(workspace_id)

    assignment = await db.scalar(
        select(ExperimentAssignment).where(
            ExperimentAssignment.workspace_id == workspace_id,
            ExperimentAssignment.experiment_key == payload.experiment_key,
            ExperimentAssignment.visitor_id == payload.visitor_id,
        )
    )
    if assignment is None:
        raise HTTPException(404, "Experiment assignment not found in the active workspace")

    assignment_id = assignment.id
    existing_query = select(ExperimentEvent).where(
        ExperimentEvent.workspace_id == workspace_id,
        ExperimentEvent.event_id == payload.event_id,
    )
    existing = await db.scalar(existing_query)
    if existing:
        if existing.assignment_id == assignment_id and existing.event_type == payload.event_type:
            return {"id": existing.id, "duplicate": True, "event_type": existing.event_type}
        raise HTTPException(409, "Event ID was already used for a different experiment event")

    event = ExperimentEvent(
        workspace_id=workspace_id,
        assignment_id=assignment_id,
        event_id=payload.event_id,
        event_type=payload.event_type,
    )
    db.add(event)
    from sqlalchemy.exc import IntegrityError
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(existing_query)
        if existing and existing.assignment_id == assignment_id and existing.event_type == payload.event_type:
            return {"id": existing.id, "duplicate": True, "event_type": existing.event_type}
        raise HTTPException(409, "Experiment event could not be persisted idempotently")
    return {
        "id": event.id,
        "duplicate": False,
        "event_type": event.event_type,
        "assignment_id": assignment_id,
        "experiment_key": payload.experiment_key,
        "variant": assignment.variant,
    }
@api.post("/analytics/self-improve")
async def learn(
    lookback_days: int = Query(30, ge=1, le=180),
    user: dict[str, Any] = Depends(require_auth),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before running performance learning")
    return await self_improver_loop(lookback_days=lookback_days, workspace_id=str(workspace_id))


@api.get("/resource-budget")
async def resource_budget(user: dict[str, Any] = Depends(require_auth)):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing resource usage")
    return await budget_status(workspace_id=str(workspace_id))
@api.get("/campaigns")
async def campaigns(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing campaigns")
    with workspace_scope(str(workspace_id)):
        rows = list((await db.scalars(
            select(Campaign)
            .where(Campaign.workspace_id == str(workspace_id))
            .order_by(Campaign.created_at.desc())
            .limit(200)
        )).all())
    return {
        "count": len(rows),
        "data": [
            {
                "id": row.id, "name": row.name, "niche": row.niche,
                "tracking_parameter": row.tracking_parameter,
                "tracking_url": f"{settings.app_public_url.rstrip('/')}/r/{row.id}",
                "primary_destination": row.primary_destination,
                "fallback_destination": row.fallback_destination,
                "is_active": row.is_active, "primary_healthy": row.primary_healthy,
                "fallback_healthy": row.fallback_healthy, "health_last_error": row.health_last_error,
            }
            for row in rows
        ],
    }


@api.post("/campaigns", status_code=201)
async def campaign_create(
    payload: CampaignCreateRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating a campaign")
    try:
        await validate_public_http_url(payload.primary_destination)
        if payload.fallback_destination:
            await validate_public_http_url(payload.fallback_destination)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with workspace_scope(str(workspace_id)):
        row = Campaign(
            workspace_id=str(workspace_id), name=payload.name, niche=payload.niche,
            primary_destination=payload.primary_destination, fallback_destination=payload.fallback_destination,
            tracking_parameter=payload.tracking_parameter, disclosure_text=payload.disclosure_text,
            auto_publish=payload.auto_publish, max_daily_spend=payload.max_daily_spend,
        )
        db.add(row)
        await db.commit()
        return {
            "id": row.id, "name": row.name, "tracking_parameter": row.tracking_parameter,
            "tracking_url": f"{settings.app_public_url.rstrip('/')}/r/{row.id}",
            "status": "created",
        }


@api.post("/campaigns/{campaign_id}/health")
async def campaign_health(
    campaign_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before checking campaign health")
    with workspace_scope(str(workspace_id)):
        row = await db.get(Campaign, campaign_id)
        if not row or row.workspace_id != str(workspace_id):
            raise HTTPException(404, "Campaign not found")
        out = await choose_destination(row)
        row.primary_healthy = out.get("primary_healthy")
        row.fallback_healthy = out.get("fallback_healthy")
        row.health_last_checked_at = utcnow()
        row.health_last_error = str(out.get("health_error") or "")[:1000] or None
        await db.commit()
        return {
            "campaign_id": row.id, **out,
            "note": "Fallback applies to this click; campaign configuration is unchanged.",
        }


@api.get("/finance/ledger")
async def ledger(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing the commission ledger")

    # The detail feed is bounded, but aggregate totals cover every conversion in
    # the active workspace. Never add different currencies into one misleading sum.
    workspace_filter = Conversion.workspace_id == str(workspace_id)
    rows = list((await db.scalars(
        select(Conversion)
        .where(workspace_filter)
        .order_by(Conversion.created_at.desc())
        .limit(500)
    )).all())
    aggregate_result = await db.execute(
        select(
            Conversion.currency,
            func.coalesce(func.sum(Conversion.commission), 0.0),
        )
        .where(workspace_filter)
        .group_by(Conversion.currency)
    )
    totals_by_currency = {
        str(currency or "USD").strip().upper(): round(float(total or 0), 2)
        for currency, total in aggregate_result.all()
    }
    return {
        "count": len(rows),
        # Backwards-compatible field explicitly defined as USD; use totals_by_currency
        # for any other currency and for a full multi-currency view.
        "total_commission_recorded": totals_by_currency.get("USD", 0.0),
        "total_commission_recorded_currency": "USD",
        "totals_by_currency": totals_by_currency,
        "data": [{
            "id": x.id,
            "network": x.network,
            "external_event_id": x.external_event_id,
            "commission": x.commission,
            "revenue": x.revenue,
            "currency": x.currency,
            "status": x.status,
            "utm_campaign": x.utm_campaign,
            "created_at": x.created_at.isoformat() if x.created_at else None,
        } for x in rows],
    }
@api.get("/finance/conversion-ledger")
async def conversion_ledger(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Return immutable decimal observations with currency and evidence kept separate."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing the conversion ledger")

    workspace_filter = ConversionLedgerEntry.workspace_id == str(workspace_id)
    rows = list((await db.scalars(
        select(ConversionLedgerEntry)
        .where(workspace_filter)
        .order_by(ConversionLedgerEntry.created_at.desc())
        .limit(500)
    )).all())
    grouped = await db.execute(
        select(
            ConversionLedgerEntry.currency,
            ConversionLedgerEntry.evidence_status,
            func.count(ConversionLedgerEntry.id),
            func.coalesce(func.sum(ConversionLedgerEntry.commission_amount), 0),
            func.coalesce(func.sum(ConversionLedgerEntry.revenue_amount), 0),
        )
        .where(workspace_filter)
        .group_by(ConversionLedgerEntry.currency, ConversionLedgerEntry.evidence_status)
        .order_by(ConversionLedgerEntry.currency, ConversionLedgerEntry.evidence_status)
    )

    def money_text(value: Any) -> str:
        return format(Decimal(str(value or 0)), ".6f")

    totals = [
        {
            "currency": str(currency).strip().upper(),
            "evidence_status": str(evidence_status),
            "entry_count": int(entry_count),
            "commission_total": money_text(commission_total),
            "revenue_total": money_text(revenue_total),
        }
        for currency, evidence_status, entry_count, commission_total, revenue_total in grouped.all()
    ]
    return {
        "returned_count": len(rows),
        "total_entry_count": sum(item["entry_count"] for item in totals),
        "limit": 500,
        "read_only": True,
        "totals_by_currency_and_evidence": totals,
        "data": [
            {
                "id": entry.id,
                "network": entry.network,
                "external_event_id": entry.external_event_id,
                "click_id": entry.click_id,
                "entry_type": entry.entry_type,
                "original_event_id": entry.original_event_id,
                "commission_amount": money_text(entry.commission_amount),
                "revenue_amount": money_text(entry.revenue_amount),
                "currency": entry.currency,
                "status": entry.status,
                "evidence_status": entry.evidence_status,
                "observed_at": entry.observed_at.isoformat() if entry.observed_at else None,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            }
            for entry in rows
        ],
    }


@api.patch("/finance/mail-commissions/{evidence_id}/review", dependencies=[Depends(require_admin)])
async def review_commission_evidence(
    evidence_id: str,
    payload: CommissionEvidenceReviewRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Record a human review decision; never mark a payout as received."""
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing commission evidence")

    evidence = await db.scalar(
        select(MailCommission).where(
            MailCommission.id == evidence_id,
            MailCommission.workspace_id == str(workspace_id),
        )
    )
    if evidence is None:
        raise HTTPException(404, "Commission evidence not found in the active workspace")
    if evidence.status not in {"pending_verification", "needs_review"}:
        raise HTTPException(409, "Commission evidence has already been reviewed")

    candidate_id = payload.candidate_conversion_id
    if payload.decision == "matched_to_conversion":
        if not candidate_id:
            raise HTTPException(422, "Choose a candidate conversion before accepting a match")
        conversion = await db.scalar(
            select(Conversion).where(
                Conversion.id == candidate_id,
                Conversion.workspace_id == str(workspace_id),
            )
        )
        if conversion is None:
            raise HTTPException(404, "Candidate conversion not found in the active workspace")
        from backend.services.commission_reconciliation import build_commission_reconciliation

        candidate_report = build_commission_reconciliation(
            [{
                "id": evidence.id,
                "network": evidence.network,
                "commission": evidence.commission,
                "currency": evidence.currency,
                "status": "pending_verification",
            }],
            [{
                "id": conversion.id,
                "network": conversion.network,
                "commission": conversion.commission,
                "currency": conversion.currency,
                "status": conversion.status,
            }],
        )
        if candidate_report["data"][0]["reconciliation_status"] != "possible_match":
            raise HTTPException(422, "Selected conversion does not match network, currency and amount, or is reversed")
    elif candidate_id:
        raise HTTPException(422, "A candidate conversion is only valid when accepting a match")

    now = utcnow()
    evidence.status = payload.decision
    evidence.evidence_json = {
        **dict(evidence.evidence_json or {}),
        "operator_review": {
            "decision": payload.decision,
            "candidate_conversion_id": candidate_id,
            "reviewed_by": str(user.get("email") or "unknown"),
            "reviewed_at": now.isoformat(),
            "note": payload.note.strip(),
            "payout_confirmed": False,
        },
    }
    db.add(AuditLog(
        workspace_id=str(workspace_id),
        actor=str(user.get("email") or "unknown"),
        action="finance.commission_evidence.reviewed",
        resource_type="mail_commission",
        resource_id=evidence.id,
        outcome=payload.decision,
        details_json={
            "candidate_conversion_id": candidate_id,
            "payout_confirmed": False,
            "note": payload.note.strip(),
        },
    ))
    await db.commit()
    return {
        "id": evidence.id,
        "status": evidence.status,
        "decision": payload.decision,
        "candidate_conversion_id": candidate_id,
        "reviewed_by": str(user.get("email") or "unknown"),
        "reviewed_at": now.isoformat(),
        "payout_confirmed": False,
        "transfers_initiated": False,
    }


@api.get("/finance/thresholds")
async def thresholds(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing payout thresholds")
    rows = list((await db.scalars(
        select(PayoutThreshold)
        .where(PayoutThreshold.workspace_id == str(workspace_id))
        .order_by(PayoutThreshold.network)
    )).all())
    return {"count": len(rows), "data": [
        {"id": x.id, "network": x.network, "currency": x.currency,
         "minimum_threshold": x.minimum_threshold, "reported_balance": x.reported_balance,
         "threshold_reached": x.threshold_reached,
         "threshold_reached_at": x.threshold_reached_at.isoformat() if x.threshold_reached_at else None,
         "funds_received_at": x.funds_received_at.isoformat() if x.funds_received_at else None,
         "note": x.reconciliation_note}
        for x in rows
    ]}


@api.post("/finance/thresholds", dependencies=[Depends(require_admin)], status_code=201)
async def threshold_create(
    p: PayoutThresholdCreateRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating payout thresholds")
    row = PayoutThreshold(
        workspace_id=str(workspace_id),
        network=p.network,
        currency=p.currency,
        minimum_threshold=p.minimum_threshold,
        reported_balance=p.reported_balance,
        reconciliation_note=p.reconciliation_note,
    )
    row.threshold_reached = row.reported_balance >= row.minimum_threshold
    row.threshold_reached_at = utcnow() if row.threshold_reached else None
    db.add(row)
    await db.commit()
    return {"id": row.id, "threshold_reached": row.threshold_reached, "note": "Tracking only; no payout is initiated."}


@api.post("/finance/thresholds/{threshold_id}/funds-received", dependencies=[Depends(require_admin)])
async def funds_received(
    threshold_id: str,
    p: FundsReceivedRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before updating a payout threshold")
    row = await db.scalar(
        select(PayoutThreshold).where(
            PayoutThreshold.id == threshold_id,
            PayoutThreshold.workspace_id == str(workspace_id),
        )
    )
    if not row:
        raise HTTPException(404, "Threshold not found")
    row.funds_received_at = p.funds_received_at
    row.reconciliation_note = p.reconciliation_note[:4000]
    await db.commit()
    return {"id": row.id, "funds_received_at": row.funds_received_at.isoformat(), "transfers_initiated": False}
@api.post("/ads/plan", status_code=201)
async def ads_plan(
    payload: AdCampaignPlanRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before creating an ad plan")
    workspace_id = str(user["workspace_id"])
    plan = await generate_ad_campaign_plan(payload)
    db.add(
        AdCampaignPlanRecord(
            workspace_id=workspace_id,
            id=plan["plan_id"],
            campaign_name=plan["campaign_name"],
            niche=payload.niche,
            audience=payload.audience,
            region=payload.region,
            objective=payload.objective,
            platforms_json=list(payload.platforms),
            plan_json=plan,
            daily_budget_usd=payload.daily_budget_usd,
            status="draft",
        )
    )
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "unknown"),
            action="ads.plan.created",
            resource_type="ad_plan",
            resource_id=plan["plan_id"],
            outcome="draft_only",
            details_json={
                "objective": payload.objective,
                "platforms": list(payload.platforms),
                "creative_count": sum(len(item["creatives"]) for item in plan["platform_plans"]),
                "external_actions_executed": False,
                "spend_authorized": False,
            },
        )
    )
    await db.commit()
    return plan


@api.get("/ads/plans")
async def list_ad_plans(
    limit: int = Query(50, ge=1, le=200),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before listing ad plans")
    workspace_id = str(user["workspace_id"])
    rows = list((await db.scalars(
        select(AdCampaignPlanRecord)
        .where(AdCampaignPlanRecord.workspace_id == workspace_id)
        .order_by(AdCampaignPlanRecord.created_at.desc())
        .limit(limit)
    )).all())
    return {
        "count": len(rows),
        "limit": limit,
        "data": [
            {
                "id": row.id,
                "campaign_name": row.campaign_name,
                "niche": row.niche,
                "audience": row.audience,
                "region": row.region,
                "objective": row.objective,
                "platforms": list(row.platforms_json or []),
                "daily_budget_usd": f"{row.daily_budget_usd:.2f}",
                "status": row.status,
                "creative_count": sum(
                    len(item.get("creatives", []))
                    for item in (row.plan_json or {}).get("platform_plans", [])
                    if isinstance(item, dict)
                ),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }


@api.get("/ads/plans/{plan_id}")
async def get_ad_plan(
    plan_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before viewing an ad plan")
    workspace_id = str(user["workspace_id"])
    row = await db.scalar(
        select(AdCampaignPlanRecord).where(
            AdCampaignPlanRecord.id == plan_id,
            AdCampaignPlanRecord.workspace_id == workspace_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Ad plan not found")
    return {
        "id": row.id,
        "campaign_name": row.campaign_name,
        "niche": row.niche,
        "audience": row.audience,
        "region": row.region,
        "objective": row.objective,
        "platforms": list(row.platforms_json or []),
        "daily_budget_usd": f"{row.daily_budget_usd:.2f}",
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "plan": row.plan_json,
        "publishing_authorized": False,
        "spend_authorized": False,
    }

@api.post("/ads/observations", status_code=201)
async def create_ad_observation(
    payload: AdPerformanceObservationRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before recording ad observations")
    workspace_id = str(user["workspace_id"])
    if payload.campaign_plan_id:
        plan = await db.scalar(
            select(AdCampaignPlanRecord).where(
                AdCampaignPlanRecord.id == payload.campaign_plan_id,
                AdCampaignPlanRecord.workspace_id == workspace_id,
            )
        )
        if plan is None:
            raise HTTPException(404, "Ad plan not found in the active workspace")

    row = AdPerformanceObservation(
        workspace_id=workspace_id,
        campaign_plan_id=payload.campaign_plan_id,
        platform=payload.platform,
        creative_id=payload.creative_id.strip(),
        source_type=payload.source_type,
        source_reference_url=payload.source_reference_url,
        impressions=payload.impressions,
        clicks=payload.clicks,
        conversions=payload.conversions,
        spend_usd=payload.spend_usd,
        commission_usd=payload.commission_usd,
        currency=payload.currency,
        evidence_status="operator_supplied_unverified",
        observed_at=payload.observed_at or utcnow(),
        note=payload.note,
    )
    db.add(row)
    await db.flush()
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "unknown"),
            action="ads.performance_observation.created",
            resource_type="ad_performance_observation",
            resource_id=row.id,
            outcome="stored_unverified",
            details_json={
                "campaign_plan_id": payload.campaign_plan_id,
                "platform": payload.platform,
                "creative_id": payload.creative_id.strip(),
                "source_type": payload.source_type,
                "evidence_status": "operator_supplied_unverified",
                "external_actions_executed": False,
            },
        )
    )
    await db.commit()
    await db.refresh(row)
    return {
        "id": row.id,
        "campaign_plan_id": row.campaign_plan_id,
        "platform": row.platform,
        "creative_id": row.creative_id,
        "source_type": row.source_type,
        "source_reference_url": row.source_reference_url,
        "impressions": row.impressions,
        "clicks": row.clicks,
        "conversions": row.conversions,
        "spend_usd": f"{row.spend_usd:.2f}",
        "commission_usd": f"{row.commission_usd:.2f}",
        "currency": row.currency,
        "evidence_status": row.evidence_status,
        "observed_at": row.observed_at.isoformat() if row.observed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "optimization_eligible": False,
        "external_actions_executed": False,
    }


@api.get("/ads/observations")
async def list_ad_observations(
    limit: int = Query(100, ge=1, le=500),
    from_date: date | None = Query(None, description="Inclusive UTC observation date (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="Inclusive UTC observation date (YYYY-MM-DD)"),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before listing ad observations")
    workspace_id = str(user["workspace_id"])
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "from_date must be on or before to_date")
    statement = select(AdPerformanceObservation).where(
        AdPerformanceObservation.workspace_id == workspace_id
    )
    if from_date:
        statement = statement.where(
            AdPerformanceObservation.observed_at >= datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
        )
    if to_date:
        statement = statement.where(
            AdPerformanceObservation.observed_at < datetime.combine(to_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        )
    rows = list((await db.scalars(
        statement.order_by(AdPerformanceObservation.created_at.desc()).limit(limit)
    )).all())
    return {
        "count": len(rows),
        "limit": limit,
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "date_timezone": "UTC",
        "data": [
            {
                "id": row.id,
                "campaign_plan_id": row.campaign_plan_id,
                "platform": row.platform,
                "creative_id": row.creative_id,
                "source_type": row.source_type,
                "impressions": row.impressions,
                "clicks": row.clicks,
                "conversions": row.conversions,
                "spend_usd": f"{row.spend_usd:.2f}",
                "commission_usd": f"{row.commission_usd:.2f}",
                "currency": row.currency,
                "evidence_status": row.evidence_status,
                "observed_at": row.observed_at.isoformat() if row.observed_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "note": "Stored reports are unverified operator-supplied inputs until a trusted provider verification path is implemented.",
    }


@api.get("/ads/performance")
async def get_ad_performance(
    limit: int = Query(250, ge=1, le=1000),
    from_date: date | None = Query(None, description="Inclusive UTC observation date (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="Inclusive UTC observation date (YYYY-MM-DD)"),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    if not user.get("workspace_id"):
        raise HTTPException(403, "Select an authorized workspace before reading ad performance")
    workspace_id = str(user["workspace_id"])
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "from_date must be on or before to_date")
    statement = select(AdPerformanceObservation).where(
        AdPerformanceObservation.workspace_id == workspace_id
    )
    if from_date:
        statement = statement.where(
            AdPerformanceObservation.observed_at >= datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
        )
    if to_date:
        statement = statement.where(
            AdPerformanceObservation.observed_at < datetime.combine(to_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        )
    rows = list((await db.scalars(
        statement.order_by(AdPerformanceObservation.observed_at.desc()).limit(limit)
    )).all())
    return {
        "count": len(rows),
        "limit": limit,
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "date_timezone": "UTC",
        "items": summarize_ad_performance(rows),
        "note": "Reported KPIs are not treated as verified evidence. No campaign changes or spend actions are executed by this endpoint.",
    }


@api.post("/ads/evaluate")
async def ads_evaluate(
    p: dict[str, Any],
    user: dict[str, Any] = Depends(require_auth),
):
    if not user.get("workspace_id"):
        raise HTTPException(
            403, "Select an authorized workspace before evaluating ad performance"
        )
    try:
        decision = evaluate_roas(
            p["campaign_id"],
            p["spend"],
            p["commission"],
            p.get("threshold", 1.2),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(
            422,
            "campaign_id must be non-empty; spend, commission and threshold must be finite non-negative numbers",
        ) from exc
    return {
        "campaign_id": decision.campaign_id,
        "roas": decision.roas,
        "threshold": decision.threshold,
        "pause_recommended": decision.pause_recommended,
        "executed": False,
        "reason": decision.reason,
    }
def _ad_guardrail_dict(row: AdBudgetGuardrail) -> dict[str, Any]:
    last = row.last_evaluation_json or {}
    return {
        "id": row.id,
        "campaign_plan_id": row.campaign_plan_id,
        "daily_spend_cap_usd": format(Decimal(row.daily_spend_cap_usd), "f"),
        "campaign_spend_cap_usd": format(Decimal(row.campaign_spend_cap_usd), "f"),
        "minimum_roas": format(Decimal(row.minimum_roas), "f"),
        "maximum_cpa_usd": format(Decimal(row.maximum_cpa_usd), "f") if row.maximum_cpa_usd is not None else None,
        "minimum_verified_impressions": row.minimum_verified_impressions,
        "minimum_verified_clicks": row.minimum_verified_clicks,
        "minimum_verified_conversions": row.minimum_verified_conversions,
        "kill_switch_engaged": row.kill_switch_engaged is True,
        "stop_latched": row.stop_latched is True,
        "last_evaluated_at": row.last_evaluated_at.isoformat() if row.last_evaluated_at else None,
        "last_evaluation": last,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "live_spend_authorized": False,
        "external_campaign_changes_executed": False,
        "execution_note": "This API evaluates guardrails only. Live ad-provider execution is not configured or authorized.",
    }


@api.post("/ads/plans/{plan_id}/guardrails", status_code=201)
async def create_ad_budget_guardrail(
    plan_id: str,
    payload: AdBudgetGuardrailCreateRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before configuring ad budget guardrails")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        plan = await db.scalar(select(AdCampaignPlanRecord).where(
            AdCampaignPlanRecord.id == plan_id,
            AdCampaignPlanRecord.workspace_id == workspace_id,
        ))
        if plan is None:
            raise HTTPException(404, "Ad plan not found in the active workspace")
        existing = await db.scalar(select(AdBudgetGuardrail).where(
            AdBudgetGuardrail.workspace_id == workspace_id,
            AdBudgetGuardrail.campaign_plan_id == plan_id,
        ))
        if existing is not None:
            raise HTTPException(409, "This ad plan already has guardrails; use the existing policy instead of creating a duplicate")
        row = AdBudgetGuardrail(
            workspace_id=workspace_id,
            campaign_plan_id=plan_id,
            daily_spend_cap_usd=payload.daily_spend_cap_usd,
            campaign_spend_cap_usd=payload.campaign_spend_cap_usd,
            minimum_roas=payload.minimum_roas,
            maximum_cpa_usd=payload.maximum_cpa_usd,
            minimum_verified_impressions=payload.minimum_verified_impressions,
            minimum_verified_clicks=payload.minimum_verified_clicks,
            minimum_verified_conversions=payload.minimum_verified_conversions,
            kill_switch_engaged=False,
            stop_latched=False,
            last_evaluation_json={},
            created_by=str(user.get("email") or "unknown")[:320],
        )
        db.add(row)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "unknown"),
            action="ads.guardrail.created",
            resource_type="ad_budget_guardrail",
            resource_id=row.id,
            outcome="monitoring_only",
            details_json={
                "daily_spend_cap_usd": format(payload.daily_spend_cap_usd, "f"),
                "campaign_spend_cap_usd": format(payload.campaign_spend_cap_usd, "f"),
                "minimum_roas": format(payload.minimum_roas, "f"),
                "maximum_cpa_usd": format(payload.maximum_cpa_usd, "f") if payload.maximum_cpa_usd is not None else None,
                "live_spend_authorized": False,
            },
        ))
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(409, "This ad plan already has guardrails") from exc
        await db.refresh(row)
    return _ad_guardrail_dict(row)


@api.get("/ads/guardrails")
async def list_ad_budget_guardrails(
    limit: int = Query(100, ge=1, le=300),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before listing ad guardrails")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        rows = list((await db.scalars(
            select(AdBudgetGuardrail)
            .where(AdBudgetGuardrail.workspace_id == workspace_id)
            .order_by(AdBudgetGuardrail.created_at.desc())
            .limit(limit)
        )).all())
    return {"count": len(rows), "limit": limit, "data": [_ad_guardrail_dict(row) for row in rows]}


@api.get("/ads/plans/{plan_id}/guardrails")
async def get_ad_budget_guardrail(
    plan_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reading ad guardrails")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(AdBudgetGuardrail).where(
            AdBudgetGuardrail.workspace_id == workspace_id,
            AdBudgetGuardrail.campaign_plan_id == plan_id,
        ))
    if row is None:
        raise HTTPException(404, "Ad budget guardrails not found for this plan")
    return _ad_guardrail_dict(row)


@api.post("/ads/guardrails/{guardrail_id}/evaluate")
async def evaluate_ad_budget_guardrails(
    guardrail_id: str,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before evaluating ad guardrails")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(AdBudgetGuardrail).where(
            AdBudgetGuardrail.id == guardrail_id,
            AdBudgetGuardrail.workspace_id == workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Ad budget guardrails not found in the active workspace")
        plan = await db.scalar(select(AdCampaignPlanRecord).where(
            AdCampaignPlanRecord.id == row.campaign_plan_id,
            AdCampaignPlanRecord.workspace_id == workspace_id,
        ))
        if plan is None:
            raise HTTPException(409, "The guardrail's ad plan is no longer available in this workspace")
        observations = list((await db.scalars(
            select(AdPerformanceObservation)
            .where(
                AdPerformanceObservation.workspace_id == workspace_id,
                AdPerformanceObservation.campaign_plan_id == plan.id,
            )
            .order_by(AdPerformanceObservation.observed_at.asc())
        )).all())
        evaluated_at = utcnow()
        evaluation = evaluate_ad_budget_guardrail(
            policy=row,
            observations=observations,
            now=evaluated_at,
            plan_daily_budget_usd=Decimal(plan.daily_budget_usd or 0),
        )
        row.last_evaluated_at = evaluated_at
        row.last_evaluation_json = evaluation
        if evaluation.get("breaches"):
            row.stop_latched = True
            row.kill_switch_engaged = True
        if row.stop_latched:
            row.kill_switch_engaged = True
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "unknown"),
            action="ads.guardrail.evaluated",
            resource_type="ad_budget_guardrail",
            resource_id=row.id,
            outcome=evaluation.get("status", "unknown"),
            details_json={
                "breaches": evaluation.get("breaches", []),
                "verified_observation_count": evaluation.get("verified_observation_count", 0),
                "reported_observation_count": evaluation.get("reported_observation_count", 0),
                "kill_switch_engaged": row.kill_switch_engaged,
                "stop_latched": row.stop_latched,
                "provider_action_executed": False,
            },
        ))
        await db.commit()
        await db.refresh(row)
    return {**_ad_guardrail_dict(row), "evaluation": evaluation}


@api.post("/ads/guardrails/{guardrail_id}/kill-switch")
async def engage_ad_budget_kill_switch(
    guardrail_id: str,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before engaging the ad kill switch")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(AdBudgetGuardrail).where(
            AdBudgetGuardrail.id == guardrail_id,
            AdBudgetGuardrail.workspace_id == workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Ad budget guardrails not found in the active workspace")
        row.kill_switch_engaged = True
        row.stop_latched = True
        row.updated_by = str(user.get("email") or "unknown")[:320]
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "unknown"),
            action="ads.guardrail.kill_switch_engaged",
            resource_type="ad_budget_guardrail",
            resource_id=row.id,
            outcome="latched",
            details_json={"manual_kill_switch": True, "provider_action_executed": False, "live_spend_authorized": False},
        ))
        await db.commit()
        await db.refresh(row)
    return _ad_guardrail_dict(row)


@api.post("/ads/guardrails/{guardrail_id}/reset")
async def reset_ad_budget_kill_switch(
    guardrail_id: str,
    payload: AdGuardrailResetRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    if payload.confirm_reset is not True:
        raise HTTPException(409, "Reset requires confirm_reset=true and an explicit review rationale")
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before resetting ad guardrails")
    workspace_id = str(workspace_id)
    with workspace_scope(workspace_id):
        row = await db.scalar(select(AdBudgetGuardrail).where(
            AdBudgetGuardrail.id == guardrail_id,
            AdBudgetGuardrail.workspace_id == workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Ad budget guardrails not found in the active workspace")
        last = row.last_evaluation_json or {}
        if last.get("breaches"):
            raise HTTPException(409, "A fresh monitoring evaluation without active breaches is required before reset")
        if last.get("status") in {"blocked_pending_provider_verification", "blocked_mixed_evidence"}:
            raise HTTPException(409, "Guardrails cannot be reset while performance evidence is unverified or mixed")
        row.kill_switch_engaged = False
        row.stop_latched = False
        row.updated_by = str(user.get("email") or "unknown")[:320]
        row.last_evaluation_json = {
            **last,
            "reset_by": str(user.get("email") or "unknown"),
            "reset_at": utcnow().isoformat(),
            "reset_reason": payload.reason,
            "live_spend_authorized": False,
            "provider_action_executed": False,
        }
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or "unknown"),
            action="ads.guardrail.reset",
            resource_type="ad_budget_guardrail",
            resource_id=row.id,
            outcome="reset",
            details_json={"reset_reason": payload.reason, "live_spend_authorized": False,
                          "provider_action_executed": False},
        ))
        await db.commit()
        await db.refresh(row)
    return _ad_guardrail_dict(row)




MAX_AD_PERFORMANCE_WEBHOOK_BODY_BYTES = 256 * 1024


async def read_limited_ad_performance_body(request: Request, limit: int = MAX_AD_PERFORMANCE_WEBHOOK_BODY_BYTES) -> bytes:
    """Read the exact signed collector payload with a hard cap, including chunked requests."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "Invalid Content-Length") from exc
        if declared_length < 0:
            raise HTTPException(400, "Invalid Content-Length")
        if declared_length > limit:
            raise HTTPException(413, "Ad performance webhook body exceeds the size limit")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise HTTPException(413, "Ad performance webhook body exceeds the size limit")
        body.extend(chunk)
    return bytes(body)


@app.post("/api/webhooks/ad-performance/{workspace_id}/{platform}", status_code=201)
async def receive_signed_ad_performance(
    workspace_id: str,
    platform: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Accept HMAC-authenticated normalized daily metrics from a provisioned trusted collector.

    The collector must verify the underlying native ad-provider data before signing.
    This endpoint authenticates the collector and does not claim to validate a native
    Meta/Google/TikTok signature or to connect an external account itself.
    """
    try:
        workspace_id = str(UUID(workspace_id.strip()))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(422, "workspace_id must be a canonical UUID") from exc
    platform = platform.strip().lower()
    allowed_platforms = {
        "google_search", "google_display", "meta", "instagram", "tiktok", "youtube_shorts",
        "pinterest", "reddit", "quora", "x", "linkedin", "snapchat", "native",
    }
    if platform not in allowed_platforms:
        raise HTTPException(422, "Unsupported ad performance platform")
    secrets_by_key = settings.ad_performance_webhook_secrets or {}
    secret = secrets_by_key.get(f"{workspace_id}:{platform}")
    if not isinstance(secret, str) or len(secret) < 32:
        raise HTTPException(503, "Signed ad performance collector is not configured for this workspace/platform")

    raw_body = await read_limited_ad_performance_body(request)
    signature = request.headers.get("X-Ad-Performance-Signature", "")
    try:
        adapter = AdPerformanceWebhookAdapter(secret)
    except ValueError as exc:
        raise HTTPException(503, "Signed ad performance collector is not configured") from exc
    if not adapter.verify(raw_body, signature):
        raise HTTPException(401, "Invalid ad performance collector signature")

    try:
        decoded = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "Signed ad performance payload must contain valid JSON") from exc
    if not isinstance(decoded, dict):
        raise HTTPException(422, "Signed ad performance payload must be a JSON object")
    try:
        payload = SignedAdPerformanceWebhookPayload.model_validate(decoded)
    except ValidationError as exc:
        raise HTTPException(422, detail=exc.errors(include_input=False)) from exc
    if payload.platform != platform:
        raise HTTPException(422, "Payload platform must match the signed endpoint platform")

    with workspace_scope(workspace_id):
        plan = await db.scalar(select(AdCampaignPlanRecord).where(
            AdCampaignPlanRecord.id == payload.campaign_plan_id,
            AdCampaignPlanRecord.workspace_id == workspace_id,
        ))
        if plan is None:
            raise HTTPException(404, "Ad plan not found in the signed webhook's workspace")
        existing = await db.scalar(select(AdPerformanceObservation).where(
            AdPerformanceObservation.workspace_id == workspace_id,
            AdPerformanceObservation.platform == platform,
            AdPerformanceObservation.provider_event_id == payload.provider_event_id,
        ))
        def duplicate_response(existing_row):
            stored_observed_at = existing_row.observed_at
            if stored_observed_at.tzinfo is None or stored_observed_at.utcoffset() is None:
                stored_observed_at = stored_observed_at.replace(tzinfo=timezone.utc)
            else:
                stored_observed_at = stored_observed_at.astimezone(timezone.utc)
            same_event = (
                existing_row.campaign_plan_id == payload.campaign_plan_id
                and existing_row.creative_id == payload.creative_id
                and existing_row.source_reference_url == payload.source_reference_url
                and int(existing_row.impressions or 0) == payload.impressions
                and int(existing_row.clicks or 0) == payload.clicks
                and int(existing_row.conversions or 0) == payload.conversions
                and Decimal(existing_row.spend_usd or 0) == payload.spend_usd
                and Decimal(existing_row.commission_usd or 0) == payload.commission_usd
                and str(existing_row.currency or "USD").upper() == payload.currency
                and stored_observed_at == payload.observed_at.astimezone(timezone.utc)
                and existing_row.note == payload.note
            )
            if not same_event:
                raise HTTPException(
                    409,
                    "Provider event ID was already recorded with different observation data",
                )
            return JSONResponse(status_code=200, content={
                "status": "duplicate_ignored",
                "observation_id": existing_row.id,
                "provider_event_id": payload.provider_event_id,
                "evidence_status": existing_row.evidence_status,
                "provider_action_executed": False,
            })

        if existing is not None:
            return duplicate_response(existing)

        row = AdPerformanceObservation(
            workspace_id=workspace_id,
            campaign_plan_id=plan.id,
            platform=platform,
            creative_id=payload.creative_id,
            source_type="provider_api",
            source_reference_url=payload.source_reference_url,
            provider_event_id=payload.provider_event_id,
            source_signature_sha256=hashlib.sha256(raw_body).hexdigest(),
            impressions=payload.impressions,
            clicks=payload.clicks,
            conversions=payload.conversions,
            spend_usd=payload.spend_usd,
            commission_usd=payload.commission_usd,
            currency=payload.currency,
            evidence_status="provider_verified",
            observed_at=payload.observed_at,
            note=payload.note,
        )
        db.add(row)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor="signed_ad_performance_collector",
            action="ads.performance.signed_webhook_received",
            resource_type="ad_performance_observation",
            resource_id=row.id,
            outcome="provider_verified_by_trusted_collector",
            details_json={
                "provider_event_id": payload.provider_event_id,
                "platform": platform,
                "campaign_plan_id": plan.id,
                "evidence_status": "provider_verified",
                "verification_method": "workspace_platform_hmac_signed_collector",
                "collector_signature_verified": True,
                "native_provider_signature_checked_by_project1": False,
                "raw_body_sha256": row.source_signature_sha256,
                "provider_action_executed": False,
            },
        ))
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            with workspace_scope(workspace_id):
                existing = await db.scalar(select(AdPerformanceObservation).where(
                    AdPerformanceObservation.workspace_id == workspace_id,
                    AdPerformanceObservation.platform == platform,
                    AdPerformanceObservation.provider_event_id == payload.provider_event_id,
                ))
            if existing is not None:
                return duplicate_response(existing)
            raise HTTPException(409, "Signed ad performance event could not be persisted due to an integrity conflict") from exc
        await db.refresh(row)

    return {
        "status": "recorded",
        "observation_id": row.id,
        "provider_event_id": row.provider_event_id,
        "campaign_plan_id": row.campaign_plan_id,
        "platform": row.platform,
        "creative_id": row.creative_id,
        "evidence_status": row.evidence_status,
        "verification_method": "workspace_platform_hmac_signed_collector",
        "collector_signature_verified": True,
        "native_provider_signature_checked_by_project1": False,
        "source_signature_sha256": row.source_signature_sha256,
        "provider_action_executed": False,
    }




def _jurisdiction_compliance_dict(row: JurisdictionComplianceAssessment) -> dict[str, Any]:
    return {
        "id": row.id,
        "activity": row.activity,
        "channels": list(row.channels_json or []),
        "jurisdictions": list(row.jurisdictions_json or []),
        "rule_evidence": list(row.rule_evidence_json or []),
        "coverage_summary": dict(row.coverage_summary_json or {}),
        "status": row.status,
        "created_by": row.created_by,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "valid_until": row.valid_until.isoformat() if row.valid_until else None,
        "reviewer_notes": row.reviewer_notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "legal_approval_boundary": "Human review of cited sources; not a legal opinion or guarantee of compliance.",
    }


async def _require_live_compliance_approval(
    db: AsyncSession,
    *,
    workspace_id: str,
    activity: str,
    jurisdictions: list[str],
    channel: str,
    actor: str,
    action: str,
) -> JurisdictionComplianceAssessment:
    try:
        normalized_jurisdictions = normalize_jurisdictions(jurisdictions)
    except ValueError as exc:
        raise HTTPException(422, {
            "code": "TARGET_JURISDICTIONS_REQUIRED",
            "message": "Choose the jurisdictions the audience/action will reach before live execution.",
            "detail": str(exc),
        }) from exc
    assessment = await find_current_assessment(
        db,
        workspace_id=workspace_id,
        activity=activity,
        jurisdictions=normalized_jurisdictions,
        channel=channel,
    )
    if assessment is None:
        missing_categories = required_categories(activity)
        with workspace_scope(workspace_id):
            db.add(AuditLog(
                workspace_id=workspace_id,
                actor=actor[:320] or "unknown",
                action="compliance.live_action.blocked",
                resource_type="jurisdiction_compliance_assessment",
                outcome="blocked_review_required",
                details_json={
                    "activity": activity,
                    "channel": channel,
                    "target_jurisdictions": normalized_jurisdictions,
                    "required_categories": missing_categories,
                    "external_action": action,
                    "provider_action_executed": False,
                    "reason": "No current approved assessment covers this activity, channel and every target jurisdiction.",
                },
            ))
            await db.commit()
        raise HTTPException(409, {
            "code": "COMPLIANCE_APPROVAL_REQUIRED",
            "message": "Live execution needs a current approved assessment covering every target jurisdiction, channel and required rule category.",
            "activity": activity,
            "channel": channel,
            "target_jurisdictions": normalized_jurisdictions,
            "required_categories": missing_categories,
            "provider_action_executed": False,
        })
    return assessment


@api.get("/compliance/source-catalog")
async def compliance_source_catalog(
    jurisdiction: str = Query(..., min_length=2, max_length=12),
    category: str | None = Query(default=None, min_length=2, max_length=80),
    activity: str | None = Query(default=None, min_length=2, max_length=80),
    channel: str | None = Query(default=None, min_length=1, max_length=60),
    user: dict[str, Any] = Depends(require_admin),
):
    """Curated source discovery; catalog entries never count as approved legal evidence."""
    del user
    try:
        return get_compliance_source_catalog(
            jurisdiction=jurisdiction,
            category=category,
            activity=activity,
            channel=channel,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@api.get("/compliance/requirements")
async def get_compliance_requirements(user: dict[str, Any] = Depends(require_admin)):
    del user
    labels = {
        "affiliate_promotion": "Affiliate promotion",
        "content_publish": "External content publishing",
        "paid_media": "Paid media",
        "email_marketing": "Email marketing",
        "lead_capture": "Lead capture",
        "tracking_analytics": "Tracking and analytics",
        "merchant_marketplace": "Merchant marketplace",
    }
    return {
        "activities": [
            {"id": activity, "label": label, "required_categories": required_categories(activity)}
            for activity, label in labels.items()
        ],
        "evidence_max_age_days": {
            activity: (180 if activity in {"paid_media", "email_marketing", "tracking_analytics", "lead_capture"} else 365)
            for activity in labels
        },
        "review_validity_days": ASSESSMENT_VALIDITY_DAYS,
        "notice": "The system records jurisdiction-specific source evidence and a human decision. It does not generate legal rules, certify a country's law, or replace qualified local legal review. Unapproved or stale assessments affect live actions only; drafts and dry-runs remain available.",
    }


@api.get("/compliance/assessments")
async def list_compliance_assessments(
    limit: int = Query(default=100, ge=1, le=300),
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing compliance assessments")
    with workspace_scope(workspace_id):
        rows = list((await db.scalars(
            select(JurisdictionComplianceAssessment)
            .where(JurisdictionComplianceAssessment.workspace_id == workspace_id)
            .order_by(JurisdictionComplianceAssessment.created_at.desc())
            .limit(limit)
        )).all())
    return {"count": len(rows), "data": [_jurisdiction_compliance_dict(row) for row in rows]}


@api.post("/compliance/assessments", status_code=201)
async def create_compliance_assessment(
    payload: JurisdictionComplianceAssessmentCreateRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating a compliance assessment")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    jurisdictions = normalize_jurisdictions(payload.jurisdictions)
    evidence = [item.model_dump(mode="json") for item in payload.rule_evidence]
    coverage = evidence_coverage(payload.activity, jurisdictions, evidence)
    row = JurisdictionComplianceAssessment(
        workspace_id=workspace_id,
        activity=payload.activity,
        channels_json=payload.channels,
        jurisdictions_json=jurisdictions,
        rule_evidence_json=evidence,
        coverage_summary_json=coverage,
        status="review_required" if coverage["coverage_complete"] else "draft",
        created_by=actor,
        reviewer_notes=payload.operator_notes or None,
    )
    with workspace_scope(workspace_id):
        db.add(row)
        await db.flush()
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="compliance.assessment.created",
            resource_type="jurisdiction_compliance_assessment",
            resource_id=row.id,
            outcome=row.status,
            details_json={
                "activity": row.activity,
                "channels": row.channels_json,
                "jurisdictions": row.jurisdictions_json,
                "coverage_complete": coverage["coverage_complete"],
                "missing_evidence_count": len(coverage["missing_evidence"]),
                "legal_approval_granted": False,
            },
        ))
        await db.commit()
        await db.refresh(row)
    return _jurisdiction_compliance_dict(row)


@api.post("/compliance/assessments/{assessment_id}/review")
async def review_compliance_assessment(
    assessment_id: str,
    payload: JurisdictionComplianceAssessmentReviewRequest,
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reviewing a compliance assessment")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        row = await db.scalar(select(JurisdictionComplianceAssessment).where(
            JurisdictionComplianceAssessment.id == assessment_id,
            JurisdictionComplianceAssessment.workspace_id == workspace_id,
        ).with_for_update())
        if row is None:
            raise HTTPException(404, "Compliance assessment not found in the active workspace")
        if row.status in {"approved", "rejected", "expired"}:
            raise HTTPException(409, "This assessment has already been reviewed; create a new version to change scope or evidence")
        now = utcnow()
        coverage = evidence_coverage(
            row.activity, list(row.jurisdictions_json or []), list(row.rule_evidence_json or []), now=now
        )
        if payload.decision == "approve":
            if payload.confirm_scope_reviewed is not True:
                raise HTTPException(409, "Approval requires confirm_scope_reviewed=true after review of the cited sources and every target jurisdiction")
            if not coverage["coverage_complete"]:
                raise HTTPException(409, {
                    "code": "COMPLIANCE_EVIDENCE_INCOMPLETE",
                    "message": "Every required rule category must have recent, attested HTTPS source evidence for every target jurisdiction.",
                    "coverage": coverage,
                })
            row.status = "approved"
            row.reviewed_by = actor
            row.reviewed_at = now
            row.valid_until = now + timedelta(days=ASSESSMENT_VALIDITY_DAYS)
            row.reviewer_notes = payload.reviewer_notes or None
            outcome = "approved_human_review"
        else:
            row.status = "rejected"
            row.reviewed_by = actor
            row.reviewed_at = now
            row.valid_until = None
            row.reviewer_notes = payload.reviewer_notes or "Rejected during compliance review."
            outcome = "rejected_human_review"
        row.coverage_summary_json = coverage
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="compliance.assessment.reviewed",
            resource_type="jurisdiction_compliance_assessment",
            resource_id=row.id,
            outcome=outcome,
            details_json={
                "activity": row.activity,
                "channels": list(row.channels_json or []),
                "jurisdictions": list(row.jurisdictions_json or []),
                "coverage_complete": coverage["coverage_complete"],
                "missing_evidence_count": len(coverage["missing_evidence"]),
                "valid_until": row.valid_until.isoformat() if row.valid_until else None,
                "human_legal_review_attested": payload.confirm_scope_reviewed is True,
            },
        ))
        await db.commit()
        await db.refresh(row)
    return _jurisdiction_compliance_dict(row)





@api.post("/cms/publish")
async def cms(
    payload: CMSPublishRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    # WordPress/Ghost credentials are global config today, so workspace-admin
    # status alone must not authorize writes to a shared external CMS account.
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before CMS publishing")
    if payload.status == "publish" and payload.confirm_live_publish is not True:
        raise HTTPException(409, "Live CMS publishing requires confirm_live_publish=true from an authorized operator")
    owner_workspace_id = str(workspace_id)
    live_cms_publish = payload.status == "publish" and settings.cms_publish_execute is True
    supplied_key = str(request.headers.get("Idempotency-Key") or "").strip()
    if not EXTERNAL_IDEMPOTENCY_KEY_RE.fullmatch(supplied_key):
        raise HTTPException(428, "A valid Idempotency-Key header is required for CMS provider writes")
    action_id, replay = await _claim_external_action(
        db, workspace_id=owner_workspace_id, action_type="cms_publish",
        provider=payload.provider, idempotency_key=supplied_key,
        request_payload=payload.model_dump(mode="json"),
    )
    if replay is not None:
        await _record_external_publish_audit(
            db, user=user, workspace_id=owner_workspace_id,
            action="cms_publish_idempotency_replay", platform=payload.provider,
            outcome="replayed", remote_id=replay.get("remote_id"),
        )
        return replay
    if live_cms_publish:
        try:
            await _require_live_compliance_approval(
                db, workspace_id=owner_workspace_id, activity="content_publish",
                jurisdictions=payload.target_jurisdictions, channel=payload.provider,
                actor=str(user.get("email") or user.get("user_id") or "unknown"), action="cms_publish",
            )
        except HTTPException as exc:
            if action_id:
                await _finish_external_action(
                    db, workspace_id=owner_workspace_id, action_id=action_id,
                    status="failed", error_type="ComplianceApprovalRequired",
                )
            raise exc
    try:
        with workspace_scope(owner_workspace_id):
            result = await publish_article(
                provider=payload.provider, title=payload.title, article_html=payload.article_html,
                canonical_url=payload.canonical_url, status=payload.status,
                tags=payload.tags, disclosure=payload.disclosure,
            )
    except Exception as exc:
        action_outcome = _external_action_failure_status(exc)
        try:
            await _finish_external_action(
                db, workspace_id=owner_workspace_id, action_id=action_id,
                status=action_outcome, error_type=type(exc).__name__,
            )
        except Exception:
            logger.exception("Could not persist CMS action outcome for workspace %s", owner_workspace_id[:8])
        await _record_external_publish_audit(
            db, user=user, workspace_id=owner_workspace_id, action="cms_publish",
            platform=payload.provider,
            outcome="outcome_unknown" if action_outcome == "unknown" else "failed",
            error_type=type(exc).__name__,
        )
        raise
    await _finish_external_action(db, workspace_id=owner_workspace_id, action_id=action_id, status="completed", result=result)
    await _record_external_publish_audit(
        db, user=user, workspace_id=owner_workspace_id, action="cms_publish",
        platform=payload.provider, outcome=str(result.get("status") or payload.status),
        remote_id=result.get("remote_id"),
    )
    return result


def _bio_link_asset_dict(row: ContentAsset, *, include_html: bool = False) -> dict[str, Any]:
    metadata = dict(row.metadata_json or {})
    result = {
        "id": row.id,
        "title": row.title,
        "status": row.status,
        "source_urls": list(row.source_urls or []),
        "link_count": int(metadata.get("link_count") or 0),
        "affiliate_link_count": int(metadata.get("affiliate_link_count") or 0),
        "page_sha256": str(metadata.get("page_sha256") or ""),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "publication": metadata.get("publication"),
        "execution_boundary": "Draft HTML is generated locally; CMS publishing uses the existing platform-admin, idempotency, and live-compliance gates.",
    }
    result["github_pages_publication"] = metadata.get("github_pages_publication")
    if include_html:
        result["html"] = row.body
    return result



def _distribution_queue_item_dict(row: DistributionQueueItem, *, replayed: bool = False) -> dict[str, Any]:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "source_asset_id": row.source_asset_id,
        "source_asset_type": row.source_asset_type,
        "title": row.content_title,
        "channel": row.channel,
        "content_sha256": row.content_sha256,
        "source_urls": list(row.source_urls_json or []),
        "target_jurisdictions": list(row.target_jurisdictions_json or []),
        "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
        "status": row.status,
        "created_by": row.created_by,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "reviewer_note": row.reviewer_note,
        "cancelled_by": row.cancelled_by,
        "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
        "external_post_id": row.external_post_id,
        "attempt_count": int(row.attempt_count or 0),
        "external_submission_status": "not_attempted" if not row.external_post_id else "provider_id_recorded",
        "dispatch_confirmation_required": True,
        "execution_boundary": "Queueing and review do not publish content. Provider readiness, current compliance, scope, idempotency, and explicit per-action dispatch confirmation remain separate.",
        "replayed": replayed,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@api.get("/distribution/queue/assets")
async def list_distribution_queue_assets(
    limit: int = Query(default=100, ge=1, le=200),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing queueable content")
    with workspace_scope(workspace_id):
        rows = list((await db.scalars(
            select(ContentAsset)
            .where(
                ContentAsset.workspace_id == workspace_id,
                ContentAsset.body != "",
                ContentAsset.status.notin_(("rejected", "archived", "cancelled")),
            )
            .order_by(ContentAsset.created_at.desc())
            .limit(limit)
        )).all())
    return {"count": len(rows), "data": [
        {
            "id": row.id,
            "title": row.title,
            "asset_type": row.asset_type,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]}


@api.get("/distribution/queue")
async def list_distribution_queue_items(
    limit: int = Query(default=100, ge=1, le=200),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing the distribution queue")
    with workspace_scope(workspace_id):
        rows = list((await db.scalars(
            select(DistributionQueueItem)
            .where(DistributionQueueItem.workspace_id == workspace_id)
            .order_by(DistributionQueueItem.created_at.desc())
            .limit(limit)
        )).all())
    return {"count": len(rows), "data": [_distribution_queue_item_dict(row) for row in rows]}


@api.post("/distribution/queue", status_code=201)
async def create_distribution_queue_item(
    payload: DistributionQueueCreateRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before queueing content")
    idempotency_key = str(request.headers.get("Idempotency-Key") or "").strip()
    if not EXTERNAL_IDEMPOTENCY_KEY_RE.fullmatch(idempotency_key):
        raise HTTPException(428, "A valid Idempotency-Key header is required to prevent duplicate queue items")

    request_payload = {
        "content_asset_id": payload.content_asset_id,
        "channel": payload.channel,
        "scheduled_at": payload.scheduled_at.isoformat() if payload.scheduled_at else None,
    }
    request_hash = hashlib.sha256(
        json.dumps(request_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]

    with workspace_scope(workspace_id):
        existing = await db.scalar(select(DistributionQueueItem).where(
            DistributionQueueItem.workspace_id == workspace_id,
            DistributionQueueItem.idempotency_key == idempotency_key,
        ))
        if existing is not None:
            if existing.request_hash != request_hash:
                raise HTTPException(409, "This idempotency key was already used for a different queue request")
            return _distribution_queue_item_dict(existing, replayed=True)

        asset = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == payload.content_asset_id,
            ContentAsset.workspace_id == workspace_id,
        ))
        if asset is None:
            raise HTTPException(404, "Content asset not found in the active workspace")
        body = str(asset.body or "")
        if not body.strip():
            raise HTTPException(422, "The selected content asset has no content to queue")
        if len(body) > 200_000:
            raise HTTPException(413, "The selected content snapshot exceeds the 200,000-character queue limit")

        content_sha256 = hashlib.sha256(
            (str(asset.asset_type) + "\0" + str(asset.title) + "\0" + body).encode("utf-8")
        ).hexdigest()
        row = DistributionQueueItem(
            workspace_id=workspace_id,
            source_asset_id=asset.id,
            source_asset_type=str(asset.asset_type)[:100],
            content_title=str(asset.title)[:500],
            content_body=body,
            content_sha256=content_sha256,
            source_urls_json=[str(item)[:2048] for item in (asset.source_urls or []) if isinstance(item, str)][:20],
            channel=payload.channel,
            target_jurisdictions_json=[],
            scheduled_at=payload.scheduled_at,
            status="pending_review",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            created_by=actor,
        )
        db.add(row)
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="distribution.queue_item.created",
            resource_type="distribution_queue_item",
            resource_id=row.id,
            outcome="pending_review",
            details_json={
                "source_asset_id": asset.id,
                "source_asset_type": asset.asset_type,
                "channel": payload.channel,
                "content_sha256": content_sha256,
                "scheduled_at": payload.scheduled_at.isoformat() if payload.scheduled_at else None,
                "external_submission_performed": False,
            },
        ))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            existing = await db.scalar(select(DistributionQueueItem).where(
                DistributionQueueItem.workspace_id == workspace_id,
                DistributionQueueItem.idempotency_key == idempotency_key,
            ))
            if existing is not None and existing.request_hash == request_hash:
                return _distribution_queue_item_dict(existing, replayed=True)
            raise HTTPException(409, "Queue idempotency key conflicts with an existing request")
        await db.refresh(row)
        return _distribution_queue_item_dict(row)


@api.post("/distribution/queue/{item_id}/approve")
async def approve_distribution_queue_item(
    item_id: str,
    payload: DistributionQueueApproveRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before approving queue items")
    if str(user.get("workspace_role") or "") not in {"owner", "admin"}:
        raise HTTPException(403, "Only a workspace owner or admin may approve distribution queue items")
    if payload.confirm_content_review is not True:
        raise HTTPException(409, "Explicit confirmation that the content and target scope were reviewed is required")

    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        row = await db.scalar(select(DistributionQueueItem).where(
            DistributionQueueItem.id == item_id,
            DistributionQueueItem.workspace_id == workspace_id,
        ))
        if row is None:
            raise HTTPException(404, "Distribution queue item not found in the active workspace")
        if row.status != "pending_review":
            raise HTTPException(409, "Only items pending review can be approved")
        if row.scheduled_at:
            scheduled_at = row.scheduled_at
            if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
            else:
                scheduled_at = scheduled_at.astimezone(timezone.utc)
            if scheduled_at <= datetime.now(timezone.utc):
                raise HTTPException(409, "The scheduled time has passed; create a new queue item with a future schedule")
        row.status = "approved_waiting_for_dispatch"
        row.target_jurisdictions_json = list(payload.target_jurisdictions)
        row.reviewed_by = actor
        row.reviewed_at = datetime.now(timezone.utc)
        row.reviewer_note = payload.reviewer_note.strip()
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="distribution.queue_item.approved",
            resource_type="distribution_queue_item",
            resource_id=row.id,
            outcome="approved_waiting_for_dispatch",
            details_json={
                "target_jurisdictions": list(payload.target_jurisdictions),
                "reviewer_note": payload.reviewer_note.strip()[:4000],
                "external_submission_performed": False,
                "dispatch_confirmation_required": True,
            },
        ))
        await db.commit()
        await db.refresh(row)
        return _distribution_queue_item_dict(row)


@api.post("/distribution/queue/{item_id}/cancel")
async def cancel_distribution_queue_item(
    item_id: str,
    payload: DistributionQueueCancelRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before cancelling queue items")
    if payload.confirm_cancel is not True:
        raise HTTPException(409, "Explicit queue cancellation confirmation is required")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    role = str(user.get("workspace_role") or "")

    with workspace_scope(workspace_id):
        row = await db.scalar(select(DistributionQueueItem).where(
            DistributionQueueItem.id == item_id,
            DistributionQueueItem.workspace_id == workspace_id,
        ))
        if row is None:
            raise HTTPException(404, "Distribution queue item not found in the active workspace")
        is_creator = row.created_by.casefold() == actor.casefold()
        if not is_creator and role not in {"owner", "admin"}:
            raise HTTPException(403, "Only the creator or a workspace owner/admin may cancel this queue item")
        if row.status == "cancelled":
            return _distribution_queue_item_dict(row)
        if row.status not in {"pending_review", "approved_waiting_for_dispatch"}:
            raise HTTPException(409, "Only undispatched queue items can be cancelled")
        row.status = "cancelled"
        row.cancelled_by = actor
        row.cancelled_at = datetime.now(timezone.utc)
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="distribution.queue_item.cancelled",
            resource_type="distribution_queue_item",
            resource_id=row.id,
            outcome="cancelled",
            details_json={"external_submission_performed": False},
        ))
        await db.commit()
        await db.refresh(row)
        return _distribution_queue_item_dict(row)


@api.get("/distribution/bio-links")
async def list_bio_link_pages(
    limit: int = Query(default=50, ge=1, le=100),
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing bio-link pages")
    with workspace_scope(workspace_id):
        rows = list((await db.scalars(
            select(ContentAsset).where(
                ContentAsset.workspace_id == workspace_id,
                ContentAsset.asset_type == "bio_link_page",
            ).order_by(ContentAsset.created_at.desc()).limit(limit)
        )).all())
    return {"count": len(rows), "data": [_bio_link_asset_dict(row) for row in rows]}


@api.post("/distribution/bio-links", status_code=201)
async def create_bio_link_page(
    payload: BioLinkPageCreateRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before creating bio-link pages")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        row = ContentAsset(
            workspace_id=workspace_id,
            asset_type="bio_link_page",
            title=payload.title,
            body="",
            status="draft",
            source_urls=[link.url for link in payload.links],
            metadata_json={"schema_version": 1},
        )
        db.add(row)
        await db.flush()
        try:
            built = build_bio_link_page(payload.model_dump(mode="json"), page_id=row.id)
        except ValueError as exc:
            await db.rollback()
            raise HTTPException(422, str(exc)) from exc
        row.body = built["html"]
        row.metadata_json = {
            "schema_version": 1,
            "link_count": built["link_count"],
            "affiliate_link_count": built["affiliate_link_count"],
            "page_sha256": built["sha256"],
            "tracking_parameters": ["utm_source", "utm_medium", "utm_content"],
            "external_scripts": False,
            "user_markup_embedded": False,
            "server_side_link_fetches": 0,
        }
        db.add(AuditLog(
            workspace_id=workspace_id, actor=actor,
            action="bio_link_page.created", resource_type="content_asset",
            resource_id=row.id, outcome="draft",
            details_json={
                "link_count": built["link_count"],
                "affiliate_link_count": built["affiliate_link_count"],
                "page_sha256": built["sha256"],
                "external_scripts": False,
            },
        ))
        await db.commit()
        await db.refresh(row)
    result = _bio_link_asset_dict(row)
    result["preview_url"] = f"/api/distribution/bio-links/{row.id}/preview"
    return result


@api.get("/distribution/bio-links/{asset_id}/preview")
async def preview_bio_link_page(
    asset_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before previewing bio-link pages")
    with workspace_scope(workspace_id):
        row = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "bio_link_page",
        ))
    if row is None:
        raise HTTPException(404, "Bio-link page not found in the active workspace")
    return HTMLResponse(
        row.body,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'",
        },
    )


@api.post("/distribution/bio-links/{asset_id}/publish")
async def publish_bio_link_page(
    asset_id: str,
    payload: BioLinkPublishRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before publishing a bio-link page")
    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    with workspace_scope(workspace_id):
        asset = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "bio_link_page",
        ))
    if asset is None:
        raise HTTPException(404, "Bio-link page not found in the active workspace")
    if payload.status == "publish" and payload.confirm_live_publish is not True:
        raise HTTPException(409, "Live bio-link publishing requires confirm_live_publish=true")
    supplied_key = str(request.headers.get("Idempotency-Key") or "").strip()
    if not EXTERNAL_IDEMPOTENCY_KEY_RE.fullmatch(supplied_key):
        raise HTTPException(428, "A valid Idempotency-Key header is required for provider writes")
    metadata = dict(asset.metadata_json or {})
    action_payload = {
        "asset_id": asset.id,
        "page_sha256": metadata.get("page_sha256"),
        "provider": payload.provider,
        "canonical_url": payload.canonical_url,
        "target_jurisdictions": payload.target_jurisdictions,
        "status": payload.status,
        "confirm_live_publish": payload.confirm_live_publish,
        "tags": payload.tags,
        "disclosure": payload.disclosure,
    }
    action_id, replay = await _claim_external_action(
        db, workspace_id=workspace_id, action_type="bio_link_publish",
        provider=payload.provider, idempotency_key=supplied_key,
        request_payload=action_payload,
    )
    if replay is not None:
        await _record_external_publish_audit(
            db, user=user, workspace_id=workspace_id,
            action="bio_link_publish_idempotency_replay", platform=payload.provider,
            outcome="replayed", remote_id=(replay.get("provider_result") or {}).get("remote_id"),
        )
        return replay
    if asset.status in {"published", "publish_outcome_unknown"}:
        await _finish_external_action(
            db, workspace_id=workspace_id, action_id=action_id,
            status="failed", error_type="BioLinkAlreadyPublishedOrUnknown",
        )
        raise HTTPException(409, "This page is already published or has an unknown provider outcome; reconcile before publishing again")
    live_publish = payload.status == "publish" and settings.cms_publish_execute is True
    if live_publish:
        try:
            await _require_live_compliance_approval(
                db, workspace_id=workspace_id, activity="content_publish",
                jurisdictions=payload.target_jurisdictions, channel=payload.provider,
                actor=actor, action="bio_link_publish",
            )
        except HTTPException:
            await _finish_external_action(
                db, workspace_id=workspace_id, action_id=action_id,
                status="failed", error_type="ComplianceApprovalRequired",
            )
            raise
    try:
        with workspace_scope(workspace_id):
            remote = await publish_article(
                provider=payload.provider,
                title=asset.title,
                article_html=asset.body,
                canonical_url=payload.canonical_url,
                status=payload.status,
                tags=payload.tags,
                disclosure=payload.disclosure,
            )
    except Exception as exc:
        action_outcome = _external_action_failure_status(exc)
        await _finish_external_action(
            db, workspace_id=workspace_id, action_id=action_id,
            status=action_outcome, error_type=type(exc).__name__,
        )
        if action_outcome == "unknown":
            with workspace_scope(workspace_id):
                asset.status = "publish_outcome_unknown"
                metadata = dict(asset.metadata_json or {})
                metadata["publication"] = {"provider": payload.provider, "status": "outcome_unknown", "error_type": type(exc).__name__}
                asset.metadata_json = metadata
                await db.commit()
        await _record_external_publish_audit(
            db, user=user, workspace_id=workspace_id, action="bio_link_publish",
            platform=payload.provider, outcome="outcome_unknown" if action_outcome == "unknown" else "failed",
            error_type=type(exc).__name__,
        )
        raise
    asset_status = "published" if str(remote.get("status") or "").lower() in {"publish", "published"} else "cms_draft"
    result = {
        "asset_id": asset.id,
        "asset_status": asset_status,
        "page_sha256": metadata.get("page_sha256"),
        "provider_result": remote,
        "status": "completed",
    }
    await _finish_external_action(
        db, workspace_id=workspace_id, action_id=action_id,
        status="completed", result=result,
    )
    with workspace_scope(workspace_id):
        asset.status = asset_status
        metadata = dict(asset.metadata_json or {})
        metadata["publication"] = {
            "provider": payload.provider,
            "remote_id": str(remote.get("remote_id") or "")[:255] or None,
            "url": remote.get("url"),
            "status": remote.get("status"),
            "published_at": utcnow().isoformat() if asset_status == "published" else None,
            "page_sha256": metadata.get("page_sha256"),
        }
        asset.metadata_json = metadata
        await db.commit()
    await _record_external_publish_audit(
        db, user=user, workspace_id=workspace_id, action="bio_link_publish",
        platform=payload.provider, outcome=asset_status, remote_id=remote.get("remote_id"),
    )
    return result




@api.get("/distribution/github-pages/status")
async def github_pages_deployment_status(
    user: dict[str, Any] = Depends(require_platform_admin),
):
    # This is configuration readiness, not a claim that the token or remote Pages source was verified.
    return github_pages_readiness(settings)


@api.post("/distribution/github-pages/deploy")
async def deploy_bio_link_to_github_pages(
    payload: GitHubPagesDeployRequest,
    request: Request,
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before deploying a site")
    if payload.confirm_live_publish is not True:
        raise HTTPException(409, "GitHub Pages deployment requires confirm_live_publish=true.")
    readiness = github_pages_readiness(settings)
    if not readiness["deployment_enabled"]:
        raise HTTPException(409, {
            "code": "GITHUB_PAGES_DEPLOYMENT_DISABLED",
            "message": "Live deployment is disabled. Configure GITHUB_PAGES_DEPLOY_EXECUTE after reviewing the target repository and token scope.",
        })
    if not readiness["configuration_ready"]:
        raise HTTPException(503, {
            "code": "GITHUB_PAGES_NOT_CONFIGURED",
            "message": "A valid fixed GitHub repository and scoped deployment token must be configured on the server.",
        })

    with workspace_scope(workspace_id):
        asset = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == payload.asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "bio_link_page",
        ))
    if asset is None:
        raise HTTPException(404, "Bio-link page not found in the active workspace.")
    metadata = dict(asset.metadata_json or {})
    expected_checksum = str(metadata.get("page_sha256") or "")
    actual_checksum = hashlib.sha256(asset.body.encode("utf-8")).hexdigest()
    if not expected_checksum or expected_checksum != actual_checksum:
        raise HTTPException(409, {
            "code": "BIO_LINK_ARTIFACT_CHECKSUM_MISMATCH",
            "message": "The saved page does not match its recorded checksum. Rebuild the bio-link artifact before deployment.",
        })
    prior_publication = metadata.get("github_pages_publication")
    if isinstance(prior_publication, dict) and prior_publication.get("status") == "outcome_unknown":
        raise HTTPException(409, {
            "code": "GITHUB_PAGES_OUTCOME_UNKNOWN",
            "message": "The previous provider outcome is unresolved. Reconcile the remote file before retrying.",
        })

    supplied_key = str(request.headers.get("Idempotency-Key") or "").strip()
    if not EXTERNAL_IDEMPOTENCY_KEY_RE.fullmatch(supplied_key):
        raise HTTPException(428, "A valid Idempotency-Key header is required for GitHub Pages writes.")
    action_payload = {
        "asset_id": asset.id,
        "page_sha256": actual_checksum,
        "repository": readiness["repository"],
        "branch": readiness["branch"],
        "directory": readiness["directory"],
        "target_jurisdictions": payload.target_jurisdictions,
        "confirm_live_publish": True,
    }
    action_id, replay = await _claim_external_action(
        db, workspace_id=workspace_id, action_type="github_pages_deploy",
        provider="github_pages", idempotency_key=supplied_key,
        request_payload=action_payload,
    )
    if replay is not None:
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or user.get("user_id") or "unknown")[:320],
            action="github_pages.deploy.idempotency_replay",
            resource_type="content_asset", resource_id=asset.id,
            outcome="replayed", details_json={"page_sha256": actual_checksum, "provider_action_executed": False},
        ))
        await db.commit()
        return replay

    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    try:
        await _require_live_compliance_approval(
            db, workspace_id=workspace_id, activity="content_publish",
            jurisdictions=payload.target_jurisdictions, channel="github_pages",
            actor=actor, action="github_pages_deploy",
        )
    except HTTPException:
        await _finish_external_action(
            db, workspace_id=workspace_id, action_id=action_id,
            status="failed", error_type="ComplianceApprovalRequired",
        )
        raise

    try:
        with workspace_scope(workspace_id):
            remote = await deploy_github_pages_html(
                html_content=asset.body,
                title=asset.title,
                asset_id=asset.id,
                settings=settings,
            )
    except Exception as exc:
        action_outcome = _external_action_failure_status(exc)
        try:
            await _finish_external_action(
                db, workspace_id=workspace_id, action_id=action_id,
                status=action_outcome, error_type=type(exc).__name__,
            )
        except Exception:
            logger.exception("Could not persist GitHub Pages action outcome for workspace %s", workspace_id[:8])
        metadata = dict(asset.metadata_json or {})
        metadata["github_pages_publication"] = {
            "status": "outcome_unknown" if action_outcome == "unknown" else "failed",
            "repository": readiness["repository"],
            "branch": readiness["branch"],
            "directory": readiness["directory"],
            "page_sha256": actual_checksum,
            "action_id": action_id,
            "error_type": type(exc).__name__,
            "last_attempt_at": utcnow().isoformat(),
        }
        asset.metadata_json = metadata
        db.add(AuditLog(
            workspace_id=workspace_id, actor=actor,
            action="github_pages.deploy", resource_type="content_asset", resource_id=asset.id,
            outcome="outcome_unknown" if action_outcome == "unknown" else "failed",
            details_json={
                "page_sha256": actual_checksum,
                "repository": readiness["repository"],
                "branch": readiness["branch"],
                "error_type": type(exc).__name__,
                "provider_outcome": action_outcome,
            },
        ))
        await db.commit()
        if isinstance(exc, GitHubPagesConfigurationError):
            raise HTTPException(409, str(exc)) from exc
        if isinstance(exc, httpx.HTTPStatusError):
            raise HTTPException(502, {
                "code": "GITHUB_PAGES_PROVIDER_REJECTED_REQUEST",
                "message": "GitHub rejected the deployment request. Verify repository permissions, Pages source branch, and token scope.",
                "provider_outcome": action_outcome,
            }) from exc
        raise HTTPException(502, {
            "code": "GITHUB_PAGES_PROVIDER_ERROR",
            "message": "GitHub Pages deployment did not complete. If the provider outcome is unknown, reconcile it before retrying.",
            "provider_outcome": action_outcome,
        }) from exc

    deployment_status = "unchanged" if remote["status"] == "unchanged" else "published"
    result = {
        "asset_id": asset.id,
        "status": "completed",
        "deployment_status": deployment_status,
        "repository": remote["repository"],
        "branch": remote["branch"],
        "content_path": remote["content_path"],
        "published_url": remote["published_url"],
        "page_sha256": remote["page_sha256"],
        "file_sha": remote.get("file_sha"),
        "commit_sha": remote.get("commit_sha"),
        "commit_url": remote.get("commit_url"),
    }
    await _finish_external_action(
        db, workspace_id=workspace_id, action_id=action_id,
        status="completed", result=result,
    )
    metadata = dict(asset.metadata_json or {})
    metadata["github_pages_publication"] = {
        "status": "published",
        "repository": remote["repository"],
        "branch": remote["branch"],
        "content_path": remote["content_path"],
        "published_url": remote["published_url"],
        "page_sha256": remote["page_sha256"],
        "file_sha": remote.get("file_sha"),
        "commit_sha": remote.get("commit_sha"),
        "commit_url": remote.get("commit_url"),
        "provider_status": deployment_status,
        "verified_at": utcnow().isoformat(),
        "action_id": action_id,
    }
    asset.metadata_json = metadata
    db.add(AuditLog(
        workspace_id=workspace_id, actor=actor,
        action="github_pages.deploy", resource_type="content_asset", resource_id=asset.id,
        outcome=deployment_status,
        details_json={
            "page_sha256": remote["page_sha256"],
            "repository": remote["repository"],
            "branch": remote["branch"],
            "content_path": remote["content_path"],
            "commit_sha": remote.get("commit_sha"),
            "external_action_id": action_id,
        },
    ))
    await db.commit()
    return result


@api.post("/distribution/github-pages/{asset_id}/reconcile")
async def reconcile_github_pages_deployment(
    asset_id: str,
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before reconciling a deployment.")
    with workspace_scope(workspace_id):
        asset = await db.scalar(select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.workspace_id == workspace_id,
            ContentAsset.asset_type == "bio_link_page",
        ))
    if asset is None:
        raise HTTPException(404, "Bio-link page not found in the active workspace.")
    metadata = dict(asset.metadata_json or {})
    publication = metadata.get("github_pages_publication")
    if not isinstance(publication, dict) or publication.get("status") != "outcome_unknown":
        raise HTTPException(409, "This page does not have an unresolved GitHub Pages outcome.")
    action_id = str(publication.get("action_id") or "")
    if not action_id:
        raise HTTPException(409, "No external-action record is available for reconciliation.")
    with workspace_scope(workspace_id):
        action = await db.scalar(select(ExternalAction).where(
            ExternalAction.id == action_id,
            ExternalAction.workspace_id == workspace_id,
            ExternalAction.action_type == "github_pages_deploy",
        ))
    if action is None or action.status != "unknown":
        raise HTTPException(409, "The external-action record is not in an unknown state.")
    try:
        verified = await verify_github_pages_html(html_content=asset.body, settings=settings)
    except Exception as exc:
        if isinstance(exc, GitHubPagesConfigurationError):
            raise HTTPException(409, str(exc)) from exc
        raise HTTPException(502, "Could not verify the remote GitHub Pages file. The outcome remains unknown.") from exc

    actor = str(user.get("email") or user.get("user_id") or "unknown")[:320]
    if verified["matches_expected_content"]:
        result = {
            "asset_id": asset.id,
            "status": "completed",
            "deployment_status": "published",
            "reconciled": True,
            "repository": verified["repository"],
            "branch": verified["branch"],
            "content_path": verified["content_path"],
            "published_url": verified["published_url"],
            "page_sha256": verified["page_sha256"],
            "file_sha": verified.get("file_sha"),
        }
        action.status = "completed"
        action.result_json = result
        action.remote_id = str(verified.get("file_sha") or "")[:255] or None
        action.error_type = None
        metadata["github_pages_publication"] = {
            **publication,
            "status": "published",
            "repository": verified["repository"],
            "branch": verified["branch"],
            "content_path": verified["content_path"],
            "published_url": verified["published_url"],
            "page_sha256": verified["page_sha256"],
            "file_sha": verified.get("file_sha"),
            "reconciled": True,
            "verified_at": utcnow().isoformat(),
        }
        asset.metadata_json = metadata
        outcome = "verified_match"
    else:
        # A different file does not prove that the original commit never landed;
        # keep the action unknown until branch history is reviewed by an operator.
        outcome = "still_unknown"
        publication["last_reconciled_at"] = utcnow().isoformat()
        publication["remote_file_matches_expected"] = False
        metadata["github_pages_publication"] = publication
        asset.metadata_json = metadata
        result = {
            "asset_id": asset.id,
            "status": "outcome_unknown",
            "reconciled": False,
            "remote_file_matches_expected": False,
            "message": "The remote file does not match this artifact. The action remains unresolved; inspect the configured branch commit history before retrying.",
        }
    db.add(AuditLog(
        workspace_id=workspace_id, actor=actor,
        action="github_pages.deploy.reconciled", resource_type="content_asset", resource_id=asset.id,
        outcome=outcome,
        details_json={
            "action_id": action_id,
            "page_sha256": verified["page_sha256"],
            "remote_file_matches_expected": verified["matches_expected_content"],
            "provider_action_executed": False,
        },
    ))
    await db.commit()
    return result


@api.get("/audit")
async def audit(
    limit: int = Query(100, ge=1, le=500),
    user: dict[str, Any] = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing audit logs")
    rows = list((await db.scalars(
        select(AuditLog).where(AuditLog.workspace_id == str(workspace_id))
        .order_by(AuditLog.created_at.desc()).limit(limit)
    )).all())
    return {"count": len(rows), "data": [
        {"id": x.id, "actor": x.actor, "action": x.action, "resource_type": x.resource_type,
         "resource_id": x.resource_id, "outcome": x.outcome, "details": x.details_json,
         "created_at": x.created_at.isoformat() if x.created_at else None}
        for x in rows
    ]}
@api.get("/admin/overview")
async def platform_admin_overview(
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    # This is an explicitly authorized cross-tenant view. It is read-only and
    # does not claim that the queue, deployment, or providers are production-verified.
    with workspace_scope(None):
        users = int(await db.scalar(select(func.count(UserAccount.id))) or 0)
        workspaces = int(await db.scalar(select(func.count(Workspace.id))) or 0)
        memberships = int(await db.scalar(select(func.count(WorkspaceMembership.id)).where(WorkspaceMembership.is_active.is_(True))) or 0)
        workflows = int(await db.scalar(select(func.count(WorkflowRun.id)) ) or 0)
        audit_events = int(await db.scalar(select(func.count(AuditLog.id))) or 0)
        workflow_rows = (await db.execute(select(WorkflowRun.status, func.count(WorkflowRun.id)).group_by(WorkflowRun.status))).all()
    registry = build_network_registry(settings.load_yaml())
    provider_status_counts: dict[str, int] = {}
    for item in registry.get("items", []):
        label = str(item.get("status") or "unknown")
        provider_status_counts[label] = provider_status_counts.get(label, 0) + 1
    return {
        "access_scope": "platform_admin",
        "read_only": True,
        "counts": {
            "users": users,
            "workspaces": workspaces,
            "active_workspace_memberships": memberships,
            "workflow_runs_persisted": workflows,
            "audit_events_persisted": audit_events,
        },
        "workflow_status_counts": {str(label or "unknown"): int(count) for label, count in workflow_rows},
        "provider_status_counts": provider_status_counts,
        "runtime": {
            "environment": settings.app_env,
            "scheduler_running": bool(scheduler.running),
            "publishing_dry_run": bool(settings.publishing_dry_run),
            "ad_automation_execute": bool(settings.ad_automation_execute),
            "durable_queue_status": "not_verified_by_this_endpoint",
        },
        "release": {
            "deployment_verification": "not_asserted",
            "note": "This endpoint reports database/runtime observations only; it is not deployment or release certification.",
        },
    }


async def _apply_workspace_lifecycle(
    workspace_id: str,
    payload: WorkspaceLifecycleActionRequest,
    user: dict[str, Any],
    db: AsyncSession,
    *,
    suspend: bool,
) -> dict[str, Any]:
    actor = str(user.get("email") or user.get("user_id") or "platform-admin")[:320]
    if suspend and str(user.get("workspace_id") or "") == workspace_id:
        raise HTTPException(409, "Switch to a different active workspace before suspending this administrative workspace.")

    now = utcnow()
    action = "suspended" if suspend else "reinstated"
    with workspace_scope(None):
        workspace = await db.scalar(select(Workspace).where(Workspace.id == workspace_id).with_for_update())
        if workspace is None:
            raise HTTPException(404, "Workspace not found")
        expected_state = "active" if suspend else "suspended"
        if workspace.lifecycle_state != expected_state:
            if suspend and workspace.lifecycle_state == "suspended":
                raise HTTPException(409, "Workspace is already suspended")
            if not suspend and workspace.lifecycle_state == "active":
                raise HTTPException(409, "Workspace is already active")
            raise HTTPException(409, "Workspace lifecycle state is invalid; manual review is required")

        previous_reason = workspace.suspension_reason
        workspace.lifecycle_state = "suspended" if suspend else "active"
        if suspend:
            workspace.suspended_at = now
            workspace.suspended_by = actor
            workspace.suspension_reason = payload.reason
        else:
            workspace.suspended_at = None
            workspace.suspended_by = None
            workspace.suspension_reason = None
        await db.flush()

    with workspace_scope(workspace_id):
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action="workspace.lifecycle.suspended" if suspend else "workspace.lifecycle.reinstated",
            resource_type="workspace",
            resource_id=workspace_id,
            outcome=action,
            details_json={
                "reason": payload.reason,
                "previous_state": expected_state,
                "new_state": workspace.lifecycle_state,
                "previous_suspension_reason": previous_reason if not suspend else None,
                "scheduled_jobs_excluded_while_suspended": True,
                "workflow_runner_boundary": "no new stage begins after suspension is observed",
                "in_flight_external_action_rolled_back": False,
            },
        ))
        await db.commit()

    return {
        "id": workspace.id,
        "name": workspace.name,
        "slug": workspace.slug,
        "lifecycle_state": workspace.lifecycle_state,
        "suspended_at": workspace.suspended_at.isoformat() if workspace.suspended_at else None,
        "suspended_by": workspace.suspended_by,
        "suspension_reason": workspace.suspension_reason,
        "active_workspace_id": user.get("workspace_id"),
    }


def _platform_execution_control_payload(control: PlatformExecutionControl) -> dict[str, Any]:
    return {
        "id": control.id,
        "outbound_actions_paused": bool(control.outbound_actions_paused),
        "reason": control.reason,
        "changed_by": control.changed_by,
        "changed_at": control.changed_at.isoformat() if control.changed_at else None,
        "enforcement_scope": (
            "ExternalAction registry claims for social/CMS/bio-link/GitHub Pages writes, plus direct Resend "
            "claims for scheduled marketing email and double-opt-in confirmation email"
        ),
        "completed_idempotency_replays_allowed": True,
        "in_flight_actions_cancelled": False,
        "note": (
            "This pause blocks new social, CMS, bio-link and GitHub Pages actions using the shared ExternalAction "
            "registry, and new scheduled-marketing or double-opt-in confirmation email sends using the same "
            "transactional control-row gate. Completed registry idempotency replays may return prior results. "
            "Actions already durably claimed/in flight are not cancelled or rolled back. Provider mutation paths "
            "not integrated with either gate remain outside this pause and require their own execution controls."
        ),
    }


@api.get("/admin/execution-control")
async def get_platform_execution_control(
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    with workspace_scope(None):
        control = await db.get(PlatformExecutionControl, 1)
    if control is None:
        raise HTTPException(503, detail={
            "code": "PLATFORM_EXECUTION_CONTROL_UNAVAILABLE",
            "message": "Global provider-write control record is missing; provider writes fail closed.",
        })
    return _platform_execution_control_payload(control)


@api.post("/admin/execution-control")
async def update_platform_execution_control(
    payload: PlatformExecutionControlChangeRequest,
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    audit_workspace_id = str(user.get("workspace_id") or "").strip()
    if not audit_workspace_id:
        raise HTTPException(403, "Select an active workspace to anchor the platform-control audit record")
    actor = str(user.get("email") or user.get("user_id") or "platform-admin")[:320]
    with workspace_scope(None):
        control = await db.scalar(
            select(PlatformExecutionControl)
            .where(PlatformExecutionControl.id == 1)
            .with_for_update()
        )
        if control is None:
            raise HTTPException(503, detail={
                "code": "PLATFORM_EXECUTION_CONTROL_UNAVAILABLE",
                "message": "Global provider-write control record is missing; provider writes fail closed.",
            })
        previous_paused = bool(control.outbound_actions_paused)
        control.outbound_actions_paused = payload.outbound_actions_paused
        control.reason = payload.reason
        control.changed_by = actor
        control.changed_at = utcnow()
        await db.flush()

    action = "platform.outbound_actions.paused" if payload.outbound_actions_paused else "platform.outbound_actions.resumed"
    with workspace_scope(audit_workspace_id):
        db.add(AuditLog(
            workspace_id=audit_workspace_id,
            actor=actor,
            action=action,
            resource_type="platform_execution_control",
            resource_id="1",
            outcome="changed" if previous_paused != payload.outbound_actions_paused else "no_op",
            details_json={
                "global_control": True,
                "previous_paused": previous_paused,
                "new_paused": payload.outbound_actions_paused,
                "reason": payload.reason,
                "enforcement_scope": "external_action_registry_new_claims",
                "completed_idempotency_replays_allowed": True,
                "in_flight_actions_cancelled": False,
            },
        ))
        await db.commit()
    return _platform_execution_control_payload(control)


@api.get("/admin/tenants")
async def platform_admin_tenants(
    limit: int = Query(100, ge=1, le=500),
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    with workspace_scope(None):
        rows = list((await db.scalars(select(Workspace).order_by(Workspace.created_at.desc()).limit(limit))).all())
        membership_rows = (await db.execute(
            select(WorkspaceMembership.workspace_id, func.count(WorkspaceMembership.id))
            .where(WorkspaceMembership.is_active.is_(True))
            .group_by(WorkspaceMembership.workspace_id)
        )).all()
    member_counts = {str(workspace_id): int(count) for workspace_id, count in membership_rows}
    return {
        "count": len(rows),
        "limit": limit,
        "read_only": True,
        "lifecycle_mutations_available": True,
        "active_workspace_id": user.get("workspace_id"),
        "data": [
            {
                "id": row.id,
                "name": row.name,
                "slug": row.slug,
                "owner_user_id": row.owner_user_id,
                "active_memberships": member_counts.get(str(row.id), 0),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "lifecycle_state": row.lifecycle_state,
                "suspended_at": row.suspended_at.isoformat() if row.suspended_at else None,
                "suspended_by": row.suspended_by,
                "suspension_reason": row.suspension_reason,
            }
            for row in rows
        ],
    }


@api.post("/admin/tenants/{workspace_id}/suspend")
async def suspend_workspace(
    workspace_id: str,
    payload: WorkspaceLifecycleActionRequest,
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    return await _apply_workspace_lifecycle(workspace_id, payload, user, db, suspend=True)


@api.post("/admin/tenants/{workspace_id}/reinstate")
async def reinstate_workspace(
    workspace_id: str,
    payload: WorkspaceLifecycleActionRequest,
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    return await _apply_workspace_lifecycle(workspace_id, payload, user, db, suspend=False)


@api.get("/admin/workflows")
async def platform_admin_workflows(
    limit: int = Query(100, ge=1, le=500),
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    with workspace_scope(None):
        rows = list((await db.scalars(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(limit))).all())
    return {
        "count": len(rows),
        "limit": limit,
        "read_only": True,
        "data": [
            {
                "id": row.id,
                "workspace_id": row.workspace_id,
                "workflow_name": row.workflow_name,
                "status": row.status,
                "current_step": row.current_step,
                "execution_mode": row.execution_mode,
                "has_error": bool(row.error_message),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            }
            for row in rows
        ],
    }


@api.get("/admin/audit")
async def platform_admin_audit(
    limit: int = Query(100, ge=1, le=500),
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    with workspace_scope(None):
        rows = list((await db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))).all())
    return {
        "count": len(rows),
        "limit": limit,
        "read_only": True,
        "data": [
            {
                "id": row.id,
                "workspace_id": row.workspace_id,
                "actor": row.actor,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "outcome": row.outcome,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }


app.include_router(api)

UNSUBSCRIBE_LINK_MAX_AGE_SECONDS = 31_536_000
UNSUBSCRIBE_POST_BODY_LIMIT = 4096
UNSUBSCRIBE_RESPONSE_HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
}


def _validate_unsubscribe_signature(lead_id: str, ts: int, sig: str) -> None:
    if abs(int(time.time()) - ts) > UNSUBSCRIBE_LINK_MAX_AGE_SECONDS:
        raise HTTPException(410, "Unsubscribe link expired")
    secret = settings.tracking_hmac_secret or settings.app_session_secret
    expected = hmac.new(
        secret.encode(),
        f"unsubscribe:{lead_id}:{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(403, "Invalid unsubscribe signature")


async def _validate_unsubscribe_post_body(request: Request) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(415, "Unsubscribe POST requires form-urlencoded content")

    raw_length = request.headers.get("content-length")
    if raw_length is not None:
        try:
            declared_length = int(raw_length)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "Invalid unsubscribe request length") from exc
        if declared_length < 0:
            raise HTTPException(400, "Invalid unsubscribe request length")
        if declared_length > UNSUBSCRIBE_POST_BODY_LIMIT:
            raise HTTPException(413, "Unsubscribe request body exceeds the size limit")

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > UNSUBSCRIBE_POST_BODY_LIMIT:
            raise HTTPException(413, "Unsubscribe request body exceeds the size limit")
        body.extend(chunk)
    try:
        encoded = bytes(body).decode("ascii")
        fields = parse_qsl(
            encoded,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=2,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(400, "Invalid unsubscribe request body") from exc

    # RFC 8058 one-click clients send List-Unsubscribe=One-Click. Browser
    # confirmation uses the single explicit confirm=unsubscribe field below.
    if fields not in ([("List-Unsubscribe", "One-Click")], [("confirm", "unsubscribe")]):
        raise HTTPException(400, "Unsubscribe confirmation is required")


def _unsubscribe_response(title: str, message: str, form_action: str | None = None) -> HTMLResponse:
    if form_action is None:
        action_html = ""
    else:
        safe_action = html_escape(form_action, quote=True)
        action_html = (
            f'<form method="post" action="{safe_action}">'
            '<input type="hidden" name="confirm" value="unsubscribe">'
            '<button type="submit">Unsubscribe</button></form>'
        )
    body = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html_escape(title)}</title></head><body>"
        f"<main><h1>{html_escape(title)}</h1><p>{html_escape(message)}</p>"
        f"{action_html}</main></body></html>"
    )
    return HTMLResponse(body, headers=UNSUBSCRIBE_RESPONSE_HEADERS)


def _email_consent_confirmation_response(title: str, message: str, token: str | None = None) -> HTMLResponse:
    action_html = ""
    if token is not None:
        safe_token = html_escape(token, quote=True)
        action_html = (
            '<form method="post" action="/email-consent/confirm">'
            f'<input type="hidden" name="token" value="{safe_token}">'
            '<input type="hidden" name="confirm" value="yes">'
            '<button type="submit">Confirm email subscription</button></form>'
        )
    body = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html_escape(title)}</title></head><body>"
        f"<main><h1>{html_escape(title)}</h1><p>{html_escape(message)}</p>"
        f"{action_html}</main></body></html>"
    )
    return HTMLResponse(body, headers={
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Robots-Tag": "noindex, nofollow",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'",
    })


@app.get("/email-consent/confirm")
async def email_consent_confirmation_page(
    request: Request,
    token: str = Query(..., min_length=32, max_length=128),
    db: AsyncSession = Depends(get_session),
):
    """Scanner-safe GET: display an explicit form without changing consent state."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        raise HTTPException(403, "Invalid or expired confirmation link")
    await public_rate_limit(request)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with workspace_scope(None):
        row = await db.scalar(select(EmailConsentConfirmation).where(EmailConsentConfirmation.token_hash == token_hash))
    if row is None or row.status != "sent":
        raise HTTPException(410, "Confirmation link is no longer valid")
    expiry = row.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        return _email_consent_confirmation_response(
            "Confirmation link expired", "Request a fresh confirmation email to continue."
        )
    return _email_consent_confirmation_response(
        "Confirm email subscription",
        "Confirm your email address only if you requested this subscription. Opening this page does not change your consent.",
        token,
    )


@app.post("/email-consent/confirm")
async def email_consent_confirmation_submit(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Explicit POST confirms a one-time token; GET requests never change subscription state."""
    await public_rate_limit(request)
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/x-www-form-urlencoded":
        raise HTTPException(415, "Submit the explicit confirmation form")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "Invalid Content-Length") from exc
        if declared_length < 0:
            raise HTTPException(400, "Invalid Content-Length")
        if declared_length > 4096:
            raise HTTPException(413, "Confirmation form is too large")
    body = await request.body()
    if len(body) > 4096:
        raise HTTPException(413, "Confirmation form is too large")
    try:
        fields = parse_qsl(body.decode("utf-8"), keep_blank_values=True, strict_parsing=True, max_num_fields=4)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(400, "Invalid confirmation form") from exc
    values = dict(fields)
    if len(values) != len(fields) or values.get("confirm") != "yes":
        raise HTTPException(400, "Explicit confirmation is required")
    try:
        await confirm_email_consent(db, values.get("token", ""))
    except ValueError as exc:
        message = str(exc).lower()
        code = 410 if "expired" in message or "no longer valid" in message or "already used" in message else 409
        raise HTTPException(code, "Confirmation could not be applied. Request a fresh confirmation email if needed.") from exc
    return _email_consent_confirmation_response(
        "Email address confirmed",
        "Your email address has been confirmed. The requested email sequence has been considered for scheduling.",
    )


@api.post("/leads/{lead_id}/consent-confirmation/resend")
async def resend_lead_consent_confirmation(
    lead_id: str,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = str(user.get("workspace_id") or "").strip()
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before resending confirmation")
    if str(user.get("workspace_role") or "") not in {"owner", "admin"}:
        raise HTTPException(403, "Only a workspace owner or admin may resend consent confirmation")
    if not getattr(settings, "email_double_opt_in_required", False):
        raise HTTPException(409, "Email double opt-in is not enabled")
    try:
        with workspace_scope(workspace_id):
            return await resend_email_consent_confirmation(db, workspace_id=workspace_id, lead_id=lead_id)
    except ConsentConfirmationDeliveryUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/unsubscribe/{lead_id}")
async def unsubscribe_confirmation(lead_id: str, ts: int = Query(...), sig: str = Query(...)):
    """Validate a signed unsubscribe link without mutating consent on a scanner-friendly GET."""
    _validate_unsubscribe_signature(lead_id, ts, sig)
    action = f"/unsubscribe/{lead_id}?ts={ts}&sig={sig}"
    return _unsubscribe_response(
        "Confirm unsubscribe",
        "Open this page only if you want to stop receiving marketing email. Select Unsubscribe to confirm. Opening the link alone does not change your preferences.",
        action,
    )


@app.post("/unsubscribe/{lead_id}")
async def unsubscribe_confirmed(
    lead_id: str,
    request: Request,
    ts: int = Query(...),
    sig: str = Query(...),
    db: AsyncSession = Depends(get_session),
):
    """Apply a signed opt-out only through explicit browser confirmation or RFC 8058 one-click POST."""
    _validate_unsubscribe_signature(lead_id, ts, sig)
    await _validate_unsubscribe_post_body(request)
    if not await unsubscribe_lead(db, lead_id):
        raise HTTPException(404, "Lead not found")
    return _unsubscribe_response(
        "You are unsubscribed",
        "No further email sequence messages will be sent. This preference has been recorded.",
    )
MAX_AFFILIATE_WEBHOOK_BODY_BYTES = 256 * 1024


async def read_limited_webhook_body(request: Request, limit: int = MAX_AFFILIATE_WEBHOOK_BODY_BYTES) -> bytes:
    """Read a signed provider webhook with a strict byte limit, including streamed bodies."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "Invalid Content-Length") from exc
        if declared_length < 0:
            raise HTTPException(400, "Invalid Content-Length")
        if declared_length > limit:
            raise HTTPException(413, "Affiliate webhook body exceeds the size limit")

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise HTTPException(413, "Affiliate webhook body exceeds the size limit")
        body.extend(chunk)
    return bytes(body)


def get_affiliate_webhook_secret(network: str) -> str | None:
    """Resolve a network-specific secret; a configured map disables shared-secret fallback."""
    network_key = network.strip().lower()
    configured = settings.affiliate_webhook_secrets or {}
    if configured:
        selected = next(
            (secret for key, secret in configured.items() if str(key).strip().lower() == network_key),
            None,
        )
        return selected if isinstance(selected, str) and len(selected) >= 32 else None
    legacy = settings.affiliate_webhook_secret
    return legacy if isinstance(legacy, str) and len(legacy) >= 32 else None


@app.post("/api/webhooks/resend/email-events", status_code=200)
async def receive_resend_email_delivery_event(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Verify and apply Resend outcomes using the exact raw request body."""
    secret = str(getattr(settings, "resend_webhook_secret", "") or "").strip()
    if not is_resend_webhook_secret_configured(secret):
        raise HTTPException(503, "Resend webhook verification is not configured")

    raw_body = await read_limited_webhook_body(request)
    svix_id = request.headers.get("svix-id", "")
    svix_timestamp = request.headers.get("svix-timestamp", "")
    svix_signature = request.headers.get("svix-signature", "")
    if not verify_resend_webhook_signature(
        raw_body, secret=secret, svix_id=svix_id,
        svix_timestamp=svix_timestamp, svix_signature=svix_signature,
    ):
        raise HTTPException(401, "Invalid Resend webhook signature")
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "Signed Resend webhook body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(422, "Signed Resend webhook body must be a JSON object")
    try:
        return await process_resend_email_event(
            db, provider_event_id=svix_id, payload=payload,
            payload_sha256=hashlib.sha256(raw_body).hexdigest(),
        )
    except UnmatchedResendMessageError as exc:
        # Ask Resend to retry if its callback races the sender's message-ID commit.
        raise HTTPException(503, "Resend message is not yet correlated; retry delivery later") from exc
    except (AmbiguousResendMessageError, ConflictingResendEventError) as exc:
        raise HTTPException(409, "Resend event conflicts with an internal delivery record") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/webhooks/conversions/{network}")
async def conversion_webhook(network:str,request:Request,db:AsyncSession=Depends(get_session)):
 net=network.strip().lower()
 if not net or len(net)>100:raise HTTPException(422,"Network must contain 1-100 characters")
 secret=get_affiliate_webhook_secret(net)
 if not secret:raise HTTPException(503,"Affiliate webhook secret is not configured for this network")
 body=await read_limited_webhook_body(request)
 try:adapter=AggregatorWebhookAdapter(net,secret)
 except ValueError as exc:raise HTTPException(503,"Affiliate webhook secret is not configured") from exc
 if not adapter.verify(body,request.headers.get("X-Affiliate-Signature","")):raise HTTPException(401,"Invalid webhook signature")
 try:p=json.loads(body)
 except (json.JSONDecodeError,UnicodeDecodeError) as exc:raise HTTPException(400,"Webhook must contain valid JSON") from exc
 if not isinstance(p,dict):raise HTTPException(422,"Webhook must be a JSON object")
 # Keep legacy provider event aliases, but validate every event through the same adapter.
 if not (p.get("event_id") or p.get("transaction_id")) and p.get("id"):p["event_id"]=p["id"]
 if not (p.get("status") or p.get("event_type")):p["status"]="pending"
 elif not p.get("status"):p["status"]=p["event_type"]
 try:event=adapter.parse_conversion(p)
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc
 eid=event["external_event_id"];click_id=str(event.get("click_id") or "").strip()
 if not click_id:raise HTTPException(422,"A known first-party click_id is required to resolve the workspace")
 if len(click_id)>80:raise HTTPException(422,"click_id must be 80 characters or fewer")
 # Provider-signed events are resolved globally by click id before a tenant context is bound.
 set_workspace_id(None)
 click=await db.scalar(select(ClickEvent).where(ClickEvent.click_id==click_id))
 if click is None or not click.workspace_id:
  return JSONResponse(status_code=202,content={"status":"unmatched_quarantined","stored":False,"reason":"The click id cannot be mapped to a workspace."})
 set_workspace_id(click.workspace_id)
 if await db.scalar(select(Conversion.id).where(Conversion.network==net,Conversion.external_event_id==eid)):return {"status":"duplicate_ignored"}
 currency = str(p.get("currency") or "USD").strip().upper()
 if len(currency) != 3 or not currency.isalpha():
  raise HTTPException(422, "currency must be a three-letter code")
 status = event["status"]
 partial_reversal = status in {"partial_refund", "partial_reversal", "partial_chargeback"}
 reversal = partial_reversal or status in {"reversed", "refunded", "chargeback", "clawback", "reversal", "commission_reversal"}
 commission = Decimal(str(event["commission"]))
 revenue = Decimal(str(event["revenue"]))
 original_id = str(p.get("original_event_id") or p.get("parent_transaction_id") or "").strip()
 if len(original_id) > 255:
  raise HTTPException(422, "original_event_id must be 255 characters or fewer")
 remaining_commission = None
 remaining_revenue = None
 if reversal:
  original_network = str(p.get("original_network") or net).lower()
  parent = await db.scalar(
   select(Conversion)
   .where(Conversion.network == original_network, Conversion.external_event_id == original_id)
   .with_for_update()
  ) if original_id else None
  if partial_reversal and parent is None:
   raise HTTPException(422, "Partial reversal requires a known original conversion")
  if parent and parent.status == "reversed":
   return {"status": "duplicate_reversal_ignored", "original_event_id": original_id}
  if parent:
   parent_currency = str(getattr(parent, "currency", currency) or currency).upper()
   if parent_currency != currency:
    raise HTTPException(422, "Reversal currency must match the original conversion")
   prior_commission = Decimal("0")
   prior_revenue = Decimal("0")
   if parent.status == "partially_reversed":
    prior_commission = Decimal(str(await db.scalar(
     select(func.coalesce(func.sum(ConversionLedgerEntry.commission_amount), 0)).where(
      ConversionLedgerEntry.workspace_id == click.workspace_id,
      ConversionLedgerEntry.network == net,
      ConversionLedgerEntry.entry_type == "reversal",
      ConversionLedgerEntry.original_event_id == original_id,
     )
    ) or 0))
    prior_revenue = Decimal(str(await db.scalar(
     select(func.coalesce(func.sum(ConversionLedgerEntry.revenue_amount), 0)).where(
      ConversionLedgerEntry.workspace_id == click.workspace_id,
      ConversionLedgerEntry.network == net,
      ConversionLedgerEntry.entry_type == "reversal",
      ConversionLedgerEntry.original_event_id == original_id,
     )
    ) or 0))
   remaining_commission = max(abs(Decimal(str(parent.commission or 0))) + prior_commission, Decimal("0"))
   remaining_revenue = max(abs(Decimal(str(parent.revenue or 0))) + prior_revenue, Decimal("0"))
   if partial_reversal:
    requested_commission = commission
    requested_revenue = revenue
    if requested_commission == 0 and requested_revenue == 0:
     raise HTTPException(422, "Partial reversal must include a commission or revenue amount")
    if requested_commission > remaining_commission or requested_revenue > remaining_revenue:
     raise HTTPException(422, "Partial reversal exceeds the remaining original amounts")
    commission = -requested_commission
    revenue = -requested_revenue
    remaining_commission -= requested_commission
    remaining_revenue -= requested_revenue
    status = "reversed" if remaining_commission == 0 and remaining_revenue == 0 else "partially_reversed"
    parent.status = status
   else:
    if remaining_commission == 0 and remaining_revenue == 0:
     return {"status": "duplicate_reversal_ignored", "original_event_id": original_id}
    commission = -remaining_commission
    revenue = -remaining_revenue
    remaining_commission = Decimal("0")
    remaining_revenue = Decimal("0")
    status = "reversed"
    parent.status = "reversed"
  else:
   if not commission and not revenue:
    raise HTTPException(422, "Unmatched reversal must include commission or revenue offset")
   if partial_reversal:
    raise HTTPException(422, "Partial reversal requires a known original conversion")
   commission = -abs(commission)
   revenue = -abs(revenue)
   status = "reversal_unmatched"
 row = Conversion(
  workspace_id=click.workspace_id, network=net, external_event_id=eid, click_id=click_id,
  utm_source=p.get("utm_source"), utm_medium=p.get("utm_medium"), utm_campaign=p.get("utm_campaign"),
  utm_content=p.get("utm_content"), hook=p.get("hook") or p.get("utm_content"),
  commission=float(commission), revenue=float(revenue), currency=currency, status=status,
  event_json={**p, "reversal": reversal, "partial_reversal": partial_reversal, "original_event_id": original_id or None},
 )
 ledger_row = ConversionLedgerEntry(
  workspace_id=click.workspace_id, network=net, external_event_id=eid, click_id=click_id,
  entry_type="reversal" if reversal else "conversion", original_event_id=original_id or None,
  commission_amount=commission, revenue_amount=revenue, currency=currency, status=status,
  evidence_status="signed_webhook_verified",
  source_event_json={**p, "reversal": reversal, "partial_reversal": partial_reversal, "original_event_id": original_id or None},
  observed_at=datetime.now(timezone.utc),
 )
 db.add(row)
 db.add(ledger_row)
 try:
  await db.commit()
 except IntegrityError as exc:
  await db.rollback()
  duplicate = await db.scalar(select(Conversion.id).where(Conversion.network == net, Conversion.external_event_id == eid))
  if duplicate:
   return {"status": "duplicate_ignored"}
  raise HTTPException(409, "Conversion could not be persisted because of an integrity conflict") from exc
 response = {
  "status": "recorded", "conversion_id": row.id, "reversal": reversal,
  "commission_adjustment": float(commission), "revenue_adjustment": float(revenue),
 }
 if remaining_commission is not None and remaining_revenue is not None:
  response["remaining_commission"] = format(remaining_commission.normalize(), "f")
  response["remaining_revenue"] = format(remaining_revenue.normalize(), "f")
 return response
@app.get("/r/{campaign_id}")
async def redirect_campaign(campaign_id:str,request:Request,db:AsyncSession=Depends(get_session)):
 with workspace_scope(None):
  campaign=await db.get(Campaign,campaign_id)
 if not campaign or not campaign.is_active:raise HTTPException(404,"Campaign not found/inactive")
 utm={k:v for k,v in request.query_params.items() if k.startswith("utm_") or k in {"gclid","fbclid","ref"}}
 if not campaign.workspace_id: raise HTTPException(404, "Campaign not found")
 with workspace_scope(campaign.workspace_id):
  result=await record_click_and_resolve(db,campaign,user_agent=request.headers.get("user-agent",""),utm=utm)
  await db.commit()
 if not result["destination"]: raise HTTPException(503,detail={"message":"Primary and fallback destinations unavailable; no redirect performed.","reason":result["health_error"]})
 url=urlparse(result["destination"]);query=dict(parse_qsl(url.query,keep_blank_values=True));query[campaign.tracking_parameter]=result["click_id"]
 final=urlunparse(url._replace(query=urlencode(query)));return RedirectResponse(final,status_code=302,headers={"Cache-Control":"no-store","Referrer-Policy":"strict-origin-when-cross-origin"})
@app.websocket("/ws")
async def websocket(ws:WebSocket):
 session=ws.scope.get("session") or {}
 user=session.get("user") if isinstance(session,dict) else None
 workspace_id=user.get("workspace_id") if isinstance(user,dict) else None
 user_id=user.get("user_id") if isinstance(user,dict) else None
 if not isinstance(user,dict):
  if settings.app_env=="production":
   await ws.close(code=1008,reason="Authentication required");return
  with workspace_scope(None):
   async with SessionLocal() as db:
    workspace=await db.scalar(select(Workspace).where(Workspace.slug=="local-development"))
  workspace_id=workspace.id if workspace else None
 elif not workspace_id or not user_id:
  await ws.close(code=1008,reason="Workspace authentication required");return
 elif user_id=="local":
  if settings.app_env=="production":
   await ws.close(code=1008,reason="Workspace membership required");return
  with workspace_scope(None):
   async with SessionLocal() as db:
    workspace=await db.scalar(select(Workspace).where(Workspace.id==str(workspace_id),Workspace.slug=="local-development"))
  if workspace is None:
   await ws.close(code=1008,reason="Workspace membership required");return
  workspace_id=workspace.id
 else:
  with workspace_scope(None):
   async with SessionLocal() as db:
    membership=await db.scalar(select(WorkspaceMembership).where(
     WorkspaceMembership.workspace_id==str(workspace_id),
     WorkspaceMembership.user_id==str(user_id),
     WorkspaceMembership.is_active.is_(True),
    ))
  if membership is None:
   await ws.close(code=1008,reason="Workspace membership is no longer active");return
  workspace_id=membership.workspace_id
 await hub.connect(ws,str(workspace_id) if workspace_id else None)
 try:
  while True:
   if await ws.receive_text()=="ping":await ws.send_text(json.dumps({"event":"PONG","time":utcnow().isoformat()}))
 except WebSocketDisconnect:await hub.disconnect(ws)
 except Exception:await hub.disconnect(ws)

async def _record_finance_email_import_audit(
    db: AsyncSession,
    *,
    user: dict[str, Any],
    workspace_id: str,
    outcome: str,
    result: dict[str, Any] | None = None,
    error_type: str | None = None,
) -> None:
    details: dict[str, Any] = {"provider": "imap", "mailbox": "INBOX"}
    if result is not None:
        details.update({
            "messages_matched": int(result.get("messages_matched") or 0),
            "rows_created": int(result.get("rows_created") or 0),
        })
    if error_type:
        details["error_type"] = error_type[:120]
    with workspace_scope(workspace_id):
        db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(user.get("email") or user.get("user_id") or "unknown")[:320],
            action="finance.email_import",
            resource_type="commission_mail_import",
            outcome=outcome[:80],
            details_json=details,
        ))
        await db.commit()


@api.post("/finance/email-import")
async def commission_email_import(
    user: dict[str, Any] = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_session),
):
    # IMAP credentials and sender allowlist are global deployment settings.
    # Restrict access to the platform operator; workspace admins must not import
    # a shared mailbox into their own tenant.
    from backend.services.commission_mail_importer import import_commission_emails

    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before importing commission evidence")
    owner_workspace_id = str(workspace_id)
    try:
        result = await import_commission_emails(workspace_id=owner_workspace_id)
    except Exception as exc:
        try:
            await _record_finance_email_import_audit(
                db,
                user=user,
                workspace_id=owner_workspace_id,
                outcome="failed",
                error_type=type(exc).__name__,
            )
        except Exception:
            logger.exception("Could not audit failed IMAP commission import for workspace %s", owner_workspace_id[:8])
        raise HTTPException(502, f"Mail import failed: {type(exc).__name__}: {str(exc)[:200]}") from exc

    await _record_finance_email_import_audit(
        db,
        user=user,
        workspace_id=owner_workspace_id,
        outcome="completed",
        result=result,
    )
    return result

@api.get("/finance/mail-commissions")
async def mail_commissions(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing commission evidence")
    rows = list((await db.scalars(
        select(MailCommission).where(MailCommission.workspace_id == str(workspace_id))
        .order_by(MailCommission.created_at.desc()).limit(300)
    )).all())
    return {"count": len(rows), "data": [
        {"id": x.id, "network": x.network, "commission": x.commission, "currency": x.currency,
         "status": x.status, "email_date": x.email_date.isoformat() if x.email_date else None,
         "subject": x.parsed_subject, "evidence": x.evidence_json}
        for x in rows
    ]}


@api.get("/finance/reconciliation")
async def finance_reconciliation(
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    """Show candidate links between commission emails and tracked conversions.

    This endpoint is read-only and intentionally does not mark a payout as received.
    Workspace filters are explicit here as defense in depth alongside ORM tenant scope.
    """
    from backend.services.commission_reconciliation import build_commission_reconciliation

    workspace_id = user.get("workspace_id")
    if not workspace_id:
        raise HTTPException(403, "Select an authorized workspace before viewing financial reconciliation")

    mail_rows = list((await db.scalars(
        select(MailCommission)
        .where(MailCommission.workspace_id == str(workspace_id))
        .order_by(MailCommission.created_at.desc())
        .limit(300)
    )).all())
    conversion_rows = list((await db.scalars(
        select(Conversion)
        .where(Conversion.workspace_id == str(workspace_id))
        .order_by(Conversion.created_at.desc())
        .limit(1000)
    )).all())
    evidence = [{
        "id": row.id,
        "network": row.network,
        "commission": row.commission,
        "currency": row.currency,
        "status": row.status,
    } for row in mail_rows]
    conversions = [{
        "id": row.id,
        "network": row.network,
        "commission": row.commission,
        "currency": row.currency,
        "status": row.status,
    } for row in conversion_rows]
    report = build_commission_reconciliation(evidence, conversions)
    report["workspace_id"] = str(workspace_id)
    return report

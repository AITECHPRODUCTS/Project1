from __future__ import annotations
import asyncio,base64,hashlib,hmac,json,logging,re,secrets,time
from contextlib import asynccontextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import parse_qsl,urlencode,urlparse,urlunparse
from typing import Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter,Depends,FastAPI,HTTPException,Query,Request,WebSocket,WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse,JSONResponse,RedirectResponse
from pwdlib import PasswordHash
from sqlalchemy import func,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware
from backend.tenancy import WorkspaceContextMiddleware, get_workspace_id, set_workspace_id, workspace_scope
from backend.config import get_settings
from backend.core.events import hub
from backend.core.middleware import CSRFMiddleware, FinancialSandboxMiddleware
from backend.core.state_machine import runner
from backend.database import SessionLocal,close_db,get_session,init_db
from backend.models import AdCampaignPlanRecord,AdPerformanceObservation,AuditLog,Campaign,ClickEvent,ContentAsset,Conversion,ExperimentAssignment,ExperimentEvent,Lead,MailCommission,Offer,PayoutThreshold,PausedSession,ScheduledEmail,UserAccount,WorkflowRun,Workspace,WorkspaceMembership
from backend.adapters.webhook import AggregatorWebhookAdapter
from backend.schemas import ABTestAssignmentRequest,AdCampaignPlanRequest,AdPerformanceObservationRequest,BlogRequest,CampaignCreateRequest,CMSPublishRequest,CompetitorRequest,CommissionEvidenceReviewRequest,ContentAngleRankRequest,ContentAtomizeRequest,ConversionRequest,ExperimentEventRequest,FundsReceivedRequest,LandingPageRequest,LeadCaptureRequest,LoginRequest,RegisterRequest,WorkspaceCreateRequest,NicheFinderRequest,PayoutThresholdCreateRequest,ResumeRequest,SocialPostRequest,TrendRequest,VideoRequest,WorkflowStartRequest
from backend.services.analytics_utils import ab_test_generator,conversion_tracker
from backend.services.ad_manager import evaluate_roas
from backend.services.ad_planner import generate_ad_campaign_plan
from backend.services.ad_performance import summarize_ad_performance
from backend.services.content_angle_ranker import rank_content_angles as rank_content_angles_service
from backend.services.cms_publisher import publish_article
from backend.services.email_delivery import capture_lead_and_schedule,send_due_emails,unsubscribe_lead
from backend.services.integration_registry import build_network_registry
from backend.services.capability_matrix import build_capability_matrix
from backend.services.offer_intelligence import compute_offer_metrics
from backend.services.resource_budget import status as budget_status
from backend.services.s1_research import competitor_spy,monopoly_niche_finder,trending_content_scout
from backend.services.s2_s3_content import affiliate_blog_builder,keyword_cluster_architect,tiktok_script_writer,viral_post_writer
from backend.services.s4_s5_landing import email_drip_sequence,grand_slam_offer_generator,social_media_scheduler,squeeze_page_builder,value_ladder_architect
from backend.services.s6_s8_analytics import self_improver_loop
from backend.services.tracking_service import choose_destination,destination_healthy,record_click_and_resolve,verify_click_signature
from backend.services.url_safety import validate_public_http_url
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
        .where(WorkspaceMembership.user_id == account.id, WorkspaceMembership.is_active.is_(True))
        .order_by(WorkspaceMembership.created_at.asc())
    )
    if membership is not None:
        return membership
    base_name = preferred_name or f"{account.email.split('@', 1)[0][:100]} workspace"
    workspace = Workspace(
        name=base_name[:160],
        slug=f"{_slugify(base_name)}-{secrets.token_hex(4)}",
        owner_user_id=account.id,
    )
    db.add(workspace)
    await db.flush()
    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=account.id,
        role="owner",
        is_active=True,
    )
    db.add(membership)
    await db.flush()
    return membership


async def bootstrap_admin():
    if not settings.initial_admin_email or not settings.initial_admin_password:
        if settings.app_env == "production":
            raise RuntimeError("Production requires initial admin credentials")
        async with SessionLocal() as db:
            dev_workspace = await db.scalar(select(Workspace).where(Workspace.slug == "local-development"))
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
        await ensure_workspace_membership(db, account, "Platform administrator workspace")
        await db.commit()
async def campaign_health_job():
 async with SessionLocal() as db:
  rows=list((await db.scalars(select(Campaign).where(Campaign.is_active.is_(True)).limit(100))).all());
  for item in rows:
   ok,code,error=await destination_healthy(item.primary_destination);item.primary_healthy=ok;item.health_last_checked_at=utcnow();item.health_last_error=None if ok else (error or f"HTTP {code}")[:1000]
   if item.fallback_destination:item.fallback_healthy=(await destination_healthy(item.fallback_destination))[0]
  await db.commit()
async def learning_job():
 try:
  async with SessionLocal() as db:
   workspace_ids=list((await db.scalars(select(Workspace.id).where(Workspace.slug!="legacy-quarantine"))).all())
  for workspace_id in workspace_ids:
   with workspace_scope(workspace_id):
    async with SessionLocal() as db:
     result=await self_improver_loop(db,lookback_days=30)
     logger.info("Performance-memory workspace %s: %s",workspace_id[:8],result)
 except Exception:
  logger.exception("Performance-memory job failed")
async def email_job():
 try:await send_due_emails()
 except Exception:logger.exception("Email sender worker failed")
async def threshold_job():
 async with SessionLocal() as db:
  rows=list((await db.scalars(select(PayoutThreshold))).all());now=utcnow()
  for row in rows:
   reached=float(row.reported_balance or 0)>=float(row.minimum_threshold or 0)
   if reached and not row.threshold_reached:row.threshold_reached=True;row.threshold_reached_at=now
   elif not reached:row.threshold_reached=False;row.threshold_reached_at=None
  await db.commit()
@asynccontextmanager
async def lifespan(app:FastAPI):
 await init_db();await hub.start(settings.redis_url);await bootstrap_admin();runner.set_resolver(resolve_steps);count=await runner.recover_paused();logger.info("Recovered paused sessions: %s",count)
 scheduler.add_job(campaign_health_job,CronTrigger(minute="*/10"),id="campaign-health",replace_existing=True,max_instances=1)
 scheduler.add_job(learning_job,CronTrigger(hour=3,minute=15),id="learning",replace_existing=True,max_instances=1)
 scheduler.add_job(email_job,"interval",minutes=5,id="email-send",replace_existing=True,max_instances=1)
 scheduler.add_job(threshold_job,CronTrigger(day_of_week="mon",hour=4),id="thresholds",replace_existing=True,max_instances=1);scheduler.start()
 yield
 scheduler.shutdown(wait=False);await hub.stop();await close_db()
docs_url="/docs" if settings.app_env != "production" else None
redoc_url="/redoc" if settings.app_env != "production" else None
openapi_url="/openapi.json" if settings.app_env != "production" else None
app=FastAPI(title=settings.app_name,version="0.1.0",description="Evidence-first RAG-backed affiliate marketing operations OS",lifespan=lifespan,docs_url=docs_url,redoc_url=redoc_url,openapi_url=openapi_url)
app.add_middleware(FinancialSandboxMiddleware)
# SessionMiddleware must wrap CSRFMiddleware so the latter can validate the signed session cookie.
app.add_middleware(CSRFMiddleware)
app.add_middleware(WorkspaceContextMiddleware)
app.add_middleware(SessionMiddleware,secret_key=settings.app_session_secret,session_cookie="affiliate_os_session",max_age=43200,same_site="lax",https_only=settings.app_env=="production")
app.add_middleware(CORSMiddleware,allow_origins=settings.allowed_origins,allow_credentials=True,allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type","X-Affiliate-Signature","X-CSRF-Token"])

async def require_auth(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if settings.app_env != "production" and not settings.initial_admin_email and not settings.api_access_token:
        workspace = await db.scalar(select(Workspace).where(Workspace.slug == "local-development"))
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


@app.get("/health")
async def health():return {"status":"ok","service":"affiliate-os-api","time":utcnow().isoformat()}
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
                  "is_active": membership.is_active, "created_at": workspace.created_at.isoformat() if workspace.created_at else None}
                 for workspace, membership in rows],
    }


@api.get("/workspaces/current")
async def current_workspace(user: dict[str, Any] = Depends(require_auth), db: AsyncSession = Depends(get_session)):
    workspace_id = user.get("workspace_id")
    workspace = await db.get(Workspace, workspace_id) if workspace_id else None
    if workspace is None:
        raise HTTPException(404, "No active workspace")
    return {"id": workspace.id, "name": workspace.name, "slug": workspace.slug, "role": user.get("workspace_role"),
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
    updated_user = dict(user)
    updated_user["workspace_id"] = workspace.id
    updated_user["workspace_role"] = membership.role
    request.session["user"] = updated_user
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    return {"active_workspace_id": workspace.id, "name": workspace.name, "role": membership.role,
            "csrf_token": request.session["csrf_token"]}


@api.get("/integrations")
async def integration_registry():
 return build_network_registry(settings.load_yaml())
@api.get("/capabilities")
async def capabilities():
    registry = build_network_registry(settings.load_yaml())
    return build_capability_matrix(settings, registry)

@api.get("/status")
async def status(db:AsyncSession=Depends(get_session)):
 clicks=int(await db.scalar(select(func.count(ClickEvent.id)) ) or 0);events=int(await db.scalar(select(func.count(Conversion.id))) or 0);commission=float(await db.scalar(select(func.coalesce(func.sum(Conversion.commission),0.0))) or 0)
 recent=list((await db.scalars(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(6))).all());path=Path(settings.chroma_persist_dir)
 indexed=path.exists() and any(path.glob("**/*"))
 model_configured=(settings.llm_backend=="openai_compatible" and bool(settings.openai_api_key)) or (settings.llm_backend=="local_transformers" and bool(settings.local_model_path))
 return {"app_name":settings.app_name,"environment":settings.app_env,"execution_mode":settings.execution_mode,"stage_count":8,"stages":[{"id":k,"label":v} for k,v in LABELS.items()],"knowledge_index_available":indexed,"api_model_configured":model_configured,"email_delivery_configured":bool(settings.resend_api_key and settings.resend_from_email),"video_rendering_available":bool(settings.pexels_api_key),"publishing_dry_run":settings.publishing_dry_run,"ad_automation_execute":settings.ad_automation_execute,"clicks":clicks,"conversion_events":events,"commission_recorded":round(commission,2),"recent_workflows":[{"session_id":x.id,"name":x.workflow_name,"status":x.status,"current_step":x.current_step,"created_at":x.created_at.isoformat() if x.created_at else None} for x in recent]}
@api.get("/flywheel/status")
async def flywheel_status(db:AsyncSession=Depends(get_session)):
 run=await db.scalar(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()))
 if not run:return {"active_session":None,"stages":[{"id":k,"label":v,"status":"idle"} for k,v in LABELS.items()]}
 states=(run.state_json or {}).get("stages",{});stages=[{"id":k,"label":v,"status":states.get(k,{}).get("status","pending"),"error":states.get(k,{}).get("error")} for k,v in LABELS.items()]
 stage_keys=list(LABELS);active=None
 if run.status=="paused" and run.current_step<len(stage_keys):active=stage_keys[run.current_step];stages[run.current_step]["status"]="waiting_for_human"
 elif run.status=="running" and run.current_step<len(stage_keys):active=stage_keys[run.current_step];stages[run.current_step]["status"]="running"
 return {"active_session":run.id,"workflow_name":run.workflow_name,"workflow_status":run.status,"current_step":run.current_step,"active_stage":active,"execution_mode":run.execution_mode,"stages":stages}
@api.post("/workflows/run",status_code=202)
async def start_workflow(payload:WorkflowStartRequest):
 try:sid=await runner.start(payload.workflow_name,payload.state,resolve_steps(payload.workflow_name),payload.execution_mode)
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc
 return {"session_id":sid,"status":"queued","workflow_name":payload.workflow_name,"execution_mode":payload.execution_mode or settings.execution_mode,"status_url":f"/api/workflows/{sid}"}
@api.get("/workflows/{session_id}")
async def workflow_status(session_id:str):
 data=await runner.status(session_id)
 if data is None:raise HTTPException(404,"Workflow session not found")
 return data
@api.post("/resume/{session_id}")
async def resume(session_id:str,payload:ResumeRequest):
 try:return await runner.resume(session_id,payload.verification_code)
 except KeyError as exc:raise HTTPException(404,str(exc)) from exc
 except ValueError as exc:raise HTTPException(409,str(exc)) from exc
@api.post("/knowledge/ingest")
async def knowledge_ingest():
 try:return {"status":"indexed",**await asyncio.to_thread(ingest_doctrine,settings.skills_root,Path(settings.chroma_persist_dir),settings.embedding_model,1200,180)}
 except FileNotFoundError as exc:raise HTTPException(400,str(exc)) from exc
 except Exception as exc:logger.exception("RAG ingest failed");raise HTTPException(500,f"RAG ingest failed: {type(exc).__name__}: {str(exc)[:200]}") from exc
@api.get("/knowledge/status")
async def knowledge_status():
 path=Path(settings.chroma_persist_dir);return {"available":path.exists() and any(path.glob("**/*")),"path":str(path.resolve()),"collection":"affiliate_doctrine","required_references":["offer-frameworks.md","platform-rules.md","seo-strategy.md","social-data-providers.md"]}
@api.get("/offers")
async def offers(q:str|None=None,limit:int=Query(50,ge=1,le=200),db:AsyncSession=Depends(get_session)):
 stmt=select(Offer)
 if q:stmt=stmt.where(Offer.name.ilike(f"%{q[:100]}%"))
 rows=list((await db.scalars(stmt.order_by(Offer.verified.desc(),Offer.name).limit(limit))).all())
 return {"count":len(rows),"data":[{"id":o.id,"network":o.network,"external_id":o.external_id,"name":o.name,"url":o.url,"category":o.category,"description":o.description,"reward_type":o.reward_type,"reward_value":o.reward_value,"cookie_days":o.cookie_days,"traffic_score":o.traffic_score,"gravity_score":o.gravity_score,"normalized_gravity":o.normalized_gravity,"epc":o.epc,"conversion_rate":o.conversion_rate,"recurring_commission":o.recurring_commission,"source_stars":o.source_stars,"verified":o.verified,"source_url":o.source_url} for o in rows]}
@api.post("/offers/sync")
async def offers_sync(q:str|None=None,limit:int=Query(100,ge=1,le=200),db:AsyncSession=Depends(get_session)):
 try:data=await openaffiliate_client.fetch_programs(q=q,limit=limit)
 except Exception as exc:raise HTTPException(502,f"OpenAffiliate error: {type(exc).__name__}: {str(exc)[:200]}") from exc
 created=updated=0
 for item in data["data"]:
  eid=str(item.get("slug") or item.get("id") or "")
  if not eid:continue
  row=await db.scalar(select(Offer).where(Offer.network=="openaffiliate",Offer.external_id==eid))
  if row is None:row=Offer(network="openaffiliate",external_id=eid,name=item["name"]);db.add(row);created+=1
  else:updated+=1
  row.name=item["name"];row.url=item.get("url");row.category=item.get("category");row.description=item.get("description","");row.reward_type=item.get("reward_type");row.reward_value=item.get("reward_value");row.cookie_days=item.get("cookie_days");row.traffic_score=item.get("traffic_score");row.source_stars=item.get("stars_count");row.verified=bool(item.get("verified"));raw=item.get("raw") or {};row.source_url=raw.get("source_url") if isinstance(raw,dict) else None;metrics=compute_offer_metrics({"reward_type":row.reward_type,"reward_value":row.reward_value,"gravity_score":raw.get("gravity_score",raw.get("gravity"))});row.gravity_score=metrics["gravity_score"];row.normalized_gravity=metrics["normalized_gravity"];row.epc=metrics["epc"];row.conversion_rate=metrics["conversion_rate"];row.recurring_commission=metrics["recurring_commission"];row.metadata_json={"tags":item.get("tags",[])}
 await db.commit();return {"created":created,"updated":updated,"registry_total":data.get("registry_total"),"traffic_score_note":"Unknown unless upstream actually supplies the field."}
@api.post("/research/niches")
async def research_niches(p:NicheFinderRequest):return {"results":monopoly_niche_finder(p.candidates,top_n=p.top_n)}
@api.post("/research/competitors")
async def research_competitors(p:CompetitorRequest):return {"results":await competitor_spy(p.urls)}
@api.post("/research/trends")
async def research_trends(p:TrendRequest):return await trending_content_scout(p.query,limit=p.limit)
@api.post("/content/social")
async def social_content(p:SocialPostRequest):return await viral_post_writer(p.topic,p.hooks,p.platform)
@api.post("/content/tiktok-script")
async def tiktok_content(p:SocialPostRequest):return await tiktok_script_writer(p.topic,p.hooks)
@api.post("/content/keywords")
async def keywords(payload:dict[str,Any]):
 items=payload.get("keywords")
 if not isinstance(items,list) or any(not isinstance(x,str) for x in items):raise HTTPException(422,"keywords must be a list of strings")
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


@api.post("/content/blog")
async def blog(p:BlogRequest,db:AsyncSession=Depends(get_session)):
 result=await affiliate_blog_builder(p.topic,product=p.product,canonical_url=p.canonical_url,minimum_words=p.minimum_words)
 asset=ContentAsset(asset_type="affiliate_blog",title=result["title"],body=result["html"],status="draft",source_urls=result["rag_sources"],metadata_json={"word_count":result["word_count"],"schema_types":result["schema_types"],"provider":result["provider"]});db.add(asset);await db.commit();result["asset_id"]=asset.id;return result
@api.post("/content/video")
async def video(p:VideoRequest):return await render_vertical_video(p.script,broll_query=p.broll_query,voice=p.voice,captions=p.captions)
@api.post("/landing/offer")
async def landing_offer(p:dict[str,Any]):return await grand_slam_offer_generator(p.get("product") or {},str(p.get("audience") or ""),str(p.get("main_problem") or ""))
@api.post("/landing/value-ladder")
async def landing_ladder(p:dict[str,Any]):return await value_ladder_architect(str(p.get("audience") or ""),p.get("product") or {},p.get("deliverable_assets"))
@api.post("/landing/page")
async def landing_page(p: LandingPageRequest):
 workspace_id = get_workspace_id()
 if settings.app_env == "production" and not workspace_id:
  raise HTTPException(403, "An active workspace is required to create a public landing page")
 return HTMLResponse(squeeze_page_builder(headline=p.headline,subheadline=p.subheadline,benefit_bullets=p.benefit_bullets,form_action=p.form_action,privacy_url=p.privacy_url,affiliate_disclosure=p.affiliate_disclosure,lead_magnet=p.lead_magnet,audience=p.audience,workspace_token=issue_workspace_token(workspace_id,"lead_capture")))
@api.post("/landing/email-drip")
async def drip(payload:dict[str,Any]):return {"sequence":email_drip_sequence(audience=str(payload.get("audience") or ""),lead_magnet=str(payload.get("lead_magnet") or ""),affiliate_offer=payload.get("affiliate_offer") or {},duration_days=int(payload.get("duration_days",5)))}
@api.post("/social/publish")
async def social_publish(payload:dict[str,Any]):return await social_media_scheduler(str(payload.get("platform") or ""),dict(payload.get("post") or {}))
_public_hits:dict[str,list[float]]={};_public_lock=asyncio.Lock()
async def public_rate_limit(request:Request):
 ip=request.client.host if request.client else "unknown";now=time.monotonic()
 async with _public_lock:
  recent=[x for x in _public_hits.get(ip,[]) if now-x<3600]
  if len(recent)>=20:raise HTTPException(429,"Signup rate limit exceeded")
  recent.append(now);_public_hits[ip]=recent
  if len(_public_hits)>5000:
   for key in list(_public_hits)[:1000]:
    if not _public_hits[key] or now-_public_hits[key][-1]>=3600:_public_hits.pop(key,None)
async def create_lead(payload:LeadCaptureRequest,db:AsyncSession):
 try:return await capture_lead_and_schedule(db,email_address=payload.email,consent=payload.consent,lead_magnet=payload.lead_magnet,audience=payload.audience,offer=payload.offer)
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@api.post("/leads/capture",status_code=201)
async def lead_capture(p:LeadCaptureRequest,db:AsyncSession=Depends(get_session)):return await create_lead(p,db)
@app.post("/api/public/leads/capture",status_code=201)
async def public_lead_capture(request:Request,db:AsyncSession=Depends(get_session)):
 await public_rate_limit(request);ctype=request.headers.get("content-type","").lower()
 if "application/json" in ctype:raw=await request.json()
 elif "application/x-www-form-urlencoded" in ctype or "multipart/form-data" in ctype:
  form=await request.form();raw=dict(form)
 else:raise HTTPException(415,"Submit JSON or an HTML form")
 consent=raw.get("consent");raw["consent"]=consent is True or str(consent or "").lower() in {"1","true","yes","on"}
 try:p=LeadCaptureRequest.model_validate(raw)
 except Exception as exc:raise HTTPException(422,"Signup form contains invalid fields") from exc
 workspace_id = verify_workspace_token(p.workspace_token, "lead_capture")
 if not workspace_id: raise HTTPException(403, "A valid workspace landing token is required for public lead capture")
 with workspace_scope(workspace_id):
  result=await create_lead(p,db)
 if "application/json" in request.headers.get("accept",""):return result
 return HTMLResponse("<!doctype html><html><body style='font-family:system-ui;background:#f8fafc;padding:48px;color:#1e293b'><h1>You're on the list</h1><p>Your consent-based email sequence was queued.</p></body></html>",status_code=201)
@api.get("/leads")
async def leads(db:AsyncSession=Depends(get_session)):
 rows=list((await db.scalars(select(Lead).order_by(Lead.created_at.desc()).limit(200))).all());return {"count":len(rows),"data":[{"id":x.id,"email":x.email,"lead_magnet":x.lead_magnet,"consented_at":x.consent_at.isoformat(),"unsubscribed":x.unsubscribed_at is not None,"purchased":x.purchased_at is not None} for x in rows]}
@api.get("/email/queue")
async def email_queue(db:AsyncSession=Depends(get_session)):
 rows=list((await db.scalars(select(ScheduledEmail).order_by(ScheduledEmail.send_at.desc()).limit(250))).all());return {"count":len(rows),"data":[{"id":x.id,"lead_id":x.lead_id,"day":x.sequence_day,"subject":x.subject,"send_at":x.send_at.isoformat(),"status":x.status,"attempts":x.attempts,"last_error":x.last_error} for x in rows]}
@api.post("/email/worker/run")
async def email_worker():return await send_due_emails()
@api.post("/analytics/conversions")
async def conversion_create(p:ConversionRequest,db:AsyncSession=Depends(get_session)):
 network=p.network.lower();existing=await db.scalar(select(Conversion.id).where(Conversion.network==network,Conversion.external_event_id==p.external_event_id))
 if existing:return {"status":"duplicate_ignored","id":existing}
 utm=conversion_tracker(p.url or "");row=Conversion(network=network,external_event_id=p.external_event_id,click_id=p.click_id or utm["click_id"],utm_source=p.utm_source or utm["utm_source"],utm_medium=p.utm_medium or utm["utm_medium"],utm_campaign=p.utm_campaign or utm["utm_campaign"],utm_content=p.utm_content or utm["utm_content"],hook=p.hook or p.utm_content or utm["utm_content"],revenue=p.revenue,commission=p.commission,currency=p.currency.upper(),status=p.status.lower(),event_json=p.event_json);db.add(row)
 try:await db.commit()
 except IntegrityError:await db.rollback();return {"status":"duplicate_ignored"}
 return {"status":"recorded","id":row.id,"utm":utm}
@api.post("/analytics/track")
async def track(p:dict[str,Any]):
 raw=p.get("url") or p.get("query")
 if not raw:raise HTTPException(422,"url or query required")
 return conversion_tracker(str(raw))
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
async def learn(lookback_days:int=Query(30,ge=1,le=180)):return await self_improver_loop(lookback_days=lookback_days)
@api.get("/resource-budget")
async def resource_budget():return await budget_status()
@api.get("/campaigns")
async def campaigns(db:AsyncSession=Depends(get_session)):
 rows=list((await db.scalars(select(Campaign).order_by(Campaign.created_at.desc()).limit(200))).all());return {"count":len(rows),"data":[{"id":x.id,"name":x.name,"niche":x.niche,"primary_destination":x.primary_destination,"fallback_destination":x.fallback_destination,"is_active":x.is_active,"primary_healthy":x.primary_healthy,"fallback_healthy":x.fallback_healthy,"health_last_error":x.health_last_error} for x in rows]}
@api.post("/campaigns",status_code=201)
async def campaign_create(p:CampaignCreateRequest,db:AsyncSession=Depends(get_session)):
 try:await validate_public_http_url(p.primary_destination);await validate_public_http_url(p.fallback_destination) if p.fallback_destination else None
 except ValueError as exc:raise HTTPException(422,str(exc)) from exc
 row=Campaign(name=p.name,niche=p.niche,primary_destination=p.primary_destination,fallback_destination=p.fallback_destination,tracking_parameter=p.tracking_parameter,disclosure_text=p.disclosure_text,auto_publish=p.auto_publish,max_daily_spend=p.max_daily_spend);db.add(row);await db.commit();return {"id":row.id,"name":row.name,"tracking_url":f"{settings.app_public_url.rstrip('/')}/r/{row.id}","status":"created"}
@api.post("/campaigns/{campaign_id}/health")
async def campaign_health(campaign_id:str,db:AsyncSession=Depends(get_session)):
 row=await db.get(Campaign,campaign_id)
 if not row:raise HTTPException(404,"Campaign not found")
 out=await choose_destination(row);row.primary_healthy=out.get("primary_healthy");row.fallback_healthy=out.get("fallback_healthy");row.health_last_checked_at=utcnow();row.health_last_error=str(out.get("health_error") or "")[:1000] or None;await db.commit();return {"campaign_id":row.id,**out,"note":"Fallback applies to this click; campaign configuration is unchanged."}
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
async def thresholds(db:AsyncSession=Depends(get_session)):
 rows=list((await db.scalars(select(PayoutThreshold).order_by(PayoutThreshold.network))).all());return {"count":len(rows),"data":[{"id":x.id,"network":x.network,"currency":x.currency,"minimum_threshold":x.minimum_threshold,"reported_balance":x.reported_balance,"threshold_reached":x.threshold_reached,"threshold_reached_at":x.threshold_reached_at.isoformat() if x.threshold_reached_at else None,"funds_received_at":x.funds_received_at.isoformat() if x.funds_received_at else None,"note":x.reconciliation_note} for x in rows]}
@api.post("/finance/thresholds",dependencies=[Depends(require_admin)],status_code=201)
async def threshold_create(p:PayoutThresholdCreateRequest,db:AsyncSession=Depends(get_session)):
 row=PayoutThreshold(network=p.network,currency=p.currency,minimum_threshold=p.minimum_threshold,reported_balance=p.reported_balance,reconciliation_note=p.reconciliation_note);row.threshold_reached=row.reported_balance>=row.minimum_threshold;row.threshold_reached_at=utcnow() if row.threshold_reached else None;db.add(row);await db.commit();return {"id":row.id,"threshold_reached":row.threshold_reached,"note":"Tracking only; no payout is initiated."}
@api.post("/finance/thresholds/{threshold_id}/funds-received",dependencies=[Depends(require_admin)])
async def funds_received(threshold_id:str,p:FundsReceivedRequest,db:AsyncSession=Depends(get_session)):
 row=await db.get(PayoutThreshold,threshold_id)
 if not row:raise HTTPException(404,"Threshold not found")
 row.funds_received_at=p.funds_received_at;row.reconciliation_note=p.reconciliation_note[:4000];await db.commit();return {"id":row.id,"funds_received_at":row.funds_received_at.isoformat(),"transfers_initiated":False}
@api.post("/ads/plan", status_code=201)
async def ads_plan(
    payload: AdCampaignPlanRequest,
    user: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_session),
):
    plan = await generate_ad_campaign_plan(payload)
    db.add(
        AdCampaignPlanRecord(
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
    db: AsyncSession = Depends(get_session),
):
    rows = list((await db.scalars(
        select(AdCampaignPlanRecord)
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
    db: AsyncSession = Depends(get_session),
):
    row = await db.scalar(
        select(AdCampaignPlanRecord).where(AdCampaignPlanRecord.id == plan_id)
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
    if payload.campaign_plan_id:
        plan = await db.scalar(
            select(AdCampaignPlanRecord).where(AdCampaignPlanRecord.id == payload.campaign_plan_id)
        )
        if plan is None:
            raise HTTPException(404, "Ad plan not found in the active workspace")

    row = AdPerformanceObservation(
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
    db: AsyncSession = Depends(get_session),
):
    rows = list((await db.scalars(
        select(AdPerformanceObservation)
        .order_by(AdPerformanceObservation.created_at.desc())
        .limit(limit)
    )).all())
    return {
        "count": len(rows),
        "limit": limit,
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
    db: AsyncSession = Depends(get_session),
):
    rows = list((await db.scalars(
        select(AdPerformanceObservation)
        .order_by(AdPerformanceObservation.observed_at.desc())
        .limit(limit)
    )).all())
    return {
        "count": len(rows),
        "limit": limit,
        "items": summarize_ad_performance(rows),
        "note": "Reported KPIs are not treated as verified evidence. No campaign changes or spend actions are executed by this endpoint.",
    }


@api.post("/ads/evaluate")
async def ads_evaluate(p:dict[str,Any]):
 try:d=evaluate_roas(str(p["campaign_id"]),float(p["spend"]),float(p["commission"]),float(p.get("threshold",1.2)))
 except (KeyError,ValueError,TypeError) as exc:raise HTTPException(422,"campaign_id, spend and commission are required numeric values") from exc
 return {"campaign_id":d.campaign_id,"roas":d.roas,"threshold":d.threshold,"pause_recommended":d.pause_recommended,"executed":False,"reason":d.reason}
@api.post("/cms/publish",dependencies=[Depends(require_admin)])
async def cms(p:CMSPublishRequest):return await publish_article(provider=p.provider,title=p.title,article_html=p.article_html,canonical_url=p.canonical_url,status=p.status,tags=p.tags,disclosure=p.disclosure)
@api.get("/audit")
async def audit(limit:int=Query(100,ge=1,le=500),db:AsyncSession=Depends(get_session)):
 rows=list((await db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))).all());return {"count":len(rows),"data":[{"id":x.id,"actor":x.actor,"action":x.action,"resource_type":x.resource_type,"resource_id":x.resource_id,"outcome":x.outcome,"details":x.details_json,"created_at":x.created_at.isoformat() if x.created_at else None} for x in rows]}
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
        "lifecycle_mutations_available": False,
        "data": [
            {
                "id": row.id,
                "name": row.name,
                "slug": row.slug,
                "owner_user_id": row.owner_user_id,
                "active_memberships": member_counts.get(str(row.id), 0),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "lifecycle_state": "not_modeled",
            }
            for row in rows
        ],
    }


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

@app.get("/unsubscribe/{lead_id}")
async def unsubscribe(lead_id:str,ts:int=Query(...),sig:str=Query(...),db:AsyncSession=Depends(get_session)):
 if abs(int(time.time())-ts)>31536000:raise HTTPException(410,"Unsubscribe link expired")
 secret=settings.tracking_hmac_secret or settings.app_session_secret;expected=hmac.new(secret.encode(),f"unsubscribe:{lead_id}:{ts}".encode(),hashlib.sha256).hexdigest()
 if not hmac.compare_digest(sig,expected):raise HTTPException(403,"Invalid unsubscribe signature")
 if not await unsubscribe_lead(db,lead_id):raise HTTPException(404,"Lead not found")
 return HTMLResponse("<!doctype html><html><body style='font-family:system-ui;background:#f8fafc;color:#1e293b;padding:48px'><h1>You are unsubscribed</h1><p>No further email sequence messages will be sent.</p></body></html>")
@app.post("/api/webhooks/conversions/{network}")
async def conversion_webhook(network:str,request:Request,db:AsyncSession=Depends(get_session)):
 secret=settings.affiliate_webhook_secret
 net=network.strip().lower()
 if not secret or len(secret)<32:raise HTTPException(503,"Affiliate webhook secret is not configured")
 if not net or len(net)>100:raise HTTPException(422,"Network must contain 1-100 characters")
 body=await request.body()
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
 status=event["status"];reversal=status in {"reversed","refunded","chargeback","clawback","reversal","commission_reversal"}
 commission=event["commission"];revenue=event["revenue"]
 original_id=str(p.get("original_event_id") or p.get("parent_transaction_id") or "").strip()
 if len(original_id)>255:raise HTTPException(422,"original_event_id must be 255 characters or fewer")
 if reversal:
  parent=await db.scalar(select(Conversion).where(Conversion.network==str(p.get("original_network") or net).lower(),Conversion.external_event_id==original_id)) if original_id else None
  if parent and parent.status=="reversed":return {"status":"duplicate_reversal_ignored","original_event_id":original_id}
  if parent:commission=-abs(parent.commission);revenue=-abs(parent.revenue);parent.status="reversed";status="reversed"
  else:
   if not commission and not revenue:raise HTTPException(422,"Unmatched reversal must include commission or revenue offset")
   commission=-abs(commission);revenue=-abs(revenue);status="reversal_unmatched"
 currency=str(p.get("currency") or "USD").strip().upper()
 if len(currency)!=3 or not currency.isalpha():raise HTTPException(422,"currency must be a three-letter code")
 row=Conversion(workspace_id=click.workspace_id,network=net,external_event_id=eid,click_id=click_id,utm_source=p.get("utm_source"),utm_medium=p.get("utm_medium"),utm_campaign=p.get("utm_campaign"),utm_content=p.get("utm_content"),hook=p.get("hook") or p.get("utm_content"),commission=commission,revenue=revenue,currency=currency,status=status,event_json={**p,"reversal":reversal,"original_event_id":original_id or None});db.add(row)
 try:await db.commit()
 except IntegrityError as exc:
  await db.rollback()
  duplicate=await db.scalar(select(Conversion.id).where(Conversion.network==net,Conversion.external_event_id==eid))
  if duplicate:return {"status":"duplicate_ignored"}
  raise HTTPException(409,"Conversion could not be persisted because of an integrity conflict") from exc
 return {"status":"recorded","conversion_id":row.id,"reversal":reversal,"commission_adjustment":commission}
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
 if settings.app_env=="production" and not ws.scope.get("session",{}).get("user"):
  await ws.close(code=1008,reason="Authentication required");return
 await hub.connect(ws)
 try:
  while True:
   if await ws.receive_text()=="ping":await ws.send_text(json.dumps({"event":"PONG","time":utcnow().isoformat()}))
 except WebSocketDisconnect:await hub.disconnect(ws)
 except Exception:await hub.disconnect(ws)

@api.post("/finance/email-import",dependencies=[Depends(require_admin)])
async def commission_email_import(user: dict[str, Any] = Depends(require_auth)):
 from backend.services.commission_mail_importer import import_commission_emails
 workspace_id = user.get("workspace_id")
 if not workspace_id:
  raise HTTPException(403, "Select an authorized workspace before importing commission evidence")
 try:return await import_commission_emails(workspace_id=str(workspace_id))
 except Exception as exc:raise HTTPException(502,f"Mail import failed: {type(exc).__name__}: {str(exc)[:200]}") from exc

@api.get("/finance/mail-commissions")
async def mail_commissions(db:AsyncSession=Depends(get_session)):
 rows=list((await db.scalars(select(MailCommission).order_by(MailCommission.created_at.desc()).limit(300))).all())
 return {"count":len(rows),"data":[{"id":x.id,"network":x.network,"commission":x.commission,"currency":x.currency,"status":x.status,"email_date":x.email_date.isoformat() if x.email_date else None,"subject":x.parsed_subject,"evidence":x.evidence_json} for x in rows]}


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

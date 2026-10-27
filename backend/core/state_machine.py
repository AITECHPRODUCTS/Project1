from __future__ import annotations
import asyncio,base64,copy,hashlib,logging,uuid
from cryptography.fernet import Fernet,InvalidToken
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from typing import Any,Awaitable,Callable
from sqlalchemy import or_,select
from backend.config import get_settings
from backend.core.errors import VerificationRequiredError
from backend.core.events import hub
from backend.database import SessionLocal
from backend.models import AuditLog,PausedSession,WorkflowRun
from backend.tenancy import get_workspace_id,workspace_scope
logger=logging.getLogger(__name__)
WORKFLOW_LEASE_SECONDS=60
WORKFLOW_HEARTBEAT_SECONDS=10
WORKFLOW_RECOVERY_INTERVAL_SECONDS=3
TERMINAL_WORKFLOW_STATUSES={"completed","failed","cancelled"}


def _resume_response_cipher() -> Fernet:
 secret=get_settings().app_session_secret
 if not isinstance(secret,str) or len(secret)<32:
  raise RuntimeError("APP_SESSION_SECRET must be configured to encrypt workflow verification responses")
 material=hashlib.sha256(b"omni-affiliate-os/hitl-response/v1\\x00"+secret.encode("utf-8")).digest()
 return Fernet(base64.urlsafe_b64encode(material))


def _encrypt_resume_response(value: str) -> str:
 return _resume_response_cipher().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt_resume_response(value: str) -> str:
 return _resume_response_cipher().decrypt(value.encode("ascii")).decode("utf-8")

class WorkflowLeaseLost(RuntimeError):
 """Raised when a worker no longer owns the durable workflow lease."""

StageHandler=Callable[[dict[str,Any]],Awaitable[dict[str,Any]|None]]
@dataclass(frozen=True)
class WorkflowStep:
 key: str
 label: str
 handler: StageHandler
 side_effecting: bool = False
class WorkflowRunner:
 def __init__(self):
  self.tasks:dict[str,asyncio.Task]={}
  self.events:dict[str,asyncio.Event]={}
  self.responses:dict[str,str]={}
  self.resolver:Callable[[str],list[WorkflowStep]]|None=None
  self.worker_id=f"workflow-worker-{uuid.uuid4().hex}"
  self._recovery_task:asyncio.Task|None=None
 def set_resolver(self,fn):self.resolver=fn
 async def _emit(self,state:dict[str,Any],payload:dict[str,Any]):
  metadata=state.get("metadata",{})
  workspace_id=metadata.get("workspace_id") if isinstance(metadata,dict) else None
  if not isinstance(workspace_id,str) or not workspace_id.strip():
   logger.warning("Dropping unscoped workflow event: %s",payload.get("event"))
   return
  await hub.publish({**payload,"workspace_id":workspace_id})
 async def start(self,name:str,state:dict[str,Any],steps:list[WorkflowStep],mode:str|None=None)->str:
  mode=mode or get_settings().execution_mode
  if mode not in {"FULL_AUTONOMOUS","SEMI_AUTONOMOUS","MANUAL_OVERRIDE"}:raise ValueError("Invalid execution mode")
  if mode=="MANUAL_OVERRIDE" and len(steps)!=1:raise ValueError("MANUAL_OVERRIDE runs exactly one stage")
  workspace_id=get_workspace_id()
  if not isinstance(workspace_id,str) or not workspace_id.strip():raise ValueError("Authorized workspace context required to start a workflow")
  sid=str(uuid.uuid4());now=datetime.now(timezone.utc)
  state=copy.deepcopy(state)
  state.setdefault("metadata",{}).update({"workflow":name,"execution_mode":mode,"started_at":now.isoformat(),"workspace_id":workspace_id})
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    db.add(WorkflowRun(
     id=sid,workspace_id=workspace_id,workflow_name=name,status="queued",execution_mode=mode,
     state_json=state,lease_owner=self.worker_id,
     lease_expires_at=now+timedelta(seconds=WORKFLOW_LEASE_SECONDS),
     heartbeat_at=now,attempt_count=1,
    ))
    db.add(AuditLog(workspace_id=workspace_id,actor="system",action="workflow.started",resource_type="workflow",resource_id=sid,details_json={"name":name,"mode":mode}))
    await db.commit()
  self.events[sid]=asyncio.Event()
  with workspace_scope(workspace_id):
   task=asyncio.create_task(
    self._with_heartbeat(sid,self.worker_id,workspace_id,self._drive(sid,name,state,steps,0,mode,worker_id=self.worker_id)),
    name=f"affiliate-os-{sid}",
   )
   self.tasks[sid]=task
  return sid
 async def _save(self,sid:str,status:str,index:int,state:dict[str,Any],error:str|None=None,done:bool=False,result:dict|None=None,worker_id:str|None=None):
  safe=copy.deepcopy(state);safe.pop("_verification_response",None)
  async with SessionLocal() as db:
   row=await db.get(WorkflowRun,sid)
   if not row:
    if worker_id:raise WorkflowLeaseLost("Workflow row disappeared while a worker held its lease")
    return
   if worker_id is not None and row.lease_owner!=worker_id:
    raise WorkflowLeaseLost("Workflow lease was claimed by another worker")
   # Merge durable operator control state; a worker's older in-memory snapshot
   # must never erase a cancellation request written by another request/worker.
   stored_state=row.state_json if isinstance(row.state_json,dict) else {}
   stored_control=stored_state.get("control") if isinstance(stored_state.get("control"),dict) else {}
   new_control=safe.get("control") if isinstance(safe.get("control"),dict) else {}
   if stored_control:
    safe["control"]={**stored_control,**new_control}
   # A stale worker may not move a terminal run back into an active state.
   if row.status in TERMINAL_WORKFLOW_STATUSES and status not in TERMINAL_WORKFLOW_STATUSES:
    return
   row.status=status;row.current_step=index;row.state_json=safe
   if error is not None:row.error_message=error[:2000]
   if result is not None:row.result_json=result
   if status=="running" and row.started_at is None:row.started_at=datetime.now(timezone.utc)
   if done:row.finished_at=datetime.now(timezone.utc)
   if worker_id:
    row.heartbeat_at=datetime.now(timezone.utc)
    row.lease_expires_at=datetime.now(timezone.utc)+timedelta(seconds=WORKFLOW_LEASE_SECONDS)
   await db.commit()
 async def _pause(self,sid:str,name:str,index:int,state:dict[str,Any],exc:VerificationRequiredError,worker_id:str|None=None):
  safe=copy.deepcopy(state);safe.pop("_verification_response",None)
  async with SessionLocal() as db:
   row=await db.get(PausedSession,sid)
   if row is None:row=PausedSession(session_id=sid,workflow_name=name);db.add(row)
   run=await db.get(WorkflowRun,sid)
   if run:
    if worker_id is not None and run.lease_owner!=worker_id:raise WorkflowLeaseLost("Workflow lease was claimed while pausing")
    stored_state=run.state_json if isinstance(run.state_json,dict) else {}
    stored_control=stored_state.get("control") if isinstance(stored_state.get("control"),dict) else {}
    new_control=safe.get("control") if isinstance(safe.get("control"),dict) else {}
    if stored_control:safe["control"]={**stored_control,**new_control}
    run.status="paused";run.current_step=index;run.state_json=safe
    if worker_id:
     run.heartbeat_at=datetime.now(timezone.utc)
     run.lease_expires_at=datetime.now(timezone.utc)+timedelta(seconds=WORKFLOW_LEASE_SECONDS)
   row.status="paused";row.current_step=index;row.required_action=exc.action;row.state_json=safe;row.last_error=str(exc)[:800]
   row.verification_response_encrypted=None
   db.add(AuditLog(actor="system",action="workflow.paused_for_verification",resource_type="workflow",resource_id=sid,workspace_id=run.workspace_id if run else None,details_json={"index":index,"action":exc.action}))
   await db.commit()
 async def _drive(self,sid:str,name:str,state:dict[str,Any],steps:list[WorkflowStep],start:int,mode:str,worker_id:str|None=None):
  settings=get_settings();event=self.events.setdefault(sid,asyncio.Event());await self._save(sid,"running",start,state,worker_id=worker_id)
  await self._emit(state, {"event":"WORKFLOW_STATUS","session_id":sid,"workflow_name":name,"status":"running","current_step":start,"total_steps":len(steps)})
  try:
   if await self._has_cancel_request(sid,state):
    await self._finish_cancelled(sid,start,state,worker_id=worker_id);return
   for i in range(start,len(steps)):
    if await self._has_cancel_request(sid,state):
     await self._finish_cancelled(sid,i,state,worker_id=worker_id);return
    step=steps[i];await self._save(sid,"running",i,state,worker_id=worker_id)
    await self._emit(state, {"event":"STAGE_STATUS","session_id":sid,"stage":step.key,"stage_label":step.label,"status":"running","current_step":i,"total_steps":len(steps)})
    attempts=0
    while True:
     if await self._has_cancel_request(sid,state):
      await self._finish_cancelled(sid,i,state,worker_id=worker_id);return
     try:
      result=await asyncio.wait_for(step.handler(state),timeout=int(settings.load_yaml().get("app",{}).get("workflow_step_timeout_seconds",120)))
      verification_response_used="_verification_response" in state
      if verification_response_used:state.pop("_verification_response",None)
      nested=[v.get("status") for k,v in (result or {}).items() if k.endswith("_result") and isinstance(v,dict) and v.get("status")]
      stage_status="skipped" if nested and all(x=="skipped" for x in nested) else "completed"
      state.setdefault("stages",{})[step.key]={"status":stage_status,"result":result or {},"completed_at":datetime.now(timezone.utc).isoformat()}
      if isinstance(result,dict):state.update({k:v for k,v in result.items() if k not in {"metadata","stages"}})
      if await self._has_cancel_request(sid,state):
       await self._finish_cancelled(sid,i+1,state,worker_id=worker_id);return
      await self._save(sid,"running",i+1,state,worker_id=worker_id)
      if verification_response_used:
       response_workspace_id=str(state.get("metadata",{}).get("workspace_id") or "").strip()
       if response_workspace_id:await self._clear_persisted_resume_response(sid,response_workspace_id,worker_id=worker_id)
      await self._emit(state, {"event":"STAGE_STATUS","session_id":sid,"stage":step.key,"stage_label":step.label,"status":stage_status,"current_step":i+1,"total_steps":len(steps)});break
     except VerificationRequiredError as exc:
      if await self._has_cancel_request(sid,state):
       await self._finish_cancelled(sid,i,state,worker_id=worker_id);return
      if mode=="FULL_AUTONOMOUS":
       await self._save(sid,"failed",i,state,f"Human verification required in FULL_AUTONOMOUS mode: {exc}",True,worker_id=worker_id);return
      await self._pause(sid,name,i,state,exc,worker_id=worker_id)
      if await self._has_cancel_request(sid,state):
       await self._finish_cancelled(sid,i,state,worker_id=worker_id);return
      await self._emit(state, {"event":"HITL_ALERT","session_id":sid,"workflow_name":name,"stage":step.key,"stage_label":step.label,"required_action":exc.action,"message":str(exc)})
      while True:
       try:
        await asyncio.wait_for(event.wait(),timeout=1.0)
        break
       except asyncio.TimeoutError:
        if await self._has_cancel_request(sid,state):
         await self._finish_cancelled(sid,i,state,worker_id=worker_id);return
      event.clear()
      if await self._has_cancel_request(sid,state):
       await self._finish_cancelled(sid,i,state,worker_id=worker_id);return
      state["_verification_response"]=self.responses.pop(sid,"")
      async with SessionLocal() as db:
       paused=await db.get(PausedSession,sid)
       if paused:paused.status="resuming";await db.commit()
      await self._emit(state, {"event":"HITL_RESUMED","session_id":sid,"stage":step.key})
      # The step retries and may consume state['_verification_response']; it must not log or persist that value.
      continue
     except asyncio.CancelledError:raise
     except Exception as exc:
      attempts+=1
      transient= isinstance(exc,(TimeoutError,ConnectionError))
      if transient and step.side_effecting:
       # A provider may have accepted a write before a timeout/connection break.
       # Never blindly retry an external side effect; leave a durable reconciliation event.
       metadata=state.get("metadata",{})
       workspace_id=str(metadata.get("workspace_id") or "").strip() if isinstance(metadata,dict) else ""
       if workspace_id:
        try:
         with workspace_scope(workspace_id):
          async with SessionLocal() as db:
           db.add(AuditLog(
            workspace_id=workspace_id,
            actor=str(metadata.get("initiated_by") or "workflow")[:320],
            action="workflow.side_effect_outcome_unknown",
            resource_type="external_publication",
            resource_id=sid,
            outcome="unknown",
            details_json={
             "stage":step.key,
             "error_type":type(exc).__name__,
             "automatic_retry":False,
             "manual_reconciliation_required":True,
            },
           ))
           await db.commit()
        except Exception:
         logger.exception("Unable to persist unknown side-effect outcome for workflow %s stage %s",sid,step.key)
       failure_message=f"{step.key}: external side-effect outcome unknown after {type(exc).__name__}; automatic retry suppressed; reconcile the provider before resubmitting."
      elif transient and attempts<=int(settings.load_yaml().get("app",{}).get("max_workflow_retries",2)):
       await asyncio.sleep(min(2**attempts,8));continue
      else:
       failure_message=f"{step.key}: {type(exc).__name__}: {exc}"
      logger.exception("Workflow stage failed: %s/%s",sid,step.key)
      state.setdefault("stages",{})[step.key]={"status":"failed","error":failure_message[:500]}
      await self._save(sid,"failed",i,state,failure_message,True,worker_id=worker_id)
      await self._emit(state, {"event":"WORKFLOW_STATUS","session_id":sid,"status":"failed","stage":step.key,"message":failure_message[:300]})
      return
   if await self._has_cancel_request(sid,state):
    await self._finish_cancelled(sid,len(steps),state,worker_id=worker_id);return
   state.setdefault("metadata",{})["finished_at"]=datetime.now(timezone.utc).isoformat();await self._save(sid,"completed",len(steps),state,done=True,result=state,worker_id=worker_id)
   async with SessionLocal() as db:db.add(AuditLog(actor="system",action="workflow.completed",resource_type="workflow",resource_id=sid,details_json={"name":name}));await db.commit()
   await self._emit(state, {"event":"WORKFLOW_STATUS","session_id":sid,"workflow_name":name,"status":"completed","current_step":len(steps),"total_steps":len(steps)})
  except asyncio.CancelledError:
   if worker_id is None:await self._save(sid,"cancelled",0,state,done=True)
   # Lease-owned work is left recoverable; shutdown or lease loss must not
   # mislabel an interrupted execution as a completed cancellation.
   raise
 async def _has_cancel_request(self,sid:str,state:dict[str,Any])->bool:
  metadata=state.get("metadata",{}) if isinstance(state,dict) else {}
  workspace_id=str(metadata.get("workspace_id") or "").strip() if isinstance(metadata,dict) else ""
  if not workspace_id:return False
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    row=await db.get(WorkflowRun,sid)
    if row is None or row.workspace_id!=workspace_id:return False
    stored_state=row.state_json if isinstance(row.state_json,dict) else {}
    control=stored_state.get("control") if isinstance(stored_state.get("control"),dict) else {}
    return row.status=="cancelled" or control.get("cancel_requested") is True

 async def request_cancel(self,sid:str,workspace_id:str,actor:str|None=None)->dict[str,Any]:
  if not isinstance(workspace_id,str) or not workspace_id.strip():raise KeyError("Workflow session not found")
  signal_local=False
  duplicate=False
  requested_status="queued"
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    row=await db.get(WorkflowRun,sid)
    if row is None or row.workspace_id!=workspace_id:raise KeyError("Workflow session not found")
    if row.status=="cancelled":
     return {"session_id":sid,"status":"cancelled","cancel_requested":True,"duplicate":True}
    if row.status in {"completed","failed"}:
     raise ValueError(f"Workflow is already {row.status}; a terminal workflow cannot be cancelled")
    requested_status=row.status
    state=copy.deepcopy(row.state_json or {})
    stored_control=state.get("control") if isinstance(state.get("control"),dict) else {}
    if stored_control.get("cancel_requested") is True:
     duplicate=True
    else:
     now=datetime.now(timezone.utc)
     state["control"]={
      **stored_control,
      "cancel_requested":True,
      "cancel_requested_at":now.isoformat(),
      "cancel_requested_by":str(actor or "operator")[:320],
      "cancel_requested_from_status":row.status,
     }
     row.state_json=state
     db.add(AuditLog(
      workspace_id=workspace_id,
      actor=str(actor or "operator")[:320],
      action="workflow.cancel_requested",
      resource_type="workflow",
      resource_id=sid,
      outcome="requested",
      details_json={
       "from_status":row.status,
       "safe_boundary":"after the current stage finishes; in-flight provider calls are not interrupted",
      },
     ))
    paused=await db.get(PausedSession,sid)
    signal_local=bool(
     row.status=="paused" and sid in self.tasks and
     self.tasks[sid] is not None and not self.tasks[sid].done()
    )
    if row.status=="paused" and paused is not None and paused.workspace_id==workspace_id:
     # A cancel request supersedes an encrypted, not-yet-consumed HITL response.
     paused.verification_response_encrypted=None
    await db.commit()
  if signal_local:
   self.responses.pop(sid,None)
   self.events.setdefault(sid,asyncio.Event()).set()
  return {
   "session_id":sid,
   "status":"cancel_requested" if requested_status!="paused" or not signal_local else "cancel_requested",
   "cancel_requested":True,
   "duplicate":duplicate,
   "current_status":requested_status,
   "detail":"The current stage will finish safely; no later stage will start. A provider outcome already in flight is not rolled back.",
  }

 async def _finish_cancelled(self,sid:str,index:int,state:dict[str,Any],worker_id:str|None=None)->bool:
  metadata=state.get("metadata",{}) if isinstance(state,dict) else {}
  workspace_id=str(metadata.get("workspace_id") or "").strip() if isinstance(metadata,dict) else ""
  if not workspace_id:raise ValueError("Authorized workspace context is required to cancel a workflow")
  safe=copy.deepcopy(state);safe.pop("_verification_response",None)
  now=datetime.now(timezone.utc)
  actor="operator"
  already_cancelled=False
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    row=await db.get(WorkflowRun,sid)
    if row is None or row.workspace_id!=workspace_id:
     if worker_id:raise WorkflowLeaseLost("Workflow row disappeared while cancelling")
     return False
    if worker_id is not None and row.lease_owner!=worker_id:
     raise WorkflowLeaseLost("Workflow lease was claimed before cancellation could be persisted")
    if row.status in {"completed","failed"}:return False
    if row.status=="cancelled":
     already_cancelled=True
    stored_state=row.state_json if isinstance(row.state_json,dict) else {}
    stored_control=stored_state.get("control") if isinstance(stored_state.get("control"),dict) else {}
    new_control=safe.get("control") if isinstance(safe.get("control"),dict) else {}
    control={**stored_control,**new_control}
    control["cancel_requested"]=True
    control.setdefault("cancel_requested_at",now.isoformat())
    control["cancelled_at"]=control.get("cancelled_at") or now.isoformat()
    actor=str(control.get("cancel_requested_by") or actor)[:320]
    safe["control"]=control
    row.status="cancelled";row.current_step=index;row.state_json=safe;row.result_json=safe
    row.error_message="Workflow cancelled by operator at a safe checkpoint."
    row.finished_at=row.finished_at or now
    paused=await db.get(PausedSession,sid)
    if paused is not None and paused.workspace_id==workspace_id:
     paused.status="cancelled"
     paused.verification_response_encrypted=None
    if not already_cancelled:
     db.add(AuditLog(
      workspace_id=workspace_id,
      actor=actor,
      action="workflow.cancelled",
      resource_type="workflow",
      resource_id=sid,
      outcome="cancelled",
      details_json={
       "current_step":index,
       "safe_boundary":True,
       "in_flight_external_action_rolled_back":False,
      },
     ))
    await db.commit()
  self.responses.pop(sid,None)
  event=self.events.get(sid)
  if event is not None:event.clear()
  await self._emit(safe,{"event":"WORKFLOW_STATUS","session_id":sid,"status":"cancelled","current_step":index,"total_steps":len(safe.get("stages",{})) if isinstance(safe.get("stages"),dict) else None})
  return True

 async def resume(self,sid:str,code:str,workspace_id:str,actor:str|None=None)->dict[str,Any]:
  if not isinstance(workspace_id,str) or not workspace_id.strip():raise KeyError("Paused session not found")
  normalized=code.strip()
  if not normalized or len(normalized)>512:raise ValueError("Verification response must be 1..512 characters")
  encrypted=_encrypt_resume_response(normalized)
  signal_local=False
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    paused=await db.get(PausedSession,sid);run=await db.get(WorkflowRun,sid)
    if not paused or not run:raise KeyError("Paused session not found")
    if paused.workspace_id!=workspace_id or run.workspace_id!=workspace_id:raise KeyError("Paused session not found")
    stored_state=run.state_json if isinstance(run.state_json,dict) else {}
    control=stored_state.get("control") if isinstance(stored_state.get("control"),dict) else {}
    if run.status=="cancelled" or control.get("cancel_requested") is True:
     raise ValueError("Workflow cancellation has been requested; verification responses are no longer accepted")
    if paused.status in {"resume_requested","resuming"} and paused.verification_response_encrypted:
     return {"session_id":sid,"status":paused.status,"verification_response_persisted":True,"duplicate":True,"detail":"An earlier response is already queued or being processed; it was not replaced."}
    if paused.status!="paused" or run.status!="paused":raise ValueError(f"Workflow is not paused ({run.status})")
    paused.status="resume_requested"
    paused.verification_response_encrypted=encrypted
    signal_local=run.lease_owner==self.worker_id
    db.add(AuditLog(
     workspace_id=workspace_id,
     actor=str(actor or "operator")[:320],
     action="workflow.resume_requested",
     resource_type="workflow",
     resource_id=sid,
     outcome="requested",
     details_json={"verification_response_persisted":True,"encrypted_at_rest":True},
    ))
    await db.commit()
  if signal_local and sid in self.tasks and not self.tasks[sid].done():
   self.responses[sid]=normalized
   self.events.setdefault(sid,asyncio.Event()).set()
  return {"session_id":sid,"status":"resume_requested","verification_response_persisted":True,"duplicate":False}
 async def status(self,sid:str,workspace_id:str|None=None)->dict[str,Any]|None:
  if not isinstance(workspace_id,str) or not workspace_id.strip():return None
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    run=await db.get(WorkflowRun,sid)
    if not run or run.workspace_id!=workspace_id:return None
    paused=await db.get(PausedSession,sid)
    state=run.state_json if isinstance(run.state_json,dict) else {}
    control=state.get("control") if isinstance(state.get("control"),dict) else {}
    return {"session_id":sid,"workflow_name":run.workflow_name,"status":run.status,"cancel_requested":control.get("cancel_requested") is True,"current_step":run.current_step,"execution_mode":run.execution_mode,"state":run.state_json,"result":run.result_json,"error":run.error_message,"paused_session":{"status":paused.status,"required_action":paused.required_action,"stage_index":paused.current_step} if paused and paused.workspace_id==workspace_id else None}
 async def _clear_persisted_resume_response(self,sid:str,workspace_id:str,worker_id:str|None=None)->None:
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    paused=await db.get(PausedSession,sid)
    run=await db.get(WorkflowRun,sid)
    if paused is None or paused.workspace_id!=workspace_id:return
    if worker_id is not None and (run is None or run.lease_owner!=worker_id):
     raise WorkflowLeaseLost("Workflow lease was lost before clearing its verification response")
    paused.verification_response_encrypted=None
    await db.commit()

 async def _load_persisted_resume_response(self,sid:str,workspace_id:str)->str|None:
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    paused=await db.get(PausedSession,sid)
    if paused is None or paused.workspace_id!=workspace_id:return None
    encrypted=paused.verification_response_encrypted
    status=paused.status
  if not encrypted or status not in {"resume_requested","resuming"}:return None
  return _decrypt_resume_response(encrypted)

 async def _fail_corrupt_resume_response(self,sid:str,workspace_id:str)->None:
  now=datetime.now(timezone.utc)
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    paused=await db.get(PausedSession,sid)
    run=await db.get(WorkflowRun,sid)
    if paused is None or run is None or paused.workspace_id!=workspace_id or run.workspace_id!=workspace_id:return
    paused.status="failed"
    paused.verification_response_encrypted=None
    run.status="failed"
    run.error_message="Stored verification response could not be decrypted; verify APP_SESSION_SECRET consistency across workers."
    run.finished_at=now
    run.lease_owner=None
    run.lease_expires_at=None
    db.add(AuditLog(
     workspace_id=workspace_id,
     actor="system",
     action="workflow.resume_payload_decryption_failed",
     resource_type="workflow",
     resource_id=sid,
     outcome="failed",
     details_json={"manual_intervention_required":True,"secret_consistency_required":True},
    ))
    await db.commit()
  current=asyncio.current_task()
  task=self.tasks.get(sid)
  if task is not None and task is not current and not task.done():task.cancel()

 async def wake_pending_responses(self)->int:
  with workspace_scope(None):
   async with SessionLocal() as db:
    stmt=select(PausedSession,WorkflowRun).join(
     WorkflowRun,WorkflowRun.id==PausedSession.session_id
    ).where(
     PausedSession.status=="resume_requested",
     PausedSession.verification_response_encrypted.is_not(None),
     WorkflowRun.status=="paused",
     WorkflowRun.lease_owner==self.worker_id,
    ).order_by(WorkflowRun.created_at.asc()).limit(100)
    pairs=(await db.execute(stmt)).all()
  woke=0
  for paused,run in pairs:
   sid=run.id
   task=self.tasks.get(sid)
   if task is None or task.done():continue
   event=self.events.setdefault(sid,asyncio.Event())
   if event.is_set() or sid in self.responses:continue
   workspace_id=str(run.workspace_id or paused.workspace_id or "").strip()
   if not workspace_id:continue
   try:
    response=_decrypt_resume_response(paused.verification_response_encrypted)
   except (InvalidToken,UnicodeDecodeError,ValueError,RuntimeError):
    logger.error("Workflow verification response decryption failed for %s; failing closed",sid)
    await self._fail_corrupt_resume_response(sid,workspace_id)
    continue
   self.responses[sid]=response
   event.set()
   woke+=1
  return woke

 async def _wait_recovered_pause(self,sid:str,name:str,state:dict[str,Any],steps:list[WorkflowStep],index:int,mode:str,action:str,error:str|None,worker_id:str|None=None):
  event=self.events.setdefault(sid,asyncio.Event())
  metadata=state.get("metadata",{})
  workspace_id=str(metadata.get("workspace_id") or "").strip() if isinstance(metadata,dict) else ""
  if not workspace_id:raise ValueError("Authorized workspace context required to recover a paused workflow")
  try:
   response=await self._load_persisted_resume_response(sid,workspace_id)
  except (InvalidToken,UnicodeDecodeError,ValueError,RuntimeError):
   logger.error("Workflow verification response decryption failed for %s during recovery; failing closed",sid)
   await self._fail_corrupt_resume_response(sid,workspace_id)
   return
  if response is None:
   await self._emit(state, {"event":"HITL_ALERT","session_id":sid,"workflow_name":name,"stage":steps[index].key if index<len(steps) else None,"stage_label":steps[index].label if index<len(steps) else None,"required_action":action,"message":error or "Workflow recovered paused; human response required."})
   while True:
    try:
     await asyncio.wait_for(event.wait(),timeout=1.0)
     break
    except asyncio.TimeoutError:
     if await self._has_cancel_request(sid,state):
      await self._finish_cancelled(sid,index,state,worker_id=worker_id);return
   event.clear()
   if await self._has_cancel_request(sid,state):
    await self._finish_cancelled(sid,index,state,worker_id=worker_id);return
   response=self.responses.pop(sid,"")
  else:
   self.responses.pop(sid,None)
  state["_verification_response"]=response
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    row=await db.get(PausedSession,sid)
    if row and row.workspace_id==workspace_id:row.status="resuming";await db.commit()
  await self._drive(sid,name,state,steps,index,mode,worker_id=worker_id)

 async def _heartbeat(self,sid:str,worker_id:str,workspace_id:str)->bool:
  while True:
   await asyncio.sleep(WORKFLOW_HEARTBEAT_SECONDS)
   try:
    with workspace_scope(workspace_id):
     async with SessionLocal() as db:
      row=await db.get(WorkflowRun,sid)
      if row is None or row.lease_owner!=worker_id:return False
      if row.status not in TERMINAL_WORKFLOW_STATUSES:
       now=datetime.now(timezone.utc)
       row.heartbeat_at=now
       row.lease_expires_at=now+timedelta(seconds=WORKFLOW_LEASE_SECONDS)
       await db.commit()
   except asyncio.CancelledError:
    raise
   except Exception:
    logger.exception("Workflow lease heartbeat failed for %s",sid)
    return False

 async def _release_lease(self,sid:str,worker_id:str,workspace_id:str)->None:
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    row=await db.get(WorkflowRun,sid)
    if row is None or row.lease_owner!=worker_id:return
    if row.status in TERMINAL_WORKFLOW_STATUSES:
     row.lease_owner=None
     row.lease_expires_at=None
     await db.commit()

 async def _with_heartbeat(self,sid:str,worker_id:str,workspace_id:str,operation:Awaitable[Any])->None:
  operation_task=asyncio.create_task(operation,name=f"workflow-exec-{sid}")
  heartbeat_task=asyncio.create_task(self._heartbeat(sid,worker_id,workspace_id),name=f"workflow-lease-{sid}")
  try:
   done,_=await asyncio.wait({operation_task,heartbeat_task},return_when=asyncio.FIRST_COMPLETED)
   if heartbeat_task in done and not operation_task.done():
    try:owned=heartbeat_task.result()
    except Exception:owned=False
    if not owned:
     logger.warning("Workflow lease lost; cancelling local execution %s",sid)
     operation_task.cancel()
     await asyncio.gather(operation_task,return_exceptions=True)
     return
   if operation_task.done():
    try:await operation_task
    except WorkflowLeaseLost:
     logger.warning("Workflow %s stopped because its lease is no longer owned",sid)
    except asyncio.CancelledError:
     raise
    except Exception:
     logger.exception("Workflow task exited unexpectedly: %s",sid)
  finally:
   if not heartbeat_task.done():heartbeat_task.cancel()
   await asyncio.gather(heartbeat_task,return_exceptions=True)
   try:await self._release_lease(sid,worker_id,workspace_id)
   except Exception:logger.exception("Could not release terminal workflow lease %s",sid)
   if self.tasks.get(sid) is asyncio.current_task():self.tasks.pop(sid,None)

 async def _claim_interrupted_row(self)->dict[str,Any]|None:
  if not self.resolver:return None
  now=datetime.now(timezone.utc)
  with workspace_scope(None):
   async with SessionLocal() as db:
    stmt=select(WorkflowRun).where(
     WorkflowRun.status.in_(["queued","running"]),
     or_(WorkflowRun.lease_expires_at.is_(None),WorkflowRun.lease_expires_at<=now),
    ).order_by(WorkflowRun.created_at.asc()).limit(20).with_for_update(skip_locked=True)
    rows=list((await db.scalars(stmt)).all())
    row=next((candidate for candidate in rows if candidate.id not in self.tasks),None)
    if row is None:return None
    workspace_id=str(row.workspace_id or "").strip()
    state=copy.deepcopy(row.state_json or {})
    steps=self.resolver(row.workflow_name)
    if not workspace_id or not steps or row.current_step<0 or row.current_step>len(steps):
     row.status="failed"
     row.error_message="Workflow could not be recovered safely: missing workspace, resolver, or valid persisted step checkpoint."
     row.finished_at=now;row.lease_owner=None;row.lease_expires_at=None
     await db.commit()
     return {"reconciliation_only":True,"session_id":row.id}
    control=state.get("control") if isinstance(state.get("control"),dict) else {}
    if control.get("cancel_requested") is True:
     now_cancelled=datetime.now(timezone.utc)
     control["cancelled_at"]=control.get("cancelled_at") or now_cancelled.isoformat()
     state["control"]=control
     row.status="cancelled";row.state_json=state;row.result_json=state
     row.error_message="Workflow cancellation completed during worker recovery."
     row.finished_at=now_cancelled;row.lease_owner=None;row.lease_expires_at=None
     paused=await db.get(PausedSession,row.id)
     if paused is not None:
      paused.status="cancelled";paused.verification_response_encrypted=None
     db.add(AuditLog(
      workspace_id=workspace_id,actor=str(control.get("cancel_requested_by") or "workflow-recovery")[:320],
      action="workflow.cancelled",resource_type="workflow",resource_id=row.id,outcome="cancelled",
      details_json={"recovered":True,"safe_boundary":True,"in_flight_external_action_rolled_back":False},
     ))
     await db.commit()
     return {"reconciliation_only":True,"session_id":row.id}
    if row.status=="running" and row.current_step<len(steps):
     step=steps[row.current_step]
     metadata=state.get("metadata",{}) if isinstance(state.get("metadata",{}),dict) else {}
     live_side_effect=step.side_effecting and bool(state.get("publish_requests")) and not bool(getattr(get_settings(),"publishing_dry_run",True))
     if live_side_effect:
      failure="Workflow lease expired during a live external side-effecting stage; provider outcome must be reconciled before another attempt."
      with workspace_scope(workspace_id):
       row.status="failed";row.error_message=failure;row.finished_at=now;row.lease_owner=None;row.lease_expires_at=None
       db.add(AuditLog(
        workspace_id=workspace_id,
        actor=str(metadata.get("initiated_by") or "workflow-recovery")[:320],
        action="workflow.side_effect_outcome_unknown",
        resource_type="external_publication",
        resource_id=row.id,
        outcome="unknown",
        details_json={"stage":step.key,"automatic_retry":False,"manual_reconciliation_required":True,"reason":"worker_lease_expired"},
       ))
       await db.commit()
      logger.warning("Workflow %s requires manual reconciliation after lease expiry at %s",row.id,step.key)
      return {"reconciliation_only":True,"session_id":row.id}
    row.lease_owner=self.worker_id
    row.lease_expires_at=now+timedelta(seconds=WORKFLOW_LEASE_SECONDS)
    row.heartbeat_at=now
    row.attempt_count=(row.attempt_count or 0)+1
    await db.commit()
    return {"session_id":row.id,"workspace_id":workspace_id,"workflow_name":row.workflow_name,"state":state,"steps":steps,"start":row.current_step,"mode":row.execution_mode,"worker_id":self.worker_id}

 async def recover_interrupted(self)->int:
  recovered=0
  while True:
   claim=await self._claim_interrupted_row()
   if claim is None:break
   recovered+=1
   if claim.get("reconciliation_only"):continue
   sid=claim["session_id"];workspace_id=claim["workspace_id"]
   self.events.setdefault(sid,asyncio.Event())
   with workspace_scope(workspace_id):
    task=asyncio.create_task(
     self._with_heartbeat(sid,claim["worker_id"],workspace_id,self._drive(
      sid,claim["workflow_name"],claim["state"],claim["steps"],claim["start"],claim["mode"],worker_id=claim["worker_id"]
     )),
     name=f"affiliate-os-recovered-{sid}",
    )
    self.tasks[sid]=task
  return recovered

 async def _claim_paused_row(self)->dict[str,Any]|None:
  if not self.resolver:return None
  now=datetime.now(timezone.utc)
  with workspace_scope(None):
   async with SessionLocal() as db:
    stmt=select(PausedSession,WorkflowRun).join(WorkflowRun,WorkflowRun.id==PausedSession.session_id).where(
     PausedSession.status.in_(["paused","resuming","resume_requested"]),
     WorkflowRun.status=="paused",
     or_(WorkflowRun.lease_expires_at.is_(None),WorkflowRun.lease_expires_at<=now),
    ).order_by(WorkflowRun.created_at.asc()).limit(20).with_for_update(skip_locked=True)
    pairs=(await db.execute(stmt)).all()
    pair=next(((paused,run) for paused,run in pairs if run.id not in self.tasks),None)
    if pair is None:return None
    paused,run=pair
    workspace_id=str(run.workspace_id or paused.workspace_id or "").strip()
    if not workspace_id:return None
    steps=self.resolver(run.workflow_name)
    if not steps or paused.current_step<0 or paused.current_step>=len(steps):
     with workspace_scope(workspace_id):
      run.status="failed";run.error_message="Paused workflow could not be recovered: checkpoint no longer matches the workflow definition.";run.finished_at=now;run.lease_owner=None;run.lease_expires_at=None
      paused.status="failed"
      await db.commit()
     return {"reconciliation_only":True,"session_id":run.id}
    state=copy.deepcopy(run.state_json or paused.state_json or {})
    control=state.get("control") if isinstance(state.get("control"),dict) else {}
    if control.get("cancel_requested") is True:
     cancelled_at=datetime.now(timezone.utc)
     control["cancelled_at"]=control.get("cancelled_at") or cancelled_at.isoformat()
     state["control"]=control
     with workspace_scope(workspace_id):
      run.status="cancelled";run.state_json=state;run.result_json=state
      run.error_message="Workflow cancellation completed during paused-worker recovery."
      run.finished_at=cancelled_at;run.lease_owner=None;run.lease_expires_at=None
      paused.status="cancelled";paused.verification_response_encrypted=None
      db.add(AuditLog(
       workspace_id=workspace_id,actor=str(control.get("cancel_requested_by") or "workflow-recovery")[:320],
       action="workflow.cancelled",resource_type="workflow",resource_id=run.id,outcome="cancelled",
       details_json={"recovered_paused":True,"safe_boundary":True,"in_flight_external_action_rolled_back":False},
      ))
      await db.commit()
     return {"reconciliation_only":True,"session_id":run.id}
    metadata=state.get("metadata")
    if not isinstance(metadata,dict):metadata={}
    metadata["workspace_id"]=workspace_id;state["metadata"]=metadata
    with workspace_scope(workspace_id):
     # Preserve queued encrypted responses after a lease changes. The new
     # owner consumes that response before asking the operator to resubmit.
     if paused.status in {"resuming","resume_requested"}:
      paused.status="resume_requested" if paused.verification_response_encrypted else "paused"
     run.lease_owner=self.worker_id
     run.lease_expires_at=now+timedelta(seconds=WORKFLOW_LEASE_SECONDS)
     run.heartbeat_at=now
     run.attempt_count=(run.attempt_count or 0)+1
     await db.commit()
    return {"session_id":run.id,"workspace_id":workspace_id,"workflow_name":run.workflow_name,"state":state,"steps":steps,"index":paused.current_step,"mode":run.execution_mode,"action":paused.required_action,"error":paused.last_error,"worker_id":self.worker_id}

 async def recover_paused(self)->int:
  recovered=0
  while True:
   claim=await self._claim_paused_row()
   if claim is None:break
   recovered+=1
   if claim.get("reconciliation_only"):continue
   sid=claim["session_id"];workspace_id=claim["workspace_id"]
   self.events[sid]=asyncio.Event()
   with workspace_scope(workspace_id):
    task=asyncio.create_task(
     self._with_heartbeat(sid,claim["worker_id"],workspace_id,self._wait_recovered_pause(
      sid,claim["workflow_name"],claim["state"],claim["steps"],claim["index"],claim["mode"],claim["action"],claim["error"],worker_id=claim["worker_id"]
     )),
     name=f"affiliate-os-paused-recovery-{sid}",
    )
    self.tasks[sid]=task
  return recovered

 async def _recovery_loop(self)->None:
  while True:
   try:
    await self.wake_pending_responses()
    await self.recover_interrupted()
    await self.recover_paused()
    await self.wake_pending_responses()
   except asyncio.CancelledError:
    raise
   except Exception:
    logger.exception("Durable workflow recovery scan failed")
   await asyncio.sleep(WORKFLOW_RECOVERY_INTERVAL_SECONDS)

 async def start_recovery_worker(self)->None:
  if self._recovery_task is None or self._recovery_task.done():
   self._recovery_task=asyncio.create_task(self._recovery_loop(),name="affiliate-os-workflow-recovery")

 async def stop_recovery_worker(self)->None:
  if self._recovery_task is not None:
   self._recovery_task.cancel()
   await asyncio.gather(self._recovery_task,return_exceptions=True)
   self._recovery_task=None
  active=list(self.tasks.values())
  for task in active:task.cancel()
  if active:await asyncio.gather(*active,return_exceptions=True)
  now=datetime.now(timezone.utc)
  with workspace_scope(None):
   async with SessionLocal() as db:
    # Termination stops renewals immediately. Expired leases are recovered on next
    # startup; live side-effecting stages are reconciled rather than replayed.
    await db.execute(
     WorkflowRun.__table__.update().where(
      WorkflowRun.lease_owner==self.worker_id,
      WorkflowRun.status.in_(["queued","running","paused"]),
     ).values(lease_expires_at=now,heartbeat_at=now)
    )
    await db.commit()
runner=WorkflowRunner()

from __future__ import annotations
import asyncio,copy,logging,uuid
from dataclasses import dataclass
from datetime import datetime,timezone
from typing import Any,Awaitable,Callable
from sqlalchemy import select
from backend.config import get_settings
from backend.core.errors import VerificationRequiredError
from backend.core.events import hub
from backend.database import SessionLocal
from backend.models import AuditLog,PausedSession,WorkflowRun
from backend.tenancy import get_workspace_id,workspace_scope
logger=logging.getLogger(__name__)
StageHandler=Callable[[dict[str,Any]],Awaitable[dict[str,Any]|None]]
@dataclass(frozen=True)
class WorkflowStep:
 key: str
 label: str
 handler: StageHandler
 side_effecting: bool = False
class WorkflowRunner:
 def __init__(self):self.tasks:dict[str,asyncio.Task]={};self.events:dict[str,asyncio.Event]={};self.responses:dict[str,str]={};self.resolver:Callable[[str],list[WorkflowStep]]|None=None
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
  sid=str(uuid.uuid4());state=copy.deepcopy(state);state.setdefault("metadata",{}).update({"workflow":name,"execution_mode":mode,"started_at":datetime.now(timezone.utc).isoformat(),"workspace_id":workspace_id})
  async with SessionLocal() as db:
   db.add(WorkflowRun(id=sid,workflow_name=name,status="queued",execution_mode=mode,state_json=state));db.add(AuditLog(actor="system",action="workflow.started",resource_type="workflow",resource_id=sid,details_json={"name":name,"mode":mode}));await db.commit()
  self.events[sid]=asyncio.Event();self.tasks[sid]=asyncio.create_task(self._drive(sid,name,state,steps,0,mode),name=f"affiliate-os-{sid}");return sid
 async def _save(self,sid:str,status:str,index:int,state:dict[str,Any],error:str|None=None,done:bool=False,result:dict|None=None):
  safe=copy.deepcopy(state);safe.pop("_verification_response",None)
  async with SessionLocal() as db:
   row=await db.get(WorkflowRun,sid)
   if not row:return
   row.status=status;row.current_step=index;row.state_json=safe
   if error is not None:row.error_message=error[:2000]
   if result is not None:row.result_json=result
   if status=="running" and row.started_at is None:row.started_at=datetime.now(timezone.utc)
   if done:row.finished_at=datetime.now(timezone.utc)
   await db.commit()
 async def _pause(self,sid:str,name:str,index:int,state:dict[str,Any],exc:VerificationRequiredError):
  safe=copy.deepcopy(state);safe.pop("_verification_response",None)
  async with SessionLocal() as db:
   row=await db.get(PausedSession,sid)
   if row is None:row=PausedSession(session_id=sid,workflow_name=name);db.add(row)
   row.status="paused";row.current_step=index;row.required_action=exc.action;row.state_json=safe;row.last_error=str(exc)[:800]
   run=await db.get(WorkflowRun,sid)
   if run:run.status="paused";run.current_step=index;run.state_json=safe
   db.add(AuditLog(actor="system",action="workflow.paused_for_verification",resource_type="workflow",resource_id=sid,details_json={"index":index,"action":exc.action}));await db.commit()
 async def _drive(self,sid:str,name:str,state:dict[str,Any],steps:list[WorkflowStep],start:int,mode:str):
  settings=get_settings();event=self.events.setdefault(sid,asyncio.Event());await self._save(sid,"running",start,state)
  await self._emit(state, {"event":"WORKFLOW_STATUS","session_id":sid,"workflow_name":name,"status":"running","current_step":start,"total_steps":len(steps)})
  try:
   for i in range(start,len(steps)):
    step=steps[i];await self._save(sid,"running",i,state)
    await self._emit(state, {"event":"STAGE_STATUS","session_id":sid,"stage":step.key,"stage_label":step.label,"status":"running","current_step":i,"total_steps":len(steps)})
    attempts=0
    while True:
     try:
      result=await asyncio.wait_for(step.handler(state),timeout=int(settings.load_yaml().get("app",{}).get("workflow_step_timeout_seconds",120)))
      nested=[v.get("status") for k,v in (result or {}).items() if k.endswith("_result") and isinstance(v,dict) and v.get("status")]
      stage_status="skipped" if nested and all(x=="skipped" for x in nested) else "completed"
      state.setdefault("stages",{})[step.key]={"status":stage_status,"result":result or {},"completed_at":datetime.now(timezone.utc).isoformat()}
      if isinstance(result,dict):state.update({k:v for k,v in result.items() if k not in {"metadata","stages"}})
      await self._save(sid,"running",i+1,state)
      await self._emit(state, {"event":"STAGE_STATUS","session_id":sid,"stage":step.key,"stage_label":step.label,"status":stage_status,"current_step":i+1,"total_steps":len(steps)});break
     except VerificationRequiredError as exc:
      if mode=="FULL_AUTONOMOUS":
       await self._save(sid,"failed",i,state,f"Human verification required in FULL_AUTONOMOUS mode: {exc}",True);return
      await self._pause(sid,name,i,state,exc)
      await self._emit(state, {"event":"HITL_ALERT","session_id":sid,"workflow_name":name,"stage":step.key,"stage_label":step.label,"required_action":exc.action,"message":str(exc)})
      await event.wait();event.clear();state["_verification_response"]=self.responses.pop(sid,"")
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
      await self._save(sid,"failed",i,state,failure_message,True)
      await self._emit(state, {"event":"WORKFLOW_STATUS","session_id":sid,"status":"failed","stage":step.key,"message":failure_message[:300]})
      return
   state.setdefault("metadata",{})["finished_at"]=datetime.now(timezone.utc).isoformat();await self._save(sid,"completed",len(steps),state,done=True,result=state)
   async with SessionLocal() as db:db.add(AuditLog(actor="system",action="workflow.completed",resource_type="workflow",resource_id=sid,details_json={"name":name}));await db.commit()
   await self._emit(state, {"event":"WORKFLOW_STATUS","session_id":sid,"workflow_name":name,"status":"completed","current_step":len(steps),"total_steps":len(steps)})
  except asyncio.CancelledError:await self._save(sid,"cancelled",0,state,done=True);raise
  finally:self.tasks.pop(sid,None)
 async def resume(self,sid:str,code:str,workspace_id:str)->dict[str,Any]:
  if not isinstance(workspace_id,str) or not workspace_id.strip():raise KeyError("Paused session not found")
  if not code.strip() or len(code)>512:raise ValueError("Verification response must be 1..512 characters")
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    paused=await db.get(PausedSession,sid);run=await db.get(WorkflowRun,sid)
    if not paused or not run:raise KeyError("Paused session not found")
    if paused.workspace_id!=workspace_id or run.workspace_id!=workspace_id:raise KeyError("Paused session not found")
    if paused.status!="paused" or run.status!="paused":raise ValueError("Workflow is not paused")
    paused.status="resume_requested";await db.commit()
  self.responses[sid]=code.strip();self.events.setdefault(sid,asyncio.Event()).set()
  return {"session_id":sid,"status":"resume_requested","verification_code_persisted":False}
 async def status(self,sid:str,workspace_id:str|None=None)->dict[str,Any]|None:
  if not isinstance(workspace_id,str) or not workspace_id.strip():return None
  with workspace_scope(workspace_id):
   async with SessionLocal() as db:
    run=await db.get(WorkflowRun,sid)
    if not run or run.workspace_id!=workspace_id:return None
    paused=await db.get(PausedSession,sid)
    return {"session_id":sid,"workflow_name":run.workflow_name,"status":run.status,"current_step":run.current_step,"execution_mode":run.execution_mode,"state":run.state_json,"result":run.result_json,"error":run.error_message,"paused_session":{"status":paused.status,"required_action":paused.required_action,"stage_index":paused.current_step} if paused and paused.workspace_id==workspace_id else None}
 async def _wait_recovered_pause(self,sid:str,name:str,state:dict[str,Any],steps:list[WorkflowStep],index:int,mode:str,action:str,error:str|None):
  event=self.events.setdefault(sid,asyncio.Event())
  await self._emit(state, {"event":"HITL_ALERT","session_id":sid,"workflow_name":name,"stage":steps[index].key if index<len(steps) else None,"stage_label":steps[index].label if index<len(steps) else None,"required_action":action,"message":error or "Workflow recovered paused; human response required."})
  await event.wait();event.clear();state["_verification_response"]=self.responses.pop(sid,"")
  async with SessionLocal() as db:
   row=await db.get(PausedSession,sid)
   if row:row.status="resuming";await db.commit()
  await self._drive(sid,name,state,steps,index,mode)
 async def recover_paused(self)->int:
  if not self.resolver:return 0
  async with SessionLocal() as db:rows=list((await db.scalars(select(PausedSession).where(PausedSession.status=="paused"))).all())
  count=0
  for row in rows:
   if row.session_id in self.tasks:continue
   async with SessionLocal() as db:
    fresh=await db.get(PausedSession,row.session_id)
    if fresh and fresh.status!="paused":fresh.status="paused";await db.commit()
   if not row.workspace_id:continue
   run=await self.status(row.session_id,workspace_id=row.workspace_id)
   if not run:continue
   steps=self.resolver(row.workflow_name)
   if row.current_step>=len(steps):continue
   self.events[row.session_id]=asyncio.Event()
   # Restore tenant context for resumed writes and emitted WebSocket events.
   recovered_state=run["state"] or {}
   recovered_state.setdefault("metadata",{})["workspace_id"]=row.workspace_id
   with workspace_scope(row.workspace_id):
    self.tasks[row.session_id]=asyncio.create_task(self._wait_recovered_pause(row.session_id,row.workflow_name,recovered_state,steps,row.current_step,run["execution_mode"],row.required_action,row.last_error))
   count+=1
  return count
runner=WorkflowRunner()

"use client";

import {useCallback,useEffect,useState} from "react";
import {apiFetch} from "@/lib/api";

type PlatformExecutionControl = {
  id:number;
  outbound_actions_paused:boolean;
  reason:string|null;
  changed_by:string|null;
  changed_at:string|null;
  enforcement_scope:string;
  completed_idempotency_replays_allowed:boolean;
  in_flight_actions_cancelled:boolean;
  note:string;
};
type WorkspaceTenant = {
  id:string;
  name:string;
  slug:string;
  owner_user_id:string|null;
  active_memberships:number;
  created_at:string|null;
  lifecycle_state:"active"|"suspended";
  suspended_at:string|null;
  suspended_by:string|null;
  suspension_reason:string|null;
};
type WorkspaceTenantResponse = {
  count:number;
  limit:number;
  read_only:boolean;
  lifecycle_mutations_available:boolean;
  active_workspace_id:string|null;
  data:WorkspaceTenant[];
};

type PlatformOverview = {
  counts:{users:number;workspaces:number;active_workspace_memberships:number;workflow_runs_persisted:number;audit_events_persisted:number};
  runtime:{environment:string;scheduler_running:boolean;publishing_dry_run:boolean;ad_automation_execute:boolean;durable_queue_status:string};
  release:{deployment_verification:string;note:string};
};
type AdminWorkflow = {id:string;workspace_id:string;workflow_name:string;status:string;current_step:string|null;execution_mode:string;has_error:boolean;created_at:string|null};
type AdminAuditEvent = {id:number;workspace_id:string|null;actor:string;action:string;resource_type:string;resource_id:string;outcome:string;created_at:string|null};
type ProviderReadiness = {provider_id:string;display_name:string;status:string;write_access_verified:boolean;reason:string};


const inputClass="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm";
const buttonClass="rounded-xl px-4 py-2.5 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-50";

export default function TenantLifecyclePage(){
  const [tenantResponse,setTenantResponse]=useState<WorkspaceTenantResponse|null>(null);
  const [executionControl,setExecutionControl]=useState<PlatformExecutionControl|null>(null);
  const [controlReason,setControlReason]=useState("");
  const [controlLoading,setControlLoading]=useState(false);
  const [controlBusy,setControlBusy]=useState(false);
  const [reasons,setReasons]=useState<Record<string,string>>({});
  const [loading,setLoading]=useState(false);
  const [busyId,setBusyId]=useState("");
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [overview,setOverview]=useState<PlatformOverview|null>(null);
  const [workflows,setWorkflows]=useState<AdminWorkflow[]>([]);
  const [providers,setProviders]=useState<ProviderReadiness[]>([]);
  const [auditEvents,setAuditEvents]=useState<AdminAuditEvent[]>([]);
  const [operationsLoading,setOperationsLoading]=useState(false);
  const [operationsError,setOperationsError]=useState("");


  const loadTenants=useCallback(async()=>{
    setLoading(true);
    setError("");
    try{
      const response=await apiFetch<WorkspaceTenantResponse>("/api/admin/tenants?limit=100");
      setTenantResponse(response);
    }catch(err){
      setError(err instanceof Error?err.message:"Could not load tenant inventory.");
    }finally{
      setLoading(false);
    }
  },[]);

  const loadExecutionControl=useCallback(async()=>{
    setControlLoading(true);
    setError("");
    try{
      const response=await apiFetch<PlatformExecutionControl>("/api/admin/execution-control");
      setExecutionControl(response);
    }catch(err){
      setError(err instanceof Error?err.message:"Could not load the platform provider-write control.");
    }finally{
      setControlLoading(false);
    }
  },[]);

  const changeExecutionControl=async()=>{
    const reason=controlReason.trim();
    if(reason.length<10){
      setError("Enter an audit reason with at least ten non-whitespace characters.");
      return;
    }
    if(!executionControl)return;
    const paused=!executionControl.outbound_actions_paused;
    setControlBusy(true);
    setError("");
    setNotice("");
    try{
      const result=await apiFetch<PlatformExecutionControl>("/api/admin/execution-control",{
        method:"POST",
        body:JSON.stringify({outbound_actions_paused:paused,reason}),
      });
      setExecutionControl(result);
      setControlReason("");
      setNotice(result.outbound_actions_paused
        ?"New registry-gated provider writes are paused."
        :"Registry-gated provider writes are resumed.");
    }catch(err){
      setError(err instanceof Error?err.message:"Platform provider-write control update failed.");
    }finally{
      setControlBusy(false);
    }
  };

  const loadOperations=useCallback(async()=>{
    setOperationsLoading(true);
    setOperationsError("");
    try{
      const [overviewData,workflowData,registryData,auditData]=await Promise.all([
        apiFetch<PlatformOverview>("/api/admin/overview"),
        apiFetch<{data:AdminWorkflow[]}>("/api/admin/workflows?limit=20"),
        apiFetch<{items:ProviderReadiness[]}>("/api/integrations"),
        apiFetch<{data:AdminAuditEvent[]}>("/api/admin/audit?limit=20"),
      ]);
      setOverview(overviewData);
      setWorkflows(workflowData.data||[]);
      setProviders(registryData.items||[]);
      setAuditEvents(auditData.data||[]);
    }catch(err){
      setOperationsError(err instanceof Error?err.message:"Could not load platform operations evidence.");
    }finally{
      setOperationsLoading(false);
    }
  },[]);

  useEffect(()=>{void loadTenants();},[loadTenants]);
  useEffect(()=>{void loadExecutionControl();},[loadExecutionControl]);
  useEffect(()=>{void loadOperations();},[loadOperations]);

  const transition=async(tenant:WorkspaceTenant)=>{
    const reason=(reasons[tenant.id]||"").trim();
    if(reason.length<10){
      setError("Enter an audit reason with at least ten non-whitespace characters.");
      return;
    }
    const action=tenant.lifecycle_state==="active"?"suspend":"reinstate";
    if(action==="suspend"&&tenant.id===tenantResponse?.active_workspace_id){
      setError("Switch to a different active workspace before suspending the current administrative workspace.");
      return;
    }
    setBusyId(tenant.id);
    setError("");
    setNotice("");
    try{
      const result=await apiFetch<WorkspaceTenant>("/api/admin/tenants/"+encodeURIComponent(tenant.id)+"/"+action,{
        method:"POST",
        body:JSON.stringify({reason}),
      });
      setTenantResponse(current=>current?{
        ...current,
        data:current.data.map(row=>row.id===result.id?{...row,...result}:row),
      }:current);
      setReasons(current=>({...current,[tenant.id]:""}));
      setNotice(tenant.name+" workspace "+result.lifecycle_state+". The transition and reason were added to the audit trail.");
    }catch(err){
      setError(err instanceof Error?err.message:"Tenant lifecycle transition failed.");
    }finally{
      setBusyId("");
    }
  };

  const tenants=tenantResponse?.data||[];
  const activeCount=tenants.filter(t=>t.lifecycle_state==="active").length;
  const suspendedCount=tenants.filter(t=>t.lifecycle_state==="suspended").length;

  return <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10">
    <div className="mx-auto max-w-6xl">
      <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex flex-wrap gap-4 text-sm font-semibold">
            <a href="/" className="text-indigo-600 hover:underline">← Growth command</a>
            <a href="/#operations" className="text-indigo-600 hover:underline">Operations overview</a>
          </div>
          <p className="mt-4 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Platform Super Admin</p>
          <h1 className="mt-1 text-3xl font-black tracking-tight">Tenant lifecycle console</h1>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">Suspend or reinstate a workspace with a mandatory human reason and tenant-scoped audit evidence.</p>
        </div>
        <button type="button" onClick={()=>void loadTenants()} disabled={loading||!!busyId} className={buttonClass+" border border-slate-200 bg-white text-slate-700"}>Refresh tenant inventory</button>
      </header>

      <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <strong>Safety boundary:</strong> a suspended workspace cannot start new authenticated API sessions, disappears from scheduled worker enumeration, and its workflow runner stops before another stage at a safe boundary. A provider request already in flight is not rolled back. Switch to a different active workspace before suspending the workspace used by this admin session.
      </div>

      <section aria-label="Platform-wide provider-write pause" className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-[.16em] text-indigo-600">Global emergency control</p>
            <h2 className="mt-1 text-xl font-black">Platform-wide provider-write pause</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">Pause or resume new actions routed through the shared external-action idempotency registry. This persistent platform control is separate from each provider's credentials and dry-run configuration.</p>
          </div>
          <span className={"rounded-full border px-3 py-2 text-xs font-bold "+(executionControl?.outbound_actions_paused?"border-rose-200 bg-rose-50 text-rose-800":"border-emerald-200 bg-emerald-50 text-emerald-800")}>
            {controlLoading?"Loading control…":executionControl?.outbound_actions_paused?"Provider writes paused":executionControl?"Provider writes not paused":"Control unavailable"}
          </span>
        </div>
        {executionControl?.changed_at&&<p className="mt-3 text-xs text-slate-500">Last changed by {executionControl.changed_by||"unknown operator"} · {new Date(executionControl.changed_at).toLocaleString()}{executionControl.reason?" · Reason: "+executionControl.reason:""}</p>}
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-5 text-amber-950">
          <strong>Enforcement boundary:</strong> new social, CMS, bio-link and GitHub Pages writes using the shared registry are denied while paused. Completed idempotency replays can return their recorded result. Already-claimed/in-flight operations cannot be rolled back, and other side-effecting paths not using this registry still require separate guards.
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
          <label className="block text-sm font-semibold text-slate-700" htmlFor="platform-execution-control-reason">Audit reason for platform-wide provider-write pause
            <textarea id="platform-execution-control-reason" rows={2} maxLength={2000} minLength={10} value={controlReason} onChange={event=>setControlReason(event.target.value)} className={inputClass} placeholder={executionControl?.outbound_actions_paused?"Why are provider writes safe to resume?":"Why should new provider writes be paused?"}/>
          </label>
          <button type="button" onClick={()=>void changeExecutionControl()} disabled={controlLoading||controlBusy||!executionControl||controlReason.trim().length<10} className={buttonClass+" "+(executionControl?.outbound_actions_paused?"bg-indigo-600 text-white":"bg-rose-600 text-white")}>
            {controlBusy?"Saving global control…":executionControl?.outbound_actions_paused?"Resume registry-gated provider writes":"Pause registry-gated provider writes"}
          </button>
        </div>
      </section>

      {error&&<div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
      {notice&&<div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}

      <section aria-labelledby="platform-operations-title" className="mt-6 space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-[.16em] text-indigo-600">Persisted platform evidence · read only</p>
            <h2 id="platform-operations-title" className="mt-1 text-2xl font-black">Platform operations overview</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">Protected API observations for platform operations. These do not certify deployment, queue health or provider connectivity.</p>
          </div>
          <button type="button" onClick={()=>void loadOperations()} disabled={operationsLoading} className={buttonClass+" border border-slate-200 bg-white text-slate-700"}>{operationsLoading?"Refreshing operations…":"Refresh operations"}</button>
        </div>
        {operationsError&&<div role="alert" data-testid="platform-operations-error" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{operationsError}</div>}
        {operationsLoading&&!overview&&<p className="text-sm text-slate-500">Loading platform operations evidence…</p>}
        {overview&&<>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <article className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs font-bold uppercase text-slate-500">Users</p><p data-testid="platform-metric-users" className="mt-1 text-2xl font-black">{overview.counts.users.toLocaleString()}</p></article>
            <article className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs font-bold uppercase text-slate-500">Workspaces</p><p data-testid="platform-metric-workspaces" className="mt-1 text-2xl font-black">{overview.counts.workspaces.toLocaleString()}</p></article>
            <article className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs font-bold uppercase text-slate-500">Memberships</p><p data-testid="platform-metric-memberships" className="mt-1 text-2xl font-black">{overview.counts.active_workspace_memberships.toLocaleString()}</p></article>
            <article className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs font-bold uppercase text-slate-500">Workflow runs</p><p data-testid="platform-metric-workflows" className="mt-1 text-2xl font-black">{overview.counts.workflow_runs_persisted.toLocaleString()}</p></article>
            <article className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs font-bold uppercase text-slate-500">Audit events</p><p data-testid="platform-metric-audits" className="mt-1 text-2xl font-black">{overview.counts.audit_events_persisted.toLocaleString()}</p></article>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <h3 className="text-lg font-black">Runtime and release observations · {overview.runtime.environment}</h3>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                <div><dt className="text-xs text-slate-500">Scheduler process</dt><dd data-testid="platform-scheduler-state" className="text-sm font-bold">{overview.runtime.scheduler_running?"Running":"Not running"}</dd></div>
                <div><dt className="text-xs text-slate-500">Publishing dry-run</dt><dd className="text-sm font-bold">{overview.runtime.publishing_dry_run?"Enabled":"Disabled"}</dd></div>
                <div><dt className="text-xs text-slate-500">Ad automation execution</dt><dd className="text-sm font-bold">{overview.runtime.ad_automation_execute?"Enabled":"Disabled"}</dd></div>
                <div><dt className="text-xs text-slate-500">Durable queue status</dt><dd data-testid="platform-queue-state" className="break-words text-sm font-bold">{overview.runtime.durable_queue_status.replace(/_/g," ")}</dd></div>
                <div><dt className="text-xs text-slate-500">Deployment verification</dt><dd className="text-sm font-bold">{overview.release.deployment_verification.replace(/_/g," ")}</dd></div>
              </dl>
              <p className="mt-4 rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-900">Runtime flags are observations, not proof of durable queue health or production deployment. {overview.release.note}</p>
            </section>
            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <h3 className="text-lg font-black">Affiliate provider readiness · {providers.length} entries</h3>
              <div className="mt-3 space-y-2">
                {providers.slice(0,8).map(provider=><article key={provider.provider_id} data-testid={"provider-readiness-"+provider.provider_id} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                  <div className="flex flex-wrap justify-between gap-2"><strong className="text-sm">{provider.display_name}</strong><span className="text-xs font-bold">{provider.status.replace(/_/g," ")}</span></div>
                  <p className="mt-1 text-xs text-slate-600">{provider.reason}</p>
                  <p className="mt-1 text-[11px] font-semibold text-slate-500">Write access: {provider.write_access_verified?"verified":"not verified"}</p>
                </article>)}
                {providers.length===0&&<p className="text-sm text-slate-500">No provider registry entries.</p>}
              </div>
            </section>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <h3 className="text-lg font-black">Recent workflow runs · read only</h3>
              <div className="mt-3 space-y-2">
                {workflows.map(run=><article key={run.id} data-testid={"platform-workflow-"+run.id} className="rounded-xl border border-slate-100 p-3">
                  <div className="flex flex-wrap justify-between gap-2"><strong className="text-sm">{run.workflow_name}</strong><span className="text-xs font-bold">{run.status.replace(/_/g," ")}</span></div>
                  <p className="mt-1 text-xs text-slate-600">Mode: {run.execution_mode.replace(/_/g," ")} · Stage: {run.current_step||"not recorded"}</p>
                  <p className="mt-1 break-all text-[11px] text-slate-500">Workspace: {run.workspace_id}</p>
                  {run.has_error&&<p className="mt-1 text-xs font-bold text-rose-700">Recorded workflow error; inspect using an authorized support process.</p>}
                </article>)}
                {workflows.length===0&&<p className="text-sm text-slate-500">No persisted workflow runs.</p>}
              </div>
            </section>
            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <h3 className="text-lg font-black">Recent platform audit events · read only</h3>
              <div className="mt-3 space-y-2">
                {auditEvents.map(event=><article key={event.id} data-testid={"platform-audit-"+event.id} className="rounded-xl border border-slate-100 p-3">
                  <div className="flex flex-wrap justify-between gap-2"><strong className="text-sm">{event.action}</strong><span className="text-xs font-bold">{event.outcome}</span></div>
                  <p className="mt-1 text-xs text-slate-600">{event.actor} · {event.resource_type} · {event.resource_id}</p>
                  <p className="mt-1 break-all text-[11px] text-slate-500">Workspace: {event.workspace_id||"platform scope"}</p>
                </article>)}
                {auditEvents.length===0&&<p className="text-sm text-slate-500">No recent audit events.</p>}
              </div>
            </section>
          </div>
        </>}
      </section>

      <section className="mt-5 grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Returned tenants</p><p className="mt-1 text-2xl font-black">{tenantResponse?.count??"—"}</p></div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Active</p><p className="mt-1 text-2xl font-black text-emerald-700">{activeCount}</p></div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Suspended</p><p className="mt-1 text-2xl font-black text-rose-700">{suspendedCount}</p></div>
      </section>

      {loading&&<p className="mt-6 text-sm text-slate-500">Loading tenant inventory…</p>}
      {!loading&&tenants.length===0&&<section className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white p-7 text-sm text-slate-600">No tenants were returned, or the active session lacks Platform Super Admin access.</section>}

      <section className="mt-6 space-y-4">
        {tenants.map(tenant=><article key={tenant.id} aria-label={"Tenant "+tenant.name} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="break-words text-lg font-black">{tenant.name}</h2>
              <p className="mt-1 break-all font-mono text-xs text-slate-500">{tenant.id} · {tenant.slug}</p>
              <p className="mt-1 text-xs text-slate-500">Owner: {tenant.owner_user_id||"Not recorded"} · Active memberships: {tenant.active_memberships}</p>
            </div>
            <span className={"rounded-full border px-3 py-1 text-xs font-bold "+(tenant.lifecycle_state==="active"?"border-emerald-200 bg-emerald-50 text-emerald-800":"border-rose-200 bg-rose-50 text-rose-800")}>{tenant.lifecycle_state}</span>
          </div>

          {tenant.lifecycle_state==="suspended"&&<div className="mt-4 rounded-xl bg-rose-50/60 p-3 text-sm">
            <p className="font-bold text-rose-900">Suspended by {tenant.suspended_by||"unknown operator"}{tenant.suspended_at?" · "+new Date(tenant.suspended_at).toLocaleString():""}</p>
            <p className="mt-1 whitespace-pre-wrap text-rose-800">Reason: {tenant.suspension_reason||"Not recorded"}</p>
          </div>}

          <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
            <label className="block text-sm font-semibold text-slate-700" htmlFor={"tenant-reason-"+tenant.id}>Audit reason for {tenant.name}
              <textarea id={"tenant-reason-"+tenant.id} rows={2} maxLength={2000} minLength={10} value={reasons[tenant.id]||""} onChange={event=>setReasons(current=>({...current,[tenant.id]:event.target.value}))} className={inputClass} placeholder={tenant.lifecycle_state==="active"?"Why should this tenant be suspended?":"Why should access be restored?"}/>
            </label>
            <button type="button" onClick={()=>void transition(tenant)} disabled={!!busyId||(reasons[tenant.id]||"").trim().length<10||(tenant.lifecycle_state==="active"&&tenant.id===tenantResponse?.active_workspace_id)} className={buttonClass+" "+(tenant.lifecycle_state==="active"?"bg-rose-600 text-white":"bg-indigo-600 text-white")}>
              {busyId===tenant.id?"Saving lifecycle change…":tenant.lifecycle_state==="active"?"Suspend "+tenant.name:"Reinstate "+tenant.name}
            </button>
          </div>
          {tenant.lifecycle_state==="active"&&tenant.id===tenantResponse?.active_workspace_id&&<p className="mt-2 text-xs font-semibold text-amber-800">Current administrative workspace is protected from self-suspension.</p>}
        </article>)}
      </section>
      <p className="mt-6 text-xs leading-5 text-slate-500">This is a workspace lifecycle control, not an account ban. In-flight provider operations cannot be undone. Each transition requires Platform Super Admin and is audited under the affected workspace.</p>
    </div>
  </main>;
}

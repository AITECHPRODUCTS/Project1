"use client";

import {useCallback,useEffect,useState} from "react";
import {apiFetch} from "@/lib/api";

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

const inputClass="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm";
const buttonClass="rounded-xl px-4 py-2.5 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-50";

export default function TenantLifecyclePage(){
  const [tenantResponse,setTenantResponse]=useState<WorkspaceTenantResponse|null>(null);
  const [reasons,setReasons]=useState<Record<string,string>>({});
  const [loading,setLoading]=useState(false);
  const [busyId,setBusyId]=useState("");
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");

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

  useEffect(()=>{void loadTenants();},[loadTenants]);

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

      {error&&<div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
      {notice&&<div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}

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

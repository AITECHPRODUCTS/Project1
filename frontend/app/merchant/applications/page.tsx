"use client";

import {useCallback,useEffect,useState} from "react";
import {apiFetch} from "@/lib/api";

type Application={
  id:string;merchant_offer_id:string;publisher_workspace_id:string;offer_name:string;applicant_email:string;
  publisher_website_url:string;audience_description:string;traffic_sources:string[];intended_regions:string[];
  promotion_plan:string;terms_snapshot:Record<string,unknown>;status:string;reviewer_notes:string|null;
  provider_submission_status:string;affiliate_network_approved:boolean;
};
const fieldClass="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm";

export default function MerchantApplicationsPage(){
  const [applications,setApplications]=useState<Application[]>([]);
  const [notes,setNotes]=useState("");
  const [busy,setBusy]=useState("");
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const load=useCallback(async()=>{
    setError("");
    try{const result=await apiFetch<{count:number;data:Application[]}>("/api/merchant/applications");setApplications(result.data||[]);}
    catch(e){setError(e instanceof Error?e.message:"Could not load incoming applications. Sign in as an owner/admin of the offer's merchant workspace.");}
  },[]);
  useEffect(()=>{void load()},[load]);
  const review=async(application:Application,decision:"approve"|"reject")=>{
    setBusy(application.id+decision);setError("");setNotice("");
    try{
      const result=await apiFetch<Application>("/api/merchant/applications/"+encodeURIComponent(application.id)+"/review",{
        method:"POST",body:JSON.stringify({decision,reviewer_notes:notes})
      });
      setNotice(result.offer_name+" application "+result.status+". This is an internal decision; external network approval remains unconfigured.");
      setNotes("");await load();
    }catch(e){setError(e instanceof Error?e.message:"Review failed.");}
    finally{setBusy("")}
  };
  return <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10"><div className="mx-auto max-w-6xl">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><a href="/merchant/offers" className="text-sm font-bold text-indigo-700">← Merchant offers</a><p className="mt-6 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Merchant · Incoming applications</p><h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Publisher applications</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">Review applications only for merchant offers owned by the active workspace. Decisions are internal to OmniAffiliateOS and do not submit an external network application or confirm network approval.</p></div><button onClick={()=>void load()} disabled={!!busy} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">Refresh</button></header>
    {error&&<div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
    {notice&&<div role="status" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
    <section className="mt-7 rounded-3xl border border-white bg-white p-5 shadow-sm sm:p-7"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-xl font-black">Applications received</h2><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{applications.filter(x=>x.status==="pending_review").length} pending</span></div>
      <label className="mt-5 block text-sm font-bold" htmlFor="merchant-app-review-notes">Review note for the next decision</label><textarea id="merchant-app-review-notes" className={fieldClass} rows={2} value={notes} onChange={e=>setNotes(e.target.value)} maxLength={3000} placeholder="Explain the decision and any missing compliance evidence."/>
      <div className="mt-5 grid gap-4">
        {applications.length===0&&<p className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">No publisher applications have been received by this merchant workspace.</p>}
        {applications.map(app=><article key={app.id} className="rounded-2xl border border-slate-200 p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-black">{app.offer_name}</h3><p className="mt-1 text-sm text-slate-500">Publisher contact: {app.applicant_email}</p><p className="mt-1 break-all text-xs text-indigo-700"><a href={app.publisher_website_url} target="_blank" rel="noreferrer">{app.publisher_website_url}</a></p></div><span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold">{app.status.replaceAll("_"," ")}</span></div>
          <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Requested regions</p><p className="mt-1 text-sm font-bold">{app.intended_regions.join(", ")}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Traffic sources</p><p className="mt-1 text-sm font-bold">{app.traffic_sources.join(", ")}</p></div></div>
          <p className="mt-3 text-sm leading-6 text-slate-600">{app.audience_description}</p><div className="mt-3 rounded-xl border border-slate-200 p-3"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Promotion plan</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{app.promotion_plan}</p></div>
          <p className="mt-3 text-xs leading-5 text-slate-500">Terms version snapshot: {String(app.terms_snapshot.terms_version||"unknown")} · External network submission: {app.provider_submission_status} · Affiliate network approved: no</p>
          {app.reviewer_notes&&<p className="mt-2 text-sm text-slate-600">Previous review note: {app.reviewer_notes}</p>}
          {app.status==="pending_review"&&<div className="mt-4 flex flex-wrap gap-2"><button onClick={()=>void review(app,"approve")} disabled={!!busy} className="rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{busy===app.id+"approve"?"Approving…":"Approve publisher application"}</button><button onClick={()=>void review(app,"reject")} disabled={!!busy} className="rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-bold text-rose-700 disabled:opacity-50">{busy===app.id+"reject"?"Rejecting…":"Reject application"}</button></div>}
        </article>)}
      </div>
    </section>
  </div></main>;
}

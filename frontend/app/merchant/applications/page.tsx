"use client";

import {useCallback,useEffect,useState} from "react";
import {apiFetch} from "@/lib/api";

type Application={
  id:string;merchant_offer_id:string;publisher_workspace_id:string;offer_name:string;applicant_email:string;
  publisher_website_url:string;audience_description:string;traffic_sources:string[];intended_regions:string[];
  promotion_plan:string;terms_snapshot:Record<string,unknown>;status:string;reviewer_notes:string|null;
  provider_submission_status:string;affiliate_network_approved:boolean;created_at:string|null;reviewed_at:string|null;
};
type StatusFilter="all"|"pending_review"|"approved"|"rejected";
type ApplicationQueue={count:number;total_count:number;limit:number;offset:number;status_filter:string;data:Application[]};
const PAGE_SIZE=25;
const fieldClass="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm";

export default function MerchantApplicationsPage(){
  const [queue,setQueue]=useState<ApplicationQueue|null>(null);
  const [statusFilter,setStatusFilter]=useState<StatusFilter>("all");
  const [notesByApplication,setNotesByApplication]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState("");
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");

  const fetchPage=async(filter:StatusFilter,offset:number)=>{
    const query=new URLSearchParams({limit:String(PAGE_SIZE),offset:String(offset)});
    if(filter!=="all")query.set("status",filter);
    return await apiFetch<ApplicationQueue>("/api/merchant/applications?"+query.toString());
  };
  const load=useCallback(async(nextStatus:StatusFilter="all",nextOffset=0)=>{
    setLoading(true);setError("");
    try{
      let result=await fetchPage(nextStatus,nextOffset);
      // A review may remove the final record from a filtered page. Clamp to the
      // last real page rather than displaying an empty page with no way back.
      if(nextOffset>0&&nextOffset>=result.total_count){
        const lastOffset=Math.max(0,Math.floor((result.total_count-1)/result.limit)*result.limit);
        if(lastOffset!==nextOffset)result=await fetchPage(nextStatus,lastOffset);
      }
      setQueue(result);
    }catch(e){setError(e instanceof Error?e.message:"Could not load incoming applications. Sign in as an owner/admin of the offer's merchant workspace.");}
    finally{setLoading(false);}
  },[]);
  useEffect(()=>{void load("all",0)},[load]);

  const review=async(application:Application,decision:"approve"|"reject")=>{
    setBusy(application.id+decision);setError("");setNotice("");
    try{
      const result=await apiFetch<Application>("/api/merchant/applications/"+encodeURIComponent(application.id)+"/review",{
        method:"POST",body:JSON.stringify({decision,reviewer_notes:notesByApplication[application.id]||""})
      });
      setNotice(result.offer_name+" application "+result.status+". This is an internal decision; external network approval remains unconfigured.");
      setNotesByApplication(previous=>({...previous,[application.id]:""}));
      await load(statusFilter,queue?.offset??0);
    }catch(e){setError(e instanceof Error?e.message:"Review failed.");}
    finally{setBusy("")}
  };
  const changeFilter=(value:StatusFilter)=>{
    setStatusFilter(value);setNotice("");void load(value,0);
  };
  const pageStart=queue&&queue.count>0?queue.offset+1:0;
  const pageEnd=queue?queue.offset+queue.count:0;
  const canGoPrevious=!!queue&&queue.offset>0&&!loading;
  const canGoNext=!!queue&&queue.offset+queue.count<queue.total_count&&queue.count>0&&!loading;

  return <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10">
    <div className="mx-auto max-w-6xl">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <a href="/merchant/offers" className="text-sm font-bold text-indigo-700">← Merchant offers</a>
          <p className="mt-6 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Merchant · Incoming applications</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Publisher applications</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">Review applications only for merchant offers owned by the active workspace. Decisions are internal to OmniAffiliateOS and do not submit an external network application or confirm network approval.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href="/merchant" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold">Merchant dashboard</a>
          <button onClick={()=>void load(statusFilter,queue?.offset??0)} disabled={!!busy||loading} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">{loading?"Refreshing…":"Refresh"}</button>
          <a href="/marketplace" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold">Publisher marketplace</a>
        </div>
      </header>
      {error&&<div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
      {notice&&<div role="status" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}

      <section className="mt-7 rounded-3xl border border-white bg-white p-5 shadow-sm sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-xl font-black">Applications received</h2><p className="mt-1 text-sm text-slate-500">{queue?queue.total_count+" application(s) match this filter":"Loading the merchant's application inbox…"}</p></div>
          <label className="block text-sm font-bold" htmlFor="merchant-application-status-filter">Filter applications by status
            <select id="merchant-application-status-filter" aria-label="Filter applications by status" value={statusFilter} onChange={e=>changeFilter(e.target.value as StatusFilter)} disabled={loading||!!busy} className="ml-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-normal">
              <option value="all">All statuses</option><option value="pending_review">Pending review</option><option value="approved">Approved</option><option value="rejected">Rejected</option>
            </select>
          </label>
        </div>
        {queue&&<div className="mt-4 flex flex-wrap items-center justify-between gap-2"><p role="status" aria-live="polite" className="text-sm text-slate-600">Showing {pageStart}–{pageEnd} of {queue.total_count} applications</p><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{queue.count} on this page</span></div>}
        <div className="mt-5 grid gap-4">
          {queue&&queue.data.length===0&&<p className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">No publisher applications match this filter.</p>}
          {queue?.data.map(app=><article key={app.id} data-testid="merchant-application-card" data-application-id={app.id} className="rounded-2xl border border-slate-200 p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><h3 className="font-black">{app.offer_name}</h3><p className="mt-1 text-sm text-slate-500">Publisher contact: {app.applicant_email}</p><p className="mt-1 break-all text-xs text-indigo-700"><a href={app.publisher_website_url} target="_blank" rel="noopener noreferrer">{app.publisher_website_url}</a></p></div>
              <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold">{app.status.replaceAll("_"," ")}</span>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Requested regions</p><p className="mt-1 text-sm font-bold">{app.intended_regions.join(", ")}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Traffic sources</p><p className="mt-1 text-sm font-bold">{app.traffic_sources.join(", ")}</p></div></div>
            <p className="mt-3 text-sm leading-6 text-slate-600">{app.audience_description}</p>
            <div className="mt-3 rounded-xl border border-slate-200 p-3"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Promotion plan</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{app.promotion_plan}</p></div>
            <p className="mt-3 text-xs leading-5 text-slate-500">Terms version snapshot: {String(app.terms_snapshot.terms_version||"unknown")} · External network submission: {app.provider_submission_status} · Affiliate network approved: no</p>
            {app.reviewer_notes&&<p className="mt-2 text-sm text-slate-600">Previous review note: {app.reviewer_notes}</p>}
            {app.status==="pending_review"&&<div className="mt-4 space-y-3">
              <label className="block text-sm font-bold" htmlFor={"merchant-review-note-"+app.id}>Review note for this application
                <textarea id={"merchant-review-note-"+app.id} data-testid="merchant-application-review-note" className={fieldClass} rows={2} value={notesByApplication[app.id]??""} onChange={e=>setNotesByApplication(previous=>({...previous,[app.id]:e.target.value}))} maxLength={3000} placeholder="Record this application's decision rationale or missing compliance evidence."/>
              </label>
              <div className="flex flex-wrap gap-2"><button onClick={()=>void review(app,"approve")} disabled={!!busy||loading} className="rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{busy===app.id+"approve"?"Approving…":"Approve publisher application"}</button><button onClick={()=>void review(app,"reject")} disabled={!!busy||loading} className="rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-bold text-rose-700 disabled:opacity-50">{busy===app.id+"reject"?"Rejecting…":"Reject application"}</button></div>
            </div>}
          </article>)}
        </div>
        {queue&&queue.total_count>queue.limit&&<nav aria-label="Merchant application pagination" className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm text-slate-600">Page {Math.floor(queue.offset/queue.limit)+1} of {Math.max(1,Math.ceil(queue.total_count/queue.limit))}</p>
          <div className="flex gap-2"><button type="button" onClick={()=>void load(statusFilter,Math.max(0,queue.offset-queue.limit))} disabled={!canGoPrevious} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold disabled:opacity-40">Previous page</button><button type="button" onClick={()=>void load(statusFilter,queue.offset+queue.limit)} disabled={!canGoNext} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold disabled:opacity-40">Next page</button></div>
        </nav>}
      </section>
    </div>
  </main>;
}

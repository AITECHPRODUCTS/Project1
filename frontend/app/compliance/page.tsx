"use client";

import {useCallback,useEffect,useMemo,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type Activity = "affiliate_promotion"|"content_publish"|"paid_media"|"email_marketing"|"lead_capture"|"tracking_analytics"|"merchant_marketplace";
type Category = "affiliate_disclosure"|"advertising_claims"|"privacy_data_protection"|"paid_media_rules"|"email_marketing"|"consent_and_marketing"|"cookie_tracking"|"data_retention"|"platform_terms"|"consumer_protection";
type Requirements = {activities:{id:Activity;label:string;required_categories:Category[]}[];evidence_max_age_days:Record<string,number>;review_validity_days:number;notice:string};
type RuleEvidence = {jurisdiction_code:string;category:Category;source_title:string;source_url:string;rule_summary:string;effective_date?:string|null;reviewed_at:string;reviewer_attestation:boolean};
type MissingEvidence = {jurisdiction_code:string;category:string;reason:string};
type Assessment = {id:string;activity:Activity;channels:string[];jurisdictions:string[];rule_evidence:RuleEvidence[];coverage_summary:{coverage_complete:boolean;missing_evidence:MissingEvidence[];covered_evidence_items:number;required_evidence_items:number};status:string;created_by:string;reviewed_by:string|null;reviewed_at:string|null;valid_until:string|null;reviewer_notes:string|null};
const inputClass="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm";
const labelClass="block text-sm font-bold text-slate-700";
const categoryLabels:Record<Category,string>={affiliate_disclosure:"Affiliate / commercial disclosure",advertising_claims:"Advertising claims and substantiation",privacy_data_protection:"Privacy and data protection",paid_media_rules:"Paid-media rules and targeting",email_marketing:"Email marketing rules",consent_and_marketing:"Consent and marketing permissions",cookie_tracking:"Cookies and tracking",data_retention:"Data retention and deletion",platform_terms:"Platform / publisher terms",consumer_protection:"Consumer protection"};
function localDateTimeInput():string{const local=new Date(Date.now()-new Date().getTimezoneOffset()*60000);return local.toISOString().slice(0,16);}
function errorMessage(error:unknown):string{return error instanceof Error?error.message:"Request failed";}
export default function CompliancePage(){
 const [requirements,setRequirements]=useState<Requirements|null>(null);
 const [assessments,setAssessments]=useState<Assessment[]>([]);
 const [activity,setActivity]=useState<Activity>("content_publish");
 const [channels,setChannels]=useState("wordpress, reddit");
 const [jurisdictions,setJurisdictions]=useState("US");
 const [operatorNotes,setOperatorNotes]=useState("");
 const [evidence,setEvidence]=useState<RuleEvidence[]>([]);
 const [evidenceJurisdiction,setEvidenceJurisdiction]=useState("US");
 const [evidenceCategory,setEvidenceCategory]=useState<Category>("affiliate_disclosure");
 const [sourceTitle,setSourceTitle]=useState("");
 const [sourceUrl,setSourceUrl]=useState("");
 const [ruleSummary,setRuleSummary]=useState("");
 const [effectiveDate,setEffectiveDate]=useState("");
 const [reviewedAt,setReviewedAt]=useState("");
 const [attested,setAttested]=useState(false);
 const [reviewNotes,setReviewNotes]=useState("");
 const [reviewConfirmations,setReviewConfirmations]=useState<Record<string,boolean>>({});
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const selectedActivity=useMemo(()=>requirements?.activities.find(item=>item.id===activity),[requirements,activity]);
 const load=useCallback(async()=>{
  setError("");
  try{
   const results=await Promise.all([
    apiFetch<Requirements>("/api/compliance/requirements"),
    apiFetch<{count:number;data:Assessment[]}>("/api/compliance/assessments")
   ]);
   setRequirements(results[0]);setAssessments(results[1].data||[]);
   const selected=results[0].activities.find(item=>item.id===activity);
   if(selected&&!selected.required_categories.includes(evidenceCategory))setEvidenceCategory(selected.required_categories[0]);
  }catch(e){setError(errorMessage(e));}
 },[activity,evidenceCategory]);
 useEffect(()=>{void load()},[load]);
 useEffect(()=>{if(!reviewedAt)setReviewedAt(localDateTimeInput())},[reviewedAt]);

 const addEvidence=(event:FormEvent)=>{
  event.preventDefault();setError("");setNotice("");
  if(!attested){setError("Confirm that you reviewed this source and its relevance before adding evidence.");return;}
  const code=evidenceJurisdiction.trim().toUpperCase();
  if(!code){setError("Enter a jurisdiction code for this source.");return;}
  setEvidence(current=>current.concat([{
   jurisdiction_code:code,category:evidenceCategory,source_title:sourceTitle.trim(),source_url:sourceUrl.trim(),
   rule_summary:ruleSummary.trim(),effective_date:effectiveDate||null,reviewed_at:new Date(reviewedAt).toISOString(),reviewer_attestation:true
  }]));
  setSourceTitle("");setSourceUrl("");setRuleSummary("");setEffectiveDate("");setAttested(false);
  setNotice("Evidence added to the draft; it is not approved yet.");
 };
 const createAssessment=async()=>{
  setBusy(true);setError("");setNotice("");
  try{
   const result=await apiFetch<Assessment>("/api/compliance/assessments",{
    method:"POST",body:JSON.stringify({
     activity,channels:channels.split(",").map(x=>x.trim().toLowerCase()).filter(Boolean),
     jurisdictions:jurisdictions.split(",").map(x=>x.trim().toUpperCase()).filter(Boolean),
     rule_evidence:evidence,operator_notes:operatorNotes
    })
   });
   setNotice("Assessment saved with status "+result.status+". Complete the coverage gaps and review it before live use.");
   setEvidence([]);setOperatorNotes("");await load();
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };
 const reviewAssessment=async(id:string,decision:"approve"|"reject")=>{
  if(decision==="approve"&&reviewConfirmations[id]!==true){setError("Confirm that you personally reviewed the listed source evidence and every target jurisdiction before approving.");return;}
  setBusy(true);setError("");setNotice("");
  try{
   const result=await apiFetch<Assessment>("/api/compliance/assessments/"+encodeURIComponent(id)+"/review",{
    method:"POST",body:JSON.stringify({decision,confirm_scope_reviewed:decision==="approve"&&reviewConfirmations[id]===true,reviewer_notes:reviewNotes})
   });
   setNotice("Review recorded: "+result.status+". Matching scope is still required for live publishing.");
   setReviewNotes("");setReviewConfirmations(current=>({...current,[id]:false}));await load();
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };
 return <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10">
  <div className="mx-auto max-w-7xl">
   <header className="flex flex-wrap items-start justify-between gap-3">
    <div><a href="/" className="text-sm font-bold text-indigo-700">← Growth command center</a><p className="mt-6 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Governance · Evidence registry</p><h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Jurisdiction compliance</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">Record target jurisdictions, cited rules and human review for each external channel. This is an evidence workflow, not an automatically generated law database or a legal opinion.</p></div>
    <div className="flex gap-2"><a href="/marketplace" className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-bold">Marketplace</a><button onClick={()=>void load()} disabled={busy} className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-bold disabled:opacity-50">Refresh</button></div>
   </header>
   {error&&<div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
   {notice&&<div role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
   <section className="mt-7 rounded-2xl border border-amber-200 bg-amber-50/70 p-4 text-sm leading-6 text-amber-950"><strong>Live-action policy:</strong> drafts and dry-runs stay available. Actual social/CMS publishing requires current approved evidence covering each target jurisdiction, required category and channel. A reviewer must check the underlying sources; the software does not certify legal compliance.</section>
   <section className="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,.9fr)]">
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
     <h2 className="text-xl font-black">Create assessment</h2><p className="mt-1 text-sm text-slate-500">Saving creates a draft or a review-ready record. Only the separate approval step grants live-action clearance for its exact scope.</p>
     <div className="mt-5 grid gap-4 sm:grid-cols-2">
      <div><label className={labelClass}>Activity</label><select className={inputClass} value={activity} onChange={e=>setActivity(e.target.value as Activity)}>{(requirements?.activities||[]).map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></div>
      <div><label className={labelClass}>Channels</label><input className={inputClass} value={channels} onChange={e=>setChannels(e.target.value)} placeholder="wordpress, reddit" required/><p className="mt-1 text-xs text-slate-500">Must match the external provider/channel.</p></div>
      <div className="sm:col-span-2"><label className={labelClass}>Target jurisdictions</label><input className={inputClass} value={jurisdictions} onChange={e=>setJurisdictions(e.target.value)} placeholder="US, GB, IN, EU" required/><p className="mt-1 text-xs text-slate-500">Comma-separated codes; include applicable country and supranational jurisdictions separately.</p></div>
     </div>
     <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4"><h3 className="font-black">Required rule categories</h3><p className="mt-1 text-xs leading-5 text-slate-500">Evidence is matched to each jurisdiction separately. A generic global source does not stand in for country-specific rules.</p><div className="mt-3 flex flex-wrap gap-2">{(selectedActivity?.required_categories||[]).map(cat=><span key={cat} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold">{categoryLabels[cat]}</span>)}</div></div>
     <div className="mt-6 border-t border-slate-100 pt-5"><h3 className="font-black">Add cited source</h3>
      <form onSubmit={addEvidence} className="mt-3 grid gap-3 sm:grid-cols-2">
       <div><label className={labelClass}>Jurisdiction code</label><input className={inputClass} value={evidenceJurisdiction} onChange={e=>setEvidenceJurisdiction(e.target.value)} required/></div>
       <div><label className={labelClass}>Rule category</label><select className={inputClass} value={evidenceCategory} onChange={e=>setEvidenceCategory(e.target.value as Category)}>{(selectedActivity?.required_categories||[]).map(cat=><option key={cat} value={cat}>{categoryLabels[cat]}</option>)}</select></div>
       <div className="sm:col-span-2"><label className={labelClass}>Source title / authority</label><input className={inputClass} value={sourceTitle} onChange={e=>setSourceTitle(e.target.value)} minLength={3} maxLength={240} required/></div>
       <div className="sm:col-span-2"><label className={labelClass}>Official source URL (HTTPS)</label><input type="url" className={inputClass} value={sourceUrl} onChange={e=>setSourceUrl(e.target.value)} required/></div>
       <div className="sm:col-span-2"><label className={labelClass}>Rule summary and scope notes</label><textarea className={inputClass} rows={3} minLength={20} maxLength={3000} value={ruleSummary} onChange={e=>setRuleSummary(e.target.value)} required/></div>
       <div><label className={labelClass}>Effective date (optional)</label><input type="date" className={inputClass} value={effectiveDate} onChange={e=>setEffectiveDate(e.target.value)}/></div>
       <div><label className={labelClass}>Source reviewed at</label><input type="datetime-local" className={inputClass} value={reviewedAt} onChange={e=>setReviewedAt(e.target.value)} required/></div>
       <label className="sm:col-span-2 flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 text-sm"><input type="checkbox" checked={attested} onChange={e=>setAttested(e.target.checked)} className="mt-1"/><span>I checked the current source and its applicability to the stated jurisdiction and activity.</span></label>
       <button type="submit" className="sm:col-span-2 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-bold">Add evidence to draft</button>
      </form>
      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3"><div className="flex items-center justify-between"><h4 className="font-bold">Draft evidence</h4><span className="text-xs text-slate-500">{evidence.length} item(s)</span></div>{evidence.length===0?<p className="mt-2 text-xs text-slate-500">Add current source evidence for each required category and every target jurisdiction.</p>:<div className="mt-3 space-y-2">{evidence.map((item,index)=><div key={item.jurisdiction_code+":"+item.category+":"+index} className="flex items-start justify-between gap-3 rounded-lg bg-slate-50 p-3"><div className="min-w-0"><p className="text-xs font-bold">{item.jurisdiction_code} · {categoryLabels[item.category]}</p><p className="mt-1 break-words text-xs text-slate-500">{item.source_title}</p><p className="mt-1 break-all text-xs text-indigo-700">{item.source_url}</p></div><button type="button" onClick={()=>setEvidence(rows=>rows.filter((_,i)=>i!==index))} className="text-xs font-bold text-rose-700">Remove</button></div>)}</div>}</div>
     </div>
     <div className="mt-5"><label className={labelClass}>Operator notes (optional)</label><textarea className={inputClass} rows={2} value={operatorNotes} onChange={e=>setOperatorNotes(e.target.value)} maxLength={3000}/></div>
     <button disabled={busy} type="button" onClick={()=>void createAssessment()} className="mt-5 w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white disabled:opacity-50">{busy?"Saving…":"Save assessment draft"}</button>
    </div>
    <div className="space-y-5">
     <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"><div className="flex items-center justify-between gap-3"><div><h2 className="text-xl font-black">Assessment register</h2><p className="mt-1 text-sm text-slate-500">Workspace-scoped decisions and expiry.</p></div><span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold">{assessments.length}</span></div>
      <div className="mt-4 space-y-4">{assessments.length===0&&<p className="rounded-xl border border-dashed border-slate-200 p-5 text-sm text-slate-500">No assessments yet. Draft content remains available; live publishing requires approved coverage.</p>}
       {assessments.map(row=><article key={row.id} className="rounded-2xl border border-slate-200 p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-black">{requirements?.activities.find(a=>a.id===row.activity)?.label||row.activity}</h3><p className="mt-1 text-xs text-slate-500">{row.channels.join(", ")} · {row.jurisdictions.join(", ")}</p></div><span className={"rounded-full px-3 py-1.5 text-xs font-bold "+(row.status==="approved"?"bg-emerald-100 text-emerald-800":row.status==="rejected"||row.status==="expired"?"bg-rose-100 text-rose-800":"bg-amber-100 text-amber-900")}>{row.status.replaceAll("_"," ")}</span></div>
        <div className="mt-3 rounded-xl bg-slate-50 p-3"><p className="text-xs font-bold">Coverage: {row.coverage_summary.covered_evidence_items||0}/{row.coverage_summary.required_evidence_items||0}</p>{row.coverage_summary.missing_evidence?.length>0&&<p className="mt-1 text-xs leading-5 text-amber-800">Missing/stale: {row.coverage_summary.missing_evidence.slice(0,6).map(x=>x.jurisdiction_code+" "+(categoryLabels[x.category as Category]||x.category)).join("; ")}{row.coverage_summary.missing_evidence.length>6?" +"+(row.coverage_summary.missing_evidence.length-6)+" more":""}</p>}</div>
        {row.valid_until&&<p className="mt-2 text-xs text-slate-500">Valid until {new Date(row.valid_until).toLocaleDateString()} · Reviewer {row.reviewed_by}</p>}
        {row.status==="review_required"&&<div className="mt-3"><label className={labelClass}>Reviewer notes</label><input className={inputClass} value={reviewNotes} onChange={e=>setReviewNotes(e.target.value)} placeholder="Record scope/source review notes"/><label className="mt-3 flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-5"><input type="checkbox" checked={reviewConfirmations[row.id]===true} onChange={e=>setReviewConfirmations(current=>({...current,[row.id]:e.target.checked}))} className="mt-1"/><span>I have independently reviewed the cited sources, their current status, and applicability to every target jurisdiction and channel shown above.</span></label><div className="mt-2 flex gap-2"><button disabled={busy||reviewConfirmations[row.id]!==true} onClick={()=>void reviewAssessment(row.id,"approve")} className="rounded-xl bg-emerald-700 px-3 py-2.5 text-xs font-bold text-white disabled:opacity-50">Approve reviewed evidence</button><button disabled={busy} onClick={()=>void reviewAssessment(row.id,"reject")} className="rounded-xl border border-rose-200 bg-white px-3 py-2.5 text-xs font-bold text-rose-700 disabled:opacity-50">Reject</button></div></div>}
       </article>)}
      </div>
     </section>
     {requirements&&<section className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs leading-5 text-slate-600"><p className="font-bold">Freshness policy</p><p>Evidence age: {requirements.evidence_max_age_days[activity]} days for {activity.replaceAll("_"," ")}; approved reviews expire after {requirements.review_validity_days} days.</p><p className="mt-2">{requirements.notice}</p></section>}
    </div>
   </section>
  </div>
 </main>;
}

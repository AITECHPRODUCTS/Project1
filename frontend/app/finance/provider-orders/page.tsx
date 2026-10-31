"use client";

import {useCallback,useEffect,useState} from "react";
import {apiFetch} from "@/lib/api";

type Candidate={
 ledger_entry_id:string;network:string;external_event_id:string;
 commission_amount:string;currency:string;status:string;evidence_status:string;
};
type ProviderOrder={
 observation_id:string;provider_id:string;account_nickname:string;receipt:string;
 transaction_time:string;transaction_type:string;product_title:string|null;line_item_status:string|null;
 account_amount:string|null;currency:string|null;click_id:string|null;attribution_status:string;
 evidence_status:string;observed_at:string|null;review_status:string;reviewed_by:string|null;
 reviewed_at:string|null;review_note:string|null;candidate_count:number;candidates:Candidate[];
 match_block_reason:string|null;
};
type Queue={
 count:number;limit:number;read_only:boolean;commission_ledger_mutated:boolean;payout_confirmed:boolean;
 counts:Record<string,number>;data:ProviderOrder[];policy:string;
};
type Auth={user?:{is_admin?:boolean;workspace_role?:string}};
type ReviewDecision="matched_to_conversion"|"not_a_match"|"rejected_as_unreliable";

const button="rounded-lg px-3 py-2 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-40";
const label=(value:string)=>value.replaceAll("_"," ");

export default function ProviderOrderReconciliationPage(){
 const [queue,setQueue]=useState<Queue|null>(null);
 const [selected,setSelected]=useState<Record<string,string>>({});
 const [canReview,setCanReview]=useState(false);
 const [loading,setLoading]=useState(true);
 const [busy,setBusy]=useState("");
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");

 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{
   const [auth,result]=await Promise.all([
    apiFetch<Auth>("/api/auth/me"),
    apiFetch<Queue>("/api/finance/provider-orders/reconciliation?limit=100")
   ]);
   setCanReview(auth.user?.is_admin===true||["owner","admin"].includes(auth.user?.workspace_role||""));
   setQueue(result);
   setSelected(current=>{
    const next={...current};
    for(const row of result.data){
     if(!next[row.observation_id]&&row.candidates.length)next[row.observation_id]=row.candidates[0].ledger_entry_id;
    }
    return next;
   });
  }catch(exc){setError(exc instanceof Error?exc.message:"Could not load ClickBank provider order evidence.");}
  finally{setLoading(false);}
 },[]);
 useEffect(()=>{void load();},[load]);

 const review=async(row:ProviderOrder,decision:ReviewDecision)=>{
  const candidate=decision==="matched_to_conversion"?(selected[row.observation_id]||row.candidates[0]?.ledger_entry_id):undefined;
  if(decision==="matched_to_conversion"&&!candidate){
   setError("Select an exact signed conversion-ledger candidate before accepting a match.");
   return;
  }
  setBusy(row.observation_id);setError("");setNotice("");
  try{
   const result=await apiFetch<{decision:string;payout_confirmed:boolean;commission_ledger_mutated:boolean}>(
    "/api/finance/provider-orders/"+encodeURIComponent(row.observation_id)+"/review",
    {method:"PATCH",body:JSON.stringify({
     decision,
     ...(candidate?{candidate_ledger_entry_id:candidate}:{}),
     note:"Reviewed in the ClickBank provider-order queue"
    })}
   );
   setNotice("Review saved: "+label(result.decision)+". Commission ledger unchanged; payout remains unconfirmed.");
   await load();
  }catch(exc){setError(exc instanceof Error?exc.message:"Provider order review could not be saved.");}
  finally{setBusy("");}
 };

 return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:px-8">
  <div className="mx-auto max-w-6xl">
   <header className="flex flex-wrap items-center justify-between gap-4">
    <div>
     <p className="text-xs font-black uppercase tracking-[.18em] text-indigo-600">Commission earner · Finance evidence</p>
     <h1 className="mt-2 text-3xl font-black tracking-tight">ClickBank order evidence reconciliation</h1>
     <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Review imported provider observations against existing, signed conversion-ledger entries. A candidate is never accepted automatically.</p>
    </div>
    <a href="/" className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold">Back to growth cockpit</a>
   </header>

   <section className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
    <p className="font-black">Review-only financial boundary</p>
    <p>Exact matching requires the same workspace, ClickBank TID click ID, provider, currency and six-decimal amount, plus a signed-webhook-verified conversion ledger entry. Accepting a match records an immutable review decision only. It does not create or alter commissions, confirm a payout or transfer funds.</p>
   </section>

   {error&&<div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
   {notice&&<div role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}

   {queue&&<div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
    {Object.entries(queue.counts).map(([state,count])=><div key={state} className="rounded-2xl border border-slate-200 bg-white p-4">
     <p className="text-xs font-bold capitalize text-slate-500">{label(state)}</p><p className="mt-1 text-2xl font-black tabular-nums">{count}</p>
    </div>)}
   </div>}

   <section className="mt-7">
    <div className="flex flex-wrap items-center justify-between gap-3">
     <div><h2 className="text-xl font-black">Provider observations</h2><p className="mt-1 text-sm text-slate-600">{queue?.count??0} rows · Read-only source evidence</p></div>
     <button type="button" onClick={()=>void load()} disabled={loading||busy!==""} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold disabled:opacity-50">Refresh</button>
    </div>
    {loading?<p role="status" className="mt-5 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Loading provider orders…</p>
    :!queue||queue.data.length===0?<p className="mt-5 rounded-xl border border-dashed border-slate-300 bg-white p-7 text-center text-sm text-slate-500">No ClickBank order observations have been imported for this workspace.</p>
    :<div className="mt-5 space-y-4">
     {queue.data.map(row=><article key={row.observation_id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" data-testid={"provider-order-"+row.observation_id}>
      <div className="flex flex-wrap items-start justify-between gap-3">
       <div><h3 className="font-black">{row.product_title||"Provider order"} <span className="text-xs font-semibold text-slate-400">· {row.transaction_type}</span></h3>
        <p className="mt-1 text-xs text-slate-500">{row.provider_id} · {row.account_nickname} · receipt {row.receipt} · {row.transaction_time}</p>
       </div>
       <span className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs font-bold capitalize">{label(row.review_status)}</span>
      </div>
      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
       <div><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Provider account amount</p><p className="mt-1 font-mono font-bold">{row.currency||"Unknown"} {row.account_amount??"Unknown"}</p></div>
       <div><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Local click attribution</p><p className="mt-1 font-mono text-xs">{row.click_id?row.click_id.slice(0,12)+"…":"No local click match"}</p><p className="text-xs text-slate-500">{label(row.attribution_status)}</p></div>
       <div><p className="text-xs font-bold uppercase tracking-wide text-slate-400">Evidence status</p><p className="mt-1 text-xs">{label(row.evidence_status)}</p><p className="text-xs text-slate-500">{row.line_item_status||"Provider status unknown"}</p></div>
      </div>
      {row.review_status==="not_reviewed"&&row.candidate_count>0&&<div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/50 p-3">
       <p className="text-xs font-black uppercase tracking-wide text-indigo-800">Exact signed-ledger candidates · {row.candidate_count}</p>
       <label className="mt-2 block text-xs font-bold text-slate-700">Select conversion-ledger entry
        <select aria-label={"Ledger candidate for "+row.receipt} value={selected[row.observation_id]||row.candidates[0].ledger_entry_id} onChange={e=>setSelected(current=>({...current,[row.observation_id]:e.target.value}))} className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
         {row.candidates.map(candidate=><option key={candidate.ledger_entry_id} value={candidate.ledger_entry_id}>{candidate.network} · {candidate.currency} {candidate.commission_amount} · {candidate.external_event_id} · signed webhook</option>)}
        </select>
       </label>
      </div>}
      {row.match_block_reason&&row.review_status==="not_reviewed"&&<p className="mt-3 text-xs text-amber-700">No exact match offered: {label(row.match_block_reason)}.</p>}
      {row.review_status!=="not_reviewed"&&<p className="mt-3 text-xs text-slate-500">Reviewed by {row.reviewed_by||"workspace operator"} · {row.reviewed_at||"timestamp unavailable"} · {row.review_note||"No note"}</p>}
      {canReview&&row.review_status==="not_reviewed"&&<div className="mt-4 flex flex-wrap items-center gap-2">
       {row.candidate_count>0&&<button type="button" onClick={()=>void review(row,"matched_to_conversion")} disabled={busy!==""} className={button+" bg-indigo-600 text-white"}>{busy===row.observation_id?"Saving…":"Accept exact ledger match"}</button>}
       <button type="button" onClick={()=>void review(row,"not_a_match")} disabled={busy!==""} className={button+" border border-slate-200 bg-white text-slate-700"}>Mark not a match</button>
       <button type="button" onClick={()=>void review(row,"rejected_as_unreliable")} disabled={busy!==""} className={button+" border border-rose-200 bg-rose-50 text-rose-700"}>Reject unreliable evidence</button>
      </div>}
     </article>)}
    </div>}
   </section>
   <p className="mt-7 text-xs leading-5 text-slate-500">{queue?.policy||"Provider-reported amounts remain unreconciled until exact evidence and human review are both present."} Payout confirmed: no.</p>
  </div>
 </main>;
}

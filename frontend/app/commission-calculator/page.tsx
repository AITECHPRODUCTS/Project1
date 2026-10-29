"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type RewardType="cps_one_time"|"cps_recurring"|"cpl"|"cpa";
type CommissionType="percentage"|"fixed";
type ProgramInput={
  id:number;name:string;reward_type:RewardType;commission_type:CommissionType;
  commission_value:string;currency:string;average_order_value:string;recurring_paid_months:string;
};
type ProjectedProgram={
  name:string;reward_type:RewardType;currency:string;commission_per_conversion_amount:string;
  expected_monthly_clicks:string;expected_monthly_conversions:string;
  estimated_first_month_commission:string;estimated_12_month_commission:string;
  recurring_paid_months:number|null;projection_basis:string;
};
type CommissionResult={
  asset_id:string;asset_status:string;requires_review:boolean;publishing_started:boolean;
  programs:ProjectedProgram[];
  measurement_basis:{monthly_visitors:number;click_through_rate_pct_assumption:string;affiliate_conversion_rate_pct_assumption:string};
  currency_comparison:string;input_provenance:string;provider_metrics_verified:boolean;
  earnings_guaranteed:boolean;external_provider_calls_made:boolean;money_transferred:boolean;
  requires_human_review:boolean;notes:string[];
};
type SavedProjection={
  asset_id:string;title:string;asset_status:string;created_at:string|null;requires_review:boolean;
  publishing_started:boolean;assumptions:Record<string,unknown>;result:CommissionResult|null;
};
type ProjectionHistoryResponse={count:number;limit:number;offset:number;items:SavedProjection[]};
const inputClass="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm";
const labelClass="block text-sm font-semibold text-slate-700";
function message(error:unknown){return error instanceof Error?error.message:"Commission calculation failed";}
function freshProgram(id:number,currency="USD"):ProgramInput{
 return {id,name:"Program "+id,reward_type:"cps_one_time",commission_type:"percentage",commission_value:"20",currency,average_order_value:"50",recurring_paid_months:"12"};
}
export default function CommissionCalculatorPage(){
 const [visitors,setVisitors]=useState("1000");
 const [ctr,setCtr]=useState("10");
 const [conversionRate,setConversionRate]=useState("5");
 const [programs,setPrograms]=useState<ProgramInput[]>([freshProgram(1)]);
 const [nextId,setNextId]=useState(2);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [result,setResult]=useState<CommissionResult|null>(null);
 const [history,setHistory]=useState<SavedProjection[]>([]);
 const [historyCount,setHistoryCount]=useState(0);
 const [historyBusy,setHistoryBusy]=useState(false);
 const [historyError,setHistoryError]=useState("");
 const loadHistory=useCallback(async()=>{
  setHistoryBusy(true);
  try{
   const response=await apiFetch<ProjectionHistoryResponse>("/api/research/commission-projections?limit=20");
   setHistory(response.items);
   setHistoryCount(response.count);
   setHistoryError("");
  }catch(err){setHistoryError(message(err));}
  finally{setHistoryBusy(false);}
 },[]);
 useEffect(()=>{void loadHistory();},[loadHistory]);
 const updateProgram=(id:number,patch:Partial<ProgramInput>)=>setPrograms(current=>current.map(p=>p.id===id?{...p,...patch}:p));
 const addProgram=()=>{if(programs.length>=10)return;setPrograms(current=>[...current,freshProgram(nextId,current[0]?.currency||"USD")]);setNextId(value=>value+1);};
 const removeProgram=(id:number)=>setPrograms(current=>current.length>1?current.filter(p=>p.id!==id):current);
 const submit=async(event:FormEvent)=>{
  event.preventDefault();setBusy(true);setError("");setNotice("");setResult(null);
  try{
   const payload={
    monthly_visitors:Number(visitors),
    click_through_rate_pct:Number(ctr),
    affiliate_conversion_rate_pct:Number(conversionRate),
    programs:programs.map(p=>({
      name:p.name.trim(),reward_type:p.reward_type,commission_type:p.commission_type,
      commission_value:Number(p.commission_value),currency:p.currency.trim().toUpperCase(),
      ...(p.commission_type==="percentage"?{average_order_value:Number(p.average_order_value)}:{}),
      ...(p.reward_type==="cps_recurring"?{recurring_paid_months:Number(p.recurring_paid_months)}:{}),
    })),
   };
   const response=await apiFetch<CommissionResult>("/api/research/commission-calculator",{method:"POST",body:JSON.stringify(payload)});
   setResult(response);
   setNotice("Projection saved as a workspace draft. Review payout terms and assumptions before making decisions.");
   await loadHistory();
  }catch(err){setError(message(err));}
  finally{setBusy(false);}
 };
 return <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10"><div className="mx-auto max-w-7xl">
  <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
   <div><a href="/" className="text-sm font-semibold text-indigo-600 hover:underline">← Growth command</a><h1 className="mt-2 text-3xl font-black tracking-tight">Commission projection calculator</h1><p className="mt-1 max-w-3xl text-sm text-slate-600">Compare affiliate payout structures using your own traffic and conversion assumptions. Results are saved to your active workspace for review.</p></div>
   <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-bold text-amber-900">Assumptions only · No payout</span>
  </header>
  <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><strong>Evidence boundary:</strong> this calculator does not fetch provider metrics or verify network terms. Traffic, click-through rate and conversion rate are assumptions you enter. Recurring projections assume no churn/refunds and cannot guarantee earnings or confirm a payout.</div>
  {error&&<div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
  {notice&&<div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}
  <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(320px,.8fr)_minmax(0,1.2fr)]">
   <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <h2 className="text-xl font-bold">Traffic assumptions</h2>
    <form onSubmit={submit} className="mt-4 space-y-4">
     <label className={labelClass}>Monthly visitors<input aria-label="Monthly visitors" className={inputClass} type="number" min="0" max="1000000000" step="1" required value={visitors} onChange={e=>setVisitors(e.target.value)}/></label>
     <div className="grid grid-cols-1 gap-3 sm:grid-cols-2"><label className={labelClass}>Click-through rate (%)<input aria-label="Click-through rate (%)" className={inputClass} type="number" min="0" max="100" step="any" required value={ctr} onChange={e=>setCtr(e.target.value)}/></label><label className={labelClass}>Affiliate conversion rate (%)<input aria-label="Affiliate conversion rate (%)" className={inputClass} type="number" min="0" max="100" step="any" required value={conversionRate} onChange={e=>setConversionRate(e.target.value)}/></label></div>
     <div className="border-t border-slate-100 pt-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-bold">Programs to compare</h2><button type="button" onClick={addProgram} disabled={programs.length>=10||busy} className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 disabled:opacity-50">Add program ({programs.length}/10)</button></div>
      <div className="mt-4 space-y-4">{programs.map((program,index)=><article key={program.id} className="rounded-xl border border-slate-200 p-4">
       <div className="flex items-center justify-between gap-2"><h3 className="font-bold">Program {index+1}</h3><button type="button" aria-label={"Remove program "+(index+1)} disabled={programs.length===1||busy} onClick={()=>removeProgram(program.id)} className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-600 disabled:opacity-40">Remove</button></div>
       <label className={labelClass}>Program {index+1} name<input className={inputClass} minLength={1} maxLength={120} required value={program.name} onChange={e=>updateProgram(program.id,{name:e.target.value})}/></label>
       <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className={labelClass}>Reward type<select className={inputClass} value={program.reward_type} onChange={e=>{const reward=e.target.value as RewardType;updateProgram(program.id,{reward_type:reward,commission_type:(reward==="cpl"||reward==="cpa")?"fixed":program.commission_type});}}><option value="cps_one_time">One-time sale (CPS)</option><option value="cps_recurring">Recurring sale (CPS)</option><option value="cpl">Lead (CPL)</option><option value="cpa">Action (CPA)</option></select></label>
        <label className={labelClass}>Commission type<select className={inputClass} value={program.commission_type} onChange={e=>updateProgram(program.id,{commission_type:e.target.value as CommissionType})}><option value="percentage">Percentage</option><option value="fixed">Fixed amount</option></select></label>
        <label className={labelClass}>Commission value<input className={inputClass} type="number" min="0.000001" max={program.commission_type==="percentage"?"100":"1000000000"} step="any" required value={program.commission_value} onChange={e=>updateProgram(program.id,{commission_value:e.target.value})}/></label>
        <label className={labelClass}>Currency (ISO code)<input className={inputClass} minLength={3} maxLength={3} pattern="[A-Za-z]{3}" required value={program.currency} onChange={e=>updateProgram(program.id,{currency:e.target.value.toUpperCase()})}/></label>
        {program.commission_type==="percentage"&&<label className={labelClass}>Average order value<input className={inputClass} type="number" min="0.000001" max="1000000000" step="any" required value={program.average_order_value} onChange={e=>updateProgram(program.id,{average_order_value:e.target.value})}/></label>}
        {program.reward_type==="cps_recurring"&&<label className={labelClass}>Paid months per conversion cohort<input className={inputClass} type="number" min="1" max="120" step="1" required value={program.recurring_paid_months} onChange={e=>updateProgram(program.id,{recurring_paid_months:e.target.value})}/></label>}
       </div>
      </article>)}</div>
      <p className="mt-3 text-xs leading-5 text-slate-500">Programs must use one common currency for ranking. Percentage commissions require an average order value; recurring CPS requires an explicit paid-duration assumption.</p>
     </div>
     <button type="submit" disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white disabled:opacity-50">{busy?"Calculating and saving…":"Estimate commissions"}</button>
    </form>
   </section>
   <section className="space-y-5">
    {!result&&<div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center"><h2 className="text-lg font-bold">Your projection will appear here</h2><p className="mt-2 text-sm leading-6 text-slate-500">Enter one or more programs to estimate expected commission, compare common-currency scenarios and save a workspace draft.</p></div>}
    {result&&<div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
     <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-bold">Estimated commission by program</h2><p className="mt-1 break-all font-mono text-xs text-slate-500">Saved draft · {result.asset_id}</p></div><a href={"data:application/json;charset=utf-8,"+encodeURIComponent(JSON.stringify(result,null,2))} download="commission-projection.json" className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-bold text-white">Export JSON</a></div>
     <div className="mt-4 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Monthly visitors</p><p className="mt-1 text-xl font-black">{result.measurement_basis.monthly_visitors.toLocaleString()}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">CTR assumption</p><p className="mt-1 text-xl font-black">{result.measurement_basis.click_through_rate_pct_assumption}%</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">CVR assumption</p><p className="mt-1 text-xl font-black">{result.measurement_basis.affiliate_conversion_rate_pct_assumption}%</p></div></div>
     <p className="mt-3 text-xs leading-5 text-slate-500">Ranking is limited to {result.currency_comparison}. The input origin is {result.input_provenance.replaceAll("_"," ")}.</p>
     <div className="mt-4 space-y-3">{result.programs.map((program,index)=><article key={program.name+index} className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-indigo-600">Rank #{index+1} · {program.reward_type.replaceAll("_"," ")}</p><h3 className="mt-1 text-lg font-bold">{program.name}</h3><p className="mt-1 text-xs text-slate-500">{program.projection_basis}</p></div><span className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs font-bold text-amber-800">Assumption-based</span></div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Estimated first-month commission</p><p className="mt-1 text-lg font-black">{program.currency} {program.estimated_first_month_commission}</p></div><div className="rounded-xl bg-indigo-50 p-3"><p className="text-xs text-indigo-700">Estimated 12-month commission</p><p className="mt-1 text-lg font-black text-indigo-900">{program.currency} {program.estimated_12_month_commission}</p></div></div>
      <p className="mt-3 text-xs text-slate-500">Expected monthly clicks: {program.expected_monthly_clicks} · expected conversions: {program.expected_monthly_conversions} · commission per conversion: {program.currency} {program.commission_per_conversion_amount}</p>
     </article>)}</div>
     <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4"><p className="font-bold text-amber-950">Review required · Not actual earnings</p><ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-amber-950">{result.notes.map(note=><li key={note}>{note}</li>)}</ul><p className="mt-3 text-xs font-bold text-amber-950">Provider metrics verified: {String(result.provider_metrics_verified)} · Earnings guaranteed: {String(result.earnings_guaranteed)} · Money transferred: {String(result.money_transferred)}</p></div>
    </div>}
   </section>
  </div>

  <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
   <div className="flex flex-wrap items-center justify-between gap-3">
    <div><h2 className="text-xl font-bold">Saved commission projections</h2><p className="mt-1 text-sm text-slate-500">Workspace-only review drafts · {historyCount} saved</p></div>
    <button type="button" onClick={()=>void loadHistory()} disabled={historyBusy} className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 disabled:opacity-50">{historyBusy?"Refreshing…":"Refresh history"}</button>
   </div>
   {historyError&&<p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">Unable to load saved projections: {historyError}</p>}
   {history.length===0&&!historyBusy?<p role="status" className="mt-4 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">No saved commission projections in this workspace yet.</p>:null}
   <div className="mt-4 grid gap-3 md:grid-cols-2">
    {history.map(item=><article key={item.asset_id} className="rounded-xl border border-slate-200 p-4">
     <div className="flex items-start justify-between gap-3"><div><h3 className="font-bold">{item.title}</h3><p className="mt-1 break-all font-mono text-[10px] text-slate-400">{item.asset_id}</p><p className="mt-1 text-xs text-slate-500">{item.created_at?new Date(item.created_at).toLocaleString():"Creation time unavailable"} · {item.asset_status}</p></div><span className="shrink-0 rounded-lg bg-amber-50 px-2 py-1 text-[10px] font-bold text-amber-800">Review required</span></div>
     {item.result&&<p className="mt-3 text-sm text-slate-600">{item.result.programs.length} program(s) · {item.result.currency_comparison} · estimates only</p>}
     <button type="button" onClick={()=>{if(item.result){setResult(item.result);setNotice("Loaded saved projection. It remains a draft requiring review.");setError("");}}} disabled={!item.result} className="mt-3 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-40">View saved results</button>
     {!item.result&&<p className="mt-2 text-xs text-rose-700">This historical record could not be parsed as a projection result.</p>}
    </article>)}
   </div>
   {historyCount>history.length&&<p className="mt-3 text-xs text-slate-500">Showing the latest {history.length} of {historyCount}; use refresh after a new calculation.</p>}
  </section>
 </div></main>;
}

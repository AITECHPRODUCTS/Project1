"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {apiFetch} from "@/lib/api";

type PayoutReadinessItem={
  program_id:string;
  program_name:string;
  publisher_workspace_id:string;
  publisher_email:string;
  application_id:string;
  application_status:string;
  promotion_link_status:string;
  currency:string;
  gross_commission:string;
  reversed_commission:string;
  net_commission:string;
  held_commission:string;
  eligible_commission:string;
  minimum_payout_amount:string;
  threshold_reached:boolean;
  refund_hold_days:number;
  next_eligible_at:string|null;
  payout_schedule:string;
  conversion_count:number;
  reversal_event_count:number;
  held_event_count:number;
  matured_event_count:number;
  payout_state:"eligible_for_manual_review"|"refund_hold"|"below_minimum"|"needs_review"|"no_earnings"|string;
  payout_confirmed:boolean;
  transfers_initiated:boolean;
};
type PayoutReadinessResponse={
  count:number;
  data:PayoutReadinessItem[];
  as_of:string;
  note:string;
  money_transferred:boolean;
};

const money=(amount:string,currency:string)=>new Intl.NumberFormat(undefined,{style:"currency",currency,maximumFractionDigits:2}).format(Number(amount||0));
const label=(value:string)=>value.replaceAll("_"," ");
const stateClass=(state:string)=>{
  if(state==="eligible_for_manual_review")return "bg-emerald-50 text-emerald-800";
  if(state==="needs_review")return "bg-rose-50 text-rose-800";
  if(state==="refund_hold")return "bg-amber-50 text-amber-900";
  return "bg-slate-100 text-slate-700";
};

export default function MerchantPayoutsPage(){
  const [report,setReport]=useState<PayoutReadinessResponse|null>(null);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");

  const load=useCallback(async()=>{
    setLoading(true);setError("");
    try{
      const identity=await apiFetch<{user?:{account_type?:string}}>("/api/auth/me");
      if(identity.user?.account_type!=="merchant_product_owner"){
        window.location.replace(identity.user?"/dashboard":"/login");
        return;
      }
      const result=await apiFetch<PayoutReadinessResponse>("/api/merchant/payout-readiness");
      setReport(result);
    }catch(cause){
      const message=cause instanceof Error?cause.message:"Partner payout readiness could not be loaded.";
      if(message.startsWith("401:"))window.location.replace("/login");
      else setError(message);
    }finally{setLoading(false);setBusy(false);}
  },[]);
  useEffect(()=>{void load();},[load]);

  const totals=useMemo(()=>{
    const rows=report?.data||[];
    const sum=(key:"held_commission"|"eligible_commission")=>rows.reduce((total,row)=>{
      const value=Number(row[key]||0);
      return total+(Number.isFinite(value)?value:0);
    },0);
    const currencies=[...new Set(rows.map(row=>row.currency))];
    return {rows:rows.length,eligible:sum("eligible_commission"),held:sum("held_commission"),currencies};
  },[report]);

  const refresh=async()=>{setBusy(true);await load();};

  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:px-8">
    <div className="mx-auto max-w-7xl">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <a href="/merchant" className="text-sm font-bold text-indigo-700">← Merchant dashboard</a>
          <p className="mt-6 text-xs font-black uppercase tracking-[.18em] text-indigo-600">Merchant · Partner finance</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Partner payout readiness</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Review partner earnings from verified signed checkout events. Refund holds and each program's minimum payout are applied before an amount is marked ready for manual review.</p>
        </div>
        <nav aria-label="Partner finance navigation" className="flex flex-wrap gap-2">
          <a href="/merchant" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold">Merchant overview</a>
          <a href="/merchant/offers" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold">Manage programs</a>
          <a href="/merchant/applications" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold">Applications</a>
          <button type="button" onClick={()=>void refresh()} disabled={busy||loading} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">{busy?"Refreshing…":"Refresh"}</button>
        </nav>
      </header>

      {error&&<div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
      {loading&&<p role="status" className="mt-6 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Loading partner earnings and refund holds…</p>}

      {!loading&&report&&<>
        <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Partner payout summary">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Partner program rows</p><p className="mt-2 text-3xl font-black tabular-nums">{totals.rows}</p><p className="mt-1 text-xs text-slate-500">Program and currency combinations</p></article>
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Held for refund window</p><p className="mt-2 text-3xl font-black tabular-nums">{totals.currencies.length===1?money(String(totals.held),totals.currencies[0]):"Multiple currencies"}</p><p className="mt-1 text-xs text-slate-500">Not yet eligible under program terms</p></article>
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Eligible for manual review</p><p className="mt-2 text-3xl font-black tabular-nums">{totals.currencies.length===1?money(String(totals.eligible),totals.currencies[0]):"Multiple currencies"}</p><p className="mt-1 text-xs text-slate-500">After the hold and minimum threshold</p></article>
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Transfers initiated</p><p className="mt-2 text-3xl font-black tabular-nums">0</p><p className="mt-1 text-xs text-slate-500">Transfers are not enabled in this workflow</p></article>
        </section>

        <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-black">Publisher earnings by program</h2><p className="mt-1 text-sm text-slate-500">{report.count} record(s) · Calculated {new Date(report.as_of).toLocaleString()}</p></div><span className="rounded-full bg-slate-100 px-3 py-2 text-xs font-bold text-slate-700">Review only · no automatic payment</span></div>
          {report.data.length===0&&<p className="mt-5 rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No approved publisher links have generated merchant-signed conversion evidence yet.</p>}
          <div className="mt-5 grid gap-3">
            {report.data.map((item)=><article key={item.program_id+"-"+item.publisher_workspace_id+"-"+item.currency} className="rounded-2xl border border-slate-200 p-4 sm:p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0"><h3 className="font-black">{item.program_name}</h3><p className="mt-1 text-sm text-slate-600">{item.publisher_email} · {item.currency}</p><p className="mt-1 text-xs text-slate-500">Application: {label(item.application_status)} · Promotion link: {label(item.promotion_link_status)}</p></div>
                <span className={"rounded-full px-3 py-1.5 text-xs font-bold "+stateClass(item.payout_state)}>{label(item.payout_state)}</span>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
                <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Gross commission</p><p className="mt-1 font-bold tabular-nums">{money(item.gross_commission,item.currency)}</p></div>
                <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Reversed</p><p className="mt-1 font-bold tabular-nums">{money(item.reversed_commission,item.currency)}</p></div>
                <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Net evidence</p><p className="mt-1 font-bold tabular-nums">{money(item.net_commission,item.currency)}</p></div>
                <div className="rounded-xl bg-amber-50 p-3"><p className="text-xs text-amber-900">On refund hold</p><p className="mt-1 font-bold tabular-nums text-amber-950">{money(item.held_commission,item.currency)}</p></div>
                <div className="rounded-xl bg-emerald-50 p-3"><p className="text-xs text-emerald-900">Eligible</p><p className="mt-1 font-bold tabular-nums text-emerald-950">{money(item.eligible_commission,item.currency)}</p></div>
              </div>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500">
                <span>Minimum: {money(item.minimum_payout_amount,item.currency)}</span>
                <span>Refund hold: {item.refund_hold_days} days</span>
                <span>Schedule: {label(item.payout_schedule)}</span>
                <span>Events: {item.conversion_count} conversion(s), {item.reversal_event_count} reversal(s)</span>
                {item.next_eligible_at&&<span>Next hold release: {new Date(item.next_eligible_at).toLocaleString()}</span>}
                {item.threshold_reached&&<span className="font-bold text-emerald-700">Minimum reached</span>}
              </div>
            </article>)}
          </div>
        </section>
        <p className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">{report.note} A merchant operator must perform any separate financial reconciliation and payment process outside this screen.</p>
      </>}
    </div>
  </main>;
}

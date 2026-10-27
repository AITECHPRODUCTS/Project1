"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type AdPlan={id:string;campaign_name:string;daily_budget_usd:string;status:string;platforms:string[];created_at:string|null};
type Guardrail={
  id:string;campaign_plan_id:string;daily_spend_cap_usd:string;campaign_spend_cap_usd:string;
  minimum_roas:string;maximum_cpa_usd:string|null;minimum_verified_impressions:number;
  minimum_verified_clicks:number;minimum_verified_conversions:number;kill_switch_engaged:boolean;
  stop_latched:boolean;last_evaluated_at:string|null;last_evaluation:Record<string,unknown>;
  live_spend_authorized:boolean;external_campaign_changes_executed:boolean;execution_note:string;
};
const inputClass="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm";
const labelClass="block text-sm font-bold text-slate-700";

export default function AdGuardrailsPage(){
  const [plans,setPlans]=useState<AdPlan[]>([]);
  const [guardrails,setGuardrails]=useState<Guardrail[]>([]);
  const [planId,setPlanId]=useState("");
  const [dailyCap,setDailyCap]=useState("40.00");
  const [campaignCap,setCampaignCap]=useState("500.00");
  const [minimumRoas,setMinimumRoas]=useState("1.20");
  const [maximumCpa,setMaximumCpa]=useState("35.00");
  const [minImpressions,setMinImpressions]=useState("1000");
  const [minClicks,setMinClicks]=useState("30");
  const [minConversions,setMinConversions]=useState("3");
  const [resetReason,setResetReason]=useState("");
  const [resetTarget,setResetTarget]=useState("");
  const [busy,setBusy]=useState("");
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");

  const load=useCallback(async()=>{
    setError("");
    try{
      const [plansResponse,guardrailsResponse]=await Promise.all([
        apiFetch<{count:number;data:AdPlan[]}>("/api/ads/plans?limit=200"),
        apiFetch<{count:number;data:Guardrail[]}>("/api/ads/guardrails?limit=300")
      ]);
      setPlans(plansResponse.data||[]);
      setGuardrails(guardrailsResponse.data||[]);
      setPlanId(old=>old||plansResponse.data?.[0]?.id||"");
    }catch(e){setError(e instanceof Error?e.message:"Could not load ad plans/guardrails. Sign in to an authorized workspace.");}
  },[]);
  useEffect(()=>{void load()},[load]);

  const act=async(label:string,path:string,payload?:unknown)=>{
    setBusy(label);setError("");setNotice("");
    try{
      const result=await apiFetch<Guardrail>(path,{method:"POST",body:payload===undefined?undefined:JSON.stringify(payload)});
      const evaluation=result.last_evaluation||{};
      setNotice(label==="evaluate"
        ? "Evaluation status: "+String((result as unknown as {evaluation?:{status?:string}}).evaluation?.status||evaluation.status||"recorded")+". No provider action is executed."
        : "Guardrail status updated. Live ad spend remains unauthorized.");
      await load();
      return result;
    }catch(e){setError(e instanceof Error?e.message:"Ad guardrail operation failed.");return null;}
    finally{setBusy("")}
  };
  const create=async(e:FormEvent)=>{
    e.preventDefault();
    if(!planId){setError("Create an ad plan before configuring budget guardrails.");return;}
    if(Number(campaignCap)<Number(dailyCap)){setError("Campaign cap must be at least the daily cap.");return;}
    const result=await act("create","/api/ads/plans/"+encodeURIComponent(planId)+"/guardrails",{
      daily_spend_cap_usd:dailyCap,campaign_spend_cap_usd:campaignCap,minimum_roas:minimumRoas,
      maximum_cpa_usd:maximumCpa.trim()?maximumCpa:null,
      minimum_verified_impressions:Number(minImpressions),minimum_verified_clicks:Number(minClicks),
      minimum_verified_conversions:Number(minConversions)
    });
    if(result){setDailyCap("40.00");setCampaignCap("500.00");}
  };
  const reset=async(guardrailId:string)=>{
    const result=await act("reset","/api/ads/guardrails/"+encodeURIComponent(guardrailId)+"/reset",{
      confirm_reset:true,reason:resetReason
    });
    if(result){setResetReason("");setResetTarget("");}
  };

  return <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10">
    <div className="mx-auto max-w-6xl">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div><a href="/" className="text-sm font-bold text-indigo-700">← Growth command center</a><p className="mt-6 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Paid media · Spend safety</p><h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Ad budget guardrails</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">Set per-plan daily and campaign caps, define ROAS/CPA stop-loss thresholds, inspect evidence-aware evaluations and latch an emergency kill switch. This layer never launches or changes external ad campaigns; provider execution remains disabled.</p></div>
        <button onClick={()=>void load()} disabled={!!busy} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">Refresh</button>
      </header>
      {error&&<div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
      {notice&&<div role="status" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
      <section className="mt-7 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <article className="rounded-2xl border border-white bg-white p-4 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Plans in workspace</p><p className="mt-2 text-3xl font-black">{plans.length}</p></article>
        <article className="rounded-2xl border border-white bg-white p-4 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Guardrail policies</p><p className="mt-2 text-3xl font-black">{guardrails.length}</p></article>
        <article className="rounded-2xl border border-white bg-white p-4 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Stop latches active</p><p className="mt-2 text-3xl font-black">{guardrails.filter(x=>x.stop_latched||x.kill_switch_engaged).length}</p></article>
      </section>
      <section className="mt-7 rounded-3xl border border-white bg-white p-5 shadow-sm sm:p-7">
        <h2 className="text-xl font-black">Configure a plan's safety policy</h2><p className="mt-1 text-sm leading-6 text-slate-500">A guardrail can only be configured for a plan in the active workspace. A zero-budget draft still cannot spend, and this feature never grants provider write permission.</p>
        {plans.length===0?<p className="mt-4 rounded-xl border border-dashed border-slate-200 p-5 text-sm text-slate-500">No ad plans exist in this workspace yet. Draft a campaign in Ad Studio, then return here.</p>:
        <form onSubmit={create} className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="lg:col-span-2"><label className={labelClass} htmlFor="guardrail-plan">Ad plan</label><select id="guardrail-plan" className={inputClass} value={planId} onChange={e=>setPlanId(e.target.value)} required>{plans.map(p=><option key={p.id} value={p.id}>{p.campaign_name} · current draft daily budget: USD {p.daily_budget_usd}</option>)}</select></div>
          <div><label className={labelClass} htmlFor="guardrail-daily">Daily spend cap (USD)</label><input id="guardrail-daily" className={inputClass} type="number" min="0.01" max="1000000" step="0.01" value={dailyCap} onChange={e=>setDailyCap(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="guardrail-campaign">Campaign spend cap (USD)</label><input id="guardrail-campaign" className={inputClass} type="number" min="0.01" max="10000000" step="0.01" value={campaignCap} onChange={e=>setCampaignCap(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="guardrail-roas">Minimum ROAS</label><input id="guardrail-roas" className={inputClass} type="number" min="0" max="100" step="0.01" value={minimumRoas} onChange={e=>setMinimumRoas(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="guardrail-cpa">Maximum CPA (USD, optional)</label><input id="guardrail-cpa" className={inputClass} type="number" min="0.01" max="1000000" step="0.01" value={maximumCpa} onChange={e=>setMaximumCpa(e.target.value)}/></div>
          <div><label className={labelClass} htmlFor="guardrail-impressions">Minimum verified impressions</label><input id="guardrail-impressions" className={inputClass} type="number" min="1" max="1000000" value={minImpressions} onChange={e=>setMinImpressions(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="guardrail-clicks">Minimum verified clicks</label><input id="guardrail-clicks" className={inputClass} type="number" min="1" max="100000" value={minClicks} onChange={e=>setMinClicks(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="guardrail-conversions">Minimum verified conversions</label><input id="guardrail-conversions" className={inputClass} type="number" min="1" max="100000" value={minConversions} onChange={e=>setMinConversions(e.target.value)} required/></div>
          <div className="lg:col-span-2"><button disabled={!!busy} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white disabled:opacity-50">{busy==="create"?"Saving policy…":"Create guardrail policy"}</button></div>
        </form>}
      </section>
      <section className="mt-7 rounded-3xl border border-white bg-white p-5 shadow-sm sm:p-7"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-xl font-black">Workspace guardrails</h2><span className="rounded-full bg-amber-50 px-3 py-1.5 text-xs font-bold text-amber-800">Provider execution disabled</span></div>
        <div className="mt-5 grid gap-4">
          {guardrails.length===0&&<p className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">No guardrail policies configured yet.</p>}
          {guardrails.map(g=><article key={g.id} className="rounded-2xl border border-slate-200 p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-black">{plans.find(p=>p.id===g.campaign_plan_id)?.campaign_name||"Ad plan "+g.campaign_plan_id.slice(0,8)}</h3><p className="mt-1 text-xs text-slate-500">Daily cap: USD {g.daily_spend_cap_usd} · Campaign cap: USD {g.campaign_spend_cap_usd} · ROAS floor {g.minimum_roas} · CPA ceiling {g.maximum_cpa_usd===null?"off":"USD "+g.maximum_cpa_usd}</p><p className="mt-2 text-xs text-slate-500">Last evaluated: {g.last_evaluated_at?new Date(g.last_evaluated_at).toLocaleString():"never"} · Live spend authorized: no</p></div><span className={"rounded-full px-3 py-1.5 text-xs font-bold "+(g.kill_switch_engaged||g.stop_latched?"bg-rose-50 text-rose-800":"bg-emerald-50 text-emerald-800")}>{g.kill_switch_engaged||g.stop_latched?"STOP LATCHED":"Monitoring policy"}</span></div>
            {Object.keys(g.last_evaluation||{}).length>0&&<pre className="mt-4 max-h-64 overflow-auto rounded-xl bg-slate-950 p-3 text-xs leading-5 text-slate-100">{JSON.stringify(g.last_evaluation,null,2)}</pre>}
            <div className="mt-4 flex flex-wrap gap-2"><button onClick={()=>void act("evaluate","/api/ads/guardrails/"+encodeURIComponent(g.id)+"/evaluate")} disabled={!!busy} className="rounded-xl bg-indigo-600 px-3 py-2.5 text-sm font-bold text-white disabled:opacity-50">Evaluate verified evidence</button><button onClick={()=>void act("kill","/api/ads/guardrails/"+encodeURIComponent(g.id)+"/kill-switch")} disabled={!!busy||g.kill_switch_engaged} className="rounded-xl border border-rose-200 px-3 py-2.5 text-sm font-bold text-rose-700 disabled:opacity-50">Engage kill switch</button>{(g.kill_switch_engaged||g.stop_latched)&&<button onClick={()=>setResetTarget(g.id)} disabled={!!busy} className="rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-bold disabled:opacity-50">Request reset</button>}</div>
            {resetTarget===g.id&&<div className="mt-4 rounded-xl border border-amber-100 bg-amber-50/70 p-4"><p className="text-sm font-bold text-amber-900">Explicit reset review</p><p className="mt-1 text-xs leading-5 text-amber-900">Reset is refused while the last evaluation has an active breach or while evidence is unverified/mixed. Reset never authorizes provider spend.</p><label className={labelClass+" mt-3"} htmlFor={"reset-reason-"+g.id}>Reason (minimum 20 characters)</label><textarea id={"reset-reason-"+g.id} className={inputClass} rows={2} value={resetReason} onChange={e=>setResetReason(e.target.value)} minLength={20} maxLength={2000}/><div className="mt-3 flex gap-2"><button onClick={()=>void reset(g.id)} disabled={!!busy||resetReason.trim().length<20} className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">Confirm reset</button><button onClick={()=>setResetTarget("")} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold">Cancel</button></div></div>}
          </article>)}
        </div>
      </section>
      <p className="mt-5 text-xs leading-5 text-slate-500">Important: observations are blocked from automated stop-loss evaluation until all linked observations are explicitly provider-verified. The current capture API labels entries unverified. A breach latches a review/kill state but does not call an ad provider or stop a real campaign. A future provider adapter must check the kill latch before any write action.</p>
    </div>
  </main>;
}

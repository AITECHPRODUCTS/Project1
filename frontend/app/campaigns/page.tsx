"use client";
import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type Campaign={id:string;name:string;niche:string;primary_destination:string;fallback_destination:string|null;tracking_parameter:string;tracking_url:string;is_active:boolean;primary_healthy:boolean|null;fallback_healthy:boolean|null;health_last_error:string|null};
type CampaignList={count:number;data:Campaign[]};
type CampaignCreated={id:string;name:string;tracking_parameter:string;tracking_url:string;status:string};
type CampaignHealth={campaign_id:string;route:string;destination:string|null;status_code:number|null;primary_healthy:boolean;fallback_healthy:boolean|null;health_error:string|null;note:string};
const fieldClass="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100";
const buttonClass="rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50";

export default function CampaignTrackingPage(){
 const [campaigns,setCampaigns]=useState<Campaign[]>([]);
 const [name,setName]=useState("");const [niche,setNiche]=useState("");
 const [destination,setDestination]=useState("");const [fallback,setFallback]=useState("");
 const [trackingParameter,setTrackingParameter]=useState<"tid"|"subid">("tid");
 const [loading,setLoading]=useState(true);const [busy,setBusy]=useState("");
 const [error,setError]=useState("");const [notice,setNotice]=useState("");
 const [created,setCreated]=useState<CampaignCreated|null>(null);
 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{const result=await apiFetch<CampaignList>("/api/campaigns");setCampaigns(Array.isArray(result.data)?result.data:[]);}
  catch(exc){setError(exc instanceof Error?exc.message:"Could not load campaigns for the active workspace.");}
  finally{setLoading(false);}
 },[]);
 useEffect(()=>{void load();},[load]);
 const createCampaign=async(event:FormEvent<HTMLFormElement>)=>{
  event.preventDefault();setBusy("create");setError("");setNotice("");setCreated(null);
  try{
   const result=await apiFetch<CampaignCreated>("/api/campaigns",{
    method:"POST",body:JSON.stringify({
     name:name.trim(),niche:niche.trim(),primary_destination:destination.trim(),
     fallback_destination:fallback.trim()||null,tracking_parameter:trackingParameter,
     disclosure_text:"Disclosure: I may earn a commission from qualifying purchases.",
     auto_publish:false,max_daily_spend:0
    })
   });
   setCreated(result);setNotice("Campaign tracking link created. Publishing and paid advertising remain disabled.");
   setName("");setDestination("");setFallback("");await load();
  }catch(exc){setError(exc instanceof Error?exc.message:"Campaign could not be created.");}
  finally{setBusy("");}
 };
 const checkHealth=async(id:string)=>{
  setBusy(id);setError("");setNotice("");
  try{
   const result=await apiFetch<CampaignHealth>("/api/campaigns/"+encodeURIComponent(id)+"/health",{method:"POST"});
   setCampaigns(current=>current.map(row=>row.id===id?{...row,primary_healthy:result.primary_healthy,fallback_healthy:result.fallback_healthy,health_last_error:result.health_error}:row));
   setNotice(result.destination?"Destination health check completed.":"No healthy destination was found; redirects will be blocked.");
  }catch(exc){setError(exc instanceof Error?exc.message:"Destination health check failed.");}
  finally{setBusy("");}
 };
 return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:px-8"><div className="mx-auto max-w-6xl">
  <header className="flex flex-wrap items-center justify-between gap-4"><div>
   <p className="text-xs font-black uppercase tracking-[.18em] text-indigo-600">Commission earner · Attribution</p>
   <h1 className="mt-2 text-3xl font-black tracking-tight">Campaign tracking links</h1>
   <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Create workspace-owned redirect links that record a first-party click ID before sending a visitor to your affiliate destination.</p>
  </div><a href="/" className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold">Back to growth cockpit</a></header>
  {error&&<div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
  {notice&&<div role="status" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
  <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
   <h2 className="text-xl font-black">Create a campaign link</h2>
   <p className="mt-1 text-sm text-slate-600">Paste the final affiliate destination or HopLink. Use the TID parameter for ClickBank when its Orders response exposes the tracking ID.</p>
   <form onSubmit={createCampaign} className="mt-5 grid gap-4 md:grid-cols-2">
    <label className="block text-sm font-bold">Campaign name<input required minLength={2} maxLength={300} value={name} onChange={e=>setName(e.target.value)} className={fieldClass} placeholder="e.g. SEO review article"/></label>
    <label className="block text-sm font-bold">Niche<input required minLength={2} maxLength={200} value={niche} onChange={e=>setNiche(e.target.value)} className={fieldClass} placeholder="e.g. productivity software"/></label>
    <label className="block text-sm font-bold md:col-span-2">Primary affiliate destination URL<input required type="url" maxLength={2048} value={destination} onChange={e=>setDestination(e.target.value)} className={fieldClass} placeholder="https://... your affiliate HopLink or destination"/></label>
    <label className="block text-sm font-bold md:col-span-2">Fallback destination URL (optional)<input type="url" maxLength={2048} value={fallback} onChange={e=>setFallback(e.target.value)} className={fieldClass} placeholder="https://... optional fallback page"/></label>
    <label className="block text-sm font-bold">Affiliate tracking parameter<select value={trackingParameter} onChange={e=>setTrackingParameter(e.target.value as "tid"|"subid")} className={fieldClass}><option value="tid">tid — ClickBank TID</option><option value="subid">subid — generic sub-ID</option></select></label>
    <div className="rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-600"><p className="font-bold text-slate-800">How TID matching works</p><p>The redirect writes this app's click ID into the selected query parameter. A ClickBank order can be linked only when its returned tracking ID exactly matches that click ID and the event falls within ClickBank's 60-day referral window. No fuzzy or cross-workspace matching is performed.</p></div>
    <div className="md:col-span-2 flex flex-wrap items-center gap-3"><button type="submit" disabled={busy!==""||name.trim().length<2||niche.trim().length<2||destination.trim().length<8} className={buttonClass}>{busy==="create"?"Creating…":"Create tracking link"}</button><span className="text-xs text-slate-500">This action creates a tracking redirect only. It does not publish content, launch ads or spend money.</span></div>
   </form>
  </section>
  {created&&<section className="mt-6 rounded-2xl border border-indigo-200 bg-indigo-50 p-5" data-testid="created-campaign"><p className="text-xs font-black uppercase tracking-wider text-indigo-700">Tracking link created</p><p className="mt-2 break-all font-mono text-sm text-slate-800">{created.tracking_url}</p><p className="mt-2 text-xs text-slate-600">Query parameter: {created.tracking_parameter}. Share this redirect URL instead of placing the raw destination directly in your campaign.</p></section>}
  <section className="mt-8"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-black">Workspace campaigns</h2><p className="mt-1 text-sm text-slate-600">Campaigns and click identifiers are isolated to the active workspace.</p></div><button type="button" onClick={()=>void load()} disabled={busy!==""||loading} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold disabled:opacity-50">Refresh</button></div>
   {loading?<p role="status" className="mt-5 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500">Loading campaigns…</p>:campaigns.length===0?<p className="mt-5 rounded-xl border border-dashed border-slate-300 bg-white p-7 text-center text-sm text-slate-500">No campaign links yet. Create one above to start recording first-party clicks.</p>:<div className="mt-5 grid gap-4">{campaigns.map(campaign=><article key={campaign.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" data-testid={"campaign-"+campaign.id}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-black">{campaign.name}</h3><p className="mt-1 text-xs text-slate-500">{campaign.niche} · {campaign.tracking_parameter} · {campaign.is_active?"Active":"Inactive"}</p></div><button type="button" onClick={()=>void checkHealth(campaign.id)} disabled={busy!==""||!campaign.is_active} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold disabled:opacity-40">{busy===campaign.id?"Checking…":"Check destination health"}</button></div>
    <p className="mt-3 break-all font-mono text-xs text-indigo-700">{campaign.tracking_url}</p><p className="mt-2 text-xs text-slate-600">Destination: {campaign.primary_destination}</p><p className="mt-2 text-xs text-slate-600">{campaign.primary_healthy===true?"Primary destination healthy":campaign.primary_healthy===false?"Primary destination unavailable":"Health not checked yet"}</p>{campaign.health_last_error&&<p className="mt-2 text-xs text-rose-700">{campaign.health_last_error}</p>}
   </article>)}</div>}
  </section>
 </div></main>;
}

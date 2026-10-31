"use client";

import { useCallback,useEffect,useState } from "react";
import { apiFetch } from "@/lib/api";

type Identity={user?:{email?:string;account_type?:string;is_admin?:boolean}};
type Status={clicks?:number;conversion_events?:number;commission_recorded?:number};
type CountResponse={count?:number;total_count?:number;data?:unknown[]};

const card="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-indigo-200 hover:shadow-md";
const linkClass="mt-4 inline-flex rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white";

export default function PublisherDashboardPage(){
  const [email,setEmail]=useState("");
  const [status,setStatus]=useState<Status|null>(null);
  const [offerCount,setOfferCount]=useState<number|null>(null);
  const [applicationCount,setApplicationCount]=useState<number|null>(null);
  const [campaignCount,setCampaignCount]=useState<number|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [denied,setDenied]=useState(false);

  const load=useCallback(async()=>{
    setLoading(true);setError("");setDenied(false);
    try{
      const identity=await apiFetch<Identity>("/api/auth/me");
      if(identity.user?.account_type!=="affiliate_publisher"&&identity.user?.is_admin!==true){setDenied(true);return;}
      setEmail(identity.user?.email||"");
      const [metrics,offers,applications,campaigns]=await Promise.all([
        apiFetch<Status>("/api/status"),
        apiFetch<CountResponse>("/api/marketplace/offers?limit=100"),
        apiFetch<CountResponse>("/api/marketplace/applications?limit=100"),
        apiFetch<CountResponse>("/api/campaigns")
      ]);
      setStatus(metrics);
      setOfferCount(offers.count??offers.data?.length??0);
      setApplicationCount(applications.total_count??applications.count??applications.data?.length??0);
      setCampaignCount(campaigns.count??campaigns.data?.length??0);
    }catch(cause){
      const message=cause instanceof Error?cause.message:"Publisher dashboard could not be loaded.";
      if(message.includes("401"))window.location.replace("/");
      else setError(message);
    }finally{setLoading(false);}
  },[]);

  useEffect(()=>{void load();},[load]);

  if(denied)return <main className="grid min-h-screen place-items-center bg-slate-50 p-6">
    <section className="max-w-lg rounded-2xl border border-slate-200 bg-white p-7 text-center">
      <h1 className="text-xl font-black">Publisher access required</h1>
      <p className="mt-2 text-sm text-slate-600">This dashboard is for accounts registered as Affiliate / Publisher.</p>
      <a href="/" className="mt-4 inline-block font-bold text-indigo-700">Return to sign in</a>
    </section>
  </main>;

  return <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10">
    <div className="mx-auto max-w-7xl">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <p className="text-xs font-black uppercase tracking-[.2em] text-indigo-600">Affiliate · Publisher</p>
          <h1 className="mt-2 text-3xl font-black sm:text-4xl">Publisher workspace</h1>
          <p className="mt-2 text-sm text-slate-500">Find suitable offers, prepare responsible promotions and measure recorded outcomes.</p>
          {email&&<p className="mt-2 text-xs text-slate-400">Signed in as {email}</p>}
        </div>
        <button onClick={()=>void load()} disabled={loading} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold disabled:opacity-50">{loading?"Refreshing…":"Refresh"}</button>
      </header>
      {error&&<p role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Tracked clicks",status?String(status.clicks??0):"—","First-party records in this workspace"],
          ["Conversion events",status?String(status.conversion_events??0):"—","Recorded provider events; not all are confirmed"],
          ["Commission recorded",status?"$"+Number(status.commission_recorded??0).toFixed(2):"—","Observations, not verified payout"],
          ["Active campaigns",campaignCount===null?"—":String(campaignCount),"Persisted campaign records"]
        ].map(([title,value,note])=><article key={title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">{title}</p><p className="mt-3 text-3xl font-black">{value}</p><p className="mt-1 text-xs leading-5 text-slate-500">{note}</p>
        </article>)}
      </section>
      <section className="mt-8">
        <h2 className="text-xl font-black">Publisher tools</h2>
        <p className="mt-1 text-sm text-slate-500">Existing features for your publisher workspace. A catalogue listing is not proof of a connected account or programme approval.</p>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <article className={card}><h3 className="font-black">Affiliate offer catalog</h3><p className="mt-2 text-sm text-slate-500">Search saved network offers and prepare shortlists.</p><a className={linkClass} href="/offers">Browse offer catalog</a></article>
          <article className={card}><h3 className="font-black">Publisher marketplace</h3><p className="mt-2 text-sm text-slate-500">{offerCount===null?"Review offers listed by merchants.":offerCount+" merchant offer(s) listed for this workspace."}</p><a className={linkClass} href="/marketplace">Explore merchant offers</a></article>
          <article className={card}><h3 className="font-black">My applications</h3><p className="mt-2 text-sm text-slate-500">{applicationCount===null?"Review your submitted publisher applications.":applicationCount+" application record(s) in this workspace."}</p><a className={linkClass} href="/marketplace">View application status</a></article>
          <article className={card}><h3 className="font-black">Affiliate research</h3><p className="mt-2 text-sm text-slate-500">Search connected affiliate-account product feeds.</p><a className={linkClass} href="/affiliate-research">Open research</a></article>
          <article className={card}><h3 className="font-black">Affiliate integrations</h3><p className="mt-2 text-sm text-slate-500">Connect supported networks using read permissions.</p><a className={linkClass} href="/integrations">Manage integrations</a></article>
          <article className={card}><h3 className="font-black">Campaign tracking</h3><p className="mt-2 text-sm text-slate-500">Manage tracked destinations and campaign records.</p><a className={linkClass} href="/campaigns">Open campaigns</a></article>
          <article className={card}><h3 className="font-black">Content studio</h3><p className="mt-2 text-sm text-slate-500">Draft articles, creative assets and social content.</p><a className={linkClass} href="/?view=content-studio">Open content studio</a></article>
          <article className={card}><h3 className="font-black">SEO tools</h3><p className="mt-2 text-sm text-slate-500">Audit pages and plan content maintenance.</p><a className={linkClass} href="/?view=seo-audit">Open SEO audit</a></article>
          <article className={card}><h3 className="font-black">Leads & attribution</h3><p className="mt-2 text-sm text-slate-500">Review consented leads and attributed outcomes.</p><a className={linkClass} href="/leads">Open leads</a></article>
        </div>
      </section>
      <p className="mt-8 rounded-xl border border-indigo-100 bg-indigo-50 p-4 text-xs leading-5 text-indigo-900">External publishing, provider writes and paid advertising stay disabled until their authorization, policy, approval and budget gates pass.</p>
      {loading&&<p role="status" className="mt-4 text-xs text-slate-500">Loading publisher workspace data…</p>}
    </div>
  </main>;
}

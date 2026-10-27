"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type MarketplaceOffer={
  id:string;name:string;description:string;category:string;commission_type:string;commission_value:string;
  commission_currency:string;terms_version:string;commission_terms_url:string;allowed_regions:string[];
  restricted_traffic_sources:string[];affiliate_disclosure:string;marketplace_listed:boolean;
  internal_status:string;affiliate_network_approval_status:string;affiliate_network_approved:boolean;
  provider_submission_performed:boolean;
};
type MarketplaceApplication={
  id:string;merchant_offer_id:string;offer_name:string;status:string;applicant_email:string;
  publisher_website_url:string;audience_description:string;traffic_sources:string[];intended_regions:string[];
  promotion_plan:string;terms_snapshot:Record<string,unknown>;reviewer_notes:string|null;
  provider_submission_status:string;affiliate_network_approved:boolean;
};
const inputClass="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm";
const labelClass="block text-sm font-bold text-slate-700";

export default function MarketplacePage(){
  const [offers,setOffers]=useState<MarketplaceOffer[]>([]);
  const [applications,setApplications]=useState<MarketplaceApplication[]>([]);
  const [selected,setSelected]=useState<MarketplaceOffer|null>(null);
  const [website,setWebsite]=useState("");
  const [audience,setAudience]=useState("");
  const [plan,setPlan]=useState("");
  const [traffic,setTraffic]=useState("seo, blog, email_opt_in");
  const [regions,setRegions]=useState("US, GB, IN");
  const [termsReviewed,setTermsReviewed]=useState(false);
  const [trafficReviewed,setTrafficReviewed]=useState(false);
  const [disclosureReady,setDisclosureReady]=useState(false);
  const [shareConsent,setShareConsent]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");

  const load=useCallback(async()=>{
    setError("");
    try{
      const [catalog,outgoing]=await Promise.all([
        apiFetch<{count:number;data:MarketplaceOffer[]}>("/api/marketplace/offers"),
        apiFetch<{count:number;data:MarketplaceApplication[]}>("/api/marketplace/applications")
      ]);
      setOffers(catalog.data||[]);
      setApplications(outgoing.data||[]);
    }catch(e){setError(e instanceof Error?e.message:"Could not load marketplace data. Sign in with an authorized workspace owner/admin account.");}
  },[]);
  useEffect(()=>{void load()},[load]);

  const submitApplication=async(e:FormEvent)=>{
    e.preventDefault();
    if(!selected)return;
    setBusy(true);setError("");setNotice("");
    try{
      const result=await apiFetch<MarketplaceApplication>("/api/marketplace/offers/"+encodeURIComponent(selected.id)+"/applications",{
        method:"POST",
        body:JSON.stringify({
          publisher_website_url:website,audience_description:audience,promotion_plan:plan,
          traffic_sources:traffic.split(",").map(x=>x.trim()).filter(Boolean),
          intended_regions:regions.split(",").map(x=>x.trim()).filter(Boolean),
          offer_terms_reviewed:termsReviewed,traffic_restrictions_reviewed:trafficReviewed,
          affiliate_disclosure_ready:disclosureReady,contact_sharing_consent:shareConsent
        })
      });
      setNotice("Application submitted for the merchant's internal review. Status: "+result.status+". This is not an external affiliate-network application.");
      setSelected(null);setPlan("");setAudience("");setTermsReviewed(false);setTrafficReviewed(false);setDisclosureReady(false);setShareConsent(false);
      await load();
    }catch(e){setError(e instanceof Error?e.message:"Application could not be submitted.");}
    finally{setBusy(false);}
  };

  return <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10">
    <div className="mx-auto max-w-6xl">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div><a href="/" className="text-sm font-bold text-indigo-700">← Growth command center</a><p className="mt-6 text-xs font-black uppercase tracking-[.2em] text-indigo-600">S1 · Internal marketplace</p><h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Publisher marketplace</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">Only merchant offers that were internally reviewed and deliberately listed here appear. Internal listing is not an affiliate-network connection or approval. Review the displayed terms and restrictions before you apply.</p></div>
        <div className="flex flex-wrap gap-2"><a href="/merchant/offers" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold">Merchant offers</a><button onClick={()=>void load()} disabled={busy} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">Refresh</button></div>
      </header>
      {error&&<div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
      {notice&&<div role="status" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
      <section className="mt-7 rounded-3xl border border-white bg-white p-5 shadow-sm sm:p-7">
        <div className="flex items-center justify-between gap-3"><div><h2 className="text-xl font-black">Available merchant offers</h2><p className="mt-1 text-sm text-slate-500">{offers.length} listing(s) available outside your own workspace.</p></div></div>
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {offers.length===0&&<p className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">No merchant offers are currently listed for this workspace. Unlisted or unapproved offers are not shown.</p>}
          {offers.map(offer=><article key={offer.id} className="rounded-2xl border border-slate-200 p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="text-base font-black">{offer.name}</h3><p className="mt-1 text-xs text-slate-500">{offer.category} · Terms version {offer.terms_version}</p></div><span className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-800">Merchant reviewed internally</span></div>
            <p className="mt-3 text-sm leading-6 text-slate-600">{offer.description}</p>
            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Commission terms (not payout evidence)</p><p className="mt-1 text-sm font-bold">{offer.commission_value} {offer.commission_currency} · {offer.commission_type}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Allowed regions</p><p className="mt-1 text-sm font-bold">{offer.allowed_regions.join(", ")}</p></div></div>
            <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50/70 p-3"><p className="text-xs font-bold text-amber-900">Traffic restrictions</p><p className="mt-1 text-sm text-amber-900">{offer.restricted_traffic_sources.join(", ")||"No restrictions recorded"}</p><p className="mt-2 text-xs leading-5 text-amber-900">{offer.affiliate_disclosure}</p><a href={offer.commission_terms_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex break-all text-xs font-bold text-indigo-700 underline">Review commission terms reference</a></div>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-slate-500">External network approval: {offer.affiliate_network_approval_status}</p><button onClick={()=>{
              setSelected(offer);setNotice("");setError("");
              setRegions(offer.allowed_regions.join(", "));
              const normalize=(value:string)=>value.trim().toLowerCase().replace(/[\s-]+/g,"_");
              const restricted=new Set(offer.restricted_traffic_sources.map(normalize));
              const defaults=["seo","blog","organic_social","email_opt_in","video","community","referral","other","paid_search","paid_social","influencer"];
              setTraffic(defaults.filter(value=>!restricted.has(normalize(value))).slice(0,3).join(", "));
            }} className="rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white">Apply to merchant</button></div>
          </article>)}
        </div>
      </section>
      {selected&&<section className="mt-7 rounded-3xl border border-indigo-100 bg-white p-5 shadow-sm sm:p-7"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-black uppercase tracking-widest text-indigo-600">Application draft</p><h2 className="mt-2 text-xl font-black">{selected.name}</h2><p className="mt-1 text-sm text-slate-500">Your profile and promotion plan will be shared with this offer's merchant for review.</p></div><button onClick={()=>setSelected(null)} className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold">Cancel</button></div>
        <form onSubmit={submitApplication} className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div><label className={labelClass} htmlFor="marketplace-publisher-website">Publisher website</label><input id="marketplace-publisher-website" type="url" className={inputClass} value={website} onChange={e=>setWebsite(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="marketplace-audience">Audience</label><textarea id="marketplace-audience" className={inputClass} value={audience} onChange={e=>setAudience(e.target.value)} minLength={30} maxLength={3000} rows={2} required/></div>
          <div><label className={labelClass} htmlFor="marketplace-traffic">Traffic sources</label><input id="marketplace-traffic" className={inputClass} value={traffic} onChange={e=>setTraffic(e.target.value)} required/><p className="mt-1 text-xs text-slate-500">Comma-separated IDs: seo, blog, organic_social, paid_search, paid_social, email_opt_in, video, influencer, community, referral, other</p></div>
          <div><label className={labelClass} htmlFor="marketplace-regions">Intended regions</label><input id="marketplace-regions" className={inputClass} value={regions} onChange={e=>setRegions(e.target.value)} required/></div>
          <div className="lg:col-span-2"><label className={labelClass} htmlFor="marketplace-plan">Promotion plan</label><textarea id="marketplace-plan" className={inputClass} value={plan} onChange={e=>setPlan(e.target.value)} minLength={80} maxLength={6000} rows={4} required placeholder="Describe planned content, traffic methods, disclosures and how you will respect merchant restrictions."/></div>
          <div className="lg:col-span-2 space-y-3 rounded-2xl border border-slate-200 p-4">
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={termsReviewed} onChange={e=>setTermsReviewed(e.target.checked)} required className="mt-1"/><span>I reviewed the merchant's current terms reference and the snapshot shown for this offer.</span></label>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={trafficReviewed} onChange={e=>setTrafficReviewed(e.target.checked)} required className="mt-1"/><span>I reviewed allowed regions and traffic-source restrictions and will comply with them.</span></label>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={disclosureReady} onChange={e=>setDisclosureReady(e.target.checked)} required className="mt-1"/><span>I will clearly disclose affiliate relationships and substantiate claims.</span></label>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={shareConsent} onChange={e=>setShareConsent(e.target.checked)} required className="mt-1"/><span>I consent to sharing my account email, publisher site and application details with this offer's merchant so they can review the request.</span></label>
          </div>
          <div className="lg:col-span-2"><button disabled={busy} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white disabled:opacity-50">{busy?"Submitting…":"Submit for merchant review"}</button></div>
        </form>
      </section>}
      <section className="mt-7 rounded-3xl border border-white bg-white p-5 shadow-sm sm:p-7"><h2 className="text-xl font-black">My marketplace applications</h2><p className="mt-1 text-sm text-slate-500">Internal application decisions do not imply approval by an external affiliate network.</p><div className="mt-4 grid gap-3">
        {applications.length===0&&<p className="rounded-xl border border-dashed border-slate-200 p-5 text-sm text-slate-500">No marketplace applications submitted from this workspace.</p>}
        {applications.map(application=><article key={application.id} className="rounded-xl border border-slate-200 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-bold">{application.offer_name}</h3><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{application.status.replaceAll("_"," ")}</span></div><p className="mt-2 text-xs text-slate-500">Terms snapshot: {String(application.terms_snapshot.terms_version||"unknown")} · External network status: {application.provider_submission_status}</p>{application.reviewer_notes&&<p className="mt-2 text-sm text-slate-600">Reviewer notes: {application.reviewer_notes}</p>}</article>)}
      </div></section>
    </div>
  </main>;
}

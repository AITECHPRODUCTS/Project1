"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type MerchantOffer={
  id:string;name:string;product_url:string;description:string;category:string;
  commission_type:string;commission_value:string;commission_currency:string;terms_version:string;
  commission_terms_url:string;seller_authorization_url:string;allowed_regions:string[];
  restricted_traffic_sources:string[];affiliate_disclosure:string;status:string;
  terms_verified:boolean;seller_authorization_verified:boolean;activation_allowed:boolean;
  reviewer_notes:string|null;reviewed_by:string|null;created_by:string;created_at:string|null;
  affiliate_network_approval_status:string;affiliate_network_approved:boolean;provider_submission_performed:boolean;
};
const inputClass="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm";
const labelClass="block text-sm font-bold text-slate-700";

export default function MerchantOffersPage(){
  const [offers,setOffers]=useState<MerchantOffer[]>([]);
  const [userEmail,setUserEmail]=useState("");
  const [busy,setBusy]=useState("");
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [name,setName]=useState("");
  const [productUrl,setProductUrl]=useState("");
  const [description,setDescription]=useState("");
  const [category,setCategory]=useState("");
  const [commissionType,setCommissionType]=useState("recurring_percentage");
  const [commissionValue,setCommissionValue]=useState("25");
  const [currency,setCurrency]=useState("USD");
  const [termsVersion,setTermsVersion]=useState("");
  const [termsUrl,setTermsUrl]=useState("");
  const [sellerUrl,setSellerUrl]=useState("");
  const [regions,setRegions]=useState("US, GB, IN");
  const [trafficRestrictions,setTrafficRestrictions]=useState("incentivized, spam");
  const [disclosure,setDisclosure]=useState("Affiliate disclosure: publishers may earn commissions from qualifying purchases.");
  const [reviewNotes,setReviewNotes]=useState("");
  const [sellerVerified,setSellerVerified]=useState(false);
  const [termsVerified,setTermsVerified]=useState(false);

  const load=useCallback(async()=>{
    setError("");
    try{
      const [response,me]=await Promise.all([
        apiFetch<{count:number;data:MerchantOffer[]}>("/api/merchant/offers"),
        apiFetch<{user?:{email?:string}}>("/api/auth/me")
      ]);
      setOffers(response.data||[]);
      setUserEmail((me.user?.email||"").toLowerCase());
    }catch(e){setError(e instanceof Error?e.message:"Could not load offers. Sign in with an authorized workspace owner/admin account.");}
  },[]);
  useEffect(()=>{void load()},[load]);

  const act=async(label:string,path:string,payload?:unknown)=>{
    setBusy(label);setError("");setNotice("");
    try{
      const result=await apiFetch<MerchantOffer>(path,{method:"POST",body:payload===undefined?undefined:JSON.stringify(payload)});
      setNotice(result.name+": status "+result.status+". External affiliate-network approval remains "+result.affiliate_network_approval_status+".");
      await load();
    }catch(e){setError(e instanceof Error?e.message:"Merchant offer operation failed.");}
    finally{setBusy("")}
  };
  const create=async(e:FormEvent)=>{
    e.preventDefault();
    await act("create","/api/merchant/offers",{
      name,product_url:productUrl,description,category,commission_type:commissionType,
      commission_value:commissionValue,commission_currency:currency,terms_version:termsVersion,
      commission_terms_url:termsUrl,seller_authorization_url:sellerUrl,
      allowed_regions:regions.split(",").map(x=>x.trim()).filter(Boolean),
      restricted_traffic_sources:trafficRestrictions.split(",").map(x=>x.trim()).filter(Boolean),
      affiliate_disclosure:disclosure
    });
  };
  const review=async(offer:MerchantOffer,decision:"approve"|"reject"|"suspend")=>{
    const path="/api/merchant/offers/"+encodeURIComponent(offer.id)+"/review";
    await act(decision,path,{
      decision,seller_authorization_verified:decision==="approve"&&sellerVerified,
      commission_terms_verified:decision==="approve"&&termsVerified,reviewer_notes:reviewNotes
    });
  };

  return <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10">
    <div className="mx-auto max-w-6xl">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <a href="/" className="text-sm font-bold text-indigo-700">← Back to Growth command center</a>
          <p className="mt-6 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Merchant · Offer governance</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Merchant offers</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">Create an offer packet, submit it for a second-person review, and record explicit evidence checks before internal activation. Saving URLs is not independent verification and does not connect the offer to an affiliate network.</p>
        </div>
        <button onClick={()=>void load()} disabled={!!busy} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">Refresh offers</button>
      </header>

      {error&&<div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
      {notice&&<div role="status" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}

      <section className="mt-7 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <article className="rounded-2xl border border-white bg-white p-4 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Offer packets</p><p className="mt-2 text-3xl font-black">{offers.length}</p></article>
        <article className="rounded-2xl border border-white bg-white p-4 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Awaiting review</p><p className="mt-2 text-3xl font-black">{offers.filter(x=>x.status==="submitted_for_review").length}</p></article>
        <article className="rounded-2xl border border-white bg-white p-4 shadow-sm"><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Internally approved</p><p className="mt-2 text-3xl font-black">{offers.filter(x=>x.status==="approved"&&x.activation_allowed).length}</p></article>
      </section>

      <section className="mt-7 rounded-3xl border border-white bg-white p-5 shadow-sm sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-black">New merchant offer packet</h2><p className="mt-1 text-sm text-slate-500">All fields describe operator-supplied evidence; no product page is fetched automatically.</p></div><span className="rounded-full bg-amber-50 px-3 py-2 text-xs font-bold text-amber-800">Draft only · no external listing</span></div>
        <form onSubmit={create} className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div><label className={labelClass} htmlFor="merchant-name">Offer / product name</label><input id="merchant-name" className={inputClass} value={name} onChange={e=>setName(e.target.value)} minLength={2} maxLength={240} required/></div>
          <div><label className={labelClass} htmlFor="merchant-category">Category</label><input id="merchant-category" className={inputClass} value={category} onChange={e=>setCategory(e.target.value)} minLength={2} maxLength={160} required/></div>
          <div className="lg:col-span-2"><label className={labelClass} htmlFor="merchant-description">Product description</label><textarea id="merchant-description" className={inputClass} rows={3} value={description} onChange={e=>setDescription(e.target.value)} minLength={30} maxLength={6000} required/></div>
          <div><label className={labelClass} htmlFor="merchant-product-url">Product URL</label><input id="merchant-product-url" className={inputClass} type="url" value={productUrl} onChange={e=>setProductUrl(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="merchant-terms-version">Commission terms version/date</label><input id="merchant-terms-version" className={inputClass} value={termsVersion} onChange={e=>setTermsVersion(e.target.value)} minLength={1} maxLength={120} required/></div>
          <div><label className={labelClass} htmlFor="merchant-terms-url">Commission terms evidence URL</label><input id="merchant-terms-url" className={inputClass} type="url" value={termsUrl} onChange={e=>setTermsUrl(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="merchant-seller-url">Seller authorization evidence URL</label><input id="merchant-seller-url" className={inputClass} type="url" value={sellerUrl} onChange={e=>setSellerUrl(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="merchant-commission-type">Commission model</label><select id="merchant-commission-type" className={inputClass} value={commissionType} onChange={e=>setCommissionType(e.target.value)}><option value="percentage">Percentage</option><option value="fixed">Fixed</option><option value="recurring_percentage">Recurring percentage</option><option value="recurring_fixed">Recurring fixed</option><option value="cpa">CPA</option><option value="cpl">CPL</option></select></div>
          <div><label className={labelClass} htmlFor="merchant-commission-value">Commission amount / rate</label><input id="merchant-commission-value" className={inputClass} type="number" min="0.0001" max="99999999" step="0.0001" value={commissionValue} onChange={e=>setCommissionValue(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="merchant-currency">Currency (ISO 4217)</label><input id="merchant-currency" className={inputClass} value={currency} onChange={e=>setCurrency(e.target.value.toUpperCase())} minLength={3} maxLength={3} required/></div>
          <div><label className={labelClass} htmlFor="merchant-regions">Allowed regions (comma-separated)</label><input id="merchant-regions" className={inputClass} value={regions} onChange={e=>setRegions(e.target.value)} required/></div>
          <div><label className={labelClass} htmlFor="merchant-traffic">Restricted traffic sources (comma-separated)</label><input id="merchant-traffic" className={inputClass} value={trafficRestrictions} onChange={e=>setTrafficRestrictions(e.target.value)}/></div>
          <div className="lg:col-span-2"><label className={labelClass} htmlFor="merchant-disclosure">Required affiliate disclosure</label><textarea id="merchant-disclosure" className={inputClass} rows={2} value={disclosure} onChange={e=>setDisclosure(e.target.value)} minLength={12} maxLength={1200} required/></div>
          <div className="lg:col-span-2"><button disabled={!!busy} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white disabled:opacity-50">{busy==="create"?"Saving draft…":"Save offer draft"}</button></div>
        </form>
      </section>

      <section className="mt-7 rounded-3xl border border-white bg-white p-5 shadow-sm sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-black">Workspace offer packets</h2><p className="mt-1 text-sm text-slate-500">Review requires a different workspace owner/admin. Only an explicit evidence review enables internal activation.</p></div><span className="rounded-full bg-slate-100 px-3 py-2 text-xs font-bold text-slate-600">Affiliate network approval: not configured</span></div>
        <div className="mt-5 grid gap-4">
          {offers.length===0&&<p className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">No merchant offers in this workspace yet.</p>}
          {offers.map(offer=><article key={offer.id} className="rounded-2xl border border-slate-200 p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="text-base font-black">{offer.name}</h3><p className="mt-1 text-xs text-slate-500">{offer.category} · Created by {offer.created_by}</p><p className="mt-2 break-all text-sm text-indigo-700"><a href={offer.product_url} target="_blank" rel="noreferrer">{offer.product_url}</a></p></div><span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold">{offer.status.replaceAll("_"," ")}</span></div>
            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Commission</p><p className="mt-1 text-sm font-bold">{offer.commission_value} {offer.commission_currency} · {offer.commission_type}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Terms evidence</p><p className="mt-1 text-sm font-bold">{offer.terms_verified?"Human-verified":"Reference only"}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Internal activation</p><p className="mt-1 text-sm font-bold">{offer.activation_allowed?"Allowed":"Blocked"}</p></div></div>
            <p className="mt-3 text-xs leading-5 text-slate-500">Network status: {offer.affiliate_network_approval_status}. Internal review does not mean an affiliate network accepted the offer.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {offer.status==="draft"&&<button onClick={()=>void act("submit","/api/merchant/offers/"+encodeURIComponent(offer.id)+"/submit")} disabled={!!busy} className="rounded-xl bg-indigo-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-50">Submit for review</button>}
              {offer.status==="submitted_for_review"&&userEmail!==offer.created_by.toLowerCase()&&<><button onClick={()=>void review(offer,"approve")} disabled={!!busy} className="rounded-xl bg-emerald-700 px-3 py-2 text-sm font-bold text-white disabled:opacity-50">Approve with checked evidence</button><button onClick={()=>void review(offer,"reject")} disabled={!!busy} className="rounded-xl border border-rose-200 px-3 py-2 text-sm font-bold text-rose-700 disabled:opacity-50">Reject</button></>}
              {offer.status==="approved"&&userEmail!==offer.created_by.toLowerCase()&&<button onClick={()=>void review(offer,"suspend")} disabled={!!busy} className="rounded-xl border border-rose-200 px-3 py-2 text-sm font-bold text-rose-700 disabled:opacity-50">Suspend internal activation</button>}
            </div>
          </article>)}
        </div>
        {offers.some(x=>x.status==="submitted_for_review"&&x.created_by.toLowerCase()!==userEmail)&&<div className="mt-5 rounded-2xl border border-amber-100 bg-amber-50/70 p-4"><p className="text-sm font-bold text-amber-900">Reviewer evidence checklist</p><label className="mt-3 flex items-start gap-2 text-sm text-amber-950"><input type="checkbox" checked={sellerVerified} onChange={e=>setSellerVerified(e.target.checked)} className="mt-1"/><span>I inspected the seller authorization reference and verified the offer creator can represent this merchant.</span></label><label className="mt-3 flex items-start gap-2 text-sm text-amber-950"><input type="checkbox" checked={termsVerified} onChange={e=>setTermsVerified(e.target.checked)} className="mt-1"/><span>I inspected the cited terms and verified commission model, amount, currency, allowed regions and traffic restrictions.</span></label><label className={labelClass+" mt-3"} htmlFor="merchant-review-notes">Review notes</label><textarea id="merchant-review-notes" className={inputClass} rows={2} value={reviewNotes} onChange={e=>setReviewNotes(e.target.value)} maxLength={3000}/><p className="mt-2 text-xs leading-5 text-amber-900">These are human attestations, not automated URL validation. The server denies approval unless both are true and prevents self-review.</p></div>}
      </section>
    </div>
  </main>;
}

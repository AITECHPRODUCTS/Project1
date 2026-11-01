"use client";

import {useCallback,useEffect,useState} from "react";
import {apiFetch} from "@/lib/api";

type Offer={id:string;name:string;status:string;commission_currency:string};
type Integration={
  id:string;merchant_offer_id:string;offer_name:string|null;provider_name:string;display_name:string;
  integration_type:string;status:string;webhook_url:string;secret_fingerprint:string;
  last_event_at:string|null;last_error_code:string|null;created_at:string|null;
};
type IntegrationCreated=Integration&{signing_secret_once:string;secret_display_policy:string};

const inputClass="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm";
const buttonClass="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-bold text-slate-700";
const statusLabel=(value:string)=>value.replaceAll("_"," ");

export default function MerchantIntegrationsPage(){
  const [offers,setOffers]=useState<Offer[]>([]);
  const [integrations,setIntegrations]=useState<Integration[]>([]);
  const [offerId,setOfferId]=useState("");
  const [providerName,setProviderName]=useState("custom");
  const [displayName,setDisplayName]=useState("Custom checkout webhook");
  const [oneTimeSecret,setOneTimeSecret]=useState("");
  const [selectedIntegration,setSelectedIntegration]=useState<IntegrationCreated|null>(null);
  const [busy,setBusy]=useState("");
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");

  const load=useCallback(async()=>{
    setError("");
    try{
      const [offerResponse,integrationResponse]=await Promise.all([
        apiFetch<{count:number;data:Offer[]}>("/api/merchant/offers?limit=300"),
        apiFetch<{count:number;data:Integration[]}>("/api/merchant/integrations")
      ]);
      setOffers(offerResponse.data||[]);
      setIntegrations(integrationResponse.data||[]);
    }catch(exc){setError(exc instanceof Error?exc.message:"Could not load merchant integrations. Sign in as a merchant workspace owner/admin.");}
  },[]);
  useEffect(()=>{void load();},[load]);

  const create=async()=>{
    if(!offerId){setError("Choose the merchant offer that will receive signed checkout events.");return;}
    setBusy("create");setError("");setNotice("");setOneTimeSecret("");setSelectedIntegration(null);
    try{
      const result=await apiFetch<IntegrationCreated>("/api/merchant/offers/"+encodeURIComponent(offerId)+"/webhook-integration",{
        method:"POST",body:JSON.stringify({provider_name:providerName,display_name:displayName})
      });
      setSelectedIntegration(result);
      setOneTimeSecret(result.signing_secret_once);
      setNotice("Webhook endpoint created. Save the signing secret now; it will not be displayed again.");
      await load();
    }catch(exc){setError(exc instanceof Error?exc.message:"Could not create the merchant webhook integration.");}
    finally{setBusy("");}
  };

  const rotate=async(item:Integration)=>{
    setBusy(item.id);setError("");setNotice("");setOneTimeSecret("");setSelectedIntegration(null);
    try{
      const result=await apiFetch<IntegrationCreated>("/api/merchant/integrations/"+encodeURIComponent(item.id)+"/rotate-secret",{method:"POST"});
      setSelectedIntegration(result);setOneTimeSecret(result.signing_secret_once);
      setNotice("Signing secret rotated. The previous secret is invalid immediately; update your checkout webhook configuration.");
      await load();
    }catch(exc){setError(exc instanceof Error?exc.message:"Could not rotate the integration secret.");}
    finally{setBusy("");}
  };

  const disable=async(item:Integration)=>{
    setBusy(item.id);setError("");setNotice("");setOneTimeSecret("");setSelectedIntegration(null);
    try{
      await apiFetch<Integration>("/api/merchant/integrations/"+encodeURIComponent(item.id)+"/disable",{method:"POST"});
      setNotice("Webhook integration disabled. New events from this endpoint will be rejected.");
      await load();
    }catch(exc){setError(exc instanceof Error?exc.message:"Could not disable the integration.");}
    finally{setBusy("");}
  };

  return <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10">
    <div className="mx-auto max-w-5xl">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div><a href="/merchant" className="text-sm font-bold text-indigo-700">← Merchant dashboard</a><p className="mt-6 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Merchant · Business integrations</p><h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Checkout & conversion integrations</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">Connect a supported checkout system through a merchant-specific signed webhook. The first validated event confirms inbound write access for that program.</p></div>
        <a href="/merchant/offers" className={buttonClass}>Manage programs</a>
      </header>
      {error&&<p role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
      {notice&&<p role="status" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</p>}
      <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <h2 className="text-xl font-black">Create a signed webhook connection</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">This connector receives order, subscription renewal, refund and chargeback events. It does not yet import product catalogues or authenticate to a merchant platform management API.</p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div><label htmlFor="merchant-webhook-offer" className="block text-sm font-bold">Merchant program</label><select id="merchant-webhook-offer" className={inputClass} value={offerId} onChange={e=>setOfferId(e.target.value)}><option value="">Choose a program</option>{offers.map(offer=><option key={offer.id} value={offer.id}>{offer.name} · {offer.commission_currency} · {statusLabel(offer.status)}</option>)}</select></div>
          <div><label htmlFor="merchant-provider-name" className="block text-sm font-bold">Event source type</label><select id="merchant-provider-name" className={inputClass} value={providerName} onChange={e=>setProviderName(e.target.value)}><option value="custom">Custom checkout</option><option value="stripe">Stripe-signed webhook</option><option value="shopify">Shopify-signed webhook</option><option value="woocommerce">WooCommerce event relay</option><option value="other">Other event source</option></select></div>
          <div className="sm:col-span-2"><label htmlFor="merchant-webhook-name" className="block text-sm font-bold">Connection name</label><input id="merchant-webhook-name" className={inputClass} value={displayName} onChange={e=>setDisplayName(e.target.value)} minLength={2} maxLength={160}/></div>
        </div>
        <button type="button" onClick={()=>void create()} disabled={!!busy||!offers.length} className="mt-5 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white disabled:opacity-50">{busy==="create"?"Creating…":"Create webhook endpoint"}</button>
      </section>

      {selectedIntegration&&oneTimeSecret&&<section className="mt-7 rounded-3xl border border-amber-200 bg-amber-50 p-5 sm:p-7" aria-label="One-time webhook secret">
        <h2 className="text-lg font-black text-amber-950">Save this signing secret now</h2>
        <p className="mt-2 text-sm leading-6 text-amber-900">It is returned only once. Store it in your checkout/server environment as a secret. Never place it in browser JavaScript or send it to affiliates.</p>
        <div className="mt-4 break-all rounded-xl border border-amber-200 bg-white p-3 font-mono text-sm">{oneTimeSecret}</div>
        <button type="button" onClick={()=>void navigator.clipboard?.writeText(oneTimeSecret)} className="mt-3 rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-bold text-amber-950">Copy secret</button>
        <p className="mt-4 text-xs font-bold text-amber-950">Webhook endpoint</p><p className="mt-1 break-all text-sm text-amber-950">{selectedIntegration.webhook_url}</p>
        <button type="button" onClick={()=>{setOneTimeSecret("");setSelectedIntegration(null);}} className="mt-4 rounded-lg bg-amber-900 px-3 py-2 text-xs font-bold text-white">I saved it — hide secret</button>
      </section>}

      <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <h2 className="text-xl font-black">Webhook event contract</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">The publisher tracking URL appends a subid to your product URL. Save that value with the order or subscription and return it as click_id or subid. Sign the exact raw JSON request body using HMAC-SHA256 and send the hex digest in the X-Omni-Signature header with a sha256= prefix.</p>
        <div className="mt-4 rounded-xl bg-slate-950 p-4 text-sm leading-6 text-slate-100">Required sale fields: event_id, event_type=sale, click_id, revenue, currency.</div>
        <div className="mt-3 rounded-xl bg-slate-950 p-4 text-sm leading-6 text-slate-100">Refund/chargeback fields: event_id, event_type, original_event_id, currency.</div>
        <p className="mt-3 text-xs leading-5 text-slate-500">Allowed events: sale, subscription_renewal (recurring programs only), refund and chargeback. This first version supports full reversals, not partial refunds. Commissions are pending observations and are not marked paid. Provider name identifies the event source; native OAuth/API catalogue sync is not included in this webhook.</p>
      </section>

      <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-black">Connected webhook endpoints</h2><p className="mt-1 text-sm text-slate-500">{integrations.length} integration(s) in this merchant workspace.</p></div><button type="button" className={buttonClass} onClick={()=>void load()} disabled={!!busy}>Refresh</button></div>
        <div className="mt-4 grid gap-3">
          {integrations.length===0&&<p className="rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-500">No merchant webhook integrations have been created.</p>}
          {integrations.map(item=><article key={item.id} className="rounded-2xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-bold">{item.display_name}</h3><p className="mt-1 text-sm text-slate-600">{item.offer_name||item.merchant_offer_id} · {item.provider_name}</p><p className="mt-1 break-all text-xs text-slate-500">{item.webhook_url}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{statusLabel(item.status)}</span></div>
            <p className="mt-2 text-xs text-slate-500">Last accepted event: {item.last_event_at?new Date(item.last_event_at).toLocaleString():"No accepted event yet"} · Secret fingerprint: {item.secret_fingerprint.slice(0,12)}…</p>
            {item.last_error_code&&<p className="mt-2 text-xs text-rose-700">Last error: {item.last_error_code}</p>}
            <div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={()=>void rotate(item)} disabled={!!busy||item.status==="disabled"} className={buttonClass}>Rotate signing secret</button><button type="button" onClick={()=>void disable(item)} disabled={!!busy||item.status==="disabled"} className="rounded-xl border border-rose-200 bg-white px-3 py-2.5 text-sm font-bold text-rose-700">Disable endpoint</button></div>
          </article>)}
        </div>
      </section>
      <p className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">Integration state reflects accepted signed events only. This is an event receiver, not a direct OAuth/API integration or product catalogue sync; native provider adapters will be built separately.</p>
    </div>
  </main>;
}

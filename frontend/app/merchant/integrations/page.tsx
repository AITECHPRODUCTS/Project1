"use client";

import {useCallback,useEffect,useState} from "react";
import {apiFetch} from "@/lib/api";

type Offer={id:string;name:string;status:string;commission_currency:string};
type Integration={
  id:string;merchant_offer_id:string;offer_name:string|null;provider_name:string;display_name:string;
  integration_type:string;status:string;webhook_url:string;secret_fingerprint:string;
  signing_secret_configured:boolean;
  last_event_at:string|null;last_error_code:string|null;created_at:string|null;
};
type IntegrationCreated=Integration&{signing_secret_once:string;secret_display_policy:string};
type ManualReviewEvent={id:string;provider_event_id:string;outcome:string;received_at:string|null;conversion_id:string|null};

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
  const [stripeOfferId,setStripeOfferId]=useState("");
  const [stripeIntegrationId,setStripeIntegrationId]=useState("");
  const [stripeSigningSecret,setStripeSigningSecret]=useState("");
  const [manualReviewByIntegration,setManualReviewByIntegration]=useState<Record<string,ManualReviewEvent[]>>({});
  const [manualReviewBusy,setManualReviewBusy]=useState("");

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

  const createStripe=async()=>{
    if(!stripeOfferId){setError("Choose the merchant program for this Stripe endpoint.");return;}
    setBusy("stripe-create");setError("");setNotice("");setOneTimeSecret("");setSelectedIntegration(null);
    try{
      const result=await apiFetch<Integration>("/api/merchant/offers/"+encodeURIComponent(stripeOfferId)+"/stripe-integration",{
        method:"POST",body:JSON.stringify({display_name:"Stripe checkout webhooks"})
      });
      setStripeIntegrationId(result.id);
      setNotice("Stripe endpoint created. Add its URL to Stripe Workbench/Webhooks, select the supported events, then configure the endpoint signing secret here.");
      await load();
    }catch(exc){setError(exc instanceof Error?exc.message:"Could not create the native Stripe webhook endpoint.");}
    finally{setBusy("");}
  };

  const configureStripe=async()=>{
    if(!stripeIntegrationId){setError("Choose a Stripe endpoint before saving its signing secret.");return;}
    if(!stripeSigningSecret.trim()){setError("Enter the Stripe endpoint signing secret (whsec_...).");return;}
    setBusy("stripe-configure");setError("");setNotice("");
    try{
      await apiFetch<Integration>("/api/merchant/integrations/"+encodeURIComponent(stripeIntegrationId)+"/stripe-secret",{
        method:"POST",body:JSON.stringify({webhook_signing_secret:stripeSigningSecret.trim()})
      });
      setStripeSigningSecret("");
      setNotice("Stripe endpoint signing secret encrypted and saved. Send a Stripe test event to verify the endpoint.");
      await load();
    }catch(exc){setError(exc instanceof Error?exc.message:"Could not save the Stripe endpoint signing secret.");}
    finally{setBusy("");}
  };

  const loadManualReview=async(item:Integration)=>{
    setManualReviewBusy(item.id);setError("");
    try{
      const result=await apiFetch<{count:number;data:ManualReviewEvent[]}>(
        "/api/merchant/integrations/"+encodeURIComponent(item.id)+"/manual-review-events"
      );
      setManualReviewByIntegration(previous=>({...previous,[item.id]:result.data||[]}));
    }catch(exc){setError(exc instanceof Error?exc.message:"Could not load merchant event review records.");}
    finally{setManualReviewBusy("");}
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
        <p className="mt-2 text-sm leading-6 text-slate-600">Custom relays accept normalized sale, renewal, refund and chargeback events. The WooCommerce option receives signed order webhooks and maps paid orders plus verified full refunds; it does not import products or authenticate to the WooCommerce REST API.</p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div><label htmlFor="merchant-webhook-offer" className="block text-sm font-bold">Merchant program</label><select id="merchant-webhook-offer" className={inputClass} value={offerId} onChange={e=>setOfferId(e.target.value)}><option value="">Choose a program</option>{offers.map(offer=><option key={offer.id} value={offer.id}>{offer.name} · {offer.commission_currency} · {statusLabel(offer.status)}</option>)}</select></div>
          <div><label htmlFor="merchant-provider-name" className="block text-sm font-bold">Event source type</label><select id="merchant-provider-name" className={inputClass} value={providerName} onChange={e=>setProviderName(e.target.value)}><option value="custom">Custom checkout</option><option value="woocommerce">WooCommerce store</option><option value="other">Other normalized event source</option></select></div>
          <div className="sm:col-span-2"><label htmlFor="merchant-webhook-name" className="block text-sm font-bold">Connection name</label><input id="merchant-webhook-name" className={inputClass} value={displayName} onChange={e=>setDisplayName(e.target.value)} minLength={2} maxLength={160}/></div>
        </div>
        <button type="button" onClick={()=>void create()} disabled={!!busy||!offers.length} className="mt-5 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white disabled:opacity-50">{busy==="create"?"Creating…":"Create webhook endpoint"}</button>
      </section>

      <section className="mt-7 rounded-3xl border border-indigo-200 bg-indigo-50/40 p-5 shadow-sm sm:p-7" aria-label="Native Stripe integration">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><p className="text-xs font-black uppercase tracking-wider text-indigo-700">Native merchant adapter</p><h2 className="mt-1 text-xl font-black">Connect Stripe webhooks</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">This integration verifies Stripe's own timestamped webhook signatures and normalizes checkout events into the merchant conversion ledger. It does not create Stripe Checkout sessions or synchronize products.</p></div>
          <a href="https://dashboard.stripe.com/webhooks" target="_blank" rel="noopener noreferrer" className={buttonClass}>Open Stripe Webhooks</a>
        </div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div><label htmlFor="stripe-merchant-offer" className="block text-sm font-bold">Merchant program</label><select id="stripe-merchant-offer" className={inputClass} value={stripeOfferId} onChange={e=>setStripeOfferId(e.target.value)}><option value="">Choose a program</option>{offers.map(offer=><option key={offer.id} value={offer.id}>{offer.name} · {offer.commission_currency} · {statusLabel(offer.status)}</option>)}</select></div>
          <div className="flex items-end"><button type="button" onClick={()=>void createStripe()} disabled={!!busy||!offers.length} className="w-full rounded-xl bg-indigo-700 px-5 py-3 text-sm font-bold text-white disabled:opacity-50">{busy==="stripe-create"?"Creating…":"Create native Stripe endpoint"}</button></div>
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-600">An offer can have one event endpoint. Disable an existing custom relay for this offer before switching it to native Stripe; historical conversion records remain intact.</p>
        <ol className="mt-5 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-700">
          <li>Create the endpoint here and copy its webhook URL from the connected endpoints list below.</li>
          <li>In Stripe Workbench, add that URL and subscribe to <code>payment_intent.succeeded</code>, <code>invoice.paid</code>, <code>charge.refunded</code> and <code>charge.dispute.created</code>.</li>
          <li>Copy the endpoint's <code>whsec_...</code> signing secret and save it below. It is encrypted and never displayed again.</li>
          <li>Attach the OmniAffiliateOS affiliate click reference as <code>omni_click_id</code> metadata to the PaymentIntent or initial subscription invoice. For subscription renewals, also store the initial PaymentIntent as <code>omni_original_payment_intent_id</code> on each renewal invoice (or preserve the click metadata).</li>
          <li>Send a Stripe test event and confirm that the endpoint status changes after a supported signed conversion is accepted.</li>
        </ol>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <div><label htmlFor="stripe-endpoint-select" className="block text-sm font-bold">Stripe endpoint to configure</label><select id="stripe-endpoint-select" className={inputClass} value={stripeIntegrationId} onChange={e=>setStripeIntegrationId(e.target.value)}><option value="">Choose a Stripe endpoint</option>{integrations.filter(item=>item.integration_type==="stripe_webhook"&&item.status!=="disabled").map(item=><option key={item.id} value={item.id}>{item.offer_name||item.merchant_offer_id} · {item.signing_secret_configured?"secret saved":"secret required"}</option>)}</select></div>
          <div><label htmlFor="stripe-endpoint-secret" className="block text-sm font-bold">Stripe endpoint signing secret</label><input id="stripe-endpoint-secret" type="password" autoComplete="off" className={inputClass} value={stripeSigningSecret} onChange={e=>setStripeSigningSecret(e.target.value)} placeholder="whsec_..." /></div>
        </div>
        <button type="button" onClick={()=>void configureStripe()} disabled={!!busy||!stripeIntegrationId||!stripeSigningSecret.trim()} className="mt-4 rounded-xl bg-indigo-700 px-5 py-3 text-sm font-bold text-white disabled:opacity-50">{busy==="stripe-configure"?"Saving securely…":"Save Stripe signing secret"}</button>
        <p className="mt-3 text-xs leading-5 text-slate-500">Do not paste Stripe secret API keys (sk_...) here. Only the specific webhook endpoint signing secret (whsec_...) is accepted. Secret values are not logged or returned by the API.</p>
      </section>

      {selectedIntegration&&oneTimeSecret&&<section className="mt-7 rounded-3xl border border-amber-200 bg-amber-50 p-5 sm:p-7" aria-label="One-time webhook secret">
        <h2 className="text-lg font-black text-amber-950">Save this signing secret now</h2>
        <p className="mt-2 text-sm leading-6 text-amber-900">{selectedIntegration.integration_type==="woocommerce_webhook"?"Copy this into both WooCommerce order webhook configurations now; it is not shown again.":"It is returned only once. Store it in your checkout/server environment as a secret. Never place it in browser JavaScript or send it to affiliates."}</p>
        <div className="mt-4 break-all rounded-xl border border-amber-200 bg-white p-3 font-mono text-sm">{oneTimeSecret}</div>
        <button type="button" onClick={()=>void navigator.clipboard?.writeText(oneTimeSecret)} className="mt-3 rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-bold text-amber-950">Copy secret</button>
        <p className="mt-4 text-xs font-bold text-amber-950">Webhook endpoint</p><p className="mt-1 break-all text-sm text-amber-950">{selectedIntegration.webhook_url}</p>
        {selectedIntegration.integration_type==="woocommerce_webhook"&&<div className="mt-4 rounded-xl border border-amber-200 bg-white p-4 text-sm leading-6 text-amber-950"><p className="font-bold">WooCommerce setup</p><ol className="mt-2 list-decimal space-y-1 pl-5"><li>Open WooCommerce → Settings → Advanced → Webhooks.</li><li>Create active webhooks for <code>Order created</code> and <code>Order updated</code>.</li><li>Use the endpoint URL above and paste the one-time secret into each webhook Secret field.</li><li>Persist the affiliate click ID as order-level <code>omni_click_id</code> metadata. For renewal orders, also persist <code>omni_original_order_id</code>.</li><li>Send a test paid order before relying on live attribution.</li></ol></div>}
        <button type="button" onClick={()=>{setOneTimeSecret("");setSelectedIntegration(null);}} className="mt-4 rounded-lg bg-amber-900 px-3 py-2 text-xs font-bold text-white">I saved it — hide secret</button>
      </section>}

      <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <h2 className="text-xl font-black">Webhook event contract</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">The publisher tracking URL appends a click reference to the destination. Store it as order-level metadata. Custom relays sign the exact raw JSON body with HMAC-SHA256 and send a hex digest in X-Omni-Signature; WooCommerce uses its native Base64 X-WC-Webhook-Signature header.</p>
        <div className="mt-4 rounded-xl bg-slate-950 p-4 text-sm leading-6 text-slate-100">Required sale fields: event_id, event_type=sale, click_id, revenue, currency.</div>
        <div className="mt-3 rounded-xl bg-slate-950 p-4 text-sm leading-6 text-slate-100">Refund/chargeback fields: event_id, event_type, original_event_id, currency.</div>
        <p className="mt-3 text-xs leading-5 text-slate-500">Custom relays accept normalized sale, subscription_renewal, refund and chargeback events. Native Stripe accepts successful PaymentIntents, paid subscription invoices and full refunds. WooCommerce accepts paid processing/completed orders, explicitly linked renewal orders and exact full-order refunds. Partial/inconsistent refunds require manual review. Commissions remain pending observations and are not marked paid. Neither native adapter creates checkout sessions, manages store products or imports catalogues.</p>
      </section>

      <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-black">Connected webhook endpoints</h2><p className="mt-1 text-sm text-slate-500">{integrations.length} integration(s) in this merchant workspace.</p></div><button type="button" className={buttonClass} onClick={()=>void load()} disabled={!!busy}>Refresh</button></div>
        <div className="mt-4 grid gap-3">
          {integrations.length===0&&<p className="rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-500">No merchant webhook integrations have been created.</p>}
          {integrations.map(item=><article key={item.id} className="rounded-2xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-bold">{item.display_name}</h3><p className="mt-1 text-sm text-slate-600">{item.offer_name||item.merchant_offer_id} · {item.provider_name}</p><p className="mt-1 break-all text-xs text-slate-500">{item.webhook_url}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{statusLabel(item.status)}</span></div>
            <p className="mt-2 text-xs text-slate-500">Last accepted event: {item.last_event_at?new Date(item.last_event_at).toLocaleString():"No accepted event yet"} · Secret fingerprint: {item.secret_fingerprint.slice(0,12)}…</p>
            {item.last_error_code&&item.last_error_code!=="stripe_secret_not_configured"&&<p className="mt-2 text-xs text-rose-700">Last error: {item.last_error_code}</p>}{item.integration_type==="stripe_webhook"&&!item.signing_secret_configured&&<p className="mt-2 text-xs text-amber-700">Stripe endpoint signing secret has not been configured yet.</p>}
            {item.integration_type==="stripe_webhook"&&<div className="mt-3 space-y-3">
              <button type="button" onClick={()=>void loadManualReview(item)} disabled={manualReviewBusy===item.id} className={buttonClass}>{manualReviewBusy===item.id?"Loading review records…":"View manual-review events"}</button>
              {manualReviewByIntegration[item.id]&&<div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                <p className="text-sm font-bold text-amber-950">Manual-review receipts · {manualReviewByIntegration[item.id].length}</p>
                {manualReviewByIntegration[item.id].length===0?<p className="mt-2 text-xs text-amber-900">No events currently require manual review.</p>:<ul className="mt-2 space-y-2">{manualReviewByIntegration[item.id].map(row=><li key={row.id} className="border-t border-amber-200 pt-2 text-xs text-amber-950"><span className="font-bold">{statusLabel(row.outcome)}</span><span className="ml-2 break-all font-mono">{row.provider_event_id}</span><p className="mt-1 text-amber-800">{row.received_at?new Date(row.received_at).toLocaleString():"Received time unavailable"}</p></li>)}</ul>}
              </div>}
            </div>}
            <div className="mt-3 flex flex-wrap gap-2">{item.integration_type==="stripe_webhook"?<span className="rounded-xl border border-indigo-100 bg-indigo-50 px-3 py-2.5 text-xs font-bold text-indigo-800">Configure from Stripe Dashboard above</span>:<button type="button" onClick={()=>void rotate(item)} disabled={!!busy||item.status==="disabled"} className={buttonClass}>Rotate signing secret</button>}<button type="button" onClick={()=>void disable(item)} disabled={!!busy||item.status==="disabled"} className="rounded-xl border border-rose-200 bg-white px-3 py-2.5 text-sm font-bold text-rose-700">Disable endpoint</button></div>
          </article>)}
        </div>
      </section>
      <p className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">Custom connections use the OmniAffiliateOS HMAC event relay. Stripe uses native Stripe-Signature verification. Neither connection manages checkout settings, creates Stripe charges or synchronizes merchant product catalogues.</p>
    </div>
  </main>;
}

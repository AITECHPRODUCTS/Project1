"use client";
import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type Connection={id:string;provider_id:string;status:"connected_read_only"|"degraded"|"disconnected";account_nicknames:string[];capabilities:string[];permissions_verified:string[];credential_present:boolean;last_checked_at:string|null;last_error_code:string|null;created_at:string|null};
type ConnectionList={data:Connection[]};
type FlipkartProduct={external_id:string;title:string;description:string;brand:string|null;category:string|null;product_url:string|null;image_url:string|null;price_amount:string|null;mrp_amount:string|null;currency:string|null;in_stock:boolean|null;discount_percentage:string|null};
type FlipkartProductSearchReport={provider_id:string;evidence_type:string;source_endpoint?:string;query?:string;requested_count?:number;result_count:number;persisted_count?:number;count?:number;limit?:number;offset?:number;has_more?:boolean;source_checked_at:string|null;commission_terms_status:string;note:string;products:FlipkartProduct[]};
type FlipkartOffer={external_id:string;title:string;description:string;category:string|null;offer_url:string;image_url:string|null;availability_status:string|null;is_available:boolean|null;start_at:string|null;end_at:string|null};
type FlipkartOfferReport={provider_id:string;evidence_type:string;source_endpoint?:string;offer_kind?:string;result_count:number;persisted_count?:number;count?:number;limit?:number;offset?:number;has_more?:boolean;source_checked_at:string|null;commission_terms_status:string;note:string;offers:FlipkartOffer[]};
type ProviderOrderTransaction={
  event_key:string;source_fingerprint:string;receipt:string;transaction_time:string;
  transaction_type:string;role:"AFFILIATE";account_nickname:string;vendor_nickname:string|null;
  affiliate_nickname:string|null;currency:string|null;item_number:string|null;line_item_type:string|null;
  product_title:string|null;account_amount:string|null;customer_amount:string|null;
  line_item_status:string|null;recurring:boolean|null;shippable:boolean|null;
  evidence_status:"provider_reported_unreconciled";click_id:string|null;attribution_status:"not_matched"|"matched_clickbank_tid";
};
type OrderImportReport={
  provider_id:string;evidence_type:string;financial_semantics:string;pii_stored:boolean;
  period:{start_date:string;end_date:string};account:string;pages_retrieved:number;
  source_order_count:number;skipped_unidentified_count:number;skipped_scope_count:number;
  imported_count:number;duplicate_count:number;matched_click_count:number;unmatched_tracking_id_count:number;has_more:boolean;next_page:number|null;
  transactions:ProviderOrderTransaction[];note:string;
};
type OrderCountReport={
 provider_id:string;evidence_type:string;metric_scope:string;
 period:{start_date:string;end_date:string};account:string;
 counts:{sales:number;refunds:number;chargebacks:number};
 transaction_types:Record<string,number>;
};
type QuickstatsReport={
 provider_id:string;evidence_type:string;metric_scope:string;
 period:{start_date:string;end_date:string};accounts:string[];
 daily:Array<{account:string;date:string;sales:string|null;refunds:string|null;chargebacks:string|null}>;
 totals:{sales:string|null;refunds:string|null;chargebacks:string|null};
};

function formatObservedAt(value:string|null):string {
 if(value===null||value.length===0) return "Not captured";
 return new Date(value).toLocaleString();
}

export default function IntegrationsPage(){
 const [connections,setConnections]=useState<Connection[]>([]);
 const [apiKey,setApiKey]=useState("");
 const [flipkartTrackingId,setFlipkartTrackingId]=useState("");
 const [flipkartToken,setFlipkartToken]=useState("");
 const [flipkartSearchText,setFlipkartSearchText]=useState("mobile phone");
 const [flipkartProducts,setFlipkartProducts]=useState<Record<string,FlipkartProductSearchReport>>({});
 const [flipkartOffers,setFlipkartOffers]=useState<Record<string,FlipkartOfferReport>>({});
 const [loading,setLoading]=useState(true);
 const [busy,setBusy]=useState("");
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [quickstats,setQuickstats]=useState<Record<string,QuickstatsReport>>({});
 const [orderCounts,setOrderCounts]=useState<Record<string,OrderCountReport>>({});
 const [orderImports,setOrderImports]=useState<Record<string,OrderImportReport>>({});
 const load=useCallback(async()=>{setLoading(true);setError("");try{const result=await apiFetch<ConnectionList>("/api/provider-connections");setConnections(result.data||[]);}catch(exc){setError(exc instanceof Error?exc.message:"Unable to load provider connections.");}finally{setLoading(false);}},[]);
 useEffect(()=>{void load();},[load]);
 const connect=async(event:FormEvent<HTMLFormElement>)=>{event.preventDefault();const submittedKey=apiKey;setApiKey("");setBusy("connect");setError("");setNotice("");try{const row=await apiFetch<Connection>("/api/provider-connections/clickbank",{method:"POST",body:JSON.stringify({api_key:submittedKey})});setConnections(current=>[row,...current.filter(item=>item.id!==row.id)]);setNotice("ClickBank account access verified. The credential was encrypted and stored for this workspace.");}catch(exc){setError(exc instanceof Error?exc.message:"ClickBank connection could not be verified.");}finally{setApiKey("");setBusy("");}};
 const connectFlipkart=async(event:FormEvent<HTMLFormElement>)=>{
  event.preventDefault();
  const submittedToken=flipkartToken;
  const submittedTrackingId=flipkartTrackingId;
  setFlipkartToken("");
  setBusy("flipkart-connect");setError("");setNotice("");
  try{
   const row=await apiFetch<Connection & {categories?:string[]}>("/api/provider-connections/flipkart",{
    method:"POST",body:JSON.stringify({tracking_id:submittedTrackingId,api_token:submittedToken})
   });
   setConnections(current=>[row,...current.filter(item=>item.id!==row.id)]);
   setFlipkartTrackingId("");
   setNotice("Flipkart affiliate account was verified with its product-feed directory. Read-only search and offers access is connected.");
  }catch(exc){setError(exc instanceof Error?exc.message:"Flipkart account verification failed.");}
  finally{setFlipkartToken("");setBusy("");}
 };
 const test=async(id:string,provider="clickbank")=>{
  setBusy(id);setError("");setNotice("");
  try{
   const endpoint=provider==="flipkart"?"/api/provider-connections/"+id+"/flipkart/test":"/api/provider-connections/"+id+"/test";
   const row=await apiFetch<Connection>(endpoint,{method:"POST"});
   setConnections(current=>current.map(item=>item.id===id?row:item));
   setNotice(provider==="flipkart"?"Flipkart affiliate API directory verification passed.":"ClickBank read-only account verification passed.");
  }catch(exc){setError(exc instanceof Error?exc.message:"Provider verification failed.");await load();}
  finally{setBusy("");}
 };
 const searchFlipkartProducts=async(id:string)=>{
  const query=flipkartSearchText.trim();
  if(query.length<2){setError("Enter at least two characters to search Flipkart products.");return;}
  setBusy(id+":flipkart-search");setError("");setNotice("");
  try{
   const report=await apiFetch<FlipkartProductSearchReport>("/api/provider-connections/"+id+"/flipkart/products/search",{
    method:"POST",body:JSON.stringify({query,result_count:10})
   });
   setFlipkartProducts(current=>({...current,[id]:report}));
   setNotice("Flipkart returned provider-reported product results. Commission and cookie terms remain unknown until verified separately.");
  }catch(exc){setError(exc instanceof Error?exc.message:"Flipkart product search failed.");}
  finally{setBusy("");}
 };
 const loadSavedFlipkartProducts=async(id:string)=>{
  setBusy(id+":flipkart-saved-products");setError("");setNotice("");
  try{
   const report=await apiFetch<FlipkartProductSearchReport>("/api/provider-connections/"+id+"/flipkart/catalog?kind=product&limit=100&offset=0");
   setFlipkartProducts(current=>({...current,[id]:report}));
   setNotice("Saved Flipkart product observations loaded from this workspace. Their original provider capture times are preserved.");
  }catch(exc){setError(exc instanceof Error?exc.message:"Saved Flipkart products could not be loaded.");}
  finally{setBusy("");}
 };
 const loadSavedFlipkartOffers=async(id:string)=>{
  setBusy(id+":flipkart-saved-offers");setError("");setNotice("");
  try{
   const report=await apiFetch<FlipkartOfferReport>("/api/provider-connections/"+id+"/flipkart/catalog?kind=offer&limit=100&offset=0");
   setFlipkartOffers(current=>({...current,[id]:report}));
   setNotice("Saved Flipkart offer observations loaded from this workspace.");
  }catch(exc){setError(exc instanceof Error?exc.message:"Saved Flipkart offers could not be loaded.");}
  finally{setBusy("");}
 };
 const loadFlipkartOffers=async(id:string)=>{
  setBusy(id+":flipkart-offers");setError("");setNotice("");
  try{
   const report=await apiFetch<FlipkartOfferReport>("/api/provider-connections/"+id+"/flipkart/offers?kind=all");
   setFlipkartOffers(current=>({...current,[id]:report}));
   setNotice("Flipkart active offers were retrieved and saved as provider-reported observations.");
  }catch(exc){setError(exc instanceof Error?exc.message:"Flipkart active-offer retrieval failed.");}
  finally{setBusy("");}
 };
 const loadQuickstats=async(id:string,account:string)=>{
  setBusy(id+":"+account);setError("");setNotice("");
  const now=new Date();
  const dateText=(value:Date)=>`${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,"0")}-${String(value.getDate()).padStart(2,"0")}`;
  const endDate=dateText(now);
  const startDate=dateText(new Date(now.getFullYear(),now.getMonth(),now.getDate()-29));
  try{
   const query=new URLSearchParams({start_date:startDate,end_date:endDate,account});
   const report=await apiFetch<QuickstatsReport>(`/api/provider-connections/${id}/quickstats?${query.toString()}`);
   setQuickstats(current=>({...current,[id+":"+account]:report}));
  }catch(exc){setError(exc instanceof Error?exc.message:"Unable to retrieve ClickBank Quickstats.");}
  finally{setBusy("");}
 };
 const importOrders=async(id:string,account:string,startPage=1)=>{
  const key=id+":"+account;
  setBusy(key+":import");setError("");setNotice("");
  const now=new Date();
  const dateText=(value:Date)=>value.getFullYear()+"-"+String(value.getMonth()+1).padStart(2,"0")+"-"+String(value.getDate()).padStart(2,"0");
  const endDate=dateText(now);
  const startDate=dateText(new Date(now.getFullYear(),now.getMonth(),now.getDate()-29));
  try{
   const report=await apiFetch<OrderImportReport>("/api/provider-connections/"+id+"/orders/import",{
    method:"POST",
    body:JSON.stringify({account,start_date:startDate,end_date:endDate,start_page:startPage,max_pages:5})
   });
   setOrderImports(current=>{
    const previous=startPage===1?null:current[key];
    return {...current,[key]:{
     ...report,
     transactions:[...(previous?.transactions||[]),...report.transactions],
     imported_count:(previous?.imported_count||0)+report.imported_count,
     duplicate_count:(previous?.duplicate_count||0)+report.duplicate_count,
     matched_click_count:(previous?.matched_click_count||0)+report.matched_click_count,
     unmatched_tracking_id_count:(previous?.unmatched_tracking_id_count||0)+report.unmatched_tracking_id_count,
     pages_retrieved:(previous?.pages_retrieved||0)+report.pages_retrieved
    }};
   });
   setNotice("ClickBank order observations imported without customer contact data.");
  }catch(exc){setError(exc instanceof Error?exc.message:"Unable to import ClickBank order observations.");}
  finally{setBusy("");}
 };
 const loadOrderCounts=async(id:string,account:string)=>{
  setBusy(id+":orders:"+account);setError("");setNotice("");
  const now=new Date();
  const dateText=(value:Date)=>`${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,"0")}-${String(value.getDate()).padStart(2,"0")}`;
  const endDate=dateText(now);
  const startDate=dateText(new Date(now.getFullYear(),now.getMonth(),now.getDate()-29));
  try{
   const query=new URLSearchParams({start_date:startDate,end_date:endDate,account});
   const report=await apiFetch<OrderCountReport>(`/api/provider-connections/${id}/order-counts?${query.toString()}`);
   setOrderCounts(current=>({...current,[id+":"+account]:report}));
  }catch(exc){setError(exc instanceof Error?exc.message:"Unable to retrieve ClickBank affiliate order counts.");}
  finally{setBusy("");}
 };
 const disconnect=async(id:string)=>{
  const provider=connections.find(item=>item.id===id)?.provider_id;
  setBusy(id);setError("");setNotice("");
  try{
   await apiFetch("/api/provider-connections/"+id,{method:"DELETE"});
   await load();
   setNotice(provider==="flipkart"?"Saved Flipkart token removed from this workspace. Revoke or regenerate it separately in Flipkart Affiliate API settings.":"Saved credential removed. Revoke the key separately in ClickBank API Management.");
  }catch(exc){setError(exc instanceof Error?exc.message:"Could not remove the saved credential.");}
  finally{setBusy("");}
 };
 return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:px-8"><div className="mx-auto max-w-5xl">
  <header className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-xs font-black uppercase tracking-[.18em] text-indigo-600">Publisher workspace · Integrations</p><h1 className="mt-2 text-3xl font-black tracking-tight">Affiliate account connections</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Provider account state is verified with the provider, not inferred from a catalogue entry or saved key.</p></div><a href="/" className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold">Back to growth cockpit</a></header>
  {error&&<div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
  {notice&&<div role="status" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
  <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"><div className="flex items-start gap-3"><div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-indigo-50 text-lg font-black text-indigo-700">CB</div><div><h2 className="text-xl font-black">Connect ClickBank</h2><p className="mt-1 text-sm text-slate-600">Read-only Quickstats account-list verification. Required permission: API Order Read.</p></div></div>
   <form onSubmit={connect} className="mt-6 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"><label className="block text-sm font-bold" htmlFor="clickbank-api-key">ClickBank API key<input id="clickbank-api-key" aria-label="ClickBank API key" type="password" autoComplete="off" spellCheck={false} value={apiKey} onChange={event=>setApiKey(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 font-mono text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"/></label><button type="submit" disabled={busy!==""||apiKey.trim().length<20} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-50">{busy==="connect"?"Verifying…":"Verify & connect"}</button></form>
   <div className="mt-4 rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-600"><p className="font-bold text-slate-800">Create a least-privilege key first</p><p>In ClickBank, open Settings → API Management, create an active API key and grant API Order Read for the account nicknames you need. OmniAffiliateOS encrypts the key and never returns it to the browser.</p><p className="mt-2">This connection checks account read access only. It does not modify orders, submit program applications, publish content, spend ad budget or transfer payouts.</p><a className="mt-2 inline-block font-bold text-indigo-700 underline" href="https://support.clickbank.com/en/articles/10535395-how-to-create-clickbank-api-keys" target="_blank" rel="noreferrer">ClickBank API-key instructions</a></div>
  </section>
  <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
   <div className="flex items-start gap-3"><div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-amber-50 text-lg font-black text-amber-800">FK</div><div><h2 className="text-xl font-black">Connect Flipkart Affiliate</h2><p className="mt-1 text-sm text-slate-600">Read-only product-feed directory verification, keyword product search and active-offer retrieval.</p></div></div>
   <form onSubmit={connectFlipkart} className="mt-5 grid gap-3 sm:grid-cols-2">
    <label className="block text-sm font-bold" htmlFor="flipkart-tracking-id">Affiliate tracking ID<input id="flipkart-tracking-id" autoComplete="off" spellCheck={false} value={flipkartTrackingId} onChange={event=>setFlipkartTrackingId(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 font-mono text-sm" placeholder="Your registered tracking ID"/></label>
    <label className="block text-sm font-bold" htmlFor="flipkart-api-token">Private Affiliate API token<input id="flipkart-api-token" type="password" autoComplete="off" spellCheck={false} value={flipkartToken} onChange={event=>setFlipkartToken(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 font-mono text-sm" placeholder="Private token from Affiliate API settings"/></label>
    <div className="sm:col-span-2 flex flex-wrap items-center justify-between gap-3"><p className="max-w-2xl text-xs leading-5 text-slate-500">Use the tracking ID and private token provided for your registered Flipkart Affiliate account. The token is verified before storage, encrypted at rest and never returned to the browser. Token rotation can invalidate the previous token.</p><button type="submit" disabled={busy!==""||flipkartTrackingId.trim().length<2||flipkartToken.trim().length<20} className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-50">{busy==="flipkart-connect"?"Verifying…":"Verify & connect Flipkart"}</button></div>
   </form>
   <p className="mt-3 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-600">This connector only reads the official feed directory, product search and offer feeds. It does not submit affiliate applications, publish content, spend advertising budget or transfer payouts. Product prices and stock are time-stamped provider observations; commission rates, attribution windows, payout terms and promotion approval are not inferred from product results.</p>
  </section>
  <section className="mt-8"><div className="flex items-center justify-between gap-3"><div><h2 className="text-xl font-black">Workspace connections</h2><p className="mt-1 text-sm text-slate-500">Credentials are isolated to the active workspace.</p></div><button type="button" onClick={()=>void load()} disabled={loading||busy!==""} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold disabled:opacity-50">Refresh</button></div>
   {loading?<p role="status" className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Loading workspace connections…</p>:connections.length===0?<p className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white p-7 text-center text-sm text-slate-500">No provider accounts have been connected to this workspace.</p>:<div className="mt-5 grid gap-4">{connections.map(connection=><article key={connection.id} data-testid={`provider-connection-${connection.id}`} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-black">{connection.provider_id==="clickbank"?"ClickBank":connection.provider_id==="flipkart"?"Flipkart Affiliate":connection.provider_id}</h3><span className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${connection.status==="connected_read_only"?"bg-emerald-50 text-emerald-700":connection.status==="degraded"?"bg-amber-50 text-amber-800":"bg-slate-100 text-slate-600"}`}>{connection.status.replaceAll("_"," ")}</span><p className="mt-2 text-xs text-slate-500">{connection.credential_present?"Encrypted credential stored":"No saved credential"} · {connection.permissions_verified.join(", ")||"No provider permission verified"}</p></div><div className="flex flex-wrap gap-2"><button type="button" onClick={()=>void test(connection.id,connection.provider_id)} disabled={busy!==""||!connection.credential_present} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold disabled:opacity-40">{busy===connection.id?"Checking…":"Test connection"}</button>{connection.status!=="disconnected"&&<button type="button" onClick={()=>void disconnect(connection.id)} disabled={busy!==""} className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-bold text-rose-700 disabled:opacity-40">Disconnect</button>}</div></div>
    {connection.provider_id==="clickbank"?(
    <div className="mt-4"><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Account nicknames and performance</p><div className="mt-2 grid gap-3">{connection.account_nicknames.map(account=>{const report=quickstats[connection.id+":"+account];const orderReport=orderCounts[connection.id+":"+account];return <div key={account} className="rounded-xl border border-slate-100 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><span className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700">{account}</span><button type="button" onClick={()=>void loadQuickstats(connection.id,account)} disabled={busy!==""} className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs font-bold text-indigo-700 disabled:opacity-40">{busy===connection.id+":"+account?"Loading…":"Load last 30 days"}</button><button type="button" onClick={()=>void loadOrderCounts(connection.id,account)} disabled={busy!==""} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold disabled:opacity-40">{busy===connection.id+":orders:"+account?"Loading…":"Load 30-day order counts"}</button><button type="button" onClick={()=>void importOrders(connection.id,account)} disabled={busy!==""} className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs font-bold text-indigo-700 disabled:opacity-40">{busy===connection.id+":"+account+":import"?"Importing…":"Import last 30 days orders"}</button></div>{orderImports[connection.id+":"+account]&&<div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3" data-testid="clickbank-order-import"><p className="text-[11px] font-semibold text-slate-600">Provider-reported, unreconciled observations · {orderImports[connection.id+":"+account].period.start_date} to {orderImports[connection.id+":"+account].period.end_date}</p><p className="mt-1 text-xs text-slate-600">{orderImports[connection.id+":"+account].imported_count} new observations · {orderImports[connection.id+":"+account].duplicate_count} duplicates ignored · {orderImports[connection.id+":"+account].pages_retrieved} pages read · {orderImports[connection.id+":"+account].matched_click_count} matched clicks</p><p className="mt-2 text-[11px] leading-4 text-slate-600">Customer names, emails, contact details and postal data are not stored. TID matches link an order to a local click within 60 days; they do not verify commission, net earnings or payout. Provider account amounts remain unreconciled evidence only.</p><div className="mt-2 max-h-56 overflow-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b border-indigo-100 text-slate-500"><th className="py-1">Transaction</th><th className="py-1">Product</th><th className="py-1">Account amount</th><th className="py-1">State</th><th className="py-1">Local click</th></tr></thead><tbody>{orderImports[connection.id+":"+account].transactions.slice(0,30).map(item=><tr key={item.event_key} className="border-b border-indigo-50"><td className="py-1"><span className="font-bold">{item.transaction_type}</span><br/><span className="text-slate-500">{item.transaction_time}</span></td><td className="py-1">{item.product_title||item.item_number||"Order item"}</td><td className="py-1">{item.account_amount===null?"—":(item.currency||"") +" "+item.account_amount}</td><td className="py-1">{item.line_item_status||"Unreconciled"}</td><td className="py-1">{item.attribution_status==="matched_clickbank_tid"&&item.click_id?"Matched · "+item.click_id.slice(0,8):"Not matched"}</td></tr>)}</tbody></table></div>{orderImports[connection.id+":"+account].has_more&&orderImports[connection.id+":"+account].next_page!==null&&<button type="button" onClick={()=>void importOrders(connection.id,account,orderImports[connection.id+":"+account].next_page as number)} disabled={busy!==""} className="mt-2 rounded-lg border border-indigo-200 bg-white px-3 py-2 text-xs font-bold text-indigo-700 disabled:opacity-40">Load next provider page</button>}</div>}{orderReport&&<div className="mt-3 rounded-lg bg-slate-50 p-3"><p className="text-[11px] font-semibold text-slate-500">{orderReport.period.start_date} to {orderReport.period.end_date} · Provider-reported affiliate transaction counts</p><div className="mt-2 grid grid-cols-3 gap-2 text-xs"><div><p className="text-slate-500">Sales</p><p className="font-black">{orderReport.counts.sales}</p></div><div><p className="text-slate-500">Refunds</p><p className="font-black">{orderReport.counts.refunds}</p></div><div><p className="text-slate-500">Chargebacks</p><p className="font-black">{orderReport.counts.chargebacks}</p></div></div><p className="mt-2 text-[11px] leading-4 text-slate-500">Counts only. These are not commission amounts, earnings or payouts; customer order records are not imported.</p></div>}{report&&<div className="mt-3"><p className="text-[11px] font-semibold text-slate-500">{report.period.start_date} to {report.period.end_date} · Provider-reported aggregate</p><div className="mt-2 grid grid-cols-3 gap-2 text-xs"><div className="rounded-lg bg-slate-50 p-2"><p className="text-slate-500">Sales</p><p className="mt-1 font-black">{report.totals.sales??"—"}</p></div><div className="rounded-lg bg-slate-50 p-2"><p className="text-slate-500">Refunds</p><p className="mt-1 font-black">{report.totals.refunds??"—"}</p></div><div className="rounded-lg bg-slate-50 p-2"><p className="text-slate-500">Chargebacks</p><p className="mt-1 font-black">{report.totals.chargebacks??"—"}</p></div></div><p className="mt-2 text-[11px] leading-4 text-slate-500">These figures are account sales/refund/chargeback aggregates. They are not affiliate commission, net earnings or payout amounts.</p><details className="mt-2"><summary className="cursor-pointer text-xs font-bold text-indigo-700">Daily breakdown ({report.daily.length})</summary><div className="mt-2 max-h-48 overflow-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b border-slate-100 text-slate-500"><th className="py-1">Date</th><th className="py-1">Sales</th><th className="py-1">Refunds</th><th className="py-1">Chargebacks</th></tr></thead><tbody>{report.daily.map((item,index)=><tr key={item.date+":"+index} className="border-b border-slate-50"><td className="py-1">{item.date}</td><td>{item.sales??"—"}</td><td>{item.refunds??"—"}</td><td>{item.chargebacks??"—"}</td></tr>)}</tbody></table></div></details></div>}</div>;})}</div></div>
    ):connection.provider_id==="flipkart"?(
     <div className="mt-4 rounded-xl border border-slate-100 p-3" data-testid="flipkart-provider-tools">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Verified tracking ID</p><p className="mt-1 font-mono text-sm font-bold">{connection.account_nicknames[0]||"Not available"}</p></div><span className="rounded-full bg-amber-50 px-3 py-1.5 text-xs font-bold text-amber-900">Read-only product data</span></div>
      <form onSubmit={event=>{event.preventDefault();void searchFlipkartProducts(connection.id);}} className="mt-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
       <label className="block text-xs font-bold text-slate-700" htmlFor={"flipkart-query-"+connection.id}>Search products by keyword<input id={"flipkart-query-"+connection.id} value={flipkartSearchText} onChange={event=>setFlipkartSearchText(event.target.value)} minLength={2} maxLength={200} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal" placeholder="e.g. wireless earbuds"/></label>
       <button type="submit" disabled={busy!==""} className="self-end rounded-lg bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-40">{busy===connection.id+":flipkart-search"?"Searching…":"Search Flipkart products"}</button>
      </form>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-slate-500">Search returns up to 10 provider results and saves the latest observation per product in this workspace.</p><div className="flex flex-wrap gap-2"><button type="button" onClick={()=>void loadSavedFlipkartProducts(connection.id)} disabled={busy!==""} className="rounded-lg border border-indigo-200 px-3 py-2 text-xs font-bold disabled:opacity-40">{busy===connection.id+":flipkart-saved-products"?"Loading…":"Load saved products"}</button><button type="button" onClick={()=>void loadFlipkartOffers(connection.id)} disabled={busy!==""} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold disabled:opacity-40">{busy===connection.id+":flipkart-offers"?"Loading…":"Load active offers"}</button><button type="button" onClick={()=>void loadSavedFlipkartOffers(connection.id)} disabled={busy!==""} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold disabled:opacity-40">{busy===connection.id+":flipkart-saved-offers"?"Loading…":"Load saved offers"}</button></div></div>
      {flipkartProducts[connection.id]&&<div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-3" data-testid="flipkart-product-results"><p className="text-xs font-bold text-slate-700">Provider-reported products · {flipkartProducts[connection.id].result_count} result(s) · checked {formatObservedAt(flipkartProducts[connection.id].source_checked_at)}</p><div className="mt-2 grid gap-3 sm:grid-cols-2">{flipkartProducts[connection.id].products.map(product=><article key={product.external_id} className="rounded-lg border border-slate-200 bg-white p-3"><div className="flex gap-3">{product.image_url&&<img src={product.image_url} alt="" className="h-16 w-16 rounded-lg object-contain"/>}<div className="min-w-0"><p className="text-sm font-bold">{product.title}</p><p className="mt-1 text-xs text-slate-500">{product.brand||"Brand unknown"} · {product.category||"Category unknown"}</p><p data-testid="flipkart-product-price" className="mt-1 text-xs font-bold">{product.currency||""} {product.price_amount??"Price unknown"}{product.mrp_amount?" · MRP "+(product.currency||"")+" "+product.mrp_amount:""}</p><p className="mt-1 text-xs text-slate-500">{product.in_stock===true?"In stock":product.in_stock===false?"Out of stock":"Stock unknown"}{product.discount_percentage?" · "+product.discount_percentage+"% discount":""}</p>{product.product_url&&<a href={product.product_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs font-bold text-indigo-700 underline">Open product</a>}</div></div></article>)}</div><p className="mt-3 text-[11px] leading-5 text-amber-900">{flipkartProducts[connection.id].note}</p></div>}
      {flipkartOffers[connection.id]&&<div className="mt-4 rounded-xl border border-amber-100 bg-amber-50/50 p-3" data-testid="flipkart-active-offers"><p className="text-xs font-bold text-slate-700">Active offers · {flipkartOffers[connection.id].result_count} result(s) · checked {formatObservedAt(flipkartOffers[connection.id].source_checked_at)}</p><div className="mt-2 grid gap-2">{flipkartOffers[connection.id].offers.map(offer=><article key={offer.external_id} className="rounded-lg bg-white p-3"><p className="text-sm font-bold">{offer.title}</p><p className="mt-1 text-xs text-slate-500">{offer.category||"Category unknown"} · {offer.availability_status||"Availability unknown"}</p>{offer.offer_url&&<a href={offer.offer_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs font-bold text-indigo-700 underline">Open offer</a>}</article>)}</div><p className="mt-3 text-[11px] leading-5 text-amber-900">{flipkartOffers[connection.id].note}</p></div>}
     </div>
    ):<p className="mt-4 text-xs text-slate-500">No provider-specific read tools are enabled for this connection.</p>}
<p className="mt-3 text-xs text-slate-500">Last provider check: {connection.last_checked_at?new Date(connection.last_checked_at).toLocaleString():"Not checked"}</p>
   </article>)}</div>}
  </section>
 </div></main>;
}

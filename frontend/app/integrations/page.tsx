"use client";
import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type Connection={id:string;provider_id:string;status:"connected_read_only"|"degraded"|"disconnected";account_nicknames:string[];capabilities:string[];permissions_verified:string[];credential_present:boolean;last_checked_at:string|null;last_error_code:string|null;created_at:string|null};
type ConnectionList={data:Connection[]};
type ProviderOrderTransaction={
  event_key:string;source_fingerprint:string;receipt:string;transaction_time:string;
  transaction_type:string;role:"AFFILIATE";account_nickname:string;vendor_nickname:string|null;
  affiliate_nickname:string|null;currency:string|null;item_number:string|null;line_item_type:string|null;
  product_title:string|null;account_amount:string|null;customer_amount:string|null;
  line_item_status:string|null;recurring:boolean|null;shippable:boolean|null;
  evidence_status:"provider_reported_unreconciled";
};
type OrderImportReport={
  provider_id:string;evidence_type:string;financial_semantics:string;pii_stored:boolean;
  period:{start_date:string;end_date:string};account:string;pages_retrieved:number;
  source_order_count:number;skipped_unidentified_count:number;skipped_scope_count:number;
  imported_count:number;duplicate_count:number;has_more:boolean;next_page:number|null;
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

export default function IntegrationsPage(){
 const [connections,setConnections]=useState<Connection[]>([]);
 const [apiKey,setApiKey]=useState("");
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
 const test=async(id:string)=>{setBusy(id);setError("");setNotice("");try{const row=await apiFetch<Connection>(`/api/provider-connections/${id}/test`,{method:"POST"});setConnections(current=>current.map(item=>item.id===id?row:item));setNotice("ClickBank read-only account verification passed.");}catch(exc){setError(exc instanceof Error?exc.message:"Provider verification failed.");await load();}finally{setBusy("");}};
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
 const disconnect=async(id:string)=>{setBusy(id);setError("");setNotice("");try{await apiFetch(`/api/provider-connections/${id}`,{method:"DELETE"});await load();setNotice("Saved credential removed. Revoke the key separately in ClickBank API Management.");}catch(exc){setError(exc instanceof Error?exc.message:"Could not remove the saved credential.");}finally{setBusy("");}};
 return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:px-8"><div className="mx-auto max-w-5xl">
  <header className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-xs font-black uppercase tracking-[.18em] text-indigo-600">Publisher workspace · Integrations</p><h1 className="mt-2 text-3xl font-black tracking-tight">Affiliate account connections</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Provider account state is verified with the provider, not inferred from a catalogue entry or saved key.</p></div><a href="/" className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold">Back to growth cockpit</a></header>
  {error&&<div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
  {notice&&<div role="status" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}
  <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"><div className="flex items-start gap-3"><div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-indigo-50 text-lg font-black text-indigo-700">CB</div><div><h2 className="text-xl font-black">Connect ClickBank</h2><p className="mt-1 text-sm text-slate-600">Read-only Quickstats account-list verification. Required permission: API Order Read.</p></div></div>
   <form onSubmit={connect} className="mt-6 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"><label className="block text-sm font-bold" htmlFor="clickbank-api-key">ClickBank API key<input id="clickbank-api-key" aria-label="ClickBank API key" type="password" autoComplete="off" spellCheck={false} value={apiKey} onChange={event=>setApiKey(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 font-mono text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"/></label><button type="submit" disabled={busy!==""||apiKey.trim().length<20} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-50">{busy==="connect"?"Verifying…":"Verify & connect"}</button></form>
   <div className="mt-4 rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-600"><p className="font-bold text-slate-800">Create a least-privilege key first</p><p>In ClickBank, open Settings → API Management, create an active API key and grant API Order Read for the account nicknames you need. OmniAffiliateOS encrypts the key and never returns it to the browser.</p><p className="mt-2">This connection checks account read access only. It does not modify orders, submit program applications, publish content, spend ad budget or transfer payouts.</p><a className="mt-2 inline-block font-bold text-indigo-700 underline" href="https://support.clickbank.com/en/articles/10535395-how-to-create-clickbank-api-keys" target="_blank" rel="noreferrer">ClickBank API-key instructions</a></div>
  </section>
  <section className="mt-8"><div className="flex items-center justify-between gap-3"><div><h2 className="text-xl font-black">Workspace connections</h2><p className="mt-1 text-sm text-slate-500">Credentials are isolated to the active workspace.</p></div><button type="button" onClick={()=>void load()} disabled={loading||busy!==""} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold disabled:opacity-50">Refresh</button></div>
   {loading?<p role="status" className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Loading workspace connections…</p>:connections.length===0?<p className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white p-7 text-center text-sm text-slate-500">No provider accounts have been connected to this workspace.</p>:<div className="mt-5 grid gap-4">{connections.map(connection=><article key={connection.id} data-testid={`provider-connection-${connection.id}`} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-black">{connection.provider_id==="clickbank"?"ClickBank":connection.provider_id}</h3><span className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${connection.status==="connected_read_only"?"bg-emerald-50 text-emerald-700":connection.status==="degraded"?"bg-amber-50 text-amber-800":"bg-slate-100 text-slate-600"}`}>{connection.status.replaceAll("_"," ")}</span><p className="mt-2 text-xs text-slate-500">{connection.credential_present?"Encrypted credential stored":"No saved credential"} · {connection.permissions_verified.join(", ")||"No provider permission verified"}</p></div><div className="flex flex-wrap gap-2"><button type="button" onClick={()=>void test(connection.id)} disabled={busy!==""||!connection.credential_present} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold disabled:opacity-40">{busy===connection.id?"Checking…":"Test connection"}</button>{connection.status!=="disconnected"&&<button type="button" onClick={()=>void disconnect(connection.id)} disabled={busy!==""} className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-bold text-rose-700 disabled:opacity-40">Disconnect</button>}</div></div>
    <div className="mt-4"><p className="text-xs font-bold uppercase tracking-wider text-slate-400">Account nicknames and performance</p><div className="mt-2 grid gap-3">{connection.account_nicknames.map(account=>{const report=quickstats[connection.id+":"+account];const orderReport=orderCounts[connection.id+":"+account];return <div key={account} className="rounded-xl border border-slate-100 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><span className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700">{account}</span><button type="button" onClick={()=>void loadQuickstats(connection.id,account)} disabled={busy!==""} className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs font-bold text-indigo-700 disabled:opacity-40">{busy===connection.id+":"+account?"Loading…":"Load last 30 days"}</button><button type="button" onClick={()=>void loadOrderCounts(connection.id,account)} disabled={busy!==""} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold disabled:opacity-40">{busy===connection.id+":orders:"+account?"Loading…":"Load 30-day order counts"}</button><button type="button" onClick={()=>void importOrders(connection.id,account)} disabled={busy!==""} className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs font-bold text-indigo-700 disabled:opacity-40">{busy===connection.id+":"+account+":import"?"Importing…":"Import last 30 days orders"}</button></div>{orderImports[connection.id+":"+account]&&<div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3" data-testid="clickbank-order-import"><p className="text-[11px] font-semibold text-slate-600">Provider-reported, unreconciled observations · {orderImports[connection.id+":"+account].period.start_date} to {orderImports[connection.id+":"+account].period.end_date}</p><p className="mt-1 text-xs text-slate-600">{orderImports[connection.id+":"+account].imported_count} new observations · {orderImports[connection.id+":"+account].duplicate_count} duplicates ignored · {orderImports[connection.id+":"+account].pages_retrieved} pages read</p><p className="mt-2 text-[11px] leading-4 text-slate-600">Customer names, emails, contact details and postal data are not stored. Provider account amounts remain evidence only, not confirmed commission, net earnings or payout.</p><div className="mt-2 max-h-56 overflow-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b border-indigo-100 text-slate-500"><th className="py-1">Transaction</th><th className="py-1">Product</th><th className="py-1">Account amount</th><th className="py-1">State</th></tr></thead><tbody>{orderImports[connection.id+":"+account].transactions.slice(0,30).map(item=><tr key={item.event_key} className="border-b border-indigo-50"><td className="py-1"><span className="font-bold">{item.transaction_type}</span><br/><span className="text-slate-500">{item.transaction_time}</span></td><td className="py-1">{item.product_title||item.item_number||"Order item"}</td><td className="py-1">{item.account_amount===null?"—":(item.currency||"") +" "+item.account_amount}</td><td className="py-1">{item.line_item_status||"Unreconciled"}</td></tr>)}</tbody></table></div>{orderImports[connection.id+":"+account].has_more&&orderImports[connection.id+":"+account].next_page!==null&&<button type="button" onClick={()=>void importOrders(connection.id,account,orderImports[connection.id+":"+account].next_page as number)} disabled={busy!==""} className="mt-2 rounded-lg border border-indigo-200 bg-white px-3 py-2 text-xs font-bold text-indigo-700 disabled:opacity-40">Load next provider page</button>}</div>}{orderReport&&<div className="mt-3 rounded-lg bg-slate-50 p-3"><p className="text-[11px] font-semibold text-slate-500">{orderReport.period.start_date} to {orderReport.period.end_date} · Provider-reported affiliate transaction counts</p><div className="mt-2 grid grid-cols-3 gap-2 text-xs"><div><p className="text-slate-500">Sales</p><p className="font-black">{orderReport.counts.sales}</p></div><div><p className="text-slate-500">Refunds</p><p className="font-black">{orderReport.counts.refunds}</p></div><div><p className="text-slate-500">Chargebacks</p><p className="font-black">{orderReport.counts.chargebacks}</p></div></div><p className="mt-2 text-[11px] leading-4 text-slate-500">Counts only. These are not commission amounts, earnings or payouts; customer order records are not imported.</p></div>}{report&&<div className="mt-3"><p className="text-[11px] font-semibold text-slate-500">{report.period.start_date} to {report.period.end_date} · Provider-reported aggregate</p><div className="mt-2 grid grid-cols-3 gap-2 text-xs"><div className="rounded-lg bg-slate-50 p-2"><p className="text-slate-500">Sales</p><p className="mt-1 font-black">{report.totals.sales??"—"}</p></div><div className="rounded-lg bg-slate-50 p-2"><p className="text-slate-500">Refunds</p><p className="mt-1 font-black">{report.totals.refunds??"—"}</p></div><div className="rounded-lg bg-slate-50 p-2"><p className="text-slate-500">Chargebacks</p><p className="mt-1 font-black">{report.totals.chargebacks??"—"}</p></div></div><p className="mt-2 text-[11px] leading-4 text-slate-500">These figures are account sales/refund/chargeback aggregates. They are not affiliate commission, net earnings or payout amounts.</p><details className="mt-2"><summary className="cursor-pointer text-xs font-bold text-indigo-700">Daily breakdown ({report.daily.length})</summary><div className="mt-2 max-h-48 overflow-auto"><table className="w-full text-left text-xs"><thead><tr className="border-b border-slate-100 text-slate-500"><th className="py-1">Date</th><th className="py-1">Sales</th><th className="py-1">Refunds</th><th className="py-1">Chargebacks</th></tr></thead><tbody>{report.daily.map((item,index)=><tr key={item.date+":"+index} className="border-b border-slate-50"><td className="py-1">{item.date}</td><td>{item.sales??"—"}</td><td>{item.refunds??"—"}</td><td>{item.chargebacks??"—"}</td></tr>)}</tbody></table></div></details></div>}</div>;})}</div></div><p className="mt-3 text-xs text-slate-500">Last provider check: {connection.last_checked_at?new Date(connection.last_checked_at).toLocaleString():"Not checked"}</p>
   </article>)}</div>}
  </section>
 </div></main>;
}

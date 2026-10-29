"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type ProductInput={name:string;facts:Record<string,string>;source_urls:string[];affiliate_url?:string|null;affiliate_relationship:"editorial"|"affiliate_primary"|"affiliate_secondary"};
type DraftSummary={asset_id:string;title:string;asset_status:string;created_at:string|null;product_count:number;word_count:number;evidence_status:string;review_status:string;content_integrity_status:string;publishing_started:boolean};
type DraftList={items:DraftSummary[];total:number;limit:number;offset:number};
type EvidenceItem={product:string;fact_name:string;supplied_value:string;source_id:string|null;source_url:string|null;excerpt_sha256:string|null;exact_text_match:boolean;evidence_status:string;evidence_note?:string;editorial_review_required:boolean};
type Snapshot={source_id:string;url:string;product_names:string[];title:string;status:string;http_status:number|null;content_type:string;fetched_at:string;excerpt:string;excerpt_sha256:string|null;error_type:string|null;detail:string|null};
type ListicleResult={
 asset_id:string;asset_status:string;title:string;slug:string;meta_description:string;topic:string;audience:string;target_keyword:string;format:string;html:string;
 word_count:number;minimum_word_target:number;minimum_word_target_met:boolean;word_count_warning:string|null;product_count:number;products:ProductInput[];
 products_featured:Array<{rank:number;name:string;affiliate_relationship:string;affiliate_url:string|null}>;evaluation_criteria:string[];source_urls:string[];
 source_snapshots:Snapshot[];fact_evidence:EvidenceItem[];
 evidence_summary:{source_count:number;source_snapshots_fetched:number;source_snapshots_failed:number;fact_count:number;exact_text_match_count:number;exact_text_not_found_count:number;facts_not_compared:number;interpretation:string};
 evidence_status:string;product_facts_independently_verified:boolean;external_product_sources_fetched:boolean;requires_review:boolean;publishing_started:boolean;
 provider_write_access_verified:boolean;provider:string;execution_boundary:string;content_sha256:string;source_snapshot_manifest_sha256:string;evidence_payload_sha256:string;
 content_integrity_status:string;review_status:string;review_history:Array<{decision:string;review_status:string;reviewed_by:string;reviewed_at:string;reviewer_notes:string|null;content_sha256:string;external_publication_started:boolean}>;
 reviewed_by:string|null;reviewed_at:string|null;reviewer_role:string|null;reviewer_notes:string|null;can_review:boolean;
};
const initialProducts=JSON.stringify([
  {name:"Product 1",facts:{Price:"Not supplied", "Best for":"Not supplied","Free plan":"Not supplied","Key features":"Not supplied","Pros":"Not supplied","Cons":"Not supplied"},source_urls:[],affiliate_relationship:"editorial"},
  {name:"Product 2",facts:{Price:"Not supplied", "Best for":"Not supplied","Free plan":"Not supplied","Key features":"Not supplied","Pros":"Not supplied","Cons":"Not supplied"},source_urls:[],affiliate_relationship:"editorial"},
  {name:"Product 3",facts:{Price:"Not supplied", "Best for":"Not supplied","Free plan":"Not supplied","Key features":"Not supplied","Pros":"Not supplied","Cons":"Not supplied"},source_urls:[],affiliate_relationship:"editorial"},
  {name:"Product 4",facts:{Price:"Not supplied", "Best for":"Not supplied","Free plan":"Not supplied","Key features":"Not supplied","Pros":"Not supplied","Cons":"Not supplied"},source_urls:[],affiliate_relationship:"editorial"},
  {name:"Product 5",facts:{Price:"Not supplied", "Best for":"Not supplied","Free plan":"Not supplied","Key features":"Not supplied","Pros":"Not supplied","Cons":"Not supplied"},source_urls:[],affiliate_relationship:"editorial"}
],null,2);
const field="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm";
const label="block text-sm font-semibold text-slate-700";
function errorMessage(error:unknown){return error instanceof Error?error.message:"Request failed";}
function present(value:string|undefined|null){return value&&value.trim()&&!["not supplied","not supplied — verify","unknown","n/a","na"].includes(value.trim().toLowerCase())?value:"Not supplied — verify";}

export default function ListicleWriterPage(){
 const [topic,setTopic]=useState("Email marketing tools for small publishers");
 const [audience,setAudience]=useState("Independent affiliate publishers choosing tools for a small list");
 const [keyword,setKeyword]=useState("best email marketing tools for affiliate publishers");
 const [criteriaText,setCriteriaText]=useState("Fit for small publishers\nSupplied features\nPricing clarity\nFree plan availability");
 const [productsJson,setProductsJson]=useState(initialProducts);
 const [disclosure,setDisclosure]=useState("Disclosure: This article may contain affiliate links. I may earn a commission from qualifying purchases.");
 const [minimumWords,setMinimumWords]=useState("1500");
 const [tone,setTone]=useState<"professional"|"conversational">("professional");
 const [items,setItems]=useState<DraftSummary[]>([]);
 const [total,setTotal]=useState(0);
 const [result,setResult]=useState<ListicleResult|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [reviewNotes,setReviewNotes]=useState("");
 const [confirmReviewed,setConfirmReviewed]=useState(false);

 const refreshList=useCallback(async()=>{
  try{const response=await apiFetch<DraftList>("/api/content/listicles?limit=20&offset=0");setItems(response.items||[]);setTotal(response.total||0);}
  catch(e){setError(errorMessage(e));}
 },[]);
 useEffect(()=>{void refreshList();},[refreshList]);

 const openDraft=async(assetId:string)=>{
  setBusy(true);setError("");setNotice("");setConfirmReviewed(false);setReviewNotes("");
  try{const detail=await apiFetch<ListicleResult>("/api/content/listicles/"+encodeURIComponent(assetId));setResult(detail);setNotice("Opened the saved workspace listicle draft.");}
  catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };

 const submit=async(event:FormEvent)=>{
  event.preventDefault();setBusy(true);setError("");setNotice("");setResult(null);
  let products:unknown;
  try{products=JSON.parse(productsJson);}catch{setError("Products must be valid JSON.");setBusy(false);return;}
  if(!Array.isArray(products)||products.length<5||products.length>12){setError("Supply between five and twelve product objects.");setBusy(false);return;}
  if(products.some(p=>!p||typeof p!=="object"||typeof p.name!=="string"||!p.name.trim()||!p.facts||typeof p.facts!=="object"||Array.isArray(p.facts))){setError("Every product needs a name and a facts object.");setBusy(false);return;}
  const minimum=Number(minimumWords);
  if(!Number.isInteger(minimum)||minimum<800||minimum>4500){setError("Minimum word target must be a whole number from 800 to 4500.");setBusy(false);return;}
  const evaluation_criteria=Array.from(new Set(criteriaText.split(/\r?\n/).map(v=>v.trim()).filter(Boolean)));
  try{
   const response=await apiFetch<ListicleResult>("/api/content/listicle",{method:"POST",body:JSON.stringify({
    topic:topic.trim(),audience:audience.trim(),target_keyword:keyword.trim()||null,products,evaluation_criteria,
    affiliate_disclosure:disclosure,minimum_words:minimum,tone
   })});
   setResult(response);setNotice("Listicle draft saved. Verify each product fact, source and affiliate destination before relying on it.");
   await refreshList();
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };

 const review=async(decision:"approve"|"request_changes"|"reject")=>{
  if(!result)return;
  setBusy(true);setError("");setNotice("");
  try{
   const response=await apiFetch<{review_status:string;publishing_started:boolean}>(
    "/api/content/listicles/"+encodeURIComponent(result.asset_id)+"/review",
    {method:"POST",body:JSON.stringify({decision,expected_content_sha256:result.content_sha256,reviewer_notes:reviewNotes,confirm_editorial_reviewed:decision==="approve"?confirmReviewed:false})}
   );
   setNotice("Editorial decision recorded: "+response.review_status.replaceAll("_"," ")+". External publication was not started.");
   await openDraft(result.asset_id);
   await refreshList();
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };

 const exportResult=result?{title:result.title,html:result.html,content_sha256:result.content_sha256,evidence_status:result.evidence_status,source_snapshots:result.source_snapshots,fact_evidence:result.fact_evidence,products_featured:result.products_featured,review_status:result.review_status,publishing_started:false}:null;

 return <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10"><div className="mx-auto max-w-7xl">
  <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
   <div><div className="flex flex-wrap gap-4 text-sm font-semibold"><a href="/" className="text-indigo-600 hover:underline">← Growth command</a><a href="/comparison-post" className="text-indigo-600 hover:underline">Product comparison writer →</a></div>
    <h1 className="mt-2 text-3xl font-black tracking-tight">Evidence-aware listicle writer</h1>
    <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">Generate a workspace-persisted “best of” article from supplied product facts and optional bounded public-page snapshots, with a deterministic comparison table and a fact-by-fact evidence ledger.</p>
   </div><span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-bold text-amber-900">Review-required draft · No publishing</span>
  </header>
  <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><strong>Evidence boundary:</strong> entered facts and affiliate relationships are operator supplied. Public page text may be captured through the application’s pinned and size-limited transport, but a literal text match does not establish truth, freshness, full terms, eligibility or compliance. Missing values remain “Not supplied — verify”. Draft generation never publishes or changes paid media.</div>
  {error&&<div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
  {notice&&<div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}

  <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(320px,.85fr)_minmax(0,1.15fr)]">
   <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold">Listicle brief</h2><form onSubmit={submit} className="mt-4 space-y-4">
    <label className={label}>Topic or category<input aria-label="Topic or category" className={field} minLength={3} maxLength={300} required value={topic} onChange={e=>setTopic(e.target.value)}/></label>
    <label className={label}>Target audience<input aria-label="Target audience" className={field} minLength={2} maxLength={300} required value={audience} onChange={e=>setAudience(e.target.value)}/></label>
    <label className={label}>Primary keyword<input aria-label="Primary keyword" className={field} maxLength={180} value={keyword} onChange={e=>setKeyword(e.target.value)}/></label>
    <label className={label}>Evaluation criteria (one per line)<textarea aria-label="Evaluation criteria" className={field} rows={4} maxLength={1200} value={criteriaText} onChange={e=>setCriteriaText(e.target.value)}/></label>
    <label className={label}>Products and facts (JSON, 5–12 products)<textarea id="listicle-products" aria-label="Products and facts (JSON, 5–12 products)" className={field+" font-mono text-xs leading-5"} rows={20} maxLength={40000} required spellCheck={false} value={productsJson} onChange={e=>setProductsJson(e.target.value)}/></label>
    <p className="text-xs leading-5 text-slate-500">Per product: name, facts object, optional source_urls; optional affiliate_url must be HTTPS and use affiliate_relationship editorial, affiliate_primary or affiliate_secondary. The primary affiliate may appear only once and within the first three supplied products. Up to 10 unique source URLs across the article.</p>
    <div className="grid gap-3 sm:grid-cols-2"><label className={label}>Minimum word target<input aria-label="Minimum word target" className={field} type="number" min="800" max="4500" step="1" required value={minimumWords} onChange={e=>setMinimumWords(e.target.value)}/></label><label className={label}>Writing tone<select aria-label="Writing tone" className={field} value={tone} onChange={e=>setTone(e.target.value as "professional"|"conversational")}><option value="professional">Professional</option><option value="conversational">Conversational</option></select></label></div>
    <label className={label}>Affiliate disclosure<input aria-label="Affiliate disclosure" className={field} minLength={20} maxLength={1200} required value={disclosure} onChange={e=>setDisclosure(e.target.value)}/></label>
    <button type="submit" disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white disabled:opacity-50">{busy?"Generating snapshots and saving…":"Generate listicle draft"}</button>
   </form></section>

   <section className="space-y-5">
    {!result&&<div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center"><h2 className="text-lg font-bold">Your article will appear here</h2><p className="mt-2 text-sm leading-6 text-slate-500">The generator preserves the supplied product order. It does not invent rankings, prices, ratings, features, earnings or reviews. A saved draft can be reopened and reviewed later.</p></div>}
    {result&&<div className="space-y-5"><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
     <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-black">{result.title}</h2><p className="mt-1 break-all font-mono text-xs text-slate-500">Saved draft · {result.asset_id}</p></div><a href={"data:application/json;charset=utf-8,"+encodeURIComponent(JSON.stringify(exportResult,null,2))} download="omni-affiliate-listicle-draft.json" className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-bold text-white">Export evidence JSON</a></div>
     <div className="mt-4 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Products</p><p className="mt-1 text-xl font-black">{result.product_count}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Source snapshots</p><p className="mt-1 text-xl font-black">{result.evidence_summary.source_snapshots_fetched} / {result.evidence_summary.source_count}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Draft words</p><p className="mt-1 text-xl font-black">{result.word_count}</p></div></div>
     <p className="mt-3 text-sm font-semibold text-amber-800">Evidence: {result.evidence_status.replaceAll("_"," ")} · Independent fact verification: No · Published: No · Editorial status: {result.review_status.replaceAll("_"," ")}</p>
     {result.word_count_warning&&<p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{result.word_count_warning}</p>}
     <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500"><span>Exact text matches: {result.evidence_summary.exact_text_match_count}</span><span>Exact text not found: {result.evidence_summary.exact_text_not_found_count}</span><span>Not compared: {result.evidence_summary.facts_not_compared}</span><span>Integrity: {result.content_integrity_status}</span></div>
     <h3 className="mt-5 font-bold">Products in supplied order</h3>
     <div className="mt-2 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr className="border-b border-slate-200"><th className="p-2">Order</th><th className="p-2">Product</th><th className="p-2">Relationship</th><th className="p-2">Affiliate link supplied</th></tr></thead><tbody>{result.products_featured.map(product=><tr className="border-b border-slate-100" key={product.name}><td className="p-2">{product.rank}</td><th className="p-2">{product.name}</th><td className="p-2">{product.affiliate_relationship.replaceAll("_"," ")}</td><td className="p-2">{product.affiliate_url?"Yes":"No"}</td></tr>)}</tbody></table></div>
     <h3 className="mt-5 font-bold">Fact evidence ledger</h3><div className="mt-2 max-h-72 overflow-auto rounded-xl border border-slate-200"><table className="min-w-full text-left text-xs"><thead className="sticky top-0 bg-slate-50"><tr><th className="p-2">Product / fact</th><th className="p-2">Supplied value</th><th className="p-2">Evidence status</th></tr></thead><tbody>{result.fact_evidence.map((fact,index)=><tr key={fact.product+"-"+fact.fact_name+"-"+index} className="border-t border-slate-100"><td className="p-2">{fact.product} / {fact.fact_name}</td><td className="max-w-xs p-2">{present(fact.supplied_value)}</td><td className="p-2">{fact.evidence_status.replaceAll("_"," ")}</td></tr>)}</tbody></table></div>
    </section><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="font-bold">Isolated article preview</h3><p className="mt-1 text-xs text-slate-500">Sandboxed HTML; script permission is not granted.</p><iframe title="Listicle article preview" sandbox="" srcDoc={result.html} className="mt-3 h-[640px] w-full rounded-xl border border-slate-200 bg-white"/></section>
    {result.can_review&&result.review_status==="pending_review"&&<section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="text-lg font-black">Editorial review</h3><p className="mt-1 text-sm leading-5 text-slate-600">Review product entries, fact evidence, source freshness, affiliate relationships and disclosures. Approval is internal editorial approval only; it does not authorize publication.</p>
     <label className={label+" mt-4"}>Reviewer notes<textarea aria-label="Reviewer notes" className={field} rows={3} maxLength={2000} value={reviewNotes} onChange={e=>setReviewNotes(e.target.value)} placeholder="Required when requesting changes or rejecting the draft."/></label>
     <label className="mt-3 flex items-start gap-2 text-sm text-slate-700"><input type="checkbox" checked={confirmReviewed} onChange={e=>setConfirmReviewed(e.target.checked)} className="mt-1"/><span>I reviewed the saved article and its source/fact evidence.</span></label>
     <div className="mt-4 flex flex-wrap gap-2"><button type="button" disabled={busy||!confirmReviewed} onClick={()=>void review("approve")} className="rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-40">Approve editorial draft</button><button type="button" disabled={busy||!reviewNotes.trim()} onClick={()=>void review("request_changes")} className="rounded-xl border border-amber-300 px-4 py-2.5 text-sm font-bold text-amber-800 disabled:opacity-40">Request changes</button><button type="button" disabled={busy||!reviewNotes.trim()} onClick={()=>void review("reject")} className="rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-bold text-rose-700 disabled:opacity-40">Reject draft</button></div>
     <p className="mt-3 text-xs leading-5 text-slate-500">Review is bound to SHA-256 {result.content_sha256}. If stored body or evidence snapshots change, the API blocks review. No provider write is performed.</p>
    </section>}
    {result.review_history?.length>0&&<section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="font-bold">Review history</h3><div className="mt-3 space-y-2">{result.review_history.map((entry,i)=><div className="rounded-xl bg-slate-50 p-3" key={entry.content_sha256+"-"+i}><p className="text-sm font-bold">{entry.review_status.replaceAll("_"," ")} · {entry.reviewed_by}</p><p className="mt-1 text-xs text-slate-500">{entry.reviewed_at} · content hash {entry.content_sha256}</p>{entry.reviewer_notes&&<p className="mt-2 text-sm text-slate-600">{entry.reviewer_notes}</p>}</div>)}</div></section>}
    <p className="rounded-xl border border-slate-200 bg-white p-4 text-xs leading-5 text-slate-600">{result.execution_boundary}</p></div>}
   </section>
  </div>

  <section className="mt-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
   <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-black">Saved listicle drafts</h2><p className="mt-1 text-sm text-slate-500">{total} workspace draft(s) · latest 20 shown</p></div><button type="button" onClick={()=>void refreshList()} disabled={busy} className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold disabled:opacity-40">Refresh drafts</button></div>
   {items.length===0?<p className="mt-4 rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-500">No saved listicle drafts are available in this workspace yet.</p>:<div className="mt-4 space-y-2">{items.map(item=><div key={item.asset_id} className="flex flex-col gap-3 rounded-xl border border-slate-200 p-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-bold">{item.title}</p><p className="mt-1 break-all font-mono text-[11px] text-slate-500">{item.asset_id}</p><p className="mt-1 text-xs text-slate-500">{item.product_count} products · {item.word_count} words · {item.review_status.replaceAll("_"," ")} · {item.evidence_status.replaceAll("_"," ")}</p></div><button type="button" disabled={busy} onClick={()=>void openDraft(item.asset_id)} className="shrink-0 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold disabled:opacity-40">Open draft</button></div>)}</div>}
  </section>
 </div></main>;
}

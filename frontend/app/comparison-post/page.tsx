"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type Product={name:string;facts:Record<string,string>;source_urls:string[]};
type Row={criterion:string;values:Array<{product:string;value:string}>};
type SourceSnapshot={source_id:string;url:string;product_names:string[];title:string;status:string;http_status:number|null;content_type:string;fetched_at:string;excerpt:string;excerpt_sha256:string|null;error_type:string|null;detail:string|null};
type FactEvidence={product:string;fact_name:string;supplied_value:string;source_id:string|null;source_url:string|null;excerpt_sha256:string|null;exact_text_match:boolean;evidence_status:string;evidence_note?:string;editorial_review_required:boolean};
type EvidenceSummary={source_count:number;source_snapshots_fetched:number;source_snapshots_failed:number;fact_count:number;exact_text_match_count:number;exact_text_not_found_count:number;facts_not_compared:number;interpretation:string};
type ReviewEntry={decision:string;review_status:string;reviewed_by:string;reviewer_role:string;reviewer_notes:string|null;reviewed_at:string;content_sha256:string;revision_number:number;external_publication_started:boolean};
type DraftSummary={asset_id:string;title:string;asset_status:string;created_at:string|null;revision_number:number;revision_of_asset_id:string|null;revision_root_asset_id:string|null;word_count:number;product_count:number;unknown_fact_count:number;evidence_status:string;source_snapshots_fetched:number;review_status:string;reviewed_by:string|null;can_review:boolean;requires_review:boolean;publishing_started:boolean};
type DraftList={items:DraftSummary[];total:number;limit:number;offset:number};
type Result={
 asset_id:string;asset_status:string;title:string;topic:string;audience:string;affiliate_disclosure:string;
 revision_number:number;revision_of_asset_id:string|null;revision_root_asset_id:string;content_sha256:string;html:string;word_count:number;
 minimum_word_target:number;minimum_word_target_met:boolean;word_count_warning:string|null;
 product_count:number;products:Product[];decision_criteria:string[];comparison_table:Row[];
 unknown_fact_count:number;source_urls:string[];source_snapshots:SourceSnapshot[];fact_evidence:FactEvidence[];evidence_summary:EvidenceSummary;evidence_status:string;
 product_facts_independently_verified:boolean;external_product_sources_fetched:boolean;
 content_integrity_status:string;source_snapshot_integrity_status:string;integrity_review_blocked:boolean;review_block_reason:string|null;is_workspace_reviewer:boolean;
 review_status:string;review_history:ReviewEntry[];reviewed_at:string|null;reviewed_by:string|null;reviewer_role:string|null;reviewer_notes:string|null;can_review:boolean;
 requires_review:boolean;publishing_started:boolean;provider_write_access_verified:boolean;
 provider:string;execution_boundary:string;
};
const initialProducts = "[\n  {\n    \"name\": \"Product Alpha\",\n    \"facts\": {\"Price\": \"Not supplied\", \"Platform support\": \"Web and desktop\"},\n    \"source_urls\": [\"https://vendor.example/products/alpha\"]\n  },\n  {\n    \"name\": \"Product Beta\",\n    \"facts\": {\"Price\": \"$49/month\", \"Support\": \"Email support\"},\n    \"source_urls\": [\"https://vendor.example/products/beta\"]\n  }\n]";
const field="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm";
const label="block text-sm font-semibold text-slate-700";
function errorMessage(error:unknown){return error instanceof Error?error.message:"Comparison article request failed";}

export default function ComparisonPostPage(){
 const [topic,setTopic]=useState("Affiliate analytics tools compared");
 const [audience,setAudience]=useState("Small affiliate publishers comparing analytics tools");
 const [criteriaText,setCriteriaText]=useState("Pricing\nEase of use\nIntegrations\nReporting");
 const [productsJson,setProductsJson]=useState(initialProducts);
 const [minimumWords,setMinimumWords]=useState("900");
 const [disclosure,setDisclosure]=useState("Disclosure: This article may contain affiliate links. I may earn a commission from qualifying purchases.");
 const [revisionOfAssetId,setRevisionOfAssetId]=useState<string|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [result,setResult]=useState<Result|null>(null);
 const [drafts,setDrafts]=useState<DraftSummary[]>([]);
 const [draftsTotal,setDraftsTotal]=useState(0);
 const [draftsLoading,setDraftsLoading]=useState(true);
 const [draftsError,setDraftsError]=useState("");
 const [openingId,setOpeningId]=useState("");
 const [reviewNote,setReviewNote]=useState("");
 const [confirmEditorialReview,setConfirmEditorialReview]=useState(false);
 const [reviewBusy,setReviewBusy]=useState(false);
 const loadDrafts=useCallback(async()=>{
  setDraftsLoading(true);setDraftsError("");
  try{
   const response=await apiFetch<DraftList>("/api/content/comparison-posts?limit=20&offset=0");
   setDrafts(response.items);setDraftsTotal(response.total);
  }catch(err){setDraftsError(errorMessage(err));}
  finally{setDraftsLoading(false);}
 },[]);
 useEffect(()=>{void loadDrafts();},[loadDrafts]);
 const openDraft=async(assetId:string)=>{
  setOpeningId(assetId);setError("");setNotice("");
  try{
   const response=await apiFetch<Result>("/api/content/comparison-posts/"+encodeURIComponent(assetId));
   setTopic(response.topic||response.title.replace(/ — Product Comparison$/,""));
   setAudience(response.audience||"");
   setCriteriaText((response.decision_criteria||[]).join("\n"));
   setProductsJson(JSON.stringify((response.products||[]).map(product=>({name:product.name,facts:product.facts||{},source_urls:product.source_urls||[]})),null,2));
   setMinimumWords(String(response.minimum_word_target||900));
   setDisclosure(response.affiliate_disclosure||"Disclosure: This article may contain affiliate links. I may earn a commission from qualifying purchases.");
   setRevisionOfAssetId(response.asset_id);
   setReviewNote("");setConfirmEditorialReview(false);
   setResult(response);setNotice("Opened saved comparison draft. Loaded as a revision starting point; the original remains unchanged.");
  }catch(err){setDraftsError(errorMessage(err));}
  finally{setOpeningId("");}
 };
 const submit=async(event:FormEvent)=>{
  event.preventDefault();setBusy(true);setError("");setNotice("");setResult(null);
  let products:unknown;
  try{products=JSON.parse(productsJson);}catch{setError("Products must be valid JSON.");setBusy(false);return;}
  if(!Array.isArray(products)||products.length<2||products.length>5){setError("Supply between two and five product objects.");setBusy(false);return;}
  if(products.some(p=>!p||typeof p!=="object"||typeof p.name!=="string"||!p.name.trim()||!p.facts||typeof p.facts!=="object"||Array.isArray(p.facts))){setError("Every product needs a name and a facts object.");setBusy(false);return;}
  const minimum=Number(minimumWords);
  if(!Number.isInteger(minimum)||minimum<300||minimum>2200){setError("Minimum word target must be a whole number from 300 to 2200.");setBusy(false);return;}
  const decision_criteria=Array.from(new Set(criteriaText.split(/\r?\n/).map(v=>v.trim()).filter(Boolean)));
  try{
   const requestBody={topic:topic.trim(),audience:audience.trim(),products,decision_criteria,affiliate_disclosure:disclosure,minimum_words:minimum,...(revisionOfAssetId?{revision_of_asset_id:revisionOfAssetId}:{})};
   const response=await apiFetch<Result>("/api/content/comparison-post",{method:"POST",body:JSON.stringify(requestBody)});
   setResult(response);setRevisionOfAssetId(response.asset_id);
   setNotice(response.revision_of_asset_id?"Saved a new draft revision. The original remains unchanged.":"Comparison draft saved to this workspace. You can revise it without overwriting the original.");
   await loadDrafts();
  }catch(err){setError(errorMessage(err));}finally{setBusy(false);}
 };
 const submitReview=async(decision:"approve"|"request_changes"|"reject")=>{
  if(!result)return;
  if(decision==="approve"&&!confirmEditorialReview){setError("Confirm that you reviewed this exact saved article before approving it.");return;}
  if(decision!=="approve"&&!reviewNote.trim()){setError("Reviewer notes are required when requesting changes or rejecting a draft.");return;}
  setReviewBusy(true);setError("");setNotice("");
  try{
   const response=await apiFetch<{
    asset_id:string;asset_status:string;review_status:string;review_history:ReviewEntry[];
    reviewed_at:string;reviewed_by:string;reviewer_role:string;reviewer_notes:string|null;
    content_sha256:string;requires_review:boolean;publishing_started:boolean;
    external_publication_started:boolean;product_facts_independently_verified:boolean;
    affiliate_eligibility_verified:boolean;provider_write_access_verified:boolean;
    publication_authorized:boolean;editorial_review_only:boolean;execution_boundary:string;
   }>("/api/content/comparison-posts/"+encodeURIComponent(result.asset_id)+"/review",{
    method:"POST",
    body:JSON.stringify({
     decision,
     reviewer_notes:reviewNote.trim(),
     expected_content_sha256:result.content_sha256,
     confirm_editorial_reviewed:decision==="approve"?confirmEditorialReview:false
    })
   });
   setResult(current=>current?({...current,...response}):current);
   setReviewNote("");setConfirmEditorialReview(false);
   setNotice(decision==="approve"
    ?"Editorial approval recorded for this exact revision. This draft was not published and product/provider claims were not verified."
    :decision==="request_changes"
     ?"Changes requested. The reviewed revision remains immutable; edit by creating a new revision."
     :"Draft rejected for editorial use. The reviewed revision remains immutable.");
   await loadDrafts();
  }catch(err){setError(errorMessage(err));}
  finally{setReviewBusy(false);}
 };

 return <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10"><div className="mx-auto max-w-7xl">
  <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
   <div><div className="flex flex-wrap gap-4 text-sm font-semibold"><a href="/" className="text-indigo-600 hover:underline">← Growth command</a><a href="/research-brief" className="text-indigo-600 hover:underline">Source-backed research brief →</a></div>
    <h1 className="mt-2 text-3xl font-black tracking-tight">Product comparison writer</h1><p className="mt-1 max-w-3xl text-sm text-slate-600">Create a workspace-persisted comparison article with a deterministic facts table, disclosure, source references and explicit unknowns.</p>
   </div><span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-bold text-amber-900">{revisionOfAssetId?"Revision · Original preserved":"Draft only · No publishing"}</span>
  </header>
  <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><strong>Evidence boundary:</strong> supplied HTTPS links are fetched through a bounded, DNS-pinned public transport and saved as timestamped excerpt snapshots with SHA-256 hashes. Facts remain operator supplied: exact wording found in a snapshot is not independent verification of truth, freshness, completeness, merchant identity, program eligibility or compliance. No affiliate account is authenticated and nothing is published. Missing values are shown as “Not supplied — verify”.</div>
  {error&&<div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
  {notice&&<div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}
  <section aria-label="Saved comparison drafts" className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
   <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold">Saved comparison drafts</h2><p className="mt-1 text-xs text-slate-500">Workspace-only history · {draftsTotal} saved · drafts never auto-publish</p></div><button type="button" onClick={()=>void loadDrafts()} disabled={draftsLoading} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold disabled:opacity-50">{draftsLoading?"Refreshing…":"Refresh list"}</button></div>
   {draftsError&&<p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{draftsError}</p>}
   {draftsLoading&&!drafts.length&&<p className="mt-3 text-sm text-slate-500">Loading saved drafts…</p>}
   {!draftsLoading&&!drafts.length&&!draftsError&&<p className="mt-3 text-sm text-slate-500">No comparison drafts saved in this workspace yet.</p>}
   {drafts.length>0&&<div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{drafts.map(draft=><article key={draft.asset_id} className="rounded-xl border border-slate-200 p-3">
    <h3 className="font-semibold">{draft.title}</h3><p className="mt-1 break-all font-mono text-[10px] text-slate-500">{draft.asset_id}</p>
    <p className="mt-2 text-xs text-slate-600">{draft.product_count} products · {draft.word_count} words · {draft.unknown_fact_count} unknown cells</p><p className="mt-1 text-xs text-slate-500">{draft.revision_number>1?`Revision ${draft.revision_number} · Parent ${draft.revision_of_asset_id||"unknown"}`:"Original draft"}</p>
    <p className="mt-1 text-xs text-amber-800">{draft.evidence_status.replaceAll("_"," ")} · {(draft.review_status||"pending_review").replaceAll("_"," ")} · Draft only</p>
    <button type="button" onClick={()=>void openDraft(draft.asset_id)} disabled={Boolean(openingId)} className="mt-3 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{openingId===draft.asset_id?"Opening…":"Open draft"}</button>
   </article>)}</div>}
  </section>
  <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(320px,.85fr)_minmax(0,1.15fr)]">
   <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-bold">Comparison brief</h2>{revisionOfAssetId&&<button type="button" onClick={()=>{setRevisionOfAssetId(null);setResult(null);setNotice("Separate draft mode. The loaded values will be saved as a new independent draft.");}} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold">Save as separate draft</button>}</div><form onSubmit={submit} className="mt-4 space-y-4">
    <label className={label}>Topic<input aria-label="Topic" className={field} minLength={3} maxLength={400} required value={topic} onChange={e=>setTopic(e.target.value)}/></label>
    <label className={label}>Target audience<input aria-label="Target audience" className={field} minLength={2} maxLength={300} required value={audience} onChange={e=>setAudience(e.target.value)}/></label>
    <label className={label}>Decision criteria (one per line)<textarea aria-label="Decision criteria" className={field} rows={4} maxLength={1000} value={criteriaText} onChange={e=>setCriteriaText(e.target.value)}/></label>
    <label className={label}>Products and facts (JSON, 2–5 products)<textarea id="comparison-products" aria-label="Products and facts (JSON, 2–5 products)" className={field+" font-mono text-xs leading-5"} rows={16} maxLength={20000} required spellCheck={false} value={productsJson} onChange={e=>setProductsJson(e.target.value)}/></label>
    <p className="text-xs leading-5 text-slate-500">Each product contains a name, facts object and optional HTTPS source_urls list. Up to 12 facts per product and 10 unique source URLs total. Credential-like query parameters are blocked. Each public page is size-limited; its saved wording and hash still require human review.</p>
    <label className={label}>Minimum article word target<input aria-label="Minimum article word target" className={field} type="number" min="300" max="2200" step="1" required value={minimumWords} onChange={e=>setMinimumWords(e.target.value)}/></label>
    <label className={label}>Affiliate disclosure<input aria-label="Affiliate disclosure" className={field} minLength={20} maxLength={1200} required value={disclosure} onChange={e=>setDisclosure(e.target.value)}/></label>
    <button type="submit" disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white disabled:opacity-50">{busy?(revisionOfAssetId?"Generating revision…":"Generating and saving…"):(revisionOfAssetId?"Save new revision":"Generate comparison draft")}</button>
   </form></section>
   <section className="space-y-5">
    {!result&&<div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center"><h2 className="text-lg font-bold">Your comparison will appear here</h2><p className="mt-2 text-sm leading-6 text-slate-500">The app generates editorial narrative, then builds a table from exact supplied facts. Unknown values are not guessed.</p></div>}
    {result&&<div className="space-y-5"><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
     <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-black">{result.title}</h2><p className="mt-1 break-all font-mono text-xs text-slate-500">Saved draft · {result.asset_id}</p></div><a href={"data:application/json;charset=utf-8,"+encodeURIComponent(JSON.stringify(result,null,2))} download="omni-affiliate-comparison-draft.json" className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-bold text-white">Export JSON</a></div>
     <div className="mt-4 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Products</p><p className="mt-1 text-xl font-black">{result.product_count}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Unknown table cells</p><p className="mt-1 text-xl font-black">{result.unknown_fact_count}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Draft words</p><p className="mt-1 text-xl font-black">{result.word_count}</p></div></div>
     <p className="mt-3 text-sm font-semibold text-amber-800">Evidence: {result.evidence_status.replaceAll("_"," ")} · Product facts independently verified: No · Source fetch: {result.external_product_sources_fetched?"bounded public snapshots fetched":"no successful snapshot"} · Published: No</p>
     <p className="mt-2 text-sm font-semibold text-slate-700">Review status: {(result.review_status||"pending_review").replaceAll("_"," ")} · Revision {result.revision_number} · Content SHA-256: <span className="break-all font-mono text-xs">{result.content_sha256}</span></p>
     <p className="mt-1 text-xs font-semibold text-slate-600">Saved integrity: article {(result.content_integrity_status||"unknown").replaceAll("_"," ")} · source snapshots {(result.source_snapshot_integrity_status||"unknown").replaceAll("_"," ")}</p>
     {result.integrity_review_blocked&&<p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{result.review_block_reason||"Saved article or source evidence integrity could not be verified. Create a new revision before review."}</p>}
     {result.word_count_warning&&<p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{result.word_count_warning}</p>}
     <div className="mt-5 grid gap-3 sm:grid-cols-3">
      <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs text-slate-500">Fetched snapshots</p><p className="mt-1 text-xl font-black">{result.evidence_summary.source_snapshots_fetched}</p></div>
      <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs text-slate-500">Exact wording observed</p><p className="mt-1 text-xl font-black">{result.evidence_summary.exact_text_match_count}</p></div>
      <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs text-slate-500">Wording not found</p><p className="mt-1 text-xl font-black">{result.evidence_summary.exact_text_not_found_count}</p></div>
     </div>
     <p className="mt-3 text-xs leading-5 text-slate-600">A literal match shows only that words appeared in the saved public-page snapshot for that product. It does not verify claim truth, currentness, completeness, program eligibility or compliance.</p>
     <h3 className="mt-5 font-bold">Per-fact evidence review</h3>
     <div className="mt-2 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr className="border-b border-slate-200"><th className="p-2">Product</th><th className="p-2">Fact</th><th className="p-2">Supplied value</th><th className="p-2">Snapshot check</th><th className="p-2">Source</th></tr></thead><tbody>{result.fact_evidence.map((item,index)=><tr className="border-b border-slate-100" key={item.product + "-" + item.fact_name + "-" + index}><td className="p-2">{item.product}</td><td className="p-2">{item.fact_name}</td><td className="p-2">{item.supplied_value}</td><td className="p-2">{item.evidence_status.replaceAll("_"," ")}</td><td className="p-2">{item.source_url?<a className="text-indigo-600 underline" href={item.source_url} target="_blank" rel="noreferrer">Open source</a>:"—"}</td></tr>)}</tbody></table></div>
     <h3 className="mt-5 font-bold">Source snapshots and hashes</h3>
     <div className="mt-2 space-y-2">{result.source_snapshots.map(source=><details key={source.source_id} className="rounded-xl border border-slate-200 p-3"><summary className="cursor-pointer text-sm font-semibold">{source.source_id} · {source.title||source.url} · {source.status.replaceAll("_"," ")}</summary><div className="mt-3 space-y-2 text-xs leading-5"><p>URL: <a className="break-all text-indigo-600 underline" href={source.url} target="_blank" rel="noreferrer">{source.url}</a></p><p>Captured at: {source.fetched_at}</p><p className="break-all">Excerpt SHA-256: {source.excerpt_sha256||"Unavailable"}</p>{source.detail&&<p>Fetch detail: {source.detail}</p>}<blockquote className="whitespace-normal rounded-lg bg-slate-50 p-3">{source.excerpt||"No readable snapshot text was saved."}</blockquote></div></details>)}</div>
     <section aria-label="Human editorial review" className="mt-5 rounded-xl border border-slate-200 p-4">
      <h3 className="font-bold">Human editorial review</h3>
      <p className="mt-1 text-xs leading-5 text-slate-600">The decision is bound to the content hash shown above and applies only to this immutable revision. Editorial approval does not verify product facts, affiliate eligibility, legal compliance, provider authorization, or publishing readiness.</p>
      {result.can_review&&result.review_status==="pending_review"&&result.requires_review&&<div className="mt-3 space-y-3">
       <label className={label}>Reviewer notes<textarea aria-label="Reviewer notes" className={field} rows={3} maxLength={2000} value={reviewNote} onChange={e=>setReviewNote(e.target.value)} placeholder="Optional for approval; required for changes or rejection."/></label>
       <label className="flex items-start gap-2 text-sm text-slate-700"><input aria-label="Confirm editorial review" type="checkbox" className="mt-1" checked={confirmEditorialReview} onChange={e=>setConfirmEditorialReview(e.target.checked)}/><span>I reviewed the exact saved article and its evidence warnings. This is editorial approval only, not provider/compliance approval or authorization to publish.</span></label>
       <div className="flex flex-wrap gap-2">
        <button type="button" onClick={()=>void submitReview("approve")} disabled={reviewBusy||!confirmEditorialReview} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{reviewBusy?"Saving review…":"Approve editorial draft"}</button>
        <button type="button" onClick={()=>void submitReview("request_changes")} disabled={reviewBusy||!reviewNote.trim()} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold disabled:opacity-50">Request changes</button>
        <button type="button" onClick={()=>void submitReview("reject")} disabled={reviewBusy||!reviewNote.trim()} className="rounded-lg border border-rose-300 px-3 py-2 text-xs font-semibold text-rose-700 disabled:opacity-50">Reject draft</button>
       </div>
      </div>}
      {result.can_review&&result.review_status!=="pending_review"&&<div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm"><p className="font-semibold">Decision: {(result.review_status||"unknown").replaceAll("_"," ")}</p><p className="mt-1 text-xs text-slate-600">Reviewed by {result.reviewed_by||"unknown"} on {result.reviewed_at||"unknown"}; this revision is immutable. Create a new revision for further editorial changes.</p>{result.reviewer_notes&&<p className="mt-2 whitespace-pre-wrap text-sm">{result.reviewer_notes}</p>}</div>}
      {!result.can_review&&!result.integrity_review_blocked&&<p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">A workspace owner or admin must record the editorial decision. This draft remains unpublished.</p>}
      {(result.review_history||[]).length>0&&<details className="mt-3 rounded-lg border border-slate-200 p-3"><summary className="cursor-pointer text-xs font-semibold">Review audit history ({result.review_history.length})</summary><ul className="mt-2 space-y-2">{result.review_history.map((entry,index)=><li key={entry.reviewed_at+"-"+index} className="border-t border-slate-100 pt-2 text-xs"><p className="font-semibold">{entry.review_status.replaceAll("_"," ")} · {entry.reviewed_by} · {entry.reviewed_at}</p><p className="mt-1 break-all font-mono text-[10px]">SHA-256 {entry.content_sha256}</p>{entry.reviewer_notes&&<p className="mt-1 whitespace-pre-wrap">{entry.reviewer_notes}</p>}</li>)}</ul></details>}
     </section>
     <h3 className="mt-5 font-bold">Structured comparison table</h3>
     <div className="mt-2 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr className="border-b border-slate-200"><th className="p-2">Criterion</th>{result.products.map(product=><th className="p-2" key={product.name}>{product.name}</th>)}</tr></thead><tbody>{result.comparison_table.map(row=><tr className="border-b border-slate-100" key={row.criterion}><th className="p-2">{row.criterion}</th>{row.values.map(value=><td className="p-2" key={value.product}>{value.value}</td>)}</tr>)}</tbody></table></div>
    </section><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="font-bold">Isolated HTML preview</h3><p className="mt-1 text-xs text-slate-500">The article is displayed in a sandboxed frame without script permission.</p><iframe title="Comparison article preview" sandbox="" srcDoc={result.html} className="mt-3 h-[640px] w-full rounded-xl border border-slate-200 bg-white"/></section>
    <p className="rounded-xl border border-slate-200 bg-white p-4 text-xs leading-5 text-slate-600">{result.execution_boundary}</p></div>}
   </section>
  </div>
 </div></main>;
}

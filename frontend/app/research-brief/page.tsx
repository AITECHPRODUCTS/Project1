"use client";

import {useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type Claim = {
 claim_id:string;claim:string;source_id:string|null;source_url:string|null;supporting_quote:string|null;
 evidence_status:string;exact_quote_match:boolean;evidence_note:string;editorial_review_required:boolean;
};
type SourceSnapshot = {
 source_id:string;url:string;title:string;status:string;http_status:number|null;content_type:string;
 fetched_at:string;excerpt:string;excerpt_sha256:string|null;statistics_seen_in_source:string[];
 error_type?:string;detail?:string;
};
type ResearchResult = {
 topic:string;brief:string;asset_id:string;asset_status:string;source_urls:string[];
 sources:SourceSnapshot[];observed_statistics:Array<{source_id:string;source_url:string;observed_text:string;excerpt_sha256:string}>;
 claim_ledger:Claim[];claim_ledger_summary:{claim_count:number;quote_match_count:number;unmatched_claim_count:number;parse_status:string;source_snapshot_count:number;failed_source_count:number;interpretation:string};
 claim_ledger_parse_status:string;provider:string;requires_review:boolean;publishing_started:boolean;execution_boundary:string;
};
const field="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm";
const label="block text-sm font-semibold text-slate-700";
function errorMessage(error:unknown){return error instanceof Error?error.message:"Request failed";}
export default function ResearchBriefPage(){
 const [topic,setTopic]=useState("Affiliate analytics");
 const [urlText,setUrlText]=useState("https://example.com/research-report");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [result,setResult]=useState<ResearchResult|null>(null);
 const [notice,setNotice]=useState("");
 const submit=async(e:FormEvent)=>{
  e.preventDefault();setBusy(true);setError("");setNotice("");setResult(null);
  try{
   const urls=Array.from(new Set(urlText.split(/\r?\n/).map(v=>v.trim()).filter(Boolean)));
   const response=await apiFetch<ResearchResult>("/api/content/research-brief",{method:"POST",body:JSON.stringify({topic,urls})});
   setResult(response);
   setNotice("Research brief saved as a workspace draft. Review source coverage and every claim before reuse.");
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };
 return <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10"><div className="mx-auto max-w-7xl">
  <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex flex-wrap gap-4 text-sm font-semibold"><a href="/" className="text-indigo-600 hover:underline">← Growth command</a><a href="/content-decay" className="text-indigo-600 hover:underline">Content decay review queue →</a><a href="/comparison-post" className="text-indigo-600 hover:underline">Product comparison writer →</a></div><h1 className="mt-2 text-3xl font-black tracking-tight">Source-backed research brief</h1><p className="mt-1 max-w-3xl text-sm text-slate-600">Fetch public sources, save source snapshots, and link generated claims to exact quoted text when possible.</p></div><span className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600">Draft only · No publishing</span></header>
  <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><strong>Evidence rule:</strong> a quote match only shows the text appears in the fetched source snapshot. It does not establish that a claim is true, current, complete, legally applicable, or approved. Claims without a valid exact-source quote remain unmatched for editorial review.</div>
  {error&&<div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
  {notice&&<div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}
  <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(320px,.75fr)_minmax(0,1.25fr)]">
   <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold">Research inputs</h2><form onSubmit={submit} className="mt-4 space-y-4">
    <label className={label}>Topic<input className={field} value={topic} onChange={e=>setTopic(e.target.value)} required minLength={3} maxLength={400}/></label>
    <label className={label}>Public source URLs (one per line)<textarea className={field+" font-mono text-xs"} value={urlText} onChange={e=>setUrlText(e.target.value)} rows={8} required spellCheck={false}/><span className="mt-1 block text-xs font-normal text-slate-500">Up to ten distinct public HTTP(S) URLs. Private/local destinations and credentials in URLs are rejected. The source fetch boundary also performs DNS/IP safety checks.</span></label>
    <button type="submit" disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white disabled:opacity-50">{busy?"Fetching sources and generating…":"Generate and save research brief"}</button>
   </form>
   {result&&<div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="font-bold">Saved draft</p><p className="mt-1 break-all font-mono text-xs text-slate-600">{result.asset_id}</p><p className="mt-2 text-xs text-slate-500">Provider: {result.provider} · Source snapshots: {result.claim_ledger_summary.source_snapshot_count} · Failed: {result.claim_ledger_summary.failed_source_count}</p></div>}
   </section>
   {result&&<section className="space-y-5">
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-bold">{result.topic}</h2><p className="mt-1 text-sm text-slate-500">Workspace-owned research draft · {result.asset_status}</p></div><span className="rounded-full bg-amber-100 px-3 py-1.5 text-xs font-bold text-amber-900">Review required</span></div>
     <div className="mt-4 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Claims parsed</p><p className="mt-1 text-xl font-black">{result.claim_ledger_summary.claim_count}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Quote matches</p><p className="mt-1 text-xl font-black">{result.claim_ledger_summary.quote_match_count}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Needs verification</p><p className="mt-1 text-xl font-black">{result.claim_ledger_summary.unmatched_claim_count}</p></div></div>
     <p className="mt-3 text-xs leading-5 text-slate-500">{result.claim_ledger_summary.interpretation}</p>
     <h3 className="mt-5 font-bold">Research brief</h3><pre className="mt-2 whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-700">{result.brief}</pre>
    </div>
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-lg font-bold">Claim ledger</h2><p className="mt-1 text-sm text-slate-500">Each row is matched to a fetched source only when the cited URL is in this run and the supporting quote appears in its snapshot.</p>
     {result.claim_ledger.length===0&&<p className="mt-4 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">No structured claim ledger was returned. Treat the narrative as unverified and manually review every factual statement.</p>}
     <div className="mt-4 space-y-3">{result.claim_ledger.map(claim=><article key={claim.claim_id} className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><span className="font-mono text-xs font-bold text-slate-500">{claim.claim_id} · {claim.source_id||"No matched source"}</span><span className={"rounded-full px-2.5 py-1 text-xs font-bold "+(claim.evidence_status==="quote_match"?"bg-indigo-50 text-indigo-800":"bg-amber-50 text-amber-800")}>{claim.evidence_status.replaceAll("_"," ")}</span></div>
      <p className="mt-2 text-sm font-semibold">{claim.claim}</p>
      {claim.supporting_quote&&<blockquote className="mt-3 border-l-2 border-indigo-300 pl-3 text-sm italic text-slate-600">{claim.supporting_quote}</blockquote>}
      {claim.source_url&&<a href={claim.source_url} target="_blank" rel="noopener noreferrer" className="mt-2 block break-all text-xs font-semibold text-indigo-700 underline">{claim.source_url}</a>}
      <p className="mt-2 text-xs leading-5 text-slate-500">{claim.evidence_note}</p>
     </article>)}</div>
    </div>
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-lg font-bold">Fetched source snapshots</h2><p className="mt-1 text-sm text-slate-500">Snapshots are truncated in persisted metadata for auditability; hashes identify the full excerpt used by the claim matcher.</p>
     <div className="mt-4 space-y-3">{result.sources.map(source=><article key={source.source_id} className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs font-bold">{source.source_id}</span><span className={"rounded-full px-2 py-1 text-xs font-bold "+(source.status==="fetched"?"bg-emerald-50 text-emerald-800":"bg-rose-50 text-rose-800")}>{source.status}</span></div>
      <h3 className="mt-2 font-bold">{source.title||source.url}</h3><a href={source.url} target="_blank" rel="noopener noreferrer" className="mt-1 block break-all text-xs font-semibold text-indigo-700 underline">{source.url}</a>
      <p className="mt-1 text-xs text-slate-500">HTTP {source.http_status??"—"} · {source.content_type||"unknown type"} · {source.fetched_at?new Date(source.fetched_at).toLocaleString():"fetch time unavailable"}</p>
      <p className="mt-2 break-all font-mono text-[11px] text-slate-400">SHA-256 {source.excerpt_sha256||"not available"}</p>
      {source.statistics_seen_in_source.length>0&&<p className="mt-2 text-xs text-slate-600">Observed numeric strings: {source.statistics_seen_in_source.join(", ")}</p>}
      {source.excerpt&&<details className="mt-3"><summary className="cursor-pointer text-xs font-bold text-indigo-700">Inspect fetched excerpt</summary><p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-600">{source.excerpt}</p></details>}
      {source.detail&&<p className="mt-2 text-xs text-rose-700">{source.detail}</p>}
     </article>)}</div>
    </div>
   </section>}
  </div>
 </div></main>;
}

"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {API_BASE,apiFetch} from "@/lib/api";

type BioLink = {label:string;url:string;description:string;is_affiliate:boolean};
type Publication = {provider:string;remote_id:string|null;url:string|null;status:string;published_at:string|null}|null;
type GithubPagesPublication = {status:string;repository?:string;branch?:string;content_path?:string;published_url?:string;commit_sha?:string;provider_status?:string;action_id?:string}|null;\ntype GithubPagesStatus = {configuration_ready:boolean;publish_ready:boolean;deployment_enabled:boolean;repository:string|null;branch:string|null;directory:string|null;token_configured:boolean;provider_connection_verified:boolean;site_source_verified:boolean;message:string};\ntype PageAsset = {id:string;title:string;status:string;source_urls:string[];link_count:number;affiliate_link_count:number;page_sha256:string;created_at:string|null;publication:Publication;github_pages_publication?:GithubPagesPublication;preview_url?:string;execution_boundary:string};
type PageList = {count:number;data:PageAsset[]};
const field="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm";
const label="block text-sm font-semibold text-slate-700";
const initialLinks:BioLink[]=[
 {label:"Read the analytics guide",url:"https://example.com/analytics",description:"A practical introduction to product analytics.",is_affiliate:false},
 {label:"Recommended creator tool",url:"https://example.com/creator-tool",description:"A tool I may earn a commission from.",is_affiliate:true},
];
function errorMessage(error:unknown){return error instanceof Error?error.message:"Request failed";}
export default function BioLinksPage(){
 const [pages,setPages]=useState<PageAsset[]>([]);\n const [githubPagesStatus,setGithubPagesStatus]=useState<GithubPagesStatus|null>(null);
 const [title,setTitle]=useState("Creator resource links");
 const [headline,setHeadline]=useState("Helpful tools and resources");
 const [subheadline,setSubheadline]=useState("A curated list of resources and products worth exploring.");
 const [linksJson,setLinksJson]=useState(JSON.stringify(initialLinks,null,2));
 const [disclosure,setDisclosure]=useState("Disclosure: I may earn a commission from qualifying purchases through affiliate links.");
 const [footer,setFooter]=useState("Independent recommendations. Check each provider's current terms.");
 const [provider,setProvider]=useState<"wordpress"|"ghost">("wordpress");
 const [canonicalUrl,setCanonicalUrl]=useState("https://example.com/my-links");
 const [jurisdictions,setJurisdictions]=useState("US, GB");
 const [confirmLive,setConfirmLive]=useState(false);
 const [reviewNotes,setReviewNotes]=useState("");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const load=useCallback(async()=>{setError("");try{const result=await apiFetch<PageList>("/api/distribution/bio-links?limit=50");setPages(result.data||[]);}catch(e){setError(errorMessage(e));}try{const readiness=await apiFetch<GithubPagesStatus>("/api/distribution/github-pages/status");setGithubPagesStatus(readiness);}catch{setGithubPagesStatus(null);}},[]);
 useEffect(()=>{void load();},[load]);
 const create=async(e:FormEvent)=>{
  e.preventDefault();setBusy(true);setError("");setNotice("");
  try{
   const links=JSON.parse(linksJson) as BioLink[];
   const result=await apiFetch<PageAsset>("/api/distribution/bio-links",{method:"POST",body:JSON.stringify({
    title,headline,subheadline,links,affiliate_disclosure:disclosure,footer_note:footer
   })});
   setNotice(`Saved ${result.title} as a draft · SHA-256 ${result.page_sha256.slice(0,12)}…`);
   await load();
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };

 const deployGithubPages=async(asset:PageAsset)=>{
  setBusy(true);setError("");setNotice("");
  try{
   const result=await apiFetch<{deployment_status:string;published_url:string;repository:string;branch:string;content_path:string}>(
    "/api/distribution/github-pages/deploy",
    {method:"POST",headers:{"Idempotency-Key":`github-pages-${crypto.randomUUID()}`},body:JSON.stringify({
     asset_id:asset.id,target_jurisdictions:jurisdictions.split(",").map(v=>v.trim()).filter(Boolean),confirm_live_publish:true
    })}
   );
   setNotice(`GitHub Pages ${result.deployment_status}: ${result.repository} · ${result.branch}/${result.content_path} · ${result.published_url}`);
   await load();
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };
 const reconcileGithubPages=async(asset:PageAsset)=>{
  setBusy(true);setError("");setNotice("");
  try{
   const result=await apiFetch<{deployment_status?:string;status:string;message?:string}>(
    `/api/distribution/github-pages/${encodeURIComponent(asset.id)}/reconcile`,
    {method:"POST",body:JSON.stringify({})}
   );
   setNotice(result.deployment_status==="published"?"GitHub Pages outcome verified against the configured remote file.":result.message||"Remote outcome remains unresolved; inspect the configured branch history before retrying.");
   await load();
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };
 const publish=async(asset:PageAsset,status:"draft"|"publish")=>{
  setBusy(true);setError("");setNotice("");
  try{
   const result=await apiFetch<{asset_status:string;provider_result:{url?:string;status?:string}}>(
    `/api/distribution/bio-links/${encodeURIComponent(asset.id)}/publish`,
    {method:"POST",headers:{"Idempotency-Key":`bio-link-${crypto.randomUUID()}`},body:JSON.stringify({
      provider,canonical_url:canonicalUrl,target_jurisdictions:jurisdictions.split(",").map(v=>v.trim()).filter(Boolean),
      status,confirm_live_publish:status==="publish"&&confirmLive,disclosure,tags:["bio-link","affiliate-resources"]
    })}
   );
   const url=result.provider_result?.url;
   setNotice(`${asset.title}: ${result.asset_status}${url?` · ${url}`:""}`);
   await load();
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };
 return <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10"><div className="mx-auto max-w-7xl">
  <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between"><div><a className="text-sm font-semibold text-indigo-600 hover:underline" href="/">← Growth command</a><h1 className="mt-2 text-3xl font-black tracking-tight">Bio-link studio</h1><p className="mt-1 max-w-3xl text-sm text-slate-600">Create disclosure-aware link pages, add transparent UTM attribution, preview the generated HTML, and optionally send it to a configured WordPress or Ghost account.</p></div><button onClick={()=>void load()} disabled={busy} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold disabled:opacity-50">Refresh drafts</button></header>
  <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><strong>Publishing gates:</strong> CMS writes require platform-admin permission and an idempotency key. Live publishing also requires explicit confirmation, CMS execution configuration, and a current human-reviewed compliance assessment for each target jurisdiction. Link pages are stored as drafts until sent to a provider.</div>
  {error&&<div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
  {notice&&<div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}
  <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(340px,.9fr)_minmax(0,1.1fr)]">
   <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold">Build page</h2><p className="mt-1 text-sm text-slate-500">Only generated text and anchor elements are emitted; user-supplied scripts and HTML are escaped.</p>
    <form onSubmit={create} className="mt-4 space-y-4">
     <label className={label}>Page title<input className={field} value={title} onChange={e=>setTitle(e.target.value)} required minLength={3}/></label>
     <label className={label}>Headline<input className={field} value={headline} onChange={e=>setHeadline(e.target.value)} required minLength={3}/></label>
     <label className={label}>Subheadline<textarea className={field} rows={2} value={subheadline} onChange={e=>setSubheadline(e.target.value)}/></label>
     <label className={label}>Links JSON<textarea className={field+" font-mono text-xs"} rows={12} value={linksJson} onChange={e=>setLinksJson(e.target.value)} required spellCheck={false}/><span className="mt-1 block text-xs font-normal text-slate-500">Each object: label, url, description, is_affiliate. Use a clear disclosure when any link is an affiliate link.</span></label>
     <label className={label}>Affiliate disclosure<textarea className={field} rows={3} value={disclosure} onChange={e=>setDisclosure(e.target.value)}/></label>
     <label className={label}>Footer note<input className={field} value={footer} onChange={e=>setFooter(e.target.value)}/></label>
     <button type="submit" disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white hover:bg-indigo-700 disabled:opacity-50">{busy?"Saving…":"Validate and save draft"}</button>
    </form>
   </section>
   <section className="space-y-4">
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold">CMS publish settings</h2><p className="mt-1 text-sm text-slate-500">Publishing reuses the shared CMS adapters. Draft delivery does not make a public page; choose live publish only after compliance review and provider configuration.</p>
     <div className="mt-4 grid gap-3 sm:grid-cols-2"><label className={label}>Provider<select className={field} value={provider} onChange={e=>setProvider(e.target.value as "wordpress"|"ghost")}><option value="wordpress">WordPress</option><option value="ghost">Ghost</option></select></label><label className={label}>CMS site URL for canonical check<input className={field} type="url" value={canonicalUrl} onChange={e=>setCanonicalUrl(e.target.value)} required/></label></div>
     <label className={label+" mt-3"}>Target jurisdictions<input className={field} value={jurisdictions} onChange={e=>setJurisdictions(e.target.value)} placeholder="US, GB, EU"/></label>
     <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700"><strong>GitHub Pages:</strong> {githubPagesStatus?.publish_ready?<>Configured target <code>{githubPagesStatus.repository}</code> on <code>{githubPagesStatus.branch}</code>{githubPagesStatus.directory?<> at <code>{githubPagesStatus.directory}/</code></>:null}. The remote Pages branch and token are verified during deployment.</>:githubPagesStatus?.message||"Configuration readiness is unavailable to this account; a platform super admin must check the server-side GitHub Pages settings."}</div>
     <label className="mt-3 flex items-start gap-2 text-sm text-slate-700"><input type="checkbox" checked={confirmLive} onChange={e=>setConfirmLive(e.target.checked)} className="mt-1"/>I confirm a live CMS or GitHub Pages publish is intentional and have reviewed the page, destinations, and jurisdiction compliance approval.</label>
    </div>
    <h2 className="text-xl font-bold">Saved pages ({pages.length})</h2>
    {pages.length===0&&<div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">No bio-link pages in this workspace yet.</div>}
    {pages.map(asset=><article key={asset.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
     <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-bold">{asset.title}</h3><p className="mt-1 text-xs font-mono text-slate-500">{asset.link_count} links · {asset.affiliate_link_count} affiliate · {asset.status}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{asset.page_sha256.slice(0,12)}…</span></div>
     <div className="mt-3 flex flex-wrap gap-2"><a className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold text-indigo-700 hover:bg-indigo-50" href={API_BASE+`/api/distribution/bio-links/${asset.id}/preview`} target="_blank" rel="noopener noreferrer">Open preview</a>
      {asset.status!=="published"&&asset.status!=="publish_outcome_unknown"&&<><button type="button" disabled={busy} onClick={()=>void publish(asset,"draft")} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold disabled:opacity-50">Send as CMS draft</button><button type="button" disabled={busy||!confirmLive} onClick={()=>void publish(asset,"publish")} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-40">Live publish</button></>}
     </div>
     {asset.publication?.url&&<p className="mt-3 break-all text-sm text-emerald-700">Provider URL: {asset.publication.url}</p>}
      {asset.github_pages_publication?.status==="outcome_unknown"&&<div className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">GitHub Pages outcome is unresolved. Reconcile the remote HTML before retrying.</div>}
      {asset.github_pages_publication?.status==="published"&&asset.github_pages_publication.published_url&&<p className="mt-2 break-all text-sm text-emerald-700">GitHub Pages: {asset.github_pages_publication.published_url} · {asset.github_pages_publication.provider_status}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
       <button type="button" disabled={busy||!githubPagesStatus?.publish_ready||!confirmLive} onClick={()=>void deployGithubPages(asset)} className="rounded-lg border border-indigo-200 px-3 py-2 text-sm font-bold text-indigo-700 disabled:opacity-40">Deploy to GitHub Pages</button>
       {asset.github_pages_publication?.status==="outcome_unknown"&&<button type="button" disabled={busy} onClick={()=>void reconcileGithubPages(asset)} className="rounded-lg border border-amber-300 px-3 py-2 text-sm font-bold text-amber-800 disabled:opacity-40">Reconcile GitHub Pages</button>}
      </div>
    </article>)}
   </section>
  </div>
 </div></main>;
}

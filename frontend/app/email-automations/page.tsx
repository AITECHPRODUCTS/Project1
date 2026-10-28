"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type Node = {
 id:string;kind:"email"|"branch"|"stop";subject?:string;body_text?:string;delay_days?:number;
 next_step_id?:string;has_affiliate_links?:boolean;affiliate_disclosure?:string;
 condition?:"purchased"|"not_purchased"|"engaged"|"not_engaged";true_step_id?:string;false_step_id?:string;
};
type Graph = {schema_version:number;name:string;description:string;version:string;entry_step_id:string;target_jurisdictions:string[];nodes:Node[]};
type Simulation = {graph_sha256:string;path:string[];emails:Array<{step_id:string;subject:string;body_text:string;scheduled_offset_days:number;affiliate_disclosure_required:boolean;affiliate_disclosure:string|null}>;stopped:boolean;stop_reason:string;provider_calls_made:number;messages_scheduled:number};
type Automation = {
 id:string;name:string;description:string;version:string;status:string;entry_step_id:string;node_count:number;
 validation_report:{email_step_count:number;branch_count:number;stop_count:number;warnings:string[]};
 graph_sha256:string;created_by:string;reviewed_by:string|null;reviewed_at:string|null;reviewer_notes:string|null;
 graph?:Graph;execution_boundary:string;
};
type ListResult={count:number;data:Automation[]};
const field="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm";
const label="block text-sm font-semibold text-slate-700";
const initialGraph:Graph={
 schema_version:1,name:"Creator nurture",description:"A consent-based email journey with purchase and engagement branches.",version:"1.0.0",entry_step_id:"welcome",target_jurisdictions:["US"],
 nodes:[
  {id:"welcome",kind:"email",subject:"Your guide is ready",body_text:"Thanks for requesting the guide. Start with one practical step.",delay_days:0,next_step_id:"purchase-check"},
  {id:"purchase-check",kind:"branch",condition:"purchased",true_step_id:"purchased-stop",false_step_id:"engagement-check"},
  {id:"engagement-check",kind:"branch",condition:"engaged",true_step_id:"engaged-followup",false_step_id:"quiet-followup"},
  {id:"engaged-followup",kind:"email",subject:"A practical next step",body_text:"Apply the guide to one small task and evaluate the result.",delay_days:2,next_step_id:"done"},
  {id:"quiet-followup",kind:"email",subject:"A simple checklist",body_text:"Use this short checklist to compare your next steps.",delay_days:3,next_step_id:"done"},
  {id:"purchased-stop",kind:"stop"},
  {id:"done",kind:"stop"}
 ]
};
function pretty(value:unknown){return JSON.stringify(value,null,2);}
function errorMessage(error:unknown){return error instanceof Error?error.message:"Request failed";}
export default function EmailAutomationsPage(){
 const [items,setItems]=useState<Automation[]>([]);
 const [name,setName]=useState(initialGraph.name);
 const [description,setDescription]=useState(initialGraph.description);
 const [version,setVersion]=useState(initialGraph.version);
 const [targetJurisdictions,setTargetJurisdictions]=useState("US");
 const [entry,setEntry]=useState(initialGraph.entry_step_id);
 const [nodesJson,setNodesJson]=useState(pretty(initialGraph.nodes));
 const [selected,setSelected]=useState<Automation|null>(null);
 const [context,setContext]=useState({purchased:false,engaged:true,consent_granted:true,unsubscribed:false});
 const [simulation,setSimulation]=useState<Simulation|null>(null);
 const [reviewNotes,setReviewNotes]=useState("");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const load=useCallback(async()=>{
  setError("");
  try{const result=await apiFetch<ListResult>("/api/email/automations?limit=100");setItems(result.data||[]);}
  catch(e){setError(errorMessage(e));}
 },[]);
 useEffect(()=>{void load();},[load]);
 const create=async(e:FormEvent)=>{
  e.preventDefault();setBusy(true);setError("");setNotice("");
  try{
   const nodes=JSON.parse(nodesJson) as Node[];
   const result=await apiFetch<Automation>("/api/email/automations",{method:"POST",body:JSON.stringify({
    name,description,version,entry_step_id:entry,target_jurisdictions:targetJurisdictions.split(",").map(v=>v.trim().toUpperCase()).filter(Boolean),nodes
   })});
   setSelected(result);setSimulation(null);setNotice("Saved graph as review-required version "+result.version+". It has not been activated or sent.");
   await load();
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };
 const selectItem=async(item:Automation)=>{
  setBusy(true);setError("");setSimulation(null);
  try{const result=await apiFetch<Automation>("/api/email/automations/"+encodeURIComponent(item.id));setSelected(result);}
  catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };
 const simulate=async(item:Automation)=>{
  setBusy(true);setError("");setNotice("");
  try{
   const result=await apiFetch<{simulation:Simulation}>(`/api/email/automations/${encodeURIComponent(item.id)}/simulate`,{method:"POST",body:JSON.stringify(context)});
   setSimulation(result.simulation);
   setNotice("Simulation finished without queueing or sending email.");
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };
 const review=async(item:Automation,decision:"approve"|"reject")=>{
  setBusy(true);setError("");setNotice("");
  try{
   const result=await apiFetch<Automation>(`/api/email/automations/${encodeURIComponent(item.id)}/review`,{method:"POST",body:JSON.stringify({
    decision,confirm_graph_reviewed:decision==="approve",reviewer_notes:reviewNotes
   })});
   setSelected(result);setReviewNotes("");setNotice("Review recorded: "+result.status+". This does not activate delivery.");
   await load();
  }catch(e){setError(errorMessage(e));}
  finally{setBusy(false);}
 };
 return <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10"><div className="mx-auto max-w-7xl">
  <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between"><div><a href="/" className="text-sm font-semibold text-indigo-600 hover:underline">← Growth command</a><h1 className="mt-2 text-3xl font-black tracking-tight">Branching email automation</h1><p className="mt-1 max-w-3xl text-sm text-slate-600">Build declarative opt-in nurture graphs, branch on purchase or engagement, and simulate paths before a future delivery integration.</p></div><button type="button" onClick={()=>void load()} disabled={busy} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold disabled:opacity-50">Refresh automations</button></header>
  <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><strong>Execution boundary:</strong> this feature validates, stores, reviews and simulates a branch graph only. It does not queue or send email. No-consent and unsubscribed test contexts stop before any message step. Existing scheduled email sending, consent capture and unsubscribe suppression remain the active delivery path.</div>
  {error&&<div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
  {notice&&<div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}
  <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(340px,.9fr)_minmax(0,1.1fr)]">
   <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold">Create graph version</h2><form onSubmit={create} className="mt-4 space-y-4">
    <label className={label}>Automation name<input className={field} value={name} onChange={e=>setName(e.target.value)} required minLength={3} maxLength={180}/></label>
    <div className="grid gap-3 sm:grid-cols-2"><label className={label}>Semantic version<input className={field} value={version} onChange={e=>setVersion(e.target.value)} pattern="(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?" required/></label><label className={label}>Entry step ID<input className={field} value={entry} onChange={e=>setEntry(e.target.value)} required pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,63}"/></label></div>
    <label className={label}>Target jurisdictions<input className={field} value={targetJurisdictions} onChange={e=>setTargetJurisdictions(e.target.value)} placeholder="US, GB, IN" required/><span className="mt-1 block text-xs font-normal text-slate-500">An approved graph is checked against a current email-marketing assessment for all listed jurisdictions before each provider send.</span></label>
    <label className={label}>Purpose and audience<textarea className={field} rows={2} value={description} onChange={e=>setDescription(e.target.value)} required minLength={10}/></label>
    <label className={label}>Branch graph JSON<textarea className={field+" font-mono text-xs"} rows={22} value={nodesJson} onChange={e=>setNodesJson(e.target.value)} required spellCheck={false}/><span className="mt-1 block text-xs font-normal text-slate-500">Nodes are email, branch (purchased / not_purchased / engaged / not_engaged), or stop. All nodes must be reachable and the graph must be acyclic.</span></label>
    <button type="submit" disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white disabled:opacity-50">{busy?"Saving…":"Validate and save review-required graph"}</button>
   </form></section>
   <section className="space-y-4">
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-end justify-between gap-3"><div><h2 className="text-xl font-bold">Saved automations</h2><p className="mt-1 text-sm text-slate-500">{items.length} workspace version(s)</p></div></div>
     {items.length===0&&<p className="mt-4 rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No email automation graphs yet.</p>}
     <div className="mt-4 space-y-3">{items.map(item=><article key={item.id} className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-xs text-indigo-700">{item.version} · {item.node_count} nodes · {item.graph_sha256.slice(0,12)}…</p><h3 className="mt-1 font-bold">{item.name}</h3><p className="mt-1 text-sm text-slate-600">{item.description}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{item.status.replaceAll("_"," ")}</span></div>
      <div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={()=>void selectItem(item)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold">Inspect graph</button><button type="button" disabled={busy} onClick={()=>void simulate(item)} className="rounded-lg border border-indigo-200 px-3 py-2 text-sm font-bold text-indigo-700 disabled:opacity-50">Simulate current context</button>{item.status!=="approved"&&item.status!=="rejected"&&<button type="button" disabled={busy} onClick={()=>void review(item,"approve")} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-50">Review & approve</button>}</div>
     </article>)}</div>
    </div>
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-lg font-bold">Simulation inputs</h2><p className="mt-1 text-sm text-slate-500">Select a saved graph above, set a sample lead state, then simulate the branch path.</p>
     <div className="mt-4 grid gap-3 sm:grid-cols-2">{[
      ["purchased","Sample lead purchased"],["engaged","Sample lead engaged"],["consent_granted","Consent granted"],["unsubscribed","Recipient unsubscribed"]
     ].map(([key,title])=><label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={context[key as keyof typeof context]} onChange={e=>setContext(v=>({...v,[key]:e.target.checked}))}/>{title}</label>)}</div>
     {selected&&<div className="mt-4 rounded-xl bg-slate-50 p-3"><p className="font-bold">{selected.name} · v{selected.version}</p><p className="mt-1 text-xs text-slate-500">Status: {selected.status} · {selected.node_count} nodes</p><div className="mt-3 flex flex-wrap gap-2"><button type="button" disabled={busy} onClick={()=>void simulate(selected)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-50">Run simulation</button>{selected.status!=="approved"&&selected.status!=="rejected"&&<button type="button" disabled={busy} onClick={()=>void review(selected,"reject")} className="rounded-lg border border-rose-200 px-3 py-2 text-sm font-bold text-rose-700 disabled:opacity-50">Reject graph</button>}</div>
     <label className={label+" mt-3"}>Reviewer notes<textarea className={field} rows={2} value={reviewNotes} onChange={e=>setReviewNotes(e.target.value)}/></label>
     </div>}
     {simulation&&<div className="mt-4 rounded-xl border border-slate-200 p-4"><h3 className="font-bold">Simulated path (no delivery side effects)</h3><div className="mt-3 flex flex-wrap items-center gap-2">{simulation.path.map((node,index)=><span key={node+index} className="flex items-center gap-2"><span className="rounded-lg bg-indigo-50 px-3 py-2 text-xs font-bold text-indigo-800">{node}</span>{index<simulation.path.length-1&&<span className="text-slate-400">→</span>}</span>)}</div><div className="mt-3 space-y-2">{simulation.emails.map(email=><div key={email.step_id} className="rounded-lg bg-slate-50 p-3"><p className="font-bold">{email.subject}</p><p className="mt-1 text-xs text-slate-500">Send offset: day {email.scheduled_offset_days} · node {email.step_id}</p><p className="mt-2 whitespace-pre-wrap text-sm">{email.body_text}</p>{email.affiliate_disclosure_required&&<p className="mt-2 text-xs text-amber-800">Affiliate disclosure required: {email.affiliate_disclosure}</p>}</div>)}</div><p className="mt-3 text-xs text-slate-500">Reason: {simulation.stop_reason}; provider calls: {simulation.provider_calls_made}; messages scheduled: {simulation.messages_scheduled}</p></div>}
    </div>
   </section>
  </div>
 </div></main>;
}

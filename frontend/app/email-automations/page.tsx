"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type Node = {
 id:string;
 kind:"email"|"branch"|"stop";
 subject?:string;
 body_text?:string;
 delay_days?:number;
 next_step_id?:string;
 has_affiliate_links?:boolean;
 affiliate_disclosure?:string;
 condition?:"purchased"|"not_purchased"|"engaged"|"not_engaged";
 true_step_id?:string;
 false_step_id?:string;
};
type Graph = {
 schema_version:number;
 name:string;
 description:string;
 version:string;
 entry_step_id:string;
 target_jurisdictions:string[];
 nodes:Node[];
};
type Simulation = {
 graph_sha256:string;
 path:string[];
 emails:Array<{
  step_id:string;
  subject:string;
  body_text:string;
  scheduled_offset_days:number;
  affiliate_disclosure_required:boolean;
  affiliate_disclosure:string|null;
 }>;
 stopped:boolean;
 stop_reason:string;
 provider_calls_made:number;
 messages_scheduled:number;
};
type Automation = {
 id:string;
 name:string;
 description:string;
 version:string;
 status:string;
 entry_step_id:string;
 node_count:number;
 validation_report:{
  email_step_count:number;
  branch_count:number;
  stop_count:number;
  warnings:string[];
 };
 graph_sha256:string;
 created_by:string;
 reviewed_by:string|null;
 reviewed_at:string|null;
 reviewer_notes:string|null;
 graph?:Graph;
 execution_boundary:string;
};
type ListResult={count:number;data:Automation[]};

const field="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100";
const label="block text-sm font-semibold text-slate-700";
const smallButton="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40";
const initialGraph:Graph={
 schema_version:1,
 name:"Creator nurture",
 description:"A consent-based email journey with purchase and engagement branches.",
 version:"1.0.0",
 entry_step_id:"welcome",
 target_jurisdictions:["US"],
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
const conditionLabels:Record<NonNullable<Node["condition"]>,string>={
 purchased:"Has purchased",
 not_purchased:"Has not purchased",
 engaged:"Has engaged",
 not_engaged:"Has not engaged"
};
function errorMessage(error:unknown){return error instanceof Error?error.message:"Request failed";}
function nextPatchVersion(version:string){
 const match=/^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$/.exec(version);
 if(!match)return "1.0.1";
 return match[1]+"."+match[2]+"."+(Number(match[3])+1);
}
function nodeTypeLabel(node:Node){
 return node.kind==="email"?"Email step":node.kind==="branch"?"Decision branch":"Stop";
}

export default function EmailAutomationsPage(){
 const [items,setItems]=useState<Automation[]>([]);
 const [name,setName]=useState(initialGraph.name);
 const [description,setDescription]=useState(initialGraph.description);
 const [version,setVersion]=useState(initialGraph.version);
 const [targetJurisdictions,setTargetJurisdictions]=useState("US");
 const [entry,setEntry]=useState(initialGraph.entry_step_id);
 const [nodes,setNodes]=useState<Node[]>(()=>initialGraph.nodes.map(node=>({...node})));
 const [selected,setSelected]=useState<Automation|null>(null);
 const [context,setContext]=useState({purchased:false,engaged:true,consent_granted:true,unsubscribed:false});
 const [simulation,setSimulation]=useState<Simulation|null>(null);
 const [reviewNotes,setReviewNotes]=useState("");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");

 const load=useCallback(async()=>{
  try{
   const result=await apiFetch<ListResult>("/api/email/automations?limit=100");
   setItems(result.data||[]);
  }catch(e){
   setError(errorMessage(e));
  }
 },[]);
 useEffect(()=>{void load();},[load]);

 const updateNode=(nodeId:string,patch:Partial<Node>)=>{
  setNodes(current=>current.map(node=>node.id===nodeId?{...node,...patch}:node));
 };
 const uniqueNodeId=(kind:"email"|"branch")=>{
  const prefix=kind==="email"?"email":"branch";
  let index=1;
  while(nodes.some(node=>node.id===prefix+"-"+index))index+=1;
  return prefix+"-"+index;
 };
 const addEmailStep=()=>{
  const predecessor=[...nodes].reverse().find(node=>{
   if(node.kind!=="email"||!node.next_step_id)return false;
   return nodes.some(target=>target.id===node.next_step_id&&target.kind==="stop");
  });
  if(!predecessor||!predecessor.next_step_id){
   setError("To insert an email step, first connect an existing email step to a stop node.");
   return;
  }
  const id=uniqueNodeId("email");
  const destination=predecessor.next_step_id;
  const inserted:Node={
   id,kind:"email",subject:"A helpful follow-up",body_text:"Add useful, accurate information relevant to the subscriber's request.",
   delay_days:1,next_step_id:destination,has_affiliate_links:false,affiliate_disclosure:""
  };
  setNodes(current=>current.map(node=>node.id===predecessor.id?{...node,next_step_id:id}:node).concat(inserted));
  setError("");
  setNotice("Added "+id+" into the existing "+predecessor.id+" → "+destination+" route.");
 };
 const addBranch=()=>{
  const predecessor=[...nodes].reverse().find(node=>{
   if(node.kind!=="email"||!node.next_step_id)return false;
   return nodes.some(target=>target.id===node.next_step_id&&target.kind==="stop");
  });
  if(!predecessor||!predecessor.next_step_id){
   setError("To insert a decision branch, connect an existing email step to a stop node first.");
   return;
  }
  const originalTarget=predecessor.next_step_id;
  const alternative=nodes.find(node=>node.kind==="stop"&&node.id!==originalTarget)?.id||originalTarget;
  const id=uniqueNodeId("branch");
  const inserted:Node={
   id,kind:"branch",condition:"purchased",true_step_id:originalTarget,false_step_id:alternative
  };
  setNodes(current=>current.map(node=>node.id===predecessor.id?{...node,next_step_id:id}:node).concat(inserted));
  setError("");
  setNotice("Added "+id+" after "+predecessor.id+". Review both decision destinations before saving.");
 };
 const referencedBy=(nodeId:string)=>{
  return nodes.some(node=>node.kind==="email"
   ?node.next_step_id===nodeId
   :node.kind==="branch"&&(node.true_step_id===nodeId||node.false_step_id===nodeId));
 };
 const removeNode=(nodeId:string)=>{
  if(nodeId===entry||referencedBy(nodeId)){
   setError("This step is connected to the graph. Reconnect every incoming route before removing it.");
   return;
  }
  setNodes(current=>current.filter(node=>node.id!==nodeId));
  setError("");
  setNotice("Removed the unreferenced step "+nodeId+".");
 };
 const loadAsNewVersion=()=>{
  if(!selected?.graph)return;
  setName(selected.name);
  setDescription(selected.description);
  setVersion(nextPatchVersion(selected.version));
  setTargetJurisdictions(selected.graph.target_jurisdictions.join(", "));
  setEntry(selected.graph.entry_step_id);
  setNodes(selected.graph.nodes.map(node=>({...node})));
  setSelected(null);
  setSimulation(null);
  setError("");
  setNotice("Loaded "+selected.name+" as a new draft version. Save it to create a separate immutable graph version.");
 };
 const create=async(e:FormEvent)=>{
  e.preventDefault();
  setBusy(true);setError("");setNotice("");setSimulation(null);
  try{
   const result=await apiFetch<Automation>("/api/email/automations",{
    method:"POST",
    body:JSON.stringify({
     name,description,version,entry_step_id:entry,
     target_jurisdictions:targetJurisdictions.split(",").map(value=>value.trim().toUpperCase()).filter(Boolean),
     nodes
    })
   });
   setSelected(result);
   setNotice("Saved graph as review-required version "+result.version+". It has not been activated or sent.");
   await load();
  }catch(e){
   setError(errorMessage(e));
  }finally{
   setBusy(false);
  }
 };
 const selectItem=async(item:Automation)=>{
  setBusy(true);setError("");setSimulation(null);
  try{
   const result=await apiFetch<Automation>("/api/email/automations/"+encodeURIComponent(item.id));
   setSelected(result);
  }catch(e){
   setError(errorMessage(e));
  }finally{
   setBusy(false);
  }
 };
 const simulate=async(item:Automation)=>{
  setBusy(true);setError("");setNotice("");
  try{
   const result=await apiFetch<{simulation:Simulation}>(
    "/api/email/automations/"+encodeURIComponent(item.id)+"/simulate",
    {method:"POST",body:JSON.stringify(context)}
   );
   setSimulation(result.simulation);
   setNotice("Simulation finished without queueing or sending email.");
  }catch(e){
   setError(errorMessage(e));
  }finally{
   setBusy(false);
  }
 };
 const review=async(item:Automation,decision:"approve"|"reject")=>{
  setBusy(true);setError("");setNotice("");
  try{
   const result=await apiFetch<Automation>(
    "/api/email/automations/"+encodeURIComponent(item.id)+"/review",
    {method:"POST",body:JSON.stringify({
     decision,confirm_graph_reviewed:decision==="approve",reviewer_notes:reviewNotes
    })}
   );
   setSelected(result);setReviewNotes("");
   setNotice("Review recorded: "+result.status+". This does not bypass consent, unsubscribe or per-send compliance checks.");
   await load();
  }catch(e){
   setError(errorMessage(e));
  }finally{
   setBusy(false);
  }
 };
 const nodeOptions=(nodeId:string)=>
  nodes.filter(node=>node.id!==nodeId).map(node=>({id:node.id,label:node.id+" · "+nodeTypeLabel(node)}));

 return <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10">
  <div className="mx-auto max-w-7xl">
   <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
    <div>
     <a href="/" className="text-sm font-semibold text-indigo-600 hover:underline">← Growth command</a>
     <h1 className="mt-2 text-3xl font-black tracking-tight">Branching email automation</h1>
     <p className="mt-1 max-w-3xl text-sm text-slate-600">Design a visual, versioned email journey. Connect email steps, purchase/engagement decisions and terminal stops, then validate and simulate the actual branch paths.</p>
    </div>
    <button type="button" onClick={()=>void load()} disabled={busy} className={smallButton}>Refresh automations</button>
   </header>

   <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
    <strong>Execution boundary:</strong> the editor only builds, validates, saves, reviews and simulates graphs. An approved graph can enter the existing email queue after explicit double opt-in; each send still checks consent, unsubscribe/suppression, immutable graph checksum, current jurisdictional compliance, worker controls and provider configuration. Editing or simulating never sends email.
   </div>
   {error&&<div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
   {notice&&<div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}

   <div className="mt-6 grid gap-6 2xl:grid-cols-[minmax(0,1.3fr)_minmax(340px,.7fr)]">
    <section className="space-y-5">
     <form data-testid="email-automation-form" onSubmit={create} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
       <div>
        <p className="text-xs font-black uppercase tracking-[.18em] text-indigo-600">Visual journey builder</p>
        <h2 className="mt-1 text-xl font-bold">Create graph version</h2>
        <p className="mt-1 text-sm text-slate-500">Each card represents a persisted graph node. Branches show distinct true and false routes.</p>
       </div>
       <div className="flex flex-wrap gap-2">
        <button type="button" data-testid="add-email-step" onClick={addEmailStep} disabled={busy} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-40">+ Add email step</button>
        <button type="button" data-testid="add-branch-step" onClick={addBranch} disabled={busy} className={smallButton}>+ Add decision</button>
       </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
       <label className={label}>Automation name
        <input className={field} value={name} onChange={e=>setName(e.target.value)} required minLength={3} maxLength={180}/>
       </label>
       <label className={label}>Semantic version
        <input className={field} value={version} onChange={e=>setVersion(e.target.value)} pattern="(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?" required/>
       </label>
       <label className={label+" sm:col-span-2"}>Purpose and audience
        <textarea className={field} rows={2} value={description} onChange={e=>setDescription(e.target.value)} required minLength={10} maxLength={3000}/>
       </label>
       <label className={label}>Target jurisdictions
        <input className={field} value={targetJurisdictions} onChange={e=>setTargetJurisdictions(e.target.value)} placeholder="US, GB, IN" required/>
        <span className="mt-1 block text-xs font-normal text-slate-500">Use country or region codes. A current email-marketing assessment is required before delivery.</span>
       </label>
       <label className={label}>Entry step
        <select className={field} data-testid="graph-entry-step" value={entry} onChange={e=>setEntry(e.target.value)}>
         {nodes.map(node=><option key={node.id} value={node.id}>{node.id} · {nodeTypeLabel(node)}</option>)}
        </select>
       </label>
      </div>

      <div data-testid="visual-graph-editor" className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-3 sm:p-4">
       <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
         <h3 className="font-bold">Journey map</h3>
         <p className="text-xs text-slate-500">{nodes.length} nodes · {nodes.filter(node=>node.kind==="email").length} email steps · {nodes.filter(node=>node.kind==="branch").length} decisions · {nodes.filter(node=>node.kind==="stop").length} stops</p>
        </div>
        <span className="rounded-full border border-indigo-100 bg-white px-3 py-1 text-xs font-semibold text-indigo-700">Entry: {entry}</span>
       </div>
       <div className="mt-4 space-y-3">
        {nodes.map((node,index)=>{
         const options=nodeOptions(node.id);
         const canRemove=node.id!==entry&&!referencedBy(node.id);
         const downstream=node.kind==="email"
          ?node.next_step_id
          :node.kind==="branch"
           ?"True → "+(node.true_step_id||"unset")+" · False → "+(node.false_step_id||"unset")
           :"Terminal";
         return <article key={node.id} data-testid={"node-card-"+node.id} className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-white px-3 py-3 sm:px-4">
           <div className="flex min-w-0 items-center gap-2">
            <span className={"grid h-7 w-7 shrink-0 place-items-center rounded-lg text-xs font-black "+(node.kind==="email"?"bg-indigo-100 text-indigo-700":node.kind==="branch"?"bg-amber-100 text-amber-800":"bg-slate-200 text-slate-700")}>{index+1}</span>
            <div className="min-w-0">
             <p className="truncate text-sm font-bold">{node.id}</p>
             <p className="text-[11px] text-slate-500">{nodeTypeLabel(node)}{node.id===entry?" · Entry":""}</p>
            </div>
           </div>
           <button type="button" data-testid={"remove-node-"+node.id} onClick={()=>removeNode(node.id)} disabled={!canRemove||busy} title={!canRemove?"Reconnect incoming routes and/or choose another entry before removing this node":""} className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40">Remove</button>
          </div>

          {node.kind==="email"&&<div className="grid gap-3 p-3 sm:grid-cols-2 sm:p-4">
           <label className={label+" sm:col-span-2"}>Subject
            <input data-testid={"node-"+node.id+"-subject"} className={field} value={node.subject||""} onChange={e=>updateNode(node.id,{subject:e.target.value})} required maxLength={300}/>
           </label>
           <label className={label+" sm:col-span-2"}>Email content
            <textarea data-testid={"node-"+node.id+"-body"} className={field} rows={3} value={node.body_text||""} onChange={e=>updateNode(node.id,{body_text:e.target.value})} required maxLength={12000}/>
           </label>
           <label className={label}>Delay after previous step (days)
            <input data-testid={"node-"+node.id+"-delay"} className={field} type="number" min={0} max={90} step={1} value={node.delay_days??0} onChange={e=>updateNode(node.id,{delay_days:Number(e.target.value)})} required/>
           </label>
           <label className={label}>Next step
            <select data-testid={"node-"+node.id+"-next"} className={field} value={node.next_step_id||""} onChange={e=>updateNode(node.id,{next_step_id:e.target.value})} required>
             <option value="" disabled>Select a destination</option>
             {options.map(option=><option key={option.id} value={option.id}>{option.label}</option>)}
            </select>
           </label>
           <label className="flex items-start gap-2 text-sm text-slate-700 sm:col-span-2">
            <input data-testid={"node-"+node.id+"-affiliate"} type="checkbox" checked={node.has_affiliate_links===true} onChange={e=>updateNode(node.id,{has_affiliate_links:e.target.checked})} className="mt-1"/>
            <span><strong>Contains affiliate links</strong><span className="block text-xs text-slate-500">The node must include a clear disclosure before it can be saved.</span></span>
           </label>
           {node.has_affiliate_links&&<label className={label+" sm:col-span-2"}>Affiliate disclosure
            <textarea data-testid={"node-"+node.id+"-disclosure"} className={field} rows={2} minLength={10} value={node.affiliate_disclosure||""} onChange={e=>updateNode(node.id,{affiliate_disclosure:e.target.value})} required/>
           </label>}
          </div>}

          {node.kind==="branch"&&<div className="grid gap-3 p-3 sm:grid-cols-2 sm:p-4">
           <label className={label+" sm:col-span-2"}>Decision condition
            <select data-testid={"node-"+node.id+"-condition"} className={field} value={node.condition||"purchased"} onChange={e=>updateNode(node.id,{condition:e.target.value as Node["condition"]})}>
             {Object.entries(conditionLabels).map(([key,value])=><option key={key} value={key}>{value}</option>)}
            </select>
           </label>
           <label className={label}>True route
            <select data-testid={"node-"+node.id+"-true"} className={field} value={node.true_step_id||""} onChange={e=>updateNode(node.id,{true_step_id:e.target.value})} required>
             <option value="" disabled>Select true destination</option>
             {options.map(option=><option key={option.id} value={option.id}>{option.label}</option>)}
            </select>
           </label>
           <label className={label}>False route
            <select data-testid={"node-"+node.id+"-false"} className={field} value={node.false_step_id||""} onChange={e=>updateNode(node.id,{false_step_id:e.target.value})} required>
             <option value="" disabled>Select false destination</option>
             {options.map(option=><option key={option.id} value={option.id}>{option.label}</option>)}
            </select>
           </label>
           <div className="flex flex-wrap gap-2 text-xs sm:col-span-2">
            <span className="rounded-lg bg-emerald-50 px-3 py-2 font-semibold text-emerald-800">TRUE → {node.true_step_id||"Not connected"}</span>
            <span className="rounded-lg bg-amber-50 px-3 py-2 font-semibold text-amber-900">FALSE → {node.false_step_id||"Not connected"}</span>
           </div>
          </div>}

          {node.kind==="stop"&&<div className="p-4 text-sm text-slate-600"><strong>End of path.</strong> No further email is scheduled after this step.</div>}
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600 sm:px-4">
           <span className="font-semibold text-slate-500">Outgoing connection</span>
           <span className="rounded-md bg-white px-2 py-1 font-mono">{downstream||"Not connected"}</span>
          </div>
         </article>;
        })}
       </div>
       <p className="mt-3 text-xs leading-5 text-slate-500">Server validation rejects missing destinations, unreachable steps and cycles. A saved version is immutable after review; load it as a new version to make changes.</p>
      </div>
      <button type="submit" disabled={busy} className="mt-4 w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white hover:bg-indigo-700 disabled:opacity-50">{busy?"Saving…":"Validate and save review-required graph"}</button>
     </form>

     <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-end justify-between gap-3">
       <div><h2 className="text-xl font-bold">Saved automations</h2><p className="mt-1 text-sm text-slate-500">{items.length} workspace version(s)</p></div>
      </div>
      {items.length===0&&<p className="mt-4 rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">No email automation graphs yet.</p>}
      <div className="mt-4 space-y-3">
       {items.map(item=><article key={item.id} data-testid={"saved-automation-"+item.id} className="rounded-xl border border-slate-200 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
         <div><p className="font-mono text-xs text-indigo-700">{item.version} · {item.node_count} nodes · {item.graph_sha256.slice(0,12)}…</p><h3 className="mt-1 font-bold">{item.name}</h3><p className="mt-1 text-sm text-slate-600">{item.description}</p></div>
         <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{item.status.replaceAll("_"," ")}</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
         <button type="button" data-testid={"inspect-automation-"+item.id} onClick={()=>void selectItem(item)} className={smallButton}>Inspect graph</button>
         <button type="button" data-testid={"simulate-automation-"+item.id} disabled={busy} onClick={()=>void simulate(item)} className="rounded-lg border border-indigo-200 px-3 py-2 text-sm font-bold text-indigo-700 disabled:opacity-40">Simulate current context</button>
         {item.status!=="approved"&&item.status!=="rejected"&&<button type="button" disabled={busy} onClick={()=>void review(item,"approve")} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-40">Review & approve</button>}
        </div>
       </article>)}
      </div>
     </section>
    </section>

    <aside className="space-y-5">
     <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-bold">Simulation inputs</h2>
      <p className="mt-1 text-sm text-slate-500">Choose a saved graph above, set a sample lead state, then simulate the exact branch path.</p>
      <div className="mt-4 grid gap-3">
       {[
        ["purchased","Sample lead purchased"],
        ["engaged","Sample lead engaged"],
        ["consent_granted","Marketing consent confirmed"],
        ["unsubscribed","Recipient unsubscribed"]
       ].map(([key,title])=><label key={key} className="flex items-start gap-2 text-sm text-slate-700">
        <input data-testid={"simulation-"+key} type="checkbox" checked={context[key as keyof typeof context]} onChange={e=>setContext(value=>({...value,[key]:e.target.checked}))} className="mt-1"/>
        <span>{title}</span>
       </label>)}
      </div>
      {selected&&<div data-testid="selected-automation" className="mt-4 rounded-xl bg-slate-50 p-3">
       <p className="font-bold">{selected.name} · v{selected.version}</p>
       <p className="mt-1 text-xs text-slate-500">Status: {selected.status} · {selected.node_count} nodes · SHA-256 {selected.graph_sha256.slice(0,12)}…</p>
       <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" data-testid="simulate-selected-automation" disabled={busy} onClick={()=>void simulate(selected)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-40">Run simulation</button>
        {selected.graph&&<button type="button" disabled={busy} onClick={loadAsNewVersion} className={smallButton}>Load as new version</button>}
        {selected.status!=="approved"&&selected.status!=="rejected"&&<button type="button" disabled={busy} onClick={()=>void review(selected,"reject")} className="rounded-lg border border-rose-200 px-3 py-2 text-sm font-bold text-rose-700 disabled:opacity-40">Reject graph</button>}
       </div>
       <label className={label+" mt-3"}>Reviewer notes<textarea data-testid="reviewer-notes" className={field} rows={2} value={reviewNotes} onChange={e=>setReviewNotes(e.target.value)} maxLength={2000}/></label>
       {selected.validation_report.warnings.length>0&&<ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-amber-800">{selected.validation_report.warnings.map((warning,index)=><li key={index}>{warning}</li>)}</ul>}
      </div>}
      {simulation&&<div data-testid="simulation-result" className="mt-4 rounded-xl border border-slate-200 p-4">
       <h3 className="font-bold">Simulated path · no delivery side effects</h3>
       <div className="mt-3 flex flex-wrap items-center gap-2">
        {simulation.path.map((node,index)=><span key={node+index} className="flex items-center gap-2"><span className="rounded-lg bg-indigo-50 px-3 py-2 text-xs font-bold text-indigo-800">{node}</span>{index<simulation.path.length-1&&<span className="text-slate-400">→</span>}</span>)}
       </div>
       <div className="mt-3 space-y-2">
        {simulation.emails.map(email=><div key={email.step_id} className="rounded-lg bg-slate-50 p-3"><p className="font-bold">{email.subject}</p><p className="mt-1 text-xs text-slate-500">Send offset: day {email.scheduled_offset_days} · node {email.step_id}</p><p className="mt-2 whitespace-pre-wrap text-sm">{email.body_text}</p>{email.affiliate_disclosure_required&&<p className="mt-2 text-xs text-amber-800">Affiliate disclosure required: {email.affiliate_disclosure}</p>}</div>)}
       </div>
       <p className="mt-3 text-xs text-slate-500">Reason: {simulation.stop_reason}; provider calls: {simulation.provider_calls_made}; messages scheduled: {simulation.messages_scheduled}</p>
      </div>}
     </section>
    </aside>
   </div>
  </div>
 </main>;
}

"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type Fixture = {name:string;input:unknown;expected_output:unknown};
type ValidationReport = {
  all_fixtures_passed:boolean;fixtures_passed:number;fixtures_failed:number;fixture_count:number;
  declarative_only:boolean;skill_instructions_executed:boolean;runtime_execution_tested:boolean;
  runtime_fixtures_executed?:number;runtime_handler?:string;
  capabilities_requiring_human_review:string[];warnings:string[];
  cases:Array<{name:string;passed:boolean;input_errors:string[];expected_output_errors:string[];runtime_errors?:string[];runtime_output_matches_expected?:boolean|null}>;
};
type Package = {
  id:string;skill_id:string;display_name:string;version:string;description:string;stage:string;runtime_handler:string;
  capabilities:string[];validation_report:ValidationReport;package_sha256:string;status:string;
  created_by:string;reviewed_by:string|null;reviewed_at:string|null;reviewer_notes:string|null;
  created_at:string|null;execution_boundary:string;instructions_markdown?:string;
  input_schema?:Record<string,unknown>;output_schema?:Record<string,unknown>;test_cases?:Fixture[];
};
type PackageList = {count:number;data:Package[]};
const field="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm";
const label="block text-sm font-semibold text-slate-700";
const defaultInputSchema={type:"object",properties:{topic:{type:"string",minLength:3}},required:["topic"],additionalProperties:false};
const defaultOutputSchema={type:"object",properties:{summary:{type:"string",minLength:3}},required:["summary"],additionalProperties:false};
const defaultFixtures=[{name:"basic topic",input:{topic:"affiliate analytics"},expected_output:{summary:"Compare analytics options."}}];
function message(error:unknown){return error instanceof Error?error.message:"Request failed";}
function pretty(value:unknown){return JSON.stringify(value,null,2);}
const summaryFixtureText="Alpha helps teams. Beta improves workflows. Gamma supports analysis.";
const runtimePresets:Record<string,{skillId:string;name:string;stage:string;description:string;capabilities:string;inputSchema:Record<string,unknown>;outputSchema:Record<string,unknown>;instructions:string;testCases:Fixture[]}>={
  "content.extractive_summary":{
    skillId:"content/extractive-summary",name:"Extractive summary",stage:"S2",
    description:"Summarize supplied text by extracting its leading sentences without inventing claims.",
    capabilities:"content.draft",
    inputSchema:{type:"object",properties:{text:{type:"string",minLength:1,maxLength:20000},max_sentences:{type:"integer",minimum:1,maximum:10}},required:["text","max_sentences"],additionalProperties:false},
    outputSchema:{type:"object",properties:{summary:{type:"string",maxLength:20000},sentence_count:{type:"integer",minimum:0,maximum:10},source_character_count:{type:"integer",minimum:0,maximum:20000}},required:["summary","sentence_count","source_character_count"],additionalProperties:false},
    instructions:"# Declarative guidance\\nSummarize supplied text by extracting leading sentences. This Markdown is never executed.",
    testCases:[{name:"two sentence summary",input:{text:summaryFixtureText,max_sentences:2},expected_output:{summary:"Alpha helps teams. Beta improves workflows.",sentence_count:2,source_character_count:summaryFixtureText.length}}],
  },
  "research.keyword_extract":{
    skillId:"research/keyword-extract",name:"Keyword extract",stage:"S3",
    description:"Extract frequent terms from supplied text; do not claim search volume or ranking data.",
    capabilities:"research.read",
    inputSchema:{type:"object",properties:{text:{type:"string",minLength:1,maxLength:20000},limit:{type:"integer",minimum:1,maximum:20}},required:["text","limit"],additionalProperties:false},
    outputSchema:{type:"object",properties:{keywords:{type:"array",items:{type:"string",minLength:3,maxLength:50},maxItems:20},keyword_count:{type:"integer",minimum:0,maximum:20},source_token_count:{type:"integer",minimum:0,maximum:5000}},required:["keywords","keyword_count","source_token_count"],additionalProperties:false},
    instructions:"# Declarative guidance\\nExtract repeated terms from supplied text. Never imply search-volume or ranking data.",
    testCases:[{name:"frequency and tie-break order",input:{text:"Affiliate marketing guide guide builds conversion",limit:3},expected_output:{keywords:["guide","affiliate","builds"],keyword_count:3,source_token_count:6}}],
  },
  "analytics.roas_calculator":{
    skillId:"analytics/roas-calculator",name:"ROAS calculator",stage:"S6",
    description:"Calculate ROAS from supplied spend and commission; return review-only signals, never change campaigns.",
    capabilities:"analytics.read",
    inputSchema:{type:"object",properties:{spend_usd:{type:"number",minimum:0,maximum:1000000000},commission_usd:{type:"number",minimum:0,maximum:1000000000},minimum_roas:{type:"number",minimum:0,maximum:1000000}},required:["spend_usd","commission_usd","minimum_roas"],additionalProperties:false},
    outputSchema:{type:"object",properties:{roas_available:{type:"boolean"},roas:{type:"number",minimum:0,maximum:1000000000000},pause_recommended:{type:"boolean"},minimum_roas:{type:"number",minimum:0,maximum:1000000},reason:{type:"string",minLength:1,maxLength:300},requires_human_review:{type:"boolean"}},required:["roas_available","pause_recommended","minimum_roas","reason","requires_human_review"],additionalProperties:false},
    instructions:"# Declarative guidance\\nCalculate commission divided by ad spend; return review-only signals, never change a campaign.",
    testCases:[{name:"above threshold review signal",input:{spend_usd:50,commission_usd:75,minimum_roas:1.2},expected_output:{roas_available:true,roas:1.5,pause_recommended:false,minimum_roas:1.2,reason:"At or above threshold; no remote campaign action was taken.",requires_human_review:true}}],
  },
};
function sampleRuntimeInput(handler:string){
  if(handler==="content.extractive_summary")return {text:summaryFixtureText,max_sentences:2};
  if(handler==="research.keyword_extract")return {text:"Affiliate marketing guide guide builds conversion",limit:3};
  if(handler==="analytics.roas_calculator")return {spend_usd:50,commission_usd:75,minimum_roas:1.2};
  return {};
}
type ExecutionResult={ok:boolean;body:string};
export default function SkillPackagesPage(){
  const [packages,setPackages]=useState<Package[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [skillId,setSkillId]=useState("content/summary-draft");
  const [name,setName]=useState("Summary draft helper");
  const [version,setVersion]=useState("1.0.0");
  const [stage,setStage]=useState("S2");
  const [runtimeHandler,setRuntimeHandler]=useState("none");
  const [description,setDescription]=useState("Create a concise summary draft from supplied topics and verified facts.");
  const [executionInputs,setExecutionInputs]=useState<Record<string,string>>({});
  const [executionResults,setExecutionResults]=useState<Record<string,ExecutionResult>>({});
  const [runtimeBusyId,setRuntimeBusyId]=useState<string|null>(null);
  const [capabilities,setCapabilities]=useState("content.draft, research.read");
  const [inputSchema,setInputSchema]=useState(pretty(defaultInputSchema));
  const [outputSchema,setOutputSchema]=useState(pretty(defaultOutputSchema));
  const [instructions,setInstructions]=useState("# Task\nProduce a concise summary from user-provided topic and facts. Do not invent claims.");
  const [fixtures,setFixtures]=useState(pretty(defaultFixtures));
  const [reviewNotes,setReviewNotes]=useState("");
  const load=useCallback(async()=>{
    setError("");
    try{const result=await apiFetch<PackageList>("/api/skills/packages?limit=100");setPackages(result.data||[]);}
    catch(e){setError(message(e));}
  },[]);
  useEffect(()=>{void load();},[load]);
  const changeRuntimeHandler=(handler:string)=>{
    setRuntimeHandler(handler);
    const preset=runtimePresets[handler];
    if(preset){
      setSkillId(preset.skillId);setName(preset.name);setStage(preset.stage);
      setDescription(preset.description);setCapabilities(preset.capabilities);
      setInputSchema(pretty(preset.inputSchema));setOutputSchema(pretty(preset.outputSchema));
      setInstructions(preset.instructions);setFixtures(pretty(preset.testCases));
    }else{
      setSkillId("content/summary-draft");setName("Summary draft helper");setStage("S2");
      setDescription("Create a concise summary draft from supplied topics and verified facts.");
      setCapabilities("content.draft, research.read");
      setInputSchema(pretty(defaultInputSchema));setOutputSchema(pretty(defaultOutputSchema));
      setInstructions("# Task\nProduce a concise summary from user-provided topic and facts. Do not invent claims.");
      setFixtures(pretty(defaultFixtures));
    }
  };
  const execute=async(pkg:Package)=>{
    setRuntimeBusyId(pkg.id);setExecutionResults(previous=>({...previous,[pkg.id]:{ok:false,body:"Execution in progress…"}}));
    try{
      const input=JSON.parse(executionInputs[pkg.id]??pretty(sampleRuntimeInput(pkg.runtime_handler)));
      const result=await apiFetch<{status:string;result:unknown;skill_instructions_executed:boolean;external_actions_executed:boolean}>(
        `/api/skills/packages/${encodeURIComponent(pkg.id)}/execute`,
        {method:"POST",body:JSON.stringify({input})},
      );
      setExecutionResults(previous=>({...previous,[pkg.id]:{ok:true,body:pretty(result)}}));
    }catch(e){
      setExecutionResults(previous=>({...previous,[pkg.id]:{ok:false,body:message(e)}}));
    }finally{setRuntimeBusyId(null);}
  };
  const submit=async(e:FormEvent)=>{
    e.preventDefault();setBusy(true);setError("");setNotice("");
    try{
      const body={skill_id:skillId,display_name:name,version,stage,runtime_handler:runtimeHandler,description,
        capabilities:capabilities.split(",").map(v=>v.trim()).filter(Boolean),
        input_schema:JSON.parse(inputSchema),output_schema:JSON.parse(outputSchema),
        instructions_markdown:instructions,test_cases:JSON.parse(fixtures)};
      const created=await apiFetch<Package>("/api/skills/packages",{method:"POST",body:JSON.stringify(body)});
      setNotice(`Package ${created.skill_id}@${created.version} saved as ${created.status}; checksum ${created.package_sha256.slice(0,12)}…`);
      await load();
    }catch(e){setError(message(e));}
    finally{setBusy(false);}
  };
  const review=async(pkg:Package,decision:"approve"|"reject")=>{
    setBusy(true);setError("");setNotice("");
    try{
      const body={decision,confirm_contract_reviewed:decision==="approve",reviewer_notes:reviewNotes};
      const result=await apiFetch<Package>(`/api/skills/packages/${encodeURIComponent(pkg.id)}/review`,{method:"POST",body:JSON.stringify(body)});
      setNotice(`${result.skill_id}@${result.version} marked ${result.status}.`);
      setReviewNotes("");
      await load();
    }catch(e){setError(message(e));}
    finally{setBusy(false);}
  };
  return <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10">
    <div className="mx-auto max-w-7xl">
      <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div><a className="text-sm font-semibold text-indigo-600 hover:underline" href="/">← Growth command</a><h1 className="mt-2 text-3xl font-black tracking-tight">Governed skill packages</h1><p className="mt-1 max-w-3xl text-sm text-slate-600">Version declarative skill manifests, validate JSON input/output fixtures, and record workspace-scoped human review.</p></div>
        <button type="button" onClick={()=>void load()} disabled={busy} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold disabled:opacity-50">Refresh packages</button>
      </header>
      <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><strong>Execution boundary:</strong> package instructions are stored as text and are never executed. Fixture checks validate JSON contracts only—not skill behavior. Approval does not grant provider credentials, API scopes, publishing access, or authority to spend money.</div>
      {error&&<div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
      {notice&&<div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}
      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(340px,.85fr)_minmax(0,1.15fr)]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-xl font-bold">Create package version</h2><p className="mt-1 text-sm text-slate-500">A new version is immutable after review; publishable runtime execution is deliberately out of scope here.</p>
          <form onSubmit={submit} className="mt-4 space-y-4">
            <div className="grid gap-3 sm:grid-cols-2"><label className={label}>Skill ID<input className={field} value={skillId} onChange={e=>setSkillId(e.target.value)} required minLength={3}/></label><label className={label}>Version<input className={field} value={version} onChange={e=>setVersion(e.target.value)} required pattern="(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?" title="Use semantic version, e.g. 1.0.0"/></label></div>
            <div className="grid gap-3 sm:grid-cols-2"><label className={label}>Display name<input className={field} value={name} onChange={e=>setName(e.target.value)} required minLength={3}/></label><label className={label}>Lifecycle stage<select className={field} value={stage} onChange={e=>setStage(e.target.value)}>{["S1","S2","S3","S4","S5","S6","S7","S8"].map(v=><option key={v}>{v}</option>)}</select></label></div>
            <label className={label}>Safe runtime handler<select className={field} value={runtimeHandler} onChange={e=>changeRuntimeHandler(e.target.value)}><option value="none">None — contract-only package</option><option value="content.extractive_summary">Content · extractive summary</option><option value="research.keyword_extract">Research · keyword extraction</option><option value="analytics.roas_calculator">Analytics · ROAS calculator (review only)</option></select><span className="mt-1 block text-xs font-normal text-slate-500">Selecting a handler loads its real input/output contract and a regression fixture. User-authored Markdown remains data, never executable code.</span></label>
            <label className={label}>Description<textarea className={field} rows={2} value={description} onChange={e=>setDescription(e.target.value)} required minLength={10}/></label>
            <label className={label}>Declared capabilities<input className={field} value={capabilities} onChange={e=>setCapabilities(e.target.value)} required/><span className="mt-1 block text-xs font-normal text-slate-500">Comma-separated identifiers. Provider/write/spend-related capabilities are flagged for human review.</span></label>
            <label className={label}>Input JSON schema<textarea className={field+" font-mono text-xs"} rows={7} value={inputSchema} onChange={e=>setInputSchema(e.target.value)} required spellCheck={false}/></label>
            <label className={label}>Output JSON schema<textarea className={field+" font-mono text-xs"} rows={7} value={outputSchema} onChange={e=>setOutputSchema(e.target.value)} required spellCheck={false}/></label>
            <label className={label}>Instructions (Markdown text, not executable)<textarea className={field} rows={5} value={instructions} onChange={e=>setInstructions(e.target.value)} required minLength={20}/></label>
            <label className={label}>Contract fixtures JSON<textarea className={field+" font-mono text-xs"} rows={7} value={fixtures} onChange={e=>setFixtures(e.target.value)} required spellCheck={false}/><span className="mt-1 block text-xs font-normal text-slate-500">Array of {"{ name, input, expected_output }"} records.</span></label>
            <button type="submit" disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50">{busy?"Saving…":"Validate and save package"}</button>
          </form>
        </section>
        <section className="space-y-4">
          <div className="flex items-end justify-between"><div><h2 className="text-xl font-bold">Workspace packages</h2><p className="mt-1 text-sm text-slate-500">{packages.length} package version(s)</p></div></div>
          {packages.length===0&&<div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">No packages in the active workspace yet.</div>}
          {packages.map(pkg=><article key={pkg.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-xs font-bold text-indigo-600">{pkg.skill_id}@{pkg.version} · {pkg.stage}</p><h3 className="mt-1 text-lg font-bold">{pkg.display_name}</h3><p className="mt-1 text-sm text-slate-600">{pkg.description}</p></div><span className={"rounded-full px-3 py-1 text-xs font-bold "+(pkg.status==="approved"?"bg-emerald-100 text-emerald-800":pkg.status==="rejected"?"bg-rose-100 text-rose-800":"bg-amber-100 text-amber-800")}>{pkg.status.replaceAll("_"," ")}</span></div>
            <p className="mt-3 break-all font-mono text-xs text-slate-500">SHA-256 {pkg.package_sha256}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Fixture checks</p><p className="mt-1 text-lg font-bold">{pkg.validation_report.fixtures_passed}/{pkg.validation_report.fixture_count}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Needs reviewed capability</p><p className="mt-1 text-sm font-bold">{pkg.validation_report.capabilities_requiring_human_review.length?"Yes":"No flagged capabilities"}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Runtime verification</p><p className="mt-1 text-sm font-bold">{pkg.runtime_handler==="none"?"Contract only":pkg.validation_report.runtime_execution_tested?"Handler fixtures executed":"Runtime fixture failed"}</p></div></div>
            {pkg.status==="approved"&&pkg.runtime_handler!=="none"&&<div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4"><h4 className="font-bold">Execute approved local handler</h4><p className="mt-1 text-xs text-slate-600">Runs allowlisted deterministic code only. No authored instructions, network calls or external actions are executed.</p><label className={label+" mt-3"}>JSON input<textarea className={field+" font-mono text-xs"} rows={4} spellCheck={false} value={executionInputs[pkg.id]??pretty(sampleRuntimeInput(pkg.runtime_handler))} onChange={e=>setExecutionInputs(previous=>({...previous,[pkg.id]:e.target.value}))}/></label><button type="button" disabled={busy||runtimeBusyId!==null} onClick={()=>void execute(pkg)} className="mt-3 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{runtimeBusyId===pkg.id?"Executing…":"Execute handler"}</button>{executionResults[pkg.id]&&<pre role="status" className={"mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg p-3 text-xs "+(executionResults[pkg.id].ok?"bg-white text-slate-800":"bg-rose-50 text-rose-800")}>{executionResults[pkg.id].body}</pre>}</div>}
            {pkg.validation_report.cases?.some(c=>!c.passed)&&<div className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{pkg.validation_report.cases.filter(c=>!c.passed).map(c=><div key={c.name}><strong>{c.name}:</strong> {[...c.input_errors,...c.expected_output_errors].join("; ")}</div>)}</div>}
            {pkg.status!=="approved"&&pkg.status!=="rejected"&&<div className="mt-4 flex flex-col gap-2 sm:flex-row"><button type="button" disabled={busy||!pkg.validation_report.all_fixtures_passed} onClick={()=>void review(pkg,"approve")} className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-40">Review & approve contract</button><button type="button" disabled={busy} onClick={()=>void review(pkg,"reject")} className="rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-bold text-rose-700 disabled:opacity-40">Reject version</button></div>}
          </article>)}
        </section>
      </div>
    </div>
  </main>;
}

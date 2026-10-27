"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {apiFetch} from "@/lib/api";

type Fixture = {name:string;input:unknown;expected_output:unknown};
type ValidationReport = {
  all_fixtures_passed:boolean;fixtures_passed:number;fixtures_failed:number;fixture_count:number;
  declarative_only:boolean;skill_instructions_executed:boolean;runtime_execution_tested:boolean;
  capabilities_requiring_human_review:string[];warnings:string[];
  cases:Array<{name:string;passed:boolean;input_errors:string[];expected_output_errors:string[]}>;
};
type Package = {
  id:string;skill_id:string;display_name:string;version:string;description:string;stage:string;
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
export default function SkillPackagesPage(){
  const [packages,setPackages]=useState<Package[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [skillId,setSkillId]=useState("content/summary-draft");
  const [name,setName]=useState("Summary draft helper");
  const [version,setVersion]=useState("1.0.0");
  const [stage,setStage]=useState("S2");
  const [description,setDescription]=useState("Create a concise summary draft from supplied topics and verified facts.");
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
  const submit=async(e:FormEvent)=>{
    e.preventDefault();setBusy(true);setError("");setNotice("");
    try{
      const body={skill_id:skillId,display_name:name,version,stage,description,
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
            <div className="mt-3 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Fixture contracts</p><p className="mt-1 text-lg font-bold">{pkg.validation_report.fixtures_passed}/{pkg.validation_report.fixture_count}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Needs reviewed capability</p><p className="mt-1 text-sm font-bold">{pkg.validation_report.capabilities_requiring_human_review.length?"Yes":"No flagged capabilities"}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Runtime execution</p><p className="mt-1 text-sm font-bold">Not executed</p></div></div>
            {pkg.validation_report.cases?.some(c=>!c.passed)&&<div className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{pkg.validation_report.cases.filter(c=>!c.passed).map(c=><div key={c.name}><strong>{c.name}:</strong> {[...c.input_errors,...c.expected_output_errors].join("; ")}</div>)}</div>}
            {pkg.status!=="approved"&&pkg.status!=="rejected"&&<div className="mt-4 flex flex-col gap-2 sm:flex-row"><button type="button" disabled={busy||!pkg.validation_report.all_fixtures_passed} onClick={()=>void review(pkg,"approve")} className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-40">Review & approve contract</button><button type="button" disabled={busy} onClick={()=>void review(pkg,"reject")} className="rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-bold text-rose-700 disabled:opacity-40">Reject version</button></div>}
          </article>)}
        </section>
      </div>
    </div>
  </main>;
}

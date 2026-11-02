"use client";

import {useCallback,useEffect,useState,type FormEvent} from "react";
import {useParams} from "next/navigation";
import {Globe2,LoaderCircle,ShieldCheck} from "lucide-react";
import {apiFetch} from "@/lib/api";

type WebinarPage={
  public_id:string;title:string;summary:string;description:string;host_name:string;host_bio:string|null;
  start_at:string;end_at:string;timezone_name:string;registration_deadline:string|null;
  agenda_items:Array<{title:string;description:string}>;privacy_policy_url:string;consent_text:string;
  affiliate_disclosure:string|null;capacity:number|null;registration_count:number;remaining_spots:number|null;
  registration_open:boolean;external_webinar_provider:string;confirmation_email_sent:boolean;
};

export default function PublicWebinarPage(){
  const params=useParams<{publicId:string}>();
  const publicId=String(params.publicId||"");
  const [webinar,setWebinar]=useState<WebinarPage|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [fullName,setFullName]=useState("");
  const [email,setEmail]=useState("");
  const [consent,setConsent]=useState(false);
  const [marketingConsent,setMarketingConsent]=useState(false);
  const [submitting,setSubmitting]=useState(false);
  const [registered,setRegistered]=useState(false);
  const [notice,setNotice]=useState("");

  const load=useCallback(async()=>{
    setLoading(true);setError("");
    try{setWebinar(await apiFetch<WebinarPage>("/api/public/webinars/"+encodeURIComponent(publicId)))}
    catch(e){setError(e instanceof Error?e.message:"This webinar registration page is unavailable")}
    finally{setLoading(false)}
  },[publicId]);
  useEffect(()=>{if(publicId)void load()},[load,publicId]);

  const submit=async(e:FormEvent)=>{
    e.preventDefault();setError("");setNotice("");
    if(!consent){setError("Please agree to the registration data-use statement before registering.");return}
    setSubmitting(true);
    try{
      const result=await apiFetch<{status:string;confirmation_email_sent:boolean;email_delivery:string}>(
        "/api/public/webinars/"+encodeURIComponent(publicId)+"/register",
        {method:"POST",body:JSON.stringify({full_name:fullName,email,consent,marketing_consent:marketingConsent})}
      );
      setRegistered(true);
      setNotice(result.status==="already_registered"?"This email address is already registered for the webinar.":"Your registration has been recorded.");
    }catch(e){setError(e instanceof Error?e.message:"Registration could not be completed")}
    finally{setSubmitting(false)}
  };

  if(loading)return <main className="min-h-screen bg-slate-50 p-6 text-slate-600"><div className="mx-auto mt-24 flex max-w-xl items-center justify-center gap-3"><LoaderCircle className="animate-spin"/><span>Loading webinar details…</span></div></main>;
  if(error&&!webinar)return <main className="min-h-screen bg-slate-50 p-6"><div className="mx-auto mt-24 max-w-xl rounded-3xl border border-slate-200 bg-white p-8"><h1 className="text-2xl font-black">Registration page unavailable</h1><p className="mt-3 text-sm leading-6 text-slate-600">{error}</p></div></main>;
  if(!webinar)return null;
  const start=new Date(webinar.start_at), end=new Date(webinar.end_at);
  const dateLabel=(d:Date)=>new Intl.DateTimeFormat(undefined,{dateStyle:"full",timeStyle:"short",timeZone:webinar.timezone_name}).format(d);
  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:px-6 lg:py-14">
    <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(340px,.8fr)]">
      <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-10">
        <div className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-700"><Globe2 size={14}/> Webinar registration</div>
        <h1 className="mt-5 text-3xl font-black tracking-tight sm:text-4xl">{webinar.title}</h1>
        <p className="mt-4 text-lg leading-7 text-slate-600">{webinar.summary}</p>
        <div className="mt-6 grid gap-2 rounded-2xl bg-slate-50 p-4 text-sm"><p><strong>Starts:</strong> {dateLabel(start)}</p><p><strong>Ends:</strong> {dateLabel(end)}</p><p><strong>Timezone:</strong> {webinar.timezone_name}</p><p><strong>Host:</strong> {webinar.host_name}</p>{webinar.remaining_spots!==null&&<p><strong>Places remaining:</strong> {webinar.remaining_spots}</p>}</div>
        <h2 className="mt-8 text-xl font-black">About this webinar</h2><p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">{webinar.description}</p>
        {webinar.host_bio&&<><h2 className="mt-7 text-xl font-black">About the host</h2><p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">{webinar.host_bio}</p></>}
        {webinar.agenda_items.length>0&&<><h2 className="mt-7 text-xl font-black">Agenda</h2><ol className="mt-3 space-y-3">{webinar.agenda_items.map((item,i)=><li key={item.title+i} className="rounded-xl border border-slate-100 p-4"><p className="font-bold">{i+1}. {item.title}</p>{item.description&&<p className="mt-1 text-sm leading-6 text-slate-600">{item.description}</p>}</li>)}</ol></>}
        {webinar.affiliate_disclosure&&<p className="mt-7 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900">{webinar.affiliate_disclosure}</p>}
        <p className="mt-7 text-xs text-slate-500">The event host is responsible for the accuracy of event details. No webinar meeting provider is connected by this page.</p>
      </article>
      <aside className="h-fit rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex items-center gap-2 text-indigo-700"><ShieldCheck size={18}/><span className="text-xs font-black uppercase tracking-widest">Registration</span></div>
        <h2 className="mt-3 text-2xl font-black">Reserve your place</h2>
        {registered?<div className="mt-5 rounded-2xl bg-emerald-50 p-4"><p className="font-bold text-emerald-900">{notice}</p><p className="mt-2 text-sm leading-6 text-emerald-800">Email confirmation is not configured for this event. Save the details shown on this page.</p></div>:<form onSubmit={submit} className="mt-5 space-y-4">
          <div><label htmlFor="webinar-name" className="block text-sm font-bold">Full name</label><input id="webinar-name" value={fullName} onChange={e=>setFullName(e.target.value)} required minLength={2} maxLength={200} autoComplete="name" className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-3 text-sm"/></div>
          <div><label htmlFor="webinar-email" className="block text-sm font-bold">Email address</label><input id="webinar-email" type="email" value={email} onChange={e=>setEmail(e.target.value)} required maxLength={320} autoComplete="email" className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-3 text-sm"/></div>
          <label className="flex items-start gap-3 rounded-xl bg-slate-50 p-3 text-sm leading-6"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)} required className="mt-1"/><span>{webinar.consent_text} <a href={webinar.privacy_policy_url} target="_blank" rel="noreferrer" className="font-bold text-indigo-700 underline">Privacy policy</a></span></label>
          <label className="flex items-start gap-3 text-xs leading-5 text-slate-500"><input type="checkbox" checked={marketingConsent} onChange={e=>setMarketingConsent(e.target.checked)} className="mt-1"/><span>Separately opt in to marketing emails (optional). This is not required to register.</span></label>
          {error&&<p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
          <button type="submit" disabled={submitting} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white disabled:opacity-50">{submitting?"Registering…":"Register for webinar"}</button>
          <p className="text-xs leading-5 text-slate-500">Submitting creates a registration record. Marketing opt-in is separate from event registration.</p>
        </form>}
        {registered&&error&&<p role="alert" className="mt-4 text-sm text-rose-700">{error}</p>}
        <p className="mt-5 text-xs text-slate-400">External provider: {webinar.external_webinar_provider} · Confirmation email: not configured</p>
      </aside>
    </div>
  </main>;
}

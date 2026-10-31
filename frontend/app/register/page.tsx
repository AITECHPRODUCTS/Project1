"use client";

import { useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";

type PublicAccountType = "affiliate_publisher" | "merchant_product_owner";

export default function RegisterPage() {
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [workspaceName,setWorkspaceName]=useState("");
  const [accountType,setAccountType]=useState<PublicAccountType|"">("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");

  const submit=async(event:FormEvent)=>{
    event.preventDefault();
    if(!accountType){setError("Choose one account type before continuing.");return;}
    setBusy(true);setError("");
    try{
      const created=await apiFetch<{user?:{account_type?:PublicAccountType}}>("/api/auth/register",{
        method:"POST",
        body:JSON.stringify({
          email:email.trim(),
          password,
          workspace_name:workspaceName.trim()||(
            accountType==="merchant_product_owner"?"My Merchant Workspace":"My Publisher Workspace"
          ),
          account_type:accountType
        })
      });
      const selected=created.user?.account_type||accountType;
      window.location.replace(selected==="merchant_product_owner"?"/merchant":"/publisher");
    }catch(cause){
      setError(cause instanceof Error?cause.message:"Account registration failed.");
    }finally{setBusy(false);}
  };

  return <main className="min-h-screen bg-slate-50 px-4 py-10 text-slate-900">
    <div className="mx-auto max-w-2xl">
      <a href="/" className="text-sm font-bold text-indigo-700">← Back to sign in</a>
      <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9">
        <p className="text-xs font-black uppercase tracking-[.2em] text-indigo-600">OmniAffiliateOS</p>
        <h1 className="mt-2 text-3xl font-black">Create your account</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">Choose one business role. Your account will have one role-specific dashboard; workspace membership permissions do not change this selection.</p>
        <form onSubmit={submit} className="mt-7 space-y-5">
          <fieldset>
            <legend className="text-sm font-bold">Which role describes your business?</legend>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className={`cursor-pointer rounded-2xl border p-4 transition ${accountType==="affiliate_publisher"?"border-indigo-500 bg-indigo-50":"border-slate-200 bg-white"}`}>
                <input className="sr-only" type="radio" name="account_type" value="affiliate_publisher" checked={accountType==="affiliate_publisher"} onChange={()=>setAccountType("affiliate_publisher")}/>
                <span className="block font-black">Affiliate / Publisher</span>
                <span className="mt-2 block text-xs leading-5 text-slate-600">Find offers, apply to programmes, create content and track affiliate performance.</span>
              </label>
              <label className={`cursor-pointer rounded-2xl border p-4 transition ${accountType==="merchant_product_owner"?"border-emerald-500 bg-emerald-50":"border-slate-200 bg-white"}`}>
                <input className="sr-only" type="radio" name="account_type" value="merchant_product_owner" checked={accountType==="merchant_product_owner"} onChange={()=>setAccountType("merchant_product_owner")}/>
                <span className="block font-black">Merchant / Product Owner</span>
                <span className="mt-2 block text-xs leading-5 text-slate-600">Manage products, commission offers, publisher applications and partner performance.</span>
              </label>
            </div>
          </fieldset>
          <div>
            <label htmlFor="register-email" className="block text-sm font-bold">Email address</label>
            <input id="register-email" type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm"/>
          </div>
          <div>
            <label htmlFor="register-password" className="block text-sm font-bold">Password</label>
            <input id="register-password" type="password" autoComplete="new-password" minLength={14} required value={password} onChange={e=>setPassword(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm"/>
            <p className="mt-1 text-xs text-slate-500">Use at least 14 characters and a unique password.</p>
          </div>
          <div>
            <label htmlFor="register-workspace" className="block text-sm font-bold">First workspace name (optional)</label>
            <input id="register-workspace" value={workspaceName} onChange={e=>setWorkspaceName(e.target.value)} maxLength={160} placeholder="Defaults to a role-specific workspace name" className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 text-sm"/>
          </div>
          {error&&<p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
          <button type="submit" disabled={busy||!accountType} className="w-full rounded-xl bg-indigo-600 px-5 py-3.5 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-50">{busy?"Creating account…":"Create account"}</button>
        </form>
        <p className="mt-6 text-sm text-slate-500">Already registered? <a href="/" className="font-bold text-indigo-700">Sign in</a></p>
      </section>
    </div>
  </main>;
}

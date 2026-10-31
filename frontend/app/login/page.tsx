"use client";

import { useEffect,useState,type FormEvent } from "react";
import Link from "next/link";
import { ArrowLeft,Eye,EyeOff,Layers3,LoaderCircle,LockKeyhole } from "lucide-react";
import { apiFetch } from "@/lib/api";
type User={email?:string;account_type?:string;is_admin?:boolean};
function destination(user?:User){return user?.is_admin===true&&user.account_type==="platform_admin"?"/admin":"/dashboard";}

export default function LoginPage(){
 const [email,setEmail]=useState("");const [password,setPassword]=useState("");const [showPassword,setShowPassword]=useState(false);const [busy,setBusy]=useState(false);const [checking,setChecking]=useState(true);const [error,setError]=useState("");
 useEffect(()=>{let active=true;apiFetch<{user?:User}>("/api/auth/me").then(identity=>{if(active)window.location.replace(destination(identity.user));}).catch(()=>{if(active)setChecking(false);});return()=>{active=false;};},[]);
 const submit=async(event:FormEvent<HTMLFormElement>)=>{event.preventDefault();setBusy(true);setError("");try{const result=await apiFetch<{user?:User}>("/api/auth/login",{method:"POST",body:JSON.stringify({email:email.trim(),password})});window.location.replace(destination(result.user));}catch(cause){const message=cause instanceof Error?cause.message:"Sign in failed. Please try again.";setError(message.startsWith("401:")?"Those sign-in details did not match. Check your email and password and try again.":message);setBusy(false);}};
 return <main className="flex min-h-screen bg-[#f7f8fc] text-slate-900">
  <section className="flex w-full flex-col justify-center px-5 py-12 sm:px-10 lg:w-1/2 lg:px-20"><div className="mx-auto w-full max-w-md">
   <Link href="/" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-indigo-700"><ArrowLeft size={16}/> Back to home</Link>
   <Link href="/" className="mt-12 inline-flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-indigo-600 text-white"><Layers3 size={22}/></span><span className="text-xl font-black tracking-tight">OmniAffiliateOS</span></Link>
   <p className="mt-12 text-xs font-extrabold uppercase tracking-[.18em] text-indigo-600">Welcome back</p><h1 className="mt-3 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">Sign in to your workspace.</h1><p className="mt-3 text-sm leading-6 text-slate-600">Use the same account for your brand or partner workspace. We will take you to the right place.</p>
   <form onSubmit={submit} className="mt-8 space-y-5">
    <div><label htmlFor="login-email" className="block text-sm font-bold text-slate-800">Email address</label><input id="login-email" type="email" autoComplete="username" required value={email} onChange={event=>setEmail(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50" placeholder="you@company.com"/></div>
    <div><label htmlFor="login-password" className="block text-sm font-bold text-slate-800">Password</label><div className="relative mt-2"><input id="login-password" type={showPassword?"text":"password"} autoComplete="current-password" required value={password} onChange={event=>setPassword(event.target.value)} className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3.5 pr-12 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50" placeholder="Enter your password"/><button type="button" onClick={()=>setShowPassword(value=>!value)} aria-label={showPassword?"Hide password":"Show password"} className="absolute inset-y-0 right-0 grid w-12 place-items-center text-slate-400 hover:text-slate-700">{showPassword?<EyeOff size={17}/>:<Eye size={17}/>}</button></div></div>
    {error&&<p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    <button type="submit" disabled={busy||checking} className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3.5 text-sm font-extrabold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60">{busy?<><LoaderCircle className="animate-spin" size={17}/> Signing in…</>:"Sign in"}</button>
   </form>
   {checking&&<p className="mt-3 text-center text-xs text-slate-400">Checking your session…</p>}
   <p className="mt-7 text-center text-sm text-slate-500">New to OmniAffiliateOS? <Link href="/register" className="font-bold text-indigo-700 hover:underline">Create an account</Link></p>
   <p className="mt-9 flex items-center justify-center gap-2 text-xs text-slate-400"><LockKeyhole size={13}/> Your workspace access is protected by your account permissions.</p>
  </div></section>
  <aside className="relative hidden flex-1 items-center justify-center overflow-hidden bg-slate-950 px-12 lg:flex"><div className="absolute -right-32 -top-28 h-96 w-96 rounded-full bg-indigo-600/30 blur-3xl"/><div className="absolute -bottom-40 -left-20 h-96 w-96 rounded-full bg-sky-500/20 blur-3xl"/><div className="relative max-w-lg text-white"><span className="grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-white/10"><Layers3 size={27}/></span><h2 className="mt-8 text-4xl font-black leading-tight">Your work, your partners, one clear view.</h2><p className="mt-5 text-base leading-8 text-slate-300">Move from research to campaigns and performance evidence with practical tools that keep important decisions in your hands.</p><div className="mt-10 space-y-4 text-sm text-slate-300"><p>• A workspace shaped around your role</p><p>• Draft-first workflows and visible approvals</p><p>• Performance reporting grounded in recorded data</p></div></div></aside>
 </main>;
}

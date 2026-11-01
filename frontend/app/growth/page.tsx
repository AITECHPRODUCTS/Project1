"use client";
import { useEffect,useState } from "react";
import { LoaderCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";
import Link from "next/link";
import LegacyGrowthCommand from "@/components/LegacyGrowthCommand";
export default function GrowthPage(){
 const [ready,setReady]=useState(false);
 useEffect(()=>{let active=true;apiFetch<{user?:{account_type?:string;is_admin?:boolean}}>("/api/auth/me").then(({user})=>{if(!active)return;if(user?.account_type==="affiliate_publisher"||(user?.is_admin===true&&user.account_type==="platform_admin"))setReady(true);else window.location.replace(user?"/dashboard":"/login");}).catch(()=>{if(active)window.location.replace("/login");});return()=>{active=false;};},[]);
 if(!ready)return <main className="grid min-h-screen place-items-center bg-[#f7f8fc]"><div className="flex items-center gap-3 text-sm font-semibold text-slate-500"><LoaderCircle size={18} className="animate-spin text-indigo-600"/> Opening your growth workspace…</div></main>;
 return (
  <>
   <nav aria-label="Growth Studio workspace navigation" className="relative z-50 border-b border-slate-200 bg-white/95 text-slate-800 shadow-sm">
    <div className="mx-auto flex max-w-[1800px] items-center px-4 py-3 sm:px-6 lg:px-8">
     <Link href="/dashboard" className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-indigo-700 hover:border-indigo-200 hover:text-indigo-800">
      Workspace overview
     </Link>
    </div>
   </nav>
   <LegacyGrowthCommand/>
  </>
 );
}

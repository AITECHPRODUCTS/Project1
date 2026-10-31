"use client";
import { useEffect,useState } from "react";
import { LoaderCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";
import LegacyGrowthCommand from "@/components/LegacyGrowthCommand";
export default function GrowthPage(){
 const [ready,setReady]=useState(false);
 useEffect(()=>{let active=true;apiFetch<{user?:{account_type?:string;is_admin?:boolean}}>("/api/auth/me").then(({user})=>{if(!active)return;if(user?.account_type==="affiliate_publisher"||(user?.is_admin===true&&user.account_type==="platform_admin"))setReady(true);else window.location.replace(user?"/dashboard":"/login");}).catch(()=>{if(active)window.location.replace("/login");});return()=>{active=false;};},[]);
 if(!ready)return <main className="grid min-h-screen place-items-center bg-[#f7f8fc]"><div className="flex items-center gap-3 text-sm font-semibold text-slate-500"><LoaderCircle size={18} className="animate-spin text-indigo-600"/> Opening your growth workspace…</div></main>;
 return <LegacyGrowthCommand/>;
}

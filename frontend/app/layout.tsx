import type { Metadata, Viewport } from "next";
import "./globals.css";
import WorkspaceNavigation from "@/components/WorkspaceNavigation";
export const metadata:Metadata={title:"OmniAffiliateOS — Affiliate growth, made clearer",description:"One connected workspace for brands and partners to discover offers, manage programs, create campaigns and understand performance."};
export const viewport:Viewport={width:"device-width",initialScale:1,themeColor:"#f7f8fc"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><WorkspaceNavigation/>{children}</body></html>;}

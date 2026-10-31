import type { Metadata, Viewport } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "OmniAffiliateOS — Growth Command", description: "Evidence-first affiliate research, compliant creative, publishing and attribution in one operations console." };
export const viewport: Viewport = { width:"device-width",initialScale:1,themeColor:"#f8fafc" };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }

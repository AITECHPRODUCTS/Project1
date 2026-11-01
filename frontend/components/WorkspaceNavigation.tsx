"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ChevronDown, Home, LayoutDashboard, Layers3 } from "lucide-react";
import { apiFetch } from "@/lib/api";

type AccountType = "affiliate_publisher" | "merchant_product_owner" | "platform_admin";
type Identity = { user?: { email?: string; account_type?: AccountType; is_admin?: boolean } };
type NavItem = { label: string; href: string };
type NavGroup = { label: string; items: NavItem[] };

const publisherGroups: NavGroup[] = [
  { label: "Discover & Research", items: [
    { label: "Publisher marketplace", href: "/marketplace" },
    { label: "Affiliate offer catalog", href: "/offers" },
    { label: "Affiliate research", href: "/affiliate-research" },
    { label: "Offer qualification", href: "/offers/qualification" },
    { label: "Research brief", href: "/research-brief" },
    { label: "Traffic analyzer", href: "/growth?view=traffic-analyzer" },
    { label: "Multi-program manager", href: "/growth?view=multi-program-manager" }
  ]},
  { label: "Create & Optimize", items: [
    { label: "Content studio", href: "/growth?view=content-studio" },
    { label: "Article writer", href: "/listicle-writer" },
    { label: "Infographic maker", href: "/growth?view=infographic-maker" },
    { label: "Content angles", href: "/growth?view=content-angles" },
    { label: "X thread draft", href: "/growth?view=x-thread-draft" },
    { label: "Differentiation audit", href: "/growth?view=differentiation-audit" },
    { label: "SEO audit", href: "/growth?view=seo-audit" },
    { label: "Content moat", href: "/growth?view=content-moat" },
    { label: "Content decay", href: "/content-decay" },
    { label: "Internal links", href: "/growth?view=internal-links" },
    { label: "Guarantee draft", href: "/growth?view=guarantee-draft" },
    { label: "Category designer", href: "/growth?view=category-designer" }
  ]},
  { label: "Campaigns & Distribution", items: [
    { label: "Campaign tracking", href: "/campaigns" },
    { label: "Ad studio", href: "/growth?view=ad-studio" },
    { label: "Ad guardrails", href: "/ads/guardrails" },
    { label: "Bio link studio", href: "/bio-links" },
    { label: "Landing pages", href: "/landing-pages" },
    { label: "Leads & attribution", href: "/leads" },
    { label: "Email automations", href: "/email-automations" },
    { label: "Distribution queue", href: "/distribution" },
    { label: "Webinar registration", href: "/growth?view=webinars" }
  ]},
  { label: "Analytics & Revenue", items: [
    { label: "Measurement", href: "/growth?view=measurement" },
    { label: "Experiments", href: "/growth?view=experiments" },
    { label: "Learning dataset", href: "/growth?view=learning-dataset" },
    { label: "Commission calculator", href: "/commission-calculator" },
    { label: "Provider order reconciliation", href: "/finance/provider-orders" }
  ]},
  { label: "Automation & Governance", items: [
    { label: "Growth Studio overview", href: "/growth" },
    { label: "Flywheel", href: "/growth?view=flywheel" },
    { label: "AI knowledge", href: "/growth?view=ai-knowledge" },
    { label: "Program applications", href: "/growth?view=program-applications" },
    { label: "Skill finder", href: "/growth?view=skill-finder" },
    { label: "Skill packages", href: "/skills" },
    { label: "Integrations", href: "/integrations" },
    { label: "Compliance", href: "/compliance" }
  ]}
];

const merchantGroups: NavGroup[] = [
  { label: "Workspace", items: [
    { label: "Overview", href: "/dashboard" },
    { label: "Merchant dashboard", href: "/merchant" }
  ]},
  { label: "Program management", items: [
    { label: "Manage offers", href: "/merchant/offers" },
    { label: "Partner applications", href: "/merchant/applications" }
  ]}
];

const adminGroups: NavGroup[] = [
  { label: "Platform administration", items: [
    { label: "Operations overview", href: "/admin#platform-operations-title" },
    { label: "Incidents & recovery", href: "/admin#platform-incidents" },
    { label: "Tenant lifecycle", href: "/admin#tenant-lifecycle" },
    { label: "Provider readiness", href: "/admin#platform-provider-readiness" },
    { label: "Emergency controls", href: "/admin#platform-provider-write-pause" },
    { label: "Audit trail", href: "/admin#platform-audit-trail" }
  ]}
];

export default function WorkspaceNavigation() {
  const pathname = usePathname();
  const [identity, setIdentity] = useState<Identity["user"] | null>(null);
  const isAuthForm = pathname === "/login" || pathname === "/register";
  const isPublicRoute = pathname === "/" || isAuthForm || pathname.startsWith("/webinar/");

  useEffect(() => {
    let active = true;
    if (isPublicRoute) {
      setIdentity(null);
      return () => { active = false; };
    }
    apiFetch<Identity>("/api/auth/me")
      .then(response => { if (active) setIdentity(response.user || null); })
      .catch(() => { if (active) setIdentity(null); });
    return () => { active = false; };
  }, [pathname, isPublicRoute]);

  if (isPublicRoute || !identity) return null;
  const isAdmin = identity.account_type === "platform_admin" && identity.is_admin === true;
  const isMerchant = identity.account_type === "merchant_product_owner";
  const roleLabel = isAdmin ? "Platform Super Admin" : isMerchant ? "Merchant / Brand" : "Affiliate / Partner";
  const overviewHref = isAdmin ? "/admin" : "/dashboard";
  const groups = isAdmin ? adminGroups : isMerchant ? merchantGroups : publisherGroups;

  return (
    <header className="relative z-40 border-b border-slate-200 bg-white/95 text-slate-800 shadow-sm backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1800px] flex-wrap items-center gap-x-5 gap-y-3 px-4 py-3 sm:px-6 lg:px-8">
        <Link href={overviewHref} aria-label="OmniAffiliateOS workspace home" className="inline-flex shrink-0 items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-600 text-white"><Layers3 size={19}/></span>
          <span className="text-base font-black tracking-tight text-slate-950">OmniAffiliateOS</span>
        </Link>
        <nav aria-label="Primary workspace navigation" className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          {groups.map(group => (
            <details key={group.label} className="group relative">
              <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-100 hover:text-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-200">
                {group.label}<ChevronDown size={13} className="transition group-open:rotate-180"/>
              </summary>
              <div className="absolute left-0 top-full z-50 mt-2 max-h-[70vh] w-64 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 shadow-xl">
                {group.items.map(item => (
                  <Link key={item.href} href={item.href} className="block rounded-lg px-3 py-2.5 text-sm font-semibold text-slate-600 hover:bg-indigo-50 hover:text-indigo-700">
                    {item.label}
                  </Link>
                ))}
              </div>
            </details>
          ))}
        </nav>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <span className="hidden rounded-full bg-slate-100 px-3 py-2 text-[11px] font-bold text-slate-600 md:inline-flex">{roleLabel}</span>
          <Link href={overviewHref} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:border-indigo-200 hover:text-indigo-700">
            <Home size={14}/>Home
          </Link>
          <Link href={overviewHref} aria-current={pathname === overviewHref ? "page" : undefined} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white hover:bg-indigo-700">
            <LayoutDashboard size={14}/>{isAdmin ? "Admin overview" : "Workspace overview"}
          </Link>
        </div>
      </div>
    </header>
  );
}

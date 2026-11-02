"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight, ArrowUpRight, BarChart3, Building2, BriefcaseBusiness,
  CheckCircle2, ChevronDown, Compass, FileText, LoaderCircle, LogOut,
  Megaphone, Plug, RefreshCw, Search, Sparkles, Users, Wallet, Workflow
} from "lucide-react";
import { apiFetch } from "@/lib/api";

type AccountType = "affiliate_publisher" | "merchant_product_owner" | "platform_admin";
type Identity = {
  user?: {
    email?: string;
    account_type?: AccountType;
    is_admin?: boolean;
    workspace_id?: string;
    workspace_role?: string;
  };
};
type Workspace = {
  id: string;
  name: string;
  role?: string;
  lifecycle_state?: string;
  is_active?: boolean;
};
type WorkspaceList = {
  active_workspace_id?: string | null;
  data?: Workspace[];
};
type CountResponse = {
  count?: number;
  total_count?: number;
  data?: unknown[];
};
type StatusResponse = {
  clicks?: number;
  conversion_events?: number;
};
type Metric = { label: string; value: string; detail: string };
type ActionCard = {
  title: string;
  detail: string;
  href: string;
  icon: typeof Search;
  label: string;
};

function countOf(value: CountResponse | null) {
  if (!value) return "—";
  if (typeof value.count === "number") return value.count.toLocaleString();
  if (typeof value.total_count === "number") return value.total_count.toLocaleString();
  return Array.isArray(value.data) ? value.data.length.toLocaleString() : "—";
}

function metricValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString() : "—";
}

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [user, setUser] = useState<{ email: string; role: AccountType; workspaceRole: string } | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState("");
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [actions, setActions] = useState<ActionCard[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [switching, setSwitching] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    setError("");
    setNotice("");
    try {
      const identity = await apiFetch<Identity>("/api/auth/me");
      const account = identity.user;
      if (!account) {
        window.location.replace("/login");
        return;
      }
      if (account.is_admin === true && account.account_type === "platform_admin") {
        window.location.replace("/admin");
        return;
      }
      if (account.account_type !== "affiliate_publisher" && account.account_type !== "merchant_product_owner") {
        window.location.replace("/login");
        return;
      }

      setUser({
        email: account.email || "",
        role: account.account_type,
        workspaceRole: account.workspace_role || "member"
      });

      const ws = await apiFetch<WorkspaceList>("/api/workspaces").catch(() => null);
      const rows = Array.isArray(ws?.data) ? ws!.data.filter(row => row.lifecycle_state !== "suspended") : [];
      setWorkspaces(rows);
      setActiveWorkspace(
        ws?.active_workspace_id ||
        rows.find(row => row.is_active)?.id ||
        rows[0]?.id ||
        account.workspace_id ||
        ""
      );

      if (account.account_type === "merchant_product_owner") {
        const [offersResult, applicationsResult] = await Promise.allSettled([
          apiFetch<CountResponse>("/api/merchant/offers?limit=300"),
          apiFetch<CountResponse>("/api/merchant/applications?limit=1&offset=0&status=pending_review")
        ]);
        const offers = offersResult.status === "fulfilled" ? offersResult.value : null;
        const applications = applicationsResult.status === "fulfilled" ? applicationsResult.value : null;
        setMetrics([
          { label: "Offer records", value: countOf(offers), detail: "Offers saved in this workspace" },
          { label: "Applications to review", value: countOf(applications), detail: "Partner applications awaiting a decision" },
          { label: "Workspaces you can access", value: rows.length ? rows.length.toLocaleString() : "—", detail: "Based on your active memberships" },
          { label: "Your workspace role", value: (account.workspace_role || "member").replaceAll("_", " "), detail: "Access granted by this workspace" }
        ]);
        if (offersResult.status === "rejected" || applicationsResult.status === "rejected") {
          setNotice("Some workspace information could not be loaded. Open the relevant section and retry.");
        }
        setActions([
          { title: "Manage your offers", detail: "Create and maintain the offers your partners can promote.", href: "/merchant/offers", icon: BriefcaseBusiness, label: "Open offers" },
          { title: "Review partner applications", detail: "See applicants and make an internal decision with an audit trail.", href: "/merchant/applications", icon: Users, label: "Review applications" },
          { title: "Merchant workspace", detail: "Open your detailed offer, partner and program overview.", href: "/merchant", icon: Building2, label: "Open workspace" },
          { title: "Performance and measurement", detail: "Explore recorded activity, attribution and available reporting tools.", href: "/finance/provider-orders", icon: BarChart3, label: "Review financial evidence" }
        ]);
      } else {
        const [statusResult, offersResult, applicationsResult, campaignsResult] = await Promise.allSettled([
          apiFetch<StatusResponse>("/api/status"),
          apiFetch<CountResponse>("/api/marketplace/offers?limit=100"),
          apiFetch<CountResponse>("/api/marketplace/applications?limit=100"),
          apiFetch<CountResponse>("/api/campaigns")
        ]);
        const status = statusResult.status === "fulfilled" ? statusResult.value : null;
        const offers = offersResult.status === "fulfilled" ? offersResult.value : null;
        const applications = applicationsResult.status === "fulfilled" ? applicationsResult.value : null;
        const campaigns = campaignsResult.status === "fulfilled" ? campaignsResult.value : null;
        setMetrics([
          { label: "Tracked clicks", value: metricValue(status?.clicks), detail: "First-party click records in this workspace" },
          { label: "Conversion events", value: metricValue(status?.conversion_events), detail: "Recorded events; not all are confirmed" },
          { label: "Offers to explore", value: countOf(offers), detail: "Offers approved and listed by OmniAffiliateOS merchants" },
          { label: "Your applications", value: countOf(applications), detail: "Applications recorded for this workspace" },
          { label: "Campaigns", value: countOf(campaigns), detail: "Persisted campaign tracking records" }
        ]);
        if ([statusResult, offersResult, applicationsResult, campaignsResult].some(result => result.status === "rejected")) {
          setNotice("Some activity could not be loaded just now. Use Refresh or open the relevant tool to try again.");
        }
        setActions([
          { title: "Connect affiliate accounts", detail: "Set up supported read-only accounts to research provider catalogues and import available reporting evidence.", href: "/integrations", icon: Plug, label: "Manage integrations" },
          { title: "My programs", detail: "Review merchant application decisions, tracked referral links, recorded clicks and commission evidence by program.", href: "/programs", icon: BriefcaseBusiness, label: "Open my programs" },
          { title: "Explore the marketplace", detail: "Find offers reviewed and listed by OmniAffiliateOS merchants before applying.", href: "/marketplace", icon: Search, label: "Explore offers" },
          { title: "Research an opportunity", detail: "Search connected Digistore24 and Flipkart catalogues and compare provider-reported evidence.", href: "/affiliate-research", icon: Compass, label: "Start research" },
          { title: "Create organic content", detail: "Prepare article, comparison and SEO drafts for your audience; review facts and disclosures before publishing.", href: "/listicle-writer", icon: FileText, label: "Create content" },
          { title: "Build a landing page", detail: "Prepare a disclosure-aware destination and lead-capture flow for an organic campaign.", href: "/landing-pages", icon: Workflow, label: "Open landing pages" },
          { title: "Capture and manage leads", detail: "Review consent, first-touch and last-touch attribution, and workspace lead records.", href: "/leads", icon: Users, label: "Open leads" },
          { title: "Plan and track campaigns", detail: "Create first-party tracking links and measure clicks before relying on provider conversion reports.", href: "/campaigns", icon: Megaphone, label: "Open campaigns" },
          { title: "Growth workspace", detail: "Access publisher research, AI-assisted creation and optimization tools.", href: "/growth", icon: Sparkles, label: "Open Growth Studio" },
          { title: "Earnings evidence", detail: "Review provider order observations and commission reconciliation without assuming payment.", href: "/finance/provider-orders", icon: Wallet, label: "Review earnings" }
        ]);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Your workspace could not be loaded.";
      if (message.startsWith("401:")) window.location.replace("/login");
      else setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const switchWorkspace = async (nextId: string) => {
    if (!nextId || nextId === activeWorkspace || switching) return;
    setSwitching(true);
    setError("");
    try {
      const result = await apiFetch<{ active_workspace_id?: string }>(
        "/api/workspaces/" + encodeURIComponent(nextId) + "/switch",
        { method: "POST" }
      );
      if (result.active_workspace_id !== nextId) {
        throw new Error("The server did not confirm the workspace change.");
      }
      window.location.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Workspace switch failed.");
      setSwitching(false);
    }
  };

  const signOut = async () => {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign out failed.");
      return;
    }
    window.location.replace("/");
  };

  const greeting = user?.email?.split("@")[0] || "there";

  if (loading && !user) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#f7f8fc]">
        <div className="flex items-center gap-3 text-sm font-semibold text-slate-500">
          <LoaderCircle size={18} className="animate-spin text-indigo-600" />
          Opening your workspace…
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#f7f8fc] text-slate-900">
      <div className="mx-auto max-w-7xl px-5 py-8 lg:px-8 lg:py-10">
        <section aria-label="Workspace overview">
          <header className="flex flex-wrap items-end justify-between gap-5">
            <div className="min-w-0">
              <p className="text-xs font-extrabold uppercase tracking-[.18em] text-indigo-600">Workspace overview</p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">Your workspace, at a glance.</h1>
              <p className="mt-2 text-sm leading-6 text-slate-600">Welcome back, {greeting}. Here is a clear starting point for your next step.</p>
              {user?.email && (
                <p className="mt-2 text-xs text-slate-400">Signed in as {user.email} · {user.workspaceRole.replaceAll("_", " ")}</p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {workspaces.length > 1 && (
                <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-600">
                  <Building2 size={15} />
                  <span className="sr-only">Active workspace</span>
                  <select
                    aria-label="Active workspace"
                    value={activeWorkspace}
                    onChange={event => void switchWorkspace(event.target.value)}
                    disabled={switching}
                    className="max-w-44 bg-transparent text-sm text-slate-800 outline-none"
                  >
                    {workspaces.map(workspace => (
                      <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
                    ))}
                  </select>
                  <ChevronDown size={13} />
                </label>
              )}
              <button
                type="button"
                onClick={() => void load()}
                disabled={refreshing}
                aria-label="Refresh workspace"
                className="grid h-10 w-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:text-indigo-700 disabled:opacity-50"
              >
                <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
              </button>
              <button
                type="button"
                onClick={() => void signOut()}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-bold text-slate-600 hover:bg-slate-100"
              >
                <LogOut size={16} /><span>Sign out</span>
              </button>
              <Link
                href={user?.role === "merchant_product_owner" ? "/merchant/offers" : "/integrations"}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-extrabold text-white hover:bg-indigo-700"
              >
                {user?.role === "merchant_product_owner" ? "Manage offers" : "Connect accounts"} <ArrowUpRight size={16} />
              </Link>
            </div>
          </header>

          {error && <p role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
          {notice && <p role="status" className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{notice}</p>}

          <div className={"mt-8 grid gap-3 " + (metrics.length > 4 ? "sm:grid-cols-2 xl:grid-cols-3" : "sm:grid-cols-2 xl:grid-cols-4")}>
            {metrics.map(metric => (
              <article key={metric.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/40">
                <p className="text-xs font-bold uppercase tracking-wider text-slate-400">{metric.label}</p>
                <p className="mt-3 text-3xl font-black tracking-tight tabular-nums text-slate-950">{metric.value}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{metric.detail}</p>
              </article>
            ))}
            {!metrics.length && !loading && (
              <article className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500 sm:col-span-2">
                Workspace information is not available yet. Refresh to try again.
              </article>
            )}
          </div>

          <div className="mt-10 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-black text-slate-950">Your organic growth workflow</h2>
              <p className="mt-1 text-sm text-slate-500">Connect, research, create, capture and measure — with review before external actions.</p>
            </div>
            <span className="hidden rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-500 sm:inline-flex">{actions.length} workspace tools</span>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {actions.map(({ title, detail, href, icon: Icon, label }) => (
              <article key={title} className="group flex min-h-48 flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/30 transition hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-lg">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-indigo-50 text-indigo-700"><Icon size={19} /></span>
                <h3 className="mt-4 font-extrabold text-slate-900">{title}</h3>
                <p className="mt-2 flex-1 text-sm leading-6 text-slate-600">{detail}</p>
                <Link href={href} className="mt-4 inline-flex items-center gap-2 text-sm font-extrabold text-indigo-700">{label} <ArrowRight size={15} /></Link>
              </article>
            ))}
          </div>

          <div className="mt-8 flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex gap-3">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-600"><CheckCircle2 size={19} /></span>
              <div>
                <h3 className="text-sm font-extrabold text-slate-900">A note about your numbers</h3>
                <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500">Counts come from active workspace APIs. Empty records stay at zero, and missing information is shown as a dash — not an invented estimate. A recorded click is not a conversion, a provider-reported commission is not a confirmed earning, and an earning is not the same as a confirmed payout.</p>
              </div>
            </div>
            {workspaces.length > 1 && <p className="text-xs font-semibold text-slate-500">{workspaces.length} active workspaces available from the selector above.</p>}
          </div>
        </section>
      </div>
    </main>
  );
}

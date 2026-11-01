"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

type EvidenceTotal = { currency: string; evidence_status: string; commission_total: string };
type ProgramApplication = {
  id: string;
  merchant_offer_id: string;
  offer_name: string;
  status: string;
  created_at: string | null;
  reviewed_at: string | null;
  reviewer_notes: string | null;
  terms_snapshot: Record<string, unknown>;
  provider_submission_status: string;
  affiliate_network_approved: boolean;
  promotion_url: string | null;
  promotion_link_status: string | null;
  tracked_clicks: number;
  commission_observations: EvidenceTotal[];
  earnings_note: string;
};
type Filter = "all" | "approved" | "pending_review" | "rejected";
const filters: { value: Filter; label: string }[] = [
  { value: "all", label: "All programs" },
  { value: "approved", label: "Merchant approved" },
  { value: "pending_review", label: "Pending review" },
  { value: "rejected", label: "Rejected" },
];

function textValue(value: unknown, fallback = "Not recorded"): string {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}
function listValue(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0) : [];
}
function pretty(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, character => character.toUpperCase());
}
function dateValue(value: string | null): string {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Not recorded" : parsed.toLocaleDateString();
}

export default function ProgramsPage() {
  const [applications, setApplications] = useState<ProgramApplication[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const identity = await apiFetch<{ user?: { account_type?: string } }>("/api/auth/me");
      if (identity.user?.account_type !== "affiliate_publisher") {
        window.location.replace(identity.user ? "/dashboard" : "/login");
        return;
      }
      const result = await apiFetch<{ count?: number; data?: ProgramApplication[] }>(
        "/api/marketplace/applications?limit=300"
      );
      setApplications(Array.isArray(result.data) ? result.data : []);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Your programs could not be loaded.";
      if (message.startsWith("401:")) window.location.replace("/login");
      else setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return applications.filter(application => {
      if (filter !== "all" && application.status !== filter) return false;
      if (!query) return true;
      const haystack = [
        application.offer_name,
        application.status,
        textValue(application.terms_snapshot.category, ""),
        textValue(application.terms_snapshot.terms_version, ""),
      ].join(" ").toLowerCase();
      return haystack.includes(query);
    });
  }, [applications, filter, search]);

  const approvedCount = applications.filter(item => item.status === "approved").length;
  const pendingCount = applications.filter(item => item.status === "pending_review").length;
  const activeLinkCount = applications.filter(
    item => item.status === "approved" && item.promotion_link_status === "active" && !!item.promotion_url
  ).length;
  const trackedClicks = applications.reduce(
    (total, item) => total + (Number.isFinite(item.tracked_clicks) ? item.tracked_clicks : 0),
    0
  );

  const copyReferralLink = async (url: string) => {
    setNotice("");
    setError("");
    try {
      await navigator.clipboard.writeText(url);
      setNotice("Tracked referral link copied.");
    } catch {
      setError("Clipboard access was blocked by this browser. Select and copy the link shown on the program card.");
    }
  };

  return (
    <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-6">
          <div>
            <Link href="/dashboard" className="text-sm font-bold text-indigo-700">← Workspace overview</Link>
            <p className="mt-5 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Affiliate · Partner workspace</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">My programs</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
              Follow merchant applications, access approved tracked links and review the activity and commission evidence recorded for each program.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/marketplace" className="rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white">Find programs</Link>
            <Link href="/publisher" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold">Publisher tools</Link>
            <button type="button" onClick={() => void load()} disabled={loading} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">
              {loading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </header>

        {error && <p role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
        {notice && <p role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</p>}

        <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Program summary">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Applications / programs</p>
            <p className="mt-3 text-3xl font-black tabular-nums">{applications.length}</p>
            <p className="mt-1 text-xs text-slate-500">Records in this publisher workspace; up to 300 loaded.</p>
          </article>
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Merchant approved</p>
            <p className="mt-3 text-3xl font-black tabular-nums">{approvedCount}</p>
            <p className="mt-1 text-xs text-slate-500">Internal merchant decisions, not external network approval.</p>
          </article>
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Tracked links active</p>
            <p className="mt-3 text-3xl font-black tabular-nums">{activeLinkCount}</p>
            <p className="mt-1 text-xs text-slate-500">Approved programs with an active first-party promotion link.</p>
          </article>
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Tracked clicks</p>
            <p className="mt-3 text-3xl font-black tabular-nums">{trackedClicks.toLocaleString()}</p>
            <p className="mt-1 text-xs text-slate-500">Recorded first-party clicks across the loaded program links.</p>
          </article>
        </section>

        <section className="mt-7 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7" aria-labelledby="program-list-title">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 id="program-list-title" className="text-xl font-black">Your merchant programs</h2>
              <p className="mt-1 text-sm text-slate-500">{pendingCount} application(s) currently awaiting merchant review.</p>
            </div>
            <label className="block w-full text-sm font-bold sm:max-w-sm" htmlFor="program-search">
              Search programs
              <input id="program-search" type="search" value={search} onChange={event => setSearch(event.target.value)}
                placeholder="Search by offer name, category or terms version"
                className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm font-normal" />
            </label>
          </div>

          <div className="mt-5 flex flex-wrap gap-2" role="group" aria-label="Filter programs by application status">
            {filters.map(item => (
              <button key={item.value} type="button" aria-pressed={filter === item.value}
                onClick={() => setFilter(item.value)}
                className={"rounded-full border px-4 py-2 text-sm font-bold " + (
                  filter === item.value ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:text-indigo-700"
                )}>
                {item.label}
              </button>
            ))}
          </div>

          {loading && <p role="status" className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">Loading programs from your publisher workspace…</p>}
          {!loading && filtered.length === 0 && (
            <div className="mt-5 rounded-2xl border border-dashed border-slate-300 p-7 text-center">
              <h3 className="font-bold text-slate-800">{applications.length ? "No programs match this view" : "No programs yet"}</h3>
              <p className="mt-2 text-sm text-slate-500">
                {applications.length ? "Change the status filter or search term to see other applications." : "Browse merchant-listed offers and submit an application to start building your program list."}
              </p>
              {!applications.length && <Link href="/marketplace" className="mt-4 inline-flex rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white">Explore merchant offers</Link>}
            </div>
          )}

          <div className="mt-5 grid gap-4">
            {filtered.map(application => {
              const terms = application.terms_snapshot || {};
              const approved = application.status === "approved";
              const linkActive = approved && application.promotion_link_status === "active" && !!application.promotion_url;
              const allowedRegions = listValue(terms.allowed_regions);
              const restrictedTraffic = listValue(terms.restricted_traffic_sources);
              const commission = textValue(terms.commission_value, "Not recorded");
              const currency = textValue(terms.commission_currency, "");
              const commissionType = pretty(textValue(terms.commission_type, "terms not recorded"));
              return (
                <article key={application.id} data-testid="publisher-program-card" data-program-id={application.id} className="rounded-2xl border border-slate-200 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-bold uppercase tracking-wider text-indigo-600">{textValue(terms.category, "Merchant offer")}</p>
                      <h3 className="mt-1 text-lg font-black text-slate-900">{application.offer_name}</h3>
                      <p className="mt-1 text-xs text-slate-500">Terms {textValue(terms.terms_version)} · Applied {dateValue(application.created_at)}</p>
                    </div>
                    <span className={"rounded-full px-3 py-1.5 text-xs font-bold " + (
                      approved ? "bg-emerald-50 text-emerald-800" :
                      application.status === "pending_review" ? "bg-amber-50 text-amber-900" :
                      "bg-slate-100 text-slate-700"
                    )}>
                      {approved ? "Merchant approved" : pretty(application.status)}
                    </span>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Commission terms</p><p className="mt-1 text-sm font-bold">{commission}{currency ? " " + currency : ""} · {commissionType}</p></div>
                    <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Cookie / attribution</p><p className="mt-1 text-sm font-bold">{textValue(terms.cookie_days, "—")} / {textValue(terms.attribution_window_days, "—")} days</p></div>
                    <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Tracked clicks</p><p className="mt-1 text-sm font-bold tabular-nums">{(application.tracked_clicks || 0).toLocaleString()}</p></div>
                    <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Promotion link</p><p className="mt-1 text-sm font-bold">{linkActive ? "Active" : approved ? "Not available" : "Available after approval"}</p></div>
                  </div>

                  {application.promotion_url && linkActive && (
                    <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50/50 p-4">
                      <p className="text-xs font-bold uppercase tracking-wider text-emerald-900">Your tracked referral link</p>
                      <a href={application.promotion_url} target="_blank" rel="noopener noreferrer" className="mt-2 block break-all text-sm font-semibold text-indigo-700 underline">{application.promotion_url}</a>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <button type="button" onClick={() => void copyReferralLink(application.promotion_url!)} className="rounded-lg bg-white px-3 py-2 text-xs font-bold text-slate-700">Copy link</button>
                        <span className="text-xs text-slate-600">First-party tracked destination</span>
                      </div>
                    </div>
                  )}

                  {application.commission_observations?.length > 0 && (
                    <div className="mt-4 rounded-xl border border-slate-200 p-4">
                      <h4 className="text-sm font-black">Recorded commission observations</h4>
                      <div className="mt-2 space-y-2">
                        {application.commission_observations.map((item, index) => (
                          <div key={item.currency + item.evidence_status + index} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 py-2 last:border-0">
                            <span className="text-sm text-slate-600">{item.currency} · {pretty(item.evidence_status)}</span>
                            <strong className="text-sm tabular-nums">{item.commission_total}</strong>
                          </div>
                        ))}
                      </div>
                      <p className="mt-2 text-xs leading-5 text-slate-500">{application.earnings_note}</p>
                    </div>
                  )}

                  <details className="mt-4 rounded-xl border border-slate-200 p-4">
                    <summary className="cursor-pointer text-sm font-bold text-slate-700">Program terms, restrictions and approval details</summary>
                    <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                      <div><p className="text-xs font-bold uppercase text-slate-400">Allowed regions</p><p className="mt-1">{allowedRegions.join(", ") || "Not recorded"}</p></div>
                      <div><p className="text-xs font-bold uppercase text-slate-400">Restricted traffic sources</p><p className="mt-1">{restrictedTraffic.join(", ") || "No restrictions recorded in this snapshot"}</p></div>
                      <div><p className="text-xs font-bold uppercase text-slate-400">Refund hold</p><p className="mt-1">{textValue(terms.refund_hold_days, "—")} days</p></div>
                      <div><p className="text-xs font-bold uppercase text-slate-400">Payout terms in merchant snapshot</p><p className="mt-1">{textValue(terms.payout_schedule)} · minimum {textValue(terms.minimum_payout_amount, "—")} {currency}</p></div>
                      <div><p className="text-xs font-bold uppercase text-slate-400">Provider submission</p><p className="mt-1">{pretty(application.provider_submission_status || "unknown")}</p></div>
                      <div><p className="text-xs font-bold uppercase text-slate-400">External affiliate-network approval</p><p className="mt-1">{application.affiliate_network_approved ? "Verified by provider" : "Not configured / not verified"}</p></div>
                      <div><p className="text-xs font-bold uppercase text-slate-400">Merchant review date</p><p className="mt-1">{dateValue(application.reviewed_at)}</p></div>
                      {typeof terms.commission_terms_url === "string" && terms.commission_terms_url.startsWith("https://") && (
                        <div><p className="text-xs font-bold uppercase text-slate-400">Terms reference</p><a href={terms.commission_terms_url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block break-all font-semibold text-indigo-700 underline">Open merchant terms</a></div>
                      )}
                    </div>
                    {application.reviewer_notes && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">Merchant review note: {application.reviewer_notes}</p>}
                  </details>
                </article>
              );
            })}
          </div>
        </section>

        <p className="mt-6 rounded-2xl border border-indigo-100 bg-indigo-50 p-4 text-xs leading-5 text-indigo-950">
          Evidence boundary: merchant approval inside OmniAffiliateOS does not prove acceptance by an external affiliate network. Click counts are first-party tracking records; commission observations are not confirmed earnings or proof of funds received. Partner chat, referred-customer profiles and cash withdrawal are not enabled in this workspace yet.
        </p>
      </div>
    </main>
  );
}

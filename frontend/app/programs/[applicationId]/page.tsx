"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

type EvidenceRow = {
  currency: string;
  evidence_status: string;
  entry_type: string;
  entry_count: string;
  commission_total: string;
  revenue_total: string;
};
type ProgramLink = {
  id: string;
  label: string;
  destination_url: string;
  campaign_id: string;
  promotion_url: string;
  status: string;
  is_primary: boolean;
  clicks_all_time: number;
  conversion_entries: number;
};
type ProgramDetail = {
  id: string;
  links?: ProgramLink[];
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
  promotion_campaign_id: string | null;
  tracked_clicks: number;
  commission_observations: EvidenceRow[];
  performance: {
    clicks_all_time: number;
    clicks_last_30_days: number;
    clicks_by_day: { date: string; clicks: number }[];
    conversion_entries: number;
  };
  performance_note: string;
  earnings_note: string;
};
type Tab = "overview" | "links" | "commissions" | "terms" | "customers" | "messages" | "payouts";
const tabs: { id: Tab; label: string; available: boolean }[] = [
  { id: "overview", label: "Overview", available: true },
  { id: "links", label: "Links", available: true },
  { id: "commissions", label: "Commissions", available: true },
  { id: "terms", label: "Terms", available: true },
  { id: "customers", label: "Customers · not available", available: false },
  { id: "messages", label: "Messages · not available", available: false },
  { id: "payouts", label: "Payouts · not available", available: false },
];

function value(input: unknown, fallback = "Not recorded"): string {
  if (typeof input === "string" && input.trim()) return input.trim();
  if (typeof input === "number" && Number.isFinite(input)) return String(input);
  return fallback;
}
function pretty(input: string): string {
  return input.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}
function dateLabel(input: string | null): string {
  if (!input) return "Not recorded";
  const date = new Date(input);
  return Number.isNaN(date.getTime()) ? "Not recorded" : date.toLocaleString();
}
function amount(input: string, currency: string): string {
  return input + " " + currency;
}

export default function PublisherProgramDetailPage() {
  const params = useParams<{ applicationId: string }>();
  const applicationId = params.applicationId;
  const [program, setProgram] = useState<ProgramDetail | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [linkLabel, setLinkLabel] = useState("Social profile link");
  const [linkDestination, setLinkDestination] = useState("");
  const [creatingLink, setCreatingLink] = useState(false);

  const load = useCallback(async () => {
    if (!applicationId) return;
    setLoading(true);
    setError("");
    try {
      const identity = await apiFetch<{ user?: { account_type?: string } }>("/api/auth/me");
      if (identity.user?.account_type !== "affiliate_publisher") {
        window.location.replace(identity.user ? "/dashboard" : "/login");
        return;
      }
      const result = await apiFetch<ProgramDetail>(
        "/api/marketplace/applications/" + encodeURIComponent(applicationId)
      );
      setProgram(result);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Program details could not be loaded.";
      if (message.startsWith("401:")) window.location.replace("/login");
      else setError(message);
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => { void load(); }, [load]);

  const copyLink = async () => {
    if (!program?.promotion_url) return;
    setNotice("");
    setError("");
    try {
      await navigator.clipboard.writeText(program.promotion_url);
      setNotice("Tracked referral link copied.");
    } catch {
      setError("Clipboard access was blocked. Select and copy the referral URL shown below.");
    }
  };

  const createLink = async () => {
    if (!applicationId || !linkLabel.trim()) return;
    setCreatingLink(true);
    setError("");
    setNotice("");
    try {
      await apiFetch<ProgramLink>(
        "/api/marketplace/applications/" + encodeURIComponent(applicationId) + "/links",
        {
          method: "POST",
          body: JSON.stringify({
            label: linkLabel.trim(),
            destination_url: linkDestination.trim() || null,
          }),
        }
      );
      setNotice("Additional tracked referral link created.");
      setLinkLabel("");
      setLinkDestination("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The referral link could not be created.");
    } finally {
      setCreatingLink(false);
    }
  };

  const terms = program?.terms_snapshot ?? {};
  const approved = program?.status === "approved";
  const activeLink = approved && program?.promotion_link_status === "active" && !!program?.promotion_url;
  const maxClicks = Math.max(1, ...(program?.performance.clicks_by_day.map(point => point.clicks) ?? [1]));

  return (
    <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-6">
          <div>
            <Link href="/programs" className="text-sm font-bold text-indigo-700">← My programs</Link>
            <p className="mt-5 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Affiliate · Partner workspace</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">{program?.offer_name ?? "Program workspace"}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
              Program-specific tracking, terms and financial evidence. Merchant approval is separate from external affiliate-network approval.
            </p>
          </div>
          <button type="button" onClick={() => void load()} disabled={loading}
            className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </header>

        {error && <p role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
        {notice && <p role="status" className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</p>}
        {loading && <p role="status" className="mt-6 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600">Loading this publisher program…</p>}
        {!loading && !error && !program && <p role="alert" className="mt-6 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600">This program is not available in the active publisher workspace.</p>}

        {program && (
          <>
            <section className="mt-6 flex flex-wrap items-center gap-3">
              <span className={"rounded-full px-3 py-1.5 text-xs font-bold " + (approved ? "bg-emerald-50 text-emerald-800" : program.status === "pending_review" ? "bg-amber-50 text-amber-900" : "bg-slate-100 text-slate-700")}>
                {approved ? "Merchant approved" : pretty(program.status)}
              </span>
              <span className="text-xs text-slate-500">Applied {dateLabel(program.created_at)} · Terms {value(terms.terms_version)}</span>
              <span className="text-xs text-slate-500">Network approval: {program.affiliate_network_approved ? "provider verified" : "not configured / not verified"}</span>
            </section>

            <nav className="mt-6 flex flex-wrap gap-2 border-b border-slate-200 pb-4" aria-label="Program sections">
              {tabs.map(item => (
                <button key={item.id} type="button" aria-pressed={tab === item.id}
                  onClick={() => setTab(item.id)}
                  className={"rounded-xl border px-3 py-2.5 text-sm font-bold " + (tab === item.id ? "border-indigo-600 bg-indigo-600 text-white" : item.available ? "border-slate-200 bg-white text-slate-700" : "border-dashed border-slate-200 bg-slate-50 text-slate-400")}>
                  {item.label}
                </button>
              ))}
            </nav>

            {tab === "overview" && (
              <section className="mt-6 space-y-5">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {[
                    ["Tracked clicks", program.performance.clicks_all_time, "First-party tracked visits, all time"],
                    ["Clicks · 30 days", program.performance.clicks_last_30_days, "Recorded in the last 30 days"],
                    ["Conversion entries", program.performance.conversion_entries, "Evidence-ledger conversion entries"],
                    ["Commission groups", program.commission_observations.length, "Grouped by currency, evidence and event type"],
                  ].map(([label, count, note]) => (
                    <article key={String(label)} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                      <p className="text-xs font-bold uppercase tracking-wider text-slate-400">{label}</p>
                      <p className="mt-3 text-3xl font-black tabular-nums">{count}</p>
                      <p className="mt-1 text-xs text-slate-500">{note}</p>
                    </article>
                  ))}
                </div>
                <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h2 className="text-lg font-black">Click activity · last 30 days</h2>
                  {program.performance.clicks_by_day.length === 0 ? (
                    <p className="mt-3 rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">No clicks have been recorded in this period.</p>
                  ) : (
                    <div className="mt-4 space-y-3">
                      {program.performance.clicks_by_day.map(point => (
                        <div key={point.date} className="grid grid-cols-[100px_1fr_40px] items-center gap-3 text-xs">
                          <span className="text-slate-500">{point.date}</span>
                          <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-indigo-500" style={{ width: ((point.clicks / maxClicks) * 100) + "%" }} /></div>
                          <strong className="text-right tabular-nums">{point.clicks}</strong>
                        </div>
                      ))}
                    </div>
                  )}
                  <p className="mt-4 text-xs leading-5 text-slate-500">{program.performance_note}</p>
                </article>
              </section>
            )}

            {tab === "links" && (
              <section className="mt-6 space-y-5">
                <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-black">Referral links</h2>
                      <p className="mt-1 text-sm text-slate-500">Each link has its own campaign ID, click count and conversion evidence while remaining attached to this approved merchant program.</p>
                    </div>
                    <span className="rounded-full bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-700">{(program.links?.length ?? (program.promotion_url ? 1 : 0))} / 20 links</span>
                  </div>
                  {(program.links && program.links.length > 0) ? (
                    <div className="mt-4 space-y-3">
                      {program.links.map(item => (
                        <div key={item.id} className="rounded-xl border border-slate-200 p-4">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="font-bold text-slate-800">{item.label}{item.is_primary ? " · primary" : ""}</p>
                            <span className={"rounded-full px-2.5 py-1 text-xs font-bold " + (item.status === "active" ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-600")}>{item.status}</span>
                          </div>
                          <a href={item.promotion_url} target="_blank" rel="noopener noreferrer" className="mt-2 block break-all text-sm font-semibold text-indigo-700 underline">{item.promotion_url}</a>
                          <p className="mt-2 break-all text-xs text-slate-500">Destination: {item.destination_url}</p>
                          <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-600">
                            <span><strong className="text-slate-900">{item.clicks_all_time}</strong> clicks</span>
                            <span><strong className="text-slate-900">{item.conversion_entries}</strong> conversion entries</span>
                          </div>
                          <button type="button" onClick={() => { void navigator.clipboard.writeText(item.promotion_url).then(() => setNotice("Tracked referral link copied.")).catch(() => setError("Clipboard access was blocked. Select and copy the referral URL.")); }}
                            className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700">Copy link</button>
                        </div>
                      ))}
                    </div>
                  ) : program.promotion_url ? (
                    <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50/60 p-4">
                      <p className="text-xs font-bold uppercase tracking-wider text-emerald-900">Primary tracked link · active</p>
                      <a href={program.promotion_url} target="_blank" rel="noopener noreferrer" className="mt-2 block break-all text-sm font-semibold text-indigo-700 underline">{program.promotion_url}</a>
                      <p className="mt-2 text-xs text-slate-600">Campaign reference: {program.promotion_campaign_id || "Not recorded"}</p>
                      <button type="button" onClick={() => void copyLink()} className="mt-3 rounded-lg bg-white px-3 py-2 text-xs font-bold text-slate-700">Copy link</button>
                    </div>
                  ) : (
                    <p className="mt-4 rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-600">A tracked link is issued only after merchant approval and activation. Current status: {pretty(program.promotion_link_status || "not issued")}.</p>
                  )}
                </article>

                {approved && (
                  <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                    <h3 className="text-base font-black">Create another referral link</h3>
                    <p className="mt-1 text-sm text-slate-500">Use a distinct label for each channel or placement. Destinations must remain on the merchant's verified HTTPS domain.</p>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <label className="text-xs font-bold text-slate-600">Link label
                        <input value={linkLabel} onChange={event => setLinkLabel(event.target.value)} maxLength={120} placeholder="e.g. Instagram bio" className="mt-1 block w-full rounded-xl border border-slate-200 px-3 py-3 text-sm font-normal text-slate-800" />
                      </label>
                      <label className="text-xs font-bold text-slate-600">Destination URL (optional)
                        <input value={linkDestination} onChange={event => setLinkDestination(event.target.value)} type="url" maxLength={2048} placeholder="https://merchant.example.com/pricing" className="mt-1 block w-full rounded-xl border border-slate-200 px-3 py-3 text-sm font-normal text-slate-800" />
                      </label>
                    </div>
                    <button type="button" onClick={() => void createLink()} disabled={creatingLink || !linkLabel.trim() || (program.links?.length ?? 1) >= 20}
                      className="mt-4 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">
                      {creatingLink ? "Creating link…" : "Create tracked link"}
                    </button>
                    <p className="mt-2 text-xs text-slate-500">Maximum 20 links per approved program. Each link is tracked separately and contributes to the program's merchant conversion and commission reporting.</p>
                  </article>
                )}
              </section>
            )}

            {tab === "commissions" && (
              <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-black">Commission observations</h2>
                {program.commission_observations.length === 0 ? (
                  <p className="mt-4 rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">No commission evidence has been recorded for this program.</p>
                ) : (
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full min-w-[720px] text-left text-sm">
                      <thead><tr className="border-b border-slate-100 text-xs text-slate-500"><th className="py-3 pr-3">Currency</th><th className="py-3 pr-3">Evidence</th><th className="py-3 pr-3">Event type</th><th className="py-3 pr-3 text-right">Entries</th><th className="py-3 pr-3 text-right">Commission observed</th><th className="py-3 text-right">Revenue observed</th></tr></thead>
                      <tbody>{program.commission_observations.map((item,index) => (
                        <tr key={item.currency + item.evidence_status + item.entry_type + index} className="border-b border-slate-50">
                          <td className="py-3 pr-3 font-bold">{item.currency}</td><td className="py-3 pr-3">{pretty(item.evidence_status)}</td><td className="py-3 pr-3">{pretty(item.entry_type)}</td>
                          <td className="py-3 pr-3 text-right tabular-nums">{item.entry_count}</td><td className="py-3 pr-3 text-right tabular-nums">{amount(item.commission_total,item.currency)}</td><td className="py-3 text-right tabular-nums">{amount(item.revenue_total,item.currency)}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                )}
                <p className="mt-4 text-xs leading-5 text-slate-500">{program.earnings_note} These grouped observations are not a customer-level commission statement, cleared balance, proof of payment, or withdrawal request.</p>
              </section>
            )}

            {tab === "terms" && (
              <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-black">Program terms and restrictions</h2>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {[
                    ["Commission", value(terms.commission_value) + " " + value(terms.commission_currency,"") + " · " + pretty(value(terms.commission_type,"not recorded"))],
                    ["Cookie window", value(terms.cookie_days) + " days"],
                    ["Attribution window", value(terms.attribution_window_days) + " days"],
                    ["Refund hold", value(terms.refund_hold_days) + " days"],
                    ["Minimum payout threshold", value(terms.minimum_payout_amount) + " " + value(terms.commission_currency,"")],
                    ["Payout schedule", pretty(value(terms.payout_schedule))],
                    ["Allowed regions", Array.isArray(terms.allowed_regions) ? terms.allowed_regions.join(", ") : "Not recorded"],
                    ["Restricted traffic", Array.isArray(terms.restricted_traffic_sources) && terms.restricted_traffic_sources.length ? terms.restricted_traffic_sources.join(", ") : "No restrictions recorded in this snapshot"],
                  ].map(([label, detail]) => <div key={label} className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-bold uppercase text-slate-500">{label}</p><p className="mt-2 text-sm font-semibold">{detail}</p></div>)}
                </div>
                {typeof terms.affiliate_disclosure === "string" && <p className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50 p-4 text-sm text-indigo-950"><strong>Disclosure requirement:</strong> {terms.affiliate_disclosure}</p>}
                {program.reviewer_notes && <p className="mt-4 rounded-xl border border-slate-200 p-4 text-sm text-slate-700"><strong>Merchant review note:</strong> {program.reviewer_notes}</p>}
              </section>
            )}

            {tab === "customers" && (
              <Unavailable title="Referred customers" reason="The current merchant-partner data model does not provide a publisher-scoped customer directory with consented masked identities, signup dates, last purchase and lifetime value. OmniAffiliateOS does not invent or expose customer identities from click or commission evidence." />
            )}
            {tab === "messages" && (
              <Unavailable title="Merchant-partner messages" reason="Persistent program conversations, inbox delivery and read receipts are not implemented yet. Merchant review notes are not a substitute for two-way partner messaging." />
            )}
            {tab === "payouts" && (
              <Unavailable title="Payout account and withdrawal history" reason="The current affiliate workspace does not yet provide payout-account onboarding, a publisher withdrawal request, or payout transaction history. Commission evidence and merchant payout-readiness are not proof that funds were paid." />
            )}
          </>
        )}
      </div>
    </main>
  );
}

function Unavailable({ title, reason }: { title: string; reason: string }) {
  return (
    <section className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white p-6" aria-label={title + " unavailable"}>
      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500">Not implemented</span>
      <h2 className="mt-3 text-lg font-black">{title}</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{reason}</p>
    </section>
  );
}

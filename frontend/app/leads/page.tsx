"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowLeft, CheckCircle2, CircleAlert, Download, RefreshCw, ShieldCheck, Users,
  type LucideIcon,
} from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type UTMField = "utm_source" | "utm_medium" | "utm_campaign" | "utm_content" | "utm_term";
type UTMValues = Partial<Record<UTMField, string>>;
type Attribution = {
  first_touch?: UTMValues;
  last_touch?: UTMValues;
  last_touch_at?: string | null;
};
type Lead = {
  id: string;
  email: string;
  lead_magnet: string;
  consented_at: string;
  email_consent_confirmed_at: string | null;
  consent_source: string;
  email_suppressed_at: string | null;
  email_suppression_reason: string | null;
  unsubscribed: boolean;
  purchased: boolean;
  attribution?: Attribution;
};
type ConsentEvent = {
  id: string;
  event_type: string;
  purpose: string;
  consent_text: string | null;
  policy_version: string;
  source: string;
  channel: string;
  observed_at: string | null;
  created_at: string | null;
};
type ConsentHistory = { lead_id: string; count: number; read_only: boolean; data: ConsentEvent[] };
type LeadList = { count: number; total_count: number; limit: number; offset: number; data: Lead[] };

const PAGE_LIMIT = 50;
const inputClass = "mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-900 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100";
const utmFields: Array<[UTMField, string]> = [
  ["utm_source", "Source"],
  ["utm_medium", "Medium"],
  ["utm_campaign", "Campaign"],
  ["utm_content", "Content"],
  ["utm_term", "Term"],
];

function message(error: unknown): string {
  return error instanceof Error ? error.message : "The leads request failed.";
}

function displayDate(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function utmPairs(values: UTMValues | undefined): Array<[string, string]> {
  return utmFields
    .filter(([key]) => typeof values?.[key] === "string" && Boolean(values[key]?.trim()))
    .map(([key, label]) => [label, values![key]!] as [string, string]);
}

function SummaryCard({ title, value, note, icon: Icon }: {
  title: string;
  value: string;
  note: string;
  icon: LucideIcon;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-black uppercase tracking-wider text-slate-400">{title}</p>
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-50 text-indigo-600">
          <Icon size={17} aria-hidden="true" />
        </span>
      </div>
      <p className="mt-3 text-2xl font-black tracking-tight text-slate-950">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">{note}</p>
    </article>
  );
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [utmQuery, setUtmQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [consentHistory, setConsentHistory] = useState<Record<string, ConsentEvent[]>>({});
  const [consentHistoryOpen, setConsentHistoryOpen] = useState<Record<string, boolean>>({});
  const [consentHistoryLoading, setConsentHistoryLoading] = useState<Record<string, boolean>>({});
  const [consentHistoryErrors, setConsentHistoryErrors] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await apiFetch<LeadList>("/api/leads?limit=" + PAGE_LIMIT + "&offset=" + offset + "&search=" + encodeURIComponent(appliedSearch));
      const total = Number.isFinite(result.total_count)
        ? Math.max(0, result.total_count)
        : Math.max(0, Number(result.count) || 0);
      if (offset > 0 && offset >= total) {
        const lastOffset = Math.max(0, Math.floor((total - 1) / PAGE_LIMIT) * PAGE_LIMIT);
        if (lastOffset !== offset) {
          setTotalCount(total);
          setOffset(lastOffset);
          return;
        }
      }
      setTotalCount(total);
      setLeads(Array.isArray(result.data) ? result.data : []);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setLoading(false);
      setBusy(false);
    }
  }, [offset, appliedSearch]);

  useEffect(() => { void load(); }, [load]);

  const toggleConsentHistory = async (leadId: string) => {
    const willOpen = !consentHistoryOpen[leadId];
    setConsentHistoryOpen((current) => ({ ...current, [leadId]: willOpen }));
    if (!willOpen || Object.prototype.hasOwnProperty.call(consentHistory, leadId)) return;
    setConsentHistoryLoading((current) => ({ ...current, [leadId]: true }));
    setConsentHistoryErrors((current) => ({ ...current, [leadId]: "" }));
    try {
      const result = await apiFetch<ConsentHistory>(
        "/api/leads/" + encodeURIComponent(leadId) + "/consent-events",
      );
      setConsentHistory((current) => ({ ...current, [leadId]: Array.isArray(result.data) ? result.data : [] }));
    } catch (caught) {
      setConsentHistoryErrors((current) => ({
        ...current,
        [leadId]: message(caught),
      }));
    } finally {
      setConsentHistoryLoading((current) => ({ ...current, [leadId]: false }));
    }
  };

  const filtered = useMemo(() => {
    const needle = utmQuery.trim().toLowerCase();
    if (!needle) return leads;
    return leads.filter((lead) => {
      const values = [
        ...utmPairs(lead.attribution?.first_touch).map(([, value]) => value),
        ...utmPairs(lead.attribution?.last_touch).map(([, value]) => value),
      ];
      return values.some((value) => value.toLowerCase().includes(needle));
    });
  }, [leads, utmQuery]);

  const attributedCount = leads.filter((lead) =>
    utmPairs(lead.attribution?.first_touch).length > 0
      || utmPairs(lead.attribution?.last_touch).length > 0
  ).length;
  const suppressedCount = leads.filter((lead) => lead.unsubscribed).length;

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <a href="/" className="inline-flex items-center gap-2 text-sm font-bold text-indigo-700 hover:text-indigo-900">
            <ArrowLeft size={16} aria-hidden="true" /> Growth command center
          </a>
          <div className="mt-5 flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="text-xs font-black uppercase tracking-[0.2em] text-indigo-600">S6 · First-party attribution</p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">Leads &amp; attribution</h1>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                Workspace-scoped view of consented leads, suppression status, and UTM campaign attribution.
                First touch is retained; last touch updates when a lead submits again with tagged campaign values.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <a
                href={API_BASE + "/api/leads/export.csv" + (appliedSearch ? "?search=" + encodeURIComponent(appliedSearch) : "")}
                aria-label={appliedSearch ? "Export matching workspace leads as CSV" : "Export all workspace leads as CSV"}
                title="Exports all workspace matches for global search (maximum 10,000 rows); the page-only UTM quick filter is not applied."
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700"
              >
                <Download size={16} aria-hidden="true" />
                Export CSV
              </a>
                          <button
              type="button"
              onClick={() => { setBusy(true); void load(); }}
              disabled={loading || busy}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 disabled:opacity-50"
            >
              <RefreshCw size={16} className={loading || busy ? "animate-spin" : ""} aria-hidden="true" />
              Refresh
            </button>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold">
            <span className="rounded-full bg-emerald-50 px-3 py-2 text-emerald-800">Read-only CRM view</span>
            <span className="rounded-full bg-slate-100 px-3 py-2 text-slate-600">No email is sent from this page</span>
            <span className="rounded-full bg-slate-100 px-3 py-2 text-slate-600">Attribution values are recorded, not proof of conversion or payout</span>
            <span className="rounded-full bg-slate-100 px-3 py-2 text-slate-600">CSV export: global search only, up to 10,000 leads</span>
          </div>
        </header>

        {error && (
          <section role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-900">
            <div className="flex items-start gap-3">
              <CircleAlert size={19} className="mt-0.5 shrink-0" aria-hidden="true" />
              <div>
                <p className="font-black">Could not load workspace leads</p>
                <p className="mt-1 break-words">{error}</p>
                <p className="mt-2 text-rose-800">Sign in through the growth dashboard if this is an authentication error, then return here.</p>
              </div>
            </div>
          </section>
        )}

        <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <SummaryCard title="Workspace leads" value={String(totalCount)} note={appliedSearch ? "Matches for email/resource search" : "Total records in the active workspace"} icon={Users} />
          <SummaryCard title="With UTM attribution" value={String(attributedCount)} note="On the current page" icon={Activity} />
          <SummaryCard title="Unsubscribed" value={String(suppressedCount)} note="On the current page; suppressed from future delivery" icon={ShieldCheck} />
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-xl font-black text-slate-950">Lead records</h2>
              <p className="mt-1 text-sm text-slate-500">Shows 50 workspace-scoped records per page. Search filters the current page; the total count covers the active workspace.</p>
            </div>
            <form
              className="w-full sm:max-w-sm"
              onSubmit={(event) => { event.preventDefault(); setAppliedSearch(query.trim()); setOffset(0); }}
            >
              <label htmlFor="lead-search" className="block text-sm font-bold text-slate-700">Search all leads by email, resource or UTM</label>
              <div className="mt-2 flex gap-2">
                <input
                  id="lead-search"
                  className="w-full min-w-0 rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-900 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                  type="search"
                  maxLength={120}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Email or resource name"
                />
                <button type="submit" disabled={loading} className="rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white disabled:opacity-50">Search</button>
              </div>
              {appliedSearch && <button type="button" onClick={() => { setQuery(""); setAppliedSearch(""); setOffset(0); }} className="mt-2 text-xs font-bold text-indigo-700">Clear global search</button>}
            </form>
            <div className="w-full sm:max-w-xs">
              <label htmlFor="utm-search" className="block text-sm font-bold text-slate-700">Filter UTM values on this page</label>
              <input
                id="utm-search"
                className={inputClass}
                type="search"
                value={utmQuery}
                onChange={(event) => setUtmQuery(event.target.value)}
                placeholder="Source, campaign or content"
              />
            </div>
          </div>

          {loading ? (
            <p role="status" className="mt-6 rounded-xl bg-slate-50 p-5 text-sm text-slate-600">Loading workspace leads…</p>
          ) : filtered.length === 0 ? (
            <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
              <Users size={27} className="mx-auto text-slate-400" aria-hidden="true" />
              <h3 className="mt-3 font-black text-slate-800">{leads.length === 0 ? "No leads recorded for this workspace" : "No matching leads"}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {leads.length === 0
                  ? "Publish a consent-gated landing page when ready, or capture a lead through an authorized first-party form."
                  : "Try a different email, resource name, source or campaign search."}
              </p>
              {leads.length === 0 && (
                <a href="/landing-pages" className="mt-4 inline-flex rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white">
                  Open landing pages
                </a>
              )}
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              {filtered.map((lead) => {
                const firstTouch = utmPairs(lead.attribution?.first_touch);
                const lastTouch = utmPairs(lead.attribution?.last_touch);
                return (
                  <article key={lead.id} data-testid={"lead-record-" + lead.id} className="rounded-2xl border border-slate-200 p-4 sm:p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="break-all text-base font-black text-slate-950">{lead.email}</h3>
                        <p className="mt-1 text-sm text-slate-600">Resource: {lead.lead_magnet || "Not recorded"}</p>
                        <p className="mt-1 text-xs text-slate-500">Consent recorded: {displayDate(lead.consented_at)}</p>
                        <p className="mt-1 text-xs text-slate-500">Consent source: {lead.consent_source || "Not recorded"}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          Email confirmation: {lead.email_consent_confirmed_at
                            ? "Confirmed " + displayDate(lead.email_consent_confirmed_at)
                            : "No confirmation timestamp recorded"}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <span className={"rounded-full px-3 py-1.5 text-xs font-bold " + (lead.unsubscribed ? "bg-rose-50 text-rose-800" : "bg-emerald-50 text-emerald-800")}>
                          {lead.unsubscribed ? "Unsubscribed · Suppressed" : "Consent recorded · Not unsubscribed"}
                        </span>
                        {lead.email_suppressed_at && (
                          <span
                            role="status"
                            aria-label={"Email delivery suppressed: " + (lead.email_suppression_reason || "provider suppression")}
                            title={"Provider suppression recorded " + displayDate(lead.email_suppressed_at)}
                            className="rounded-full bg-amber-50 px-3 py-1.5 text-xs font-bold text-amber-900"
                          >
                            Delivery blocked · {(lead.email_suppression_reason || "provider suppression").replaceAll("_", " ")}
                          </span>
                        )}
                        <span className={"rounded-full px-3 py-1.5 text-xs font-bold " + (lead.purchased ? "bg-indigo-50 text-indigo-800" : "bg-slate-100 text-slate-600")}>
                          {lead.purchased ? "Purchase recorded" : "No purchase recorded"}
                        </span>
                      </div>
                    </div>

                    <div className="mt-4">
                      <button
                        type="button"
                        onClick={() => void toggleConsentHistory(lead.id)}
                        disabled={Boolean(consentHistoryLoading[lead.id])}
                        aria-expanded={Boolean(consentHistoryOpen[lead.id])}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-indigo-700 disabled:opacity-50"
                      >
                        {consentHistoryLoading[lead.id]
                          ? "Loading consent history…"
                          : consentHistoryOpen[lead.id] ? "Hide consent history" : "View consent history"}
                      </button>
                      {consentHistoryOpen[lead.id] && (
                        <section aria-label={"Consent history for " + lead.email} className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                          <p className="text-xs font-semibold text-slate-500">Read-only consent event ledger. Events are shown in recorded order; this page cannot edit or delete them.</p>
                          {consentHistoryErrors[lead.id] && (
                            <p role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                              Could not load consent history: {consentHistoryErrors[lead.id]}
                            </p>
                          )}
                          {consentHistoryLoading[lead.id] && <p role="status" className="mt-3 text-sm text-slate-600">Loading consent events…</p>}
                          {!consentHistoryLoading[lead.id] && !consentHistoryErrors[lead.id] && (consentHistory[lead.id] || []).length === 0 && (
                            <p className="mt-3 text-sm text-slate-600">No consent events are recorded for this lead.</p>
                          )}
                          <ol className="mt-3 space-y-3">
                            {(consentHistory[lead.id] || []).map((event) => (
                              <li key={event.id} className="rounded-lg border border-slate-200 bg-white p-3">
                                <div className="flex flex-wrap items-start justify-between gap-2">
                                  <p className="text-sm font-black text-slate-900">{event.event_type.replaceAll("_", " ")}</p>
                                  <p className="text-xs text-slate-500">{displayDate(event.observed_at || event.created_at)}</p>
                                </div>
                                <dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-xs">
                                  <dt className="text-slate-500">Purpose</dt><dd className="break-words text-slate-800">{event.purpose || "Not recorded"}</dd>
                                  <dt className="text-slate-500">Source / channel</dt><dd className="break-words text-slate-800">{event.source || "Not recorded"} / {event.channel || "Not recorded"}</dd>
                                  <dt className="text-slate-500">Policy version</dt><dd className="break-words text-slate-800">{event.policy_version || "Not recorded"}</dd>
                                </dl>
                                <p className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-700">
                                  {event.consent_text || "No consent wording is attached to this event (for example, a withdrawal event)."}
                                </p>
                              </li>
                            ))}
                          </ol>
                        </section>
                      )}
                    </div>

                    <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
                      <section className="rounded-xl bg-slate-50 p-4">
                        <h4 className="text-sm font-black text-slate-800">First touch</h4>
                        {firstTouch.length ? (
                          <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
                            {firstTouch.map(([label, value]) => (
                              <div key={label} className="contents">
                                <dt className="text-slate-500">{label}</dt>
                                <dd className="break-words font-semibold text-slate-800">{value}</dd>
                              </div>
                            ))}
                          </dl>
                        ) : <p className="mt-2 text-sm text-slate-500">No UTM source recorded.</p>}
                      </section>
                      <section className="rounded-xl bg-slate-50 p-4">
                        <h4 className="text-sm font-black text-slate-800">Last tagged submission</h4>
                        {lastTouch.length ? (
                          <>
                            <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
                              {lastTouch.map(([label, value]) => (
                                <div key={label} className="contents">
                                  <dt className="text-slate-500">{label}</dt>
                                  <dd className="break-words font-semibold text-slate-800">{value}</dd>
                                </div>
                              ))}
                            </dl>
                            <p className="mt-3 text-xs text-slate-500">Tagged lead capture recorded: {displayDate(lead.attribution?.last_touch_at)}</p>
                          </>
                        ) : <p className="mt-2 text-sm text-slate-500">No UTM source recorded.</p>}
                      </section>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
          {!loading && totalCount > PAGE_LIMIT && (
            <nav aria-label="Lead pagination" className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
              <p className="text-sm text-slate-600">
                Showing {totalCount === 0 ? 0 : offset + 1}–{Math.min(offset + leads.length, totalCount)} of {totalCount} leads · page {Math.floor(offset / PAGE_LIMIT) + 1} of {Math.ceil(totalCount / PAGE_LIMIT)}
              </p>
              <div className="flex gap-2">
                <button type="button" onClick={() => setOffset(Math.max(0, offset - PAGE_LIMIT))} disabled={offset === 0 || loading} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 disabled:opacity-40">Previous</button>
                <button type="button" onClick={() => setOffset(offset + PAGE_LIMIT)} disabled={offset + PAGE_LIMIT >= totalCount || loading} className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 disabled:opacity-40">Next</button>
              </div>
            </nav>
          )}
          {!loading && filtered.length > 0 && (
            <p className="mt-4 text-xs text-slate-500">Showing {filtered.length} matching records on this page; {totalCount} total workspace records. This page is read-only; changing consent or suppression remains in the existing subscription controls.</p>
          )}
        </section>

        <footer className="flex items-start gap-2 rounded-2xl border border-indigo-100 bg-indigo-50 p-4 text-xs leading-5 text-indigo-950">
          <CheckCircle2 size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <p>Attribution is limited to allowlisted UTM fields. UTM tags are acquisition context, not a verified sale, commission or payout. Unsubscribed leads remain suppressed; this page does not change their status or send messages.</p>
        </footer>
      </div>
    </main>
  );
}

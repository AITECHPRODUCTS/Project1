"use client";

import { useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";

type DecayPageInput = {
  url: string;
  title?: string;
  publish_date?: string;
  last_updated?: string;
  target_keyword?: string;
  previous_clicks?: number;
  current_clicks?: number;
  previous_impressions?: number;
  current_impressions?: number;
  previous_avg_position?: number;
  current_avg_position?: number;
  contains_affiliate_links?: boolean | null;
  revenue_impact?: "high" | "medium" | "low" | "unknown";
  outdated_elements?: string[];
  competitor_refresh_observed?: boolean | null;
  competitor_note?: string;
  serp_displacement_observed?: boolean | null;
  refresh_effort_hours?: number | null;
};

type DecayingPage = {
  url: string;
  title: string;
  target_keyword: string;
  priority: string;
  priority_score: number;
  decay_signals: string[];
  preliminary_signals: string[];
  refresh_actions: string[];
  estimated_effort_hours: number;
  effort_source: string;
  revenue_impact: string;
  metrics: {
    clicks_decline_pct: number | null;
    impressions_decline_pct: number | null;
    position_worsening: number | null;
  };
  evidence_confidence: string;
  data_provenance: string;
  requires_review: boolean;
};

type DecayReport = {
  asset_id: string;
  site: string;
  timeframe: string;
  timeframe_label: string;
  pages_analyzed: number;
  pages_decaying: number;
  total_refresh_effort_hours: number;
  decaying_pages: DecayingPage[];
  healthy_pages: string[];
  pages_needing_more_data: Array<{
    url: string;
    title: string;
    missing_data: string[];
    preliminary_signals: string[];
    data_provenance: string;
  }>;
  priority_queues: Record<string, string[]>;
  search_console_connected: boolean;
  competitor_data_checked: boolean;
  external_search_performed: boolean;
  metrics_source: string;
  traffic_recovery_estimate_supported: boolean;
  requires_review: boolean;
  publishing_started: boolean;
  note: string;
};

const samplePages = [
  {
    url: "https://example.com/best-tools",
    title: "Best tools",
    target_keyword: "best tools",
    previous_clicks: 1000,
    current_clicks: 650,
    previous_impressions: 12000,
    current_impressions: 9000,
    previous_avg_position: 4,
    current_avg_position: 13,
    revenue_impact: "medium",
    contains_affiliate_links: true,
    outdated_elements: ["Verify current pricing before editing"],
    competitor_refresh_observed: null,
    serp_displacement_observed: null
  }
];

const field = "mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900";
const label = "block text-sm font-semibold text-slate-700";

function message(error: unknown) {
  return error instanceof Error ? error.message : "Request failed";
}

function formatMetric(value: number | null, suffix = "") {
  return value === null ? "Not supplied" : `${value}${suffix}`;
}

export default function ContentDecayPage() {
  const [siteUrl, setSiteUrl] = useState("https://example.com");
  const [timeframe, setTimeframe] = useState<"30d" | "90d" | "6m" | "1y">("90d");
  const [pagesJson, setPagesJson] = useState(JSON.stringify(samplePages, null, 2));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<DecayReport | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setReport(null);
    try {
      const parsed: unknown = JSON.parse(pagesJson);
      if (!Array.isArray(parsed) || parsed.length < 1 || parsed.length > 30) {
        throw new Error("Provide a JSON array containing 1–30 content pages.");
      }
      const result = await apiFetch<DecayReport>("/api/research/content-decay", {
        method: "POST",
        body: JSON.stringify({ site_url: siteUrl.trim(), timeframe, pages: parsed as DecayPageInput[] })
      });
      setReport(result);
    } catch (cause) {
      setError(message(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-7 text-slate-900 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <a href="/research-brief" className="text-sm font-semibold text-indigo-600 hover:underline">← Source-backed research</a>
            <h1 className="mt-2 text-3xl font-black tracking-tight">Content decay review queue</h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-600">Rank supplied performance evidence, identify missing data and save a workspace-scoped refresh review. No crawling or publishing is performed.</p>
          </div>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600">Saved draft · Human review required</span>
        </header>

        <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
          <strong>Evidence boundary:</strong> the service uses only the metrics and observations you supply. It does not connect to Search Console, verify competitor activity, crawl your pages or predict traffic recovery. Replace the example values with matched reporting periods before relying on a recommendation.
        </div>

        {error && <div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(320px,.8fr)_minmax(0,1.2fr)]">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-xl font-bold">Review inputs</h2>
            <form onSubmit={submit} className="mt-4 space-y-4">
              <label className={label}>Public site URL
                <input className={field} type="url" value={siteUrl} onChange={event => setSiteUrl(event.target.value)} required maxLength={2048} />
              </label>
              <label className={label}>Comparison window
                <select className={field} value={timeframe} onChange={event => setTimeframe(event.target.value as typeof timeframe)}>
                  <option value="30d">30 days</option>
                  <option value="90d">90 days</option>
                  <option value="6m">6 months</option>
                  <option value="1y">1 year</option>
                </select>
              </label>
              <label className={label}>Content page evidence (JSON array)
                <textarea className={field + " min-h-80 font-mono text-xs leading-5"} value={pagesJson} onChange={event => setPagesJson(event.target.value)} required spellCheck={false} />
                <span className="mt-1 block text-xs font-normal text-slate-500">1–30 pages. Each page URL must share the site's public origin. Supply previous/current metric pairs together; publication and update dates must be valid and not in the future.</span>
              </label>
              <button type="submit" disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">
                {busy ? "Analyzing and saving draft…" : "Build and save review queue"}
              </button>
            </form>
          </section>

          <section className="space-y-5">
            {!report && <div className="flex min-h-72 flex-col justify-center rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
              <h2 className="text-xl font-bold">Your review queue will appear here</h2>
              <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600">The report separates evidence-backed decay signals from healthy pages and pages that need more data. Every saved report remains a draft until an editor reviews it.</p>
            </div>}

            {report && <>
              <div role="status" className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
                <strong>Review draft saved.</strong> Asset ID: <span className="font-mono">{report.asset_id}</span>. Publishing was not started.
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["Pages analyzed", report.pages_analyzed],
                  ["Decay candidates", report.pages_decaying],
                  ["Healthy pages", report.healthy_pages.length],
                  ["Estimated refresh hours", report.total_refresh_effort_hours]
                ].map(([title, value]) => <div key={title} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
                  <p className="mt-2 text-2xl font-black">{value}</p>
                </div>)}
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <h2 className="text-xl font-bold">Priority review queue</h2>
                <p className="mt-1 text-sm text-slate-600">Sorted by the service's transparent heuristic score; this is not a prediction of ranking or revenue recovery.</p>
                {report.decaying_pages.length === 0 && <p className="mt-4 text-sm text-slate-600">No pages have enough supplied signals to qualify as decay candidates.</p>}
                <div className="mt-4 space-y-4">
                  {report.decaying_pages.map(page => <article key={page.url} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="font-bold">{page.title}</h3>
                        <a href={page.url} target="_blank" rel="noreferrer" className="mt-1 block break-all text-xs text-indigo-700 underline">{page.url}</a>
                      </div>
                      <span className="rounded-full border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-bold">{page.priority} · {page.priority_score}</span>
                    </div>
                    <div className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
                      <p>Clicks: <strong>{formatMetric(page.metrics.clicks_decline_pct, "% decline")}</strong></p>
                      <p>Impressions: <strong>{formatMetric(page.metrics.impressions_decline_pct, "% decline")}</strong></p>
                      <p>Position change: <strong>{formatMetric(page.metrics.position_worsening, " places worse")}</strong></p>
                    </div>
                    <p className="mt-3 text-xs text-slate-500">Evidence: {page.evidence_confidence} confidence · {page.data_provenance} · Review required</p>
                    <h4 className="mt-3 text-sm font-bold">Observed signals</h4>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{page.decay_signals.map(signal => <li key={signal}>{signal.replaceAll("_", " ")}</li>)}</ul>
                    <h4 className="mt-3 text-sm font-bold">Suggested editorial actions</h4>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{page.refresh_actions.map(action => <li key={action}>{action}</li>)}</ul>
                  </article>)}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <h2 className="text-xl font-bold">Pages needing more data</h2>
                {report.pages_needing_more_data.length === 0 ? <p className="mt-2 text-sm text-slate-600">No additional data requests for this report.</p> : <div className="mt-3 space-y-3">
                  {report.pages_needing_more_data.map(page => <article key={page.url} className="rounded-xl border border-slate-200 p-3">
                    <h3 className="break-all text-sm font-bold">{page.title || page.url}</h3>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">{page.missing_data.map(item => <li key={item}>{item}</li>)}</ul>
                    {page.preliminary_signals.length > 0 && <p className="mt-2 text-xs font-semibold text-amber-800">Preliminary only: {page.preliminary_signals.join(", ").replaceAll("_", " ")}</p>}
                  </article>)}
                </div>}
              </div>
              <p className="rounded-xl bg-slate-100 p-4 text-xs leading-5 text-slate-600">{report.note} Search Console connected: {String(report.search_console_connected)}. Competitor data checked: {String(report.competitor_data_checked)}. External search performed: {String(report.external_search_performed)}. Recovery estimate supported: {String(report.traffic_recovery_estimate_supported)}.</p>
            </>}
          </section>
        </div>
      </div>
    </main>
  );
}

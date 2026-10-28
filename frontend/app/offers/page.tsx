"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ChevronLeft, ChevronRight, ExternalLink, RefreshCw, Search } from "lucide-react";
import { apiFetch } from "@/lib/api";

type Offer = {
  id: string;
  network: string;
  external_id: string;
  name: string;
  url: string | null;
  category: string | null;
  description: string;
  reward_type: string | null;
  reward_value: string | null;
  cookie_days: number | null;
  traffic_score: number | null;
  gravity_score: number | null;
  normalized_gravity: number | null;
  epc: number | null;
  conversion_rate: number | null;
  recurring_commission: boolean | null;
  source_stars: number | null;
  verified: boolean;
  verification_basis: string;
  source_url: string | null;
  updated_at: string | null;
};

type CatalogResponse = {
  count: number;
  total_count: number;
  offset: number;
  limit: number;
  data: Offer[];
};

type Filters = {
  q: string;
  network: string;
  category: string;
  reward_type: string;
  recurring_commission: string;
  min_cookie_days: string;
  provider_claimed_verified: string;
  sort_by: string;
  sort_order: "asc" | "desc";
};

const PAGE_SIZE = 20;
const DEFAULT_FILTERS: Filters = {
  q: "",
  network: "",
  category: "",
  reward_type: "",
  recurring_commission: "",
  min_cookie_days: "",
  provider_claimed_verified: "",
  sort_by: "epc",
  sort_order: "desc",
};
const fieldClass = "mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100";
const labelClass = "block text-sm font-bold text-slate-700";

function safeHttpsUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" && parsed.hostname ? parsed.href : null;
  } catch {
    return null;
  }
}

function numberLabel(value: number | null, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: 0 })
    : "Unknown";
}

function conversionRateLabel(value: number | null): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unknown";
  return (value * 100).toLocaleString(undefined, { maximumFractionDigits: 2 }) + "%";
}

function updatedLabel(value: string | null): string {
  if (!value) return "Catalog update time unavailable";
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? "Catalog updated " + parsed.toLocaleString() : "Catalog update time unavailable";
}

function providerVerificationLabel(offer: Offer): string {
  return offer.verification_basis === "provider_claimed_unattested"
    ? "Provider claimed — not independently attested"
    : "Not verified / unknown";
}

export default function OfferCatalogPage() {
  const [draftFilters, setDraftFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [activeFilters, setActiveFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadCatalog = useCallback(async (filters: Filters, nextOffset: number) => {
    const params = new URLSearchParams();
    const q = filters.q.trim();
    const network = filters.network.trim();
    const category = filters.category.trim();
    const rewardType = filters.reward_type.trim();
    if (q) params.set("q", q);
    if (network) params.set("network", network);
    if (category) params.set("category", category);
    if (rewardType) params.set("reward_type", rewardType);
    if (filters.recurring_commission !== "") params.set("recurring_commission", filters.recurring_commission);
    if (filters.min_cookie_days.trim() !== "") params.set("min_cookie_days", filters.min_cookie_days.trim());
    if (filters.provider_claimed_verified !== "") params.set("provider_claimed_verified", filters.provider_claimed_verified);
    params.set("sort_by", filters.sort_by);
    params.set("sort_order", filters.sort_order);
    params.set("offset", String(nextOffset));
    params.set("limit", String(PAGE_SIZE));

    setLoading(true);
    setError("");
    setCatalog(null);
    setActiveFilters(filters);
    try {
      const response = await apiFetch<CatalogResponse>("/api/offers?" + params.toString());
      setCatalog(response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The persisted offer catalog could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCatalog(DEFAULT_FILTERS, 0);
  }, [loadCatalog]);

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void loadCatalog(draftFilters, 0);
  };
  const previousPage = () => {
    if (!catalog || loading || catalog.offset === 0) return;
    void loadCatalog(activeFilters, Math.max(0, catalog.offset - catalog.limit));
  };
  const nextPage = () => {
    if (!catalog || loading || catalog.offset + catalog.limit >= catalog.total_count) return;
    void loadCatalog(activeFilters, catalog.offset + catalog.limit);
  };
  const hasPrevious = !!catalog && catalog.offset > 0;
  const hasNext = !!catalog && catalog.offset + catalog.limit < catalog.total_count;
  const firstRow = catalog && catalog.count > 0 ? catalog.offset + 1 : 0;
  const lastRow = catalog ? catalog.offset + catalog.count : 0;

  return (
    <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10" aria-busy={loading}>
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <a href="/" className="text-sm font-bold text-indigo-700">← Growth command center</a>
            <p className="mt-6 text-xs font-black uppercase tracking-[.2em] text-indigo-600">S1 · Affiliate research</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Affiliate offer catalog</h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Search the persisted offer directory by name, network, category, reward terms and available metrics.
              Unknown values stay unknown; this catalog does not independently verify provider claims or account approval.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a href="/marketplace" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold">Publisher marketplace</a>
            <a href="/merchant/offers" className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold">Merchant offers</a>
            <button type="button" onClick={() => void loadCatalog(activeFilters, catalog?.offset ?? 0)} disabled={loading} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">
              <RefreshCw size={15} className={loading ? "animate-spin" : ""}/> Refresh
            </button>
          </div>
        </header>

        <section className="mt-7 rounded-3xl border border-white bg-white p-5 shadow-sm sm:p-7" aria-label="Offer catalog filters">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-indigo-50 text-indigo-600"><Search size={18}/></span>
            <div><h2 className="text-xl font-black">Search and qualify offers</h2><p className="mt-1 text-sm text-slate-500">Filters apply to stored catalog entries and do not trigger provider requests.</p></div>
          </div>
          <form onSubmit={submitSearch} className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="sm:col-span-2"><label className={labelClass} htmlFor="offer-search-q">Search terms</label><input id="offer-search-q" maxLength={100} value={draftFilters.q} onChange={e => setDraftFilters(current => ({...current, q:e.target.value}))} className={fieldClass} placeholder="Name, description or category"/></div>
            <div><label className={labelClass} htmlFor="offer-search-network">Affiliate network</label><input id="offer-search-network" maxLength={100} value={draftFilters.network} onChange={e => setDraftFilters(current => ({...current, network:e.target.value}))} className={fieldClass} placeholder="e.g. clickbank"/></div>
            <div><label className={labelClass} htmlFor="offer-search-category">Category</label><input id="offer-search-category" maxLength={200} value={draftFilters.category} onChange={e => setDraftFilters(current => ({...current, category:e.target.value}))} className={fieldClass} placeholder="e.g. creator tools"/></div>
            <div><label className={labelClass} htmlFor="offer-search-reward">Reward type</label><input id="offer-search-reward" maxLength={100} value={draftFilters.reward_type} onChange={e => setDraftFilters(current => ({...current, reward_type:e.target.value}))} className={fieldClass} placeholder="e.g. recurring_percentage"/></div>
            <div><label className={labelClass} htmlFor="offer-search-recurring">Recurring commission</label><select id="offer-search-recurring" value={draftFilters.recurring_commission} onChange={e => setDraftFilters(current => ({...current, recurring_commission:e.target.value}))} className={fieldClass}><option value="">All</option><option value="true">Yes</option><option value="false">No</option></select></div>
            <div><label className={labelClass} htmlFor="offer-search-cookie">Minimum cookie duration (days)</label><input id="offer-search-cookie" type="number" min={0} max={2147483647} step={1} value={draftFilters.min_cookie_days} onChange={e => setDraftFilters(current => ({...current, min_cookie_days:e.target.value}))} className={fieldClass} placeholder="Any duration"/></div>
            <div><label className={labelClass} htmlFor="offer-search-verification">Provider claim filter</label><select id="offer-search-verification" value={draftFilters.provider_claimed_verified} onChange={e => setDraftFilters(current => ({...current, provider_claimed_verified:e.target.value}))} className={fieldClass}><option value="">All records</option><option value="true">Provider claims verified</option><option value="false">Not verified or unknown</option></select></div>
            <div><label className={labelClass} htmlFor="offer-search-sort">Sort by</label><select id="offer-search-sort" value={draftFilters.sort_by} onChange={e => setDraftFilters(current => ({...current, sort_by:e.target.value}))} className={fieldClass}>
              <option value="epc">EPC (currency not recorded)</option><option value="conversion_rate">Conversion rate</option><option value="traffic_score">Traffic score</option><option value="gravity_score">Gravity score</option><option value="cookie_days">Cookie duration</option><option value="source_stars">Source star rating</option><option value="updated_at">Catalog update time</option><option value="name">Name</option><option value="network">Network</option>
            </select></div>
            <div><label className={labelClass} htmlFor="offer-search-direction">Sort direction</label><select id="offer-search-direction" value={draftFilters.sort_order} onChange={e => setDraftFilters(current => ({...current, sort_order:e.target.value as Filters["sort_order"]}))} className={fieldClass}><option value="desc">Descending · nulls last</option><option value="asc">Ascending · nulls last</option></select></div>
            <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-2"><button type="submit" disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white disabled:opacity-50"><Search size={16}/> Search catalog</button><button type="button" disabled={loading} onClick={() => {setDraftFilters(DEFAULT_FILTERS);void loadCatalog(DEFAULT_FILTERS, 0);}} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold disabled:opacity-50">Clear filters</button></div>
          </form>
        </section>

        {error && <div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">Offer catalog request failed: {error}</div>}
        {loading && <p role="status" className="mt-6 rounded-xl border border-indigo-100 bg-indigo-50 p-4 text-sm font-bold text-indigo-800">Loading persisted offer data…</p>}
        {!loading && catalog && (
          <section data-testid="offer-results" className="mt-7 rounded-3xl border border-white bg-white p-5 shadow-sm sm:p-7" aria-label="Offer catalog results">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><h2 className="text-xl font-black">Catalog results</h2><p className="mt-1 text-sm text-slate-500">{catalog.total_count === 0 ? "No matching offers" : "Showing " + firstRow + "-" + lastRow + " of " + catalog.total_count + " results"}</p></div>
              <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-700">{catalog.count} result(s) on this page</span>
            </div>
            {catalog.count === 0 ? <p className="mt-5 rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">No offers matched these filters. Widen the search or clear the filters; empty fields are not treated as zero.</p> : (
              <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-2">
                {catalog.data.map(offer => {
                  const offerUrl = safeHttpsUrl(offer.url);
                  const sourceUrl = safeHttpsUrl(offer.source_url);
                  return <article key={offer.id} data-testid="offer-card" className="rounded-2xl border border-slate-200 p-4 sm:p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="text-lg font-black">{offer.name}</h3><p className="mt-1 break-all text-xs text-slate-500">{offer.network} · ID {offer.external_id}</p><p className="mt-1 text-xs text-slate-500">{offer.category || "Category unknown"}</p></div><span className={"rounded-full px-3 py-1.5 text-xs font-bold " + (offer.verification_basis === "provider_claimed_unattested" ? "bg-amber-50 text-amber-900" : "bg-slate-100 text-slate-700")}>{providerVerificationLabel(offer)}</span></div>
                    <p className="mt-4 text-sm leading-6 text-slate-600">{offer.description || "Description not supplied."}</p>
                    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                      <div data-testid={"offer-epc-" + offer.id} className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">EPC (currency not recorded)</p><p className="mt-1 text-sm font-black">{numberLabel(offer.epc)}</p></div>
                      <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Conversion rate</p><p className="mt-1 text-sm font-black">{conversionRateLabel(offer.conversion_rate)}</p></div>
                      <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Traffic score</p><p className="mt-1 text-sm font-black">{numberLabel(offer.traffic_score)}</p></div>
                      <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Cookie duration</p><p className="mt-1 text-sm font-black">{offer.cookie_days === null ? "Unknown" : offer.cookie_days + " days"}</p></div>
                      <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Recurring commission</p><p className="mt-1 text-sm font-black">{offer.recurring_commission === null ? "Unknown" : offer.recurring_commission ? "Yes (source field)" : "No (source field)"}</p></div>
                      <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Source rating</p><p className="mt-1 text-sm font-black">{numberLabel(offer.source_stars)}</p></div>
                    </div>
                    <div className="mt-4 rounded-xl border border-amber-100 bg-amber-50/70 p-3"><p className="text-xs font-bold text-amber-900">Verification boundary</p><p className="mt-1 text-sm leading-5 text-amber-900">{providerVerificationLabel(offer)}. The stored flag is not independent proof of source authenticity, approval, availability or permission to promote.</p></div>
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-slate-500">{updatedLabel(offer.updated_at)}</p><div className="flex flex-wrap gap-3">{offerUrl && <a href={offerUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-bold text-indigo-700 underline">Offer page <ExternalLink size={13}/></a>}{sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-bold text-indigo-700 underline">Source reference <ExternalLink size={13}/></a>}</div></div>
                    <div className="mt-3 border-t border-slate-100 pt-3"><p className="text-xs text-slate-500">Reward terms: {offer.reward_value ?? "Unknown"} · {offer.reward_type ?? "type unknown"} · Gravity {numberLabel(offer.gravity_score)} · Normalized gravity {numberLabel(offer.normalized_gravity)}</p></div>
                  </article>;
                })}
              </div>
            )}
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-5"><p className="text-xs leading-5 text-slate-500">Sorting places unknown values last in either direction. This is catalog data, not a live provider health check.</p><div className="flex gap-2"><button type="button" onClick={previousPage} disabled={!hasPrevious || loading} className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold disabled:opacity-40"><ChevronLeft size={16}/> Previous page</button><button type="button" onClick={nextPage} disabled={!hasNext || loading} className="inline-flex items-center gap-1 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-40">Next page <ChevronRight size={16}/></button></div></div>
          </section>
        )}
      </div>
    </main>
  );
}

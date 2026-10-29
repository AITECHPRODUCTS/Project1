"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { RefreshCw, Save } from "lucide-react";
import { apiFetch } from "@/lib/api";

type CheckState = "pass" | "fail" | "unknown" | "pending";
type ReviewStatus = "pending_review" | "qualified" | "rejected" | "needs_evidence" | "deferred";
type CheckKey = "account_eligibility" | "geography_fit" | "traffic_source_fit" | "terms_review" | "landing_page_review" | "disclosure_review";
type Qualification = {
  status: string; account_eligibility: CheckState; geography_fit: CheckState; traffic_source_fit: CheckState;
  terms_review: CheckState; landing_page_review: CheckState; disclosure_review: CheckState; evidence_urls: string[];
  notes: string; policy_version: string; reviewed_by: string | null; reviewed_at: string | null;
  evidence_basis: string; affiliate_network_approval_implied: false;
};
type QueueItem = {
  offer: { id: string; network: string; external_id: string; name: string; category: string | null; description: string;
    url: string | null; cookie_days: number | null; reward_type: string | null; reward_value: string | null;
    epc: number | null; conversion_rate: number | null; verification_basis: string };
  qualification: Qualification;
};
type QueueResponse = { count: number; total_count: number; offset: number; limit: number; status_filter: string; data: QueueItem[]; note: string };
const checks: { key: CheckKey; label: string }[] = [
  { key: "account_eligibility", label: "Publisher account eligibility" }, { key: "geography_fit", label: "Target geography allowed" },
  { key: "traffic_source_fit", label: "Traffic sources allowed" }, { key: "terms_review", label: "Program terms reviewed" },
  { key: "landing_page_review", label: "Destination / landing page reviewed" }, { key: "disclosure_review", label: "Affiliate disclosure ready" },
];
const checkOptions = [{ value: "unknown", label: "Unknown" }, { value: "pending", label: "Pending evidence" },
  { value: "pass", label: "Pass (operator attested)" }, { value: "fail", label: "Fail" }];
const statusOptions: { value: ReviewStatus; label: string }[] = [
  { value: "pending_review", label: "Pending review" }, { value: "needs_evidence", label: "Needs more evidence" },
  { value: "qualified", label: "Qualified for internal planning" }, { value: "deferred", label: "Deferred" }, { value: "rejected", label: "Rejected" },
];
const inputClass = "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100";
const labelClass = "block text-sm font-semibold text-slate-700";

function QualificationCard({ item, onSaved }: { item: QueueItem; onSaved: (message: string) => Promise<void> }) {
  const [status, setStatus] = useState<ReviewStatus>(statusOptions.some(s => s.value === item.qualification.status) ? item.qualification.status as ReviewStatus : "pending_review");
  const [values, setValues] = useState<Record<CheckKey, CheckState>>({
    account_eligibility: item.qualification.account_eligibility, geography_fit: item.qualification.geography_fit,
    traffic_source_fit: item.qualification.traffic_source_fit, terms_review: item.qualification.terms_review,
    landing_page_review: item.qualification.landing_page_review, disclosure_review: item.qualification.disclosure_review,
  });
  const [evidence, setEvidence] = useState(item.qualification.evidence_urls.join("\n"));
  const [notes, setNotes] = useState(item.qualification.notes);
  const [policyVersion, setPolicyVersion] = useState(item.qualification.policy_version || "manual-review-v1");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setError("");
    const urls = evidence.split("\n").map(value => value.trim()).filter(Boolean);
    if (status === "qualified" && (checks.some(check => values[check.key] !== "pass") || urls.length === 0)) {
      setError("To qualify for internal planning, all six checks must be pass and at least one evidence URL is required."); return;
    }
    if (["rejected", "deferred", "needs_evidence"].includes(status) && !notes.trim()) {
      setError("Add reviewer notes for rejected, deferred, or needs-evidence decisions."); return;
    }
    setBusy(true);
    try {
      await apiFetch("/api/offers/" + encodeURIComponent(item.offer.id) + "/qualification", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status, ...values, evidence_urls: urls, notes, policy_version: policyVersion }) });
      await onSaved("Qualification review saved for " + item.offer.name + ". This is an operator decision, not network approval.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Qualification review could not be saved."); }
    finally { setBusy(false); }
  };
  return <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="qualification-card">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-lg font-black">{item.offer.name}</h2><p className="mt-1 text-xs text-slate-500">{item.offer.network} · {item.offer.external_id} · {item.offer.category || "Category unknown"}</p><p className="mt-2 text-sm text-slate-600">{item.offer.description || "No description supplied."}</p></div>
      <span className="rounded-full bg-amber-50 px-3 py-1.5 text-xs font-bold text-amber-900">{item.qualification.status === "not_reviewed" ? "Not reviewed" : item.qualification.status.replaceAll("_", " ")}</span>
    </div>
    <p className="mt-3 text-xs text-slate-500">{item.offer.verification_basis === "provider_claimed_unattested" ? "Provider claimed — not independently attested." : "Provider verification unknown."} Current metrics and operator evidence remain unverified.</p>
    {item.qualification.reviewed_at && <p className="mt-2 text-xs text-slate-500">Last reviewed {new Date(item.qualification.reviewed_at).toLocaleString()} by {item.qualification.reviewed_by || "unknown reviewer"} · policy {item.qualification.policy_version}</p>}
    <form onSubmit={submit} className="mt-5 space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{checks.map(check => <div key={check.key}>
        <label className={labelClass} htmlFor={item.offer.id + "-" + check.key}>{check.label}</label>
        <select id={item.offer.id + "-" + check.key} aria-label={check.label} className={inputClass} value={values[check.key]} onChange={event => setValues(current => ({ ...current, [check.key]: event.target.value as CheckState }))}>
          {checkOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select></div>)}</div>
      <div className="grid gap-4 md:grid-cols-2">
        <div><label className={labelClass} htmlFor={item.offer.id + "-review-status"}>Decision</label><select id={item.offer.id + "-review-status"} className={inputClass} value={status} onChange={event => setStatus(event.target.value as ReviewStatus)}>{statusOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
        <div><label className={labelClass} htmlFor={item.offer.id + "-policy-version"}>Policy/checklist version</label><input id={item.offer.id + "-policy-version"} className={inputClass} maxLength={80} value={policyVersion} onChange={event => setPolicyVersion(event.target.value)} required/></div>
      </div>
      <div><label className={labelClass} htmlFor={item.offer.id + "-evidence"}>Evidence URLs (one HTTPS URL per line)</label><textarea id={item.offer.id + "-evidence"} className={inputClass + " min-h-24"} maxLength={12000} value={evidence} onChange={event => setEvidence(event.target.value)} placeholder="https://merchant.example/affiliate-terms"/></div>
      <div><label className={labelClass} htmlFor={item.offer.id + "-review-notes"}>Reviewer notes</label><textarea id={item.offer.id + "-review-notes"} className={inputClass + " min-h-20"} maxLength={2000} value={notes} onChange={event => setNotes(event.target.value)} placeholder="Record what was checked, unknowns, and follow-up required."/></div>
      {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      <button type="submit" disabled={busy} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50"><Save size={15}/>{busy ? "Saving review…" : "Save qualification review"}</button>
    </form>
  </article>;
}

export default function OfferQualificationPage() {
  const [filter, setFilter] = useState("needs_review");
  const [queue, setQueue] = useState<QueueResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const load = useCallback(async (nextFilter: string) => {
    setLoading(true); setError("");
    try { setQueue(await apiFetch<QueueResponse>("/api/offers/qualification-queue?status=" + encodeURIComponent(nextFilter) + "&limit=50")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Qualification queue could not be loaded."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(filter); }, [filter, load]);
  const onSaved = async (text: string) => { setMessage(text); await load(filter); };
  return <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10"><div className="mx-auto max-w-7xl">
    <a href="/offers" className="text-sm font-bold text-indigo-700">← Affiliate offer catalog</a>
    <p className="mt-6 text-xs font-black uppercase tracking-[.2em] text-indigo-600">S1 · Evidence and eligibility</p>
    <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Offer qualification review</h1>
    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Record workspace-specific checks for account eligibility, geography, traffic restrictions, terms, landing-page safety and disclosure. This checklist is an operator attestation; it does not verify provider claims or imply affiliate-network approval.</p>
    <div className="mt-5 flex flex-wrap items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><strong>Qualification boundary:</strong><span>“Qualified” means eligible for internal planning only. Live network approval and provider-side facts remain unverified.</span></div>
    <div className="mt-6 flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200 bg-white p-4">
      <div className="min-w-56 flex-1"><label className={labelClass} htmlFor="qualification-filter">Queue filter</label><select id="qualification-filter" className={inputClass} value={filter} onChange={event => setFilter(event.target.value)}>
        <option value="needs_review">Needs review (default)</option><option value="not_reviewed">Not reviewed</option><option value="pending_review">Pending review</option><option value="needs_evidence">Needs evidence</option><option value="qualified">Qualified for internal planning</option><option value="deferred">Deferred</option><option value="rejected">Rejected</option><option value="all">All catalog offers</option>
      </select></div>
      <button type="button" onClick={() => void load(filter)} disabled={loading} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold disabled:opacity-50"><RefreshCw size={15} className={loading ? "animate-spin" : ""}/> Refresh queue</button>
      <p className="text-sm text-slate-500">{queue ? queue.total_count + " offers match this filter" : "Loading saved review queue…"}</p>
    </div>
    {message && <p role="status" data-testid="qualification-message" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">{message}</p>}
    {error && <p role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
    {loading && <p role="status" className="mt-5 text-sm text-slate-500">Loading qualification records…</p>}
    {!loading && queue && queue.data.length === 0 && <p className="mt-5 rounded-2xl border border-dashed border-slate-300 p-6 text-sm text-slate-600">No offers match this filter. Try “All catalog offers” to review the current shared catalog.</p>}
    {!loading && queue && queue.data.length > 0 && <div className="mt-5 space-y-4">{queue.data.map(item => <QualificationCard key={item.offer.id} item={item} onSaved={onSaved}/>)}</div>}
    <p className="mt-6 text-xs leading-5 text-slate-500">{queue?.note || "Stored decisions are operator-supplied and workspace-specific. They are not independent provider evidence."}</p>
  </div></main>;
}

"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";

type QueueAsset = { id: string; title: string; asset_type: string; status: string; created_at: string | null };
type QueueAssetList = { count: number; data: QueueAsset[] };
type QueueItem = {
  id: string; source_asset_id: string; source_asset_type: string; title: string; channel: string;
  content_sha256: string; target_jurisdictions: string[]; scheduled_at: string | null;
  status: "pending_review" | "approved_waiting_for_dispatch" | "cancelled" | string;
  created_by: string; reviewed_by: string | null; reviewer_note: string | null;
  external_post_id: string | null; attempt_count: number; external_submission_status: string;
  dispatch_confirmation_required: boolean; execution_boundary: string; replayed: boolean; created_at: string | null;
};
type QueueList = { count: number; data: QueueItem[] };

const channels = [
  { value: "meta", label: "Meta" }, { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" }, { value: "tiktok", label: "TikTok" },
  { value: "youtube", label: "YouTube" }, { value: "youtube_shorts", label: "YouTube Shorts" },
  { value: "pinterest", label: "Pinterest" }, { value: "reddit", label: "Reddit" },
  { value: "quora", label: "Quora" }, { value: "x", label: "X" },
  { value: "linkedin", label: "LinkedIn" }, { value: "telegram", label: "Telegram" },
  { value: "whatsapp_business", label: "WhatsApp Business" },
  { value: "wordpress", label: "WordPress" }, { value: "ghost", label: "Ghost" },
  { value: "email", label: "Email" },
] as const;
const inputClass = "mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-900 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100";
const channelName = (value: string) => channels.find((item) => item.value === value)?.label || value;
const statusName = (value: string) => value === "pending_review" ? "Pending review"
  : value === "approved_waiting_for_dispatch" ? "Approved — not sent"
  : value === "cancelled" ? "Cancelled" : value.replaceAll("_", " ");
const errorMessage = (error: unknown) => error instanceof Error ? error.message : "The distribution queue request failed.";
const displayDate = (value: string | null) => value ? new Date(value).toLocaleString() : "Not scheduled";

export default function DistributionQueuePage() {
  const [assets, setAssets] = useState<QueueAsset[]>([]);
  const [items, setItems] = useState<QueueItem[]>([]);
  const [assetId, setAssetId] = useState("");
  const [channel, setChannel] = useState("pinterest");
  const [scheduledAt, setScheduledAt] = useState("");
  const [jurisdictions, setJurisdictions] = useState("");
  const [reviewerNote, setReviewerNote] = useState("");
  const [reviewConfirmations, setReviewConfirmations] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [assetResult, queueResult] = await Promise.all([
        apiFetch<QueueAssetList>("/api/distribution/queue/assets?limit=100"),
        apiFetch<QueueList>("/api/distribution/queue?limit=100"),
      ]);
      setAssets(assetResult.data || []);
      setItems(queueResult.data || []);
      setAssetId((current) => current && assetResult.data.some((item) => item.id === current)
        ? current : (assetResult.data[0]?.id || ""));
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const createQueueItem = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!assetId) { setError("Create or select a saved content asset before queueing it."); return; }
    setBusy("create"); setError(""); setNotice("");
    try {
      await apiFetch<QueueItem>("/api/distribution/queue", {
        method: "POST",
        headers: { "Idempotency-Key": "distribution-" + crypto.randomUUID() },
        body: JSON.stringify({
          content_asset_id: assetId, channel,
          scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
        }),
      });
      setNotice("Saved in the review queue. The content has not been sent to an external provider.");
      setScheduledAt("");
      await load();
    } catch (caught) { setError(errorMessage(caught)); }
    finally { setBusy(""); }
  };

  const approve = async (item: QueueItem) => {
    const targets = [...new Set(jurisdictions.split(",").map((value) => value.trim().toUpperCase()).filter(Boolean))];
    if (!reviewConfirmations[item.id]) { setError("Confirm that you reviewed the content before approving it."); return; }
    if (!targets.length) { setError("Enter the jurisdictions that you reviewed for this content."); return; }
    setBusy("approve:" + item.id); setError(""); setNotice("");
    try {
      await apiFetch<QueueItem>("/api/distribution/queue/" + item.id + "/approve", {
        method: "POST",
        body: JSON.stringify({ confirm_content_review: true, target_jurisdictions: targets, reviewer_note: reviewerNote.trim() }),
      });
      setNotice("Review recorded. The item remains unsent; provider readiness and a separate dispatch confirmation are still required.");
      setReviewConfirmations((current) => ({ ...current, [item.id]: false }));
      await load();
    } catch (caught) { setError(errorMessage(caught)); }
    finally { setBusy(""); }
  };

  const cancel = async (item: QueueItem) => {
    setBusy("cancel:" + item.id); setError(""); setNotice("");
    try {
      await apiFetch<QueueItem>("/api/distribution/queue/" + item.id + "/cancel", {
        method: "POST", body: JSON.stringify({ confirm_cancel: true }),
      });
      setNotice("Queue item cancelled. No external action was attempted.");
      await load();
    } catch (caught) { setError(errorMessage(caught)); }
    finally { setBusy(""); }
  };

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-7">
        <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-indigo-600">S5 · Distribution</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">Distribution queue</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Select a saved content asset, queue an immutable snapshot, and require a workspace owner/admin review before an item is approved for a future dispatch flow.</p>
          <div className="mt-4 flex flex-wrap gap-3 text-xs font-semibold text-slate-500">
            <span className="rounded-full bg-amber-50 px-3 py-2 text-amber-800">Review required</span>
            <span className="rounded-full bg-slate-100 px-3 py-2">Idempotent queue creation</span>
            <span className="rounded-full bg-slate-100 px-3 py-2">No external send from this page</span>
          </div>
        </header>
        {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
        {notice && <div role="status" className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-800">{notice}</div>}
        <section className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
          <form onSubmit={createQueueItem} className="space-y-5 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div><h2 className="text-xl font-black text-slate-950">Queue a saved draft</h2><p className="mt-1 text-sm text-slate-500">The queued body and source references are snapshotted so later edits do not silently change this item.</p></div>
            <div>
              <label htmlFor="queue-asset" className="block text-sm font-bold text-slate-700">Saved content asset</label>
              <select id="queue-asset" aria-label="Saved content asset" required value={assetId} onChange={(event) => setAssetId(event.target.value)} className={inputClass}>
                <option value="" disabled>Select a saved draft</option>
                {assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.title} · {asset.asset_type} · {asset.status}</option>)}
              </select>
              {assets.length === 0 && <p className="mt-2 text-sm text-slate-500">No saved content assets are available in this workspace yet. Create a content draft first, then refresh.</p>}
            </div>
            <div>
              <label htmlFor="queue-channel" className="block text-sm font-bold text-slate-700">Target channel</label>
              <select id="queue-channel" aria-label="Target channel" value={channel} onChange={(event) => setChannel(event.target.value)} className={inputClass}>
                {channels.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
              <p className="mt-2 text-xs leading-5 text-slate-500">Choosing a channel records intent only; it does not mean the account or write scope is connected.</p>
            </div>
            <div>
              <label htmlFor="queue-schedule" className="block text-sm font-bold text-slate-700">Desired publish time (optional)</label>
              <input id="queue-schedule" type="datetime-local" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} className={inputClass} />
              <p className="mt-2 text-xs text-slate-500">A future time is stored in UTC. No scheduler dispatches this item in this slice.</p>
            </div>
            <button type="submit" disabled={busy !== "" || assets.length === 0} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white disabled:cursor-not-allowed disabled:opacity-50">
              {busy === "create" ? "Adding…" : "Add to review queue"}
            </button>
          </form>
          <section className="space-y-4">
            <div className="flex items-center justify-between gap-3"><div><h2 className="text-xl font-black text-slate-950">Queue items</h2><p className="mt-1 text-sm text-slate-500">{items.length} persisted item(s) · no provider sends claimed</p></div><button type="button" onClick={() => void load()} disabled={busy !== ""} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold disabled:opacity-50">Refresh</button></div>
            {items.length === 0 && <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">Your queue is empty. Queue a saved content asset to start a review record.</div>}
            {items.map((item) => (
              <article key={item.id} data-testid={"distribution-queue-" + item.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-base font-black text-slate-950">{item.title}</h3><p className="mt-1 text-xs text-slate-500">{item.source_asset_type} · {channelName(item.channel)} · {displayDate(item.scheduled_at)}</p></div><span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-700">{statusName(item.status)}</span></div>
                <p className="mt-3 break-all text-xs text-slate-500">Snapshot SHA-256: {item.content_sha256}</p>
                <p className="mt-2 text-xs text-slate-500">External submission: {item.external_submission_status === "not_attempted" ? "Not sent" : "Provider ID recorded"}.</p>
                {item.status === "pending_review" && <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
                  <label className="flex items-start gap-2 text-sm text-slate-700"><input type="checkbox" checked={Boolean(reviewConfirmations[item.id])} onChange={(event) => setReviewConfirmations((current) => ({ ...current, [item.id]: event.target.checked }))} className="mt-1" /><span>I reviewed this content for the selected jurisdictions.</span></label>
                  <label className="block text-sm font-bold text-slate-700">Target jurisdictions for review<input aria-label="Target jurisdictions for review" value={jurisdictions} onChange={(event) => setJurisdictions(event.target.value)} placeholder="US, GB, IN" className={inputClass} /></label>
                  <label className="block text-sm font-bold text-slate-700">Review note (optional)<textarea aria-label="Distribution review note" value={reviewerNote} onChange={(event) => setReviewerNote(event.target.value)} rows={2} maxLength={4000} className={inputClass} /></label>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => void approve(item)} disabled={busy !== "" || !reviewConfirmations[item.id] || !jurisdictions.trim()} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">{busy === "approve:" + item.id ? "Saving review…" : "Approve for dispatch review"}</button>
                    <button type="button" onClick={() => void cancel(item)} disabled={busy !== ""} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-700 disabled:opacity-50">Cancel item</button>
                  </div>
                </div>}
                {item.status === "approved_waiting_for_dispatch" && <div className="mt-4 space-y-3 border-t border-slate-100 pt-4"><p className="text-sm text-slate-700">Approved by {item.reviewed_by || "workspace reviewer"}. This item remains <strong>not sent</strong>; a separate dispatch confirmation and verified provider capability are required.</p><button type="button" onClick={() => void cancel(item)} disabled={busy !== ""} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-700 disabled:opacity-50">Cancel item</button></div>}
              </article>
            ))}
          </section>
        </section>
        <footer className="rounded-2xl border border-slate-200 bg-white p-4 text-xs leading-5 text-slate-600">Queue and review records are persisted and audited. This page does not call external publishing APIs, does not start ad spend, and does not claim that a channel is connected. Dispatch, provider receipts, retries and scheduled-worker execution remain separate engineering/authorization gates.</footer>
      </div>
    </main>
  );
}

"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";

type LandingPage = {
  id: string;
  title: string;
  status: "draft" | "published" | string;
  public_url: string | null;
  preview_url: string;
  requires_review: boolean;
  publishing_started: boolean;
  privacy_url: string | null;
  lead_magnet: string | null;
  audience: string | null;
  created_at: string | null;
};

type LandingPageList = { count: number; data: LandingPage[] };

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const inputClass = "mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-900 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100";
const labelClass = "block text-sm font-bold text-slate-700";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The landing-page request failed.";
}

export default function LandingPagesPage() {
  const [items, setItems] = useState<LandingPage[]>([]);
  const [headline, setHeadline] = useState("A clear creator guide");
  const [subheadline, setSubheadline] = useState("A practical, evidence-first resource for independent creators.");
  const [benefits, setBenefits] = useState("Choose products using consistent criteria\nVerify claims against official sources\nKeep limitations visible before deciding");
  const [privacyUrl, setPrivacyUrl] = useState("https://example.com/privacy");
  const [leadMagnet, setLeadMagnet] = useState("Creator starter guide");
  const [audience, setAudience] = useState("Independent creators");
  const [disclosure, setDisclosure] = useState("Disclosure: I may earn a commission from qualifying purchases through affiliate links.");
  const [publishConfirmations, setPublishConfirmations] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const result = await apiFetch<LandingPageList>("/api/landing/pages");
      setItems(result.data || []);
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const createDraft = async (event: FormEvent) => {
    event.preventDefault();
    setBusy("create");
    setError("");
    setNotice("");
    const benefitBullets = benefits.split("\n").map((item) => item.trim()).filter(Boolean);
    if (benefitBullets.length < 1 || benefitBullets.length > 8) {
      setError("Enter between one and eight benefit bullets.");
      setBusy("");
      return;
    }
    try {
      await apiFetch<LandingPage>("/api/landing/pages", {
        method: "POST",
        body: JSON.stringify({
          headline: headline.trim(),
          subheadline: subheadline.trim(),
          benefit_bullets: benefitBullets,
          form_action: "/api/public/leads/capture",
          privacy_url: privacyUrl.trim(),
          affiliate_disclosure: disclosure.trim(),
          lead_magnet: leadMagnet.trim(),
          audience: audience.trim(),
        }),
      });
      setNotice("Landing-page draft saved. It stays private until an owner or admin explicitly publishes it.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy("");
    }
  };

  const publish = async (item: LandingPage) => {
    setBusy("publish:" + item.id);
    setError("");
    setNotice("");
    try {
      await apiFetch<LandingPage>("/api/landing/pages/" + item.id + "/publish", {
        method: "POST",
        body: JSON.stringify({ confirm_public_publish: true }),
      });
      setNotice("Landing page published. Its public form requires explicit email consent.");
      await load();
      setPublishConfirmations((current) => ({ ...current, [item.id]: false }));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy("");
    }
  };

  const unpublish = async (item: LandingPage) => {
    setBusy("unpublish:" + item.id);
    setError("");
    setNotice("");
    try {
      await apiFetch<LandingPage>("/api/landing/pages/" + item.id + "/unpublish", { method: "POST" });
      setNotice("Landing page unpublished. Its public URL is no longer served.");
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy("");
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-7">
        <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <p className="text-xs font-black uppercase tracking-[0.2em] text-indigo-600">S4 · Offer, landing and consent</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">Landing pages and funnels</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Create a private draft, preview it, and require an explicit workspace-owner/admin decision before it becomes public. Lead capture stays bound to the consent-gated first-party endpoint.</p>
          <div className="mt-4 flex flex-wrap gap-3 text-xs font-semibold text-slate-500">
            <span className="rounded-full bg-amber-50 px-3 py-2 text-amber-800">Draft by default</span>
            <span className="rounded-full bg-slate-100 px-3 py-2">No affiliate-network submission</span>
            <span className="rounded-full bg-slate-100 px-3 py-2">No ad spend</span>
          </div>
        </header>

        {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
        {notice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}

        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <h2 className="text-xl font-black text-slate-950">Create a landing-page draft</h2>
          <p className="mt-1 text-sm text-slate-500">Use one clear claim per bullet. Do not include statistics or product claims you cannot verify.</p>
          <form onSubmit={createDraft} className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="lg:col-span-2">
              <label className={labelClass} htmlFor="landing-headline">Headline</label>
              <input id="landing-headline" value={headline} onChange={(event) => setHeadline(event.target.value)} minLength={3} maxLength={250} required className={inputClass} />
            </div>
            <div className="lg:col-span-2">
              <label className={labelClass} htmlFor="landing-subheadline">Subheadline</label>
              <textarea id="landing-subheadline" value={subheadline} onChange={(event) => setSubheadline(event.target.value)} minLength={3} maxLength={800} required rows={2} className={inputClass} />
            </div>
            <div className="lg:col-span-2">
              <label className={labelClass} htmlFor="landing-benefits">Benefit bullets (one per line)</label>
              <textarea id="landing-benefits" value={benefits} onChange={(event) => setBenefits(event.target.value)} maxLength={4000} required rows={4} className={inputClass} />
            </div>
            <div>
              <label className={labelClass} htmlFor="landing-privacy">Privacy policy URL</label>
              <input id="landing-privacy" type="url" value={privacyUrl} onChange={(event) => setPrivacyUrl(event.target.value)} maxLength={2048} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass} htmlFor="landing-magnet">Lead magnet / resource</label>
              <input id="landing-magnet" value={leadMagnet} onChange={(event) => setLeadMagnet(event.target.value)} minLength={2} maxLength={300} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass} htmlFor="landing-audience">Audience</label>
              <input id="landing-audience" value={audience} onChange={(event) => setAudience(event.target.value)} minLength={2} maxLength={500} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass} htmlFor="landing-disclosure">Affiliate disclosure</label>
              <textarea id="landing-disclosure" value={disclosure} onChange={(event) => setDisclosure(event.target.value)} maxLength={1200} rows={2} className={inputClass} />
            </div>
            <div className="lg:col-span-2 flex flex-wrap items-center justify-between gap-3">
              <p className="max-w-2xl text-xs leading-5 text-slate-500">Saving does not publish. Publishing exposes this page on a public URL and is restricted to workspace owners/admins.</p>
              <button type="submit" disabled={!!busy} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-black text-white disabled:opacity-50">{busy === "create" ? "Saving draft…" : "Save landing page draft"}</button>
            </div>
          </form>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="text-xl font-black text-slate-950">Workspace landing pages</h2><p className="mt-1 text-sm text-slate-500">{items.length} saved page{items.length === 1 ? "" : "s"}</p></div>
            <button type="button" onClick={() => void load()} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-700">Refresh</button>
          </div>
          {items.length === 0 ? <p className="mt-5 rounded-xl border border-dashed border-slate-200 p-5 text-sm text-slate-500">No landing pages yet. Save a draft above to begin.</p> :
            <div className="mt-5 grid gap-4">
              {items.map((item) => (
                <article key={item.id} data-testid={"landing-page-" + item.id} className="rounded-2xl border border-slate-200 p-4 sm:p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div><h3 className="font-black text-slate-950">{item.title}</h3><p className="mt-1 text-xs text-slate-500">ID: {item.id}</p></div>
                    <span className={"rounded-full px-3 py-1.5 text-xs font-bold " + (item.status === "published" ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800")}>{item.status}</span>
                  </div>
                  <p className="mt-3 text-sm text-slate-600">Resource: {item.lead_magnet || "Not set"} · Audience: {item.audience || "Not set"}</p>
                  <div className="mt-4 flex flex-wrap gap-3">
                    <a className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-700" href={apiBase + item.preview_url} target="_blank" rel="noreferrer">Preview page</a>
                    {item.status === "published" && item.public_url && <a className="rounded-xl bg-indigo-50 px-4 py-2.5 text-sm font-bold text-indigo-700" href={item.public_url} target="_blank" rel="noreferrer">Open public page</a>}
                    {item.status === "draft" && (
                      <div className="flex flex-col gap-3 rounded-xl bg-amber-50 p-3">
                        <label className="flex items-start gap-2 text-sm text-amber-950" htmlFor={"landing-publish-confirm-" + item.id}>
                          <input id={"landing-publish-confirm-" + item.id} type="checkbox" checked={publishConfirmations[item.id] === true} onChange={(event) => setPublishConfirmations((current) => ({ ...current, [item.id]: event.target.checked }))} />
                          <span>I reviewed this page and approve making it public.</span>
                        </label>
                        <button type="button" onClick={() => void publish(item)} disabled={!publishConfirmations[item.id] || !!busy} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-black text-white disabled:opacity-40">Publish page</button>
                      </div>
                    )}
                    {item.status === "published" && <button type="button" onClick={() => void unpublish(item)} disabled={!!busy} className="rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-bold text-rose-700 disabled:opacity-40">Unpublish page</button>}
                  </div>
                </article>
              ))}
            </div>}
        </section>
      </div>
    </main>
  );
}

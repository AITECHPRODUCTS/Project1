"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type MerchantOffer = {
  id: string;
  name: string;
  status: string;
  affiliate_network_approval_status: string;
  affiliate_network_approved: boolean;
  terms_verified: boolean;
  seller_authorization_verified: boolean;
  activation_allowed: boolean;
  marketplace_listed: boolean;
  created_at: string | null;
};

type OfferResponse = {
  count: number;
  data: MerchantOffer[];
};

type PendingApplicationResponse = {
  count: number;
  total_count: number;
  limit: number;
  offset: number;
  status_filter: string;
  data: unknown[];
};

type MerchantApplicationPreview={id:string;offer_name:string;status:string;applicant_email:string;created_at:string|null};
type DashboardSnapshot = {
  offerCount: number;
  offers: MerchantOffer[];
  pendingApplications: number;
  approvedApplications: number;
  rejectedApplications: number;
  recentPendingApplications: MerchantApplicationPreview[];
};

function readableStatus(value: string | null | undefined): string {
  if (!value) return "unknown";
  return value.replaceAll("_", " ");
}

const statCard = "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm";
const actionLink = "inline-flex items-center justify-center rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white transition hover:bg-indigo-700";
const secondaryLink = "inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 transition hover:bg-slate-50";

export default function MerchantDashboardPage() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const identity = await apiFetch<{ user?: { account_type?: string; is_admin?: boolean } }>("/api/auth/me");
      if (identity.user?.account_type !== "merchant_product_owner") {
        throw new Error("This dashboard is only available to Merchant / Product Owner accounts.");
      }
      const [offerResponse,pendingResponse,approvedResponse,rejectedResponse] = await Promise.all([
        apiFetch<OfferResponse>("/api/merchant/offers?limit=300"),
        apiFetch<PendingApplicationResponse & {data:MerchantApplicationPreview[]}>("/api/merchant/applications?limit=5&offset=0&status=pending_review"),
        apiFetch<PendingApplicationResponse>("/api/merchant/applications?limit=1&offset=0&status=approved"),
        apiFetch<PendingApplicationResponse>("/api/merchant/applications?limit=1&offset=0&status=rejected"),
      ]);
      const offers = Array.isArray(offerResponse.data) ? offerResponse.data : [];
      setSnapshot({
        offerCount: Number.isFinite(offerResponse.count) ? offerResponse.count : offers.length,
        offers,
        pendingApplications: Number.isFinite(pendingResponse.total_count) ? pendingResponse.total_count : 0,
        approvedApplications: Number.isFinite(approvedResponse.total_count) ? approvedResponse.total_count : 0,
        rejectedApplications: Number.isFinite(rejectedResponse.total_count) ? rejectedResponse.total_count : 0,
        recentPendingApplications: Array.isArray(pendingResponse.data) ? pendingResponse.data : [],
      });
    } catch (cause) {
      setSnapshot(null);
      setError(cause instanceof Error
        ? cause.message
        : "Could not load merchant data. Sign in to an authorized merchant workspace as an owner or admin.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const drafts = snapshot?.offers.filter((offer) => offer.status === "draft").length ?? 0;
  const submitted = snapshot?.offers.filter((offer) => offer.status === "submitted_for_review").length ?? 0;
  const internallyApproved = snapshot?.offers.filter((offer) => offer.status === "approved").length ?? 0;
  const networkMarkedApproved = snapshot?.offers.filter((offer) => offer.affiliate_network_approved === true).length ?? 0;
  const termsVerified = snapshot?.offers.filter((offer) => offer.terms_verified === true).length ?? 0;
  const sellerEvidenceVerified = snapshot?.offers.filter((offer) => offer.seller_authorization_verified === true).length ?? 0;
  const activationReady = snapshot?.offers.filter((offer) => offer.activation_allowed === true).length ?? 0;
  const marketplaceListed = snapshot?.offers.filter((offer) => offer.marketplace_listed === true).length ?? 0;
  const evidenceGaps = snapshot?.offers.filter((offer) => offer.terms_verified !== true || offer.seller_authorization_verified !== true).length ?? 0;
  const recentOffers = snapshot?.offers.slice(0, 5) ?? [];

  return (
    <main className="min-h-screen bg-[var(--canvas)] px-4 py-6 text-slate-800 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <a href="/merchant" className="text-sm font-bold text-indigo-700">Merchant workspace</a>
            <p className="mt-6 text-xs font-black uppercase tracking-[.2em] text-indigo-600">Merchant · Product publisher</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Merchant workspace</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
              Manage your product and offer records, review affiliate applications, and keep internal decisions separate from external affiliate-network approval.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <nav aria-label="Merchant dashboard navigation" className="flex flex-wrap gap-2">
              <a className={secondaryLink} href="/merchant" aria-current="page">Dashboard</a>
              <a className={secondaryLink} href="/merchant/offers">Manage offers</a>
              <a className={actionLink} href="/merchant/applications">Review applications</a>
            </nav>
            <button type="button" onClick={() => void load()} disabled={loading} className={secondaryLink + " disabled:opacity-50"}>{loading ? "Refreshing…" : "Refresh workspace"}</button>
          </div>
        </header>

        {loading && (
          <p className="mt-8 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600" role="status">
            Loading merchant workspace data…
          </p>
        )}

        {!loading && error && (
          <section className="mt-8 rounded-2xl border border-rose-200 bg-rose-50 p-5" aria-labelledby="merchant-load-error">
            <h2 id="merchant-load-error" className="font-bold text-rose-900">Merchant data could not be loaded</h2>
            <p className="mt-2 text-sm text-rose-800" role="alert">{error}</p>
            <button className="mt-4 rounded-xl bg-rose-700 px-4 py-2.5 text-sm font-bold text-white" onClick={() => void load()}>
              Retry
            </button>
          </section>
        )}

        {!loading && snapshot && (
          <>
            <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Merchant workspace summary">
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Offer records loaded</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-offers">{snapshot.offerCount}</p>
                <p className="mt-1 text-xs text-slate-500">Latest records in this workspace; up to 300 are listed.</p>
              </article>
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Draft offers</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-drafts">{drafts}</p>
                <p className="mt-1 text-xs text-slate-500">Drafts among the loaded offer records.</p>
              </article>
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Submitted for review</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-review">{submitted}</p>
                <p className="mt-1 text-xs text-slate-500">Awaiting an internal merchant decision.</p>
              </article>
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Affiliate applications pending</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-applications">{snapshot.pendingApplications}</p>
                <p className="mt-1 text-xs text-slate-500">Total pending review for this merchant workspace.</p>
              </article>
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Approved internally</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-internal-approved">{internallyApproved}</p>
                <p className="mt-1 text-xs text-slate-500">Merchant workspace approval only; it does not imply affiliate-network approval.</p>
              </article>
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Marked network-approved</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-network-approved">{networkMarkedApproved}</p>
                <p className="mt-1 text-xs text-slate-500">Records explicitly marked approved by a network.</p>
              </article>
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Terms evidence verified</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-terms-verified">{termsVerified}</p>
                <p className="mt-1 text-xs text-slate-500">Among the latest 300 offers loaded.</p>
              </article>
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Seller authorization verified</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-seller-verified">{sellerEvidenceVerified}</p>
                <p className="mt-1 text-xs text-slate-500">Separate evidence check; not a network approval.</p>
              </article>
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Activation-ready offers</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-activation-ready">{activationReady}</p>
                <p className="mt-1 text-xs text-slate-500">Internal activation gate currently allows these offers.</p>
              </article>
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Marketplace listings</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-marketplace-listed">{marketplaceListed}</p>
                <p className="mt-1 text-xs text-slate-500">Listed in the OmniAffiliateOS internal marketplace.</p>
              </article>
              <article className={statCard}>
                <p className="text-sm font-semibold text-slate-500">Offers with evidence gaps</p>
                <p className="mt-2 text-3xl font-black tabular-nums" data-testid="merchant-stat-evidence-gaps">{evidenceGaps}</p>
                <p className="mt-1 text-xs text-slate-500">Terms or seller authorization still need explicit verification.</p>
              </article>
            </section>

            <section className="mt-8 grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,.8fr)]">
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-black uppercase tracking-[.18em] text-indigo-600">Product catalogue</p>
                    <h2 className="mt-2 text-xl font-black">Recent merchant offers</h2>
                    <p className="mt-1 text-sm text-slate-500">The latest offer records belonging to the active merchant workspace.</p>
                  </div>
                  <a className="text-sm font-bold text-indigo-700" href="/merchant/offers">Open offer manager →</a>
                </div>

                {recentOffers.length === 0 ? (
                  <div className="mt-6 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
                    <h3 className="font-bold text-slate-800">No merchant offers yet</h3>
                    <p className="mt-2 text-sm text-slate-500">Create a product offer and provide its terms and evidence to begin the merchant review process.</p>
                    <a className={actionLink + " mt-4"} href="/merchant/offers">Create an offer</a>
                  </div>
                ) : (
                  <ul className="mt-5 divide-y divide-slate-100">
                    {recentOffers.map((offer) => (
                      <li key={offer.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                        <div className="min-w-0">
                          <h3 className="truncate font-bold text-slate-800">{offer.name}</h3>
                          <p className="mt-1 text-xs text-slate-500">Internal merchant status: {readableStatus(offer.status)}</p>
                          <p className="mt-1 text-xs text-slate-500">Affiliate-network status: {readableStatus(offer.affiliate_network_approval_status)}</p>
                          <p className="mt-1 text-xs text-slate-500">Terms: {offer.terms_verified ? "verified" : "not verified"} · Seller authorization: {offer.seller_authorization_verified ? "verified" : "not verified"}</p>
                          <p className="mt-1 text-xs text-slate-500">Activation: {offer.activation_allowed ? "allowed" : "blocked"} · Internal marketplace: {offer.marketplace_listed ? "listed" : "not listed"}</p>
                        </div>
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold capitalize text-slate-700">
                          {readableStatus(offer.status)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <aside className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
                <p className="text-xs font-black uppercase tracking-[.18em] text-indigo-600">Partner operations</p>
                <h2 className="mt-2 text-xl font-black">Affiliate applications</h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  Review publishers applying to promote offers owned by this workspace. Your decision is an internal merchant decision; it does not submit an application to, or grant approval from, an external affiliate network.
                </p>
                <div className="mt-5 rounded-xl bg-indigo-50 p-4">
                  <p className="text-sm font-semibold text-indigo-800">Waiting for review</p>
                  <p className="mt-1 text-3xl font-black tabular-nums text-indigo-950" data-testid="merchant-stat-pending-applications">{snapshot.pendingApplications}</p>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <div className="rounded-xl border border-slate-100 p-3"><p className="text-xs text-slate-500">Approved internally</p><p className="mt-1 text-2xl font-black tabular-nums" data-testid="merchant-stat-applications-approved">{snapshot.approvedApplications}</p></div>
                  <div className="rounded-xl border border-slate-100 p-3"><p className="text-xs text-slate-500">Rejected internally</p><p className="mt-1 text-2xl font-black tabular-nums" data-testid="merchant-stat-applications-rejected">{snapshot.rejectedApplications}</p></div>
                </div>
                <div className="mt-4">
                  <h3 className="text-sm font-black">Latest pending applications</h3>
                  {snapshot.recentPendingApplications.length===0&&<p className="mt-2 text-xs text-slate-500">No publisher applications are waiting for review.</p>}
                  {snapshot.recentPendingApplications.map(application=><div key={application.id} className="mt-2 flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 py-2">
                    <div className="min-w-0"><p className="truncate text-sm font-semibold">{application.offer_name}</p><p className="text-xs text-slate-500">{application.applicant_email}</p></div>
                    <span className="text-xs font-bold text-amber-700">Pending review</span>
                  </div>)}
                </div>
                <a className={actionLink + " mt-5 w-full"} href="/merchant/applications">Open application queue</a>
              </aside>
            </section>

            <p className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
              Internal offer review and external affiliate-network approval are different states. This dashboard does not infer network approval, publisher earnings, or commission payments from merchant records.
            </p>
          </>
        )}
      </div>
    </main>
  );
}

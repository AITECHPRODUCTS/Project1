# Master requirement traceability
| Requirement area | Implementation path | Current status | Remaining acceptance evidence |
|---|---|---|---|
| S1 research / offer intelligence | `backend/services/s1_research.py`, `backend/tools/affiliate_api.py`, `backend/services/offer_intelligence.py`, `backend/services/traffic_analyzer.py`, `POST /api/research/traffic-analyzer` | partial | Supplied traffic-metric scoring/comparison exists; authorized analytics provider contracts, data freshness, regional estimates and advertiser validation remain pending |
| S2 creative / evidence brief | `backend/services/s2_s3_content.py`, `backend/services/llm.py` | partial | Claim-by-claim evidence and generated claim evaluation |
| S3 SEO / blogs | `backend/services/s2_s3_content.py`; `backend/services/content_decay_detector.py`; `backend/services/content_moat_calculator.py`; POST /api/research/content-decay and POST /api/research/content-moat | partial | operator-supplied decay triage and content-investment planning exist; Search Console integration, validated competitor discovery, technical SEO crawl and publish UAT remain pending |
| S4 offers / landing / lead | `backend/services/s4_s5_landing.py`, `backend/main.py`, `backend/services/email_delivery.py` | partial | Accessibility, deployed landing and consent/unsubscribe tests |
| S5 distribution / nurture | `backend/services/s4_s5_landing.py`, `backend/services/cms_publisher.py`, `backend/services/email_delivery.py` | partial | Real OAuth scopes, provider response verification, policy checks |
| S6 attribution / experiment | `backend/services/analytics_utils.py`, `backend/services/tracking_service.py`, `backend/models.py` | partial | Per-network HMAC secret isolation, append-only Numeric(18,6) conversion ledger, legacy evidence labeling, workspace-scoped read-only finance UI and PostgreSQL concurrent reversal/ledger immutability tests added; provider reconciliation, provider-specific signature contracts, partial-reversal policy, browser UAT and privacy |
| S7 operations / cost control | `backend/services/resource_budget.py`, `backend/services/ad_manager.py`, `backend/core/middleware.py` | partial | Distributed budget locking, measured provider invoices, admin console |
| Multi-program manager | `backend/services/multi_program_manager.py`, `MultiProgramManagerRequest`, `POST /api/automation/multi-program-manager`, `frontend/app/page.tsx`, `tests/test_multi_program_manager.py` | partial | Review-only EPC/revenue-share dashboard, risk signals, recommendations and exact-hours plan from operator-supplied data | Provider/API integrations, payout reconciliation, attribution quality and browser UAT |
| S8 performance memory | `backend/services/s6_s8_analytics.py`, `ai_memory/rag_chain.py` | partial | Ground-truth sample sufficiency, promotion/rollback and held-out evaluation |
| API persistence | `backend/database.py`, `backend/models.py` | partial | Alembic migrations; PostgreSQL upgrade/rollback/backups |
| UI / responsive control center | `frontend/app/page.tsx`, `frontend/components/FlywheelVisualizer.tsx` | present, unverified | GitHub frontend typecheck/build and browser a11y/UAT |
| Provider registry / outbound endpoint safety | `backend/services/integration_registry.py`, `backend/adapters/factory.py`, `backend/services/url_safety.py`, `tests/test_adapter_factory.py` | SSRF-safe URL validation and bounded generic-adapter reads implemented; provider authorization remains unverified | Official provider contract/scope tests, credential rotation/revocation, live sandbox evidence |
| Platform Super Admin / Operations | `backend/main.py` (`require_platform_admin`, `/api/admin/overview`, `/api/admin/tenants`, `/api/admin/workflows`, `/api/admin/audit`), `frontend/app/page.tsx` (Operations console), `tests/test_platform_admin.py` | partial: explicit global-role gate and read-only cross-tenant summaries implemented | tenant suspension/reactivation, member administration, queue/dead-letter control, incident/alert UI, feature flags/kill switches, deployment evidence, authenticated HTTP/browser UAT |
| AI ad planning / targeting | `backend/services/ad_planner.py`, `backend/models.py` (`AdCampaignPlanRecord`), migration `0003_ad_campaign_plans.py`, `POST /api/ads/plan`, `GET /api/ads/plans`, `GET /api/ads/plans/{plan_id}`, `frontend/app/page.tsx` (Ad studio), `tests/test_ad_planner.py`, `tests/test_ad_plan_persistence.py`, `tests/test_tenant_isolation.py` | tenant-scoped persisted draft plans, listing/detail APIs and dashboard control implemented; model enrichment optional | hosted CI for exact commit, PostgreSQL migration/tenant UAT, browser UAT, authorized ad-provider contracts, measured experiment results and account/placement verification |
| Ad performance ingestion / optimization evidence | `backend/models.py` (`AdPerformanceObservation`), migration `0004_ad_performance_observations.py`, `POST /api/ads/observations`, `GET /api/ads/observations`, `GET /api/ads/performance`, `backend/services/ad_performance.py`, `frontend/app/page.tsx` (reported results form), `tests/test_ad_performance.py` | persistent reported KPI intake and aggregation implemented; unverified inputs are isolated from optimization eligibility; automatic campaign changes remain disabled | signed/official provider ingestion that can attest metrics, verified event reconciliation, sample-size policy, real stop-loss UAT and authorized provider writes |
| Paid media stop-loss | `backend/services/ad_manager.py`, `POST /api/ads/evaluate` | recommendation-only | durable experiments, real provider metrics, approval-gated provider mutation contract |
| Skill runtime parity | `docs/skill-parity-matrix.csv` | major gap | Complete every matrix row with service/API/UI/contracts/tests |

| Commission evidence / financial ledger | `backend/services/commission_reconciliation.py`, `backend/services/commission_mail_importer.py`, `GET /api/finance/reconciliation`, `GET /api/finance/ledger` | partial: workspace-scoped candidate matching and currency-separated totals implemented; no payout is auto-confirmed | live provider statement contracts, workspace isolation against PostgreSQL, human review UI, payout evidence verification and production UAT |

| Tenant-scoped conversion idempotency | `backend/models.py` (`Conversion`), migration `0005_workspace_scoped_conversion_identity`, `tests/test_tenant_isolation.py` | implementation added; hosted migration and cross-workspace regression checks pending | PostgreSQL upgrade/rollback with existing data, provider idempotency contract tests and production tenant-isolation UAT |

| Human commission-evidence review | `CommissionEvidenceReviewRequest`, `PATCH /api/finance/mail-commissions/{evidence_id}/review`, `frontend/app/page.tsx`, `tests/test_finance_evidence_review.py` | implementation added with workspace-admin gate, candidate consistency checks and audit log; payout remains unconfirmed | hosted CI, authenticated browser UAT, PostgreSQL workspace-isolation test and operator workflow acceptance |

| A/B experiment decision support | `backend/services/analytics_utils.py`, `POST /api/analytics/ab-test`, `tests/test_analytics_utils.py` | stable visitor assignment and deterministic posterior recommendation implemented | durable assignment/impression/conversion ledger, experiment UI, held-out evaluation and browser UAT |

| Persisted A/B experiment ledger | `ExperimentAssignment`, `ExperimentEvent`, migration `0006_experiment_assignment_ledger`, `POST /api/analytics/ab-test`, `POST /api/analytics/ab-test/event`, `frontend/app/page.tsx` | workspace-scoped assignments, idempotent events, posterior analysis and manual dashboard console implemented | hosted CI/migration gate, production site instrumentation, authenticated provider event attestation and held-out evaluation |

| Platform-native content atomizer | `backend/services/content_atomizer.py`, `ContentAtomizeRequest`, `POST /api/content/atomize`, `tests/test_content_atomizer.py` | source-grounded draft generation, deterministic fallback, disclosure and workspace-persisted assets implemented | hosted CI, full content-pillar planning, production site publishing adapters, editorial approval UX and browser UAT |

| Content angle ranker | `backend/services/content_angle_ranker.py`, `ContentAngleRankRequest`, `POST /api/content/angles/rank`, `frontend/app/page.tsx`, `tests/test_content_angle_ranker.py` | deterministic topic/audience/evidence-note ranking with risk-language flags; workspace-authenticated and draft-only; no performance forecasts | relevance evaluation set and editorial UAT; evidence notes are still operator-supplied and unverified |

| Single-page SEO audit | `backend/services/seo_audit.py`, `SEOAuditRequest`, `POST /api/research/seo-audit`, `frontend/app/page.tsx`, `tests/test_seo_audit.py`, `tests/test_seo_audit_api.py` | authenticated read-only checklist for title, description, headings, canonical, robots directives, language, viewport, image alt and internal links; no crawl/traffic claims | Search Console and response-header integration, CMS-wide crawl index, client-rendered content/browser UAT, relevance/accessibility review |

| Platform-specific AI ad targeting hypotheses | backend/services/ad_planner.py; POST /api/ads/plan; frontend/app/page.tsx; tests/test_ad_planner.py | channel-specific signal hypotheses, audience test cells, event hypotheses, audience budget splits and sensitive-targeting guardrails; review-only | authorized provider feature checks, consented event ingestion, validated stop-loss thresholds, live optimization and browser UAT |

| Ad analytics authorization boundary | `backend/main.py` ad plan, observation, performance and evaluation routes; `tests/test_ad_route_access.py` | ad-read and evaluation endpoints now require an authenticated active workspace; regression tests cover missing auth and missing workspace | deployment/session-cookie security verification, database tenant-isolation tests against PostgreSQL, live account and provider authorization checks |

| Internal-link opportunity finder | `backend/services/internal_linking.py`, `InternalLinkingRequest`, `POST /api/research/internal-links`, `frontend/app/page.tsx`, `tests/test_internal_linking.py` | bounded read-only analysis of user-supplied same-origin pages with topical-overlap scoring, missing-link suggestions, and per-page fetch status | full CMS index/crawl, user acceptance for anchor text, link-insertion workflow, rendered-JS pages, and browser UAT |

| Verified-data ad optimization review gates | `backend/services/ad_performance.py`, `GET /api/ads/performance`, `tests/test_ad_performance.py` | provider-verified minimum sample gates; ROAS stop-loss review; scale review requires 1.25× threshold and at least 10 conversions; fatigue review requires four verified dates and a 30% CTR decline; no external actions | trusted provider ingestion, mature attribution windows, provider policy/account checks, human approval UX, production instrumentation and browser UAT |

| Workspace isolation for finance, lead, email and audit operations | `backend/main.py` finance thresholds/commission evidence, leads, email queue/worker and audit routes; `backend/services/email_delivery.py`; `tests/test_finance_email_access.py` | authenticated active-workspace reads with explicit tenant filters; admin-gated threshold mutations and user-triggered email worker; email worker checks the queued item and lead belong to the selected workspace | production session security review, PostgreSQL cross-tenant integration tests, provider sending contract tests and browser UAT |

| Source-grounded X thread writer | `backend/services/content_atomizer.py`, `POST /api/content/atomize` with `x_thread`, `frontend/app/page.tsx`, `tests/test_content_atomizer.py`, `tests/test_content_atomizer_api.py` | source-grounded numbered X drafts with per-post 280-character cap and disclosure reminder persisted as reviewable workspace assets | live X account and policy checks, authorized publishing and browser UAT |

| Purple Cow differentiation audit | backend/services/purple_cow_audit.py; PurpleCowAuditRequest; POST /api/research/purple-cow-audit; frontend/app/page.tsx; tests/test_purple_cow_audit.py; tests/test_purple_cow_audit_api.py | transparent comparison against operator-supplied alternatives; score components and risky claims are review-only; missing evidence remains explicit | primary-source verification, buyer interviews, market validation and browser UAT |

| Searchable skill finder | backend/services/skill_finder.py; GET /api/skills/find; frontend/app/page.tsx; Dockerfile; tests/test_skill_finder.py; tests/test_skill_finder_api.py | read-only search over the committed 53-skill parity matrix with stage/status filters; missing inventory fails explicitly | full upstream skill source coverage, per-skill acceptance tests, live provider verification and browser UAT |

| Deterministic SVG infographic drafts | backend/services/infographic_generator.py; InfographicRequest; POST /api/content/infographic; frontend/app/page.tsx; tests/test_infographic.py | self-contained escaped SVG from operator-supplied points, authenticated workspace-scoped draft persistence and dashboard preview/download | licensed imagery or image model integration, user brand templates, image accessibility checks and browser UAT |

| Merchant-terms-based guarantee drafts | backend/services/guarantee_draft.py; GuaranteeDraftRequest; POST /api/landing/guarantee-draft; frontend/app/page.tsx; tests/test_guarantee_draft.py | requires matching type/duration in supplied terms; output marks terms unverified and persists review-only workspace draft | official merchant verification, legal/policy review, terms-change monitoring and browser UAT |

| Category taxonomy designer | backend/services/category_designer.py; CategoryDesignRequest; POST /api/research/category-design; frontend/app/page.tsx; tests/test_category_designer.py | deterministic taxonomy draft from supplied topics with collision-safe slugs, existing-label overlap flags, workspace persistence and JSON export | demand/search-volume validation, crawl and canonical analysis, live CMS application and browser UAT |
| Content decay detector | backend/services/content_decay_detector.py; ContentDecayRequest; POST /api/research/content-decay; frontend/app/page.tsx; tests/test_content_decay_detector.py | compares matched-period operator-supplied metrics and explicit content signals, scores a persisted review-only refresh queue | authorized Search Console ingestion, competitor/SERP intelligence, impact evaluation and browser UAT |
| Content moat calculator | backend/services/content_moat_calculator.py; ContentMoatRequest; POST /api/research/content-moat; frontend/app/page.tsx; tests/test_content_moat_calculator.py | calculates the 1.5× content-count target, gap, rough timeline and roadmap from operator-supplied counts | validated competitor discovery/page counts, keyword demand, quality evaluation and browser UAT |
| Traffic analyzer | backend/services/traffic_analyzer.py; TrafficAnalysisRequest; POST /api/research/traffic-analyzer; frontend/app/page.tsx; tests/test_traffic_analyzer.py | transparent weighted traffic and engagement score for operator-supplied metrics, with normalized missing components and review-only comparison | SimilarWeb or another authorized analytics provider, verified/dated traffic and region data, advertiser legitimacy verification and browser UAT |

| Upstream skill source and registry parity | knowledge/affiliate-skills/upstream/; knowledge/affiliate-skills/upstream/SOURCE_MANIFEST.json; scripts/verify_skill_registry.py; .github/workflows/ci.yml repo-guard job | source definitions and pinned registry vendored; runtime status remains independent (47 partial, 6 not implemented) | exact-SHA repo-guard workflow, app-level end-to-end acceptance for each skill, retrieval evaluation, provider authorization, lockfile/security/UAT gates |


## 2026-10-25 resumed checkpoint — lockfile and exact-SHA evidence
- Current verified HEAD before the security-audit increment: `e6e6eb4e552b4887da252db0df172dd25ee79561` on the only implementation branch `build/omni-affiliate-os-production`.
- Hosted push run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213802242 and PR run https://github.com/AITECHPRODUCTS/Project1/actions/runs/40213808545 both succeeded. The push run included a passing lockfile-sync job; the PR skipped that write-capable job by design.
- Frontend reproducibility is no longer blocked by missing lockfile: `frontend/package-lock.json` (npm lockfile v3, 141 resolved packages) is committed and regular CI runs `npm ci`, typecheck and a production build.
- The source/parity guard still reports 53 upstream skill definitions with app-runtime status 47 partial, 6 not implemented and 0 fully end-to-end complete.
- Next P0 gate is dependency auditing: a dedicated workflow job now runs pip-audit for the core/test and optional AI/RAG profiles and npm audit at high severity. The audit result is pending until the new workflow completes. Do not mark it passed just because the job is configured.
- Product readiness remains NOT RELEASE READY pending audit remediation, broader tenant/RBAC and worker security, secret scanning/SBOM, browser UAT, official provider-contract tests, deployment/staging, backup/restore and rollback.


## 2026-10-25 P0 security-audit finding
- At `f129ecf4576f1d35229525669613ecebcf17d65b`, `pip-audit -r requirements-dev.txt` found Pillow 12.3.0 vulnerabilities (scanner-listed fix 13.0.0) and pytest 8.4.2 advisory (scanner-listed fix 9.0.3). The declared bounds have been raised to these fixed versions. The next action is to re-run all backend, AI/RAG, PostgreSQL, frontend and audit gates on the resulting SHA, repair any compatibility/security failures on the same branch, and only then proceed.


## 2026-10-25 P0 dependency-resolver repair
- On commit `32ea455a6d32279777ac190a4f59f535864ac712`, the security-audit resolver could not satisfy `pytest>=9.0.3,<10.0` while `pytest-asyncio>=0.24,<1.0` remained in the dev manifest. Updated the plugin range to `pytest-asyncio>=1.3.0,<2.0` based on upstream's stated pytest 9 support. Next action: new exact-SHA regression, PostgreSQL, AI/RAG, npm and audit runs, and immediate repairs for any new failures.


## 2026-10-25 AI/RAG audit findings and compensating control
- Hosted `pip-audit -r requirements-dev.txt` passed on the fixed dependency candidate. The optional AI/RAG audit found LangChain package advisories and ChromaDB 1.5.9 IDs `PYSEC-2026-311`, `PYSEC-2026-3814`, `PYSEC-2026-3815`, and `PYSEC-2026-3813`; reviewed upstream records indicate no fixed PyPI release for those Chroma findings as of 25 October 2026.
- The remediation upgrades LangChain to compatible 1.x releases, migrates `RetrievalQA` to `langchain-classic`, and adds a CI-enforced test that Project1 uses only local embedded Chroma persistence with no HTTP client/server or `trust_remote_code=True`. Those four exact IDs may be excepted for CI only after that guard passes. The warning/exception is not a clean scan and remains a production-release blocker until a patched Chroma version is available or the vector backend is replaced.


## 2026-10-26 resume checkpoint — npm audit is the only failing CI job
- Inspected the exact current branch/head and recent runs rather than restarting from a historical snapshot. On `565c76bd7d6931721ce66cb0a84fc25129997c52`, Python tests, SQLite migrations, PostgreSQL migration/concurrency tests, repo/source guard, 53-skill parity, AI/RAG imports, and frontend typecheck/build all passed in push and PR CI.
- Push run [40215636414](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40215636414) and PR run [40215641152](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40215641152) failed only the frontend dependency audit. Its logs identify a nested Next.js/PostCSS path and postcss-selector-parser; do not count the run as green.
- The fix is on this same existing branch and includes a guarded lock refresh plus a required clean npm audit and clean-install/typecheck/build. The resulting SHA and logs must be rechecked before the backlog item can be marked complete.


## 2026-10-26 lockfile repair — follow-up full matrix required
- GitHub's temporary lock refresh succeeded: `npm audit`, clean `npm ci`, TypeScript check and production UI build passed using the patched resolution; lock commit is `0180f2f0fd84445ff76131d4ca04389676043b8a` on the existing build branch.
- The regular frontend job on the earlier commit failed because it began before that lockfile was pushed. Treat that run as failed; the success of the helper job does not substitute for exact-SHA full CI.
- Removed the one-shot lock-refresh job to keep CI deterministic. The current normal push run must validate the committed lock, full Python and PostgreSQL tests/migration gates, AI/RAG, skill parity, and frontend security audit. Keep release blocked until all required gates and the separately documented Chroma exception are resolved.


## 2026-10-26 P0 dependency gate verified on exact SHA
- Push [40264037056](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264037056) and PR [40264040473](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264040473) both completed successfully at `668b33670ea11e30f97ccc3c6e50180124609207`.
- Passed gates include the full Python suite, SQLite and PostgreSQL migration/drift, PostgreSQL concurrency, AI/RAG imports, 53-skill registry parity, frontend typecheck/build, dependency audit, clean `npm ci`, and lockfile reproducibility.
- Security caveat remains material: four exact ChromaDB advisory IDs are conditionally excepted only behind the documented local-only guard. The current result is not production security clearance. Provider authorization, browser UAT, SBOM/license/secret scan, deployment and restore evidence remain pending.


## 2026-10-26 next P0 auth/tenancy verification item
- The full CI matrix and CI-runtime action upgrade passed at `70dd041a8c27607467f8605d1eabad09f815d2bf` (https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264278741).
- Added direct regression tests for workspace-membership revocation, static-token scope denial and the workspace-member/admin boundary. These assert existing enforcement behavior and do not weaken or replace existing assertions.
- Status remains pending until the full exact-SHA CI run for the test addition succeeds.


## 2026-10-26 P0 WebSocket tenant-isolation finding and candidate fix
- Root cause: `backend/core/events.py` delivered every workflow/HITL event to every socket, `backend/core/state_machine.py` published events without workspace scope, and `/ws` checked session presence but did not revalidate the user's current membership.
- Candidate fix adds workspace-bound event metadata, fail-closed event delivery, recovery-state tenant metadata, and active membership validation on WebSocket connection. Four regression tests cover delivery isolation, unscoped event dropping, event-emitter scope, and revoked-membership denial.
- Status: pending full hosted CI on the resulting commit SHA.


## 2026-10-26 WebSocket tenant isolation — verified
- Exact SHA `65a5a884acf0195a2720cb6de76a5279fd4e5dde`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265255592 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265259440 both passed.
- Test coverage proves same-workspace event routing, dropping scope-less events, scoped event emission, and denying WebSocket connections after workspace membership revocation. All seven push jobs passed, including PostgreSQL, AI/RAG imports and the dependency audit.
- Next P0: audit and enforce workspace ownership for workflow status, pause, resume, retry, cancel and background-worker recovery endpoints/actions.


## 2026-10-26 workflow lifecycle ownership — exact-SHA proof
- At 16eee55a6935e9afa1d5f2b020c867713754aa67, push run [40265845238](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265845238) and PR run [40265848400](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265848400) passed.
- Workflow starts are explicitly scoped to the authenticated workspace. Status/resume require and validate the workspace and return a not-found result across tenants; paused recovery uses stored ownership. Dashboard status aggregates are scoped.
- Three additional tests cover authentication, cross-workspace access denial and unscoped-start rejection.
- Next: platform-admin authorization for shared knowledge ingestion and limited status disclosure.


## 2026-10-26 shared RAG ingestion permission — exact-SHA proof
- `743e404e63b7c3a54423a18b1cf17af1338c5abf` passed push [40266330644](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266330644) and PR [40266336192](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266336192).
- Shared RAG ingestion is explicitly platform-admin-only; ordinary workspace owners cannot mutate the index. UI authorization matches the API authorization, and the knowledge-status route no longer exposes an absolute host path.
- New tests prove denied workspace-owner mutation, allowed platform-admin action, and path non-disclosure.
- Next: test tenant isolation of resource-budget/learning summaries and cron/background execution contexts.

## 2026-10-26 campaign/conversion tenant binding — exact-SHA verification
- Exact SHA `4becae03e155fedc361e5b9fcdfc9fde66602f75`: push https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268073324 and PR https://github.com/AITECHPRODUCTS/Project1/actions/runs/40268078547 both completed successfully.
- Passed Python, SQLite, PostgreSQL integration/concurrency, AI/RAG imports, frontend, dependency audit, 53-skill guard and push lockfile sync.
- A first run exposed a legacy test fixture that stubbed the database session but did not provide an authorized workspace; the handler's 403 was correct. The fixture now provides a workspace and asserts both Conversion and ledger entries carry that workspace ID. The rerun passed.
- Next P0: audit remaining tenant-owned ContentAsset/Lead/ScheduledEmail routes and public lead-capture token binding.

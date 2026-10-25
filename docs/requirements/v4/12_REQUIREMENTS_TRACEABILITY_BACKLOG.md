# Requirement-to-code backlog

| ID | Area | Current evidence | Status | Acceptance still required |
|---|---|---|---|---|
| R-01 | S1 offer discovery and traffic screening | `backend/tools/affiliate_api.py`, `backend/services/s1_research.py`, `backend/services/traffic_analyzer.py`, `POST /api/research/traffic-analyzer` | partial | Authorized live source/freshness, real provider contracts, verified analytics metrics and geo validation |
| R-02 | S2 content intelligence | `backend/services/s2_s3_content.py`, `backend/services/llm.py` | partial | Claim ledger and grounding evaluation |
| R-03 | S3 SEO/blog | `backend/services/s2_s3_content.py`, `backend/services/content_decay_detector.py`, `backend/services/content_moat_calculator.py`, the content-decay and content-moat API routes | partial | Search Console ingestion, validated competitor/page counts, keyword demand, technical crawl and publish UAT |
| R-04 | S4 landing/consent | `backend/services/s4_s5_landing.py`, `backend/services/email_delivery.py` | partial | Accessibility and full consent/unsubscribe tests |
| R-05 | S5 distribution | `backend/services/s4_s5_landing.py`, `backend/services/cms_publisher.py` | partial | OAuth scopes, remote success and idempotency |
| R-06 | S6 attribution/ledger | `backend/services/tracking_service.py`, `backend/models.py`, `POST /api/webhooks/conversions/{network}` | partial | Signed bounded webhook input, per-network secrets, workspace idempotency, row-locked reversals, Numeric(18,6) append-only ledger/backfill and a read-only evidence-separated finance UI are implemented; commit `67df5a275176ebda09fa2e2f7aec041928c4e126` passed push/PR CI including PostgreSQL trigger tests. Still required: provider reconciliation, partial-reversal semantics, provider-specific signature contracts, browser UAT and end-to-end provider evidence |
| R-07 | S7 operations/budgets | `backend/services/resource_budget.py`, `backend/core/state_machine.py` | partial | Durable worker lease and distributed budget locking |
| R-08 | S8 learning | `backend/services/s6_s8_analytics.py`, `ai_memory/rag_chain.py` | partial | Independent evaluation and reversible promotion |
| R-09 | Provider catalogue | `config.yaml`, `backend/services/integration_registry.py` | catalogued/partial | Per-provider live auth, scope, contract and health evidence |
| R-10 | Autopilot truth table | `backend/services/capability_matrix.py`, `GET /api/capabilities` | implemented, not environment-verified | UI/API end-to-end and provider state sync |
| R-11 | Responsive control center | `frontend/app/page.tsx`, `frontend/components/FlywheelVisualizer.tsx` | present, unverified | Multi-viewport browser and accessibility UAT |
| R-12 | Production schema | `migrations/versions/0001_initial_schema.py`; exact-SHA CI at `e6e6eb4e552b4887da252db0df172dd25ee79561` | PostgreSQL upgrade/downgrade/drift and reversal integration pass in push/PR runs | Production backup/restore rehearsal, rollback evidence and deployed database operations |
| R-13 | Tenant SaaS | `backend/models.py`, `backend/main.py` | major gap | Workspace schema, row-level scope and cross-tenant tests |
| R-14 | Platform Super Admin | requirements and current global admin gaps | not implemented end-to-end | Separate platform RBAC, tenant/incident/kill switch UI |
| R-15 | All 53 skills | `../skill-parity-matrix.csv` | 47 partial, 6 not implemented | Implement and verify each skill service/API/UI/provider path |
| R-16 | Production release | Actions + deployment docs | not release ready | All required CI, provider, security, staging and rollback gates |

| R-17 | Affiliate portfolio operations | `backend/services/multi_program_manager.py`, `POST /api/automation/multi-program-manager` | partial | Authorized network data and payout reconciliation, attribution quality, program-action UAT |

| R-18 | P0 — pinned skill source/traceability | `knowledge/affiliate-skills/upstream/SOURCE_MANIFEST.json`; 53 vendored skill documents; `scripts/verify_skill_registry.py`; repo-guard CI on `e6e6eb4e552b4887da252db0df172dd25ee79561` | source integrity and registry/status parity guard passed on exact push/PR SHA; runtime 47 partial / 6 not implemented | Per-skill service/API/UI/provider acceptance, retrieval evaluation and provider authorization remain independently required |

| R-19 | P0 — reproducible frontend dependencies | `frontend/package-lock.json` (npm lockfile v3, 141 packages); `npm ci` typecheck/build on exact SHA `e6e6eb4e552b4887da252db0df172dd25ee79561` | implemented and CI-verified on push/PR; lockfile-sync passed on push | Continue running `npm ci`; add SBOM/license/secret scans and keep dependency audit findings remediated |

| R-20 | P0 — dependency security audits | `.github/workflows/ci.yml` `security-audit` job; `pip-audit` core/test and AI/RAG profiles; `npm audit --audit-level=high` | scanner added; Pillow/pytest advisories found, fixed-version ranges applied; pytest-asyncio resolver constraint corrected; re-verification pending | Pass core/test + AI/RAG pip-audit and npm audit on exact SHA; remediate all findings, attach SBOM/license/secret-scan evidence |

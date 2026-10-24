# Master requirement traceability
| Requirement area | Implementation path | Current status | Remaining acceptance evidence |
|---|---|---|---|
| S1 research / offer intelligence | `backend/services/s1_research.py`, `backend/tools/affiliate_api.py`, `backend/services/offer_intelligence.py` | partial | Authorized provider contracts, demand-source quality, geo freshness |
| S2 creative / evidence brief | `backend/services/s2_s3_content.py`, `backend/services/llm.py` | partial | Claim-by-claim evidence and generated claim evaluation |
| S3 SEO / blogs | `backend/services/s2_s3_content.py` | partial | Search Console, technical SEO crawl and publish UAT |
| S4 offers / landing / lead | `backend/services/s4_s5_landing.py`, `backend/main.py`, `backend/services/email_delivery.py` | partial | Accessibility, deployed landing and consent/unsubscribe tests |
| S5 distribution / nurture | `backend/services/s4_s5_landing.py`, `backend/services/cms_publisher.py`, `backend/services/email_delivery.py` | partial | Real OAuth scopes, provider response verification, policy checks |
| S6 attribution / experiment | `backend/services/analytics_utils.py`, `backend/services/tracking_service.py`, `backend/models.py` | partial | Durable experiment ledger, provider event reconciliation, privacy |
| S7 operations / cost control | `backend/services/resource_budget.py`, `backend/services/ad_manager.py`, `backend/core/middleware.py` | partial | Distributed budget locking, measured provider invoices, admin console |
| S8 performance memory | `backend/services/s6_s8_analytics.py`, `ai_memory/rag_chain.py` | partial | Ground-truth sample sufficiency, promotion/rollback and held-out evaluation |
| API persistence | `backend/database.py`, `backend/models.py` | partial | Alembic migrations; PostgreSQL upgrade/rollback/backups |
| UI / responsive control center | `frontend/app/page.tsx`, `frontend/components/FlywheelVisualizer.tsx` | present, unverified | GitHub frontend typecheck/build and browser a11y/UAT |
| Provider registry | `backend/services/integration_registry.py`, `config.yaml` | partial | Account credentials, scopes, live contract and revocation tests |
| Platform Super Admin | `backend/main.py`, `backend/models.py` | major gap | Global admin RBAC/tenant lifecycle/quota/incident console |
| Skill runtime parity | `docs/skill-parity-matrix.csv` | major gap | Complete every matrix row with service/API/UI/contracts/tests |

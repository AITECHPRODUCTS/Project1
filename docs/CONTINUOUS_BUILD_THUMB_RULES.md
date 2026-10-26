# Continuous-build thumb rules

Canonical project: https://github.com/AITECHPRODUCTS/Project1
Single implementation branch: build/omni-affiliate-os-production

These additive rules apply to every future Project1 build session.

1. Review prior chats and all available conversation/Library attachments relevant to the master prompt before coding. Read the source register and requirements contract. Note missing files explicitly and never claim to have inspected an unavailable ZIP.
2. Continue without another prompt. Do not ask the user to reissue the master command, select the next ordinary feature, or tell them to wait. Choose the highest-priority unblocked item from the traceability backlog.
3. Use only AITECHPRODUCTS/Project1 and build/omni-affiliate-os-production for code, tests, docs, repairs and workflow fixes. Do not create feature/fix/test branches, rewrite history, reset shared state or alter other repositories.
4. Implement small vertical slices with backend/schema/API/UI work where applicable, regression tests and traceability. Prefer additive changes and preserve existing endpoints, feature behavior and data.
5. After each push, inspect hosted Python tests and migration gate, AI/RAG verification, and frontend typecheck/production build for the exact commit SHA. Read failing logs, fix on the same branch and rerun. Queued, cancelled or in-progress is not a pass.
6. Report status with evidence. Distinguish implemented, partial, not implemented and blocked. CI success alone is not production certification; PostgreSQL migration tests, security review, provider authorization, browser UAT and deployment health remain separate gates.
7. Never commit credentials, customer data or private media. External publishing, paid spend, payouts, audience uploads and account mutations remain disabled until provider authorization, consent, idempotency, approval and kill-switch requirements are implemented and verified.
8. The 2026-10-25 upload affiliate-skills-main(1).zip was inspected and is an MIT-licensed source skill pack (53 definitions, registry/evals/docs/CLI). The content-decay-detector, content-moat-calculator, traffic-analyzer and multi-program-manager specs are used as source contracts; their data-provider gaps must remain explicit. This ZIP is not a deployable FastAPI/Next.js application. Also use the prior Library app-source snapshot OmniAffiliateOS_build.zip as reference only. For any additional live-app ZIP, inspect archive safety, license/provenance, secrets, dependencies, architecture, migrations, tests and workflows; compare with the current backlog and port only compatible, validated code. Never blindly replace Project1.
9. Update implementation status, requirements traceability, skill parity and blocker evidence after each slice. State each completion-stat denominator and never treat the 53-skill inventory as overall product completion.
10. The 25 October 2026 ZIP-reminder checkpoint has been met: a source package arrived. Continue implementation from all available materials and do not block on another prompt or reminder.

11. After each vertical slice is implemented and its hosted CI is checked, immediately continue to the next highest-priority unblocked requirement in the same session. Never stop to request an ordinary next command. At the start of each session, re-review prior chat requirements and relevant Library attachments, maintain a clear blocked/unblocked list, and keep progressing on independent work while external provider approvals or credentials remain pending.

12. Treat every instruction in the user's messages and every relevant attached source as additive, binding requirements. Review the actual text—not just filenames or a partial summary—preserve its terminology and constraints, map requirements to acceptance criteria, and update this rules file plus traceability/status records when the user adds a rule. Do not silently discard any instruction, and do not ask the user to repeat the master command or choose the next ordinary task.
13. Use the Full Blueprint v3 build sequence as the priority order: recover exact repository/branch/HEAD and CI evidence first; then complete P0 engineering, dependency/lockfile, security/tenancy and traceability gates before low-priority feature breadth. A source skill document or heuristic service is not end-to-end capability evidence; provider, implementation, testing and production readiness have separate statuses.


14. Current verified checkpoint: at HEAD `e6e6eb4e552b4887da252db0df172dd25ee79561`, push run 40213802242 and PR run 40213808545 passed, including npm ci, frontend typecheck/build, Python, PostgreSQL, AI/RAG and repo-guard; the push lockfile-sync job passed. The frontend lockfile is committed. The new security-audit job is pending exact-SHA evidence until its next hosted run completes; do not mark security scanning complete from configuration alone.


15. Dependency scanning is a fix gate, not a report-only decoration. When pip-audit/npm audit report an available fixed version, adjust compatible dependency ranges, preserve app constraints, rerun the full CI matrix, and record remaining findings with evidence. Never suppress or label the scan green before exact-SHA results prove it.


16. When upgrading an audited dependency, update conflicting plugin/test-runner constraints based on upstream compatibility evidence, then prove dependency resolution and run the entire regression matrix. A successful audit tool install alone is not a pass.


17. A dependency advisory with no upstream fix must not be silently suppressed or described as clean. Any temporary exception requires exact advisory IDs, source links, an explicit exploitability boundary, enforceable compensating controls, a regression test, an explicit CI warning, and a release blocker until the exception is removed or formally re-evaluated.


18. Resume checkpoint dated 2026-10-26: the current next action is to repair the verified npm audit failure on the existing `build/omni-affiliate-os-production` branch; do not restart/rebase/branch-switch. Pre-repair SHA `565c76bd7d6931721ce66cb0a84fc25129997c52` has passing Python, PostgreSQL, AI/RAG, skill-parity and frontend build jobs but failing `npm audit` (five advisories reported). Preserve all passing areas, regenerate the lockfile through the guarded one-shot workflow, inspect logs, and rerun the full matrix before advancing to the next P0 backlog item.


19. 2026-10-26 lockfile checkpoint: the temporary `dependency-remediation` workflow job passed `npm audit`, `npm ci`, frontend typecheck and production build, then committed the patched lockfile as `0180f2f0fd84445ff76131d4ca04389676043b8a`. That bot commit did not give a normal full-matrix push run; do not count it as a full CI pass. The temporary lock-refresh job has been removed. The next regular commit must trigger the full matrix on the committed Next.js 16.4.3 lockfile; inspect and fix failures before selecting another P0 task.


20. 2026-10-26 verified checkpoint: full push run [40264037056](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264037056) and PR run [40264040473](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264040473) passed on exact SHA `668b33670ea11e30f97ccc3c6e50180124609207`. The frontend npm audit and standard/AI-RAG audits passed, with only the four precisely documented Chroma advisories conditionally excepted by the embedded-only guard. Preserve this as a verified checkpoint. Next: move GitHub Actions dependencies off retired Node 20 releases to current Node 24-capable action majors, then rerun the full matrix; production is still blocked by the Chroma exception and provider/UAT/deploy/restore gates.


21. P0 tenant-auth regression tests: signed sessions with deactivated workspace membership are rejected and cleared (403); static bearer API tokens are denied for workspace-scoped access (403); workspace members are denied workspace-admin permissions. Verified on exact SHA `e715878c76fb6f1876c2ff1769653fa72ad51396` by successful push run [40264570099](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40264570099). This does not substitute for broad route-by-route authorization, WebSocket/export/background-job tests, or production release gates.


22. P0 WebSocket tenant isolation: workflow/HITL events must never be globally broadcast. Workflow events require workspace scope; EventHub delivers only to sockets for the same verified workspace and drops unscoped/legacy payloads. WebSocket connection setup revalidates active membership instead of trusting cached session role. Tests in `tests/test_websocket_tenant_isolation.py` passed on exact SHA `65a5a884acf0195a2720cb6de76a5279fd4e5dde`; push [40265255592](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265255592) and PR [40265259440](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265259440) both succeeded. Next audit workflow run status/pause/resume/retry ownership checks.


23. P0 workflow lifecycle ownership: workflow starts require an authorized workspace; workflow status/resume must use the owner workspace; background pause recovery must pass the persisted workspace explicitly; dashboard totals must be workspace-scoped. Verified on exact SHA 16eee55a6935e9afa1d5f2b020c867713754aa67 by push [40265845238](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265845238) and PR [40265848400](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40265848400), both successful. Next: gate global knowledge-index mutation to platform operations and avoid leaking host paths in ordinary status responses.


24. P0 shared knowledge-index mutation: the shared RAG ingestion endpoint is platform-admin-only; non-platform workspace owners receive 403, the UI hides the action unless `isPlatformAdmin` is true, and knowledge status does not disclose an absolute filesystem path. Verified on exact SHA `743e404e63b7c3a54423a18b1cf17af1338c5abf` by successful push [40266330644](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266330644) and PR [40266336192](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40266336192). Keep the documented Chroma advisory exception as a production blocker; next audit resource-budget and learning aggregates for tenant scope.


25. P0 resource-budget / learning tenant boundary: `ResourceUsage` and `PerformanceMemory` are tenant-scoped. Resource-budget reserve/finalize/status and performance-learning helpers must fail closed without an authorized workspace, must reject a mismatched requested workspace, and must scope database reads/writes. API routes and scheduled jobs must pass the tenant explicitly. The regression-test commit is pending full exact-SHA CI.

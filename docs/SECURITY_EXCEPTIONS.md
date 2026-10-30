# Vector-store security exception record

**Status:** historical remediation record; dependency replacement verified in CI on `3ba90e4cb2fcb72494c0fda71e1d535398229c22`. Push [40304270245](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304270245) and PR [40304278972](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304278972) passed with the unignored AI dependency audit and AI/RAG import checks green.
**Production release:** still blocked by the other release/UAT gates documented in the implementation status.

## Historical upstream findings

The prior optional RAG graph included ChromaDB 1.5.9, which was reported against:
- `PYSEC-2026-311` / CVE-2026-45829 (pre-auth code injection)
- `PYSEC-2026-3814` / CVE-2026-45833 (code injection)
- `PYSEC-2026-3815` / CVE-2026-45831 (tenant/database/collection authorization)
- `PYSEC-2026-3813` / CVE-2026-45830 (cross-tenant access)

These records describe the former package graph. This project does **not** claim the upstream ChromaDB package has been patched.

## Candidate remediation

- Remove both `chromadb` and `langchain-chroma` from `requirements-ai.txt`.
- Replace the Chroma-backed index with `ai_memory/local_vector_store.py`: a local `sqlite3` database storing normalized float32 embedding vectors, source text and JSON metadata. Queries use bounded in-process cosine similarity.
- Preserve the existing configured persistence directory and `CHROMA_PERSIST_DIR` environment variable as compatibility names. The new on-disk index file is `local_vectors.sqlite3`.
- The index supports stable-ID upsert, stale chunk deletion and collection/embedding-model identity checks. It does not use a remote vector service or pickle/dill deserialization.
- Remove the previous four `pip-audit --ignore-vuln` arguments and the conditional audit warning. The optional AI/RAG dependency graph must pass `pip-audit -r requirements-ai.txt` without ignored advisories.

## Verification and rollout

This is still a **candidate** until exact-SHA push and PR workflows pass, including the unignored AI audit, static security guard, SQLite persistence/search tests and AI-profile imports. Old Chroma index files are not automatically converted or deleted; after rollout, operators must run `python -m ai_memory.ingester` to build the SQLite index. Keep the old directory/backups until the replacement index is validated.

Actual trusted-proxy ingress verification, authorized provider live UAT, SBOM/license/secret scans, deployment smoke and backup/restore remain separate release gates.


## Remediation verification evidence — 2026-10-26
- Exact verified SHA: `3ba90e4cb2fcb72494c0fda71e1d535398229c22`.
- Push [40304270245](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304270245) and PR [40304278972](https://github.com/AITECHPRODUCTS/Project1/actions/runs/40304278972) both succeeded.
- `pip-audit -r requirements-ai.txt` ran without advisory-ignore flags and passed. The local SQLite vector-store guard and all 10 AI/RAG import checks passed.
- This record preserves the removed package's former vulnerability context; it is not a current advisory exception. The new index still requires data re-ingestion and staging verification before production use.

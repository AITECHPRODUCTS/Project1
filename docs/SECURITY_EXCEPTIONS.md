# Vector-store security exception record

**Status:** ChromaDB dependency removal candidate; not verified until the exact-SHA push and PR workflows pass with a clean, unignored AI dependency audit.
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

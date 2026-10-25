# Temporary security exception — embedded-only ChromaDB

**Review date:** 25 October 2026  
**Status:** temporary, configuration-scoped mitigation; **not** a clean dependency scan and **not** production-release approval.  
**Scope:** optional AI/RAG profile only.

## Unpatched upstream findings

The latest PyPI ChromaDB release resolved by CI is 1.5.9. The audit database reports these IDs without a fixed version: `PYSEC-2026-311` / CVE-2026-45829 (pre-auth code injection), `PYSEC-2026-3814` / CVE-2026-45833 (code injection), `PYSEC-2026-3815` / CVE-2026-45831 (tenant/database/collection authorization), and `PYSEC-2026-3813` / CVE-2026-45830 (cross-tenant access). As checked on 25 October 2026, the upstream/published records mark 1.5.9 as affected and no fixed PyPI version is available.

References:
- https://osv.dev/vulnerability/PYSEC-2026-311
- https://osv.dev/vulnerability/PYSEC-2026-3814
- https://osv.dev/vulnerability/PYSEC-2026-3815
- https://osv.dev/vulnerability/PYSEC-2026-3813
- https://github.com/chroma-core/chroma/issues/7909

## Compensating controls enforced by code and CI

- Project1 uses LangChain's Chroma integration with a local `persist_directory` in `ai_memory/ingester.py` and `ai_memory/rag_chain.py`.
- Project1 does not configure a separate Chroma HTTP server, a `chromadb.HttpClient` / `AsyncHttpClient`, or a Chroma network listener in Docker Compose.
- The product runtime may not set `trust_remote_code=True` for untrusted model repositories.
- `scripts/verify_chroma_security_boundary.py` enforces these assumptions in CI; `tests/test_ai_security_boundary.py` is its regression test.
- The AI dependency audit may ignore only these four exact PYSEC IDs, only after the local-only guard passes. Any other advisory fails the audit and must be fixed. The workflow emits an explicit warning when this exception is in force.

## Release restriction

This mitigation does **not** patch ChromaDB. Do not deploy a standalone/network-exposed Chroma service, enable remote code, or promote this dependency profile as fully security-cleared. Production release remains blocked until a patched upstream version is available and the ignore list is removed, or Chroma is replaced with a separately reviewed vector-store implementation and the full RAG acceptance suite passes.

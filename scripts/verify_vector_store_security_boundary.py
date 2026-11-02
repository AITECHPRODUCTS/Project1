from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOTS = (ROOT / "backend", ROOT / "ai_memory")


def verify_vector_store_boundary(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    requirements_path = root / "requirements-ai.txt"
    try:
        requirements = requirements_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        requirements = ""
        errors.append(f"AI requirements unavailable: {exc}")
    active_requirements = "\n".join(
        line.split("#", 1)[0].strip().lower()
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if re.search(r"(?m)^\s*(?:chromadb|langchain-chroma)(?:\s|[<>=!~;]|$)", active_requirements):
        errors.append("ChromaDB and langchain-chroma must not be installed in the product AI profile")

    store_path = root / "ai_memory" / "local_vector_store.py"
    ingester_path = root / "ai_memory" / "ingester.py"
    rag_path = root / "ai_memory" / "rag_chain.py"
    for path in (store_path, ingester_path, rag_path):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"required local vector source unavailable ({path.relative_to(root)}): {exc}")
            continue
        if path == store_path and ("sqlite3" not in source or "INDEX_FILENAME" not in source):
            errors.append("local vector store must use a named SQLite persistence file")
        if path in (ingester_path, rag_path) and "LocalSQLiteVectorStore" not in source:
            errors.append(f"{path.relative_to(root)} must use LocalSQLiteVectorStore")
        for forbidden in ("langchain_chroma", "chromadb.", "Chroma("):
            if forbidden in source:
                errors.append(f"removed vector dependency found: {forbidden} in {path.relative_to(root)}")

    runtime_sources: list[str] = []
    for base in RUNTIME_ROOTS:
        if not base.exists():
            errors.append(f"runtime directory missing: {base.relative_to(root)}")
            continue
        for path in base.rglob("*.py"):
            try:
                runtime_sources.append(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as exc:
                errors.append(f"cannot inspect {path.relative_to(root)}: {exc}")
    runtime = "\n".join(runtime_sources)
    if re.search(r"\b(?:chromadb|langchain_chroma)\b", runtime):
        errors.append("removed Chroma package reference remains in backend/ai_memory runtime")
    if re.search(r"\btrust_remote_code\s*=\s*True\b", runtime):
        errors.append("trust_remote_code=True is forbidden in product runtime")
    if re.search(r"\b(?:pickle|dill)\.(?:load|loads)\s*\(", runtime):
        errors.append("unsafe pickle/dill deserialization is forbidden in product runtime")

    for path in (root / "docker-compose.yml", root / "Dockerfile"):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"container security file unavailable ({path.relative_to(root)}): {exc}")
            continue
        if re.search(r"^\s{2}chroma(?:db)?\s*:", content, re.MULTILINE | re.IGNORECASE):
            errors.append(f"{path.relative_to(root)} must not declare a standalone Chroma service")
        if re.search(r"chromadb?[-_ ]server|CHROMA_(?:HOST|SERVER_URL|HTTP_HOST)", content, re.IGNORECASE):
            errors.append(f"{path.relative_to(root)} configures a remote Chroma server")
    return errors


def main() -> int:
    errors = verify_vector_store_boundary()
    if errors:
        print("LOCAL SQLITE VECTOR-STORE SECURITY BOUNDARY FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("LOCAL SQLITE VECTOR-STORE SECURITY BOUNDARY PASSED")
    print("No ChromaDB package or remote vector service is configured; the index is stored in local SQLite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

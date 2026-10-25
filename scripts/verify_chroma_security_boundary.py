from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOTS = (ROOT / "backend", ROOT / "ai_memory")


def verify_chroma_boundary(root: Path = ROOT) -> list[str]:
    """Enforce the temporary embedded-only mitigation for upstream-unfixed Chroma advisories."""
    errors: list[str] = []
    required_rag_files = (root / "ai_memory" / "ingester.py", root / "ai_memory" / "rag_chain.py")

    for path in required_rag_files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"required RAG source unavailable ({path.relative_to(root)}): {exc}")
            continue
        if "Chroma(" not in source or "persist_directory=" not in source:
            errors.append(f"{path.relative_to(root)} must instantiate Chroma using local persistence")
        for forbidden in ("chromadb.HttpClient", "chromadb.AsyncHttpClient", "chromadb.server"):
            if forbidden in source:
                errors.append(f"remote Chroma access is forbidden: {forbidden} in {path.relative_to(root)}")

    runtime_sources: list[str] = []
    for base in RUNTIME_ROOTS:
        for path in base.rglob("*.py"):
            try:
                runtime_sources.append(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as exc:
                errors.append(f"cannot inspect {path.relative_to(root)}: {exc}")
    runtime = "\n".join(runtime_sources)
    if re.search(r"\bchromadb\.(?:Async)?HttpClient\s*\(", runtime):
        errors.append("Chroma HttpClient/AsyncHttpClient is present in runtime source")
    if re.search(r"\btrust_remote_code\s*=\s*True\b", runtime):
        errors.append("trust_remote_code=True is forbidden in product runtime")

    try:
        compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
        config = (root / "backend" / "config.py").read_text(encoding="utf-8")
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"container/config security files unavailable: {exc}")
        compose = config = dockerfile = ""

    if re.search(r"^\s{2}chroma(?:db)?\s*:", compose, re.MULTILINE | re.IGNORECASE):
        errors.append("docker-compose.yml must not expose a standalone Chroma service")
    if any(token in compose or token in config for token in ("CHROMA_HOST", "CHROMA_SERVER_URL", "CHROMA_HTTP_HOST")):
        errors.append("remote Chroma host/server configuration is forbidden")
    if re.search(r"(?:chromadb|chroma-server).{0,80}(?:EXPOSE|ports:)", dockerfile, re.IGNORECASE | re.DOTALL):
        errors.append("Dockerfile must not expose or launch a standalone Chroma server")
    return errors


def main() -> int:
    errors = verify_chroma_boundary()
    if errors:
        print("CHROMA LOCAL-ONLY SECURITY BOUNDARY FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("CHROMA LOCAL-ONLY SECURITY BOUNDARY PASSED")
    print("Chroma is used with embedded local persistence only; no network server or remote-code option is configured.")
    print("Upstream package advisories remain open and are explicitly excepted only in the AI dependency audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

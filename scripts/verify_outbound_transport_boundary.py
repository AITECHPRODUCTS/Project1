from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
APPROVED_TRANSPORT = "backend/services/url_safety.py"
RUNTIME_ROOTS = ("backend", "ai_memory")

_HTTP_METHODS = {"request", "get", "head", "options", "post", "put", "patch", "delete", "stream"}
_FORBIDDEN_EXACT = {
    "httpx.Client",
    "httpx.AsyncClient",
    "aiohttp.ClientSession",
    "urllib3.PoolManager",
    "urllib3.ProxyManager",
    "urllib.request.urlopen",
    "urllib.request.urlretrieve",
    "http.client.HTTPConnection",
    "http.client.HTTPSConnection",
    "socket.create_connection",
    "socket.socket",
}


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def find_transport_violations(source: str, relative_path: str) -> list[str]:
    """Return raw outbound-client call sites outside the single pinned transport."""
    if relative_path.replace("\\", "/") == APPROVED_TRANSPORT:
        return []
    try:
        tree = ast.parse(source, filename=relative_path)
    except SyntaxError as exc:
        return [f"{relative_path}:{exc.lineno}: cannot parse source: {exc.msg}"]

    module_aliases: dict[str, str] = {}
    imported_names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                canonical_module = alias.name if alias.asname else alias.name.split(".", 1)[0]
                module_aliases[local_name] = canonical_module
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    continue
                imported_names[alias.asname or alias.name] = f"{module}.{alias.name}".strip(".")

    def canonical_call(node: ast.AST) -> str:
        name = _dotted_name(node)
        if name in imported_names:
            return imported_names[name]
        if not name:
            return ""
        parts = name.split(".")
        if parts[0] in module_aliases:
            parts[0] = module_aliases[parts[0]]
        return ".".join(parts)

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = canonical_call(node.func)
        forbidden = target in _FORBIDDEN_EXACT
        segments = target.split(".")
        if len(segments) == 2 and segments[0] in {"httpx", "requests"} and segments[1] in _HTTP_METHODS:
            forbidden = True
        if len(segments) == 3 and segments[:2] == ["requests", "api"] and segments[2] in _HTTP_METHODS:
            forbidden = True
        if forbidden:
            violations.append(
                f"{relative_path}:{getattr(node, 'lineno', '?')}: raw outbound client {target} "
                f"must use backend.services.url_safety"
            )

        if target.endswith(".ChatOpenAI"):
            required_sdk_transports = ("http_client", "http_async_client")
        elif target.endswith(".AsyncOpenAI") or target.endswith(".OpenAI"):
            required_sdk_transports = ("http_client",)
        else:
            required_sdk_transports = ()
        supplied_keywords = {keyword.arg for keyword in node.keywords if keyword.arg}
        for required_sdk_transport in required_sdk_transports:
            if required_sdk_transport not in supplied_keywords:
                violations.append(
                    f"{relative_path}:{getattr(node, 'lineno', '?')}: provider SDK client {target} "
                    f"must receive {required_sdk_transport} backed by backend.services.url_safety"
                )
    return sorted(set(violations))


def _runtime_python_files() -> Iterable[Path]:
    for directory in RUNTIME_ROOTS:
        root = ROOT / directory
        if root.is_dir():
            yield from sorted(root.rglob("*.py"))


def main() -> int:
    errors: list[str] = []
    approved_path = ROOT / APPROVED_TRANSPORT
    if not approved_path.is_file():
        errors.append(f"missing approved transport implementation: {APPROVED_TRANSPORT}")
    else:
        transport_source = approved_path.read_text(encoding="utf-8")
        for required in (
            "follow_redirects=False",
            "trust_env=False",
            "request.url.copy_with(host=connect_ip)",
            'request.extensions["sni_hostname"]',
        ):
            if required not in transport_source:
                errors.append(f"pinned transport invariant missing from {APPROVED_TRANSPORT}: {required}")

    scanned = 0
    for path in _runtime_python_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative == APPROVED_TRANSPORT:
            continue
        scanned += 1
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            errors.append(f"{relative}: cannot decode source: {exc}")
            continue
        errors.extend(find_transport_violations(source, relative))

    llm_path = ROOT / "backend/services/llm.py"
    if not llm_path.is_file():
        errors.append("missing hosted-LLM integration: backend/services/llm.py")
    else:
        llm_source = llm_path.read_text(encoding="utf-8")
        required_llm_transport_bits = (
            "pinned_public_client(",
            "pinned_public_async_client(",
            "http_client=sync_http_client",
            "http_async_client=async_http_client",
        )
        for required in required_llm_transport_bits:
            if required not in llm_source:
                errors.append(f"OpenAI-compatible LLM is missing pinned SDK transport configuration: {required}")

    if errors:
        print("OUTBOUND TRANSPORT BOUNDARY FAILED")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1
    print("OUTBOUND TRANSPORT BOUNDARY PASSED")
    print(f"Runtime Python files scanned: {scanned}")
    print(f"Raw HTTP client constructors are restricted to {APPROVED_TRANSPORT}")
    print("Pinned-IP, TLS SNI, redirect and ambient-proxy invariants are present")
    print("OpenAI-compatible SDK clients must inject DNS-pinned sync and async transports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

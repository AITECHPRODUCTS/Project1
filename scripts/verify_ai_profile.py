from __future__ import annotations

import importlib
import sys

MODULES = (
    "langchain",
    "langchain_chroma",
    "langchain_huggingface",
    "langchain_openai",
    "langchain_text_splitters",
    "chromadb",
    "sentence_transformers",
    "openai",
)


def main() -> int:
    missing: list[str] = []
    for module in MODULES:
        try:
            importlib.import_module(module)
        except Exception as exc:  # Report broken native/import dependencies too.
            missing.append(f"{module}: {type(exc).__name__}: {str(exc)[:220]}")
    if missing:
        print("AI/RAG profile verification FAILED")
        for item in missing:
            print(f"- {item}")
        return 1
    print(f"AI/RAG profile verification PASSED ({len(MODULES)} imports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

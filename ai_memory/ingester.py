from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path
from typing import Any

COLLECTION_NAME = "affiliate_doctrine"
REQUIRED_REFERENCES = {
    "offer-frameworks.md",
    "platform-rules.md",
    "seo-strategy.md",
    "social-data-providers.md",
}
EXCLUDED_PARTS = {"node_modules", ".git", ".next", "dist", "build", "__pycache__"}


def find_markdown_files(repository: Path) -> list[Path]:
    roots = [repository / "shared" / "references", repository / "skills"]
    files: set[Path] = set()
    for root in roots:
        if root.exists():
            files.update(root.rglob("*.md"))
    files.update(path for path in repository.glob("*.md") if path.is_file())
    return sorted(
        path for path in files
        if path.is_file() and path.stat().st_size
        and not any(part in EXCLUDED_PARTS for part in path.parts)
    )


def split_markdown(path: Path, repository: Path, chunk_size: int = 1200, overlap: int = 180) -> list[Any]:
    try:
        from langchain_core.documents import Document
        from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise RuntimeError("Install requirements-ai.txt to use RAG ingestion") from exc
    content = path.read_text(encoding="utf-8", errors="replace").replace("\x00", "")
    content = re.sub(r"\n{4,}", "\n\n\n", content).strip()
    if not content:
        return []
    relative = path.relative_to(repository).as_posix()
    headers = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )
    sections = headers.split_text(content)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        add_start_index=True,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(sections or [Document(page_content=content)])
    results: list[Any] = []
    for index, chunk in enumerate(chunks):
        text = chunk.page_content.strip()
        if not text:
            continue
        heading = " | ".join(
            f"{key}: {chunk.metadata[key]}"
            for key in ("h1", "h2", "h3")
            if chunk.metadata.get(key)
        )
        full_text = f"Source path: {relative}\nSection: {heading or 'document'}\n\n{text}"
        digest = hashlib.sha256(f"{relative}:{index}:{full_text}".encode()).hexdigest()
        results.append(
            Document(
                page_content=full_text,
                metadata={
                    "source": relative,
                    "chunk_index": index,
                    "content_hash": digest,
                    "document_kind": "skill" if relative.startswith("skills/") else "reference",
                    **{key: value for key, value in chunk.metadata.items() if key in {"h1", "h2", "h3"}},
                },
            )
        )
    return results


def build_documents(repository: Path, chunk_size: int = 1200, overlap: int = 180) -> list[Any]:
    if not repository.is_dir():
        raise FileNotFoundError(f"Skill repository not found: {repository}")
    reference_dir = repository / "shared" / "references"
    missing = sorted(name for name in REQUIRED_REFERENCES if not (reference_dir / name).is_file())
    if missing:
        raise FileNotFoundError(
            f"Required reference file(s) missing from {reference_dir}: {', '.join(missing)}"
        )
    documents = [
        document
        for path in find_markdown_files(repository)
        for document in split_markdown(path, repository, chunk_size, overlap)
    ]
    if not documents:
        raise RuntimeError("No non-empty markdown documents found")
    return documents


def ingest(
    repository: Path,
    persist_directory: Path,
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    chunk_size: int = 1200,
    overlap: int = 180,
    collection_name: str = COLLECTION_NAME,
) -> dict[str, Any]:
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError as exc:
        raise RuntimeError("Install requirements-ai.txt to use local vector indexing") from exc
    from ai_memory.local_vector_store import LocalSQLiteVectorStore

    if chunk_size < 200 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require chunk_size >= 200 and 0 <= overlap < chunk_size")
    documents = build_documents(repository, chunk_size, overlap)
    embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model,
        model_kwargs={"device": os.getenv("EMBEDDING_DEVICE", "cpu")},
        encode_kwargs={"normalize_embeddings": True},
    )
    store = LocalSQLiteVectorStore(
        persist_directory=persist_directory,
        collection_name=collection_name,
        embedding_function=embeddings,
        embedding_id=embedding_model,
    )
    ids = [document.metadata["content_hash"] for document in documents]
    active_ids = set(ids)
    for offset in range(0, len(documents), 64):
        store.add_documents(documents[offset : offset + 64], ids=ids[offset : offset + 64])

    stale_ids = []
    existing = store.get(include=["metadatas"])
    for document_id, metadata in zip(existing["ids"], existing.get("metadatas", [])):
        if (
            isinstance(metadata, dict)
            and metadata.get("document_kind") in {"skill", "reference"}
            and document_id not in active_ids
        ):
            stale_ids.append(document_id)
    for offset in range(0, len(stale_ids), 64):
        store.delete(ids=stale_ids[offset : offset + 64])

    return {
        "repository": str(repository.resolve()),
        "persist_directory": str(persist_directory.resolve()),
        "collection": collection_name,
        "chunks_processed": len(documents),
        "collection_count": store.count(),
        "markdown_files": len(find_markdown_files(repository)),
        "stale_chunks_deleted": len(stale_ids),
        "index_file": str(store.db_path.resolve()),
        "vector_store": "local_sqlite",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest licensed affiliate doctrine into a local SQLite vector index")
    parser.add_argument("--repository", default=os.getenv("AFFILIATE_SKILLS_DIR", "./knowledge/affiliate-skills"))
    parser.add_argument("--persist-directory", default=os.getenv("CHROMA_PERSIST_DIR", "./storage/chroma"))
    parser.add_argument("--embedding-model", default=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=180)
    args = parser.parse_args()
    import json

    print(
        json.dumps(
            ingest(
                Path(args.repository),
                Path(args.persist_directory),
                args.embedding_model,
                args.chunk_size,
                args.overlap,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

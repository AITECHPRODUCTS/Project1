from __future__ import annotations

import re
from typing import Any

IMMUTABLE_MODEL_REVISION = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def normalize_embedding_revision(revision: str | None) -> str | None:
    """Return an immutable Hugging Face commit SHA or None for a local/dev artifact."""
    if revision is None or not str(revision).strip():
        return None
    normalized = str(revision).strip().lower()
    if not IMMUTABLE_MODEL_REVISION.fullmatch(normalized):
        raise ValueError("Embedding model revision must be a 40-character immutable commit SHA")
    return normalized


def embedding_identity(model_name: str, revision: str | None = None) -> str:
    """Distinguish vector indexes created with different immutable model revisions."""
    model = str(model_name).strip()
    if not model:
        raise ValueError("Embedding model name or local path is required")
    normalized_revision = normalize_embedding_revision(revision)
    return f"{model}@{normalized_revision}" if normalized_revision else model


def build_local_embeddings(
    model_name: str,
    *,
    device: str = "cpu",
    revision: str | None = None,
) -> Any:
    """Create embeddings using only pre-staged/cache-resident artifacts.

    Runtime application and indexing never implicitly download a mutable model from
    the Hub. Operators must stage the chosen artifact first and pin its immutable
    commit SHA for production; a cache miss fails rather than opening network access.
    """
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError as exc:
        raise RuntimeError("Install requirements-ai.txt to use the local embedding model") from exc

    normalized_revision = normalize_embedding_revision(revision)
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={
            "device": device,
            "local_files_only": True,
            **({"revision": normalized_revision} if normalized_revision else {}),
        },
        encode_kwargs={"normalize_embeddings": True},
    )

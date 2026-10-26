from __future__ import annotations

import json
import math
import sqlite3
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

INDEX_FILENAME = "local_vectors.sqlite3"


@dataclass(frozen=True)
class LocalDocument:
    """Document-compatible record used when LangChain is not installed."""

    page_content: str
    metadata: dict[str, Any]


class LocalSQLiteVectorStore:
    """Persistent cosine-similarity index backed only by local SQLite."""

    def __init__(self, persist_directory: str | Path, collection_name: str, embedding_function: Any, *, embedding_id: str | None = None) -> None:
        self.persist_directory = Path(persist_directory)
        self.db_path = self.persist_directory / INDEX_FILENAME
        self.collection_name = str(collection_name).strip()
        if not self.collection_name:
            raise ValueError("collection_name is required")
        self.embedding_function = embedding_function
        self.embedding_id = str(
            embedding_id
            or getattr(embedding_function, "model_name", "")
            or f"{type(embedding_function).__module__}.{type(embedding_function).__qualname__}"
        )
        if not self.embedding_id.strip():
            raise ValueError("embedding_id is required")
        self._ensure_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.db_path), timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS vector_collections (
                    collection_name TEXT PRIMARY KEY,
                    embedding_id TEXT NOT NULL,
                    dimensions INTEGER NOT NULL CHECK (dimensions > 0)
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS vector_documents (
                    collection_name TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    page_content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    dimensions INTEGER NOT NULL CHECK (dimensions > 0),
                    PRIMARY KEY (collection_name, document_id),
                    FOREIGN KEY (collection_name) REFERENCES vector_collections(collection_name)
                        ON DELETE CASCADE
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_vector_documents_collection ON vector_documents(collection_name)"
            )

    @staticmethod
    def _normalized_vector(values: Sequence[Any]) -> list[float]:
        try:
            vector = [float(value) for value in values]
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Embedding must be a finite numeric vector") from exc
        if not vector or not all(math.isfinite(value) for value in vector):
            raise ValueError("Embedding must be a non-empty finite numeric vector")
        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isfinite(norm) or norm <= 1e-12:
            raise ValueError("Embedding vector must have a non-zero norm")
        return [value / norm for value in vector]

    @staticmethod
    def _pack_vector(vector: Sequence[float]) -> bytes:
        return struct.pack(f"<{len(vector)}f", *vector)

    @staticmethod
    def _unpack_vector(blob: bytes, dimensions: int) -> list[float]:
        if dimensions < 1 or len(blob) != dimensions * 4:
            raise ValueError("Stored embedding has an invalid binary length")
        vector = list(struct.unpack(f"<{dimensions}f", blob))
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("Stored embedding contains a non-finite value")
        return vector

    def add_documents(self, documents: Sequence[Any], ids: Sequence[str]) -> None:
        if len(documents) != len(ids):
            raise ValueError("Each document must have exactly one stable ID")
        if not documents:
            return
        normalized_ids = [str(value).strip() for value in ids]
        if any(not value for value in normalized_ids):
            raise ValueError("Document IDs must be non-empty strings")
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("Document IDs must be unique within a batch")
        texts = [str(document.page_content) for document in documents]
        vectors = self.embedding_function.embed_documents(texts)
        if len(vectors) != len(documents):
            raise ValueError("Embedding provider returned a different number of vectors")
        normalized = [self._normalized_vector(vector) for vector in vectors]
        dimensions = len(normalized[0])
        if any(len(vector) != dimensions for vector in normalized):
            raise ValueError("Embedding provider returned inconsistent dimensions")

        rows: list[tuple[str, str, str, str, bytes, int]] = []
        for document, document_id, text, vector in zip(documents, normalized_ids, texts, normalized):
            metadata = getattr(document, "metadata", {})
            if not isinstance(metadata, dict):
                raise ValueError("Document metadata must be an object")
            metadata_json = json.dumps(
                metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                allow_nan=False, default=str,
            )
            rows.append((
                self.collection_name, document_id, text, metadata_json,
                self._pack_vector(vector), dimensions,
            ))

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            collection = connection.execute(
                "SELECT embedding_id, dimensions FROM vector_collections WHERE collection_name=?",
                (self.collection_name,),
            ).fetchone()
            if collection is None:
                connection.execute(
                    "INSERT INTO vector_collections(collection_name, embedding_id, dimensions) VALUES (?, ?, ?)",
                    (self.collection_name, self.embedding_id, dimensions),
                )
            elif collection["embedding_id"] != self.embedding_id or collection["dimensions"] != dimensions:
                raise ValueError(
                    "Embedding model or dimensions changed for this collection; "
                    "use a new index directory or re-ingest into an empty index"
                )
            connection.executemany(
                """INSERT INTO vector_documents(
                    collection_name, document_id, page_content, metadata_json, embedding, dimensions
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(collection_name, document_id) DO UPDATE SET
                    page_content=excluded.page_content,
                    metadata_json=excluded.metadata_json,
                    embedding=excluded.embedding,
                    dimensions=excluded.dimensions""",
                rows,
            )

    def get(self, *, include: Sequence[str] | None = None) -> dict[str, Any]:
        fields = set(include or ("documents", "metadatas", "embeddings"))
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT document_id, page_content, metadata_json, embedding, dimensions
                FROM vector_documents WHERE collection_name=? ORDER BY document_id""",
                (self.collection_name,),
            ).fetchall()
        result: dict[str, Any] = {"ids": [row["document_id"] for row in rows]}
        if "documents" in fields:
            result["documents"] = [row["page_content"] for row in rows]
        if "metadatas" in fields:
            result["metadatas"] = [json.loads(row["metadata_json"]) for row in rows]
        if "embeddings" in fields:
            result["embeddings"] = [self._unpack_vector(row["embedding"], row["dimensions"]) for row in rows]
        return result

    def delete(self, *, ids: Sequence[str]) -> None:
        if not ids:
            return
        with self._connection() as connection:
            connection.executemany(
                "DELETE FROM vector_documents WHERE collection_name=? AND document_id=?",
                [(self.collection_name, str(document_id)) for document_id in ids],
            )

    def count(self) -> int:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM vector_documents WHERE collection_name=?",
                (self.collection_name,),
            ).fetchone()
        return int(row["total"])

    def similarity_search(self, query: str, *, k: int = 4) -> list[Any]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Vector search query cannot be empty")
        if k < 1:
            return []
        query_vector = self._normalized_vector(self.embedding_function.embed_query(query))
        with self._connection() as connection:
            collection = connection.execute(
                "SELECT embedding_id, dimensions FROM vector_collections WHERE collection_name=?",
                (self.collection_name,),
            ).fetchone()
            if collection is None:
                return []
            if collection["embedding_id"] != self.embedding_id:
                raise ValueError("Configured embedding model does not match the persisted vector index")
            if collection["dimensions"] != len(query_vector):
                raise ValueError("Query embedding dimensions do not match the persisted vector index")
            rows = connection.execute(
                """SELECT document_id, page_content, metadata_json, embedding, dimensions
                FROM vector_documents WHERE collection_name=?""",
                (self.collection_name,),
            ).fetchall()

        ranked: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            vector = self._unpack_vector(row["embedding"], row["dimensions"])
            if len(vector) != len(query_vector):
                raise ValueError("Stored embedding dimensions are inconsistent")
            score = sum(left * right for left, right in zip(query_vector, vector))
            ranked.append((score, row))
        ranked.sort(key=lambda item: (-item[0], item[1]["document_id"]))
        return [self._make_document(row["page_content"], json.loads(row["metadata_json"])) for _, row in ranked[:k]]

    @staticmethod
    def _make_document(page_content: str, metadata: dict[str, Any]) -> Any:
        try:
            from langchain_core.documents import Document
        except ImportError:
            return LocalDocument(page_content=page_content, metadata=metadata)
        return Document(page_content=page_content, metadata=metadata)

    def as_retriever(self, *, search_kwargs: dict[str, Any] | None = None) -> Any:
        try:
            from langchain_core.retrievers import BaseRetriever
            from pydantic import ConfigDict
        except ImportError as exc:
            raise RuntimeError("Install the optional AI profile to create a RAG retriever") from exc
        options = dict(search_kwargs or {})
        result_count = max(1, min(int(options.get("k", 6)), 12))
        store = self

        class LocalSQLiteRetriever(BaseRetriever):
            model_config = ConfigDict(arbitrary_types_allowed=True)
            vector_store: Any
            result_count: int = 6

            def _get_relevant_documents(self, query: str, *, run_manager: Any) -> list[Any]:
                return self.vector_store.similarity_search(query, k=self.result_count)

        return LocalSQLiteRetriever(vector_store=store, result_count=result_count)

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_memory.local_vector_store import INDEX_FILENAME, LocalSQLiteVectorStore


class FakeEmbeddings:
    model_name = "fake-embedding-v1"

    @staticmethod
    def _vector(text: str) -> list[float]:
        lowered = text.lower()
        return [float("apple" in lowered), float("banana" in lowered), float("citrus" in lowered), 0.05]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def _store(tmp_path, *, collection="affiliate_doctrine", embedding_id="fake-embedding-v1"):
    return LocalSQLiteVectorStore(
        persist_directory=tmp_path,
        collection_name=collection,
        embedding_function=FakeEmbeddings(),
        embedding_id=embedding_id,
    )


def test_sqlite_store_persists_vectors_and_returns_cosine_ranked_documents(tmp_path):
    store = _store(tmp_path)
    docs = [
        SimpleNamespace(page_content="Apple affiliate offer framework", metadata={"source": "offer-frameworks.md", "kind": "reference"}),
        SimpleNamespace(page_content="Banana platform policy", metadata={"source": "platform-rules.md", "kind": "reference"}),
        SimpleNamespace(page_content="Apple and citrus SEO strategy", metadata={"source": "seo-strategy.md", "kind": "reference"}),
    ]
    store.add_documents(docs, ids=["apple-1", "banana-1", "apple-citrus-1"])

    assert store.db_path.name == INDEX_FILENAME
    assert store.db_path.is_file()
    assert store.count() == 3
    assert store.get(include=["metadatas"])["ids"] == ["apple-1", "apple-citrus-1", "banana-1"]
    ranked = store.similarity_search("apple", k=2)
    assert len(ranked) == 2
    assert ranked[0].page_content == "Apple affiliate offer framework"
    assert ranked[0].metadata["source"] == "offer-frameworks.md"
    assert ranked[1].page_content == "Apple and citrus SEO strategy"

    reopened = _store(tmp_path)
    assert reopened.count() == 3
    assert reopened.similarity_search("banana", k=1)[0].metadata["source"] == "platform-rules.md"


def test_sqlite_store_upserts_stable_ids_and_removes_stale_chunks(tmp_path):
    store = _store(tmp_path)
    store.add_documents(
        [SimpleNamespace(page_content="old apple document", metadata={"source": "old.md", "document_kind": "reference"})],
        ids=["stable-id"],
    )
    store.add_documents(
        [SimpleNamespace(page_content="new banana document", metadata={"source": "new.md", "document_kind": "reference"})],
        ids=["stable-id"],
    )
    assert store.count() == 1
    row = store.get(include=["documents", "metadatas"])
    assert row["documents"] == ["new banana document"]
    assert row["metadatas"] == [{"document_kind": "reference", "source": "new.md"}]
    store.delete(ids=["stable-id"])
    assert store.count() == 0
    assert store.get(include=["metadatas"]) == {"ids": [], "metadatas": []}


def test_sqlite_store_isolates_collections_and_rejects_embedding_model_changes(tmp_path):
    first = _store(tmp_path, collection="tenant-a")
    second = _store(tmp_path, collection="tenant-b")
    first.add_documents([SimpleNamespace(page_content="apple only", metadata={"workspace": "a"})], ids=["same-id"])
    second.add_documents([SimpleNamespace(page_content="banana only", metadata={"workspace": "b"})], ids=["same-id"])
    assert first.count() == second.count() == 1
    assert first.similarity_search("apple", k=1)[0].metadata["workspace"] == "a"
    assert second.similarity_search("banana", k=1)[0].metadata["workspace"] == "b"

    incompatible = _store(tmp_path, collection="tenant-a", embedding_id="different-model")
    with pytest.raises(ValueError, match="Embedding model or dimensions changed"):
        incompatible.add_documents([SimpleNamespace(page_content="citrus", metadata={})], ids=["another-id"])


def test_sqlite_store_rejects_non_finite_or_zero_embeddings(tmp_path):
    store = _store(tmp_path)
    for vector in ([], [0.0, 0.0], [float("nan"), 1.0], [float("inf"), 1.0]):
        with pytest.raises(ValueError, match="Embedding"):
            store._normalized_vector(vector)


def test_sqlite_store_rejects_empty_queries(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="query cannot be empty"):
        store.similarity_search("   ")

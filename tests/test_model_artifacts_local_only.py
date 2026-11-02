from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

import pytest
from pydantic import ValidationError

from ai_memory.model_artifacts import (
    build_local_embeddings,
    embedding_identity,
    normalize_embedding_revision,
)
from backend.config import Settings


REVISION = "ab" * 20


def test_embedding_builder_forces_local_files_only_and_pins_revision(monkeypatch):
    captured: dict[str, Any] = {}

    class FakeEmbeddings:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_module = ModuleType("langchain_huggingface")
    fake_module.HuggingFaceEmbeddings = FakeEmbeddings
    monkeypatch.setitem(sys.modules, "langchain_huggingface", fake_module)

    instance = build_local_embeddings("sentence-transformers/example", device="cpu", revision=REVISION.upper())

    assert isinstance(instance, FakeEmbeddings)
    assert captured == {
        "model_name": "sentence-transformers/example",
        "model_kwargs": {
            "device": "cpu",
            "local_files_only": True,
            "revision": REVISION,
        },
        "encode_kwargs": {"normalize_embeddings": True},
    }


def test_embedding_revision_rejects_mutable_tags_and_short_values():
    for revision in ("main", "latest", "abc123", "../model", "g" * 40):
        with pytest.raises(ValueError, match="40-character immutable"):
            normalize_embedding_revision(revision)


def test_embedding_identity_changes_when_revision_changes():
    model = "sentence-transformers/example"
    assert embedding_identity(model) == model
    assert embedding_identity(model, REVISION) == f"{model}@{REVISION}"
    with pytest.raises(ValueError):
        embedding_identity(model, "main")


def _production_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "production",
        "app_public_url": "https://app.example.test",
        "app_session_secret": "s" * 48,
        "api_access_token": "a" * 48,
        "tracking_hmac_secret": "t" * 48,
        "affiliate_webhook_secret": "w" * 48,
        "database_url": "postgresql+asyncpg://user:password@db.example.test/omni",
        "initial_admin_email": "admin@example.test",
        "initial_admin_password": "strong-test-password-123",
        "llm_backend": "openai_compatible",
        "openai_api_key": "test-only-not-a-real-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_requires_immutable_revision_for_hub_embedding_model():
    with pytest.raises(ValidationError, match="EMBEDDING_MODEL_REVISION"):
        _production_settings()


def test_production_accepts_valid_pinned_embedding_revision():
    settings = _production_settings(embedding_model_revision=REVISION)
    assert settings.embedding_model_revision == REVISION

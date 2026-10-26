from __future__ import annotations

from scripts.verify_outbound_transport_boundary import (
    APPROVED_TRANSPORT,
    find_transport_violations,
)


def test_direct_async_httpx_client_is_rejected():
    source = "import httpx as transport\nasync def fetch():\n    async with transport.AsyncClient() as client:\n        return await client.get('https://provider.example')\n"
    errors = find_transport_violations(source, "backend/services/provider.py")
    assert len(errors) == 1
    assert "httpx.AsyncClient" in errors[0]
    assert errors[0].startswith("backend/services/provider.py:3:")


def test_requests_aiohttp_and_urllib_aliases_are_rejected():
    source = (
        "import requests as provider\n"
        "from urllib.request import urlopen as open_url\n"
        "from aiohttp import ClientSession as Session\n"
        "def fetch():\n"
        "    provider.post('https://provider.example')\n"
        "    open_url('https://provider.example')\n"
        "async def async_fetch():\n"
        "    async with Session() as session:\n"
        "        return await session.get('https://provider.example')\n"
    )
    errors = find_transport_violations(source, "backend/services/unreviewed_provider.py")
    assert len(errors) == 3
    assert any("requests.post" in error for error in errors)
    assert any("urllib.request.urlopen" in error for error in errors)
    assert any("aiohttp.ClientSession" in error for error in errors)


def test_httpx_convenience_calls_and_urllib3_pool_are_rejected():
    source = (
        "import httpx\n"
        "import urllib3 as pools\n"
        "def fetch():\n"
        "    httpx.get('https://provider.example')\n"
        "    pools.PoolManager()\n"
    )
    errors = find_transport_violations(source, "ai_memory/unreviewed_provider.py")
    assert len(errors) == 2
    assert any("httpx.get" in error for error in errors)
    assert any("urllib3.PoolManager" in error for error in errors)


def test_approved_transport_is_the_only_documented_exception():
    source = "import httpx\nclient = httpx.AsyncClient()\n"
    assert find_transport_violations(source, APPROVED_TRANSPORT) == []


def test_project_transport_call_through_helper_is_allowed():
    source = (
        "from backend.services.url_safety import request_public_json\n"
        "async def fetch():\n"
        "    return await request_public_json('https://provider.example/api')\n"
    )
    assert find_transport_violations(source, "backend/services/provider.py") == []


def test_syntax_errors_fail_closed():
    errors = find_transport_violations("async def broken(:\n pass\n", "backend/services/broken.py")
    assert len(errors) == 1
    assert "cannot parse source" in errors[0]


def test_langchain_openai_sdk_requires_both_pinned_clients():
    source = (
        "from langchain_openai import ChatOpenAI as Model\n"
        "model = Model(model='test-model', api_key='fake-test-key', "
        "http_async_client=safe_async_client)\n"
    )
    errors = find_transport_violations(source, "backend/services/unreviewed_llm.py")
    assert len(errors) == 1
    assert "ChatOpenAI" in errors[0]
    assert "http_client" in errors[0]


def test_langchain_openai_sdk_with_both_pinned_clients_is_allowed():
    source = (
        "from langchain_openai import ChatOpenAI\n"
        "from backend.services.url_safety import pinned_public_client, pinned_public_async_client\n"
        "async def build():\n"
        "    with pinned_public_client() as sync_client:\n"
        "        async with pinned_public_async_client() as async_client:\n"
        "            return ChatOpenAI(model='test-model', api_key='fake-test-key', "
        "http_client=sync_client, http_async_client=async_client)\n"
    )
    assert find_transport_violations(source, "backend/services/llm.py") == []


def test_transformer_model_loaders_require_local_files_only():
    source = (
        "from transformers import AutoTokenizer as Tokenizer\\n"
        "tokenizer = Tokenizer.from_pretrained('model/repo')\\n"
    )
    errors = find_transport_violations(source, "backend/services/unreviewed_model.py")
    assert len(errors) == 1
    assert "local_files_only=True" in errors[0]


def test_transformer_model_loaders_accept_local_files_only_alias():
    source = (
        "from transformers import AutoTokenizer as Tokenizer\\n"
        "tokenizer = Tokenizer.from_pretrained('model/repo', local_files_only=True)\\n"
    )
    assert find_transport_violations(source, "backend/services/local_model.py") == []


def test_embedding_sdk_requires_local_files_only_in_model_kwargs():
    source = (
        "from langchain_huggingface import HuggingFaceEmbeddings\\n"
        "embedding = HuggingFaceEmbeddings(model_name='model/repo', "
        "model_kwargs={'device': 'cpu'})\\n"
    )
    errors = find_transport_violations(source, "ai_memory/unreviewed_embeddings.py")
    assert len(errors) == 1
    assert "local_files_only" in errors[0]


def test_embedding_sdk_accepts_local_files_only_in_model_kwargs():
    source = (
        "from langchain_huggingface import HuggingFaceEmbeddings\\n"
        "embedding = HuggingFaceEmbeddings(model_name='model/repo', "
        "model_kwargs={'device': 'cpu', 'local_files_only': True})\\n"
    )
    assert find_transport_violations(source, "ai_memory/model_artifacts.py") == []

from __future__ import annotations

import base64
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from backend.config import Settings
from backend.services import github_pages_deployer as deployer


def _settings(**overrides):
    values = {
        "github_pages_deploy_execute": True,
        "github_pages_repository": "ExampleOrg/creator-site",
        "github_pages_branch": "gh-pages",
        "github_pages_directory": "resources/links",
        "github_pages_token": "github_test_token_with_sufficient_length_12345",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _FakeResponse:
    def __init__(self, status_code, payload, url):
        self.status_code = status_code
        self._payload = payload
        self.request = httpx.Request("GET", url)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request, json=self._payload)
            raise httpx.HTTPStatusError("simulated GitHub response", request=self.request, response=response)


class _FakeGitHubClient:
    def __init__(self, *, existing_html=None, pages_branch="gh-pages", pages_path="/"):
        self.existing_html = existing_html
        self.pages_branch = pages_branch
        self.pages_path = pages_path
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if url.endswith("/pages"):
            return _FakeResponse(200, {
                "html_url": "https://exampleorg.github.io/creator-site/",
                "source": {"branch": self.pages_branch, "path": self.pages_path},
            }, url)
        if "/contents/" in url:
            if self.existing_html is None:
                return _FakeResponse(404, {"message": "Not Found"}, url)
            return _FakeResponse(200, {
                "type": "file", "encoding": "base64",
                "content": base64.b64encode(self.existing_html.encode("utf-8")).decode("ascii"),
                "sha": "old-blob-sha", "path": "resources/links/index.html",
            }, url)
        raise AssertionError(f"Unexpected GET URL: {url}")

    async def put(self, url, **kwargs):
        self.calls.append(("PUT", url, kwargs))
        return _FakeResponse(200, {
            "content": {"path": "resources/links/index.html", "sha": "new-blob-sha"},
            "commit": {"sha": "new-commit-sha", "html_url": "https://github.com/exampleorg/creator-site/commit/new-commit-sha"},
        }, url)


class _FakeClientContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, *_):
        return False


def test_readiness_reports_configuration_without_claiming_remote_connection():
    status = deployer.github_pages_readiness(_settings())
    assert status["configuration_ready"] is True
    assert status["publish_ready"] is True
    assert status["repository"] == "exampleorg/creator-site"
    assert status["branch"] == "gh-pages"
    assert status["provider_connection_verified"] is False
    assert status["site_source_verified"] is False
    assert "github_test_token" not in str(status)


@pytest.mark.parametrize("repository", [
    "https://github.com/owner/repo",
    "owner/repo/extra",
    "../repo",
    "owner/../repo",
    "owner/repo.git",
])
def test_repository_must_be_a_fixed_owner_repo_identifier(repository):
    with pytest.raises(deployer.GitHubPagesConfigurationError):
        deployer.validate_repository_name(repository)


@pytest.mark.parametrize("branch", [
    "../main",
    "/gh-pages",
    "gh-pages/",
    "bad//branch",
    "release/../main",
    "bad branch",
    "folder/.hidden",
])
def test_branch_ref_rejects_traversal_and_invalid_git_ref_components(branch):
    with pytest.raises(deployer.GitHubPagesConfigurationError):
        deployer.validate_branch_name(branch)


@pytest.mark.parametrize("directory", [
    "../repo",
    "/root",
    "foo//bar",
    "foo/../bar",
    "foo\\bar",
    "docs/",
])
def test_directory_must_be_a_safe_relative_path(directory):
    with pytest.raises(deployer.GitHubPagesConfigurationError):
        deployer.validate_directory(directory)


def test_settings_rejects_deploy_enabled_without_fixed_target_and_token():
    with pytest.raises(ValidationError, match="GITHUB_PAGES_DEPLOY_EXECUTE=true"):
        Settings(github_pages_deploy_execute=True)


@pytest.mark.asyncio
async def test_deployer_checks_pages_source_and_writes_only_configured_contents_target(monkeypatch):
    client = _FakeGitHubClient()
    monkeypatch.setattr(deployer, "pinned_public_async_client", lambda timeout=20.0: _FakeClientContext(client))
    html = "<!doctype html><html><body><h1>Generated safe page</h1></body></html>"
    result = await deployer.deploy_github_pages_html(
        html_content=html, title="Creator links", asset_id="asset-123456", settings=_settings()
    )
    assert result["status"] == "published"
    assert result["repository"] == "exampleorg/creator-site"
    assert result["branch"] == "gh-pages"
    assert result["content_path"] == "resources/links/index.html"
    assert result["published_url"] == "https://exampleorg.github.io/creator-site/resources/links/"
    assert result["commit_sha"] == "new-commit-sha"
    assert len([call for call in client.calls if call[0] == "PUT"]) == 1
    put = next(call for call in client.calls if call[0] == "PUT")
    assert put[2]["headers"]["Authorization"] == "Bearer " + _settings().github_pages_token
    assert "github_test_token" not in str(result)
    payload = put[2]["json"]
    assert payload["branch"] == "gh-pages"
    assert "sha" not in payload


@pytest.mark.asyncio
async def test_deployer_is_idempotent_at_content_level_when_remote_html_already_matches(monkeypatch):
    html = "<!doctype html><html><body><h1>Already deployed</h1></body></html>"
    client = _FakeGitHubClient(existing_html=html)
    monkeypatch.setattr(deployer, "pinned_public_async_client", lambda timeout=20.0: _FakeClientContext(client))
    result = await deployer.deploy_github_pages_html(
        html_content=html, title="Existing page", asset_id="asset-123456", settings=_settings()
    )
    assert result["status"] == "unchanged"
    assert result["file_sha"] == "old-blob-sha"
    assert not any(call[0] == "PUT" for call in client.calls)


@pytest.mark.asyncio
async def test_deployer_refuses_a_mismatched_pages_source_branch_before_writing(monkeypatch):
    client = _FakeGitHubClient(pages_branch="main")
    monkeypatch.setattr(deployer, "pinned_public_async_client", lambda timeout=20.0: _FakeClientContext(client))
    with pytest.raises(deployer.GitHubPagesConfigurationError, match="source branch"):
        await deployer.deploy_github_pages_html(
            html_content="<html><body>safe</body></html>", title="Page", asset_id="asset-123456", settings=_settings()
        )
    assert not any(call[0] == "PUT" for call in client.calls)


@pytest.mark.asyncio
async def test_reconciliation_only_reports_match_for_exact_remote_content(monkeypatch):
    html = "<!doctype html><html><body><h1>Deployed page</h1></body></html>"
    client = _FakeGitHubClient(existing_html=html)
    monkeypatch.setattr(deployer, "pinned_public_async_client", lambda timeout=20.0: _FakeClientContext(client))
    result = await deployer.verify_github_pages_html(html_content=html, settings=_settings(github_pages_deploy_execute=False))
    assert result["matches_expected_content"] is True
    assert result["file_exists"] is True
    assert not any(call[0] == "PUT" for call in client.calls)

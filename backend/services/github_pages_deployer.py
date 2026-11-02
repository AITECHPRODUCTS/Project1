from __future__ import annotations

import base64
import hashlib
import re
from typing import Any
from urllib.parse import quote, urlsplit

from backend.services.url_safety import pinned_public_async_client


_GITHUB_API = "https://api.github.com"
_GITHUB_API_VERSION = "2022-11-28"
_MAX_PAGE_BYTES = 2_000_000


class GitHubPagesConfigurationError(ValueError):
    """The configured repository, Pages source, or token is not ready for deployment."""


def validate_repository_name(value: str) -> str:
    repository = str(value or "").strip()
    if not re.fullmatch(
        r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,98}[A-Za-z0-9])?/[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?",
        repository,
    ):
        raise GitHubPagesConfigurationError(
            "Configure GITHUB_PAGES_REPOSITORY as a fixed owner/repository name, not a URL."
        )
    owner, name = repository.split("/", 1)
    if owner in {".", ".."} or name in {".", ".."} or name.endswith(".git"):
        raise GitHubPagesConfigurationError("The configured GitHub Pages repository identifier is invalid.")
    return f"{owner.lower()}/{name.lower()}"


def validate_branch_name(value: str) -> str:
    branch = str(value or "").strip()
    if not branch or len(branch) > 255 or not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
        raise GitHubPagesConfigurationError("Configure a valid Git branch in GITHUB_PAGES_BRANCH.")
    parts = branch.split("/")
    if (
        branch.startswith("/") or branch.endswith("/") or "//" in branch or "@{" in branch
        or any(
            part in {"", ".", ".."} or part.startswith(".") or part.endswith(".") or part.endswith(".lock")
            for part in parts
        )
    ):
        raise GitHubPagesConfigurationError("GITHUB_PAGES_BRANCH contains a forbidden Git ref component.")
    return branch


def validate_directory(value: str) -> str:
    directory = str(value or "").strip()
    if not directory:
        return ""
    if (
        len(directory) > 300 or directory.startswith("/") or directory.endswith("/")
        or "\\" in directory or not re.fullmatch(r"[A-Za-z0-9._/-]+", directory)
        or any(part in {"", ".", ".."} for part in directory.split("/"))
    ):
        raise GitHubPagesConfigurationError(
            "GITHUB_PAGES_DIRECTORY must be a safe relative path without traversal segments."
        )
    return directory


def github_pages_readiness(settings: Any) -> dict[str, Any]:
    raw_repository = str(getattr(settings, "github_pages_repository", "") or "").strip()
    raw_token = str(getattr(settings, "github_pages_token", "") or "").strip()
    enabled = bool(getattr(settings, "github_pages_deploy_execute", False))
    branch = str(getattr(settings, "github_pages_branch", "gh-pages") or "gh-pages")
    directory = str(getattr(settings, "github_pages_directory", "") or "")
    try:
        repository = validate_repository_name(raw_repository) if raw_repository else None
        branch = validate_branch_name(branch)
        directory = validate_directory(directory)
        target_valid = repository is not None
    except GitHubPagesConfigurationError:
        repository = None
        target_valid = False
    credentials_ready = bool(raw_token and len(raw_token) >= 20)
    return {
        "provider": "github_pages",
        "configuration_ready": bool(target_valid and credentials_ready),
        "publish_ready": bool(target_valid and credentials_ready and enabled),
        "deployment_enabled": enabled,
        "repository": repository,
        "branch": branch if target_valid else None,
        "directory": directory if target_valid else None,
        "token_configured": credentials_ready,
        "provider_connection_verified": False,
        "site_source_verified": False,
        "message": (
            "Configuration is present but remote access is not yet verified. A deployment checks the GitHub token, "
            "Pages branch source, and destination file through the fixed GitHub API."
            if target_valid and credentials_ready and enabled else
            "GitHub Pages deployment is disabled or missing a valid target/token. Configure the fixed repository, "
            "branch, optional relative directory, a scoped token, and GITHUB_PAGES_DEPLOY_EXECUTE=true."
        ),
    }


def _configuration(settings: Any, *, require_execution: bool) -> tuple[str, str, str, str]:
    repository = validate_repository_name(str(getattr(settings, "github_pages_repository", "") or ""))
    branch = validate_branch_name(str(getattr(settings, "github_pages_branch", "gh-pages") or "gh-pages"))
    directory = validate_directory(str(getattr(settings, "github_pages_directory", "") or ""))
    token = str(getattr(settings, "github_pages_token", "") or "").strip()
    if len(token) < 20:
        raise GitHubPagesConfigurationError("A scoped GITHUB_PAGES_TOKEN is required.")
    if require_execution and not bool(getattr(settings, "github_pages_deploy_execute", False)):
        raise GitHubPagesConfigurationError("GitHub Pages live deployment is disabled by GITHUB_PAGES_DEPLOY_EXECUTE.")
    return repository, branch, directory, token


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": _GITHUB_API_VERSION,
        "User-Agent": "OmniAffiliateOS-GitHub-Pages-Deployer",
    }


async def _pages_target(client: Any, repository: str, branch: str, directory: str, headers: dict[str, str]) -> dict[str, str]:
    url = f"{_GITHUB_API}/repos/{repository}/pages"
    response = await client.get(url, headers=headers)
    if response.status_code == 404:
        raise GitHubPagesConfigurationError(
            "GitHub Pages is not configured for the fixed target repository; configure branch-based Pages publishing first."
        )
    response.raise_for_status()
    page = response.json()
    if not isinstance(page, dict):
        raise GitHubPagesConfigurationError("GitHub returned an invalid Pages configuration response.")
    source = page.get("source")
    if not isinstance(source, dict) or str(source.get("branch") or "") != branch:
        raise GitHubPagesConfigurationError(
            "The target repository's GitHub Pages source branch does not match GITHUB_PAGES_BRANCH."
        )
    source_directory = str(source.get("path") or "/").strip("/")
    if source_directory not in {"", "docs"}:
        raise GitHubPagesConfigurationError("Only the repository root or docs/ Pages source is supported.")
    site_url = str(page.get("html_url") or "").strip()
    parsed = urlsplit(site_url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise GitHubPagesConfigurationError("GitHub Pages did not report a valid HTTPS site URL.")
    file_parts = [part for part in (source_directory, directory) if part]
    content_path = "/".join([*file_parts, "index.html"])
    public_url = site_url.rstrip("/") + ("/" + quote(directory, safe="/-._~") if directory else "") + "/"
    return {
        "repository": repository,
        "branch": branch,
        "directory": directory,
        "source_directory": source_directory,
        "content_path": content_path,
        "site_url": site_url,
        "published_url": public_url,
    }


async def _read_remote_file(client: Any, target: dict[str, str], headers: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    encoded_path = quote(target["content_path"], safe="/")
    url = f"{_GITHUB_API}/repos/{target['repository']}/contents/{encoded_path}"
    response = await client.get(url, headers=headers, params={"ref": target["branch"]})
    if response.status_code == 404:
        return None, None
    response.raise_for_status()
    item = response.json()
    if not isinstance(item, dict) or item.get("type") != "file":
        raise GitHubPagesConfigurationError("The configured GitHub Pages destination is not a regular file.")
    if item.get("encoding") != "base64" or not isinstance(item.get("content"), str):
        raise GitHubPagesConfigurationError("GitHub did not return a base64 file payload for the configured page.")
    try:
        current_html = base64.b64decode("".join(item["content"].split()), validate=False).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise GitHubPagesConfigurationError("The existing GitHub Pages index is not valid UTF-8 content.") from exc
    return item, current_html


async def deploy_github_pages_html(
    *,
    html_content: str,
    title: str,
    asset_id: str,
    settings: Any,
) -> dict[str, Any]:
    """Replace a single generated index.html on a server-configured branch-based Pages site.

    The API origin and repository come from server configuration, not request data.
    A read-before-write avoids commits when the deployed HTML already matches; the
    Contents API SHA provides optimistic concurrency control for an existing file.
    """
    repository, branch, directory, token = _configuration(settings, require_execution=True)
    content_bytes = str(html_content).encode("utf-8")
    if not content_bytes or len(content_bytes) > _MAX_PAGE_BYTES:
        raise GitHubPagesConfigurationError("Generated page content must be between 1 byte and 2 MB.")
    checksum = hashlib.sha256(content_bytes).hexdigest()
    headers = _headers(token)
    async with pinned_public_async_client(timeout=20.0) as client:
        target = await _pages_target(client, repository, branch, directory, headers)
        existing, existing_html = await _read_remote_file(client, target, headers)
        if existing is not None and existing_html == html_content:
            return {
                **target,
                "status": "unchanged",
                "page_sha256": checksum,
                "file_sha": existing.get("sha"),
                "commit_sha": None,
            }
        safe_title = " ".join(str(title).split())[:80]
        request_payload: dict[str, Any] = {
            "message": f"OmniAffiliateOS: publish bio-link page {safe_title} ({str(asset_id)[:8]})",
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "branch": branch,
        }
        if existing is not None:
            request_payload["sha"] = existing.get("sha")
        encoded_path = quote(target["content_path"], safe="/")
        response = await client.put(
            f"{_GITHUB_API}/repos/{repository}/contents/{encoded_path}",
            headers=headers,
            json=request_payload,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or not isinstance(result.get("content"), dict):
            raise GitHubPagesConfigurationError("GitHub accepted a request but returned no file record.")
        commit = result.get("commit") if isinstance(result.get("commit"), dict) else {}
        return {
            **target,
            "status": "published",
            "page_sha256": checksum,
            "file_sha": result["content"].get("sha"),
            "commit_sha": commit.get("sha"),
            "commit_url": commit.get("html_url"),
        }


async def verify_github_pages_html(
    *,
    html_content: str,
    settings: Any,
) -> dict[str, Any]:
    """Read-only reconciliation after an ambiguous provider response."""
    repository, branch, directory, token = _configuration(settings, require_execution=False)
    headers = _headers(token)
    async with pinned_public_async_client(timeout=20.0) as client:
        target = await _pages_target(client, repository, branch, directory, headers)
        existing, current_html = await _read_remote_file(client, target, headers)
    expected_sha = hashlib.sha256(str(html_content).encode("utf-8")).hexdigest()
    return {
        **target,
        "matches_expected_content": existing is not None and current_html == html_content,
        "page_sha256": expected_sha,
        "file_sha": existing.get("sha") if existing else None,
        "file_exists": existing is not None,
    }

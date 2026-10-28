from __future__ import annotations
import ipaddress
import os
import re
from uuid import UUID
from functools import lru_cache
from pathlib import Path
from typing import Literal
import yaml
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Omnichannel Affiliate OS"
    app_public_url: str = "http://localhost:8000"
    app_session_secret: str = "development-session-secret-change-me"
    api_access_token: str = ""
    initial_admin_email: str = ""
    initial_admin_password: str = ""
    database_url: str = "sqlite+aiosqlite:///./storage/affiliate_os.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    # Uvicorn forwarded-header trust; loopback-only unless exact proxy IP/CIDRs are known.
    forwarded_allow_ips: str = "127.0.0.1"
    execution_mode: Literal["FULL_AUTONOMOUS", "SEMI_AUTONOMOUS", "MANUAL_OVERRIDE"] = "SEMI_AUTONOMOUS"
    llm_backend: Literal["offline", "openai_compatible", "local_transformers"] = "offline"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str = ""
    local_model_path: str = ""
    local_lora_adapter_path: str = ""
    local_model_device: str = "auto"
    affiliate_skills_dir: str = "./knowledge/affiliate-skills"
    # Legacy field/env name retained for deployment compatibility; stores local_vectors.sqlite3, not ChromaDB.
    chroma_persist_dir: str = "./storage/chroma"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Immutable Hub commit SHA for reproducible production embedding artifacts.
    embedding_model_revision: str = ""
    openaffiliate_base_url: str = "https://openaffiliate.dev/api"
    pexels_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_access_token: str = ""
    reddit_user_agent: str = "AffiliateOS/0.1"
    x_bearer_token: str = ""
    pinterest_access_token: str = ""
    publishing_dry_run: bool = True
    # Enable recipient-confirmed opt-in before any marketing sequence delivery.
    email_double_opt_in_required: bool = False
    video_output_dir: str = "./storage/videos"
    content_max_llm_tokens: int = 2500
    resource_budget_usd_per_day: float = 5.0
    resource_budget_usd_per_niche: float = 1.5
    llm_input_cost_per_million_usd: float = 1.0
    llm_output_cost_per_million_usd: float = 4.0
    local_input_cost_per_million_usd: float = 0.0
    local_output_cost_per_million_usd: float = 0.0
    min_conversions_for_learning: int = 5
    min_hook_conversion_rate: float = 0.03
    ad_automation_execute: bool = False
    cms_publish_execute: bool = False
    tracking_hmac_secret: str = ""
    affiliate_webhook_secret: str = ""
    affiliate_webhook_secrets: dict[str, str] = Field(default_factory=dict)
    # Workspace/platform keyed secrets for an explicitly trusted reporting collector.
    ad_performance_webhook_secrets: dict[str, str] = Field(default_factory=dict)
    mail_imap_host: str = "imap.gmail.com"
    mail_imap_port: int = 993
    mail_imap_user: str = ""
    mail_imap_password: str = ""
    mail_sender_allowlist: str = ""
    resend_api_key: str = ""
    resend_from_email: str = ""
    word_press_site_url: str = ""
    word_press_username: str = ""
    word_press_application_password: str = ""
    ghost_site_url: str = ""
    ghost_admin_api_key: str = ""
    # Branch-based GitHub Pages deployment is off until an explicit target and scoped token are configured.
    github_pages_deploy_execute: bool = False
    github_pages_repository: str = ""
    github_pages_branch: str = "gh-pages"
    github_pages_directory: str = ""
    github_pages_token: str = ""
    config_yaml_path: str = "./config.yaml"

    @field_validator("github_pages_repository", mode="before")
    @classmethod
    def normalize_github_pages_repository(cls, value):
        repository = str(value or "").strip()
        if not repository:
            return ""
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,98}[A-Za-z0-9])?/[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?", repository):
            raise ValueError("GITHUB_PAGES_REPOSITORY must be a fixed owner/repository identifier, not a URL")
        owner, name = repository.split("/", 1)
        if owner in {".", ".."} or name in {".", ".."} or name.endswith(".git"):
            raise ValueError("GITHUB_PAGES_REPOSITORY must be a GitHub owner/repository name")
        return f"{owner.lower()}/{name.lower()}"

    @field_validator("github_pages_branch", mode="before")
    @classmethod
    def validate_github_pages_branch(cls, value):
        branch = str(value or "").strip()
        if not branch or len(branch) > 255 or not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
            raise ValueError("GITHUB_PAGES_BRANCH must be a valid, non-empty branch name")
        segments = branch.split("/")
        if (
            branch.startswith("/") or branch.endswith("/") or "//" in branch or
            any(segment in {"", ".", ".."} or segment.startswith(".") or segment.endswith(".") or segment.endswith(".lock") for segment in segments) or
            "@{" in branch
        ):
            raise ValueError("GITHUB_PAGES_BRANCH contains a forbidden Git ref component")
        return branch

    @field_validator("github_pages_directory", mode="before")
    @classmethod
    def validate_github_pages_directory(cls, value):
        directory = str(value or "").strip()
        if not directory:
            return ""
        if (
            len(directory) > 300 or directory.startswith("/") or directory.endswith("/") or
            "\\" in directory or not re.fullmatch(r"[A-Za-z0-9._/-]+", directory) or
            any(part in {"", ".", ".."} for part in directory.split("/"))
        ):
            raise ValueError("GITHUB_PAGES_DIRECTORY must be a safe relative path without traversal segments")
        return directory

    @model_validator(mode="after")
    def github_pages_execution_configuration(self):
        if self.github_pages_deploy_execute and (
            not self.github_pages_repository or len(self.github_pages_token.strip()) < 20
        ):
            raise ValueError(
                "GITHUB_PAGES_DEPLOY_EXECUTE=true requires a fixed GITHUB_PAGES_REPOSITORY and scoped GITHUB_PAGES_TOKEN"
            )
        return self

    @field_validator("forwarded_allow_ips", mode="before")
    @classmethod
    def validate_forwarded_allow_ips(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("FORWARDED_ALLOW_IPS must list exact proxy IP addresses or CIDRs")
        entries = [part.strip() for part in value.split(",") if part.strip()]
        if not entries:
            raise ValueError("FORWARDED_ALLOW_IPS must not be empty")
        for entry in entries:
            if entry == "*":
                raise ValueError("FORWARDED_ALLOW_IPS='*' is forbidden; trust only exact proxy IPs/CIDRs")
            try:
                network = ipaddress.ip_network(entry, strict=False)
            except ValueError as exc:
                raise ValueError("FORWARDED_ALLOW_IPS accepts IP addresses/CIDRs only, not hostnames") from exc
            if network.prefixlen == 0:
                raise ValueError("FORWARDED_ALLOW_IPS must not trust the default route")
        return ",".join(entries)

    @field_validator("embedding_model_revision", mode="before")
    @classmethod
    def validate_embedding_model_revision(cls, value):
        if value is None or not str(value).strip():
            return ""
        revision = str(value).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("EMBEDDING_MODEL_REVISION must be a 40-character immutable model commit SHA")
        return revision

    @field_validator("affiliate_webhook_secrets", mode="before")
    @classmethod
    def normalize_affiliate_webhook_secrets(cls, value):
        if value is None or value == "":
            return {}
        if not isinstance(value, dict):
            raise ValueError("AFFILIATE_WEBHOOK_SECRETS must be a JSON object mapping network names to secrets")
        normalized: dict[str, str] = {}
        for raw_network, raw_secret in value.items():
            network = str(raw_network).strip().lower()
            if not network or len(network) > 100:
                raise ValueError("Affiliate webhook network keys must contain 1-100 characters")
            if network in normalized:
                raise ValueError("Affiliate webhook network keys must be unique after normalization")
            if not isinstance(raw_secret, str) or len(raw_secret) < 32:
                raise ValueError("Each per-network affiliate webhook secret must contain at least 32 characters")
            normalized[network] = raw_secret
        return normalized


    @field_validator("ad_performance_webhook_secrets", mode="before")
    @classmethod
    def normalize_ad_performance_webhook_secrets(cls, value):
        if value is None or value == "":
            return {}
        if not isinstance(value, dict):
            raise ValueError("AD_PERFORMANCE_WEBHOOK_SECRETS must be a JSON object keyed by '<workspace UUID>:<platform>'")
        platforms = {
            "google_search", "google_display", "meta", "instagram", "tiktok", "youtube_shorts",
            "pinterest", "reddit", "quora", "x", "linkedin", "snapchat", "native",
        }
        normalized: dict[str, str] = {}
        for raw_key, raw_secret in value.items():
            parts = str(raw_key).strip().lower().split(":")
            if len(parts) != 2 or parts[1] not in platforms:
                raise ValueError("Ad webhook keys must be '<workspace UUID>:<supported platform>'")
            try:
                workspace_id = str(UUID(parts[0]))
            except (ValueError, AttributeError) as exc:
                raise ValueError("Ad webhook keys must contain a valid workspace UUID") from exc
            key = f"{workspace_id}:{parts[1]}"
            if key in normalized:
                raise ValueError("Ad webhook keys must be unique after normalization")
            if not isinstance(raw_secret, str) or len(raw_secret) < 32:
                raise ValueError("Each workspace/platform ad webhook secret must contain at least 32 characters")
            normalized[key] = raw_secret
        return normalized

    @model_validator(mode="after")
    def production_safety(self):
        if self.app_env == "production":
            if len(self.api_access_token) < 32 or len(self.app_session_secret) < 32 or self.app_session_secret == "development-session-secret-change-me":
                raise ValueError("Production requires fresh 32+ character API_ACCESS_TOKEN and APP_SESSION_SECRET; development defaults are forbidden")
            if len(self.tracking_hmac_secret) < 32 or (not self.affiliate_webhook_secrets and len(self.affiliate_webhook_secret) < 32):
                raise ValueError("Production requires a fresh 32+ character tracking secret and either a shared or per-network 32+ character affiliate webhook secret")
            if not self.app_public_url.startswith("https://"):
                raise ValueError("Production APP_PUBLIC_URL must use HTTPS")
            if self.database_url.startswith("sqlite"):
                raise ValueError("Use PostgreSQL for production")
            if not self.initial_admin_email or len(self.initial_admin_password) < 14:
                raise ValueError("Production requires INITIAL_ADMIN_EMAIL and a 14+ character INITIAL_ADMIN_PASSWORD")
            if self.llm_backend == "offline":
                raise ValueError("Production cannot use offline-only drafts")
            if self.llm_backend == "openai_compatible" and not self.openai_api_key:
                raise ValueError("Production OpenAI-compatible mode requires OPENAI_API_KEY")
            if self.llm_backend == "local_transformers" and not self.local_model_path:
                raise ValueError("Production local model mode requires LOCAL_MODEL_PATH")
            if not Path(self.embedding_model).expanduser().is_dir() and not self.embedding_model_revision:
                raise ValueError(
                    "Production Hub embedding models require EMBEDDING_MODEL_REVISION as an immutable "
                    "40-character commit SHA; model artifacts must be staged before runtime"
                )
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @property
    def skills_root(self) -> Path:
        return Path(self.affiliate_skills_dir).expanduser().resolve()

    def load_yaml(self) -> dict:
        path = Path(self.config_yaml_path)
        if not path.exists(): return {}
        with path.open("r", encoding="utf-8") as f: value = yaml.safe_load(f) or {}
        return value if isinstance(value, dict) else {}

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

"""Two-tier configuration.

Tier 1 — app/core/config/config.yaml: static, non-secret tunables (model names,
temperatures, retrieval thresholds, rate limits). Safe to commit, reviewable like
any other code change.

Tier 2 — .env: secrets and per-environment values (API keys, JWT signing key).
Never committed; .env.example documents every variable name.

Both tiers are cached with lru_cache so the file is only read once per process,
and every module gets the same object via get_settings() / get_config_dict().
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.exception.exceptions import ConfigurationException

_CONFIG_YAML_PATH = Path(__file__).resolve().parents[1] / "core" / "config" / "config.yaml"
_ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ".env"


class _EnvBaseSettings(BaseSettings):
    """Shared base: every settings group reads from the same .env file."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE_PATH if _ENV_FILE_PATH.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )


class LLMProviderSettings(_EnvBaseSettings):
    """Which chat/embedding provider to use, and their API keys."""

    llm_provider: str = "google"
    embedding_provider: str = "local"
    google_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""


class AuthSettings(_EnvBaseSettings):
    """JWT simulation settings, and which auth mode is active."""

    auth_mode: str = "simulated"
    # Dev default, override via .env; 32+ bytes to satisfy HS256's minimum
    # recommended key length (PyJWT warns below that).
    jwt_secret_key: str = "dev-only-change-me-replace-with-32-bytes-random-value"  # noqa: S105
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30


class EntraSettings(_EnvBaseSettings):
    """Microsoft Entra ID settings, only read when auth_mode == 'entra'."""

    entra_tenant_id: str = ""
    entra_client_id: str = ""


class MiddlewarePolicySettings(_EnvBaseSettings):
    """CORS and trusted-host middleware configuration."""

    cors_origin: str = "http://localhost:8501"
    allowed_host: str = "localhost;127.0.0.1"


class LoggingSettings(_EnvBaseSettings):
    """Log verbosity."""

    log_level: str = "INFO"


class Settings(BaseModel):
    """Composed settings object — the one thing the rest of the app depends on."""

    llm: LLMProviderSettings = LLMProviderSettings()
    auth: AuthSettings = AuthSettings()
    entra: EntraSettings = EntraSettings()
    middleware: MiddlewarePolicySettings = MiddlewarePolicySettings()
    logging: LoggingSettings = LoggingSettings()


class ConfigYAML:
    """Loads and holds the parsed contents of config.yaml."""

    def __init__(self) -> None:
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            with _CONFIG_YAML_PATH.open("r", encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        except OSError as exc:
            raise ConfigurationException(detail=f"Could not load config.yaml: {exc}") from exc

    @property
    def data(self) -> dict[str, Any]:
        return self._data


@lru_cache
def get_settings() -> Settings:
    """Cached secrets/env settings — call this, don't instantiate Settings() yourself."""
    return Settings()


@lru_cache
def get_config() -> ConfigYAML:
    """Cached static YAML tunables."""
    return ConfigYAML()


def get_config_dict() -> dict[str, Any]:
    """Convenience accessor returning the raw YAML dict."""
    return get_config().data


def get_secrets_dict() -> dict[str, Any]:
    """Convenience accessor returning settings as a plain dict (e.g. for logging/debug)."""
    return json.loads(get_settings().model_dump_json())

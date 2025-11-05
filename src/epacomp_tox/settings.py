from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


LEGACY_CTX_BASE_URL = "https://api-ccte.epa.gov"
DEFAULT_CTX_BASE_URL = "https://comptox.epa.gov/ctx-api"


@dataclass(frozen=True)
class AppSettings:
    environment: str
    log_level: str

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in {"dev", "development"}


@dataclass(frozen=True)
class SecuritySettings:
    bypass_auth: bool
    allowed_origins: List[str]


@dataclass(frozen=True)
class ContextSettings:
    api_key: str
    base_url: str
    use_legacy: bool
    retry_attempts: int
    retry_base: float


@dataclass(frozen=True)
class TransportSettings:
    heartbeat_timeout: int
    handshake_timeout: int


@dataclass(frozen=True)
class ObservabilitySettings:
    metrics_enabled: bool = True


class _RawSettings(BaseSettings):
    """Base settings loader leveraging Pydantic for env parsing."""

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    bypass_auth: bool = Field(default=False, alias="BYPASS_AUTH")
    cors_allow_origins: Optional[str] = Field(default=None, alias="CORS_ALLOW_ORIGINS")

    ctx_api_key: Optional[str] = Field(default=None, alias="CTX_API_KEY")
    ctx_api_key_legacy: Optional[str] = Field(default=None, alias="EPA_COMPTOX_API_KEY")
    ctx_api_key_client: Optional[str] = Field(default=None, alias="ctx_x_api_key")
    ctx_api_base_url: str = Field(default=DEFAULT_CTX_BASE_URL, alias="CTX_API_BASE_URL")
    ctx_use_legacy: bool = Field(default=False, alias="CTX_USE_LEGACY")
    ctx_retry_attempts: int = Field(default=3, alias="CTX_RETRY_ATTEMPTS")
    ctx_retry_base: float = Field(default=0.5, alias="CTX_RETRY_BASE")

    heartbeat_timeout: int = Field(default=120, alias="EPACOMP_MCP_HEARTBEAT_TIMEOUT_SECONDS")
    handshake_timeout: int = Field(default=30, alias="EPACOMP_MCP_HANDSHAKE_TIMEOUT_SECONDS")

    metrics_enabled: bool = Field(default=True, alias="EPACOMP_MCP_METRICS_ENABLED")


class Settings(_RawSettings):
    """High-level accessor that exposes strongly-typed sub-settings."""

    @cached_property
    def app(self) -> AppSettings:
        return AppSettings(environment=self.environment, log_level=self.log_level)

    @cached_property
    def security(self) -> SecuritySettings:
        raw = self.cors_allow_origins or ""
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        if not origins and self.app.is_development:
            origins = ["*"]
        return SecuritySettings(bypass_auth=self.bypass_auth, allowed_origins=origins)

    @cached_property
    def ctx(self) -> ContextSettings:
        api_key = self.ctx_api_key or self.ctx_api_key_legacy or self.ctx_api_key_client
        if not api_key:
            raise ValueError(
                "CTX API key is required. Provide CTX_API_KEY (preferred) or EPA_COMPTOX_API_KEY."
            )

        base_url = self.ctx_api_base_url
        use_legacy = bool(self.ctx_use_legacy)
        if use_legacy:
            base_url = LEGACY_CTX_BASE_URL

        return ContextSettings(
            api_key=api_key,
            base_url=base_url,
            use_legacy=use_legacy,
            retry_attempts=max(0, self.ctx_retry_attempts),
            retry_base=max(0.0, self.ctx_retry_base),
        )

    @cached_property
    def transport(self) -> TransportSettings:
        heartbeat = max(5, int(self.heartbeat_timeout))
        handshake = max(5, int(self.handshake_timeout))
        return TransportSettings(heartbeat_timeout=heartbeat, handshake_timeout=handshake)

    @cached_property
    def observability(self) -> ObservabilitySettings:
        return ObservabilitySettings(metrics_enabled=bool(self.metrics_enabled))


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    return Settings()


settings = _load_settings()


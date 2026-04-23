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
    auth_issuer: Optional[str]
    auth_audience: Optional[str]
    auth_jwks_url: Optional[str]
    auth_required_scopes: List[str]
    resource_url: str

    @property
    def auth_configured(self) -> bool:
        return bool(self.auth_issuer and self.auth_audience and self.auth_jwks_url)

    @property
    def auth_requested(self) -> bool:
        return bool(
            self.auth_issuer
            or self.auth_audience
            or self.auth_jwks_url
            or self.auth_required_scopes
        )


@dataclass(frozen=True)
class RateLimitSettings:
    requests_per_minute: int
    burst: int


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
    metrics_bypass_auth: bool = False


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
    mcp_auth_issuer: Optional[str] = Field(default=None, alias="MCP_AUTH_ISSUER")
    mcp_auth_audience: Optional[str] = Field(default=None, alias="MCP_AUTH_AUDIENCE")
    mcp_auth_jwks_url: Optional[str] = Field(default=None, alias="MCP_AUTH_JWKS_URL")
    mcp_auth_required_scopes: Optional[str] = Field(
        default=None, alias="MCP_AUTH_REQUIRED_SCOPES"
    )
    mcp_resource_url: str = Field(
        default="http://localhost:8000/mcp", alias="MCP_RESOURCE_URL"
    )
    rate_limit_requests_per_minute: int = Field(
        default=120, alias="MCP_RATE_LIMIT_REQUESTS_PER_MINUTE"
    )
    rate_limit_burst: int = Field(default=20, alias="MCP_RATE_LIMIT_BURST")

    ctx_api_key: Optional[str] = Field(default=None, alias="CTX_API_KEY")
    ctx_api_key_legacy: Optional[str] = Field(default=None, alias="EPA_COMPTOX_API_KEY")
    ctx_api_key_client: Optional[str] = Field(default=None, alias="ctx_x_api_key")
    ctx_api_base_url: str = Field(
        default=DEFAULT_CTX_BASE_URL, alias="CTX_API_BASE_URL"
    )
    ctx_use_legacy: bool = Field(default=False, alias="CTX_USE_LEGACY")
    ctx_retry_attempts: int = Field(default=3, alias="CTX_RETRY_ATTEMPTS")
    ctx_retry_base: float = Field(default=0.5, alias="CTX_RETRY_BASE")

    heartbeat_timeout: int = Field(
        default=120, alias="EPACOMP_MCP_HEARTBEAT_TIMEOUT_SECONDS"
    )
    handshake_timeout: int = Field(
        default=30, alias="EPACOMP_MCP_HANDSHAKE_TIMEOUT_SECONDS"
    )

    metrics_enabled: bool = Field(default=True, alias="EPACOMP_MCP_METRICS_ENABLED")
    metrics_bypass_auth: bool = Field(default=False, alias="MCP_METRICS_BYPASS_AUTH")


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
        scopes = [
            scope.strip()
            for chunk in (self.mcp_auth_required_scopes or "").split(",")
            for scope in chunk.split()
            if scope.strip()
        ]
        return SecuritySettings(
            bypass_auth=bool(self.bypass_auth),
            allowed_origins=origins,
            auth_issuer=self.mcp_auth_issuer,
            auth_audience=self.mcp_auth_audience,
            auth_jwks_url=self.mcp_auth_jwks_url,
            auth_required_scopes=scopes,
            resource_url=self.mcp_resource_url,
        )

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
        return TransportSettings(
            heartbeat_timeout=heartbeat, handshake_timeout=handshake
        )

    @cached_property
    def rate_limit(self) -> RateLimitSettings:
        rpm = max(0, int(self.rate_limit_requests_per_minute))
        burst = int(self.rate_limit_burst)
        if burst <= 0:
            burst = rpm
        return RateLimitSettings(requests_per_minute=rpm, burst=max(0, burst))

    @cached_property
    def observability(self) -> ObservabilitySettings:
        return ObservabilitySettings(
            metrics_enabled=bool(self.metrics_enabled),
            metrics_bypass_auth=bool(self.metrics_bypass_auth),
        )


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    return Settings()


settings = _load_settings()

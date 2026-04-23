from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from epacomp_tox.settings import AppSettings, RateLimitSettings, SecuritySettings

try:  # pragma: no cover - exercised when JWT validation is configured
    import jwt
    from jwt import PyJWKClient
except ImportError:  # pragma: no cover - optional until auth is configured
    jwt = None  # type: ignore[assignment]
    PyJWKClient = None  # type: ignore[assignment]


class AuthError(RuntimeError):
    """Authentication or authorization failure."""

    def __init__(
        self,
        *,
        status_code: int,
        error: str,
        description: str,
        required_scopes: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(description)
        self.status_code = status_code
        self.error = error
        self.description = description
        self.required_scopes = list(required_scopes or [])


@dataclass(frozen=True)
class AuthContext:
    """Safe authentication summary for sessions, audit, and metadata."""

    subject_hash: Optional[str]
    issuer: Optional[str]
    audience: Tuple[str, ...]
    scopes: Tuple[str, ...]
    expires_at: Optional[int]
    token_hash: Optional[str]
    bypassed: bool = False

    def safe_summary(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "authenticated": self.subject_hash is not None and not self.bypassed,
            "scopes": list(self.scopes),
        }
        if self.subject_hash:
            summary["subjectHash"] = self.subject_hash
        if self.issuer:
            summary["issuer"] = self.issuer
        if self.audience:
            summary["audience"] = list(self.audience)
        if self.expires_at is not None:
            summary["expiresAt"] = self.expires_at
        if self.token_hash:
            summary["tokenHash"] = self.token_hash
        if self.bypassed:
            summary["bypassed"] = True
        return summary

    def rate_limit_key(self, fallback: str) -> str:
        if self.subject_hash:
            return f"sub:{self.subject_hash}"
        if self.token_hash:
            return f"tok:{self.token_hash}"
        return fallback


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: float = 0.0
    remaining: int = 0


class InMemoryRateLimiter:
    """Simple process-local token-bucket limiter for MCP tool calls."""

    def __init__(self, settings: RateLimitSettings):
        self.requests_per_minute = settings.requests_per_minute
        self.burst = max(1, settings.burst)
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = Lock()

    @property
    def enabled(self) -> bool:
        return self.requests_per_minute > 0

    def check(self, key: str) -> RateLimitDecision:
        if not self.enabled:
            return RateLimitDecision(allowed=True, remaining=self.burst)

        now = time.monotonic()
        refill_per_second = self.requests_per_minute / 60.0
        with self._lock:
            tokens, last_seen = self._buckets.get(key, (float(self.burst), now))
            elapsed = max(0.0, now - last_seen)
            tokens = min(float(self.burst), tokens + elapsed * refill_per_second)
            if tokens < 1.0:
                retry_after = (1.0 - tokens) / refill_per_second
                self._buckets[key] = (tokens, now)
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=retry_after,
                    remaining=0,
                )
            tokens -= 1.0
            self._buckets[key] = (tokens, now)
            return RateLimitDecision(
                allowed=True,
                remaining=max(0, int(tokens)),
            )


class BearerAuthValidator:
    """Validate MCP bearer tokens against configured OIDC/JWKS settings."""

    def __init__(
        self,
        *,
        security: SecuritySettings,
        app: AppSettings,
        bypass_auth: Optional[bool] = None,
    ) -> None:
        self.security = security
        self.app = app
        self.bypass_auth = security.bypass_auth if bypass_auth is None else bypass_auth
        self.enabled = self._resolve_enabled()
        self.required_scopes = tuple(security.auth_required_scopes)
        self._jwks_client = None
        if self.enabled:
            self._validate_configuration()
            if PyJWKClient is None:
                raise RuntimeError(
                    "PyJWT[crypto] is required when MCP bearer authentication is enabled."
                )
            self._jwks_client = PyJWKClient(security.auth_jwks_url)  # type: ignore[arg-type]

    def _resolve_enabled(self) -> bool:
        if self.bypass_auth:
            return False
        if self.security.auth_configured:
            return True
        if self.security.auth_requested:
            return True
        return not self.app.is_development

    def _validate_configuration(self) -> None:
        missing = []
        if not self.security.auth_issuer:
            missing.append("MCP_AUTH_ISSUER")
        if not self.security.auth_audience:
            missing.append("MCP_AUTH_AUDIENCE")
        if not self.security.auth_jwks_url:
            missing.append("MCP_AUTH_JWKS_URL")
        if missing:
            raise RuntimeError(
                "MCP auth is enabled but incomplete; set "
                + ", ".join(missing)
                + " or use BYPASS_AUTH=1 for local development."
            )

    def authenticate_header(
        self, authorization: Optional[str], *, remote_addr: Optional[str] = None
    ) -> AuthContext:
        if not self.enabled:
            return AuthContext(
                subject_hash=None,
                issuer=None,
                audience=(),
                scopes=(),
                expires_at=None,
                token_hash=None,
                bypassed=self.bypass_auth,
            )

        scheme, token = _split_authorization(authorization)
        if scheme.lower() != "bearer" or not token:
            raise AuthError(
                status_code=401,
                error="invalid_token",
                description="Bearer token is required.",
                required_scopes=self.required_scopes,
            )

        claims = self._decode_jwt(token)
        scopes = tuple(sorted(_extract_scopes(claims)))
        missing_scopes = sorted(set(self.required_scopes) - set(scopes))
        if missing_scopes:
            raise AuthError(
                status_code=403,
                error="insufficient_scope",
                description="Bearer token is missing required MCP scope.",
                required_scopes=self.required_scopes,
            )

        subject = str(claims.get("sub") or "")
        audience = claims.get("aud")
        return AuthContext(
            subject_hash=_hash_value(subject) if subject else None,
            issuer=claims.get("iss"),
            audience=tuple(str(item) for item in _as_list(audience)),
            scopes=scopes,
            expires_at=(
                claims.get("exp") if isinstance(claims.get("exp"), int) else None
            ),
            token_hash=_hash_value(token),
            bypassed=False,
        )

    def _decode_jwt(self, token: str) -> Dict[str, Any]:
        if jwt is None or self._jwks_client is None:
            raise AuthError(
                status_code=401,
                error="invalid_token",
                description="JWT validation is not available.",
                required_scopes=self.required_scopes,
            )
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                signing_key,
                algorithms=[
                    "RS256",
                    "RS384",
                    "RS512",
                    "ES256",
                    "ES384",
                    "ES512",
                ],
                audience=_split_config_values(self.security.auth_audience),
                issuer=self.security.auth_issuer,
            )
        except Exception as exc:
            raise AuthError(
                status_code=401,
                error="invalid_token",
                description="Bearer token is invalid.",
                required_scopes=self.required_scopes,
            ) from exc

    def protected_resource_metadata(self) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "resource": self.security.resource_url,
            "bearer_methods_supported": ["header"],
            "scopes_supported": list(self.required_scopes),
        }
        if self.security.auth_issuer:
            metadata["authorization_servers"] = [self.security.auth_issuer]
        if self.security.auth_jwks_url:
            metadata["jwks_uri"] = self.security.auth_jwks_url
        return metadata

    def www_authenticate_header(self, error: Optional[AuthError] = None) -> str:
        parts = [
            "Bearer",
            f'resource="{self.security.resource_url}"',
            f'resource_metadata="{self.security.resource_url.rstrip("/")}/.well-known/oauth-protected-resource"',
        ]
        scopes = error.required_scopes if error else self.required_scopes
        if scopes:
            parts.append(f'scope="{" ".join(scopes)}"')
        if error is not None:
            parts.append(f'error="{error.error}"')
        return ", ".join(parts)


def _split_authorization(authorization: Optional[str]) -> Tuple[str, str]:
    if not authorization:
        return "", ""
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2:
        return authorization.strip(), ""
    return parts[0], parts[1].strip()


def _split_config_values(value: Optional[str]) -> Any:
    values = [item.strip() for item in (value or "").split(",") if item.strip()]
    if not values:
        return value
    if len(values) == 1:
        return values[0]
    return values


def _extract_scopes(claims: Dict[str, Any]) -> List[str]:
    scopes: List[str] = []
    scope_value = claims.get("scope")
    if isinstance(scope_value, str):
        scopes.extend(scope_value.split())
    scp_value = claims.get("scp")
    if isinstance(scp_value, str):
        scopes.extend(scp_value.split())
    elif isinstance(scp_value, Iterable):
        scopes.extend(str(item) for item in scp_value)
    return [scope for scope in scopes if scope]


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

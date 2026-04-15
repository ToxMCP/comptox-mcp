"""
ToxMCP Reviewed Remediation Snippets
===================================

This module contains implementation-oriented reference code derived from the
reviewed audit package. It is intentionally written as reference code rather
than a drop-in patch set.

Important:
- These patterns still require repository-specific adaptation.
- Provider/version controls must use features the upstream actually supports.
- Signature verification is exposed via an injected verifier callback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol
import hashlib
import json
import os
import platform
import subprocess
import unicodedata


# =============================================================================
# Shared helpers
# =============================================================================

def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    """Serialize datetime consistently in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_json_value(value: Any, *, fp_precision: int = 17) -> Any:
    """
    Normalize a value for deterministic JSON hashing.

    Notes:
    - Floats are normalized conservatively.
    - NaN/Infinity are represented as strings because JSON itself does not
      define canonical encodings for these values.
    """
    if isinstance(value, float):
        if value != value:  # NaN
            return "NaN"
        if value == float("inf"):
            return "Infinity"
        if value == float("-inf"):
            return "-Infinity"
        if value == 0.0:
            return 0.0
        return round(value, fp_precision)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return iso_utc(value)
    if isinstance(value, Mapping):
        return {str(k): normalize_json_value(v, fp_precision=fp_precision) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [normalize_json_value(v, fp_precision=fp_precision) for v in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    normalized = normalize_json_value(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")


# =============================================================================
# Audit trail reference model
# =============================================================================

class AuditStorage(Protocol):
    def append(self, event: "RegulatoryAuditEvent") -> None:
        ...

    def read_all(self) -> Iterable["RegulatoryAuditEvent"]:
        ...


class InMemoryAuditStorage:
    """Simple storage backend for examples and tests."""

    def __init__(self) -> None:
        self._events: List[RegulatoryAuditEvent] = []

    def append(self, event: "RegulatoryAuditEvent") -> None:
        self._events.append(event)

    def read_all(self) -> Iterable["RegulatoryAuditEvent"]:
        return list(self._events)


@dataclass(frozen=True)
class RegulatoryAuditEvent:
    """Reference audit-event envelope for higher-assurance workflows."""

    event_id: str
    event_type: str
    timestamp_utc: datetime
    user_id: str
    session_id: str
    payload: Dict[str, Any]
    previous_hash: str
    content_hash: str
    service_version: str
    git_commit: str
    upstream: Dict[str, Any] = field(default_factory=dict)
    signature: Optional[str] = None

    @staticmethod
    def build(
        *,
        event_id: str,
        event_type: str,
        user_id: str,
        session_id: str,
        payload: Dict[str, Any],
        previous_hash: str,
        service_version: str,
        git_commit: str,
        upstream: Optional[Dict[str, Any]] = None,
        timestamp_utc: Optional[datetime] = None,
        signature: Optional[str] = None,
    ) -> "RegulatoryAuditEvent":
        ts = timestamp_utc or utc_now()
        canonical = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp_utc": iso_utc(ts),
            "user_id": user_id,
            "session_id": session_id,
            "payload": payload,
            "previous_hash": previous_hash,
            "service_version": service_version,
            "git_commit": git_commit,
            "upstream": upstream or {},
        }
        content_hash = sha256_hex(canonical_json_bytes(canonical))
        return RegulatoryAuditEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp_utc=ts,
            user_id=user_id,
            session_id=session_id,
            payload=payload,
            previous_hash=previous_hash,
            content_hash=content_hash,
            service_version=service_version,
            git_commit=git_commit,
            upstream=upstream or {},
            signature=signature,
        )


class AuditChainBrokenError(Exception):
    """Raised when the expected audit chain has been broken."""


class RegulatoryAuditTrail:
    """
    Append-only audit trail reference implementation.

    This example uses an in-memory backend by default. In production, replace
    with an append-controlled storage implementation and add retention/access
    controls appropriate for the deployment context.
    """

    def __init__(self, storage: Optional[AuditStorage] = None) -> None:
        self._storage = storage or InMemoryAuditStorage()
        self._tail_hash = "0" * 64

    @property
    def tail_hash(self) -> str:
        return self._tail_hash

    def record(self, event: RegulatoryAuditEvent) -> str:
        if event.previous_hash != self._tail_hash:
            raise AuditChainBrokenError(
                f"Expected previous_hash={self._tail_hash}, got {event.previous_hash}"
            )
        if self._compute_hash(event) != event.content_hash:
            raise AuditChainBrokenError("Event content hash does not match canonical content")
        self._storage.append(event)
        self._tail_hash = event.content_hash
        return self._tail_hash

    def verify_chain(self) -> bool:
        expected = "0" * 64
        for event in self._storage.read_all():
            if event.previous_hash != expected:
                return False
            if self._compute_hash(event) != event.content_hash:
                return False
            expected = event.content_hash
        return True

    @staticmethod
    def _compute_hash(event: RegulatoryAuditEvent) -> str:
        canonical = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp_utc": iso_utc(event.timestamp_utc),
            "user_id": event.user_id,
            "session_id": event.session_id,
            "payload": event.payload,
            "previous_hash": event.previous_hash,
            "service_version": event.service_version,
            "git_commit": event.git_commit,
            "upstream": event.upstream,
        }
        return sha256_hex(canonical_json_bytes(canonical))


# =============================================================================
# Electronic review/signature reference model
# =============================================================================

SignatureVerifier = Callable[[bytes, "ElectronicSignature"], bool]


@dataclass(frozen=True)
class ElectronicSignature:
    """
    Reference structure for review or approval events.

    This intentionally leaves cryptographic verification pluggable because the
    concrete mechanism depends on deployment policy and available infrastructure.
    """

    signer_user_id: str
    signer_full_name: str
    signature_meaning: str  # e.g. authored / reviewed / approved / rejected
    signature_timestamp_utc: datetime
    content_hash: str
    signature_value: bytes
    algorithm: str = "ecdsa-sha256"
    certificate_chain_pem: List[str] = field(default_factory=list)

    def verify(self, content: bytes, verifier: SignatureVerifier) -> bool:
        if sha256_hex(content) != self.content_hash:
            return False
        return verifier(content, self)


# =============================================================================
# Upstream provenance capture
# =============================================================================

@dataclass(frozen=True)
class UpstreamRecord:
    """
    Captures the strongest provenance information available for an upstream call.

    Note:
    - Only populate provider_version or snapshot_id if the upstream actually
      exposes such concepts.
    - If not, internal response hashing and cache identity become more important.
    """

    provider_name: str
    request_url: str
    request_params: Dict[str, Any] = field(default_factory=dict)
    retrieved_at_utc: datetime = field(default_factory=utc_now)
    provider_version: Optional[str] = None
    snapshot_id: Optional[str] = None
    response_hash: Optional[str] = None
    cache_key: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "request_url": self.request_url,
            "request_params": self.request_params,
            "retrieved_at_utc": iso_utc(self.retrieved_at_utc),
            "provider_version": self.provider_version,
            "snapshot_id": self.snapshot_id,
            "response_hash": self.response_hash,
            "cache_key": self.cache_key,
        }


# =============================================================================
# Reproducibility and environment capture
# =============================================================================

@dataclass(frozen=True)
class ExecutionEnvironment:
    container_image_digest: str
    container_image_tag: str
    git_commit_hash: str
    git_tag: Optional[str]
    git_dirty: bool
    poetry_lock_hash: Optional[str]
    python_version: str
    os_name: str
    os_version: str
    cpu_architecture: str
    random_seed: Optional[int] = None
    floating_point_mode: str = "strict"
    upstream_records: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "container": {
                "image_digest": self.container_image_digest,
                "image_tag": self.container_image_tag,
            },
            "code": {
                "git_commit": self.git_commit_hash,
                "git_tag": self.git_tag,
                "git_dirty": self.git_dirty,
                "poetry_lock_hash": self.poetry_lock_hash,
            },
            "runtime": {
                "python": self.python_version,
                "os": f"{self.os_name} {self.os_version}",
                "cpu": self.cpu_architecture,
                "random_seed": self.random_seed,
                "floating_point_mode": self.floating_point_mode,
            },
            "upstream": self.upstream_records,
        }


def _run_git_command(args: List[str]) -> Optional[str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=True)
        return result.stdout.strip() or None
    except Exception:
        return None


def _file_hash_if_exists(path: str) -> Optional[str]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    return sha256_hex(p.read_bytes())


def capture_execution_environment(
    *,
    upstream_records: Optional[Mapping[str, UpstreamRecord]] = None,
    random_seed: Optional[int] = None,
    floating_point_mode: str = "strict",
) -> ExecutionEnvironment:
    git_commit = _run_git_command(["git", "rev-parse", "HEAD"]) or "unknown"
    git_tag = _run_git_command(["git", "describe", "--tags", "--exact-match"])
    git_status = _run_git_command(["git", "status", "--porcelain"])
    git_dirty = bool(git_status)

    upstream = {
        name: record.as_dict()
        for name, record in (upstream_records or {}).items()
    }

    return ExecutionEnvironment(
        container_image_digest=os.getenv("TOXMCP_IMAGE_DIGEST", "unknown"),
        container_image_tag=os.getenv("TOXMCP_IMAGE_TAG", "unknown"),
        git_commit_hash=git_commit,
        git_tag=git_tag,
        git_dirty=git_dirty,
        poetry_lock_hash=_file_hash_if_exists("poetry.lock"),
        python_version=platform.python_version(),
        os_name=platform.system(),
        os_version=platform.release(),
        cpu_architecture=platform.machine(),
        random_seed=random_seed,
        floating_point_mode=floating_point_mode,
        upstream_records=upstream,
    )


# =============================================================================
# Untrusted text handling for model-facing contexts
# =============================================================================

def sanitize_untrusted_identifier(text: str, *, allow_newlines: bool = False, max_length: int = 256) -> str:
    """
    Normalize and sanitize a free-text identifier before passing it into an
    LLM- or agent-facing context.

    This is a helper, not a complete prompt-injection defense. The primary
    defense should still be prompt structure and isolation of untrusted fields.
    """
    normalized = unicodedata.normalize("NFKC", text)
    if len(normalized) > max_length:
        raise ValueError(f"Identifier exceeds maximum length {max_length}")

    cleaned_chars: List[str] = []
    for char in normalized:
        category = unicodedata.category(char)
        if category.startswith("C"):
            if allow_newlines and char in "\n\r":
                cleaned_chars.append("\n")
            # drop all other control characters
            continue
        cleaned_chars.append(char)

    cleaned = "".join(cleaned_chars)
    if not allow_newlines:
        cleaned = cleaned.replace("\n", " ").replace("\r", " ")
    return " ".join(cleaned.split()).strip()


# =============================================================================
# Example usage
# =============================================================================

if __name__ == "__main__":
    audit_trail = RegulatoryAuditTrail()

    env = capture_execution_environment(
        upstream_records={
            "comptox": UpstreamRecord(
                provider_name="comptox",
                request_url="https://example.invalid/chemical/detail/DTXSID123",
                request_params={"id": "DTXSID123"},
                provider_version=None,
                snapshot_id=None,
                response_hash="placeholder-response-hash",
                cache_key="comptox:DTXSID123:v1",
            )
        },
        random_seed=1234,
    )

    event = RegulatoryAuditEvent.build(
        event_id="evt-001",
        event_type="workflow_started",
        user_id="user-123",
        session_id="sess-001",
        payload={"chemical_name": sanitize_untrusted_identifier("Benzene")},
        previous_hash=audit_trail.tail_hash,
        service_version="toxmcp-suite reviewed-reference",
        git_commit=env.git_commit_hash,
        upstream={"comptox": env.upstream_records.get("comptox", {})},
    )

    audit_trail.record(event)
    print(json.dumps(env.as_dict(), indent=2))
    print(f"audit_chain_ok={audit_trail.verify_chain()}")

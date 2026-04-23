from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Tuple, Union

SAFE_PATH_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class AuditBundleStore:
    """Durable storage for orchestrator audit bundles and attachments."""

    def __init__(
        self, base_dir: Union[str, Path], *, retention_days: Optional[int] = None
    ) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days

    def save(
        self,
        bundle: Dict[str, any],
        *,
        attachments: Optional[Dict[str, Union[str, bytes]]] = None,
    ) -> Dict[str, any]:
        run_id = bundle.get("workflowRunId")
        if not run_id:
            raise ValueError("Bundle must include 'workflowRunId'.")
        run_id = self._safe_component(str(run_id), "workflowRunId")

        run_dir = self._resolve_under_base(self.base_dir / run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(timezone.utc).isoformat()

        payload = json.dumps(
            bundle, ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8")
        bundle_path = run_dir / "bundle.json"
        self._atomic_write(bundle_path, payload)
        bundle_checksum = hashlib.sha256(payload).hexdigest()

        attachments_meta: List[Dict[str, any]] = []
        if attachments:
            attachments_dir = run_dir / "attachments"
            attachments_dir.mkdir(parents=True, exist_ok=True)
            for name, content in attachments.items():
                safe_name, target = self._safe_attachment_path(attachments_dir, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                data = content.encode("utf-8") if isinstance(content, str) else content
                self._atomic_write(target, data)
                attachments_meta.append(
                    {
                        "name": safe_name,
                        "path": str(target.relative_to(self.base_dir)),
                        "size": len(data),
                        "checksum": hashlib.sha256(data).hexdigest(),
                    }
                )

        # Chain-aware provenance: link to previous bundle hash
        chain_manifest_path = self.base_dir / "chain_manifest.json"
        previous_hash = self._load_previous_hash(chain_manifest_path)

        metadata = {
            "workflowRunId": run_id,
            "createdAt": created_at,
            "bundlePath": str(bundle_path.relative_to(self.base_dir)),
            "bundleChecksum": bundle_checksum,
            "previousBundleHash": previous_hash,
            "attachments": attachments_meta,
            "retentionDays": self.retention_days,
        }

        metadata_path = run_dir / "metadata.json"
        self._atomic_write(
            metadata_path,
            json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8"),
        )

        # Update chain manifest with latest hash
        self._update_chain_manifest(chain_manifest_path, bundle_checksum, created_at)

        return metadata

    def _load_previous_hash(self, chain_manifest_path: Path) -> str:
        """Read the last bundle hash from the chain manifest."""
        if not chain_manifest_path.exists():
            return "0" * 64
        try:
            manifest = json.loads(chain_manifest_path.read_text(encoding="utf-8"))
            return manifest.get("lastBundleHash", "0" * 64)
        except (json.JSONDecodeError, KeyError, OSError):
            return "0" * 64

    def _update_chain_manifest(
        self, chain_manifest_path: Path, bundle_checksum: str, created_at: str
    ) -> None:
        """Persist the latest bundle hash for the next link in the chain."""
        manifest = {
            "lastBundleHash": bundle_checksum,
            "updatedAt": created_at,
        }
        try:
            self._atomic_write(
                chain_manifest_path,
                json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
            )
        except OSError:  # pragma: no cover - defensive
            pass

    def verify_chain(self) -> Tuple[bool, List[str]]:
        """Verify integrity of the stored bundle chain.

        Returns:
            (is_valid, list of error messages for any broken links)
        """
        errors: List[str] = []
        previous_hash = "0" * 64
        for meta in self.list_runs():
            run_id = meta.get("workflowRunId")
            expected_previous = meta.get("previousBundleHash")
            if expected_previous != previous_hash:
                errors.append(f"Run {run_id}: previous hash mismatch")

            # Recompute bundle hash from file
            bundle_path = self._resolve_under_base(
                self.base_dir / meta.get("bundlePath", "")
            )
            if bundle_path.exists():
                computed = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
                if computed != meta.get("bundleChecksum"):
                    errors.append(f"Run {run_id}: bundle checksum mismatch")
                previous_hash = computed
            else:
                errors.append(f"Run {run_id}: bundle file missing")
                previous_hash = meta.get("bundleChecksum", "0" * 64)

        return (not errors, errors)

    def load_bundle(self, run_id: str) -> Dict[str, any]:
        safe_run_id = self._safe_component(str(run_id), "workflowRunId")
        bundle_path = self._resolve_under_base(
            self.base_dir / safe_run_id / "bundle.json"
        )
        if not bundle_path.exists():
            raise FileNotFoundError(f"No bundle found for run {run_id}")
        return json.loads(bundle_path.read_text(encoding="utf-8"))

    def load_metadata(self, run_id: str) -> Dict[str, any]:
        safe_run_id = self._safe_component(str(run_id), "workflowRunId")
        metadata_path = self._resolve_under_base(
            self.base_dir / safe_run_id / "metadata.json"
        )
        if not metadata_path.exists():
            raise FileNotFoundError(f"No metadata found for run {run_id}")
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    def list_runs(self) -> List[Dict[str, any]]:
        runs: List[Dict[str, any]] = []
        for entry in sorted(self.base_dir.iterdir()):
            if not entry.is_dir():
                continue
            metadata_path = entry / "metadata.json"
            if not metadata_path.exists():
                continue
            try:
                runs.append(json.loads(metadata_path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return runs

    @staticmethod
    def _safe_component(value: str, label: str) -> str:
        if not SAFE_PATH_COMPONENT.match(value) or ".." in value:
            raise ValueError(f"Unsafe {label}: {value!r}")
        return value

    def _resolve_under_base(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.base_dir)
        except ValueError as exc:
            raise ValueError("Resolved audit path escapes store root.") from exc
        return resolved

    def _safe_attachment_path(
        self, attachments_dir: Path, name: Union[str, Path]
    ) -> Tuple[str, Path]:
        raw_name = str(name).replace("\\", "/")
        relative = PurePosixPath(raw_name)
        if relative.is_absolute() or not relative.parts:
            raise ValueError(f"Unsafe attachment name: {raw_name!r}")
        safe_parts = [
            self._safe_component(part, "attachment path component")
            for part in relative.parts
        ]
        safe_name = "/".join(safe_parts)
        target = self._resolve_under_base(attachments_dir.joinpath(*safe_parts))
        return safe_name, target

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        tmp_path = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
        tmp_path.write_bytes(payload)
        tmp_path.replace(path)

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union


class AuditBundleStore:
    """Durable storage for orchestrator audit bundles and attachments."""

    def __init__(
        self, base_dir: Union[str, Path], *, retention_days: Optional[int] = None
    ) -> None:
        self.base_dir = Path(base_dir)
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

        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(timezone.utc).isoformat()

        payload = json.dumps(
            bundle, ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8")
        bundle_path = run_dir / "bundle.json"
        bundle_path.write_bytes(payload)
        bundle_checksum = hashlib.sha256(payload).hexdigest()

        attachments_meta: List[Dict[str, any]] = []
        if attachments:
            attachments_dir = run_dir / "attachments"
            attachments_dir.mkdir(parents=True, exist_ok=True)
            for name, content in attachments.items():
                target = attachments_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                data = content.encode("utf-8") if isinstance(content, str) else content
                target.write_bytes(data)
                attachments_meta.append(
                    {
                        "name": name,
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
        metadata_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
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
            chain_manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
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
                errors.append(
                    f"Run {run_id}: previous hash mismatch"
                )

            # Recompute bundle hash from file
            bundle_path = self.base_dir / meta.get("bundlePath", "")
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
        bundle_path = self.base_dir / run_id / "bundle.json"
        if not bundle_path.exists():
            raise FileNotFoundError(f"No bundle found for run {run_id}")
        return json.loads(bundle_path.read_text(encoding="utf-8"))

    def load_metadata(self, run_id: str) -> Dict[str, any]:
        metadata_path = self.base_dir / run_id / "metadata.json"
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

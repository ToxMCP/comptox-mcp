from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union


class AuditBundleStore:
    """Durable storage for orchestrator audit bundles and attachments."""

    def __init__(self, base_dir: Union[str, Path], *, retention_days: Optional[int] = None) -> None:
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

        payload = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
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

        metadata = {
            "workflowRunId": run_id,
            "createdAt": created_at,
            "bundlePath": str(bundle_path.relative_to(self.base_dir)),
            "bundleChecksum": bundle_checksum,
            "attachments": attachments_meta,
            "retentionDays": self.retention_days,
        }

        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return metadata

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

#!/usr/bin/env python3
"""Regenerate the golden spine-projection fixtures from the released corpus.

For each released ``prioritize_risk_signals`` corpus file, project it onto its
spine ``BioactivityExposureRatioRecord`` object(s) and write each projected object
to ``tests/fixtures/governance/spine_projection/`` under a deterministic,
byte-stable filename. CI runs this and ``git diff --exit-code`` to prove the
projection is TOTAL & DETERMINISTIC (no clocks / randomness / hidden defaults): a
projection change that is not reflected in the committed golden fixtures fails the
build.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from epacomp_tox.governance import project_to_spine as projector  # noqa: E402

CORPUS: tuple[str, ...] = (
    "tests/fixtures/governance/released/pristine_prioritize_risk_signals.json",
)
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "governance" / "spine_projection"


def _kind(schema_id: str) -> str:
    return schema_id.rsplit("/", 1)[-1].split(".")[0] or "object"


def main() -> int:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for rel in CORPUS:
        src = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))
        stem = Path(rel).stem
        for obj in projector.project_packet(src):
            kind = _kind(obj.get("schemaId", ""))
            ref = obj.get("bioactivityExposureRatioRecordId", "object")
            safe_ref = ref.replace(":", "_").replace("/", "_")
            out = GOLDEN_DIR / f"{stem}__{kind}__{safe_ref}.json"
            out.write_text(
                json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8"
            )
            written.append(out.name)
    print(f"[golden] wrote {len(written)} projection fixture(s): {', '.join(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

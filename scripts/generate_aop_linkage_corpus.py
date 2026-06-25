#!/usr/bin/env python3
"""Regenerate the released aopLinkageSummary corpus + golden spine projections.

The SERVER-AUTHORED ``aopLinkageSummary`` block (a confidence-band AOP linkage) is
released BOTH standalone (``build_aop_linkage_summary``) AND embedded in
``assemble_comptox_evidence_pack`` (``payload["aopLinkageSummary"]``). This script
runs the REAL ``InteropResource`` against the committed stub data sources, captures
each released surface, NORMALIZES its non-deterministic timestamp/trace fields to a
fixed sentinel (so the committed corpus is byte-stable — those fields are pure
provenance the projection never reads), and writes:

  * the released corpus fixtures under
    ``tests/fixtures/governance/released/`` (the gate's aopLinkageSummary corpus);
  * the golden ReadAcrossJustification projection(s) under
    ``tests/fixtures/governance/spine_projection/``.

CI runs this + ``git diff --exit-code`` to prove the projection is TOTAL &
DETERMINISTIC. The same normalization helper is shared with the test module so the
committed corpus provably equals the real producer's (normalized) emission.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests"))

from epacomp_tox.governance import project_to_spine as projector  # noqa: E402

RELEASED_DIR = REPO_ROOT / "tests" / "fixtures" / "governance" / "released"
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "governance" / "spine_projection"


def build_corpus() -> dict[str, dict[str, Any]]:
    """Run the real producer and return the normalized released surfaces."""
    from interop_test_support import (  # noqa: E402
        build_interop_resource,
        normalize_timestamps,
    )

    resource = build_interop_resource()
    standalone = resource.execute_tool(
        "build_aop_linkage_summary", {"dtxsid": "DTXSID7020182"}
    )
    pack = resource.execute_tool(
        "assemble_comptox_evidence_pack",
        {"dtxsid": "DTXSID7020182", "hazard_datasets": ["toxval", "adme_ivive"]},
    )
    return {
        "pristine_aop_linkage_summary.json": normalize_timestamps(standalone),
        "pristine_evidence_pack_aop_linkage.json": normalize_timestamps(pack),
    }


def _kind(schema_id: str) -> str:
    return schema_id.rsplit("/", 1)[-1].split(".")[0] or "object"


def main() -> int:
    RELEASED_DIR.mkdir(parents=True, exist_ok=True)
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    corpus = build_corpus()
    written: list[str] = []
    for name, obj in corpus.items():
        path = RELEASED_DIR / name
        path.write_text(
            json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
        written.append(name)

        projected = projector.project_aop_packet(obj)
        for proj in projected:
            kind = _kind(proj.get("schemaId", ""))
            ref = proj.get("readAcrossJustificationId", "object")
            safe_ref = ref.replace(":", "_").replace("/", "_")
            stem = Path(name).stem
            out = GOLDEN_DIR / f"{stem}__{kind}__{safe_ref}.json"
            out.write_text(
                json.dumps(proj, indent=2, sort_keys=False) + "\n", encoding="utf-8"
            )
            written.append(out.name)

    print(f"[aop-golden] wrote {len(written)} fixture(s): {', '.join(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

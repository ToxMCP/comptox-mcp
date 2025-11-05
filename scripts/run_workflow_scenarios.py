#!/usr/bin/env python3
"""
Workflow scenario runner for MCP Phase 2 harness.

Currently supports the offline orchestrator scenarios to validate bundle outputs.
Future extensions can plug in sandbox/live MCP transports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from epacomp_tox import PredictiveTask, PredictiveRequest  # noqa: E402
from epacomp_tox.orchestrator.offline import (  # noqa: E402
    OFFLINE_SCENARIOS,
    build_offline_orchestrator,
)


def run_offline_scenarios(output_dir: Path) -> List[Dict[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    orchestrator = build_offline_orchestrator(
        persistence_dir=output_dir,
        clock=lambda: "2025-03-26T00:00:00Z",
    )
    results: List[Dict[str, str]] = []
    for scenario in OFFLINE_SCENARIOS:
        bundle = orchestrator.run_workflow(
            target_identifier="50-00-0",
            identifier_type="casrn",
            scenarios=[scenario],
            predictive_plan=[
                PredictiveTask(
                    service="offline_genra",
                    scenario=scenario,
                    request=PredictiveRequest(chemical_identifier="DTXSID0000001"),
                )
            ],
        )
        run_id = bundle["workflowRunId"]
        bundle_path = output_dir / run_id / "bundle.json"
        bundle_output = output_dir / f"{scenario}_bundle.json"
        bundle_output.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        results.append(
            {
                "scenario": scenario,
                "status": bundle.get("status", "unknown"),
                "bundlePath": str(bundle_path),
                "workflowRunId": run_id,
            }
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP workflow test harness scenarios.")
    parser.add_argument(
        "--mode",
        choices=["offline"],
        default="offline",
        help="Execution mode (offline only for now).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/workflows"),
        help="Directory to store bundle outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "offline":
        results = run_offline_scenarios(args.output_dir)
        print(json.dumps({"mode": "offline", "results": results}, indent=2))
    else:  # pragma: no cover - defensive
        raise ValueError(f"Unsupported mode {args.mode}")


if __name__ == "__main__":
    main()

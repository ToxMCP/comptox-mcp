#!/usr/bin/env python3
"""
Offline demonstration of the GenRA orchestrator workflow.

This script assembles stub resources, runs the orchestrator, and prints the
resulting audit bundle as JSON. It does not contact external services and is
intended for quick smoke checks or onboarding demonstrations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from epacomp_tox import PredictiveRequest, PredictiveTask
from epacomp_tox.orchestrator.offline import build_offline_orchestrator

# --------------------------------------------------------------------------- #
# CLI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the GenRA orchestrator demo workflow."
    )
    parser.add_argument(
        "--identifier", default="50-00-0", help="Input identifier (CASRN/DTXSID)."
    )
    parser.add_argument(
        "--identifier-type",
        default="casrn",
        help="Identifier type (defaults to casrn).",
    )
    parser.add_argument(
        "--scenario",
        default="genra_read_across",
        help="Scenario label for the predictive plan.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the audit bundle JSON (defaults to stdout).",
    )
    parser.add_argument(
        "--persistence-dir",
        type=Path,
        help="Directory for persisted bundles. When omitted, persistence is disabled.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    orchestrator = build_offline_orchestrator(persistence_dir=args.persistence_dir)
    bundle = orchestrator.run_workflow(
        target_identifier=args.identifier,
        identifier_type=args.identifier_type,
        scenarios=[args.scenario],
        predictive_plan=[
            PredictiveTask(
                service="offline_genra",
                scenario=args.scenario,
                request=PredictiveRequest(chemical_identifier="DTXSID0000001"),
            )
        ],
    )

    payload = json.dumps(bundle, indent=2)
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
        print(f"Wrote bundle to {args.output}")
    else:
        print(payload)


if __name__ == "__main__":
    main()

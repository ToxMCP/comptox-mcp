#!/usr/bin/env python3
"""
Utility for inspecting GenRA orchestrator audit bundles.

Examples:
  python scripts/genra_bundle_cli.py list --store audit/genra
  python scripts/genra_bundle_cli.py show <run-id>
  python scripts/genra_bundle_cli.py metadata <run-id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from epacomp_tox import AuditBundleStore  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect GenRA orchestrator audit bundles."
    )
    parser.set_defaults(command=None)
    parser.add_argument(
        "--store",
        type=Path,
        default=Path("audit/genra"),
        help="Base directory containing audit bundles (default: audit/genra).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List stored bundles.")

    show_parser = subparsers.add_parser(
        "show", help="Print bundle JSON for a workflow run."
    )
    show_parser.add_argument("run_id", help="Workflow run identifier.")

    metadata_parser = subparsers.add_parser(
        "metadata", help="Print metadata for a workflow run."
    )
    metadata_parser.add_argument("run_id", help="Workflow run identifier.")

    return parser


def cmd_list(store: AuditBundleStore) -> None:
    rows = store.list_runs()
    if not rows:
        print("No bundles found.")
        return
    for row in rows:
        print(
            f"{row.get('workflowRunId')}  created:{row.get('createdAt')}  checksum:{row.get('bundleChecksum')[:12]}"
        )


def cmd_show(store: AuditBundleStore, run_id: str) -> None:
    bundle = store.load_bundle(run_id)
    print(json.dumps(bundle, indent=2))


def cmd_metadata(store: AuditBundleStore, run_id: str) -> None:
    metadata = store.load_metadata(run_id)
    print(json.dumps(metadata, indent=2))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    store = AuditBundleStore(args.store)

    if args.command == "list":
        cmd_list(store)
    elif args.command == "show":
        cmd_show(store, args.run_id)
    elif args.command == "metadata":
        cmd_metadata(store, args.run_id)
    else:  # pragma: no cover - defensive
        parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()

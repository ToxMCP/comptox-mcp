#!/usr/bin/env python3
"""Live smoke runner for the public interop tools over MCP HTTP transport."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from epacomp_tox.interop_live import (  # noqa: E402
    SmokeError,
    build_parser,
    run_live_interop_suite,
    write_capture_bundle,
)


def main() -> int:
    args = build_parser().parse_args()
    try:
        artifacts = run_live_interop_suite(args)
    except SmokeError as exc:
        print(f"Interop smoke failed: {exc}", file=sys.stderr)
        return 1

    summary = dict(artifacts.summary)
    if args.capture_dir:
        try:
            manifest = write_capture_bundle(
                artifacts,
                capture_dir=args.capture_dir,
                refresh=args.refresh_live_fixtures,
            )
        except SmokeError as exc:
            print(f"Interop smoke failed: {exc}", file=sys.stderr)
            return 1
        summary["capture"] = {
            "directory": str(args.capture_dir),
            "fixtureCount": len(manifest["fixtures"]),
            "manifest": str(Path(args.capture_dir) / "capture_manifest.json"),
        }

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print("Interop live smoke passed.")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

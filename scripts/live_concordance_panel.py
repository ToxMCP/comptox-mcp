#!/usr/bin/env python3
"""Run the live CTX concordance reference panel and emit JSON or Markdown output."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _maybe_reexec_with_project_python() -> None:
    if os.environ.get("EPACOMP_SKIP_VENV_REEXEC") == "1":
        return
    try:
        import pydantic  # noqa: F401

        import ctxpy  # noqa: F401
    except ModuleNotFoundError:
        for candidate in (
            ROOT_DIR / ".venv_live" / "bin" / "python",
            ROOT_DIR / ".venv" / "bin" / "python",
        ):
            if not candidate.exists():
                continue
            probe = subprocess.run(
                [str(candidate), "-c", "import ctxpy, pydantic"],
                check=False,
                capture_output=True,
            )
            if probe.returncode == 0:
                env = dict(os.environ)
                env["EPACOMP_SKIP_VENV_REEXEC"] = "1"
                os.execve(
                    str(candidate),
                    [str(candidate), str(Path(__file__).resolve()), *sys.argv[1:]],
                    env,
                )


_maybe_reexec_with_project_python()

from epacomp_tox.orchestrator.reference_panel import (  # noqa: E402
    build_default_live_concordance_panel,
    generate_live_concordance_panel_report,
    render_live_concordance_panel_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        dest="cases",
        action="append",
        help="Reference-panel case id to run. Repeat to select a subset; default runs the curated panel.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="Numeric concordance mismatch threshold in log units (default: %(default)s).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the report as JSON instead of Markdown.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional path to write the JSON report.",
    )
    parser.add_argument(
        "--output-markdown",
        help="Optional path to write the Markdown report.",
    )
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="Return exit code 0 even if one or more curated expectations fail.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    panel = build_default_live_concordance_panel()
    if args.cases:
        wanted = set(args.cases)
        panel = [case for case in panel if case.case_id in wanted]
        missing = sorted(wanted - {case.case_id for case in panel})
        if missing:
            raise SystemExit(
                f"Unknown live concordance panel case id(s): {', '.join(missing)}"
            )

    report = generate_live_concordance_panel_report(
        panel=panel,
        threshold=args.threshold,
    )
    payload = report.model_dump()
    markdown = render_live_concordance_panel_markdown(report)

    if args.output_json:
        output_json_path = Path(args.output_json)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.output_markdown:
        output_markdown_path = Path(args.output_markdown)
        output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        output_markdown_path.write_text(markdown, encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(markdown)

    if report.summary.all_cases_passed or args.allow_failures:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

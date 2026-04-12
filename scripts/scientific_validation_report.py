#!/usr/bin/env python3
"""Run the offline scientific-validation suite and emit JSON or Markdown output."""

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
        import jsonschema  # noqa: F401
        import pydantic  # noqa: F401
    except ModuleNotFoundError:
        for candidate in (
            ROOT_DIR / ".venv_live" / "bin" / "python",
            ROOT_DIR / ".venv" / "bin" / "python",
        ):
            if not candidate.exists():
                continue
            probe = subprocess.run(
                [str(candidate), "-c", "import jsonschema, pydantic"],
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

from epacomp_tox.orchestrator.validation import (  # noqa: E402
    generate_offline_validation_report,
    render_validation_report_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--persistence-dir",
        default="artifacts/scientific_validation",
        help="Directory used to persist audit bundles for the validation run.",
    )
    parser.add_argument(
        "--scenario",
        dest="scenarios",
        action="append",
        help="Offline scenario to run. Repeat to select a subset; default runs all offline scenarios.",
    )
    parser.add_argument(
        "--target-identifier",
        default="50-00-0",
        help="Target identifier to resolve for the validation run (default: %(default)s).",
    )
    parser.add_argument(
        "--identifier-type",
        default="casrn",
        help="Identifier type for the target identifier (default: %(default)s).",
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    persistence_dir = Path(args.persistence_dir)
    persistence_dir.mkdir(parents=True, exist_ok=True)

    report = generate_offline_validation_report(
        persistence_dir=persistence_dir,
        scenarios=args.scenarios,
        target_identifier=args.target_identifier,
        identifier_type=args.identifier_type,
    )
    payload = report.model_dump()
    markdown = render_validation_report_markdown(report)

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

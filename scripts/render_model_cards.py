#!/usr/bin/env python3
"""Render JSON model cards and guardrail policies to Markdown and HTML."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import indent


def _default_output_dir() -> Path:
    return Path("docs/generated/model_cards")


def _default_html_dir() -> Path:
    return Path("docs/generated/model_cards_html")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_card(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _format_bullets(strings: list[str] | None) -> str:
    if not strings:
        return "- (none)"
    return "\n".join(f"- {item}" for item in strings)


def _format_metrics(metrics: list[dict] | None) -> str:
    if not metrics:
        return "- (none)"
    lines = []
    for item in metrics:
        name = item.get("name", "metric")
        value = item.get("value", "?")
        dataset = item.get("dataset")
        units = item.get("units")
        parts = [f"{name}: {value}"]
        if dataset:
            parts.append(f"dataset={dataset}")
        if units:
            parts.append(f"units={units}")
        lines.append(f"- {' | '.join(parts)}")
    return "\n".join(lines)


def _render_markdown(card: dict, ad_definition: dict | None) -> str:
    model = card.get("modelDetails", {})
    intended = card.get("intendedUse", {})
    ad = card.get("applicabilityDomain", {})
    provenance = card.get("provenance", {})
    enforcement = ad.get("enforcement", {})

    lines = [
        f"# {model.get('name', 'Unknown Model')} (v{model.get('version', '?')})",
        "",
        "## Summary",
        f"- **Schema Version:** {card.get('schemaVersion', 'n/a')}",
        f"- **Model Type:** {model.get('modelType', 'n/a')}",
        f"- **Release Date:** {model.get('releaseDate', 'n/a')}",
        "",
        "## Intended Use",
        f"{intended.get('summary', 'Not documented.')}",
        "",
        "### In Scope",
        _format_bullets(intended.get("inScope")),
        "",
        "### Out of Scope",
        _format_bullets(intended.get("outOfScope")),
        "",
        "### Limitations",
        _format_bullets(intended.get("limitations")),
        "",
        "## Applicability Domain",
        f"{ad.get('summary', 'No applicability domain summary documented.')}",
        "",
        "### Enforcement Policy",
        f"- **Policy:** {enforcement.get('policy', (ad_definition or {}).get('policy', 'block')).upper()}",
        f"- **Error Codes:** {', '.join(enforcement.get('errorCodes', [])) or 'n/a'}",
        "",
        "### Criteria",
    ]

    for criterion in ad.get("criteria", []):
        header = criterion.get("type", "criterion").replace("_", " ").title()
        lines.append(
            f"- **{header}:** {criterion.get('description', '').strip() or 'See parameters.'}"
        )
        parameters = criterion.get("parameters")
        if parameters:
            formatted = "\n".join(
                f"  - {key}: {value}" for key, value in parameters.items()
            )
            lines.append(formatted)

    if not ad.get("criteria"):
        lines.append("- (none)")

    lines.extend(
        [
            "",
            "### Confidence Bands",
        ]
    )
    for band in ad.get("confidenceBands", []):
        actions = _format_bullets(band.get("actions"))
        lines.append(
            f"- **{band.get('label', 'Band')}** (min {band.get('minConfidence', 'n/a')}):"
        )
        lines.append(indent(actions, "  "))

    if not ad.get("confidenceBands"):
        lines.append("- (none)")

    if ad_definition:
        lines.extend(
            [
                "",
                "### Guardrail Definition (metadata/applicability_domains)",
                f"- **Policy:** {ad_definition.get('policy', 'block').upper()}",
                f"- **Error Code:** {ad_definition.get('errorCode', 'n/a')}",
                "- **Criteria:**",
            ]
        )
        criteria = ad_definition.get("criteria", [])
        if criteria:
            for item in criteria:
                ctype = item.get("type", "criterion").replace("_", " ").title()
                lines.append(
                    f"  - {ctype}: {json.dumps({k: v for k, v in item.items() if k != 'type'}, ensure_ascii=False)}"
                )
        else:
            lines.append("  - (none)")

    lines.extend(
        [
            "",
            "## Performance Metrics",
            "### Training / Validation",
            _format_metrics(
                card.get("oecdValidationPrinciples", {})
                .get("goodnessOfFitMetrics", {})
                .get("internalValidation")
            ),
            "",
            "### External Validation",
            _format_metrics(
                card.get("oecdValidationPrinciples", {})
                .get("goodnessOfFitMetrics", {})
                .get("externalValidation")
            ),
            "",
            "## Provenance",
            "- **Source Repositories:**",
            indent(_format_bullets(provenance.get("sourceRepositories")), "  "),
        ]
    )

    review = provenance.get("reviewStatus", {})
    approvals = review.get("approvedBy") or []
    if approvals:
        reviewers = ", ".join(person.get("name", "Reviewer") for person in approvals)
    else:
        reviewers = "Pending"

    lines.extend(
        [
            f"- **Approval Date:** {review.get('approvalDate', 'n/a')}",
            f"- **Approved By:** {reviewers}",
        ]
    )

    checksum = provenance.get("checksum", {})
    if checksum:
        lines.append(
            f"- **Checksum:** {checksum.get('algorithm', 'SHA256')} {checksum.get('value', 'n/a')}"
        )

    return "\n".join(lines).strip() + "\n"


def _render_html(markdown_text: str) -> str:
    """Very small Markdown-to-HTML helper covering the constructs we emit."""
    html_lines: list[str] = ["<html>", "<body>"]
    in_list = False

    for line in markdown_text.splitlines():
        if line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{line[2:].strip()}</h1>")
        elif line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{line[3:].strip()}</h2>")
        elif line.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{line[4:].strip()}</h3>")
        elif line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{line[2:].strip()}</li>")
        elif line.startswith("  - "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{line[4:].strip()}</li>")
        elif line.strip() == "":
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<br/>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{line.strip()}</p>")
    if in_list:
        html_lines.append("</ul>")
    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines)


def render_cards(source_dir: Path, markdown_dir: Path, html_dir: Path) -> list[Path]:
    _ensure_dir(markdown_dir)
    _ensure_dir(html_dir)
    ad_dir = Path("metadata/applicability_domains")
    rendered: list[Path] = []

    for card_path in sorted(source_dir.glob("*.json")):
        card = _load_card(card_path)
        ad_definition = None
        candidate = ad_dir / card_path.name.replace(".json", "_ad.json")
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as handle:
                ad_definition = json.load(handle)

        markdown = _render_markdown(card, ad_definition)
        html = _render_html(markdown)

        markdown_path = markdown_dir / f"{card_path.stem}.md"
        html_path = html_dir / f"{card_path.stem}.html"

        markdown_path.write_text(markdown, encoding="utf-8")
        html_path.write_text(html, encoding="utf-8")
        rendered.extend([markdown_path, html_path])

    return rendered


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render model cards to Markdown and HTML summaries."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("metadata/model_cards"),
        help="Directory containing JSON model cards.",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=_default_output_dir(),
        help="Directory to write Markdown summaries.",
    )
    parser.add_argument(
        "--html-out",
        type=Path,
        default=_default_html_dir(),
        help="Directory to write HTML summaries.",
    )
    args = parser.parse_args()

    rendered = render_cards(args.source, args.markdown_out, args.html_out)
    for path in rendered:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()

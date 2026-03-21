from __future__ import annotations

import json
import re
from pathlib import Path

from epacomp_tox.server import MCPServer

ROOT_DIR = Path(__file__).resolve().parents[1]
README_PATH = ROOT_DIR / "README.md"
SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "tool_catalog_snapshot.json"


def _load_snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _live_catalog() -> dict:
    server = MCPServer(api_key="dummy", validate_health=False)
    return {
        "resource_names": list(server.resources.keys()),
        "tool_names": sorted(tool["name"] for tool in server.get_tools()),
    }


def _extract_readme_tool_names() -> list[str]:
    lines = README_PATH.read_text(encoding="utf-8").splitlines()
    in_catalog = False
    tool_names: list[str] = []
    for line in lines:
        if line.startswith("## Tool catalog"):
            in_catalog = True
            continue
        if in_catalog and line.startswith("### "):
            break
        if not in_catalog or not line.startswith("|"):
            continue
        if line.startswith("| Category |") or line.startswith("| ---"):
            continue
        tool_names.extend(
            token
            for token in re.findall(r"`([^`]+)`", line)
            if re.fullmatch(r"[a-z0-9_]+", token)
        )
    return tool_names


def _extract_readme_resource_names() -> list[str]:
    text = README_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"The default server currently registers .*? public resources: (.+?)\.",
        text,
        flags=re.DOTALL,
    )
    assert match, "README resource summary sentence not found."
    raw_items = match.group(1).replace(" and ", ", ")
    return [
        item.strip().replace(" ", "_") for item in raw_items.split(",") if item.strip()
    ]


def test_tool_catalog_snapshot_matches_live_server() -> None:
    assert _live_catalog() == _load_snapshot()


def test_readme_highlighted_tools_exist_in_live_catalog() -> None:
    snapshot = _load_snapshot()
    live_tools = set(snapshot["tool_names"])
    missing = sorted(set(_extract_readme_tool_names()) - live_tools)
    assert not missing, f"README advertises tools absent from live catalog: {missing}"


def test_readme_resource_summary_matches_live_catalog() -> None:
    snapshot = _load_snapshot()
    assert _extract_readme_resource_names() == snapshot["resource_names"]

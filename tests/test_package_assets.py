from __future__ import annotations

import os
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DATA = ROOT / "src" / "epacomp_tox" / "data"


def _relative_files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".json", ".md"}
    }


def test_packaged_runtime_assets_match_source_copies() -> None:
    source_roots = {
        "contracts/schemas": ROOT / "docs" / "contracts" / "schemas",
        "schemas": ROOT / "schemas",
        "metadata/model_cards": ROOT / "metadata" / "model_cards",
        "metadata/applicability_domains": ROOT / "metadata" / "applicability_domains",
    }
    package_roots = {
        "contracts/schemas": PACKAGE_DATA / "contracts" / "schemas",
        "schemas": PACKAGE_DATA / "schemas",
        "metadata/model_cards": PACKAGE_DATA / "metadata" / "model_cards",
        "metadata/applicability_domains": PACKAGE_DATA
        / "metadata"
        / "applicability_domains",
    }

    for label, source_root in source_roots.items():
        assert _relative_files(package_roots[label]) == _relative_files(source_root)


def test_wheel_contains_runtime_assets_and_instantiates_server(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheelhouse"
    wheel_dir.mkdir()
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--wheel-dir",
            str(wheel_dir),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    assert build.returncode == 0, build.stdout
    wheel = next(wheel_dir.glob("*.whl"))

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    assert (
        "epacomp_tox/data/contracts/schemas/metadata/model_cards.response.schema.json"
        in names
    )
    assert "epacomp_tox/data/schemas/comptoxEvidencePack.v1.json" in names
    assert "epacomp_tox/data/metadata/model_cards/genra_read_across.json" in names

    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(venv_dir)
    bin_dir = "Scripts" if os.name == "nt" else "bin"
    pip = venv_dir / bin_dir / "pip"
    python = venv_dir / bin_dir / "python"
    install = subprocess.run(
        [str(pip), "install", "--no-deps", str(wheel)],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    assert install.returncode == 0, install.stdout

    smoke = subprocess.run(
        [
            str(python),
            "-c",
            (
                "from epacomp_tox.server import MCPServer; "
                "s=MCPServer(api_key='dummy-key'); "
                "names={t['name'] for t in s.get_tools()}; "
                "assert 'metadata_get_model_card' in names; "
                "assert 'get_contract_manifest' in names; "
                "assert s.call_tool('metadata_get_model_card', {}, context={})"
                "['structuredContent']['modelCards']; "
                "assert s.call_tool('metadata_list_applicability_domain', {}, context={})"
                "['structuredContent']['applicabilityDomains']; "
                "assert s.call_tool('get_contract_manifest', {}, context={})"
                "['structuredContent']['responseSchemas']"
            ),
        ],
        cwd=tmp_path,
        env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    assert smoke.returncode == 0, smoke.stdout

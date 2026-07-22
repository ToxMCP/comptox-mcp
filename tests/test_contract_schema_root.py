from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_contracts_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "epacomp_tox"
        / "contracts"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(
        "epacomp_tox_contracts_under_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_contract_schema_root_exists() -> None:
    contracts = load_contracts_module()
    assert (
        contracts.SCHEMA_ROOT / "chemical" / "search_chemical.response.schema.json"
    ).exists()


def test_contract_schema_root_env_override(monkeypatch, tmp_path: Path) -> None:
    schema_root = tmp_path / "contract-schemas"
    chemical_dir = schema_root / "chemical"
    chemical_dir.mkdir(parents=True)
    schema_path = chemical_dir / "search_chemical.response.schema.json"
    schema_path.write_text(json.dumps({"type": "object"}), encoding="utf-8")

    monkeypatch.setenv("EPACOMP_TOX_CONTRACT_SCHEMA_ROOT", str(schema_root))
    reloaded = load_contracts_module()
    try:
        assert reloaded.SCHEMA_ROOT == schema_root
        assert reloaded.load_schema("chemical", "search_chemical.response.schema") == {
            "type": "object"
        }
    finally:
        monkeypatch.delenv("EPACOMP_TOX_CONTRACT_SCHEMA_ROOT", raising=False)


def test_installed_contract_schema_root_is_used_outside_checkout(
    monkeypatch, tmp_path: Path
) -> None:
    contracts = load_contracts_module()
    repository_root = tmp_path / "missing-repository-schemas"
    installed_root = tmp_path / "installed-schemas"
    installed_root.mkdir()

    monkeypatch.setattr(contracts, "_repository_schema_root", lambda: repository_root)
    monkeypatch.setattr(contracts, "_installed_schema_root", lambda: installed_root)

    assert contracts._default_schema_root() == installed_root


def test_distribution_data_files_cover_every_contract_namespace() -> None:
    import tomllib

    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    configured = project["tool"]["setuptools"]["data-files"]
    packaged_namespaces = {Path(destination).name for destination in configured}
    schema_namespaces = {
        path.name for path in Path("docs/contracts/schemas").iterdir() if path.is_dir()
    }

    assert packaged_namespaces == schema_namespaces

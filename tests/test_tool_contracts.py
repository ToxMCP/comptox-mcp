"""Ensure every MCP tool defines a response schema/output schema."""

from epacomp_tox.resources.bioactivity import BioactivityResource
from epacomp_tox.resources.chemical import ChemicalResource
from epacomp_tox.resources.chemical_list import ChemicalListResource
from epacomp_tox.resources.cheminformatics import CheminformaticsResource
from epacomp_tox.resources.exposure import ExposureResource
from epacomp_tox.resources.hazard import HazardResource
from epacomp_tox.resources.metadata import MetadataResource


RESOURCE_FACTORIES = {
    "chemical": lambda: ChemicalResource(api_key="fake"),
    "chemical_list": lambda: ChemicalListResource(api_key="fake"),
    "cheminformatics": lambda: CheminformaticsResource(api_key="fake"),
    "bioactivity": lambda: BioactivityResource(api_key="fake"),
    "exposure": lambda: ExposureResource(api_key="fake"),
    "hazard": lambda: HazardResource(api_key="fake"),
    "metadata": lambda: MetadataResource(api_key="fake"),
}


def test_all_tools_declare_response_schemas() -> None:
    missing = []
    for name, factory in RESOURCE_FACTORIES.items():
        resource = factory()
        for tool in resource.get_tools():
            if not tool.get("responseSchemaRef") and not tool.get("outputSchema"):
                missing.append(f"{name}:{tool['name']}")
    assert not missing, f"Missing response schema for: {', '.join(missing)}"

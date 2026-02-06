from __future__ import annotations

from typing import Any, Dict, List

from epacomp_tox.contracts import schema_ref
from epacomp_tox.metadata import ModelCardFilter, ModelCardStore
from epacomp_tox.metadata.applicability import ApplicabilityDomainStore
from epacomp_tox.resources.base import BaseResource


class MetadataResource(BaseResource):
    """Resource exposing model metadata and applicability domain definitions."""

    def __init__(
        self,
        api_key: str = "",
        *,
        store: ModelCardStore | None = None,
        ad_store: ApplicabilityDomainStore | None = None,
    ):
        super().__init__(api_key)
        self.store = store or ModelCardStore()
        self.ad_store = ad_store or ApplicabilityDomainStore()

    @property
    def name(self) -> str:
        return "metadata"

    @property
    def description(self) -> str:
        return "Model cards, applicability domain definitions, and provenance metadata"

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "metadata_get_model_card",
                "description": "Retrieve CompTox model cards with optional filters and pagination",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model_name": {"type": "string"},
                        "endpoint": {"type": "string"},
                        "compliance": {
                            "type": "string",
                            "enum": ["approved", "draft"],
                        },
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        "cursor": {"type": "string"},
                    },
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "modelCards": {"type": "array"},
                        "nextCursor": {"type": ["string", "null"]},
                    },
                },
                "responseSchemaRef": schema_ref(
                    "metadata", "model_cards.response.schema"
                ),
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "modelCards": {"type": "array"},
                        "nextCursor": {"type": ["string", "null"]},
                    },
                },
            },
            {
                "name": "metadata_list_applicability_domain",
                "description": "List applicability domain reference definitions",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        "cursor": {"type": "string"},
                    },
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "applicabilityDomains": {"type": "array"},
                        "nextCursor": {"type": ["string", "null"]},
                    },
                },
                "responseSchemaRef": schema_ref(
                    "metadata", "applicability_list.response.schema"
                ),
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "applicabilityDomains": {"type": "array"},
                        "nextCursor": {"type": ["string", "null"]},
                    },
                },
            },
            {
                "name": "metadata_get_applicability_domain",
                "description": "Fetch applicability domain configuration for a specific model",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model_name": {"type": "string"},
                    },
                    "required": ["model_name"],
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "version": {"type": "string"},
                        "criteria": {"type": "array"},
                        "policy": {"type": "string"},
                        "errorCode": {"type": "string"},
                        "references": {"type": "array"},
                    },
                },
                "responseSchemaRef": schema_ref(
                    "metadata", "applicability_detail.response.schema"
                ),
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "version": {"type": "string"},
                        "criteria": {"type": "array"},
                        "policy": {"type": "string"},
                        "errorCode": {"type": ["string", "null"]},
                        "references": {"type": "array"},
                    },
                },
            },
        ]

    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "metadata_get_model_card":
            filters = ModelCardFilter(
                model_name=parameters.get("model_name"),
                endpoint_contains=parameters.get("endpoint"),
                compliance=parameters.get("compliance"),
            )
            limit = parameters.get("limit")
            cursor = parameters.get("cursor")
            cards, next_cursor = self.store.list_cards(
                filters=filters, limit=limit, cursor=cursor
            )
            payload = []
            for item in cards:
                data = {
                    "card": item["card"],
                    "checksum": item["checksum"],
                    "lastModified": item["lastModified"],
                }
                payload.append(data)
            return {
                "modelCards": payload,
                "nextCursor": next_cursor,
            }

        if tool_name == "metadata_list_applicability_domain":
            limit = parameters.get("limit")
            cursor = parameters.get("cursor")
            defs, next_cursor = self.ad_store.list_definitions(
                limit=limit, cursor=cursor
            )
            return {
                "applicabilityDomains": defs,
                "nextCursor": next_cursor,
            }

        if tool_name == "metadata_get_applicability_domain":
            model_name = parameters["model_name"]
            definition = self.ad_store.get_definition(model_name)
            if not definition:
                raise ValueError(f"No applicability domain found for {model_name}")
            return definition

        raise ValueError(f"Unknown tool: {tool_name}")

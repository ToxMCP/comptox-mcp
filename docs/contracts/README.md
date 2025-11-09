# Contract Metadata

All MCP tool responses are backed by JSON Schemas stored under `docs/contracts/schemas/`. Whenever you add a new tool or transport surface, follow these steps:

1. **Author the schema** – drop a Draft 2020-12 schema in the appropriate namespace (e.g., `common/`, `hazard/`, `predictive/`). Favor the shared schemas in `docs/contracts/schemas/common/` when possible.
2. **Reference it in the tool definition** – include `"responseSchemaRef": schema_ref("namespace", "file.json")` in the resource's `get_tools()` entry (or expose a concrete `outputSchema`).
3. **Update tests if needed** – `tests/test_tool_contracts.py` enforces that every tool has either a `responseSchemaRef` or `outputSchema`, so missing contracts will fail CI automatically.

This workflow keeps MCP responses stable for downstream agents and makes future schema coverage straightforward.

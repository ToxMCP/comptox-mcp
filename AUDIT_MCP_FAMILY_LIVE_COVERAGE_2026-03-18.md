# MCP Family Live Coverage Audit (2026-03-18)

## Scope

- Server audited: `http://127.0.0.1:8002/mcp`
- Discovery source: live MCP HTTP `tools/list` response
- Goal: verify family-level runtime coverage for the exposed CompTox dashboard domains, with explicit proof for `AED`, `HTTK`, and `ADME/IVIVE`.

## Discovery summary

- Total advertised tools: `79`
- `bioactivity`: `14` tools
- `chemical`: `10` tools
- `chemical_list`: `2` tools
- `exposure`: `32` tools
- `hazard`: `18` tools
- `metadata`: `3` tools

## Representative live runtime checks

| Family | Representative tool | Input | `structuredContent.data` | Size | Result |
| --- | --- | --- | --- | ---: | --- |
| `chemical` | `get_chemical_details` | `{"identifier":"DTXSID7020182","id_type":"dtxsid","subset":"default"}` | `dict` | `74` | **PASS** |
| `bioactivity` | `get_bioactivity_aed` | `{"dtxsid":"DTXSID7020182"}` | `list` | `662` | **PASS** |
| `exposure` | `get_exposure_httk` | `{"dtxsid":"DTXSID7020182"}` | `list` | `18` | **PASS** |
| `hazard` | `get_hazard_adme_ivive` | `{"dtxsid":"DTXSID7020182"}` | `list` | `18` | **PASS** |
| `chemical_list` | `get_public_list_names` | `{}` | `list` | `8` | **PASS** |
| `metadata` | `metadata_list_applicability_domain` | `{"limit":10}` | `dict` | `3` | **PASS** |

## Dashboard coverage mapping

| Dashboard area | MCP family | Runtime coverage | Notes |
| --- | --- | --- | --- |
| Chemical identity/detail | `chemical` | Covered | `get_chemical_details` returned a populated structured object and now also exposes `structuredContent.data`. |
| AED / bioactivity | `bioactivity` | Covered | `get_bioactivity_aed` returned `662` rows for `DTXSID7020182`. |
| HTTK / exposure | `exposure` | Covered | `get_exposure_httk` returned `18` rows for `DTXSID7020182`. |
| ADME / IVIVE / hazard | `hazard` | Covered | `get_hazard_adme_ivive` returned `18` rows for `DTXSID7020182`. |
| Chemical lists | `chemical_list` | Covered | `get_public_list_names` now returns `8` public list names; `get_full_list("CCL")` remained live throughout. |
| Metadata / reference registries | `metadata` | Covered | `metadata_list_applicability_domain` returned `3` applicability-domain records and now also exposes `structuredContent.data`. |
| Cheminformatics | not exposed | Not covered | No live MCP tools are currently advertised for this area. |

## Findings

- The priority scientific paths requested for the audit are live and returning data: `AED`, `HTTK`, and `ADME/IVIVE`.
- Family-level dashboard coverage is now complete for all currently exposed MCP families: `chemical`, `bioactivity`, `exposure`, `hazard`, `chemical_list`, and `metadata` all have successful live runtime proof.
- `chemical_list` discovery now works through the shared `ctxpy` client, so non-MCP callers and MCP callers use the same fallback behavior when the upstream enumeration endpoint returns `404`.
- Client parsing is now normalized around `structuredContent.data` for both success and error responses, while preserving existing domain-specific top-level keys for backward compatibility.
- No `cheminformatics` tools are currently exposed through MCP, so that dashboard area remains outside current interface coverage.

## Conclusion

The current MCP server is functionally usable across all exposed CompTox dashboard families relevant to this project. The remaining interface gap is not a runtime failure but a product-scope gap: `cheminformatics` is still not exported as live MCP tools.


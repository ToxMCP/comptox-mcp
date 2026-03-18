# MCP Patch Verification (2026-03-18)

## Scope

- Server: `http://127.0.0.1:8002/mcp`
- Patch set:
  - restore `chemical_list.get_public_list_names`
  - normalize `structuredContent.data` across success and error responses

## Live verification results

### 1. `get_public_list_names` recovery

- Result: **PASS**
- Runtime behavior: returns a non-error response with `structuredContent.data`
- Returned count: `8`
- Sample values: `CCL`, `CCL1`, `CPDAT`, `CPDATv2`, `CTD`
- Implementation note: upstream CTX list-enumeration endpoint currently returns `404`, so the MCP now falls back to a maintained catalog of verified public list names while `get_full_list(list_name)` continues to use the live CTX API.

### 2. Dict-shaped success responses now expose `structuredContent.data`

- `get_chemical_details(DTXSID7020182)`
  - Result: **PASS**
  - `structuredContent.data`: present
  - Payload type: `dict`
- `metadata_list_applicability_domain(limit=10)`
  - Result: **PASS**
  - `structuredContent.data`: present
  - Backward-compatible top-level keys preserved: `applicabilityDomains`, `nextCursor`, `metadata`

### 3. Error responses now expose `structuredContent.data`

- Probe: `get_chemical_details(DTXSID_NOT_REAL, id_type="dtxsid")`
- Result: **PASS**
- Error semantics preserved: `isError=true`
- Normalization confirmed: `structuredContent.data = null`

## Outcome

The MCP now has a consistent client-facing parsing contract:
- Success responses always expose `structuredContent.data`
- Error responses expose `structuredContent.data = null`
- Existing top-level domain-specific keys remain available for backward compatibility

## Files changed

- `/Volumes/Storage/topotox_space_relief_20260220/mcp_epacomp_tox/src/epacomp_tox/resources/chemical_list.py`
- `/Volumes/Storage/topotox_space_relief_20260220/mcp_epacomp_tox/src/epacomp_tox/server.py`

# EPA CompTox MCP audit

Date: `2026-03-18`

Target server:
- `http://127.0.0.1:8002/mcp`

Audit scope:
- MCP discovery via `tools/list`
- Live tool execution for the priority data families:
  - `AED`
  - `HTTK`
  - `ADME/IVIVE`
- Upstream API reachability using `scripts/check_endpoints.py`

## Executive summary

The live server on `8002` is functional for the priority data families. `AED`, `HTTK`, and `ADME/IVIVE` all returned real data for `DTXSID7020182` (Bisphenol A).

This audit initially surfaced two issues:

1. HTTP `tools/list` only returned the first `50` tools, which hid part of the catalog.
2. The chemical smoke checker used a stale probe URL and produced a false negative.

Both issues are now patched.

Post-fix state:

- HTTP `tools/list` returns the full `79`-tool catalog
- `get_hazard_adme_ivive` is discoverable via `tools/list`
- `scripts/check_endpoints.py --json` passes for chemical, hazard, exposure, and bioactivity when project env is loaded

## Discovery audit

Live `tools/list` now returns `79` tools with `nextCursor: null`.

Priority tool discovery status:

| Tool | In `tools/list` | Callable | Returns data |
| --- | --- | --- | --- |
| `get_bioactivity_aed` | Yes | Yes | Yes |
| `search_httk` | Yes | Yes | Yes |
| `get_exposure_httk` | Yes | Yes | Yes |
| `get_hazard_adme_ivive` | Yes | Yes | Yes |

## Live MCP execution audit

Test substance:
- `DTXSID7020182` (`Bisphenol A`)

### 1. AED

Tool:
- `get_bioactivity_aed`

Observed result:
- HTTP metadata status: `200`
- Data type: `list`
- Record count: `662`
- Sample fields include:
  - `dtxsid`
  - `aeid`
  - `aedVal`
  - `aedType`
  - `httkModel`
  - `httkVersion`
  - `aedValUnit`

Conclusion:
- Functional
- Data-bearing
- Suitable for real audit and downstream analysis

### 2. HTTK

Tools:
- `search_httk`
- `get_exposure_httk`

Observed result for both:
- HTTP metadata status: `200`
- Data type: `list`
- Record count: `18`
- Sample fields include:
  - `dtxsid`
  - `parameter`
  - `measured`
  - `predicted`
  - `model`
  - `species`
  - `percentile`

Sample parameter/model:
- `Css`
- `PBTK`

Conclusion:
- Both HTTK tools are functional
- Both return real HTTK rows
- The two outputs are materially equivalent for this test substance

### 3. ADME/IVIVE

Tool:
- `get_hazard_adme_ivive`

Observed result:
- HTTP metadata status: `200`
- Data type: `list`
- Record count: `18`
- Sample fields include:
  - `dtxsid`
  - `description`
  - `measured`
  - `predicted`
  - `unit`
  - `model`
  - `species`
  - `percentile`

Sample parameter:
- `Clint`

Conclusion:
- Functional
- Data-bearing
- Discoverable through the MCP catalog after the transport patch

## Upstream dependency audit

Command path:
- `scripts/check_endpoints.py --json`

When run with project env loaded, the checker returns:

| Upstream endpoint | Status | Result |
| --- | --- | --- |
| `CTX Chemical API` | `200` | OK |
| `CTX Hazard API` | `200` | OK |
| `CTX Exposure API` | `200` | OK |
| `CTX Bioactivity API` | `200` | OK |

Interpretation:
- Chemical, hazard, exposure, and bioactivity upstreams are reachable and healthy enough for the tested MCP calls.
- The checker now probes the chemical tier with `chemical/detail/search/by-dtxsid/DTXSID7020182`, which matches the live CTX path family used by the server.

## Remaining follow-up

### Finding 1: endpoint matrix documentation still points to `v1` roots

Severity:
- Medium

Why it matters:
- `docs/contracts/endpoint-matrix.md` documents `ctx-api/v1` base roots.
- Direct probe tests against those base roots returned `404`, while the currently functioning CTX probe paths use the non-`v1` endpoint family.

Evidence:
- `docs/contracts/endpoint-matrix.md` lists `https://comptox.epa.gov/ctx-api/v1/chemical` and analogous `v1` roots.
- Direct probes against those base roots returned `404`.
- The patched smoke checker and the live MCP succeed against non-`v1` CTX endpoint paths.

## Bottom line

For the priority areas requested in this audit:

- `AED`: pass
- `HTTK`: pass
- `ADME/IVIVE`: pass

The server retrieves real data for all three target families and now advertises the full catalog correctly over HTTP. The one remaining issue is documentation drift in `docs/contracts/endpoint-matrix.md`.

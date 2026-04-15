# EPA CompTox MCP coverage audit

Date: `2026-03-18`

Target:
- `http://127.0.0.1:8002/mcp`

## Executive summary

After the HTTP catalog patch, the live MCP now advertises the full catalog over `tools/list`:

- total tools: `79`
- `nextCursor`: `null`

Current resource coverage by family:

| Resource family | Tool count |
| --- | ---: |
| `chemical` | 10 |
| `bioactivity` | 14 |
| `exposure` | 32 |
| `hazard` | 18 |
| `chemical_list` | 2 |
| `metadata` | 3 |
| `cheminformatics` | 0 |

## What is covered

The current MCP catalog covers the major CTX dashboard data families represented in this repository:

- chemical discovery and detail lookup
- bioactivity assays, assay chemicals, AED, and AOP lookups
- exposure datasets including `HTTK`, `CPDat`, `SEEM`, `MMDB`, functional use, and CCD
- hazard datasets including `ToxValDB`, `ToxRefDB`, cancer, genetox, `ADME/IVIVE`, `IRIS`, `PPRTV`, and `HAWC`
- public chemical lists
- metadata and applicability-domain assets

Representative live-discovery checks after the patch:

- `search_hazard`: present
- `get_hazard_adme_ivive`: present
- `get_hazard_toxref`: present
- `get_bioactivity_aed`: present
- `search_httk`: present

## What is not covered or not yet surfaced

### 1. Predictive services are not part of the live MCP catalog

The repository contains predictive service code (`GenRA`, `OPERA`, `TEST` wrappers), but these are not currently advertised as MCP tools in the live `79`-tool catalog.

Interpretation:
- CTX dashboard-style data access is broadly covered.
- Predictive micro-services exist in the codebase, but they are not yet exposed through the same MCP discovery surface.

### 2. `cheminformatics` currently contributes zero tools

The `cheminformatics` resource is initialized, but its current tool count is `0`.

Interpretation:
- This is not blocking dashboard data access.
- It is an obvious expansion point if cheminformatics operations are expected to be part of the MCP surface.

## Answer to “do we cover the entire dashboard?”

For the core CTX data tiers used by this server, coverage is strong:

- chemical: yes
- bioactivity: yes
- exposure: yes
- hazard: yes
- metadata/list assets: yes

Two qualifiers remain:

1. “Entire dashboard” is broader than the audited priority families and broader than the CTX API surface used in this repo.
2. Predictive services and cheminformatics are not fully surfaced as MCP tools in the same way as the core CTX data families.

## Bottom line

If the goal is comprehensive MCP coverage of the main CTX dashboard data families, the server is now in good shape and the full catalog is discoverable over HTTP.

If the goal is literal “everything in the repo” or “everything a user may associate with the dashboard,” the remaining visible gaps are:

1. predictive services are not exposed as MCP tools
2. cheminformatics contributes no live tools

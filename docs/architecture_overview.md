# EPA CompTox MCP Architecture Overview

This document describes the current public architecture of the EPA CompTox MCP server.

The key boundary for `v0.2.0` is simple:

- the default public server is an evidence and federation MCP
- it exposes CompTox retrieval resources over MCP
- predictive and orchestrator code in this repository remains experimental until it is explicitly registered, documented, and contract-stabilized

## 1. Public component stack

```
┌───────────────────────────────┐
│ MCP Clients                   │
│  • Codex / Gemini / Claude    │
│  • notebooks / scripts        │
└──────────────┬────────────────┘
               │ JSON-RPC (MCP)
┌──────────────▼────────────────┐
│ FastAPI MCP Transport         │
│  • `/mcp` HTTP                │
│  • `/mcp/ws` WebSocket        │
│  • handshake + discovery      │
│  • validation + audit hooks   │
└──────────────┬────────────────┘
               │
┌──────────────▼────────────────────────────────────────────┐
│ Registered CompTox Resources                              │
│  • chemical            • bioactivity                      │
│  • exposure            • hazard                           │
│  • chemical_list       • cheminformatics                  │
│  • metadata            • interop                          │
└──────────────┬────────────────────────────────────────────┘
               │
┌──────────────▼────────────────────────────────────────────┐
│ Upstream Data Sources                                     │
│  • CTX chemical, bioactivity, exposure, hazard APIs       │
│  • packaged metadata bundles                              │
└───────────────────────────────────────────────────────────┘
```

## 2. Public execution model

The default request path is:

1. MCP transport accepts `initialize`, `tools/list`, or `tools/call`.
2. Tool registry validates the incoming schema.
3. The selected resource calls the relevant CTX or local metadata backend.
4. Output is normalized to MCP payload shape and validated against the configured response schema.
5. The response returns as source-grounded evidence, not as a suite-level decision.

This is the public contract the README and release notes should describe.

## 3. Resource ownership

- `chemical`: identifier resolution, structures, details
- `bioactivity`: ToxCast/Tox21 summaries, assays, AOP crosswalks
- `exposure`: CPDat, HTTK, SEEM, MMDB, CCD
- `hazard`: ToxValDB, ToxRefDB, cancer, genetox, ADME/IVIVE, IRIS, PPRTV, HAWC
- `metadata`: model cards and applicability definitions
- `interop`: portable evidence-pack assembly plus AOP and PBPK handoff builders
- `cheminformatics` and `chemical_list`: supporting utility/catalog helpers

Together these resources make CompTox the suite's Tier-0 evidence ingress layer.

## 4. Experimental modules in-repo

This repository also contains:

- `src/epacomp_tox/predictive/`
- `src/epacomp_tox/orchestrator/`
- related tests, QA notes, and workflow design documents

These modules are valuable internal assets, but they are not part of the default public MCP surface today because `src/epacomp_tox/server.py` does not register them as resources.

Until that changes, documentation must treat them as:

- experimental
- internal
- non-canonical for the public tool catalog

## 5. Validation and release discipline

- Public response contracts live under `docs/contracts/schemas/`.
- Current public schema coverage includes `common/`, `chemical/`, `cheminformatics/`, `hazard/`, `exposure/`, `bioactivity/`, `workflow/`, `metadata/`, and `predictive/`.
- Root portable evidence objects under `schemas/` provide the cross-suite handoff layer, while `docs/contracts/schemas/` remains the MCP response-wrapper layer.
- `tests/test_mcp_conformance_suite.py` and `tests/test_tool_contracts.py` are the current baseline gates for the registered public surface.

## 6. Boundary statement for the suite

CompTox MCP should be documented as:

- a source-grounded evidence and federation MCP
- not the suite orchestrator
- not the owner of OECD AOP semantics
- not the owner of PBPK qualification or internal exposure objects
- not the owner of final NGRA decision logic

That boundary keeps CompTox complementary to AOP MCP, PBPK MCP, O-QT MCP, and the future ToxClaw orchestration layer.

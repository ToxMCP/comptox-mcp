# Changelog

## [Unreleased]

- tightened repository governance with support, intake, review-ownership, and dependency-automation hygiene
- expanded release discipline around public-surface validation and metadata consistency checks
- standardized GitHub workflow job names in preparation for required branch-protection status checks

## [0.2.0] - 2026-03-21

- repositioned the public package and README around CompTox evidence federation
- updated repository URLs from the legacy `senseibelbi/CompTox_MCP` location to `ToxMCP/comptox-mcp`
- clarified that predictive and orchestrator modules remain experimental until they are part of the default registered MCP surface
- aligned architecture and contract documentation with the current default server boundary
- published a portable evidence schema layer under `schemas/` with validated examples for identity, hazard, exposure, bioactivity, AOP linkage, PBPK context, and bundled evidence packs
- added dedicated `hazard/`, `exposure/`, and `bioactivity/` MCP response namespaces for the highest-value evidence tools so they no longer depend only on generic contract wrappers
- added the `interop` resource with workflow contracts for `assemble_comptox_evidence_pack`, `build_aop_linkage_summary`, and `build_pbpk_context_bundle`
- added deterministic release gates for cross-suite AOP/PBPK handoffs plus a public tool-catalog snapshot and README drift checks

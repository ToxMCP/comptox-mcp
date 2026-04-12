# Changelog

## [Unreleased]

- tightened repository governance with support, intake, review-ownership, and dependency-automation hygiene
- expanded release discipline around public-surface validation and metadata consistency checks
- standardized GitHub workflow job names in preparation for required branch-protection status checks
- upgraded GitHub Actions workflow dependencies toward Node 24-compatible versions and opted dependency review into the Node 24 runtime
- pinned GitHub workflow actions to immutable SHAs, added CodeQL scanning, and added workflow-hardening regression coverage
- added a release/workflow-dispatch pipeline that builds distributions, emits a CycloneDX SBOM artifact, and publishes signed provenance/SBOM attestations
- documented online and offline verification of signed release provenance and SBOM attestations for downstream consumers

## [0.2.2] - 2026-04-12

- cleaned the release-facing metadata for a neutral `v0.2.2` patch release without changing the public MCP boundary
- aligned README, architecture notes, release notes, and release metadata tests with the new patch version
- kept the protected-branch release path CI-clean by fixing docs-link hygiene and normalizing formatting/import ordering across touched files

## [0.2.1] - 2026-04-12

- hardened `resolve_chemical_identifier` so partial-name upstream matches no longer masquerade as exact identity
- normalized invalid identifier searches to the documented `not_found` resolver contract instead of surfacing raw upstream 4xx envelopes
- made `/readyz` require an authenticated CTX probe while keeping `/healthz` as a pure liveness check
- stabilized the public `prioritization` and `manifest` resources and additive interop provenance fields
- added CTX-backed interop live-fixture capture plus a reusable `scripts/release_smoke.py` release-validation path
- documented the `v0.2.1` release surface, release notes, and release-prep verification sweep
- continued internal predictive/orchestrator hardening without publishing those modules as default public MCP tools

## [0.2.0] - 2026-03-21

- repositioned the public package and README around CompTox evidence federation
- updated repository URLs from the legacy `senseibelbi/CompTox_MCP` location to `ToxMCP/comptox-mcp`
- clarified that predictive and orchestrator modules remain experimental until they are part of the default registered MCP surface
- aligned architecture and contract documentation with the current default server boundary
- published a portable evidence schema layer under `schemas/` with validated examples for identity, hazard, exposure, bioactivity, AOP linkage, PBPK context, and bundled evidence packs
- added dedicated `hazard/`, `exposure/`, and `bioactivity/` MCP response namespaces for the highest-value evidence tools so they no longer depend only on generic contract wrappers
- added the `interop` resource with workflow contracts for `assemble_comptox_evidence_pack`, `build_aop_linkage_summary`, and `build_pbpk_context_bundle`
- added deterministic release gates for cross-suite AOP/PBPK handoffs plus a public tool-catalog snapshot and README drift checks

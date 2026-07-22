# Changelog

## [Unreleased]

## [0.2.6] - 2026-07-22

- packaged all MCP response schemas in wheel installations instead of relying on a source checkout's `docs/` tree
- added an installed-schema fallback that follows Python's active installation data path
- added regression coverage for installed schema discovery and complete namespace packaging

## [0.2.5] - 2026-07-22

- kept `structuredContent` schema-valid and moved runtime/session provenance to MCP `_meta`
- restored readable, sourced output for `search_chemical` and `resolve_chemical_identifier` in clients that primarily render text content
- defaulted `search_chemical.search_type` to `contains` for simpler agent calls
- stopped translating CompTox 401/403 authentication failures into false `not_found` resolution results
- documented the official EPA API-key request path and added a live Bisphenol A search/resolution release gate
- updated local quickstarts to bind to `127.0.0.1` without development reload processes

## [0.2.4] - 2026-07-20

- fixed MCP discovery responses so `nextCursor` is omitted when pagination is complete instead of being serialized as invalid JSON `null`
- applied the pagination fix consistently to HTTP and WebSocket tool/resource discovery
- restored tool discovery in strict clients including Claude Code 2.1.214
- added regression coverage for absent terminal cursors and string-valued continuation cursors

## [0.2.3] - 2026-04-15

- hardened audit subsystem with SHA-256 content hashing, sequential chain linkage, and tamper-evident event verification
- added privacy-aware audit parameter scrubbing for sensitive identifiers (DTXSID, CASRN, SMILES, InChI, InChIKey)
- captured upstream response provenance in `BaseResource` with `response_hash`, `retrieved_at`, and `retry_count`
- added W3C `traceparent` propagation in HTTP transport and injected runtime provenance into orchestrator bundles
- hardened `AuditBundleStore` with bundle checksums, previous-bundle hash linkage, and chain integrity verification
- defaulted AD clearance to `True` in orchestrator when predictive tasks exist, with explicit opt-out still supported
- added advisory `reviewCheckpoints` metadata to orchestrator bundle outputs
- kept the public MCP boundary unchanged; all changes are internal governance, privacy, and traceability improvements

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

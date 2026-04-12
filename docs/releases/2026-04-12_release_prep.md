# Release Prep Snapshot — 2026-04-12

This document captures the release-readiness sweep completed for `v0.2.1`.

## Scope Confirmed

- Public surface remains evidence federation plus screening prioritization.
- Predictive and orchestrator code remains experimental and unregistered in the default public server.
- Version bump target: `0.2.1`.

## Verification Summary

- ✅ `pytest -q` -> `165 passed in 88.36s`
- ✅ Direct CTX dependency checks passed against:
  - chemical
  - hazard
  - exposure
  - bioactivity
- ✅ `/healthz` returned liveness `ok`
- ✅ `/readyz` returned authenticated CTX readiness
- ✅ HTTP MCP validation:
  - `initialize`
  - `tools/list`
  - `resources/list`
  - `get_contract_manifest`
  - `resolve_chemical_identifier`
  - `prioritize_risk_signals`
  - `assemble_comptox_evidence_pack`
  - `build_aop_linkage_summary`
  - `build_pbpk_context_bundle`
- ✅ WebSocket MCP validation:
  - initialize
  - tools/resources discovery
  - `resolve_chemical_identifier`
- ✅ `scripts/mcp_interop_smoke.py --endpoint http://127.0.0.1:8013/mcp --json`
- ✅ `scripts/release_smoke.py --endpoint http://127.0.0.1:8013/mcp --json`

## Release-Critical Fixes Confirmed

- `resolve_chemical_identifier` no longer treats permissive upstream partial-name matches as exact identity.
- Invalid identifier inputs now collapse to the documented `not_found` contract instead of surfacing raw CTX 4xx envelopes.
- `/readyz` no longer reports success based on generic `/ctx-api/health` reachability alone.

## Known Caveats Accepted For Release

- Partial-name identifier inputs are intentionally ambiguous unless they truly match exactly; downstream agents should prefer `DTXSID` or `CASRN`.
- Some optional MMDB slices still return `404` for specific chemicals and are represented as known data gaps rather than hard failures.
- Predictive/orchestrator modules remain experimental and are not part of the default public tool catalog.

## Checklist

- [x] Bump package version to `0.2.1`
- [x] Update README for the new public contract and release smoke path
- [x] Publish `v0.2.1` release description
- [x] Run full automated test suite
- [x] Run release-oriented live smoke
- [x] Validate authenticated readiness against live CTX

## Recommended Next Step

Tag and publish `v0.2.1` once the release notes and changelog copy are moved into the GitHub release draft.

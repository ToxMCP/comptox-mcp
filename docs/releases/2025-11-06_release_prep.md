# Release Prep Snapshot — 2025-11-06

This document captures the final verification steps before tagging the 0.1.0 release candidate of the EPA CompTox MCP server.

## Test & Verification Summary

- ✅ `pytest` (63/63 passing in 2.12s) on Python 3.10.9.
- ✅ Manual HTTP/WebSocket smoke (initialize, tools/list, search_chemical).
- ✅ Health endpoints (`/healthz`, `/readyz`, `/metrics`) returning `200 OK`.
- ⚠️ ToxPrint endpoints (`search_toxprints`, `batch_search_toxprints`) returning upstream HTTP 500 errors (see `docs/qa/known_issues.md`).

## Release Checklist

- [x] Run full automated test suite (`pytest`).
- [x] Refresh `test_results_summary.md` with current run metadata.
- [x] Capture outstanding defects in `docs/qa/known_issues.md`.
- [x] Verify README quick-start and integration docs reference the latest transport endpoints.
- [ ] Coordinate fix or escalation for ToxPrint outage before tagging release.

## Next Actions

1. Engage CompTox bridge maintainers with the ToxPrint failure context.
2. Re-run the smoke checklist after the upstream fix; update `test_results_summary.md` accordingly.
3. Tag `v0.1.0` once ToxPrint parity is restored, then publish the checklist + summary alongside release notes.

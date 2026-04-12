# MCP Regression Test Matrix

| Area | Primary checks | Commands |
| --- | --- | --- |
| Transport – HTTP | JSON-RPC handshake, tool listing, call flow, error handling | `pytest tests/test_http_transport.py` and `scripts/mcp_http_smoke.sh` |
| Transport – WebSocket | Initialize, streaming events, cancel/timeout handling | `pytest tests/test_websocket_transport.py` |
| Cross-transport parity | Tool catalog/metadata consistency, shared audit logs | `pytest tests/test_mcp_conformance_suite.py` |
| Interop – live MCP | Public interop builders over HTTP transport, partial-data tolerance, handoff object shape, and explicit live fixture refresh workflow | `python scripts/mcp_interop_smoke.py --endpoint http://127.0.0.1:8000/mcp --json`, `python scripts/mcp_interop_smoke.py --endpoint http://127.0.0.1:8000/mcp --capture-dir tests/golden/interop_live --refresh-live-fixtures --json`, and `.github/workflows/live-interop-smoke.yml` |
| Predictive guardrails | Guardrail enforcement, audit bundle persistence | `pytest tests/test_predictive_regression.py` |
| Scientific validation | Offline orchestrator scenario scorecards, evidence-assessment rollups, interop attachment coverage | `python scripts/scientific_validation_report.py --json` and `pytest tests/workflows/test_scientific_validation_report.py` |
| Live concordance panel | CTX-backed ToxVal reference cases with expected observed-concordance outcomes and drift detection | `python scripts/live_concordance_panel.py --json` and `pytest tests/workflows/test_live_concordance_panel.py` |
| CTX connectivity | Live API health, credential validation | `scripts/smoke_ctx.sh` |
| Agent integration | Codex/Gemini/Claude CLI flows | Follow `docs/integration_guides/mcp_integration.md` |

> Keep this matrix referenced in release checklists so regressions cover HTTP + WebSocket transports and agent compatibility.

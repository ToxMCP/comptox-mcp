# MCP Regression Test Matrix

| Area | Primary checks | Commands |
| --- | --- | --- |
| Transport – HTTP | JSON-RPC handshake, tool listing, call flow, error handling | `pytest tests/test_http_transport.py` and `scripts/mcp_http_smoke.sh` |
| Transport – WebSocket | Initialize, streaming events, cancel/timeout handling | `pytest tests/test_websocket_transport.py` |
| Cross-transport parity | Tool catalog/metadata consistency, shared audit logs | `pytest tests/test_mcp_conformance_suite.py` |
| Predictive guardrails | Guardrail enforcement, audit bundle persistence | `pytest tests/test_predictive_regression.py` |
| CTX connectivity | Live API health, credential validation | `scripts/smoke_ctx.sh` |
| Agent integration | Codex/Gemini/Claude CLI flows | Follow `docs/integration_guides/mcp_integration.md` |

> Keep this matrix referenced in release checklists so regressions cover HTTP + WebSocket transports and agent compatibility.

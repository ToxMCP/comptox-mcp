# Transport & Agentic SDK Smoke Checklist

## Prerequisites
- [ ] `CTX_API_KEY` set (or legacy override via `CTX_USE_LEGACY=1` if required).
- [ ] Phase 2 transport running: `uvicorn epacomp_tox.transport.websocket:app --host 127.0.0.1 --port 8000`.
- [ ] Local Agentic SDK environment configured (Python `agentic-sdk` or Node equivalent).
- [ ] `scripts/mcp_ws_client.py` available for manual probing.

## Transport Validation
- [ ] Run `python scripts/mcp_ws_client.py --url ws://127.0.0.1:8000/mcp/ws --list-tools` (expect negotiated protocol `2025-06-18`).
- [ ] Run `scripts/mcp_http_smoke.sh` (or `EPA_MCP_HTTP_ENDPOINT=<url> scripts/mcp_http_smoke.sh`) and confirm the HTTP transport returns protocol version and tool count.
- [ ] Run `python scripts/mcp_interop_smoke.py --endpoint http://127.0.0.1:8000/mcp --json` and confirm all three interop tools return structured handoff objects.
- [ ] Execute `--call-tool search_chemical --arguments '{"query":"toluene","search_type":"equals"}'` (observe streaming events and final result).
- [ ] Trigger cancellation with `--cancel-after-ms 200` and confirm server logs show cancellation handling.
- [ ] Inspect `docs/architecture_overview.md` to confirm deployment settings match staging/production environment (TLS, heartbeat, session limits).

## Agentic SDK Adapter
- [ ] Run `python samples/agentic_sdk/python_phase2_quickstart.py` (confirm events logged until `events/end`).
- [ ] Integrate the adapter into a local Agentic SDK agent and validate a prompt such as “Summarise exposure data for PFAS” produces guardrail-aware responses.
- [ ] For TypeScript, compile `samples/agentic_sdk/ts_phase2_quickstart.ts` and confirm streaming output with `node dist/ts_phase2_quickstart.js`.
- [ ] Capture a session using `scripts/mcp_ws_client.py --record /tmp/mcp.jsonl` for audit trail verification.

## Observability & Logging
- [ ] Verify structured logs contain `requestId`, `sessionId`, `toolName`, and CTX correlation IDs.
- [ ] Ensure heartbeat metrics are visible in monitoring dashboards (idle timeout, connection counts).
- [ ] Scrape `/metrics` once via Prometheus or curl (e.g., `curl http://127.0.0.1:8000/metrics`) and confirm `mcp_sessions_total` and `mcp_capability_sessions_total` appear.
- [ ] Document any anomalies in `docs/operations/transport_runbook.md` (create/update as needed).

## Sign-off
- [x] QA sign-off (Codex, 2025-10-25)
- [x] DX sign-off (Codex, 2025-10-25)

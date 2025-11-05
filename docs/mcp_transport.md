# MCP Transport Compliance Plan

This document captures the transport requirements for Model Context Protocol (MCP) Phase 2, the behaviour expected from the CompTox MCP server, and the gaps in the current implementation (`epacomp_tox.transport.websocket`). It is the contract driver for Task&nbsp;1 subtasks.

## 1. Handshake Lifecycle

1. Client connects to `/mcp/ws` via WebSocket.
2. Client sends `initialize` request (`jsonrpc` 2.0) including:
   - `protocolVersion` (server must negotiate from supported set).
   - `capabilities` requested by client (per MCP spec §3.2).
   - Optional session metadata (auth headers, agent info).
3. Server response must include:
   - Chosen `protocolVersion`.
   - Server `capabilities` object describing supported features.
   - `serverInfo` (name, version, description).
   - `sessionId` (stable for duration of connection).
   - Optional `instructions`.
4. Server emits `notifications/initialized` after successful handshake.
5. Either side may send `ping`/`pong` heartbeats; server should enforce configurable timeout and close idle sessions.
6. When handshake fails (unsupported protocol, auth failure, server not ready) the response must carry JSON-RPC error with MCP-specific codes (`-32001` pending initialization, `-32602` invalid params, etc.).

### Current State

- Server advertises supported protocol versions (`2025-06-18`, `2025-03-26`, `2024-11-05`) and negotiates correctly.
- `notifications/initialized` event emitted.
- Client capability negotiation is persisted per session; `tools.streams`/`tools.cancel` features downgrade when the client opts out.
- Ping/heartbeat logic responds to client `ping` frames and enforces configurable idle timeouts derived from transport settings or client overrides.
- Authentication metadata is included in tool responses so downstream orchestrators can forward bearer tokens and trace identifiers.
- Negotiated capability flags are exposed via `MCPServer.get_transport_metrics()` for transport telemetry dashboards.

### Required Follow-up

- Wire transport metrics feed into central observability dashboards (Prometheus/OpenTelemetry export). Sample configs are provided in `deploy/prometheus_scrape.yaml` and `deploy/otel_collector_metrics.yaml`.

## 2. Discovery Workflows

### Tools

- `tools/list` accepts optional `cursor` and `limit`, returning `tools` array plus `nextCursor` when additional pages remain.
- `capabilities.tools.listChanged` advertises incremental updates; when `true` the server should emit `notifications/tools/updated` when catalog changes.

### Resources

- `resources/list` mirrors `tools/list` behaviour.
- `capabilities.resources.subscribe` enables `resources/subscribe` stream for change notifications.

### Current State

- `tools/list` and `resources/list` implemented with static catalog; pagination and limits ignored.
- Server always returns `nextCursor: null` and sets `listChanged: False`, so real-time updates are not advertised.
- Resource descriptors include URI, name, title, description, MIME type, annotations.
- No subscription support (`subscribe: False`).

### Required Follow-up

- Implement cursor semantics once catalog exceeds single page (design ready, but low priority until needed).
- Honour optional `limit` parameter (currently discarded).
- Track dynamic tool/resource registrations for future phases; keep `listChanged` false until update signalling exists.

## 3. Tool Execution Streams

### Expected Behaviour

- Client issues `tools/call` with:
  - `name` of tool.
  - `arguments` object.
  - Optional `requestId` for client correlation.
- Server must:
  - Validate tool availability and schema; respond with `-32602` for invalid inputs.
  - Begin streaming execution events using `events` channel when `capabilities.tools.streams` negotiated.
  - Emit at least:
    - `events/result` (partial or final payload slices),
    - `events/log` (optional debug),
    - `events/error` when execution fails before completion,
    - `events/end` once execution finishes.
  - Respect cancellation via `tools/cancel` or `notifications/cancel` per spec §4.4.
  - Provide final JSON-RPC response summarising outcome (`result` or `error`).

### Current State

- `tools/call` executes synchronously and returns final result in one response.
- No event streaming or partial results.
- Cancellation not implemented.
- Errors map to JSON-RPC error codes but lack structured MCP error envelopes (`{isError: true, content: ...}` is used instead of event stream).
- Retry/circuit-breaker logic lives inside resource executors but is not surfaced over transport.

### Required Follow-up

- Add streaming support with FastAPI WebSocket send loop:
  - For long-running CTX calls emit progress events (e.g., request accepted, chunk completion).
  - Wrap existing synchronous calls in async tasks to enable cancellation.
- Implement `tools/cancel` handler wiring to underlying task cancellation.
- Adopt MCP error envelope (`events/error` + JSON-RPC error result) with AD guardrail data included in `data`.

## 4. Logging and Diagnostics

- MCP allows optional `logging` capability enabling `logging/event` notifications.
- Current implementation advertises empty `logging` capability and emits no logs.
- Need to expose structured logs (request id, tool name, duration, CTX request id) under opt-in flag.

## 5. Configuration & Deployment

- Endpoint: `/mcp/ws` (FastAPI WebSocket). To meet hardening requirements we must:
  - Add TLS termination guidance and mutual-auth hooks.
  - Provide health endpoint for readiness (outside scope of WebSocket but needed for packaging).
  - Expose configurable session limits (max concurrent connections, per-client rate limits).

## 6. Open Questions

1. **Transport Auth**: Should agents provide per-session bearer/API tokens via handshake params, or do we continue with server-side CTX credentials only?
2. **Capability Negotiation**: Which advanced capabilities (streaming, subscriptions, logging) must be enabled for Phase 2 GA? Need stakeholder sign-off.
3. **Backpressure**: Do we require explicit flow control for large streaming payloads, or are JSON chunk sizes sufficient?
4. **Audit Hooks**: How should transport emit audit events so orchestrator and governance tasks can merge them with workflow logs?
5. **Rate Limiting**: Must transport enforce per-session or per-agent rate limits independent of CTX platform limits?

## 7. Next Steps

Completed: handshake negotiation, capability persistence, discovery pagination, heartbeat enforcement, and streaming/cancellation pipeline as of this iteration.

Remaining priorities:
1. Align streaming error payloads with applicability domain guardrail data and orchestrator audit requirements.
2. Design logging/audit emission format in coordination with Observability workstream (Task&nbsp;6).
3. Capture decisions on authentication and rate limiting before promoting deployment artifacts.

## 8. CLI + Conformance Harness

- `scripts/mcp_ws_client.py` now supports JSONL recording (`--record`), timeout overrides (`--timeout-ms`), and automated cancellation (`--cancel-after-ms`) so transport streams can be inspected end-to-end.
- `tests/test_mcp_conformance_suite.py` provides a deterministic contract harness with golden fixtures in `tests/fixtures/` covering handshake responses and discovery catalog expectations.
- Additional streaming and health checks are validated in `tests/test_websocket_transport.py` and `tests/test_transport_health_endpoints.py`, giving CI coverage for the upgraded transport features.

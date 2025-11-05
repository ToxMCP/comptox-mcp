# MCP Transport Streaming Event Schemas

The WebSocket transport streams tool execution updates via MCP events once a
session has negotiated the `tools.streams` capability. Each event follows the
JSON-RPC 2.0 envelope produced by `MCPWebSocketSession._emit_event`:

```json
{
  "jsonrpc": "2.0",
  "method": "events/<type>",
  "params": { /* event payload */ }
}
```

The following tables document the payload fields emitted for each event type.
Golden fixtures reflecting these shapes live in `tests/fixtures/events_*.json`
and are exercised by `tests/test_websocket_transport.py`.

## `events/log`

| Field | Type | Description |
| --- | --- | --- |
| `sessionId` | `string` | Active MCP session identifier. |
| `requestId` | `string` | Tool invocation identifier associated with the log. |
| `level` | `string` | Log severity (e.g., `info`, `debug`). |
| `message` | `string` | Human-readable message. |
| `timestamp` | `number` | UNIX epoch timestamp (seconds). |

## `events/result`

| Field | Type | Description |
| --- | --- | --- |
| `sessionId` | `string` | Active MCP session identifier. |
| `requestId` | `string` | Tool invocation identifier. |
| `result.structuredContent` | `object \| null` | Structured result payload encoded for MCP (`data`, `metadata`, etc.). |
| `result.content` | `array \| null` | Optional textual content slices. |
| `result.isError` | `boolean` | Indicates whether the result represents an error payload. |

## `events/error`

| Field | Type | Description |
| --- | --- | --- |
| `sessionId` | `string` | Active MCP session identifier. |
| `requestId` | `string` | Tool invocation identifier. |
| `message` | `string` | Error message suitable for clients. |
| `code` | `integer` | MCP / JSON-RPC error code. |
| `data` | `object` | Optional error data (guards, retry hints, etc.). |

## `events/end`

| Field | Type | Description |
| --- | --- | --- |
| `sessionId` | `string` | Active MCP session identifier. |
| `requestId` | `string` | Tool invocation identifier. |
| `status` | `string` | Final status (`ok`, `error`, `cancelled`). |
| `durationMs` | `integer` | Elapsed time in milliseconds. |

The fixtures capture representative payloads and allow downstream tooling to
generate helper types or documentation from a canonical source.

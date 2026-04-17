# Integrating the EPA CompTox MCP Server with Coding Agents

The EPA CompTox MCP server exposes JSON-RPC over HTTP (`/mcp`) and WebSocket (`/mcp/ws`). Any MCP-aware IDE or CLI can connect once you provide the endpoint and headers. This guide outlines the configuration for three popular clients.

> **Prerequisites**
>
> 1. Deploy the MCP server (local or remote) and expose the `/mcp` endpoint.
> 2. Set `CTX_API_KEY` (preferred) or `EPA_COMPTOX_API_KEY` so the server can reach the EPA CompTox API. EPA currently distributes free CTX API keys via `ccte_api@epa.gov`; see the [CTX APIs overview](https://www.epa.gov/comptox-tools/computational-toxicology-and-exposure-apis).
> 3. If you front the MCP server with an auth layer, obtain the access token required by your MCP client.
>
> Replace `http://localhost:8000/mcp` with your deployment URL when following the snippets.

## Codex CLI

1. Create or edit `~/.config/openai/mcp.json` (check the location with `codex --show-config`).
2. Add a provider entry:

```json
{
  "providers": [
    {
      "name": "epa-comptox",
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer <ACCESS_TOKEN>"
      }
    }
  ]
}
```

- Omit the `Authorization` header when running with `BYPASS_AUTH=1`.
- Codex stores binary payloads (e.g., audit bundles) in its output directory; the command response contains the file path.

3. Restart Codex CLI and run:

```bash
codex tools list
codex tools call epa-comptox tools.list | jq '.tools[:5]'
codex tools call epa-comptox tools.call --name "search_chemical" --arguments '{"query":"Benzene","search_type":"equals"}' | jq '.structuredContent.data[0]'
```

## Gemini CLI

1. Update `~/.config/gemini/mcp.json` (or the path reported by `gemini mcp config`).

```json
{
  "providers": {
    "epa-comptox": {
      "transport": "http",
      "endpoint": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer <ACCESS_TOKEN>"
      }
    }
  }
}
```

2. Reload the CLI:

```bash
gemini mcp providers
gemini mcp call epa-comptox tools.list | jq '.tools | length'
gemini mcp call epa-comptox tools.call --name metadata_get_model_card --arguments '{"model_name":"OPERA","limit":1}' | jq '.structuredContent.metadata'
```

- Gemini expects HTTP 204 for notifications; the server handles this automatically.
- For long-running predictive calls set `--timeout` if you customised the heartbeat/handshake timeouts.

## Claude Code / Cursor

1. Open the Claude MCP settings (CLI: `~/.config/claude/mcp.json`; Cursor: MCP configuration panel).
2. Add an HTTP provider:

```json
{
  "name": "epa-comptox",
  "type": "http",
  "url": "http://localhost:8000/mcp",
  "headers": {
    "Authorization": "Bearer <ACCESS_TOKEN>"
  }
}
```

3. Reload Claude Code / Cursor. The tool palette should list `epa-comptox` with the same catalog returned by the HTTP transport.

- Claude supports WebSocket transports as well. Use `ws://localhost:8000/mcp/ws` when you want streaming `events/log` notifications; otherwise the HTTP provider is sufficient.
- Claude presents returned JSON as chat attachments. Click the attachment to view full `structuredContent` payloads.

## Troubleshooting

| Symptom | Likely cause | Suggested fix |
| --- | --- | --- |
| `401 Unauthorized` | Missing/expired access token | Regenerate the Bearer token or disable `BYPASS_AUTH` only for local development. |
| `503 MCP server unavailable` | Server not initialised or CTX health check failing | Check server logs, ensure `CTX_API_KEY` is set, and verify the CTX API host is reachable. |
| `Method not found` errors | Tool name mismatch | Use `tools.list` to inspect available tools; note that names are snake_case. |
| Large JSON responses truncated in chat | Client UI limit | Use the CLI's output file path (e.g., Codex `--output-dir`) or request `structuredContent` sections explicitly. |

For additional automation examples, consult:

- [`tests/test_http_transport.py`](../../tests/test_http_transport.py) for pure HTTP flows.
- [`tests/test_websocket_transport.py`](../../tests/test_websocket_transport.py) for WebSocket streaming and cancellation cases.
- [`scripts/mcp_ws_client.py`](../../scripts/mcp_ws_client.py) for a minimal WebSocket client you can adapt.

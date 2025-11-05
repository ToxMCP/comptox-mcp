#!/usr/bin/env bash
set -euo pipefail

ENDPOINT="${EPA_MCP_HTTP_ENDPOINT:-http://localhost:8000/mcp}"
AUTH_HEADER=""
if [[ -n "${EPA_MCP_BEARER_TOKEN:-}" ]]; then
  AUTH_HEADER="-H Authorization: Bearer ${EPA_MCP_BEARER_TOKEN}"
fi

function rpc() {
  local payload="$1"
  curl -sS ${AUTH_HEADER:+-H "$AUTH_HEADER"} -H 'Content-Type: application/json' -d "$payload" "$ENDPOINT"
}

initialize='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{}}}'
list_tools='{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

rpc "$initialize" | jq '.result.protocolVersion'
rpc "$list_tools" | jq '.result.tools | length'

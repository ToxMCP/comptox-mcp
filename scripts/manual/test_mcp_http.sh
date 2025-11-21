#!/usr/bin/env bash
# Test script to verify MCP HTTP endpoint is working correctly

set -e

MCP_URL="${MCP_URL:-http://127.0.0.1:8001/mcp}"
echo "Testing MCP endpoint at: $MCP_URL"
echo "========================================"

# Test 1: GET request (should work now with our new handler)
echo ""
echo "Test 1: GET /mcp (service descriptor)"
curl -sS -X GET "$MCP_URL" | jq . || echo "Failed to GET $MCP_URL"

# Test 2: List tools
echo ""
echo "Test 2: POST tools/list"
curl -sS -X POST "$MCP_URL" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .

# Test 3: Call search_chemical
echo ""
echo "Test 3: POST tools/call (search_chemical for chlorpyrifos)"
curl -sS -X POST "$MCP_URL" \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc":"2.0",
    "id":"2",
    "method":"tools/call",
    "params":{
      "name":"search_chemical",
      "arguments":{"query":"chlorpyrifos","search_type":"contains"}
    }
  }' | jq .

echo ""
echo "========================================"
echo "All tests completed!"
echo ""
echo "If all tests passed, your MCP server is healthy."
echo "You can now use it from Codex with:"
echo "  url = \"$MCP_URL\""
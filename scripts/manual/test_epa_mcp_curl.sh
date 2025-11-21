#!/bin/bash
# EPA CompTox MCP Server Test Script
# Tests the MCP server endpoints using curl

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

MCP_URL="${MCP_URL:-http://127.0.0.1:8001/mcp}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8001/healthz}"

echo -e "${BLUE}=== EPA CompTox MCP Server Test Suite ===${NC}"
echo "Testing server at: $MCP_URL"
echo ""

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local expected_status="$2"
    shift 2
    
    echo -e "${YELLOW}Test: ${test_name}${NC}"
    
    # Run curl and capture both response and status code
    response=$(curl -sS -w "\n%{http_code}" "$@" 2>&1)
    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$status_code" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASSED (HTTP $status_code)${NC}"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAILED (Expected HTTP $expected_status, got $status_code)${NC}"
        echo "$body"
        ((TESTS_FAILED++))
    fi
    echo ""
}

# Test 1: Health check
run_test "Health Check (GET /healthz)" "200" \
    "$HEALTH_URL"

# Test 2: MCP Probe (GET)
run_test "MCP Probe (GET /mcp)" "200" \
    "$MCP_URL"

# Test 3: Initialize handshake
run_test "Initialize Handshake" "200" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }'

# Test 4: List tools
run_test "List Tools" "200" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }'

# Test 5: Search for chlorpyrifos
run_test "Search Chemical: chlorpyrifos" "200" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "search_chemical",
            "arguments": {
                "query": "chlorpyrifos",
                "search_type": "contains"
            }
        }
    }'

# Test 6: Invalid JSON-RPC version (should fail)
run_test "Invalid JSON-RPC Version (Expected Failure)" "400" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "1.0",
        "id": 4,
        "method": "tools/list",
        "params": {}
    }'

# Test 7: Unknown method (should fail)
run_test "Unknown Method (Expected Failure)" "404" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 5,
        "method": "unknown/method",
        "params": {}
    }'

# Test 8: Ping
run_test "Ping" "200" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 6,
        "method": "ping",
        "params": {}
    }'

# Summary
echo -e "${BLUE}=== Test Summary ===${NC}"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
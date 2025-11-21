#!/bin/bash
# Test script for legacy resource:// URI format compatibility
# This tests the backward compatibility shim for Codex clients

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

MCP_URL="${MCP_URL:-http://127.0.0.1:8001/mcp}"

echo -e "${BLUE}=== EPA CompTox Legacy URI Compatibility Test ===${NC}"
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

echo -e "${BLUE}--- Modern tools/call Format (Baseline) ---${NC}"
echo ""

# Test 1: Modern format - search_chemical via tools/call
run_test "Modern Format: search_chemical via tools/call" "200" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_chemical",
            "arguments": {
                "query": "chlorpyrifos",
                "search_type": "contains"
            }
        }
    }'

echo -e "${BLUE}--- Legacy resource:// URI Format (Compatibility Shim) ---${NC}"
echo ""

# Test 2: Legacy format - search_chemical via resources/read with tool URI
run_test "Legacy Format: search_chemical via resource://chemical/tool/search_chemical" "200" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 2,
        "method": "resources/read",
        "params": {
            "uri": "resource://chemical/tool/search_chemical?query=chlorpyrifos&search_type=contains"
        }
    }'

# Test 2b: Legacy format without /tool/ segment - should still map to tools/call
run_test "Legacy Format: search_chemical via resource://chemical/search_chemical" "200" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 22,
        "method": "resources/read",
        "params": {
            "uri": "resource://chemical/search_chemical?query=chlorpyrifos&search_type=contains"
        }
    }'

# Test 3: Legacy format with different tool - get_chemical_details
run_test "Legacy Format: get_chemical_details via resource URI" "200" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 3,
        "method": "resources/read",
        "params": {
            "uri": "resource://chemical/tool/get_chemical_details?dtxsid=DTXSID7020458"
        }
    }'

# Test 4: Legacy format with numeric parameter (should coerce to int)
run_test "Legacy Format: list_chemicals with numeric limit" "200" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 4,
        "method": "resources/read",
        "params": {
            "uri": "resource://chemical/tool/list_chemicals?limit=5"
        }
    }'

# Test 5: Standard resource read (non-tool URI) should still work
run_test "Standard Resource Read: resource://chemical" "200" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 5,
        "method": "resources/read",
        "params": {
            "uri": "resource://chemical"
        }
    }'

# Test 6: Invalid tool URI (should fail gracefully)
run_test "Invalid Tool URI (Expected Failure)" "400" \
    -X POST "$MCP_URL" \
    -H 'Content-Type: application/json' \
    -d '{
        "jsonrpc": "2.0",
        "id": 6,
        "method": "resources/read",
        "params": {
            "uri": "resource://chemical/tool/"
        }
    }'

# Summary
echo -e "${BLUE}=== Test Summary ===${NC}"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Legacy URI compatibility is working.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi

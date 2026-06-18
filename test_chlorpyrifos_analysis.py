#!/usr/bin/env python3
"""A direct test script for invoking the search_chemical tool."""

import json
import sys

import requests

MCP_URL = "http://127.0.0.1:8001/mcp"


def call_search_chemical(query: str, search_type: str = "contains"):
    """Directly calls the search_chemical tool via JSON-RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": "chlorpyrifos_test",
        "method": "tools/call",
        "params": {
            "name": "search_chemical",
            "arguments": {"query": query, "search_type": search_type},
        },
    }

    print("=" * 60)
    print(f"Attempting to call 'search_chemical' with query: '{query}'")
    print(f"Target URL: {MCP_URL}")
    print(f"Payload:\n{json.dumps(payload, indent=2)}")
    print("=" * 60)

    try:
        response = requests.post(MCP_URL, json=payload, timeout=20)

        print(f"\nResponse Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                print("\n✓ SUCCESS: Server returned a result.")
                print(
                    f"Result Preview:\n{json.dumps(result['result'], indent=2)[:500]}..."
                )
                return True
            elif "error" in result:
                print(f"\n✗ FAILURE: Server returned a JSON-RPC error.")
                print(f"Error Details:\n{json.dumps(result['error'], indent=2)}")
                return False
            else:
                print(f"\n✗ FAILURE: Unexpected JSON response structure.")
                print(f"Response Body:\n{response.text}")
                return False
        else:
            print(f"\n✗ FAILURE: HTTP request failed.")
            print(f"Response Body:\n{response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"\n✗ FATAL: Connection to the server failed.")
        print(f"  Error: {e}")
        print(
            f"  Is the EPA CompTox MCP server running? Try './scripts/manual/start_epa_mcp.sh'"
        )
        return False


def main():
    """Run the chlorpyrifos test."""
    success = call_search_chemical("chlorpyrifos")

    print("\n" + "=" * 60)
    if success:
        print(
            "✓ Test Passed. The 'tools/call' method for 'search_chemical' is working correctly."
        )
        print("  The server is capable of performing the analysis.")
        print("  The issue likely lies in how Codex is formatting its request.")
        return 0
    else:
        print("✗ Test Failed. The server did not successfully execute the tool call.")
        print("  Review the error messages above to diagnose the server-side issue.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

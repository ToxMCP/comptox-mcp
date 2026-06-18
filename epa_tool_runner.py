#!/usr/bin/env python3
"""
A command-line wrapper to call EPA CompTox MCP tools via JSON-RPC.

This script acts as a bridge for clients like Codex that can discover MCP
tools but lack a built-in method to execute the generic 'tools/call' method.

Usage:
  python epa_tool_runner.py --tool <tool_name> --args '<json_arguments>'

Examples:
  # Search for a chemical
  python epa_tool_runner.py --tool search_chemical --args '{"query": "chlorpyrifos", "search_type": "contains"}'

  # Get hazard information for a chemical by DTXSID
  python epa_tool_runner.py --tool get_hazard_toxval --args '{"dtxsid": "DTXSID4020458"}'
"""

import argparse
import json
import sys

import requests

MCP_URL = "http://127.0.0.1:8001/mcp"


def call_mcp_tool(tool_name: str, arguments: dict):
    """Constructs and sends a JSON-RPC request to call a specific tool."""
    payload = {
        "jsonrpc": "2.0",
        "id": f"tool_runner_{tool_name}",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    try:
        response = requests.post(MCP_URL, json=payload, timeout=300)

        if response.status_code == 200:
            # Print the raw JSON response to stdout for the calling process
            print(response.text)
            return 0
        else:
            sys.stderr.write(
                f"Error: HTTP request failed with status code {response.status_code}\n"
            )
            sys.stderr.write(response.text + "\n")
            return 1

    except requests.exceptions.RequestException as e:
        sys.stderr.write(f"FATAL: Connection to MCP server failed.\n")
        sys.stderr.write(f"Error: {e}\n")
        sys.stderr.write(f"Is the server running at {MCP_URL}?\n")
        return 1


def main():
    """Parse arguments and execute the tool call."""
    parser = argparse.ArgumentParser(description="Call an EPA CompTox MCP tool.")
    parser.add_argument(
        "--tool",
        required=True,
        help="The name of the tool to call (e.g., 'search_chemical').",
    )
    parser.add_argument(
        "--args", required=True, help="A JSON string with the arguments for the tool."
    )

    args = parser.parse_args()

    try:
        arguments_dict = json.loads(args.args)
    except json.JSONDecodeError:
        sys.stderr.write("Error: --args parameter is not a valid JSON string.\n")
        sys.stderr.write("Please wrap the JSON in single quotes.\n")
        sys.stderr.write('Example: --args \'{"query": "caffeine"}\'\n')
        return 1

    return call_mcp_tool(args.tool, arguments_dict)


if __name__ == "__main__":
    sys.exit(main())

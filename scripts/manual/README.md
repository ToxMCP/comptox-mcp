Manual helper scripts used for ad hoc local verification and debugging live outside the public package surface.

- `start_epa_mcp.sh`: starts the local MCP server for manual testing.
- `test_epa_mcp_curl.sh`, `test_mcp_http.sh`, `test_legacy_uri.sh`: shell-based smoke checks for the transport layer.
- `epa_tool_runner.py`: JSON-RPC helper for direct `tools/call` execution against a local server.
- `test_api.py`, `test_chlorpyrifos_analysis.py`: one-off API probing scripts kept for manual diagnosis.
- `extract_api_structure.py`: captures a local CTX client method snapshot into ignored `artifacts/`.

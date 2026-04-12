# Development Guide

This document provides guidance for developers who want to extend or modify the EPA CompTox MCP implementation.

The released `v0.2.2` public server is an evidence-and-federation MCP. Predictive and orchestrator code still exists in-repo, but it is not part of the default public MCP surface unless explicitly registered and documented.

## Project Structure

```
mcp_epacomp_tox/
├── src/epacomp_tox/
│   ├── transport/            # MCP HTTP + WebSocket transport
│   ├── orchestrator/         # Experimental GenRA/orchestration assets
│   ├── predictive/           # Experimental predictive micro-server assets
│   ├── metadata/             # Model cards, applicability-domain stores, validators
│   ├── resources/            # Public CTX resource adapters + interop builders
│   ├── health.py             # Liveness/readiness probes
│   ├── server.py             # MCP server façade with tool/catalog wiring
│   ├── client.py             # Lightweight MCP client for offline usage
│   └── config.py             # Central configuration helpers (env parsing)
├── scripts/
│   ├── mcp_ws_client.py      # Manual MCP conformance/smoke harness
│   ├── mcp_interop_smoke.py  # Live interop smoke runner for the public handoff tools
│   ├── smoke_ctx.sh          # CTX live smoke tests
│   └── build_docs.sh         # MkDocs build wrapper (added in Task 7.6)
├── docs/                     # Markdown guides, architecture diagrams, runbooks
├── metadata/                 # JSON model cards, applicability domains, audit policy files
├── schemas/                  # JSON Schemas (model cards, policy definitions)
├── tests/
│   ├── test_mcp_conformance_suite.py
│   ├── test_predictive_regression.py
│   ├── test_transport_health_endpoints.py
│   └── ... (see repository for full coverage)
├── pyproject.toml            # Build + dependency metadata
└── README.md                 # Project overview and quickstarts
```

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/ToxMCP/comptox-mcp.git
cd comptox-mcp
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the package with development extras:
```bash
pip install -e .[dev]
```

## Running Tests

Run the full test suite with pytest (includes HTTP/WebSocket transport coverage):
```bash
pytest
```

Generate coverage and stricter MCP transport checks:
```bash
pytest --cov=epacomp_tox tests/test_http_transport.py tests/test_websocket_transport.py
```

Run the live interop smoke against a running server when you need runtime confirmation of the AOP/PBPK handoff paths:
```bash
python scripts/mcp_interop_smoke.py --endpoint http://127.0.0.1:8000/mcp --json
```

Refresh the reviewable live interop fixtures only when upstream CTX drift has been accepted deliberately:
```bash
python scripts/mcp_interop_smoke.py \
  --endpoint http://127.0.0.1:8000/mcp \
  --capture-dir tests/golden/interop_live \
  --refresh-live-fixtures \
  --json
```

## Code Style

This project follows PEP 8 style guidelines. You can use black and isort to format your code:
```bash
black src tests
isort src tests
```

## Adding a New Resource

Public MCP tools are registered directly from resources in `src/epacomp_tox/resources/`. To add a new public resource:

1. Create a new file in the `src/epacomp_tox/resources/` directory:
```python
# src/epacomp_tox/resources/new_resource.py
from typing import Dict, List, Any, Optional
import ctxpy as ctx
from .base import BaseResource

class NewResource(BaseResource):
    """
    MCP resource for new EPA CompTox data.
    
    Provides access to new data type.
    """
    
    @property
    def name(self) -> str:
        return "new_resource"
    
    @property
    def description(self) -> str:
        return "Access to new data type"
    
    def __init__(self, api_key: str):
        """
        Initialize the new resource.
        
        Args:
            api_key: EPA CompTox API key.
        """
        super().__init__(api_key)
        # Initialize client if needed
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of tools provided by this resource.
        
        Returns:
            List of tool definitions.
        """
        return [
            {
                "name": "new_tool",
                "description": "Description of the new tool",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "param1": {
                            "type": "string",
                            "description": "Description of param1"
                        }
                    },
                    "required": ["param1"]
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """
        Execute a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to execute.
            parameters: Parameters for the tool.
            
        Returns:
            Tool execution result.
            
        Raises:
            ValueError: If the tool is not found or parameters are invalid.
        """
        if tool_name == "new_tool":
            return self.new_tool(
                param1=parameters["param1"]
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def new_tool(self, param1: str) -> Any:
        """
        Implementation of the new tool.
        
        Args:
            param1: Description of param1.
            
        Returns:
            Tool result.
        """
        # Implement the tool
        return {"result": f"Processed {param1}"}
```

2. Register the resource inside the server/orchestrator wiring (e.g., `_initialize_resources` in `src/epacomp_tox/server.py` and any orchestrator stage that consumes it):
```python
def _initialize_resources(self) -> Dict[str, Any]:
    ...
    from .resources.new_resource import NewResource
    resources["new_resource"] = NewResource(self.api_key)
    return resources
```

3. Add response schemas for new public tools, preferably under a dedicated namespace in `docs/contracts/schemas/`, and wire them with `responseSchemaRef` or `outputSchema`.

4. If the resource publishes suite-facing portable objects, add or update root schemas in `schemas/` plus examples under `schemas/examples/`.

5. Update tests:

   - `tests/test_tool_contracts.py` for schema declarations
   - `tests/test_mcp_conformance_suite.py` if the public discovery surface changes
   - `tests/test_tool_catalog_snapshot.py` if the public tool catalog changes
   - resource/domain tests such as `tests/test_domain_contracts.py` or `tests/test_interop_resource.py`

Refer to `docs/architecture_overview.md` for the current public boundary and to `docs/contracts/README.md` for schema-layer expectations.

## Adding a New Tool to an Existing Resource

To add a new tool to an existing resource:

1. Add the tool definition to the resource's `get_tools` method:
```python
def get_tools(self) -> List[Dict[str, Any]]:
    """
    Get a list of tools provided by this resource.
    
    Returns:
        List of tool definitions.
    """
    return [
        # Existing tools...
        {
            "name": "new_tool",
            "description": "Description of the new tool",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Description of param1"
                    }
                },
                "required": ["param1"]
            }
        }
    ]
```

2. Add the tool implementation to the resource's `execute_tool` method:
```python
def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
    """
    Execute a tool with the given parameters.
    
    Args:
        tool_name: Name of the tool to execute.
        parameters: Parameters for the tool.
        
    Returns:
        Tool execution result.
        
    Raises:
        ValueError: If the tool is not found or parameters are invalid.
    """
    if tool_name == "existing_tool":
        # Existing tool implementation...
    elif tool_name == "new_tool":
        return self.new_tool(
            param1=parameters["param1"]
        )
    else:
        raise ValueError(f"Unknown tool: {tool_name}")
```

3. Add the tool implementation method to the resource:
```python
def new_tool(self, param1: str) -> Any:
    """
    Implementation of the new tool.
    
    Args:
        param1: Description of param1.
        
    Returns:
        Tool result.
    """
    # Implement the tool
    return {"result": f"Processed {param1}"}
```

4. Add tests for the new tool and update contract coverage if it changes the public surface.

## Customizing the API Integration

The API integration is designed to be customizable through the `EPACompToxAuth` class in `src/epacomp_tox/auth.py`. Users can extend this class to add custom authentication logic:

```python
from epacomp_tox.auth import EPACompToxAuth

class CustomAuth(EPACompToxAuth):
    """Custom authentication handler for EPA CompTox APIs."""
    
    def __init__(self, api_key=None, additional_param=None):
        """
        Initialize with API key and additional parameters.
        
        Args:
            api_key: EPA CompTox API key.
            additional_param: Additional parameter for custom authentication.
        """
        super().__init__(api_key)
        self.additional_param = additional_param
        
    def get_headers(self):
        """
        Get authentication headers with custom modifications.
        
        Returns:
            Dictionary of headers including the API key and custom headers.
        """
        headers = super().get_headers()
        headers["X-Custom-Header"] = self.additional_param
        return headers
```

## Deployment

### Server Deployment

The MCP server can be deployed as a web service using frameworks like Flask, FastAPI, or Django. Here's an example using Flask:

```python
from flask import Flask, request, jsonify
from epacomp_tox.server import MCPServer
import os

app = Flask(__name__)
server = MCPServer(api_key=os.environ.get("EPA_COMPTOX_API_KEY"))

@app.route("/resources", methods=["GET"])
def get_resources():
    return jsonify(server.get_resources())

@app.route("/tools", methods=["GET"])
def get_tools():
    return jsonify(server.get_tools())

@app.route("/execute", methods=["POST"])
def execute_tool():
    data = request.json
    tool_name = data.get("tool_name")
    parameters = data.get("parameters", {})
    result = server.execute_tool(tool_name, parameters)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

### Package Distribution

To distribute the package:

1. Update the version in `pyproject.toml`.
2. Build the package (requires `build`):
```bash
python -m pip install --upgrade build
python -m build
```

3. Upload to PyPI:
```bash
pip install twine
twine upload dist/*
```

### Updating dependency pins

1. Edit `pyproject.toml` to adjust the desired version ranges.
2. Reinstall the project with dev extras to pick up the changes:
   ```bash
   pip install -e .[dev] --upgrade
   ```
3. Run the test suite (`pytest`) to confirm compatibility.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

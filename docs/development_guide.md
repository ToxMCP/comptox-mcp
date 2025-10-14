# Development Guide

This document provides guidance for developers who want to extend or modify the EPAComp Tox MCP implementation.

## Project Structure

```
mcp_epacomp_tox/
├── src/
│   └── epacomp_tox/
│       ├── __init__.py
│       ├── server.py         # MCP server implementation
│       ├── client.py         # MCP client implementation
│       ├── auth.py           # Authentication handler
│       └── resources/        # Resource implementations
│           ├── __init__.py
│           ├── base.py       # Base resource class
│           ├── chemical.py   # Chemical resource
│           ├── exposure.py   # Exposure resource
│           ├── hazard.py     # Hazard resource
│           ├── chemical_list.py  # ChemicalList resource
│           └── cheminformatics.py  # Cheminformatics resource
├── tests/
│   ├── __init__.py
│   ├── test_mcp.py           # Tests for server, client, and auth
│   ├── test_resources.py     # Tests for resources
│   └── integration_test.py   # Integration tests
├── docs/
│   ├── api_reference.md      # API reference documentation
│   └── agentic_sdk_integration.md  # Guide for Agentic SDK integration
├── setup.py                  # Package setup file
└── README.md                 # Project README
```

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/mcp_epacomp_tox.git
cd mcp_epacomp_tox
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the package in development mode:
```bash
pip install -e .
```

4. Install development dependencies:
```bash
pip install pytest pytest-cov black isort mypy
```

## Running Tests

Run the tests using pytest:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=epacomp_tox
```

## Code Style

This project follows PEP 8 style guidelines. You can use black and isort to format your code:
```bash
black src tests
isort src tests
```

## Adding a New Resource

To add a new resource to the MCP:

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
                "parameters": {
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

2. Add the new resource to the server's `_initialize_resources` method in `src/epacomp_tox/server.py`:
```python
def _initialize_resources(self) -> Dict[str, Any]:
    """Initialize and return all available resources."""
    from .resources.chemical import ChemicalResource
    from .resources.exposure import ExposureResource
    from .resources.hazard import HazardResource
    from .resources.chemical_list import ChemicalListResource
    from .resources.cheminformatics import CheminformaticsResource
    from .resources.new_resource import NewResource  # Add this line
    
    return {
        "chemical": ChemicalResource(self.api_key),
        "exposure": ExposureResource(self.api_key),
        "hazard": HazardResource(self.api_key),
        "chemical_list": ChemicalListResource(self.api_key),
        "cheminformatics": CheminformaticsResource(self.api_key),
        "new_resource": NewResource(self.api_key),  # Add this line
    }
```

3. Add tests for the new resource in `tests/test_resources.py`.

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
            "parameters": {
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

4. Add tests for the new tool in `tests/test_resources.py`.

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

1. Update the version in `setup.py`.
2. Build the package:
```bash
python setup.py sdist bdist_wheel
```

3. Upload to PyPI:
```bash
pip install twine
twine upload dist/*
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

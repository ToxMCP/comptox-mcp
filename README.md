# EPAComp Tox Model Context Protocol (MCP)

A Model Context Protocol implementation for EPA's Computational Toxicology and Exposure APIs, designed for integration with LLM agents through the Agentic SDK.

## Overview

This package provides a standardized interface for LLM agents to access and interact with the EPA's Computational Toxicology and Exposure data. It follows the Model Context Protocol (MCP) architecture, which defines a client-server pattern for providing context to LLMs.

## Features

- **Standardized API**: Access EPA CompTox data through a consistent interface
- **LLM Agent Integration**: Designed for use with the Agentic SDK
- **Comprehensive Coverage**: Includes Chemical, Exposure, Hazard, ChemicalList, and Cheminformatics data
- **Tool Definitions**: Predefined tools for LLM agents to use
- **Authentication Handling**: Manages EPA API authentication

## Installation

```bash
pip install epacomp-tox-mcp
```

## Usage

### Server Setup

```python
from epacomp_tox.server import MCPServer

# Initialize the server with your EPA CompTox API key
server = MCPServer(api_key="your-api-key")

# Get available resources
resources = server.get_resources()
print(resources)

# Get available tools for LLM agents
tools = server.get_tools()
print(tools)

# Execute a tool
result = server.execute_tool(
    "search_chemical", 
    {"query": "toluene", "search_type": "equals"}
)
print(result)
```

### Client Setup

```python
from epacomp_tox.client import MCPClient

# Initialize the client with the server URL
client = MCPClient(server_url="http://localhost:8000")

# Get available tools
tools = client.get_tools()
print(tools)

# Execute a tool
result = client.execute_tool(
    "search_chemical", 
    {"query": "toluene", "search_type": "equals"}
)
print(result)
```

### Integration with Agentic SDK

```python
from agentic_sdk import Agent
from epacomp_tox.client import MCPClient

# Initialize the MCP client
mcp_client = MCPClient(server_url="http://localhost:8000")

# Get the tools
tools = mcp_client.get_tools()

# Initialize the agent with the tools
agent = Agent(tools=tools)

# Use the agent
response = agent.run("Find information about the chemical toluene")
print(response)
```

## API Reference

### Server

The `MCPServer` class provides the core functionality for the MCP server.

```python
MCPServer(api_key=None)
```

- `api_key`: EPA CompTox API key. If not provided, resolves in order: `CTX_API_KEY` (preferred) → `EPA_COMPTOX_API_KEY` → `ctx_x_api_key`.

Migration env vars
- `CTX_API_BASE_URL` (default: `https://comptox.epa.gov/ctx-api`)
- `CTX_USE_LEGACY=1` switches to `https://api-ccte.epa.gov` (until 2025-10-01)
- For ctx-python compatibility, the server also sets `ctx_api_host`, `ctx_api_accept`, and `ctx_x_api_key` envs at runtime.

Methods:

- `get_resources()`: Get a list of all available resources.
- `get_tools()`: Get a list of all available tools for LLM agents.
- `execute_tool(tool_name, parameters)`: Execute a tool with the given parameters.

### Client

The `MCPClient` class provides the client interface for connecting to the MCP server.

```python
MCPClient(server_url=None, api_key=None)
```

- `server_url`: URL of the MCP server. If not provided, will attempt to use environment variable `MCP_EPACOMP_TOX_SERVER_URL`.
- `api_key`: API key for the MCP server, if required. If not provided, will attempt to use environment variable `MCP_EPACOMP_TOX_API_KEY`.

Methods:

- `get_tools()`: Get a list of all available tools for LLM agents.
- `execute_tool(tool_name, parameters)`: Execute a tool with the given parameters.

### Authentication

The `EPACompToxAuth` class handles authentication with the EPA CompTox APIs.

```python
EPACompToxAuth(api_key=None)
```

- `api_key`: EPA CompTox API key.

Methods:

- `get_headers()`: Get authentication headers for EPA CompTox API requests.
- `get_api_key()`: Get the API key.

## Available Tools

The MCP provides the following tools for LLM agents:

### Chemical Tools

- `search_chemical`: Search for chemicals by name, CAS-RN, or other identifiers.
- `get_chemical_details`: Get detailed information about a chemical.
- `search_msready`: Search for chemicals by MS-ready properties.

### Exposure Tools

- `search_cpdat`: Search for chemical product and use data from CPDat.
- `search_httk`: Search for high-throughput toxicokinetics data.
- `get_cpdat_vocabulary`: Get controlled vocabulary from CPDat.
- `search_qsurs`: Search for functional use predictions from QSUR models.
- `search_exposures`: Search for exposure pathway predictions or SEEM framework estimates.

### Hazard Tools

- `search_hazard`: Search for chemical hazard data from ToxValDB.
- `batch_search_hazard`: Search for hazard data for multiple chemicals.

### ChemicalList Tools

- `get_public_list_names`: Get names of available public chemical lists.
- `get_full_list`: Get all chemicals in a specific list.

### Cheminformatics Tools

- `search_toxprints`: Search for ToxPrint chemotypes for a chemical.
- `batch_search_toxprints`: Search for ToxPrint chemotypes for multiple chemicals.

## Customizing API Integration

You can customize the API integration by modifying the `EPACompToxAuth` class:

```python
from epacomp_tox.auth import EPACompToxAuth

class CustomAuth(EPACompToxAuth):
    def __init__(self, api_key=None, custom_param=None):
        super().__init__(api_key)
        self.custom_param = custom_param
    
    def get_headers(self):
        headers = super().get_headers()
        headers["Custom-Header"] = self.custom_param
        return headers
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- EPA's Center for Computational Toxicology and Exposure (CCTE) for providing the APIs
- The ctx-python library for providing the Python wrapper for the EPA APIs
- The Model Context Protocol for defining the standardized interface for LLM agents

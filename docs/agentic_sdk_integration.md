# EPAComp Tox MCP Integration with Agentic SDK

This document provides a guide for integrating the EPAComp Tox Model Context Protocol (MCP) with LLM agents using the Agentic SDK.

## Overview

The EPAComp Tox MCP provides a standardized interface for LLM agents to access and interact with the EPA's Computational Toxicology and Exposure data. This guide explains how to integrate it with the Agentic SDK to enable LLM agents to use EPA CompTox data for toxicology-related tasks.

## Prerequisites

- Python 3.7+
- Agentic SDK
- EPA CompTox API key

## Integration Steps

### 1. Install the EPAComp Tox MCP Package

```bash
pip install epacomp-tox-mcp
```

### 2. Set Up the MCP Server

The MCP server handles communication with the EPA CompTox APIs and exposes the data through a standardized interface.

```python
from epacomp_tox.server import MCPServer

# Initialize the server with your EPA CompTox API key
server = MCPServer(api_key="your-api-key")

# Start the server (implementation depends on your deployment strategy)
# For example, using Flask:
from flask import Flask, request, jsonify
import json

app = Flask(__name__)

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

### 3. Configure the MCP Client

The MCP client connects to the server and provides the interface for LLM agents.

```python
from epacomp_tox.client import MCPClient

# Initialize the client with the server URL
client = MCPClient(server_url="http://localhost:8000")
```

### 4. Integrate with Agentic SDK

The Agentic SDK allows you to create LLM agents that can use the MCP tools.

```python
from agentic_sdk import Agent, Tool

# Get the tools from the MCP client
mcp_tools_response = client.get_tools()
mcp_tools = mcp_tools_response["tools"]

# Convert MCP tools to Agentic SDK tools
agentic_tools = []
for tool in mcp_tools:
    agentic_tools.append(
        Tool(
            name=tool["name"],
            description=tool["description"],
            parameters=tool["parameters"],
            function=lambda name=tool["name"], params: client.execute_tool(name, params)
        )
    )

# Create an agent with the tools
agent = Agent(tools=agentic_tools)

# Use the agent
response = agent.run("Find information about the toxicity of toluene")
print(response)
```

### 5. Advanced Integration: Custom Tool Execution

For more control over tool execution, you can implement custom handlers:

```python
def execute_chemical_search(params):
    """Custom handler for chemical search tool."""
    result = client.execute_tool("search_chemical", params)
    # Process the result as needed
    return result

# Create a tool with the custom handler
chemical_search_tool = Tool(
    name="search_chemical",
    description="Search for chemicals by name, CAS-RN, or other identifiers",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term"
            },
            "search_type": {
                "type": "string",
                "description": "Search type: equals, starts-with, or contains",
                "enum": ["equals", "starts-with", "contains"]
            }
        },
        "required": ["query", "search_type"]
    },
    function=execute_chemical_search
)

# Create an agent with the custom tool
agent = Agent(tools=[chemical_search_tool])
```

## Example Use Cases

### 1. Chemical Hazard Assessment

```python
prompt = """
Assess the potential hazards of benzene based on EPA CompTox data. 
Include information about:
1. Human health hazards
2. Environmental hazards
3. Exposure pathways
"""

response = agent.run(prompt)
print(response)
```

### 2. Chemical Comparison

```python
prompt = """
Compare the toxicological profiles of toluene and xylene based on EPA CompTox data.
Focus on:
1. Hazard data
2. Exposure potential
3. Key differences in health effects
"""

response = agent.run(prompt)
print(response)
```

### 3. Chemical Identification

```python
prompt = """
I have a chemical with the following properties:
- Molecular formula: C8H10
- Mass: 106.165 g/mol
- Used as a solvent

Identify this chemical and provide toxicological information from EPA CompTox.
"""

response = agent.run(prompt)
print(response)
```

## Customizing the API Integration

You can customize the API integration by replacing the placeholder in `auth.py` with your own implementation:

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

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Ensure your EPA CompTox API key is valid and properly configured.
2. **Connection Errors**: Verify that the MCP server is running and accessible from the client.
3. **Tool Execution Errors**: Check that the tool parameters match the expected format.

### Debugging

Enable debug logging to get more information about the MCP client-server communication:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Conclusion

By following this guide, you've integrated the EPAComp Tox MCP with the Agentic SDK, enabling LLM agents to access and utilize EPA's computational toxicology and exposure data. This integration allows for sophisticated toxicology-related tasks to be performed by LLM agents, enhancing their capabilities in environmental and health domains.

import os
import sys
from pathlib import Path

# Add the src directory to the Python path
src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))

from epacomp_tox.server import MCPServer
from epacomp_tox.client import MCPClient
from epacomp_tox.auth import EPACompToxAuth

def main():
    """
    Run a simple integration test of the MCP implementation.
    
    This script demonstrates how to use the MCP server and client
    to access EPA CompTox data.
    """
    # Get API key from environment
    api_key = os.environ.get("CTX_API_KEY") or os.environ.get("EPA_COMPTOX_API_KEY")
    if not api_key:
        raise SystemExit("Missing CTX_API_KEY (or EPA_COMPTOX_API_KEY). Set your key in the environment to run integration tests.")
    
    print("=== Testing MCP Server ===")
    
    # Initialize the server
    server = MCPServer(api_key=api_key)
    
    # Get available resources
    print("\nAvailable resources:")
    resources = server.get_resources()
    for resource in resources:
        print(f"- {resource['name']}: {resource['description']}")
    
    # Get available tools
    print("\nAvailable tools:")
    tools = server.get_tools()
    for tool in tools:
        print(f"- {tool['name']}: {tool['description']}")
    
    print("\n=== Testing MCP Client ===")
    
    # Set up environment for client
    os.environ["MCP_EPACOMP_TOX_SERVER_URL"] = "http://localhost:8000"
    
    # Initialize the client
    client = MCPClient()
    
    # Get available tools from client
    print("\nClient tools:")
    tools_response = client.get_tools()
    for tool in tools_response["tools"]:
        print(f"- {tool['name']}: {tool['description']}")
    
    # Execute a tool
    print("\nExecuting tool:")
    result = client.execute_tool(
        "search_chemical", 
        {"query": "toluene", "search_type": "equals"}
    )
    print(f"Result: {result}")
    
    print("\n=== Testing Authentication ===")
    
    # Initialize auth handler
    auth = EPACompToxAuth(api_key=api_key)
    
    # Get headers
    headers = auth.get_headers()
    print(f"Auth headers: {headers}")
    
    print("\nIntegration test completed successfully!")

if __name__ == "__main__":
    main()

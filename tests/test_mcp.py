import os
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest
from unittest.mock import MagicMock, patch

from epacomp_tox.auth import EPACompToxAuth
from epacomp_tox.client import MCPClient

# Now we can import our modules
from epacomp_tox.server import MCPServer


class TestMCPServer(unittest.TestCase):
    """Test cases for the MCP server implementation."""

    def setUp(self):
        """Set up test environment."""
        # Use the API key from environment or a test key
        self.api_key = "test_key"
        # Patch the _initialize_resources method directly on the instance
        with patch.object(MCPServer, "_initialize_resources") as mock_init:
            mock_init.return_value = {}
            self.server = MCPServer(api_key=self.api_key)
            self.server.resources = {
                "chemical": MagicMock(),
                "exposure": MagicMock(),
                "hazard": MagicMock(),
                "chemical_list": MagicMock(),
                "cheminformatics": MagicMock(),
            }
            for resource in self.server.resources.values():
                resource.description = "Test description"
                resource.get_tools.return_value = []

    def test_get_resources(self):
        """Test that the server returns a list of resources."""
        resources = self.server.get_resources()
        self.assertIsInstance(resources, list)
        self.assertEqual(len(resources), 5)

        # Check that each resource has the required fields
        for resource in resources:
            self.assertIn("name", resource)
            self.assertIn("description", resource)
            self.assertIn("url", resource)

    def test_get_tools(self):
        """Test that the server returns a list of tools."""
        tools = self.server.get_tools()
        self.assertIsInstance(tools, list)

        # Each resource returns an empty list of tools in our mock
        self.assertEqual(len(tools), 0)


class TestMCPClient(unittest.TestCase):
    """Test cases for the MCP client implementation."""

    def setUp(self):
        """Set up test environment."""
        # Use a mock server URL for testing
        self.server_url = "http://localhost:8000"
        os.environ["MCP_EPACOMP_TOX_SERVER_URL"] = self.server_url
        self.client = MCPClient()

    def test_get_tools(self):
        """Test that the client returns a list of tools."""
        tools_response = self.client.get_tools()
        self.assertIsInstance(tools_response, dict)
        self.assertIn("tools", tools_response)

        tools = tools_response["tools"]
        self.assertIsInstance(tools, list)
        self.assertTrue(len(tools) > 0)

        # Check that each tool has the required fields
        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("parameters", tool)

    def test_execute_tool(self):
        """Test that the client can execute a tool."""
        result = self.client.execute_tool(
            "search_chemical", {"query": "toluene", "search_type": "equals"}
        )
        self.assertIsInstance(result, dict)
        self.assertIn("status", result)
        self.assertEqual(result["status"], "success")


class TestEPACompToxAuth(unittest.TestCase):
    """Test cases for the EPA CompTox authentication handler."""

    def test_get_headers(self):
        """Test that the auth handler returns the correct headers."""
        api_key = "test_key"
        auth = EPACompToxAuth(api_key=api_key)
        headers = auth.get_headers()
        self.assertIsInstance(headers, dict)
        self.assertIn("x-api-key", headers)
        self.assertEqual(headers["x-api-key"], api_key)

    def test_get_api_key(self):
        """Test that the auth handler returns the API key."""
        api_key = "test_key"
        auth = EPACompToxAuth(api_key=api_key)
        returned_key = auth.get_api_key()
        self.assertEqual(returned_key, api_key)

    def test_missing_api_key(self):
        """Test that the auth handler raises an error when the API key is missing."""
        auth = EPACompToxAuth(api_key=None)
        with self.assertRaises(ValueError):
            auth.get_headers()
        with self.assertRaises(ValueError):
            auth.get_api_key()


if __name__ == "__main__":
    unittest.main()

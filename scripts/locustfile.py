"""Locust load test scaffold for MCP workflow harness.

Usage:
    locust -f scripts/locustfile.py --host ws://localhost:8000

The scenarios currently simulate websocket initialization and a simple tools/list call.
Extend `on_start` and `mcp_workflow` tasks with additional transport/predictive calls as needed.
"""

from __future__ import annotations

import json
import time

from locust import HttpUser, task, events  # type: ignore


class MCPUser(HttpUser):
    wait_time = lambda self: 1  # type: ignore

    @task
    def mcp_workflow(self):
        with self.client.websocket("/mcp/ws") as ws:
            ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "clientInfo": {"name": "locust", "version": "1.0"},
                },
            }))
            ws.recv()
            ws.recv()
            ws.send(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}))
            ws.recv()
            time.sleep(0.1)


@events.init.add_listener
def on_locust_init(environment, **_):
    environment.parsed_options.headless = True

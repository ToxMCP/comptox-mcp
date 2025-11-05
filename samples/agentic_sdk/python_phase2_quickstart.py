"""Minimal Phase 2 MCP quickstart for Agentic SDK integrations.

This script demonstrates how to:
1. Establish a WebSocket MCP session (`initialize` handshake).
2. List the available tools/resources.
3. Call a tool with streaming events and cancellation support.
4. Adapt the stream into a shape that an Agentic SDK agent can consume.

Prerequisites
-------------

    pip install websockets

Optionally install Agentic SDK if you want to plug the stream into a live agent:

    pip install agentic-sdk

Then run the transport in another terminal:

    uvicorn epacomp_tox.transport.websocket:app --host 127.0.0.1 --port 8000

Finally execute:

    python samples/agentic_sdk/python_phase2_quickstart.py
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional

import websockets


Request = Dict[str, Any]
Response = Dict[str, Any]


@dataclass
class MCPEvent:
    """Represents a streaming MCP event emitted after `tools/call`."""

    typ: str
    payload: Dict[str, Any]


class MCPWebSocketSession:
    """Lightweight JSON-RPC client for the EPA CompTox Phase 2 MCP transport."""

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None) -> None:
        self.url = url
        self.headers = headers or {}
        self._next_id = 0
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._listen_task: Optional[asyncio.Task[None]] = None
        self._responses: Dict[int, asyncio.Future[Response]] = {}
        self._event_queue: asyncio.Queue[MCPEvent] = asyncio.Queue()

    async def __aenter__(self) -> "MCPWebSocketSession":
        self._ws = await websockets.connect(self.url, extra_headers=self.headers)
        self._listen_task = asyncio.create_task(self._listen_loop())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._listen_task:
            self._listen_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listen_task
        if self._ws:
            await self._ws.close()

    async def initialize(self) -> Response:
        """Perform the MCP `initialize` handshake."""
        params = {
            "protocolVersion": "2025-06-18",
            "capabilities": {
                "tools": {"list": {"pagination": True}, "call": {"stream": True}},
                "resources": {"list": {"pagination": True}},
                "logging": {"subscribe": False},
            },
            "clientInfo": {"name": "samples.agentic_sdk", "version": "0.1.0"},
        }
        return await self._request("initialize", params)

    async def list_tools(self) -> Response:
        return await self._request("tools/list", {"cursor": None})

    async def list_resources(self) -> Response:
        return await self._request("resources/list", {"cursor": None})

    async def call_tool(self, name: str, arguments: Dict[str, Any], request_id: Optional[str] = None) -> Response:
        """Invoke `tools/call` and return the final JSON-RPC response.

        Streaming events are yielded via `stream_events()` until `events/end` arrives.
        """
        params = {"name": name, "arguments": arguments}
        if request_id:
            params["requestId"] = request_id
        return await self._request("tools/call", params)

    async def cancel_tool(self, call_id: str) -> Response:
        return await self._request("tools/cancel", {"id": call_id})

    async def stream_events(self) -> AsyncIterator[MCPEvent]:
        """Yield MCP events emitted by the transport."""
        while True:
            event = await self._event_queue.get()
            yield event
            if event.typ == "events/end":
                return

    async def _request(self, method: str, params: Dict[str, Any]) -> Response:
        self._next_id += 1
        msg_id = self._next_id
        request: Request = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
        assert self._ws is not None
        await self._ws.send(json.dumps(request))
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Response] = loop.create_future()
        self._responses[msg_id] = future
        return await future

    async def _listen_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                data = json.loads(raw)
                if "event" in data:
                    await self._event_queue.put(MCPEvent(data["event"], data.get("params", {})))
                    continue
                if "id" in data:
                    msg_id = data["id"]
                    future = self._responses.pop(msg_id, None)
                    if future and not future.done():
                        future.set_result(data)
                else:
                    # Notifications (e.g., notifications/initialized)
                    await self._event_queue.put(MCPEvent(data.get("method", "notification"), data.get("params", {})))
        except asyncio.CancelledError:  # pragma: no cover - cleanup
            pass


async def main() -> None:
    url = os.environ.get("MCP_SERVER_URL", "ws://127.0.0.1:8000/mcp/ws")
    api_key = os.environ.get("CTX_API_KEY")
    headers = {"x-api-key": api_key} if api_key else None

    async with MCPWebSocketSession(url, headers=headers) as session:
        handshake = await session.initialize()
        print("Handshake response:", json.dumps(handshake, indent=2))

        tools = await session.list_tools()
        print("Available tools:", [t["name"] for t in tools.get("result", {}).get("tools", [])])

        # Call the chemical search tool and stream results.
        call_response = await session.call_tool(
            "search_chemical",
            {"query": "toluene", "search_type": "equals"},
            request_id="example-call-1",
        )
        print("Call accepted:", json.dumps(call_response, indent=2))

        async for event in session.stream_events():
            print(f"[event] {event.typ}: {json.dumps(event.payload)}")
            if event.typ == "events/result":
                # Agentic SDK adapters can route this payload directly to an Agent tool output.
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user.")

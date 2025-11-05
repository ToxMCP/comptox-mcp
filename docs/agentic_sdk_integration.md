# Agentic SDK Integration Guide

This guide walks through connecting the EPA CompTox Phase 2 MCP transport to the Agentic SDK. It covers the end-to-end handshake, streaming tool calls, and how to adapt the transport’s event stream into an Agentic agent workflow. Use it together with the quickstart script in `samples/agentic_sdk/python_phase2_quickstart.py`.

## 1. Prerequisites

- Python 3.10+
- `pip install epacomp-tox-mcp websockets`
- Optional: `pip install agentic-sdk` (for fully wiring into an Agentic agent)
- EPA CompTox API key exported as `CTX_API_KEY`

Start the transport in a separate terminal:

```bash
uvicorn epacomp_tox.transport.websocket:app --host 127.0.0.1 --port 8000
```

## 2. Quickstart Script

Run the provided sample to exercise the MCP handshake, discover tools, and stream a tool call:

```bash
python samples/agentic_sdk/python_phase2_quickstart.py
```

What it does:
- Performs `initialize` with protocol `2025-06-18` and streaming capabilities enabled.
- Calls `tools/list` and `resources/list` to mirror Agentic SDK discovery.
- Executes `tools/call` for `search_chemical`, streaming `events/log`, `events/result`, and `events/end`.
- Prints each event, demonstrating the payloads you can feed into an agent’s tool adapters.

Review the script to learn how JSON-RPC requests/responses and streaming events are handled over the WebSocket session. You can reuse the `MCPWebSocketSession` helper inside Agentic SDK adapters.

## 3. Wiring Into Agentic SDK (Python)

```python
import asyncio
from agentic_sdk import Agent
from agentic_sdk.adapters import ToolStreamAdapter

from samples.agentic_sdk.python_phase2_quickstart import MCPWebSocketSession


class MCPToolAdapter(ToolStreamAdapter):
    """Minimal bridge from MCP events to Agentic SDK tool responses."""

    def __init__(self, session: MCPWebSocketSession, tool_name: str):
        super().__init__(name=tool_name)
        self._session = session

    async def invoke(self, *, arguments: dict, request_id: str):
        # Kick off the MCP call (returns when JSON-RPC response is received).
        await self._session.call_tool(self.name, arguments, request_id=request_id)
        # Stream MCP events back to the Agentic SDK runtime.
        async for event in self._session.stream_events():
            if event.typ == "events/result":
                await self.emit_delta(event.payload)
            elif event.typ == "events/error":
                await self.emit_error(event.payload)
            elif event.typ == "events/end":
                return


async def setup_agent():
    async with MCPWebSocketSession("ws://127.0.0.1:8000/mcp/ws") as session:
        await session.initialize()
        chemical_tool = MCPToolAdapter(session, "search_chemical")

        agent = Agent(name="CompToxAgent")
        agent.register_tool(chemical_tool)

        await agent.run_task(
            "Find analogues for toluene and summarise AD guardrails.",
            tool_arguments={"search_chemical": {"query": "toluene", "search_type": "equals"}},
        )


asyncio.run(setup_agent())
```

Key integration points:
- Derive a custom `ToolStreamAdapter` (or equivalent) that turns MCP `events/result` chunks into Agentic SDK deltas.
- Pass the Agentic request identifier (`request_id`) through to `tools/call` so streams correlate back to the Agentic task.
- Handle `events/error` and `events/log` to provide agent-facing explanations or structured error handling.

## 4. TypeScript Outline

```ts
import { Agent } from "agentic-sdk";
import { MCPWebSocket } from "./mcp_websocket"; // copy helper from samples/agentic_sdk/ts_phase2_quickstart.ts

const session = await MCPWebSocket.connect("ws://127.0.0.1:8000/mcp/ws", {
  headers: { "x-api-key": process.env.CTX_API_KEY ?? "" },
  protocolVersion: "2025-06-18",
});

await session.initialize();

const agent = new Agent({ name: "CompToxAgent" });

agent.registerTool({
  name: "search_chemical",
  async invoke(args, ctx) {
    await session.callTool("search_chemical", args, ctx.requestId);
    for await (const event of session.streamEvents()) {
      if (event.event === "events/result") {
        ctx.emitDelta(event.payload);
      } else if (event.event === "events/error") {
        ctx.emitError(event.payload);
      } else if (event.event === "events/end") {
        break;
      }
    }
  },
});

await agent.run("Find PFAS analogues with AD summaries.");
```

> Copy `MCPWebSocket` (including JSON-RPC helpers) from `samples/agentic_sdk/ts_phase2_quickstart.ts` into your project, or publish it as a shared utility inside your Agentic workspace.

Reuse the JSON-RPC logic from the Python helper or the TypeScript quickstart to integrate with other runtimes.

## 5. Testing & Troubleshooting

- Use `scripts/mcp_ws_client.py --record` to capture raw event streams when debugging agent integrations.
- Verify guardrail enforcement by calling predictive tools; `events/error` will include AD rationale (also persisted in audit bundles).
- Heartbeat/ping failures appear as WebSocket close codes. Ensure the Agentic SDK reconnect logic respects MCP idle timeouts.
- If you see `-32602` or `-32001` errors, confirm tool schemas and initialization sequence match the MCP spec.

## 6. Next Steps

1. Extend the Tool adapter pattern to include additional CTX tools (exposure, hazard, metadata, orchestrator workflows).
2. Wrap guardrail/error payloads with user-friendly text inside the agent responses.
3. Wire QA smoke tests (see `docs/qa/`) into your CI to ensure the Agentic integration stays healthy after upgrades.

For a deeper architecture view, read `docs/architecture_overview.md` and the guardrail details in `docs/model_cards_and_policies.md`.

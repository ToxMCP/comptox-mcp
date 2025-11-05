/**
 * Minimal TypeScript outline for integrating the Phase 2 MCP transport with Agentic SDK.
 * Use node >=18 (for global fetch/WebSocket) or install `ws`.
 *
 *   npm install agentic-sdk ws
 *
 * Run the transport separately:
 *   uvicorn epacomp_tox.transport.websocket:app --host 127.0.0.1 --port 8000
 */

import WebSocket from "ws";

type JsonRpcRequest = {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params?: Record<string, unknown>;
};

type JsonRpcResponse = {
  jsonrpc: "2.0";
  id: number;
  result?: unknown;
  error?: unknown;
};

type McpEvent = {
  event: string;
  params: Record<string, unknown>;
};

export class MCPWebSocket {
  private socket: WebSocket;
  private nextId = 0;
  private inflight = new Map<number, (payload: JsonRpcResponse) => void>();
  private eventHandlers: Array<(evt: McpEvent) => void> = [];
  private pendingEvents: McpEvent[] = [];
  private resolveNextEvent: ((evt: McpEvent) => void) | undefined;

  private constructor(socket: WebSocket) {
    this.socket = socket;
    this.socket.on("message", (raw) => {
      const data = JSON.parse(raw.toString());
      if ("event" in data) {
        this.eventHandlers.forEach((handler) => handler(data));
        if (this.resolveNextEvent) {
          this.resolveNextEvent(data);
          this.resolveNextEvent = undefined;
        } else {
          this.pendingEvents.push(data);
        }
      } else if ("id" in data) {
        const handler = this.inflight.get(data.id);
        if (handler) {
          handler(data);
          this.inflight.delete(data.id);
        }
      }
    });
  }

  static async connect(
    url: string,
    headers?: Record<string, string>
  ): Promise<MCPWebSocket> {
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(url, { headers });
      socket.once("open", () => resolve(new MCPWebSocket(socket)));
      socket.once("error", reject);
    });
  }

  async initialize(): Promise<JsonRpcResponse> {
    return this.request("initialize", {
      protocolVersion: "2025-06-18",
      capabilities: {
        tools: { call: { stream: true } },
        resources: { list: { pagination: true } },
      },
      clientInfo: { name: "samples.agentic_sdk.ts", version: "0.1.0" },
    });
  }

  async callTool(
    name: string,
    args: Record<string, unknown>,
    requestId?: string
  ): Promise<JsonRpcResponse> {
    return this.request("tools/call", {
      name,
      arguments: args,
      requestId,
    });
  }

  async listTools(): Promise<JsonRpcResponse> {
    return this.request("tools/list", { cursor: null });
  }

  onEvent(handler: (evt: McpEvent) => void) {
    this.eventHandlers.push(handler);
  }

  async *streamEvents(): AsyncGenerator<McpEvent> {
    while (true) {
      const evt = await this.nextEvent();
      yield evt;
      if (evt.event === "events/end") {
        break;
      }
    }
  }

  private nextEvent(): Promise<McpEvent> {
    if (this.pendingEvents.length > 0) {
      return Promise.resolve(this.pendingEvents.shift()!);
    }
    return new Promise((resolve) => {
      this.resolveNextEvent = resolve;
    });
  }

  private async request(
    method: string,
    params?: Record<string, unknown>
  ): Promise<JsonRpcResponse> {
    this.nextId += 1;
    const id = this.nextId;
    const payload: JsonRpcRequest = { jsonrpc: "2.0", id, method, params };

    return new Promise<JsonRpcResponse>((resolve, reject) => {
      this.inflight.set(id, resolve);
      this.socket.send(JSON.stringify(payload), (err) => {
        if (err) {
          this.inflight.delete(id);
          reject(err);
        }
      });
    });
  }
}

// Example usage
async function main() {
  const session = await MCPWebSocket.connect(
    process.env.MCP_SERVER_URL ?? "ws://127.0.0.1:8000/mcp/ws",
    process.env.CTX_API_KEY ? { "x-api-key": process.env.CTX_API_KEY } : undefined
  );

  console.log("Handshake:", await session.initialize());
  console.log("Tools:", await session.listTools());

  session.onEvent((evt) => {
    console.log(`[event] ${evt.event}`, evt.params);
  });

  await session.callTool("search_chemical", {
    query: "toluene",
    search_type: "equals",
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

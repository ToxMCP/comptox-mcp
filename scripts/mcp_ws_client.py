#!/usr/bin/env python3
"""Reference CLI client for the EPA CompTox MCP WebSocket transport."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import websockets


class Recorder:
    """Optional JSONL recorder for CLI sessions."""

    def __init__(self, path: Optional[str]):
        self.path = Path(path) if path else None
        self._fh = None

    def __enter__(self) -> "Recorder":
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self.path.open("w", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

    def write(self, message: Dict[str, Any]) -> None:
        if not self._fh:
            return
        json.dump(message, self._fh)
        self._fh.write("\n")
        self._fh.flush()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="ws://127.0.0.1:8000/mcp/ws",
        help="WebSocket URL for the MCP server (default: %(default)s)",
    )
    parser.add_argument(
        "--protocol-version",
        default="2025-06-18",
        help="Requested MCP protocol version (default: %(default)s)",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List tools after initialization",
    )
    parser.add_argument(
        "--list-resources",
        action="store_true",
        help="List resources after initialization",
    )
    parser.add_argument(
        "--call-tool",
        help="Call a tool by name",
    )
    parser.add_argument(
        "--arguments",
        help="JSON payload with tool arguments (only used with --call-tool)",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=None,
        help="Optional timeout in milliseconds for `tools/call`",
    )
    parser.add_argument(
        "--cancel-after-ms",
        type=int,
        default=None,
        help="Send `tools/cancel` after the specified milliseconds (requires --call-tool)",
    )
    parser.add_argument(
        "--record",
        help="Record all messages to the given JSONL file",
    )
    return parser.parse_args()


async def send_request(
    ws: websockets.WebSocketClientProtocol,
    payload: Dict[str, Any],
    *,
    recorder: Recorder,
    event_log: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    await ws.send(json.dumps(payload))
    recorder.write(payload)  # Log outbound request
    while True:
        response_raw = await ws.recv()
        response = json.loads(response_raw)
        recorder.write(response)
        if "id" in response:
            if response.get("id") == payload.get("id"):
                return response
            print(f"[response] id={response.get('id')} -> {json.dumps(response, indent=2)}")
            continue
        if "method" in response and event_log is not None:
            event_log.append(response)
            _display_event(response)


def _display_event(event: Dict[str, Any]) -> None:
    method = event.get("method")
    params = event.get("params", {})
    if method.startswith("events/"):
        request_id = params.get("requestId")
        summary = json.dumps(params, indent=2)
        print(f"[event] {method} (requestId={request_id}) -> {summary}")
    else:
        print("Notification:", json.dumps(event, indent=2))


async def run_client(args: argparse.Namespace) -> None:
    print(f"Connecting to {args.url}", file=sys.stderr)
    with Recorder(args.record) as recorder:
        async with websockets.connect(args.url) as ws:
            initialize = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": args.protocol_version,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "epacomp-tox-cli",
                        "version": "0.1.0",
                    },
                },
            }
            event_log: List[Dict[str, Any]] = []
            init_response = await send_request(ws, initialize, recorder=recorder, event_log=event_log)
            print("Initialize response:", json.dumps(init_response, indent=2))

            # Drain initialization notifications
            while True:
                try:
                    notification_raw = await asyncio.wait_for(ws.recv(), timeout=0.1)
                except asyncio.TimeoutError:
                    break
                notification = json.loads(notification_raw)
                recorder.write(notification)
                if notification.get("method") != "notifications/initialized":
                    print("Notification:", json.dumps(notification, indent=2))
                else:
                    print("Server initialized notification received.")

            next_id = 2

            if args.list_tools:
                response = await send_request(
                    ws,
                    {"jsonrpc": "2.0", "id": next_id, "method": "tools/list", "params": {}},
                    recorder=recorder,
                    event_log=event_log,
                )
                next_id += 1
                print("Tools:", json.dumps(response, indent=2))

            if args.list_resources:
                response = await send_request(
                    ws,
                    {"jsonrpc": "2.0", "id": next_id, "method": "resources/list", "params": {}},
                    recorder=recorder,
                    event_log=event_log,
                )
                next_id += 1
                print("Resources:", json.dumps(response, indent=2))

            if args.call_tool:
                arguments: Dict[str, Any] = {}
                if args.arguments:
                    try:
                        arguments = json.loads(args.arguments)
                    except json.JSONDecodeError as exc:
                        raise SystemExit(f"Failed to parse arguments JSON: {exc}") from exc

                params: Dict[str, Any] = {"name": args.call_tool, "arguments": arguments}
                if args.timeout_ms:
                    params["timeoutMs"] = args.timeout_ms

                cancel_task: Optional[asyncio.Task[None]] = None
                if args.cancel_after_ms:
                    async def send_cancel() -> None:
                        await asyncio.sleep(args.cancel_after_ms / 1000)
                        cancel_payload = {
                            "jsonrpc": "2.0",
                            "id": next_id + 1,
                            "method": "tools/cancel",
                            "params": {"requestId": params.get("requestId", str(next_id))},
                        }
                        print("Sending cancellation request...", file=sys.stderr)
                        await ws.send(json.dumps(cancel_payload))
                        recorder.write(cancel_payload)

                    # ensure requestId stable
                    params["requestId"] = params.get("requestId", f"req-{next_id}")
                    cancel_task = asyncio.create_task(send_cancel())

                response = await send_request(
                    ws,
                    {
                        "jsonrpc": "2.0",
                        "id": next_id,
                        "method": "tools/call",
                        "params": params,
                    },
                    recorder=recorder,
                    event_log=event_log,
                )
                next_id += 1
                if cancel_task:
                    await cancel_task
                print("Tool call result:", json.dumps(response, indent=2))


def main() -> None:
    args = parse_arguments()
    asyncio.run(run_client(args))


if __name__ == "__main__":
    main()

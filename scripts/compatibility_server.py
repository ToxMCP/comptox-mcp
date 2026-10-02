"""Test-only offline launcher; production never installs these fixture hooks."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHEMICAL = {
    "dtxsid": "DTXSID7020182",
    "preferredName": "Bisphenol A",
    "casrn": "80-05-7",
    "smiles": "CC(C)(C1=CC=C(C=C1)O)C2=CC=C(C=C2)O",
    "synonyms": ["BPA"],
    "rank": 1,
}


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 10, 1, 12, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


class FixtureResponse:
    status = 200
    headers = {
        "x-request-id": "fixture-provider-request",
        "x-ratelimit-limit": "100",
        "x-ratelimit-remaining": "99",
        "x-ratelimit-reset": "1790856060",
    }

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def fixture_urlopen(request, timeout=None):
    parsed = urllib.parse.urlparse(request.full_url)
    record = {
        "method": request.get_method(),
        "path": parsed.path,
        "query": parsed.query,
        "body": request.data.decode() if request.data else None,
    }
    captured = os.environ.get("COMPTOX_COMPATIBILITY_REQUEST_LOG")
    if captured:
        with Path(captured).open("a") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    if "fixture-unavailable" in parsed.path:
        raise urllib.error.HTTPError(
            request.full_url,
            503,
            "Fixture unavailable",
            FixtureResponse.headers,
            io.BytesIO(b'{"message":"synthetic failure"}'),
        )
    if "/chemical/search/" in parsed.path:
        payload = [dict(CHEMICAL)]
    elif "/chemical/detail/search/" in parsed.path:
        payload = dict(CHEMICAL)
    else:
        raise AssertionError(f"Unexpected fixture upstream request: {record}")
    return FixtureResponse(payload)


def make_application():
    os.environ["CTX_API_KEY"] = "offline-fixture-key"
    os.environ["CTX_RETRY_ATTEMPTS"] = "0"
    os.environ["CTX_RETRY_BASE"] = "0"
    os.environ["LOG_LEVEL"] = "WARNING"
    from epacomp_tox.resources import base, interop, prioritization
    from epacomp_tox.server import MCPServer

    # Real urllib request construction/metadata capture and domain schema validation.
    urllib.request.urlopen = fixture_urlopen
    for module in [base, interop, prioritization]:
        module.datetime = FixedDatetime
    sys.path.insert(0, str(ROOT / "tests"))
    from interop_test_support import (
        StubBioactivityResource,
        StubChemicalResource,
        StubExposureResource,
        StubHazardResource,
        StubMetadataResource,
    )

    server = MCPServer(api_key="offline-fixture-key", validate_health=False)
    for name in ["interop", "prioritization"]:
        resource = server.resources[name]
        for kind, fixture in [
            ("chemical", StubChemicalResource),
            ("bioactivity", StubBioactivityResource),
            ("exposure", StubExposureResource),
            ("hazard", StubHazardResource),
            ("metadata", StubMetadataResource),
        ]:
            if hasattr(resource, kind + "_resource"):
                setattr(resource, kind + "_resource", fixture())
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["http", "stdio"], required=True)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    application = make_application()
    if args.transport == "http":
        import uvicorn

        from epacomp_tox.transport.websocket import create_app

        uvicorn.run(
            create_app(server=application),
            host="127.0.0.1",
            port=args.port,
            log_level="warning",
        )
    else:
        import anyio
        from mcp.server.stdio import stdio_server

        from epacomp_tox.transport.sdk2 import create_sdk_server

        async def serve():
            server = create_sdk_server(application)
            async with stdio_server() as (reader, writer):
                await server.run(reader, writer, server.create_initialization_options())

        anyio.run(serve)


if __name__ == "__main__":
    main()

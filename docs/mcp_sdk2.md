# SDK2 compatibility and hosting

This unreleased v0.3.0 candidate uses stable `mcp==2.2.0`. SDK2 modern clients use protocol `2026-07-28`; older clients keep the released initialization/HTTP alias path. The existing WebSocket interface remains implemented by its legacy handler, including authorization, sessions, streaming, cancellation and capability negotiation.

## Client setup

Existing HTTP clients keep their `/mcp` URL. The new local command is `comptox-mcp-stdio`; supply `CTX_API_KEY` in its environment. Local stdio uses the same evidence-federation resources and writes logs to stderr. It does not add predictive or orchestrator tools.

Modern HTTP is stateless JSON. SDK clients provide `MCP-Protocol-Version`, `Mcp-Method` and `Mcp-Name` (tool name or resource URI where required) plus the matching request metadata. Browser CORS preflights allow these standard headers. SDK2 validates header/body consistency and rejects unsupported versions.

## Hosting configuration

`EPACOMP_MCP_ALLOWED_HOSTS` is a comma-separated modern Host allowlist; empty defaults to `localhost:*`, `127.0.0.1:*`, `[::1]:*`. Configure public gateway authorities before deployment. `EPACOMP_MCP_ALLOWED_ORIGINS` is a comma-separated modern Origin allowlist. Empty uses explicit non-wildcard `CORS_ALLOW_ORIGINS`, then loopback HTTP origins. Wildcard development CORS does not remove modern DNS rebinding protection. Existing gateway authentication and WebSocket bearer checks remain their respective responsibilities; the EPA API key is an upstream credential.

`EPACOMP_MCP_MAX_REQUEST_BYTES` is positive and defaults to 4 MiB. Both old and modern HTTP parsers are bounded before parsing, including chunked requests. Raise it explicitly when an existing trusted integration needs larger batches.

## Catalog and application compatibility

All tool/resource names, schemas, descriptions and standard hints remain. Modern tool `annotations.resource` moves to `_meta["org.toxmcp/toolPolicy"].resource`; modern resource `annotations.resource` moves to `_meta["org.toxmcp/resourcePolicy"].resource`. Legacy catalog extensions remain in their original locations. Catalogs advertise a private 60-second SDK cache hint; resource reads have private zero-TTL hints. These hints do not change provider caching or scientific results.

Tool results retain structured content, text, upstream request IDs, rate limits, response hashes, retry counts and provenance. The modern SDK adds server identity/result-envelope fields. `_meta.session` and `_meta.error.runtime.session` retain transport-specific identities, so they naturally differ between stdio and HTTP. The compatibility gate validates their structure and compares every other application value under fixed test-only application clocks. Production never imports the offline launcher.

Run `scripts/verify_protocol_clients.py --legacy-python tests/compatibility/legacy-client/.venv/bin/python --server-python <installed-python> --output-dir <results>` after `uv sync --locked --project tests/compatibility/legacy-client`. It exercises actual SDK1/SDK2 clients over stdio and HTTP outside the checkout. It uses synthetic provider fixtures and the existing scientific handoff fixtures; this proves protocol preservation, not live EPA availability. Existing WebSocket conformance and scientific gates remain required.

Task-based durable execution, Apps and elicitation are separate future work. The adapter retains synchronous domain dispatch so shared resource provenance does not acquire cross-thread races.

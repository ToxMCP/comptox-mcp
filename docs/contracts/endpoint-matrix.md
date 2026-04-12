# Endpoint Matrix — EPA CompTox MCP

This matrix summarizes the upstream services the MCP server depends on, their failover strategy, and operational guidance. Pair this page with `docs/deployment.md` when planning reproducible runs.

| Integration | Capability | Primary Endpoint | Failover / Fixture | Auth & Secrets | SLA / Rate Notes | Retry & Cache Guidance |
|-------------|------------|------------------|--------------------|----------------|------------------|------------------------|
| CTX Chemical API | Identifier resolution, structures, property lookups | `https://comptox.epa.gov/ctx-api/v1/chemical` | Legacy host `https://api-ccte.epa.gov/chemical/v1/` (enable via `CTX_USE_LEGACY=1`) | `CTX_API_KEY` (preferred) or `EPA_COMPTOX_API_KEY` | 50 req/min default; 429 burst throttling and nightly maintenance 00:00–01:00 ET | Retry 3x with exponential backoff (0.5s base); cache positive ID lookups 24h |
| CTX Hazard API | ToxValDB, ToxRefDB, cancer, genetox, ADME/IVIVE, IRIS, PPRTV, HAWC | `https://comptox.epa.gov/ctx-api/v1/hazard` | Same legacy host as Chemical; fixture capture under `tests/golden/hazard/*` for offline testing | Same API key | Occasional 502 during dataset refresh; 5xx often clear within 60s | Retry 3x with jitter; guardrails enforce schema validation before return |
| CTX Exposure API | CPDat, SEEM, MMDB, HTTK | `https://comptox.epa.gov/ctx-api/v1/exposure` | Legacy host fallback; offline fixtures for `search_cpdat` and `get_seem_*` | Same API key | Some endpoints (MMDB) slow >5s; monitor latency metrics | Retry 2x for GET, but short-circuit when identifiers empty |
| CTX Bioactivity API | ToxCast/Tox21 assays, AOP mappings | `https://comptox.epa.gov/ctx-api/v1/bioactivity` | Legacy host fallback; offline fixtures for assay summaries | Same API key | Rate comparable to hazard; 404 for unavailable AEIDs | Retry 2x; cache assay annotations for 12h |
| CTX Metadata API | Model cards, applicability domains | `https://comptox.epa.gov/ctx-api/v1/metadata` | Local `metadata/` JSON bundle packaged with repo | Same API key | Static datasets; rarely down | No retries required; prefer packaged bundle when offline |
| MCP HTTP transport | JSON-RPC surface (`/mcp`) | Local FastAPI app | WebSocket transport `ws://<host>/mcp/ws` | Optional bearer token via proxy | N/A | Health check `/healthz` every 30s; rotate to WebSocket when long streams needed |

## Operational Practices

- **Secret handling:** Store CTX keys in your secrets manager and expose via `CTX_API_KEY`. The server also checks `EPA_COMPTOX_API_KEY` and `ctx_x_api_key` for backward compatibility.
- **Health checks:** `scripts/smoke_ctx.sh` pings chemical, hazard, and exposure endpoints plus `/mcp`. `GET /readyz` now requires a successful authenticated CTX probe; it will not report ready based only on a generic `/ctx-api/health` 404. Run the smoke script before large jobs and pin results for audits.
- **Automated verification:** `python scripts/check_endpoints.py` emits a status/latency report for every endpoint in this matrix (set `CTX_API_KEY` so the requests are authorized). Capturing the JSON output alongside releases creates an auditable failover record.
- **Failover workflow:** Set `CTX_USE_LEGACY=1` to route all clients to the legacy host when the primary API reports sustained 5xx. Document the window in release notes.
- **Fixtures for reproducibility:** Place captured payloads under `tests/golden/<resource>/<endpoint>.json` when network access is unavailable. The hazard smoke commands in `README.md` describe expected baseline outputs (BPA + PFOA).
- **Logging:** `epacomp_tox.server.MCPServer` records upstream metadata (status, request ID, rate-limit headers). Surface these through MCP `structuredContent.metadata` for downstream debugging.
- **Schema validation:** Public response validation now covers the shared schemas under `docs/contracts/schemas/common/` plus dedicated `chemical/`, `cheminformatics/`, `hazard/`, `exposure/`, `bioactivity/`, `workflow/`, `metadata/`, and `predictive/` namespaces.

Keep this document updated as new endpoints are added or mirrors change. Consistency here is a requirement for A-grade reproducibility reviews.

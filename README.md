[![CI](https://github.com/ToxMCP/comptox-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ToxMCP/comptox-mcp/actions/workflows/ci.yml)
[![DOI](https://img.shields.io/badge/DOI-10.64898%2F2026.02.06.703989-blue)](https://doi.org/10.64898/2026.02.06.703989)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

# EPA CompTox MCP Server

> Part of **ToxMCP** Suite → https://github.com/ToxMCP/toxmcp


**Public MCP endpoint for the EPA Computational Toxicology (CompTox) API.**  
Expose CompTox resources, predictive services, and guardrailed workflows to any MCP-aware agent (Codex CLI, Gemini CLI, Claude Code, etc.).

## Why this project exists

Regulatory and research teams rely on the CompTox API for high-quality chemical, exposure, and hazard data. Traditional workflows involve bespoke scripts or manual dashboard exports that are hard to share with AI copilots.  

The EPA CompTox MCP server wraps those workflows in a **secure, programmable interface**:

- **One MCP surface (`/mcp` HTTP + `/mcp/ws` WebSocket)** delivers discovery and execution across chemical, exposure, hazard, and metadata catalogues.
- **Guardrails + provenance** – Applicability-domain policies, audit bundles, and metadata attachments are available to downstream automations.
- **Agent friendly** – tested with Codex CLI, Gemini CLI, and Claude (see [integration guide](docs/integration_guides/mcp_integration.md)).

> Looking for the orchestrator or Agentic SDK samples? The MCP server reuses the same components but packages them for any MCP-compatible agent instead of the bespoke SDK clients.

---

## Feature snapshot

| Capability | Description |
| --- | --- |
| 🌐 **Dual MCP Transports** | JSON-RPC over HTTP (`/mcp`) and WebSocket (`/mcp/ws`) with identical tool catalogues. |
| 🧬 **CompTox Tooling** | Chemical, exposure, hazard, metadata, and predictive helpers mapped to structured MCP tools. |
| 🛡️ **Guardrail Enforcement** | Applicability-domain policies, audit logging, JSON Schema response validation, and provenance bundles returned alongside tool data. |
| ⚙️ **Configurable by Design** | Pydantic settings with `.env` support for API keys, retries, auth bypass, transport tuning, and observability. |
| 🤖 **Agent Ready** | Verified with Codex CLI, Gemini CLI, and Claude Code; includes quick-start config snippets. |

---

## Table of contents

1. [Quick start](#quick-start)
2. [Configuration](#configuration)
3. [Tool catalog](#tool-catalog)
4. [Running the server](#running-the-server)
5. [Integrating with coding agents](#integrating-with-coding-agents)
6. [Output artifacts](#output-artifacts)
7. [Security checklist](#security-checklist)
8. [Development notes](#development-notes)
9. [Roadmap](#roadmap)
10. [License](#license)

---

## Quick start

```bash
git clone https://github.com/senseibelbi/CompTox_MCP.git mcp_epacomp_tox
cd mcp_epacomp_tox
pip install -e .
cp .env.example .env
uvicorn epacomp_tox.transport.websocket:app --reload
```

> **Important:** The server needs a valid EPA CompTox API key. Set `CTX_API_KEY` (preferred) or `EPA_COMPTOX_API_KEY` in `.env` before starting the transport.

With the server running, MCP clients can connect to `http://localhost:8000/mcp` (HTTP) or `ws://localhost:8000/mcp/ws` (WebSocket).

---

## Configuration

Settings are resolved via [`pydantic-settings`](https://docs.pydantic.dev/latest/concepts/settings/) with `.env`/`.env.local` support. Key environment variables:

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `CTX_API_KEY` | ✅ | – | CompTox API key used for all downstream requests. Fallbacks: `EPA_COMPTOX_API_KEY`, `ctx_x_api_key`. |
| `CTX_API_BASE_URL` | Optional | `https://comptox.epa.gov/ctx-api` | Base URL for CompTox API. |
| `CTX_USE_LEGACY` | Optional | `0` | Set to `1` to use the legacy `https://api-ccte.epa.gov` endpoint. |
| `CTX_RETRY_ATTEMPTS` | Optional | `3` | Number of retry attempts for transient errors. |
| `CTX_RETRY_BASE` | Optional | `0.5` | Base sleep (seconds) used in exponential backoff. |
| `ENVIRONMENT` | Optional | `development` | Controls defaults like permissive CORS. |
| `LOG_LEVEL` | Optional | `INFO` | Application log level. |
| `BYPASS_AUTH` | Optional | `0` | Set to `1` to disable auth (development only). |
| `CORS_ALLOW_ORIGINS` | Optional | – | Comma-separated origins for HTTP transport. Defaults to `*` in development. |
| `EPACOMP_MCP_HEARTBEAT_TIMEOUT_SECONDS` | Optional | `120` | Minimum heartbeat timeout negotiated with WebSocket clients. |
| `EPACOMP_MCP_HANDSHAKE_TIMEOUT_SECONDS` | Optional | `30` | Minimum handshake timeout negotiated with WebSocket clients. |
| `EPACOMP_MCP_METRICS_ENABLED` | Optional | `1` | Toggle `/metrics` endpoint exposure. |

See [`docs/deployment.md`](docs/deployment.md) for production hardening tips and expanded configuration.

---

## Tool catalog

| Category | Highlight tools | Notes |
| --- | --- | --- |
| Chemical discovery | `search_chemical`, `batch_search_chemical`, `get_chemical_details` | Resolve identifiers, structures, and details with CTX retry/backoff baked in. |
| Exposure & hazard | `search_hazard`, `get_hazard_toxval`, `get_hazard_toxref` | Batch-normalized access to CTX exposure datasets plus granular hazard endpoints (ToxValDB, ToxRefDB, cancer, genetox, ADME/IVIVE, IRIS, PPRTV, HAWC). |
| Metadata & governance | `metadata_get_model_card`, `metadata_list_applicability_domain`, `metadata_get_applicability_domain` | Fetch model cards, applicability-domain policies, and audit metadata. |
| Predictive services | `predictive_run_test`, `predictive_run_opera`, `predictive_run_genra` (via orchestrator helpers) | Trigger guardrailed predictive runs and receive provenance detail alongside outputs. |
| Utility helpers | `opsin_convert_name`, `indigo_convert_molfile` | Provide supporting conversions for downstream automations. |

Full schema definitions (input and output) are returned via the MCP `tools/list` call. See [`tests/test_resources.py`](tests/test_resources.py) for examples of exercising each category.

---

## Running the server

### Local development

```bash
# install and start the dual-transport server
pip install -e .
uvicorn epacomp_tox.transport.websocket:app --host 0.0.0.0 --port 8000 --reload
```

The FastAPI app exposes both transports:

- HTTP JSON-RPC: `http://localhost:8000/mcp`
- WebSocket JSON-RPC: `ws://localhost:8000/mcp/ws`

Quick handshake + tool discovery via HTTP:

```bash
curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"capabilities":{}}}'

curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | jq '.result.tools | length'
```

### Hazard smoke test

Validate the hazard suite once transports are online:

```bash
# Bisphenol A toxval summary (expect a 40 mg/kg-day NOEL among the records)
curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_hazard","arguments":{"data_type":"toxval","dtxsid":"DTXSID7020182","summary":true}}}' | jq '.result.structuredContent.data[0]'

# Perfluorooctanoic acid cancer classification (expect CalEPA and IARC calls)
curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"search_hazard","arguments":{"data_type":"cancer","dtxsid":"DTXSID8031865","summary":true}}}' | jq '.result.structuredContent.data'
```

Bisphenol A should return HESS and HPVIS toxicity values (including the 40 mg/kg-day NOEL), while Perfluorooctanoic acid surfaces the ATSDR MRL alongside CalEPA and IARC cancer classifications. Errors typically indicate missing API credentials or upstream CompTox outages; inspect the returned metadata for rate-limit status when troubleshooting.

### Endpoint smoke check

Before exposing the MCP server, run the endpoint checker to verify the upstream CompTox APIs are reachable:

```bash
python scripts/check_endpoints.py
# add --json for machine-readable output
```

The script pings each endpoint listed in `docs/contracts/endpoint-matrix.md` and reports latency plus HTTP status. Provide `CTX_API_KEY`/`EPA_COMPTOX_API_KEY` in the environment to avoid 401/403 responses.

### Endpoint automation

A scheduled GitHub Action (`.github/workflows/endpoint-check.yml`) runs `python scripts/check_endpoints.py --json` every day at 06:00 UTC using the `CTX_API_KEY` secret. The workflow uploads `endpoint_status.json` as an artifact so operators can review upstream availability without rerunning the checker locally. Maintainers can also trigger the workflow for a specific pull request by applying the `run-endpoint-check` label (the job only executes for internal branches so secrets stay protected).

### Production deployment

- Run via Gunicorn: `gunicorn epacomp_tox.transport.websocket:app -c deploy/gunicorn_conf.py`
- Container image: see [`deploy/Dockerfile`](deploy/Dockerfile) for a hardened, non-root runtime.
- Probes: `/healthz` (liveness) and `/readyz` (performs CTX connectivity check). Non-200 responses should trigger restarts.
- Metrics: `/metrics` exposes Prometheus gauges derived from `MCPServer.get_transport_metrics()`. Sample scrape/OTEL configs live in `deploy/prometheus_scrape.yaml` and `deploy/otel_collector_metrics.yaml`.
- Additional rollout guidance (TLS, ingress, scaling) lives in [`docs/deployment.md`](docs/deployment.md).

---

## Integrating with coding agents

The repository includes step-by-step instructions in [`docs/integration_guides/mcp_integration.md`](docs/integration_guides/mcp_integration.md). Highlights:

- **Codex CLI**: add an HTTP provider pointing to `http://localhost:8000/mcp` with the `Authorization: Bearer <token>` header when auth is enabled.
- **Gemini CLI**: configure the provider transport to `http` with the same endpoint and optional headers.
- **Claude Code / Cursor**: update the MCP provider JSON to point to the HTTP endpoint; WebSocket is optional when streaming events are required.

Each guide covers tool listing, sample calls, binary payload handling, and troubleshooting tips (timeouts, auth failures, unexpected 4xx responses).

---

## Output artifacts

Every successful tool invocation returns structured payloads designed for agents:

- `content`: human-readable JSON wrapped as text for chat surfaces.
- `structuredContent.data`: machine-readable results (lists, dicts, or arrays) for programmatic chaining.
- `structuredContent.metadata`: when available, includes rate-limit information, applicability-domain context, audit bundle references, and session metadata.
- Predictive tools return additional provenance such as model version, policy enforcement outcome, and attachments (e.g. audit bundle IDs).

---

## Security checklist

- Disable `BYPASS_AUTH` and front the MCP server with OAuth/OIDC once deployed beyond local development.
- Restrict `CORS_ALLOW_ORIGINS` to approved hosts when exposing the HTTP transport.
- Rotate `CTX_API_KEY` regularly and store secrets outside the repository (e.g. cloud secret manager or OS keychain).
- Monitor `/metrics` for negotiated capability changes and unexpected spikes in `tools/call` failures.
- Enable HTTPS/TLS at the ingress or reverse proxy layer.
- Follow coordinated vulnerability disclosure guidance in [`SECURITY.md`](SECURITY.md).

---

## Development notes

### Architecture snapshot

```
┌────────────────┐       ┌─────────────────────────┐       ┌──────────────────────┐
│ MCP Client     │  MCP  │ FastAPI App             │  CQRS │ CompTox Orchestrator │
│ (CLI / IDE)    │──────▶│ HTTP (/mcp) & WS (/mcp/ws)│ ────▶│ + Predictive services│
└────────────────┘       │ • tool registry         │       │ • guardrails/audit    │
       │                 │ • JSON-RPC dispatch     │◀──────│ • audit bundle store  │
       ▼                 └─────────────────────────┘       └──────────────────────┘
```

### Guardrails & governance

- Applicability-domain definitions, policy defaults, and remediation steps live under `metadata/` with JSON Schema validation.
- Predictive invocations persist audit bundles that can be fetched via metadata tools.
- Governance workflows (SME review, policy approval, publication) are documented in `docs/model_cards_and_policies.md`.
- Response contracts live under `docs/contracts/schemas/` (see `docs/contracts/README.md`) and are enforced before MCP responses (and predictive HTTP endpoints) are returned; upstream failover policies are summarized in `docs/contracts/endpoint-matrix.md`.

### Testing & quality gates

- `tests/test_mcp_conformance_suite.py` covers handshake, catalog discovery, and streaming behaviours.
- `tests/test_predictive_regression.py` exercises guardrail outcomes and predictive routing.
- `scripts/smoke_ctx.sh` runs integration smoke tests against the live CTX API.
- `scripts/mcp_http_smoke.sh` performs a quick JSON-RPC handshake and tool listing against the HTTP transport.
- Documentation builds (`scripts/build_docs.sh`) and CI workflows keep diagrams and links healthy.
- The regression matrix in [`docs/testing_matrix.md`](docs/testing_matrix.md) summarizes the expected checks across transports and predictive workflows.

---

## Roadmap

- Expand predictive coverage beyond current TEST/OPERA/GenRA helpers.
- Surface additional analytics (latency histograms, rate-limit breaches) through `/metrics`.
- Optional SSE transport once MCP spec finalises streaming semantics.

---

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## Acknowledgements

- EPA's Center for Computational Toxicology and Exposure (CCTE)
- The ctx-python project for the official CompTox Python bindings
- The Model Context Protocol community for defining the automation surface we target
## Acknowledgements / Origins

This work was developed in the context of the **VHP4Safety** project and related efforts. It builds on upstream third-party data/services (see repository documentation for exact dependencies and access requirements).

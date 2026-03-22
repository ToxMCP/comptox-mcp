# EPA CompTox MCP Server [![CI](https://github.com/ToxMCP/comptox-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ToxMCP/comptox-mcp/actions/workflows/ci.yml) [![DOI](https://img.shields.io/badge/DOI-10.64898%2F2026.02.06.703989-blue)](https://doi.org/10.64898/2026.02.06.703989) [![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](./LICENSE) [![Release](https://img.shields.io/github/v/release/ToxMCP/comptox-mcp?sort=semver)](https://github.com/ToxMCP/comptox-mcp/releases) [![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

> Part of **ToxMCP** Suite -> https://github.com/ToxMCP/toxmcp
>
> **Public MCP endpoint for EPA Computational Toxicology (CompTox) evidence federation.** Expose chemical identity, hazard, exposure, bioactivity, metadata, and cross-suite handoff builders to any MCP-aware agent (Codex CLI, Gemini CLI, Claude Code, etc.).

## Architecture

```mermaid
flowchart LR
  subgraph Clients["Clients and Agents"]
    Codex["Codex CLI / Desktop"]
    Gemini["Gemini CLI"]
    Claude["Claude Code"]
    Scripts["Scripts / notebooks"]
  end

  subgraph API["FastAPI MCP Service"]
    Router["HTTP + WebSocket entrypoints\n/healthz, /readyz, /mcp, /mcp/ws"]
    Registry["Tool registry\ninputSchema + outputSchema"]
    Tools["Tool handlers\nretrieval, validation, handoff"]
  end

  subgraph Evidence["Tier-0 Evidence and Federation Layer"]
    Chemical["Chemical identity"]
    Hazard["Hazard datasets"]
    Exposure["Exposure + HTTK"]
    Bioactivity["Bioactivity + AOP link-outs"]
    Metadata["Model cards + applicability"]
    Interop["Portable evidence packs\nAOP / PBPK handoff builders"]
  end

  subgraph Contracts["Contract and Artifact Layer"]
    McpSchemas["MCP response schemas\n/docs/contracts/schemas"]
    Portable["Portable object schemas\n/schemas"]
    Tests["Catalog, schema, and handoff tests"]
  end

  subgraph Upstream["Upstream Sources"]
    CTX["EPA CTX APIs"]
    Bundles["Packaged metadata bundles"]
  end

  Clients --> Router
  Router --> Registry
  Registry --> Tools
  Tools --> Chemical
  Tools --> Hazard
  Tools --> Exposure
  Tools --> Bioactivity
  Tools --> Metadata
  Tools --> Interop
  Chemical --> CTX
  Hazard --> CTX
  Exposure --> CTX
  Bioactivity --> CTX
  Metadata --> Bundles
  Tools --> McpSchemas
  Interop --> Portable
  McpSchemas --> Tests
  Portable --> Tests
```

The current implementation follows a layered model:

- `FastAPI + JSON-RPC` expose `/mcp` and `/mcp/ws`, with `/healthz` and `/readyz` kept separate from domain logic.
- `Retrieval resources` own CompTox-native evidence access for chemical, hazard, exposure, bioactivity, cheminformatics, and metadata.
- `Interop tools` package portable evidence objects for downstream MCP consumers without cloning AOP OECD semantics or PBPK execution semantics.
- `Contract layers` are split intentionally: `docs/contracts/schemas/` for MCP response wrappers, `schemas/` for cross-suite portable evidence objects.
- `Regression gates` keep README, live discovery, published schemas, and AOP/PBPK handoff fixtures aligned before release.

## What's New In v0.2.0

- Repositioned CompTox MCP as the suite's Tier-0 evidence and federation MCP instead of a partially advertised orchestrator surface.
- Published portable evidence objects under `schemas/` for identity, hazard, exposure, bioactivity, AOP linkage, PBPK context, and bundled evidence packs.
- Added domain-specific MCP response namespaces for `hazard/`, `exposure/`, `bioactivity/`, and `workflow/`.
- Added a public `interop` resource exposing `assemble_comptox_evidence_pack`, `build_aop_linkage_summary`, and `build_pbpk_context_bundle`.
- Added deterministic release gates so README drift, catalog drift, and AOP/PBPK handoff drift fail CI before publish.

## Published Schemas

The portable CompTox handoff objects are now published as machine-readable JSON Schemas under `schemas/`, with matching examples under `schemas/examples/`.

Published object family:

- `schemas/chemicalIdentityRecord.v1.json`
- `schemas/hazardEvidenceSummary.v1.json`
- `schemas/exposureEvidenceSummary.v1.json`
- `schemas/bioactivityEvidenceSummary.v1.json`
- `schemas/aopLinkageSummary.v1.json`
- `schemas/pbpkContextBundle.v1.json`
- `schemas/comptoxEvidencePack.v1.json`

Design intent:

- keep the stable core fields required and allow additive convenience fields
- keep AOP OECD normalization outside CompTox MCP
- keep PBPK execution, qualification, and internal exposure objects outside CompTox MCP
- make the portable evidence layer consumable by downstream validators and orchestrators without scraping examples out of tests

See `schemas/README.md`, `tests/test_portable_schemas.py`, and `tests/test_cross_suite_handoffs.py` for the maintainer gates that keep published objects aligned with live payload generation.

## Why this project exists

Regulatory and research teams rely on the CompTox API for high-quality chemical, exposure, and hazard data. Traditional workflows involve bespoke scripts or manual dashboard exports that are hard to share with AI copilots.  

The EPA CompTox MCP server wraps those workflows in a **secure, programmable interface**:

- **One MCP surface (`/mcp` HTTP + `/mcp/ws` WebSocket)** delivers discovery and execution across chemical, bioactivity, exposure, hazard, metadata, interop, and supporting utility catalogues.
- **Evidence federation role** – CompTox acts as the suite's source-grounded evidence ingress layer for downstream AOP, PBPK, O-QT, and orchestration workflows.
- **Guardrails + provenance** – JSON Schema validation, metadata attachments, transport audit hooks, and signed release attestations improve downstream reproducibility.
- **Agent friendly** – tested with Codex CLI, Gemini CLI, and Claude (see [integration guide](docs/integration_guides/mcp_integration.md)).

> Experimental predictive and orchestrator components still exist in this repository, but they are not part of the default public MCP tool catalog exposed by the server today.

---

## Feature snapshot

| Capability | Description |
| --- | --- |
| 🌐 **Dual MCP Transports** | JSON-RPC over HTTP (`/mcp`) and WebSocket (`/mcp/ws`) with identical tool catalogues. |
| 🧬 **CompTox Tooling** | Chemical, bioactivity, exposure, hazard, metadata, and supporting utility helpers mapped to structured MCP tools. |
| 🔗 **Evidence Federation** | Designed as the suite's Tier-0 evidence ingress layer, packaging source-grounded CompTox outputs for downstream consumers. |
| 🛡️ **Guardrail Enforcement** | JSON Schema response validation, metadata attachments, audit hooks, and transport safety controls improve reproducibility. |
| ⚙️ **Configurable by Design** | Pydantic settings with `.env` support for API keys, retries, auth bypass, transport tuning, and observability. |
| 🤖 **Agent Ready** | Verified with Codex CLI, Gemini CLI, and Claude Code; includes quick-start config snippets. |

---

## Table of contents

1. [Architecture](#architecture)
2. [Published schemas](#published-schemas)
3. [Quick start](#quick-start)
4. [Release verification](#release-verification)
5. [Configuration](#configuration)
6. [Tool catalog](#tool-catalog)
7. [Running the server](#running-the-server)
8. [Integrating with coding agents](#integrating-with-coding-agents)
9. [Output artifacts](#output-artifacts)
10. [Security checklist](#security-checklist)
11. [Current limitations](#current-limitations)
12. [Development notes](#development-notes)
13. [Contributing](#contributing)
14. [Security policy](#security-policy)
15. [Support](#support)
16. [Code of conduct](#code-of-conduct)
17. [Citation](#citation)
18. [Roadmap](#roadmap)
19. [License](#license)

---

## Quickstart TL;DR

```bash
# 1) install
git clone https://github.com/ToxMCP/comptox-mcp.git
cd comptox-mcp
pip install -e .

# 2) configure
cp .env.example .env
# set CTX_API_KEY in .env

# 3) run
uvicorn epacomp_tox.transport.websocket:app --host 0.0.0.0 --port 8000 --reload

# 4) verify
curl -s http://localhost:8000/healthz | jq .
curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq '.result.tools | length'
```

## Quick start

```bash
git clone https://github.com/ToxMCP/comptox-mcp.git
cd comptox-mcp
pip install -e .
cp .env.example .env
uvicorn epacomp_tox.transport.websocket:app --reload
```

> **Important:** The server needs a valid EPA CompTox API key. Set `CTX_API_KEY` (preferred) or `EPA_COMPTOX_API_KEY` in `.env` before starting the transport.

With the server running, MCP clients can connect to `http://localhost:8000/mcp` (HTTP) or `ws://localhost:8000/mcp/ws` (WebSocket).

Once the server is running:

- HTTP MCP endpoint: `http://localhost:8000/mcp`
- WebSocket MCP endpoint: `ws://localhost:8000/mcp/ws`
- Health check: `http://localhost:8000/healthz`
- Readiness check: `http://localhost:8000/readyz`
- Architecture docs: `docs/architecture_overview.md`
- Contract docs: `docs/contracts/README.md`
- Release verification guide: `docs/releases/release_artifact_verification.md`

## Verification (smoke test)

Once the server is running:

```bash
# health
curl -s http://localhost:8000/healthz | jq .

# list MCP tools
curl -s http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq '.result.tools | length'

# live interop smoke
python scripts/mcp_interop_smoke.py --endpoint http://localhost:8000/mcp --json
```

---

## Release verification

For published GitHub releases, signed provenance/SBOM attestation verification is documented in [`docs/releases/release_artifact_verification.md`](docs/releases/release_artifact_verification.md).

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
| Bioactivity & AOP link-outs | `search_bioactivity_terms`, `get_bioactivity_summary_by_dtxsid`, `get_bioactivity_aop` | Surface ToxCast/Tox21 summaries, assay metadata, and AOP crosswalks from CompTox bioactivity APIs. |
| Exposure & hazard | `search_cpdat`, `search_httk`, `search_hazard`, `get_hazard_toxval` | Batch-normalized access to CTX exposure datasets plus granular hazard endpoints (ToxValDB, ToxRefDB, cancer, genetox, ADME/IVIVE, IRIS, PPRTV, HAWC). |
| Metadata & governance | `metadata_get_model_card`, `metadata_list_applicability_domain`, `metadata_get_applicability_domain` | Fetch model cards, applicability-domain policies, and audit metadata. |
| Interop handoff builders | `assemble_comptox_evidence_pack`, `build_aop_linkage_summary`, `build_pbpk_context_bundle` | Package portable evidence objects and downstream-ready handoff summaries for AOP and PBPK MCP consumers without duplicating their semantics. |
| Utility helpers | `opsin_convert_name`, `indigo_convert_molfile` | Provide supporting conversions for downstream automations. |

The default server currently registers eight public resources: chemical, bioactivity, exposure, hazard, chemical list, cheminformatics, metadata, and interop. Full schema definitions (input and output) are returned via the MCP `tools/list` call. See [`tests/test_resources.py`](tests/test_resources.py) for examples of exercising each category.

### Experimental components

The repository also contains predictive and orchestrator code under `src/epacomp_tox/predictive/` and `src/epacomp_tox/orchestrator/`. Treat those modules as experimental until they are registered in the default server, documented as part of the canonical tool catalog, and backed by stable public response contracts.

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
- `structuredContent.metadata`: when available, includes rate-limit information, validation metadata, and session metadata.
- Default registered tools are retrieval and federation oriented; experimental predictive/orchestrator modules in this repository are not part of the canonical public surface yet.

---

## Security checklist

- Disable `BYPASS_AUTH` and front the MCP server with OAuth/OIDC once deployed beyond local development.
- Restrict `CORS_ALLOW_ORIGINS` to approved hosts when exposing the HTTP transport.
- Rotate `CTX_API_KEY` regularly and store secrets outside the repository (e.g. cloud secret manager or OS keychain).
- Monitor `/metrics` for negotiated capability changes and unexpected spikes in `tools/call` failures.
- Enable HTTPS/TLS at the ingress or reverse proxy layer.
- Keep GitHub branch protection, dependency review, and CodeQL scanning enabled on the canonical repository.
- Pin GitHub Actions workflows to immutable commit SHAs and update them intentionally during maintenance windows.
- Generate and retain a CycloneDX SBOM for release artifacts so downstream consumers can audit package composition.
- Publish signed provenance and SBOM attestations for release artifacts so consumers can verify what was built and released.
- Follow coordinated vulnerability disclosure guidance in [`SECURITY.md`](SECURITY.md).

---

## Development notes

### Architecture snapshot

```
┌────────────────┐       ┌────────────────────────────┐       ┌──────────────────────┐
│ MCP Client     │  MCP  │ FastAPI App                │  MCP  │ CompTox Resources    │
│ (CLI / IDE)    │──────▶│ HTTP (/mcp) & WS (/mcp/ws) │──────▶│ • chemical           │
└────────────────┘       │ • tool registry            │       │ • bioactivity        │
       │                 │ • JSON-RPC dispatch        │       │ • exposure / hazard  │
       ▼                 │ • response validation      │       │ • metadata / interop │
                         └────────────────────────────┘       │ • utility catalogs   │
                                                              └──────────────────────┘
```

### Guardrails & governance

- Applicability-domain definitions, policy defaults, and remediation steps live under `metadata/` with JSON Schema validation.
- Response contracts live under `docs/contracts/schemas/` (see `docs/contracts/README.md`) and are enforced before MCP responses are returned; upstream failover policies are summarized in `docs/contracts/endpoint-matrix.md`.
- Experimental predictive/orchestrator modules remain in-repo design and implementation assets; they are not part of the default public tool catalog until explicitly registered and documented.

### Testing & quality gates

- `tests/test_mcp_conformance_suite.py` covers handshake, catalog discovery, and streaming behaviours.
- `tests/test_tool_contracts.py` enforces output schema declarations for the registered resources.
- `scripts/smoke_ctx.sh` runs integration smoke tests against the live CTX API.
- `scripts/mcp_http_smoke.sh` performs a quick JSON-RPC handshake and tool listing against the HTTP transport.
- `scripts/mcp_interop_smoke.py` validates the public interop tool path end-to-end over the HTTP transport.
- Documentation builds (`scripts/build_docs.sh`) and CI workflows keep diagrams and links healthy.
- Experimental predictive/orchestrator suites remain valuable internal regression coverage, but they should not be presented as canonical public-surface checks.

---

## Roadmap

- Add CTX-backed golden payload capture for interop outputs so release checks cover both deterministic stubs and live upstream normalization.
- Expand workflow contract coverage beyond the three current interop tools only where the public surface is stable enough to justify dedicated schemas.
- Publish a cleaner contract manifest resource for downstream consumers that inventories portable objects, MCP response schemas, and live discovery metadata together.
- Revisit predictive/orchestrator publication only after the default server, contracts, and docs all agree.

---

## Current limitations

- Predictive and orchestrator code still exists in-repo, but it is not part of the default public MCP tool catalog.
- CompTox MCP publishes AOP linkage summaries, but OECD-style mechanistic normalization still belongs in `aop-mcp`.
- CompTox MCP publishes PBPK context bundles, but PBPK execution, qualification, uncertainty synthesis, and internal exposure objects still belong in `pbpk-mcp`.
- BER logic, stop/continue/refine policy, and final NGRA decisions remain out of scope for this server.
- Live evidence retrieval still depends on upstream CTX availability and API credentials.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow, coding standards, and PR expectations.

## Security policy

See [SECURITY.md](SECURITY.md) for coordinated disclosure guidance and supported reporting channels.

## Support

See [SUPPORT.md](SUPPORT.md) for public support, bug-reporting, and non-security guidance.

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for collaboration expectations across the project and suite.

## Citation

If you use this project in research or derived tooling, please cite:

- Ivo Djidrovski. *BioRxiv preprint*. DOI / link: [10.64898/2026.02.06.703989v1](https://www.biorxiv.org/content/10.64898/2026.02.06.703989v1)

---

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## Acknowledgements

- EPA's Center for Computational Toxicology and Exposure (CCTE)
- The ctx-python project for the official CompTox Python bindings
- The Model Context Protocol community for defining the automation surface we target

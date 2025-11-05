# MCP Phase 2 Architecture Overview

This document captures the end-to-end architecture for the EPA CompTox MCP as of the Phase 2 refresh. It ties together the transport, orchestrator, predictive micro-servers, metadata service, and audit tooling referenced across the README and developer guides.

## 1. Component Stack

```
┌───────────────────────────────┐
│ Agentic SDK Clients           │
│  • LLM agents & workflows     │
│  • Conformance harness        │
└──────────────┬────────────────┘
               │ JSON-RPC (MCP)
┌──────────────▼────────────────┐
│ FastAPI MCP Transport         │
│  • `/mcp/ws` WebSocket        │
│  • Handshake negotiation      │
│  • Tool/resource catalogues   │
│  • Streaming + cancellation   │
│  • Logging + heartbeat hooks  │
└──────────────┬────────────────┘
               │ CQRS commands/events
┌──────────────▼────────────────┐
│ Orchestrator Service          │
│  • Identifier resolution      │
│  • Workflow sequencing        │
│  • Policy enforcement         │
│  • Audit bundle writer        │
└──────────────┬────────────────┘
         ┌─────┼───────────────────────────────────────────────┐
         │     │                                               │
┌────────▼─┐ ┌──▼────────┐ ┌──────────────┐ ┌──────────────────▼───┐
│ CTX API  │ │ Metadata  │ │ Predictive   │ │ Observability & Audit │
│ Resources│ │ Service   │ │ Micro-servers│ │ (S3, Elastic, etc.)   │
│ (REST)   │ │ (model    │ │ (TEST/OPERA/ │ │ - Audit bundle store   │
│          │ │ cards, AD │ │  GenRA)      │ │ - Structured logging   │
└──────────┘ │ policies) │ └──────────────┘ │ - Metrics exporters    │
             └───────────┘                  └────────────────────┘
```

## 2. Tool Execution Sequence

```
Agent                     Transport                     Orchestrator                    Downstream Services
-----                     ----------                    -------------                    -------------------
initialize ─────────────▶ authenticate + negotiate
                          ◀────────────── handshake (protocol, capabilities, session)
tools/list ─────────────▶ returns catalog snapshot
tools/call search_chemical
 arguments = {...} ─────▶ validate schema & quota
                          events/log "routing search_chemical"
                          ───────────▶ orchestrator.dispatch()
                                                │
                                                ├──▶ Metadata service hydrates model card
                                                ├──▶ CTX chemical.search endpoint
                                                └──▶ Policy engine enforces AD
                          ◀────────── events/result chunk(s)
tools/cancel? ──────────▶ (optional) propagate cancel token
                          ◀────────── events/end + final JSON-RPC response
```

Key guarantees:
- Transport emits structured events (`log`, `result`, `error`, `end`) aligned with MCP protocol `2025-06-18`.
- Request IDs and CTX correlation IDs propagate through every component and are persisted in audit bundles.
- Policy decisions (AD block/warn) are surfaced as structured payloads and added to the audit artefact alongside model provenance.

## 3. Guardrail Enforcement Flow

```
┌──────────────┐      ┌──────────────────┐      ┌───────────────────┐      ┌────────────────────┐
│ MCP Request  │ ---> │ Orchestrator     │ ---> │ Policy Engine      │ ---> │ Audit Bundle Store │
└──────────────┘      │ 1. Resolve IDs   │      │ - AD rules (block) │      │ - request metadata │
                      │ 2. Fetch metadata│      │ - AD rules (warn)  │      │ - AD verdict       │
                      │ 3. Route service │      │ - Policy overrides │      │ - model provenance │
                      └──────────────────┘      └───────────────────┘      └────────────────────┘
                                   │
                                   ▼
                      Predictive Micro-server + CTX APIs
```

- Applicability-domain rules are sourced from `metadata/applicability_domains/` and reference the model card version.
- Guardrail failures return structured `events/error` payloads with remediation hints while writing full artefacts to the audit store.
- Audit bundles are retrievable via `orchestrator_get_audit_bundle` and contain MCP session IDs, CTX request IDs, AD rationale, and policy state.

## 4. Success Metrics

- **Handshake Reliability**: 99.9% handshake success with protocol negotiation across supported agents.
- **Guardrail Coverage**: 100% predictive workflows enforce AD policies with non-bypassable blocking in production environments.
- **Audit Completeness**: Every orchestrated execution yields an audit bundle with provenance, AD verdict, and tool chain trace.
- **Streaming Latency**: <500 ms between upstream completion and `events/result` delivery for median payloads.
- **Documentation Parity**: README + docs/ content reflect current endpoints, policies, and release notes; CI fails if doc build or link checks break.

## 5. Testing & Validation

- Conformance tests (`tests/test_mcp_conformance_suite.py`) cover handshake, catalog pagination, streaming, and cancellation paths.
- Predictive regression tests validate AD behaviours, including block vs warn routing and remediation messaging.
- `scripts/smoke_ctx.sh` performs live CTX smoke tests with environment-provided credentials.
- Documentation automation (`scripts/build_docs.sh`, `.github/workflows/docs.yml`) ensures diagrams, examples, and references stay in sync.
- QA checklists under `docs/qa/` provide human validation steps before releases (transport, orchestrator, predictive, metadata).

## 6. Configuration Reference

- `CTX_API_BASE_URL`, `CTX_USE_LEGACY`, `CTX_API_KEY`: CTX connectivity.
- `MCP_MAX_SESSIONS`, `MCP_HEARTBEAT_SECONDS`, `MCP_STREAM_CHUNK_SIZE`: Transport behaviour.
- `MCP_POLICY_PROFILE`: Selects guardrail profile (`dev`, `staging`, `prod`).
- `AUDIT_BUNDLE_BUCKET`, `AUDIT_BUNDLE_PREFIX`: Audit storage targets.
- `MODEL_METADATA_SCHEMA`: Override path to the JSON Schema when testing.

Refer to `docs/configuration.md` (pending) for the exhaustive list and defaults.

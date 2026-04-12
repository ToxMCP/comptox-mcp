# Observability & Governance Requirements (MCP Phase 2)

> Historical/internal planning document. These requirements cover broader transport, predictive, and orchestrator ambitions beyond the current default public MCP surface released in `v0.2.2`.

## Overview
To support MCP Phase 2, the platform must expose consistent telemetry, audit, and policy hooks across transport, metadata, predictive services, and the GenRA orchestrator. This document captures the requirements aligned with stakeholder needs.

## Stakeholder Goals
- **Operations:** Rapid outage triage, visibility into latency/throughput, proactive alerting.
- **Regulatory / Compliance:** Immutable audit trails with retention policies, demonstrable applicability domain (AD) enforcement, consent handling.
- **Platform Engineering:** Extensible policy engine, adherence to existing logging / metrics standards.

## Logging Requirements
- Emit structured JSON logs with `timestamp`, `service`, `workflowRunId` (when applicable), correlation / request IDs, severity.
- Redact sensitive payloads (API keys, PII) before logging.
- Transport logs include handshake events, tool calls, cancellations, errors, and duration metrics.
- Predictive services log AD check outcomes, policy decisions, and fallback behaviour.
- Orchestrator logs state transitions, guardrail events, evidence synthesis summaries, audit storage metadata (bundle checksum, path).

## Metrics & Tracing
- Expose Prometheus-compatible `/metrics` endpoint per service with:
  - Request counters (success/failure segmented by tool/service).
  - Latency histograms (p50, p95, p99).
  - AD failure counts per model.
  - Retry attempts, rate-limit hits, cancellation counts.
- Surface negotiated MCP capability flags (streams, cancel, etc.) via `MCPServer.get_transport_metrics()` so dashboards capture client opt-in rates. Example Prometheus and OTEL Collector configs are available under `deploy/prometheus_scrape.yaml` and `deploy/otel_collector_metrics.yaml` for quick adoption.
- Adopt OpenTelemetry tracing. Each request carries a trace ID with spans covering transport → predictive services → orchestrator.
- Correlate orchestrator `workflowRunId` with trace ID for cross-service debugging.

## Audit & Retention
- Persist audit bundles via `AuditBundleStore` (or production equivalent) with SHA256 checksums and attachment metadata.
- Metadata index includes `workflowRunId`, `createdAt`, scenario, retention class.
- Default retention window: 18 months (configurable per regulatory program).
- Storage must support immutability / append-only writes and enforce role-based access control (RBAC).
- Provide CLI/API for retrieving bundles, listing runs, and querying metadata.

## Policy Hooks
- Configurable policy engine with versioned JSON definitions:
  - Enforce AD pass (block/warn) before predictions execute.
  - Require consent flags for high-risk endpoints (e.g., human toxicity).
  - Rate-limit enforcement with exponential backoff; log policy outcomes.
- Support real-time overrides via admin API; audit trail logs actor identity, timestamp, and action.
- Policy configuration stored in version control with change history.

## Monitoring & Alerting
- Integrate metrics into central dashboards (Grafana, Datadog, etc.).
- Alert thresholds:
  - Transport or predictive error rate above baseline.
  - AD failure spikes.
  - Audit bundle persistence errors or storage unavailability.
- Document escalation matrix and on-call rotation for each alert.

## Security & Access Control
- Logs/metrics adhere to least-privilege access; audit data encrypted at rest and in transit.
- Service accounts follow quarterly credential rotation with documented runbooks.
- Enforce data retention policies; implement automated purging after retention window.

## Deliverables
- Logging configuration and sample log schemas.
- Metrics/alerting dashboard definitions.
- Policy engine configuration schema + example policies.
- Operational runbooks covering log access, metric dashboards, incident response, credential rotation.
- Governance review checklist capturing stakeholder approvals.

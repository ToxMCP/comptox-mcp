# MCP Transport Metrics Integration Guide

This runbook walks through connecting the EPA CompTox MCP transport `/metrics`
endpoint to common observability stacks. The endpoint exposes Prometheus gauges
derived from `MCPServer.get_transport_metrics()`, reporting session counts and
capability-negotiation outcomes.

## 1. Prerequisites
- MCP transport running with `/metrics` enabled via
  `EPACOMP_MCP_METRICS_ENABLED=1` (FastAPI app exposed on HTTP).
- A bearer token accepted by the MCP auth policy, unless
  `MCP_METRICS_BYPASS_AUTH=1` is deliberately set behind a trusted gateway.
- Network connectivity from Prometheus / the OTEL Collector to the transport.
- Access to the target monitoring configuration repo (GitOps) or cluster.

## 2. Prometheus Scrape Job
1. Copy `deploy/prometheus_scrape.yaml` into your Prometheus configuration
   repository.
2. Replace the `targets` hostname with the service address for your
   environment (e.g., Kubernetes service DNS or load balancer).
3. Add the required `Authorization: Bearer <token>` header or configure a
   gateway-side scrape identity.
4. Adjust labels (such as `env`, `service`) to match your dashboard naming.
5. Reload Prometheus or commit the change to your GitOps pipeline.

Verify:
- Open the Prometheus UI (`/graph`) and query `mcp_sessions_total` to confirm
  the transport is emitting session counts.
- Check that capability gauges (e.g., `mcp_capability_sessions_total`) appear.

## 3. OpenTelemetry Collector Pipeline
1. Copy `deploy/otel_collector_metrics.yaml` into your OTEL Collector config.
2. Update the `targets` field, `env` labels, and the OTLP exporter endpoint to
   match your telemetry backend.
3. Supply authentication headers or certificates required by your exporter.
4. Reload the collector (or redeploy the collector DaemonSet) to pick up the
   new pipeline.

Verify:
- Use your telemetry backend’s query tools to confirm `mcp_sessions_total` and
  capability gauges are ingested.
- Ensure the exporter shows successful sends (no error logs in OTEL collector).

## 4. Dashboard & Alert Hooks
- Add panels showing active vs closed sessions and opt-in rates for
  `tools.streams`, `tools.cancel`, etc.
- Consider an alert when `mcp_capability_sessions_total{capability="tools.streams",state="enabled"}`
  drops unexpectedly (could signal clients opting out of streaming).
- Include heartbeat timeout counts if you extend metrics in the future.

## 5. QA Checklist Updates
- Update `docs/qa/transport_smoke_checklist.md` to include a metric scrape
  validation step (already documented in this commit).

## 6. Troubleshooting
- If `/metrics` returns 404, ensure `EPACOMP_MCP_METRICS_ENABLED=1` and that
  your deployment uses the refreshed application module
  (`epacomp_tox.transport.websocket:app`).
- If `/metrics` returns 401 or 403, check the scrape token issuer, audience,
  JWKS, and scopes against `MCP_AUTH_*` settings.
- Verify network policies allow the monitoring stack to reach port `8000` (or
  your chosen bind port).
- Enable debug logging on the OTEL collector (`service.telemetry.metrics.level = detailed`)
  to inspect scrape progress.

## 7. Change Management
- Record the monitoring integration in your runbooks and incident response playbooks.
- Notify the observability team to add long-term retention or SLO dashboards as
  needed.

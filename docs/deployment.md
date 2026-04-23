# Deployment Guide

This guide explains how to run the EPA CompTox MCP transport service in production-quality environments. It covers uvicorn/gunicorn settings, container packaging, health probes, and TLS considerations introduced during Phase 2.

## Prerequisites

- Python 3.11 (or newer) for bare-metal deployments.
- Valid CompTox credentials exposed via `CTX_API_KEY` (preferred) or `EPA_COMPTOX_API_KEY`.
- Network access to the CompTox CTX API endpoint configured with `CTX_API_BASE_URL` (defaults to `https://comptox.epa.gov/ctx-api`).
- Production MCP bearer-token validation configured with `MCP_AUTH_ISSUER`, `MCP_AUTH_AUDIENCE`, `MCP_AUTH_JWKS_URL`, and an externally reachable `MCP_RESOURCE_URL`.

## Running with Gunicorn + Uvicorn Workers

The repository ships a production-ready Gunicorn configuration under `deploy/gunicorn_conf.py`. To launch the service directly on a VM:

```bash
export CTX_API_KEY="your-key"
export EPACOMP_MCP_BIND="0.0.0.0:8000"   # Optional override

python -m pip install "uvicorn[standard]" gunicorn .
gunicorn epacomp_tox.transport.websocket:app -c deploy/gunicorn_conf.py
```

Key environment overrides:

| Variable | Purpose | Default |
|----------|---------|---------|
| `EPACOMP_MCP_BIND` | Bind address/port | `0.0.0.0:8000` |
| `EPACOMP_MCP_WORKERS` | Number of workers | `2 * CPU + 1` |
| `EPACOMP_MCP_TIMEOUT` | Worker timeout (seconds) | `120` |
| `EPACOMP_MCP_GRACEFUL_TIMEOUT` | Graceful shutdown window | `30` |
| `EPACOMP_MCP_KEEPALIVE` | HTTP keepalive (seconds) | `5` |
| `EPACOMP_MCP_LOG_LEVEL` | Gunicorn log level | `info` |
| `MCP_AUTH_ISSUER` | Expected OIDC issuer for MCP JWTs | unset |
| `MCP_AUTH_AUDIENCE` | Expected MCP JWT audience | unset |
| `MCP_AUTH_JWKS_URL` | JWKS URL for JWT signature verification | unset |
| `MCP_AUTH_REQUIRED_SCOPES` | Required bearer scopes for MCP calls | unset |
| `MCP_RESOURCE_URL` | Canonical protected MCP resource URL | `http://localhost:8000/mcp` |
| `MCP_RATE_LIMIT_REQUESTS_PER_MINUTE` | Process-local per-subject/IP tool-call limit | `120` |
| `MCP_RATE_LIMIT_BURST` | Process-local token-bucket burst size | `20` |

All workers use the `uvicorn.workers.UvicornWorker` class, so the WebSocket transport runs on ASGI-native workers.

## Container Image

The `deploy/Dockerfile` produces a minimal Python 3.11 image with non-root execution and baked-in Gunicorn defaults.

Build and run:

```bash
docker build -t comptox-mcp -f deploy/Dockerfile .
docker run --rm -p 8000:8000 \
  -e CTX_API_KEY="your-key" \
  comptox-mcp
```

To override Gunicorn settings at runtime:

```bash
docker run --rm -p 8000:8000 \
  -e CTX_API_KEY="your-key" \
  -e EPACOMP_MCP_WORKERS=4 \
  comptox-mcp
```

If you need to run a custom command inside the container:

```bash
docker run --rm -it comptox-mcp uvicorn epacomp_tox.transport.websocket:app --reload
```

The image exposes port `8000` and ships with `/app/gunicorn_conf.py` plus `/app/entrypoint.sh`. The entrypoint starts Gunicorn unless command overrides are supplied.

## Health Endpoints

`create_app` now exposes:

- `GET /healthz`: liveness signal, returns immediate 200 when the process is responsive.
- `GET /readyz`: readiness probe. Performs a strict authenticated CTX probe via `MCPServer.check_health(probe_mode="readiness")` against stable upstream API routes. Bare reachability to `/ctx-api/health` is not enough. The endpoint returns HTTP 503 when CTX credentials are missing, rejected, or when no authenticated probe succeeds. If a prior successful probe exists it will be returned with `status: degraded`.
- `GET /metrics`: Prometheus-compatible transport metrics derived from `MCPServer.get_transport_metrics()` when `EPACOMP_MCP_METRICS_ENABLED=1`. Gauges report session counts (`status=active|closed`) and negotiated capability adoption (`capability=tools.streams`, `scope=all|active`, `state=enabled|disabled`). The endpoint requires the configured bearer auth unless `MCP_METRICS_BYPASS_AUTH=1` is explicitly set for deployments where a trusted gateway already protects the scrape path. Integrate the scrape endpoint with your platform’s monitoring stack—see `deploy/prometheus_scrape.yaml` for a vanilla Prometheus job and `deploy/otel_collector_metrics.yaml` for an OpenTelemetry Collector pipeline.
- `GET /.well-known/oauth-protected-resource`: OAuth Protected Resource Metadata for MCP clients. Unauthorized `/mcp` HTTP and `/mcp/ws` WebSocket requests return `WWW-Authenticate` challenges that point clients at this metadata.

Configure Kubernetes probes (example):

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8000
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /readyz
    port: 8000
  periodSeconds: 30
  timeoutSeconds: 5
  failureThreshold: 3
```

`/readyz` is intentionally stricter than `/healthz`. Use it only when the deployment is expected to have working CTX credentials and authenticated upstream access.

## TLS and Network Hardening

The container runs plain HTTP by default. Recommended options:

1. Terminate TLS at an upstream proxy (Ingress, Envoy, NGINX, or a service mesh). Ensure the proxy forwards `X-Forwarded-For` and `X-Forwarded-Proto` headers when mutual TLS or audit logging is required.
2. If terminating TLS within the container is necessary, supply the standard uvicorn flags via the entrypoint override, for example:

```bash
docker run --rm -p 8443:8443 \
  -e CTX_API_KEY="your-key" \
  comptox-mcp \
  gunicorn epacomp_tox.transport.websocket:app \
    -c /app/gunicorn_conf.py \
    --keyfile /certs/server.key \
    --certfile /certs/server.crt \
    --bind 0.0.0.0:8443
```

3. Use a network policy or firewall rule to restrict incoming traffic to trusted agent subnets and Platform load balancers.
4. Keep `BYPASS_AUTH=0` in production. Startup fails when production auth is enabled but issuer, audience, or JWKS settings are incomplete.
5. Use the built-in process-local rate limiter as defense in depth, and enforce shared limits at the ingress/gateway for horizontally scaled deployments.

## Logging and Observability

- Gunicorn access logs stream to STDOUT. Error logs stream to STDERR.
- Uvicorn logs include session IDs emitted by `MCPWebSocketSession`.
- To attach OpenTelemetry or structured logging targets, configure an upstream agent (e.g., Fluent Bit) or extend the logging configuration via `GUNICORN_CMD_ARGS` / `UVICORN_LOG_LEVEL`.

Metrics and distributed traces will be folded into Task 6 (Observability) once the policy engine is in place.

## Graceful Shutdown

- `/app/entrypoint.sh` runs Gunicorn with `preload_app = True` and `graceful_timeout = 30`.
- Kubernetes (or other orchestrators) should send SIGTERM and wait at least 30 seconds before SIGKILL to allow active WebSocket sessions to drain.

## Next Steps

- Wire the container into CI publishing once nightly deployments are established.
- Integrate MCP conformance tests (Task 1.6) with the container image.
- Finalize TLS certificate automation with the Platform infra team.

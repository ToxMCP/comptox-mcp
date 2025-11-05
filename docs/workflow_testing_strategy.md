# Workflow Testing Strategy – MCP Phase 2

## Objectives
- Guarantee transport, predictive, and orchestrator services behave reliably across success, guardrail, and failure scenarios.
- Provide repeatable automation for PR gating, nightly validation, and high-scale stress exercises.
- Deliver actionable diagnostics and reports consumable by SMEs, platform engineering, and regulatory reviewers.

## Scope & Coverage Matrix
| Layer | Focus Areas | Existing Assets | Planned Additions |
| --- | --- | --- | --- |
| **Unit** | Request parsing, AD policy enforcement, metadata serialization | `tests/test_resources.py`, `tests/test_predictive_services.py`, orchestrator unit suites | Expand coverage for new policy hooks, audit persistence failure modes |
| **Contract / Integration** | MCP transport (handshake, discovery, tools), model metadata, predictive micro-servers | Conformance suite (Task 1), `tests/test_mcp_conformance_suite.py`, `tests/test_predictive_regression.py` | Dedicated transport harness exercising malformed frames, auth flow, timeout recovery |
| **End-to-End Workflows** | Identifier resolution → CTX staging → predictive execution → audit bundle persistence | `tests/test_orchestrator_stages.py`, `scripts/demo_genra_orchestrator.py` | Scenario suites for acute toxicity, exposure prioritization, GenRA RAx with golden bundles & HTML/json reporting |
| **Load / Stress** | Multi-chemical batches, concurrency, transport back-pressure | — | Locust/k6 scripts targeting websocket transport + predictive services with real/sandbox data |

## Tooling & Data
- **Core test runner:** `pytest` (unit, integration, orchestrator scenarios). Leverage parametrization for scenario coverage.
- **Transport conformance:** existing JSON fixtures + MCP conformance suite wired into harness.
- **Scenario execution:** CLI wrappers (existing demo script, upcoming scenario drivers) to facilitate golden bundle capture.
- **Load testing:** Locust (Python) for websocket / REST endpoints and k6 for HTTP micro-services. Reusable configuration files with environment overrides for sandbox vs. staging.
- **Data fixtures:** curated sandbox identifiers (DTXSID, CASRN) per scenario with expected AD outcomes. Store under `tests/fixtures/workflows/`.

## Execution Cadence
| Pipeline | Trigger | Suites | Reporting |
| --- | --- | --- | --- |
| PR Gate | Every pull request | Unit + contract + fast orchestrator smoke scenarios | Pytest JUnit + summary comment |
| Nightly Sandbox | 01:00 UTC daily | Full orchestrator scenarios, predictive regression, metadata validation | HTML bundle reports, JSON provenance summaries, Slack/email alerts |
| Weekly Load | Off-peak (e.g., Sunday) | Locust/k6 runs at 10× expected load | Aggregated latency/throughput dashboards, CSV export |

## Reporting & Diagnostics
- **Audit bundles:** persisted via `AuditBundleStore` with SHA256 checksums and attachments; CLI (`scripts/genra_bundle_cli.py`) supports retrieval for failure analysis.
- **Scenario reports:** generate HTML dashboards summarizing branch outcomes, AD statuses, and evidence bands; archive alongside bundle metadata.
- **Telemetry hooks:** ensure orchestrator logging includes workflowRunId to correlate with transport/predictive logs.

## Action Plan
1. **Harness Scaffolding**
   - Add `tests/workflows/` module orchestrating scenarios using existing `GenRAOrchestrator`.
- Capture golden bundles per scenario under `tests/fixtures/workflows/<scenario>/expected.json`.

### Observability Alignments
- Harness emits structured logs for scenario executions (workflowRunId, scenario name, duration). Future instrumentation will align with logging requirements in `docs/observability_requirements.md`.
- Stores bundle metadata (checksums, attachments) via `AuditBundleStore`, providing inputs for audit retention pipelines.
2. **Transport Harness**
   - Integrate MCP websocket client utilities; add fuzzed handshake cases and timeout recovery tests.
   - Record coverage via conformance suite output.
3. **Predictive Scenario Coverage**
   - Extend regression fixtures to include AD failure cases; ensure evidence synthesis metrics validated.
4. **Load Testing Scripts**
   - Author Locust file targeting websocket endpoints; parameterize chemical lists and concurrency.
   - Provide k6 script for REST-based predictive services.
5. **Automation**
   - Create GitHub Actions workflows (`ci-workflows.yml`, `nightly-workflows.yml`) wiring environment secrets, persistence directories, and artifact uploads.
   - Ensure nightly job stores bundle metadata + reports in `artifacts/workflows/<date>/`.

## Risks & Mitigations
- **External API instability:** add sandbox fallback configuration and skip markers when endpoints are offline; ensure nightly job reports skips.
- **Large artifact storage:** compress bundle attachments and enforce retention window via `AuditBundleStore.retentionDays`.
- **Test data drift:** version fixtures with checksum validation; add utility to re-capture golden bundles intentionally.

## Acceptance Criteria
- PR and nightly pipelines execute defined suites with deterministic pass/fail signals.
- Audit bundle harness emits retrievable artifacts for each orchestrator scenario run.
- Load test scripts produce benchmark summaries for each weekly execution.
- Documentation (README + `docs/genra_workflow.md`) references the harness usage, ensuring SMEs can reproduce scenarios locally.

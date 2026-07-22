# Documentation Refresh Content Plan (Phase 2)

> Historical planning artifact. The `v0.2.5` release preserves the public server boundary around evidence federation and interop; use this document as background context, not as the current public contract.

## Goals
- Update public and internal documentation to reflect MCP Phase 2 architecture, guardrails, observability, and developer tooling.
- Provide step-by-step guidance for SMEs and developers integrating via the Agentic SDK.
- Ensure governance artifacts (model cards, policy requirements) are discoverable and versioned.

## Key Deliverables
1. **Architecture Updates**
   - Refresh README overview with Phase 2 components (transport, metadata service, predictive micro-servers, orchestrator).
   - Expand `docs/mcp_design.md` to include orchestration diagrams, audit flow, and AD guardrails.
   - Document new module exports (`AuditBundleStore`, offline orchestrator, evidence synthesizer).
2. **Workflow & Testing Docs**
   - Finalize `docs/workflow_testing_strategy.md` and integrate nightly/CI instructions.
   - Add scenario-specific guides referencing offline harness and real CTX integration.
   - Provide troubleshooting checklist for orchestrator failures (AD blocks, missing CTX data).
3. **Observability & Governance**
   - `docs/observability_requirements.md` aligns telemetry/policy deliverables.
   - Cross-link from README, workflow docs, and future runbooks under `docs/operations/`.
4. **Agentic SDK Integration**
   - Example scripts (notebooks/CLI) showing orchestrator usage with Agentic SDK.
   - Sequence diagrams illustrating tool invocation order.
   - QA checklist for SMEs validating analogues, evidence, AD decisions.
5. **Runbooks & Operations**
   - Create `docs/operations/` folder housing deployment, monitoring, incident response, credential rotation guides.
   - Link runbooks to observability dashboards and alert routes.

## Action Items
- Inventory existing docs needing updates (README, docs/mcp_design.md, docs/predictive_services.md, etc.).
- Gather feedback from Platform, Compliance, and DX stakeholders on current gaps.
- Establish editorial timeline with checkpoints (draft, review, approve).
- Define acceptance criteria: DX team sign-off, SMEs approve scenario docs, operations validate runbooks.

## Next Steps
1. Draft architecture and workflow updates aligning with latest code structure.
2. Produce integration quickstart for the Agentic SDK, referencing offline orchestrator.
3. Build operations runbook template and populate with current processes.
4. Schedule doc review session with stakeholders; track tasks in the project tracker for implementation.

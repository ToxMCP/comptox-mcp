# Model Cards & Guardrail Policies

> This guide primarily covers in-repo predictive and orchestrator assets. These components remain experimental and are not part of the default public MCP tool catalog in `v0.2.6`.

This guide explains how to publish human-readable summaries for machine-readable model cards and applicability-domain (AD) policies, interpret guardrail outcomes, and follow the governance workflow required for release sign-off.

## 1. Rendering Model Cards

Use the helper script to generate Markdown and HTML views from the JSON model cards in `metadata/model_cards/`:

```bash
python scripts/render_model_cards.py
```

Outputs:
- Markdown: `docs/generated/model_cards/<model>.md`
- HTML: `docs/generated/model_cards_html/<model>.html`

Add the generated artefacts to release notes or portals as needed. The Markdown files include applicability-domain criteria, enforcement policy, confidence bands, validation metrics, and provenance metadata extracted from each card. HTML output is intentionally minimal so it can be embedded in internal portals without additional styling.

## 2. Guardrail Policy Summary

| Model | Policy | Failure Code | Primary Criteria | Recommended Remediation |
| --- | --- | --- | --- | --- |
| TEST Consensus Acute Toxicity | `BLOCK` | `TEST_AD_FAIL` | Descriptor percentile ranges and 0.65 Tanimoto similarity threshold | Harmonise identifiers (MS-Ready), ensure descriptors fall within training percentiles, or escalate to SME for analogous assessment. |
| OPERA Property Predictions | `WARN` | `OPERA_AD_WARN` | Descriptor min/max bounds and Tanimoto ≥0.6 across 5 neighbours | Investigate descriptor outliers, review top analogues, document override justification in audit bundle if proceeding. |
| GenRA Read-Across Workflow | `BLOCK` | `GENRA_AD_FAIL` | ≥3 analogues with 0.7 similarity, coverage across in vivo/in vitro domains, matching mode-of-action tags | Expand analogue search space, confirm mode-of-action tags, collect additional evidence before re-running workflow. |

The policy column indicates how the orchestrator reacts when AD checks fail:
- `BLOCK`: execution stops and the guardrail event is returned as an `events/error`. Audit bundles store full context.
- `WARN`: execution continues but the guardrail outcome is attached to the response and audit bundle. Downstream automation should require human review.

Guardrail definitions live in `metadata/applicability_domains/*.json` and are referenced in the generated Markdown summaries. Update these JSON files alongside model cards to change enforcement behaviour.

## 3. Failure Modes & Agent Guidance

- **Identifier mismatches**: Ensure inputs are MS-Ready and use DTXSID identifiers when available. Use the orchestrator identifier resolution tools before invoking predictive models.
- **Descriptor range violations**: Normalise features (logS, logP, polar surface area, etc.) to fall inside documented percentiles. Consider SME override only when scientific justification exists.
- **Sparse analogue coverage (GenRA)**: Adjust search parameters (`analogue_limit`, evidence filters) or collect additional in vitro/in vivo evidence before rerunning.
- **Policy overrides**: The orchestrator accepts policy profile overrides via `MCP_POLICY_PROFILE`. Overrides must be recorded in the audit bundle with reviewer sign-off.

For internal predictive/orchestrator workflows, failures should be captured in the corresponding audit bundle or workflow record, including AD rationale, policy state, and remediation hints.

## 4. Governance & Sign-off Workflow

1. **Draft** – Update JSON model card and AD definitions. Run `python scripts/render_model_cards.py` to regenerate human-readable artefacts.
2. **Validation** – Execute `scripts/smoke_ctx.sh` and the predictive regression tests to confirm guardrails still enforce policy outcomes.
3. **Review** – Circulate Markdown or HTML summaries to SMEs, Regulatory Affairs, and Platform for review. Capture comments in the issue tracker or an RFC.
4. **Approval** – Obtain documented approval (sign-off recorded in `provenance.reviewStatus` within the JSON card). Update audit bundle runbooks if policies changed.
5. **Publish** – Commit regenerated docs, bump versions if required, and ensure CI (`.github/workflows/docs.yml`) passes to validate documentation and link health.
6. **Archive** – Store signed checklists and rendered artefacts alongside release notes (see `docs/qa/` for checklist templates).

Refer to `docs/model_metadata.md` for schema-level guidance and to `docs/architecture_overview.md` for how guardrails integrate with the orchestrator.

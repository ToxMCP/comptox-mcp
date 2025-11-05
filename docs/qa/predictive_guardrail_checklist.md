# Predictive Guardrail Validation Checklist

## Prerequisites
- [ ] Model metadata updated (`metadata/model_cards/*.json`, `metadata/applicability_domains/*.json`).
- [ ] `python scripts/render_model_cards.py` executed and artefacts regenerated under `docs/generated/`.
- [ ] Predictive services reachable (TEST, OPERA, GenRA micro-servers) with latest builds.
- [ ] Audit bundle storage configured (e.g., `AUDIT_BUNDLE_BUCKET`, local fallback).

## Automated Tests
- [ ] `pytest tests/test_predictive_regression.py` passes (covers AD block/warn flows).
- [ ] `pytest tests/test_orchestrator_stages.py -k predictive` passes (ensures orchestrator sequencing).
- [ ] `scripts/smoke_ctx.sh --predictive` (if available) completes without errors.

## Manual Guardrail Verification
- [ ] Invoke `metadata_get_model_card` and confirm schema version + policy metadata matches release plan.
- [ ] Run a `search_chemical` → predictive workflow for a compound in-domain (expect success audit bundle).
- [ ] Run the same workflow with an out-of-domain compound (expect `events/error` with AD rationale, policy `BLOCK` for TEST/GenRA).
- [ ] Validate OPERA `WARN` behaviour returns results plus guardrail event (no hard failure).
- [ ] Retrieve audit bundle (`orchestrator_get_audit_bundle`) and confirm it contains guardrail status, AD criteria details, and reviewer instructions.

## Documentation Updates
- [ ] `docs/model_cards_and_policies.md` table reflects any policy or failure-mode changes.
- [ ] `docs/generated/model_cards/*.md` checked into release branch.
- [ ] Governance approvals recorded in `metadata/model_cards/*` `provenance.reviewStatus`.

## Sign-off
- [ ] SME sign-off (name/date):
- [ ] Regulatory/Compliance sign-off (name/date):
- [ ] Platform/DevOps sign-off (name/date):

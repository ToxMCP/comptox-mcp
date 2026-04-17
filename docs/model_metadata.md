# Model Metadata Service Overview

Phase 2 introduces a dedicated ModelMetadataServer that exposes machine-readable CompTox model cards and applicability-domain definitions. This document summarises the schema and validation workflow that underpin Task 2.

## Schema Location

The canonical JSON Schema lives at:

```
schemas/comptox_model_card.schema.json
```

Key characteristics:

- Aligns with OECD QSAR validation principles (defined endpoint, algorithm transparency, AD requirements, goodness-of-fit metrics, mechanistic interpretation).
- Embeds applicability-domain criteria in a machine-readable form that micro-servers can consume to enforce guardrails.
- Captures provenance, review status, checksum information, and explicit intended-use boundaries required for regulatory sign-off.

The schema allows additional properties so future governance teams can extend cards without a breaking change, while strongly typing the core fields consumed by MCP services.

## Authoring & Validation Workflow

1. Author model cards under `metadata/model_cards/` (to be created in Task 2.3) as JSON documents conforming to the schema.
2. Validate cards locally with `jsonschema`:

   ```bash
   python -m jsonschema \
     --instance metadata/model_cards/test.json \
     --schema schemas/comptox_model_card.schema.json
   ```

   A helper script will be added in Task 2.5 to automate CI checks and provide friendlier error messaging.
3. Reference the schema version (`schemaVersion`) in every card so downstream services can detect breaking updates.
4. Store all supporting datasets, applicability-domain parameter files, and references alongside the model card to keep provenance reproducible.

To generate human-readable artefacts from the JSON cards, run:

```bash
python scripts/render_model_cards.py
```

This writes Markdown and HTML summaries under `docs/generated/`. See `docs/model_cards_and_policies.md` for publication guidance and guardrail policy context.

## Next Steps

- **Task 2.2** will expose a `metadata.get_model_card` MCP tool backed by this schema and add pagination/filtering hooks.
- **Task 2.3** will populate cards for TEST, OPERA, and GenRA using the schema, ensuring AD definitions and provenance are complete.
- **Task 2.4–2.5** will publish the AD reference data and wire schema validation into CI so regressions are blocked automatically.

Questions or suggestions should be captured in GitHub issues or focused documentation PRs during the metadata governance workshops.

## Implementation Notes

- `MetadataResource` (`src/epacomp_tox/resources/metadata.py`) exposes the `metadata_get_model_card` MCP tool.
- Model cards are stored under `metadata/model_cards/`; a sample TEST consensus card is provided as a template.
- `ModelCardStore` manages filtering (model name, endpoint text, compliance) and cursor-based pagination while computing card checksums.

- Seed cards currently include TEST consensus acute toxicity, OPERA property predictions, and GenRA read-across workflow.

- Applicability Domain reference data resides in `metadata/applicability_domains/` and is retrievable via `metadata_list_applicability_domain` / `metadata_get_applicability_domain`.

- Run `scripts/validate_metadata.py` before publishing to ensure model cards and applicability domains pass schema checks.

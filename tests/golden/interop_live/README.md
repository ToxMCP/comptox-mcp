This directory stores reviewable CTX-backed live payload captures for the public interop tools.

These files are intentionally separate from deterministic stub fixtures under `tests/fixtures/`.

Refresh them only when upstream CTX drift has been reviewed and accepted:

```bash
python scripts/mcp_interop_smoke.py \
  --endpoint http://127.0.0.1:8000/mcp \
  --capture-dir tests/golden/interop_live \
  --refresh-live-fixtures \
  --json
```

Each refresh writes:

- `assemble_comptox_evidence_pack.json`
- `build_aop_linkage_summary.json`
- `build_pbpk_context_bundle.json`
- `capture_manifest.json`

Use the manifest checksums and schema references to review payload drift intentionally before committing updated live fixtures.

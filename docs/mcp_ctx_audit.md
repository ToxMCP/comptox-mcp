Overview
- MCP uses `ctx-python` (`ctxpy`) client classes to access CTX APIs. No raw HTTP is issued in this codebase.
- Resources map to ctxpy domains and methods; auth uses `x-api-key` header.
- Base URL was not explicitly configured before; now set via env for ctxpy.

Authentication
- Header: `x-api-key`
- Env resolution in server: prefers `CTX_API_KEY`, then `EPA_COMPTOX_API_KEY`, then `ctx_x_api_key`.
- Also sets `os.environ['ctx_x_api_key']` for ctxpy compatibility.

Base URL
- New default base: `https://comptox.epa.gov/ctx-api`
- Legacy toggle: `CTX_USE_LEGACY=1` switches to `https://api-ccte.epa.gov`
- Env exposed for ctxpy: `ctx_api_host` set from `CTX_API_BASE_URL` or legacy toggle; `ctx_api_accept=application/json`.

Resource → Underlying ctxpy calls
- chemical (src/epacomp_tox/resources/chemical.py:1):
  - `search_chemical`/`batch_search_chemical` → `/chemical/search/*` (batch sends newline-delimited identifiers)
  - `get_chemical_details`/`batch_get_chemical_details` → `/chemical/detail/search/*` with optional projection query param
  - `search_msready` → `/chemical/msready/search/(by-dtxcid|by-formula|by-mass)`
- hazard (src/epacomp_tox/resources/hazard.py:1):
  - `search_hazard` → `ctx.Hazard.search` shim selecting `/hazard/{dataset}` routes (toxval, skin-eye, cancer, genetox, adme-ivive, toxref, iris, pprtv, hawc)
  - `batch_search_hazard` → Reuses `ctx.Hazard.batch_search` to iterate the selector for each DTXSID
  - `get_hazard_toxval` / `batch_get_hazard_toxval` → `/hazard/toxval/search/by-dtxsid/{id}` (single + newline-delimited batch)
  - `get_hazard_skin_eye` / `batch_get_hazard_skin_eye` → `/hazard/skin-eye/search/by-dtxsid/{id}`
  - `get_hazard_cancer_summary` / `batch_get_hazard_cancer_summary` → `/hazard/cancer-summary/search/by-dtxsid/{id}`
  - `get_hazard_genetox_summary` / `batch_get_hazard_genetox_summary` → `/hazard/genetox/summary/search/by-dtxsid/{id}`
  - `get_hazard_genetox_details` / `batch_get_hazard_genetox_details` → `/hazard/genetox/details/search/by-dtxsid/{id}`
  - `get_hazard_adme_ivive` → `/hazard/adme-ivive/search/by-dtxsid/{id}`
  - `get_hazard_pprtv` → `/hazard/pprtv/search/by-dtxsid/{id}`
  - `get_hazard_iris` → `/hazard/iris/search/by-dtxsid/{id}`
  - `get_hazard_hawc` → `/hazard/hawc/search/by-dtxsid/{id}`
  - `get_hazard_toxref` / `batch_get_hazard_toxref` → `/hazard/toxref/{dataset}/search/{lookup}/{value}` + `/hazard/toxref/search/by-dtxsid/`
- exposure (src/epacomp_tox/resources/exposure.py:1):
  - `search_cpdat` → `/exposure/{functional-use|product-data|list-presence}/search/by-dtxsid/{id}`
  - `search_httk` → `GET /exposure/httk/search/by-dtxsid/{id}`
  - `get_cpdat_vocabulary` → `/exposure/{functional-use|product-data|list-presence}/(category|puc|tags)`
  - `search_qsurs` → `GET /exposure/functional-use/probability/search/by-dtxsid/{id}`
  - `search_exposures` → `/exposure/{mmdb|seem}/...` endpoints based on selector
- chemical_list (src/epacomp_tox/resources/chemical_list.py:1):
  - `get_public_list_names` → `GET /chemical/list/`
  - `get_full_list` → `GET /chemical/list/chemicals/search/by-listname/{list}`
- cheminformatics (src/epacomp_tox/resources/cheminformatics.py:1):
  - `search_toxprints` → `ctx.search_toxprints(chemical)` (returns DataFrame; code converts to dict)

Notes
- Method signatures and available calls extracted into `epa_comptox_api_structure.json:1` (generated via `extract_api_structure.py:1`).
- Lightweight shim in `src/ctxpy/__init__.py` wraps GET/POST/batch, respects `ctx_api_host`, enforces batch chunking, and surfaces structured `CtxApiError` data (request id, rate limits, retry-after).
- `_with_retry` now provides exponential backoff with jitter, retries only on retryable statuses, and exposes `get_last_metadata()` for downstream telemetry.
- Cheminformatics/ToxPrint endpoints remain unavailable on comptox.epa.gov/ctx-api; shim raises migration warning.

Gaps/Actions
- Confirm maximum batch payload accepted by comptox host (shim currently assumes 200 identifiers per chunk).
- Add smoke tests exercising 1–2 endpoints per domain using `CTX_API_KEY`.

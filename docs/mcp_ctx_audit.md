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
  - `search_chemical` → `ctx.Chemical.search(by, word)`
  - `get_chemical_details` → `ctx.Chemical.details(by, word)`
  - `search_msready` → `ctx.Chemical.msready(by, word)` or mass range variant
- hazard (src/epacomp_tox/resources/hazard.py:1):
  - `search_hazard` → `ctx.Hazard.search(by, dtxsid, summary)`
  - `batch_search_hazard` → `ctx.Hazard.batch_search(by, dtxsid[], summary)`
- exposure (src/epacomp_tox/resources/exposure.py:1):
  - `search_cpdat` → `ctx.Exposure.search_cpdat(vocab_name, dtxsid)`
  - `search_httk` → `ctx.Exposure.search_httk(dtxsid)`
  - `get_cpdat_vocabulary` → `ctx.Exposure.get_cpdat_vocabulary(vocab_name)`
  - `search_qsurs` → `ctx.Exposure.search_qsurs(dtxsid)`
  - `search_exposures` → `ctx.Exposure.search_exposures(by, dtxsid)`
- chemical_list (src/epacomp_tox/resources/chemical_list.py:1):
  - `get_public_list_names` → `ctx.ChemicalList.public_list_names()`
  - `get_full_list` → `ctx.ChemicalList.get_full_list(list_name)`
- cheminformatics (src/epacomp_tox/resources/cheminformatics.py:1):
  - `search_toxprints` → `ctx.search_toxprints(chemical)` (returns DataFrame; code converts to dict)

Notes
- Method signatures and available calls extracted into `epa_comptox_api_structure.json:1` (generated via `extract_api_structure.py:1`).
- No explicit retry/backoff or error normalization implemented yet. Those will be addressed in dedicated tasks.

Gaps/Actions
- Confirm ctxpy honors `ctx_api_host` for new base; if not, pass a host/base parameter directly when supported.
- Add retry/backoff on 429/5xx at the resource call layer or via a thin wrapper.
- Add smoke tests exercising 1–2 endpoints per domain using `CTX_API_KEY`.

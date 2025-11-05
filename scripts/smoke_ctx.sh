#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${CTX_API_KEY:-}" && -z "${EPA_COMPTOX_API_KEY:-}" ]]; then
  echo "Error: Missing CTX_API_KEY (or EPA_COMPTOX_API_KEY)." >&2
  exit 1
fi

export CTX_API_BASE_URL="${CTX_API_BASE_URL:-https://comptox.epa.gov/ctx-api}"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/src"

python - <<'PY'
import os
import ctxpy as ctx

api_key = os.environ.get('CTX_API_KEY') or os.environ.get('EPA_COMPTOX_API_KEY')
chem = ctx.Chemical(x_api_key=api_key)
res = chem.search(by='equals', word='toluene')
print(f"OK: Chemical.search returned {len(res)} results")

haz = ctx.Hazard(x_api_key=api_key)
res2 = haz.search(by='human', dtxsid='DTXSID7021659')
print(f"OK: Hazard.search returned {len(res2)} results")
PY

echo "Smoke test passed."

import os
import ctxpy as ctx
import pandas as pd

# Initialize with API key from environment
api_key = os.environ.get('CTX_API_KEY') or os.environ.get('EPA_COMPTOX_API_KEY')
if not api_key:
    raise SystemExit('Missing CTX_API_KEY (or EPA_COMPTOX_API_KEY). Set your key in the environment to run this script.')

# Test Chemical module
print("\n=== Testing Chemical Module ===")
try:
    chem = ctx.Chemical(x_api_key=api_key)
    result = chem.search(by='equals', word='toluene')
    print(f'Chemical search successful: {len(result)} results found')
    if len(result) > 0:
        print(f'First result: {result[0]}')
except Exception as e:
    print(f'Chemical search error: {str(e)}')

# Test Exposure module
print("\n=== Testing Exposure Module ===")
try:
    expo = ctx.Exposure(x_api_key=api_key)
    # Use a known DTXSID from the previous search if available
    dtxsid = 'DTXSID7021659'  # Toluene's DTXSID
    result = expo.search_cpdat(vocab_name='fc', dtxsid=dtxsid)
    print(f'Exposure search successful: {len(result)} results found')
    if len(result) > 0:
        print(f'First result: {result[0]}')
except Exception as e:
    print(f'Exposure search error: {str(e)}')

# Test Hazard module
print("\n=== Testing Hazard Module ===")
try:
    haz = ctx.Hazard(x_api_key=api_key)
    result = haz.search(by='human', dtxsid=dtxsid)
    print(f'Hazard search successful: {len(result)} results found')
    if len(result) > 0:
        print(f'First result: {result[0]}')
except Exception as e:
    print(f'Hazard search error: {str(e)}')

# Test ToxPrints
print("\n=== Testing ToxPrints ===")
try:
    result = ctx.search_toxprints(chemical=dtxsid)
    print(f'ToxPrints search successful: {result.shape} shape')
    if not result.empty:
        print(f'First few columns: {list(result.columns)[:5]}')
except Exception as e:
    print(f'ToxPrints search error: {str(e)}')

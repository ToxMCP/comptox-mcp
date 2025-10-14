import os
import ctxpy as ctx
import inspect
import json

# Initialize with API key from environment
api_key = os.environ.get('CTX_API_KEY') or os.environ.get('EPA_COMPTOX_API_KEY')
if not api_key:
    raise SystemExit('Missing CTX_API_KEY (or EPA_COMPTOX_API_KEY). Set your key in the environment to run this extractor.')

# Extract Chemical module structure
def extract_class_methods(cls, instance=None):
    methods = {}
    for name, method in inspect.getmembers(cls, inspect.isfunction):
        if not name.startswith('_'):  # Skip private methods
            if instance:
                # Get method signature
                sig = str(inspect.signature(getattr(instance, name)))
                methods[name] = sig
            else:
                methods[name] = 'No signature available'
    return methods

# Extract structure for all main modules
api_structure = {}

# Chemical module
try:
    chem = ctx.Chemical(x_api_key=api_key)
    api_structure['Chemical'] = extract_class_methods(ctx.Chemical, chem)
except Exception as e:
    api_structure['Chemical'] = {"error": str(e)}

# Exposure module
try:
    expo = ctx.Exposure(x_api_key=api_key)
    api_structure['Exposure'] = extract_class_methods(ctx.Exposure, expo)
except Exception as e:
    api_structure['Exposure'] = {"error": str(e)}

# Hazard module
try:
    haz = ctx.Hazard(x_api_key=api_key)
    api_structure['Hazard'] = extract_class_methods(ctx.Hazard, haz)
except Exception as e:
    api_structure['Hazard'] = {"error": str(e)}

# ChemicalList module
try:
    chem_list = ctx.ChemicalList(x_api_key=api_key)
    api_structure['ChemicalList'] = extract_class_methods(ctx.ChemicalList, chem_list)
except Exception as e:
    api_structure['ChemicalList'] = {"error": str(e)}

# Cheminformatics functions
api_structure['Cheminformatics'] = {
    'search_toxprints': str(inspect.signature(ctx.search_toxprints))
}

# Save to file
with open('epa_comptox_api_structure.json', 'w') as f:
    json.dump(api_structure, f, indent=2)

print('API structure extracted and saved to epa_comptox_api_structure.json')

# API Reference

This document provides detailed information about the EPAComp Tox MCP API.

Migration Notes
- Default CTX base URL is `https://comptox.epa.gov/ctx-api`. Override with `CTX_API_BASE_URL`.
- Set `CTX_USE_LEGACY=1` to use `https://api-ccte.epa.gov` until 2025-10-01.
- API key env precedence: `CTX_API_KEY` (preferred), `EPA_COMPTOX_API_KEY`, then `ctx_x_api_key`.

## Server API

### MCPServer

The `MCPServer` class is the core component of the MCP implementation. It handles communication with the EPA CompTox APIs and exposes the data through a standardized interface.

```python
MCPServer(api_key=None, validate_health=False)
```

**Parameters:**
- `api_key` (str, optional): EPA CompTox API key. If not provided, server resolves in order: `CTX_API_KEY` (preferred) → `EPA_COMPTOX_API_KEY` → `ctx_x_api_key`.
- `validate_health` (bool, optional): When `True`, perform a connectivity probe during initialization and raise immediately if the CTX API is unreachable.

**Methods:**

#### get_resources()

Get a list of all available resources.

**Returns:**
- List of resource information dictionaries, each containing:
  - `name` (str): Resource name
  - `description` (str): Resource description
  - `url` (str): Resource URL

#### get_tools()

Get a list of all available tools for LLM agents.

**Returns:**
- List of tool definitions, each containing:
  - `name` (str): Tool name
  - `description` (str): Tool description
  - `parameters` (dict): Tool parameters schema

#### execute_tool(tool_name, parameters)

Execute a tool with the given parameters.

**Parameters:**
- `tool_name` (str): Name of the tool to execute
- `parameters` (dict): Parameters for the tool

**Returns:**
- Tool execution result (varies by tool)

**Raises:**
- `ValueError`: If the tool is not found or parameters are invalid

#### check_health(timeout=5.0)

Run a lightweight connectivity check against the configured CTX base URL.

**Parameters:**
- `timeout` (float, optional): Request timeout in seconds for each probe attempt.

**Returns:**
- Dictionary containing probe metadata with keys such as `ok`, `status`, and `url`.

**Raises:**
- `RuntimeError`: If all probe attempts fail or return 5xx errors.

## Client API

### MCPClient

The `MCPClient` class provides the client interface for connecting to the MCP server.

```python
MCPClient(server_url=None, api_key=None)
```

**Parameters:**
- `server_url` (str, optional): URL of the MCP server. If not provided, will attempt to use environment variable `MCP_EPACOMP_TOX_SERVER_URL`.
- `api_key` (str, optional): API key for the MCP server, if required. If not provided, will attempt to use environment variable `MCP_EPACOMP_TOX_API_KEY`.

**Methods:**

#### get_tools()

Get a list of all available tools for LLM agents.

**Returns:**
- Dictionary containing:
  - `tools` (list): List of tool definitions

#### execute_tool(tool_name, parameters)

Execute a tool with the given parameters.

**Parameters:**
- `tool_name` (str): Name of the tool to execute
- `parameters` (dict): Parameters for the tool

**Returns:**
- Tool execution result (varies by tool)

## Authentication API

### EPACompToxAuth

The `EPACompToxAuth` class handles authentication with the EPA CompTox APIs.

```python
EPACompToxAuth(api_key=None)
```

**Parameters:**
- `api_key` (str, optional): EPA CompTox API key.

**Methods:**

#### get_headers()

Get authentication headers for EPA CompTox API requests.

**Returns:**
- Dictionary of headers including the API key

**Raises:**
- `ValueError`: If the API key is missing

#### get_api_key()

Get the API key.

**Returns:**
- The API key (str)

**Raises:**
- `ValueError`: If the API key is missing

## Resource APIs

### BaseResource

The `BaseResource` class is the base class for all MCP resources.

```python
BaseResource(api_key)
```

**Parameters:**
- `api_key` (str): EPA CompTox API key.

**Properties:**

#### name

Get the resource name.

**Returns:**
- Resource name (str)

#### description

Get the resource description.

**Returns:**
- Resource description (str)

**Methods:**

#### get_tools()

Get a list of tools provided by this resource.

**Returns:**
- List of tool definitions

#### has_tool(tool_name)

Check if this resource provides the given tool.

**Parameters:**
- `tool_name` (str): Name of the tool to check

**Returns:**
- `True` if the tool is provided by this resource, `False` otherwise

#### execute_tool(tool_name, parameters)

Execute a tool with the given parameters.

**Parameters:**
- `tool_name` (str): Name of the tool to execute
- `parameters` (dict): Parameters for the tool

**Returns:**
- Tool execution result (varies by tool)

**Raises:**
- `ValueError`: If the tool is not found or parameters are invalid

### ChemicalResource

The `ChemicalResource` class provides access to chemical structures, nomenclature, IDs, and properties.

**Methods:**

#### search_chemical(query, search_type='contains')

Search for chemicals by name, CAS-RN, or other identifiers.

**Parameters:**
- `query` (str): Search term.
- `search_type` (str, optional): Type of search (`equals`, `starts-with`, `contains`); defaults to `contains`.

**Returns:**
- List of matching chemicals.

#### batch_search_chemical(identifiers)

Batch search for chemicals using the CTX batch endpoint.

**Parameters:**
- `identifiers` (list[str]): Identifiers to resolve (DTXSID, DTXCID, CASRN, etc.).

**Returns:**
- List of matching chemicals.

#### get_chemical_details(identifier, id_type, subset='default')

Get detailed information about a chemical with optional projections.

**Parameters:**
- `identifier` (str): Chemical identifier.
- `id_type` (str): Type of identifier (`dtxsid` or `dtxcid`).
- `subset` (str, optional): Projection selector (`default`, `all`, `details`, `identifiers`, `structures`, `nta`).

**Returns:**
- Chemical details dictionary.

#### batch_get_chemical_details(identifiers, id_type, subset='default')

Retrieve detail projections for multiple identifiers at once.

**Parameters:**
- `identifiers` (list[str]): Chemical identifiers.
- `id_type` (str): Identifier type (`dtxsid` or `dtxcid`).
- `subset` (str, optional): Projection selector.

**Returns:**
- List of chemical detail dictionaries.

#### search_msready(search_type, query=None, mass_start=None, mass_end=None)

Search for chemicals by MS-ready properties or mass range.

**Parameters:**
- `search_type` (str): Selector (`dtxcid`, `formula`, `mass-range`).
- `query` (str, optional): Search term for `dtxcid` or `formula`.
- `mass_start` (float, optional): Start of mass range (when `search_type` is `mass-range`).
- `mass_end` (float, optional): End of mass range (when `search_type` is `mass-range`).

**Returns:**
- List of matching chemicals.

### ExposureResource

The `ExposureResource` class provides access to chemical exposure data, CPDat, and QSUR models.

**Methods:**

#### search_cpdat(vocab_name, dtxsid=None, dtxsids=None)

Search for chemical product and use data from CPDat.

**Parameters:**
- `vocab_name` (str): Vocabulary name (`fc`, `puc`, `lpk`).
- `dtxsid` (str, optional): Single chemical identifier.
- `dtxsids` (list[str], optional): Multiple chemical identifiers.

**Returns:**
- List of matching data.

#### search_httk(dtxsid=None, dtxsids=None)

Search for high-throughput toxicokinetics data.

**Parameters:**
- `dtxsid` (str, optional): Single chemical identifier.
- `dtxsids` (list[str], optional): Multiple chemical identifiers.

**Returns:**
- List of HTTK records.

#### get_cpdat_vocabulary(vocab_name)

Get controlled vocabulary from CPDat.

**Parameters:**
- `vocab_name` (str): Vocabulary name (fc functional use, puc product use categories, lpk list presence keywords)

**Returns:**
- List of vocabulary terms

#### search_qsurs(dtxsid=None, dtxsids=None)

Search for functional use predictions from QSUR models.

**Parameters:**
- `dtxsid` (str, optional): Single chemical identifier.
- `dtxsids` (list[str], optional): Multiple chemical identifiers.

**Returns:**
- List of QSUR predictions.

#### search_exposures(data_type, dtxsid=None, dtxsids=None)

Search for exposure datasets (MMDB aggregates or SEEM predictions).

**Parameters:**
- `data_type` (str): Dataset selector (`pathways`, `mmdb-single`, `seem`, `seem-demographic`).
- `dtxsid` (str, optional): Single chemical identifier.
- `dtxsids` (list[str], optional): Multiple chemical identifiers.

**Returns:**
- List of exposure data records.

### HazardResource

The `HazardResource` class exposes the full CTX hazard catalog, including ToxValDB, ToxRefDB, cancer and genetox datasets, ADME/IVIVE, IRIS, PPRTV, and HAWC link mappers. Every method applies consistent list/dict normalization and surfaces the latest request metadata.

**Methods:**

#### search_hazard(data_type, dtxsid, summary=True)

Fetch hazard data via a selector that spans multiple CTX datasets.

**Parameters:**
- `data_type` (str): Dataset selector (`all`, `hazard`, `toxval`, `human`, `eco`, `skin-eye`, `cancer`, `genetox`, `adme`, `toxref`, `iris`, `pprtv`, `hawc`).
- `dtxsid` (str): Chemical identifier.
- `summary` (bool, optional): Whether to request summary records when the underlying dataset offers both summary/detail responses. Defaults to True.

**Returns:**
- List of hazard records associated with the requested dataset.

#### batch_search_hazard(data_type, dtxsids, summary=True)

Fetch hazard data for multiple chemicals using the same dataset selector.

**Parameters:**
- `data_type` (str): Dataset selector (see `search_hazard`).
- `dtxsids` (list[str]): Chemical identifiers; empty/whitespace values are ignored.
- `summary` (bool, optional): Whether to request summary records when supported. Defaults to True.

**Returns:**
- Dictionary mapping each DTXSID to a list of hazard records.

#### get_hazard_toxval(dtxsid)

Retrieve full ToxValDB records for a single chemical.

**Parameters:**
- `dtxsid` (str): Chemical identifier.

**Returns:**
- List of ToxValDB records.

#### batch_get_hazard_toxval(dtxsids)

Retrieve ToxValDB records for multiple chemicals.

**Parameters:**
- `dtxsids` (list[str]): Chemical identifiers; empty/whitespace values are skipped.

**Returns:**
- Combined list of ToxValDB records.

#### get_hazard_skin_eye(dtxsid)

Retrieve skin and eye hazard metadata for a chemical.

**Parameters:**
- `dtxsid` (str): Chemical identifier.

**Returns:**
- List of skin/eye hazard records.

#### batch_get_hazard_skin_eye(dtxsids)

Retrieve skin and eye hazard metadata for multiple chemicals.

**Parameters:**
- `dtxsids` (list[str]): Chemical identifiers; empty/whitespace values are skipped.

**Returns:**
- List of skin/eye hazard records across all requested chemicals.

#### get_hazard_cancer_summary(dtxsid)

Retrieve cancer hazard summaries for a chemical.

**Parameters:**
- `dtxsid` (str): Chemical identifier.

**Returns:**
- List of cancer hazard summary records.

#### batch_get_hazard_cancer_summary(dtxsids)

Retrieve cancer hazard summaries for multiple chemicals.

**Parameters:**
- `dtxsids` (list[str]): Chemical identifiers; empty/whitespace values are skipped.

**Returns:**
- List of cancer hazard summary records across all requested chemicals.

#### get_hazard_genetox_summary(dtxsid)

Retrieve genotoxicity summary data for a chemical.

**Parameters:**
- `dtxsid` (str): Chemical identifier.

**Returns:**
- List of genetox summary records.

#### batch_get_hazard_genetox_summary(dtxsids)

Retrieve genotoxicity summary data for multiple chemicals.

**Parameters:**
- `dtxsids` (list[str]): Chemical identifiers; empty/whitespace values are skipped.

**Returns:**
- List of genetox summary records across all requested chemicals.

#### get_hazard_genetox_details(dtxsid)

Retrieve genotoxicity detailed data for a chemical.

**Parameters:**
- `dtxsid` (str): Chemical identifier.

**Returns:**
- List of genetox detail records (e.g., study-level findings).

#### batch_get_hazard_genetox_details(dtxsids)

Retrieve genotoxicity detailed data for multiple chemicals.

**Parameters:**
- `dtxsids` (list[str]): Chemical identifiers; empty/whitespace values are skipped.

**Returns:**
- List of genetox detail records across all requested chemicals.

#### get_hazard_adme_ivive(dtxsid)

Retrieve ADME / IVIVE hazard data (High-Throughput Toxicokinetics).

**Parameters:**
- `dtxsid` (str): Chemical identifier.

**Returns:**
- List of ADME/IVIVE records for the chemical.

#### get_hazard_pprtv(dtxsid)

Retrieve Provisional Peer-Reviewed Toxicity Value (PPRTV) data.

**Parameters:**
- `dtxsid` (str): Chemical identifier.

**Returns:**
- List of PPRTV records for the chemical.

#### get_hazard_iris(dtxsid)

Retrieve IRIS toxicity assessment data.

**Parameters:**
- `dtxsid` (str): Chemical identifier.

**Returns:**
- List of IRIS records for the chemical.

#### get_hazard_hawc(dtxsid)

Retrieve HAWC link mapper data for integrated risk assessment.

**Parameters:**
- `dtxsid` (str): Chemical identifier.

**Returns:**
- List of HAWC link records for the chemical.

#### get_hazard_toxref(dataset, lookup_type, value)

Retrieve ToxRefDB data using dataset/lookup selectors.

**Parameters:**
- `dataset` (str): ToxRefDB dataset to query (`summary`, `data`, `effects`, `observations`).
- `lookup_type` (str): Lookup mode (`dtxsid`, `study-id`, `study-type`).
- `value` (str): Identifier corresponding to the lookup type.

**Returns:**
- List of ToxRefDB records.

#### batch_get_hazard_toxref(dtxsids)

Retrieve summary ToxRefDB data for multiple chemicals.

**Parameters:**
- `dtxsids` (list[str]): Chemical identifiers; empty/whitespace values are skipped.

**Returns:**
- List of ToxRefDB records aggregated across the requested chemicals.

### ChemicalListResource

The `ChemicalListResource` class provides access to chemical lists and collections.

**Methods:**

#### get_public_list_names()

Get names of available public chemical lists.

**Returns:**
- List of chemical list names (normalized to string list).

#### get_full_list(list_name)

Get all chemicals in a specific list.

**Parameters:**
- `list_name` (str): Name of the chemical list

**Returns:**
- List of chemicals (normalized to list-of-dict output).

### CheminformaticsResource

The `CheminformaticsResource` class provides access to ToxPrint chemotypes and other cheminformatics tools.

**Methods:**

#### search_toxprints(chemical)

Search for ToxPrint chemotypes for a chemical.

**Parameters:**
- `chemical` (str): Chemical identifier (DTXSID, DTXCID, or SMILES)

**Returns:**
- ToxPrint chemotypes

#### batch_search_toxprints(chemicals)

Search for ToxPrint chemotypes for multiple chemicals.

**Parameters:**
- `chemicals` (list): List of chemical identifiers (DTXSIDs, DTXCIDs, or SMILES)

**Returns:**
- ToxPrint chemotypes for multiple chemicals

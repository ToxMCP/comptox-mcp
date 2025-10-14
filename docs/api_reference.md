# API Reference

This document provides detailed information about the EPAComp Tox MCP API.

## Server API

### MCPServer

The `MCPServer` class is the core component of the MCP implementation. It handles communication with the EPA CompTox APIs and exposes the data through a standardized interface.

```python
MCPServer(api_key=None)
```

**Parameters:**
- `api_key` (str, optional): EPA CompTox API key. If not provided, will attempt to use environment variable `EPA_COMPTOX_API_KEY`.

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

#### search_chemical(query, search_type)

Search for chemicals by name, CAS-RN, or other identifiers.

**Parameters:**
- `query` (str): Search term
- `search_type` (str): Type of search (equals, starts-with, contains)

**Returns:**
- List of matching chemicals

#### get_chemical_details(id, id_type)

Get detailed information about a chemical.

**Parameters:**
- `id` (str): Chemical identifier
- `id_type` (str): Type of identifier (dtxsid or dtxcid)

**Returns:**
- Chemical details

#### search_msready(search_type, query)

Search for chemicals by MS-ready properties.

**Parameters:**
- `search_type` (str): Type of MS-ready search (dtxcid or formula)
- `query` (str): Search term

**Returns:**
- List of matching chemicals

#### search_msready_mass(start, end)

Search for chemicals by mass range.

**Parameters:**
- `start` (float): Start of mass range
- `end` (float): End of mass range

**Returns:**
- List of matching chemicals

### ExposureResource

The `ExposureResource` class provides access to chemical exposure data, CPDat, and QSUR models.

**Methods:**

#### search_cpdat(vocab_name, dtxsid)

Search for chemical product and use data from CPDat.

**Parameters:**
- `vocab_name` (str): Vocabulary name (fc, puc, lpk)
- `dtxsid` (str): Chemical identifier

**Returns:**
- List of matching data

#### search_httk(dtxsid)

Search for high-throughput toxicokinetics data.

**Parameters:**
- `dtxsid` (str): Chemical identifier

**Returns:**
- HTTK data

#### get_cpdat_vocabulary(vocab_name)

Get controlled vocabulary from CPDat.

**Parameters:**
- `vocab_name` (str): Vocabulary name (fc, puc, lpk)

**Returns:**
- List of vocabulary terms

#### search_qsurs(dtxsid)

Search for functional use predictions from QSUR models.

**Parameters:**
- `dtxsid` (str): Chemical identifier

**Returns:**
- QSUR predictions

#### search_exposures(data_type, dtxsid)

Search for exposure pathway predictions or SEEM framework estimates.

**Parameters:**
- `data_type` (str): Type of exposure data (pathways or seem)
- `dtxsid` (str): Chemical identifier

**Returns:**
- Exposure data

### HazardResource

The `HazardResource` class provides access to human and ecotoxicology data from ToxValDB.

**Methods:**

#### search_hazard(data_type, dtxsid, summary=True)

Search for chemical hazard data from ToxValDB.

**Parameters:**
- `data_type` (str): Type of hazard data (all, human, eco, skin-eye, cancer, genetox)
- `dtxsid` (str): Chemical identifier
- `summary` (bool, optional): Whether to return summary data only. Defaults to True.

**Returns:**
- List of hazard data

#### batch_search_hazard(data_type, dtxsids, summary=True)

Search for hazard data for multiple chemicals.

**Parameters:**
- `data_type` (str): Type of hazard data (all, human, eco, skin-eye, cancer, genetox)
- `dtxsids` (list): List of chemical identifiers
- `summary` (bool, optional): Whether to return summary data only. Defaults to True.

**Returns:**
- Dictionary mapping DTXSIDs to hazard data

### ChemicalListResource

The `ChemicalListResource` class provides access to chemical lists and collections.

**Methods:**

#### get_public_list_names()

Get names of available public chemical lists.

**Returns:**
- List of chemical list names

#### get_full_list(list_name)

Get all chemicals in a specific list.

**Parameters:**
- `list_name` (str): Name of the chemical list

**Returns:**
- List of chemicals

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

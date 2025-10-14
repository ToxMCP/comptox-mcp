# EPAComp Tox Model Context Protocol (MCP) Design

## Overview

This document outlines the design for the EPAComp Tox Model Context Protocol (MCP), which will enable LLM agents to interact with the EPA's Computational Toxicology and Exposure APIs through a standardized interface.

## Architecture

The MCP follows a client-server architecture:

1. **MCP Server**: Exposes EPA CompTox data and functionality through standardized MCP endpoints
2. **MCP Client**: Used by LLM agents to connect to and interact with the MCP server
3. **LLM Agent**: Consumes the MCP client to access EPA CompTox data

```
┌───────────┐     ┌────────────┐     ┌─────────────┐     ┌───────────┐
│ LLM Agent │────▶│ MCP Client │────▶│ MCP Server  │────▶│ EPA APIs  │
└───────────┘     └────────────┘     └─────────────┘     └───────────┘
```

## Core Components

### 1. MCP Server

The MCP server will be implemented as a Python application that:

- Exposes standardized MCP endpoints for EPA CompTox data
- Handles authentication with the EPA APIs
- Translates between MCP requests and EPA API calls
- Formats responses according to MCP standards

#### Key Modules:

- **Server**: Core MCP server implementation
- **Resources**: Defines available EPA CompTox resources
- **Tools**: Implements tool definitions for LLM agents
- **Auth**: Handles EPA API authentication

### 2. EPA CompTox API Integration

The server will integrate with the EPA CompTox APIs through the ctx-python library, providing access to:

- **Chemical**: Chemical structures, nomenclature, IDs, and properties
- **Exposure**: Chemical exposure data, CPDat, and QSUR models
- **Hazard**: Human and ecotoxicology data from ToxValDB
- **ChemicalList**: Access to chemical lists and collections
- **Cheminformatics**: ToxPrint chemotypes and other cheminformatics tools

### 3. MCP Resources

The MCP will expose the following resources:

#### Chemical Resource
- Search chemicals by name, CAS-RN, DTXSID
- Get detailed chemical information
- Search by MS-ready properties

#### Exposure Resource
- Access CPDat data
- Get HTTK data
- Retrieve functional use predictions
- Access exposure pathway predictions

#### Hazard Resource
- Search ToxValDB for human and ecological data
- Access skin/eye irritant data
- Retrieve cancer and genetic toxicity data

#### ChemicalList Resource
- Get public list names
- Retrieve full chemical lists

#### Cheminformatics Resource
- Search ToxPrints for chemicals

## API Design

### Endpoints

The MCP server will expose the following endpoints:

```
/resources
  GET /resources - List all available resources

/chemical
  GET /chemical/search?query={query}&type={equals|starts-with|contains}
  GET /chemical/details?id={dtxsid|dtxcid}
  GET /chemical/msready?type={dtxcid|formula|mass}&query={query}

/exposure
  GET /exposure/cpdat?vocab={fc|puc|lpk}&dtxsid={dtxsid}
  GET /exposure/httk?dtxsid={dtxsid}
  GET /exposure/vocabulary?vocab={fc|puc|lpk}
  GET /exposure/qsur?dtxsid={dtxsid}
  GET /exposure/pathways?dtxsid={dtxsid}
  GET /exposure/seem?dtxsid={dtxsid}

/hazard
  GET /hazard/search?type={all|human|eco|skin-eye|cancer|genetox}&dtxsid={dtxsid}

/chemical-list
  GET /chemical-list/names
  GET /chemical-list/full?name={list_name}

/cheminformatics
  GET /cheminformatics/toxprints?chemical={dtxsid|dtxcid|smiles}
```

### Tools

The MCP will define the following tools for LLM agents:

```json
{
  "tools": [
    {
      "name": "search_chemical",
      "description": "Search for chemicals by name, CAS-RN, or other identifiers",
      "parameters": {
        "query": "Search term",
        "type": "Search type: equals, starts-with, or contains"
      }
    },
    {
      "name": "get_chemical_details",
      "description": "Get detailed information about a chemical",
      "parameters": {
        "id": "Chemical identifier (DTXSID or DTXCID)"
      }
    },
    {
      "name": "search_exposure_data",
      "description": "Search for chemical exposure data",
      "parameters": {
        "dtxsid": "Chemical identifier (DTXSID)",
        "data_type": "Type of exposure data: cpdat, httk, qsur, pathways, or seem"
      }
    },
    {
      "name": "search_hazard_data",
      "description": "Search for chemical hazard data",
      "parameters": {
        "dtxsid": "Chemical identifier (DTXSID)",
        "data_type": "Type of hazard data: all, human, eco, skin-eye, cancer, or genetox"
      }
    },
    {
      "name": "get_chemical_list",
      "description": "Get a list of chemicals",
      "parameters": {
        "list_name": "Name of the chemical list"
      }
    },
    {
      "name": "search_toxprints",
      "description": "Search for ToxPrint chemotypes",
      "parameters": {
        "chemical": "Chemical identifier (DTXSID, DTXCID, or SMILES)"
      }
    }
  ]
}
```

## Authentication

The MCP server will handle authentication with the EPA APIs:

1. The MCP server will be configured with an EPA API key
2. The key will be used for all requests to the EPA APIs
3. The MCP client will not need to handle EPA API authentication
4. The MCP server may implement its own authentication for clients if needed

## Integration with Agentic SDK

The MCP will integrate with LLM agents through the Agentic SDK:

1. The MCP client will be implemented as an Agentic SDK plugin
2. The client will connect to the MCP server and expose the EPA CompTox tools
3. LLM agents will use the tools through the Agentic SDK's tool-calling interface
4. The MCP client will handle serialization and deserialization of requests and responses

## Implementation Plan

1. Implement the MCP server core components
2. Implement the EPA CompTox API integration
3. Define and implement the MCP resources and endpoints
4. Implement the MCP client for Agentic SDK
5. Create documentation and examples

## API Placeholder

The design includes a placeholder for the API integration that will be provided by the user:

```python
# In src/epacomp_tox/auth.py
class EPACompToxAuth:
    """Authentication handler for EPA CompTox APIs."""
    
    def __init__(self, api_key=None):
        """Initialize with API key."""
        self.api_key = api_key
        # User can replace this with their own implementation
        
    def get_headers(self):
        """Get authentication headers."""
        return {"x-api-key": self.api_key}
```

## Next Steps

1. Implement the core MCP server components
2. Create the resource definitions
3. Implement the tool definitions
4. Create the MCP client for Agentic SDK
5. Test the implementation
6. Prepare documentation and examples

# Known Issues (2025-11-06)

This log captures outstanding defects discovered during the 2025-11-06 release readiness sweep. Update entries as fixes land or additional details become available.

## 1. ToxPrint MCP Calls Return HTTP 500

- **Impacted tools:** `search_toxprints`, `batch_search_toxprints`
- **Reproduction:**
  1. Start the MCP server (`uvicorn epacomp_tox.transport.websocket:app --port 8001`).
  2. Invoke either tool, e.g.:
     ```bash
     curl -s http://localhost:8001/mcp \
       -H 'Content-Type: application/json' \
       -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_toxprints","arguments":{"chemical":"DTXSID0020232"}}}'
     ```
  3. Observed response: HTTP 500 with message `Transport send error: Client error: HTTP status server error (500 Internal Server Error)`.
- **Suspected cause:** The upstream CompTox bridge running on `http://localhost:8001/mcp` returns `500 Internal Server Error` for ToxPrint calls. Other tools continue to function, so the failure is scoped to the ToxPrint dispatcher.
- **Impact:** ToxPrint fingerprints are unavailable to agents; all other chemical, exposure, hazard, and metadata tools remain operational.
- **Workaround:** None. Downstream flows relying on fingerprints should fall back to alternative structure descriptors until the upstream issue is resolved.
- **Next actions:**
  - [ ] Capture upstream service logs (`deploy/logs/bridge/*.log`) once available.
  - [ ] File issue with the CompTox MCP bridge maintainers including timestamps and reproduction payloads.
  - [ ] Add regression test once a fix is deployed to ensure ToxPrint coverage stays green.

---

_Last updated: 2025-11-06_

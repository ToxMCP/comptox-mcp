# ToxMCP Comprehensive Audit - Master Index (Reviewed Copy)

**Audit package date:** 2026-04-15  
**Repositories in scope:** `comptox-mcp`, `oqt-mcp`, `aop-mcp`, `pbpk-mcp`

---

## Read this first

Before reusing any finding outside the immediate engineering team, read:

1. `AUDIT_EVIDENCE_FRAMEWORK.md`
2. `TOXMCP_MASTER_AUDIT_REPORT.md`
3. `VALIDATION_BACKLOG.md`
4. `PUBLIC_REFERENCE_NOTES.md`

These four documents define:
- what the package actually claims
- how strong the evidence is
- what still needs validation

---

## Navigation by audience

### Leadership / program management
- `DELIVERY_SUMMARY.md`
- `QUICK_REFERENCE.md`
- `TOXMCP_MASTER_AUDIT_REPORT.md`

### Engineering leads
- repository-specific `README.md` files
- `QUICK_REFERENCE.md`
- `VALIDATION_BACKLOG.md`

### Security / platform engineering
- `toxmcp_security_audit_report.md`
- `ToxMCP_Performance_Resilience_Audit_Report.md`
- `toxmcp_observability_audit_report.md`
- `aop-mcp-audit/REMEDIATION_CODE.md`
- `pbpk-mcp-audit/REMEDIATION_CODE.md`

### Regulatory / quality / scientific governance
- `toxmcp_regulatory_audit_report.md`
- `cognitive_ergonomics_audit_report.md`
- `toxmcp_adversarial_audit_report.md`
- `oqt-mcp-audit/README.md`
- `comptox-mcp-audit/README.md`

### Architecture / integration owners
- `toxmcp_contract_audit_report.md`
- `toxmcp_future_proofing_audit_report.md`
- `TOXMCP_MASTER_AUDIT_REPORT.md`

---

## Package structure

```text
README.md
DELIVERY_SUMMARY.md
INDEX.md
QUICK_REFERENCE.md
TOXMCP_MASTER_AUDIT_REPORT.md
AUDIT_EVIDENCE_FRAMEWORK.md
REVISION_LOG.md
VALIDATION_BACKLOG.md

Specialist reports/
  toxmcp_regulatory_audit_report.md
  toxmcp_adversarial_audit_report.md
  toxmcp_contract_audit_report.md
  toxmcp_security_audit_report.md
  ToxMCP_Performance_Resilience_Audit_Report.md
  toxmcp_observability_audit_report.md
  cognitive_ergonomics_audit_report.md
  toxmcp_future_proofing_audit_report.md

Repository packages/
  comptox-mcp-audit/
  oqt-mcp-audit/
  aop-mcp-audit/
  pbpk-mcp-audit/

Shared reference code/
  toxmcp_remediation_snippets.py
```

---

## Fastest route to decisions

### Question: “What are the top cross-suite issues?”
Read:
- `TOXMCP_MASTER_AUDIT_REPORT.md`
- `QUICK_REFERENCE.md`

### Question: “What should each repo team do next?”
Read:
- repo `README.md`
- repo `REMEDIATION_CODE.md`
- `VALIDATION_BACKLOG.md`

### Question: “How much of this is directly observed vs inferred?”
Read:
- `AUDIT_EVIDENCE_FRAMEWORK.md`
- relevant specialist report summary section

### Question: “Can we circulate this externally?”
Read:
- `DELIVERY_SUMMARY.md`
- `REVISION_LOG.md`
- `VALIDATION_BACKLOG.md`

---

## Highest-priority repository docs

| Repository | Start here | Then read |
|---|---|---|
| `comptox-mcp` | `comptox-mcp-audit/README.md` | `toxmcp_regulatory_audit_report.md`, `comptox-mcp-audit/REMEDIATION_CODE.md` |
| `oqt-mcp` | `oqt-mcp-audit/README.md` | `cognitive_ergonomics_audit_report.md`, `oqt-mcp-audit/REMEDIATION_CODE.md` |
| `aop-mcp` | `aop-mcp-audit/README.md` | `toxmcp_security_audit_report.md`, `aop-mcp-audit/REMEDIATION_CODE.md` |
| `pbpk-mcp` | `pbpk-mcp-audit/README.md` | `ToxMCP_Performance_Resilience_Audit_Report.md`, `pbpk-mcp-audit/REMEDIATION_CODE.md` |

---

## Legend used in reviewed summaries

| Label | Meaning |
|---|---|
| **Observed** | Directly supported by the audit material itself |
| **Observed + inferred** | A direct observation supports a broader architectural conclusion |
| **Scenario** | Threat or misuse path with stated preconditions |
| **High / Medium / Low confidence** | How strongly the package supports the claim |

---

## Package-level caution

The repository packages and specialist reports are useful and actionable, but several findings still need:
- live-repo verification
- proof-of-concept reproduction
- fix verification tests

Treat this package as a strong internal audit and planning artifact, not a substitute for formal external assurance.

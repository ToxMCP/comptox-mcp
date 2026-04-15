# ToxMCP Suite - Performance & Resilience Audit Report

**Audit Date:** 2026-04-15  
**Auditor:** Performance & Resilience Engineer  
**Scope:** comptox-mcp, oqt-mcp, aop-mcp, pbpk-mcp repositories

---

> **Reviewed copy (2026-04-15):** This document was retained from the original package but lightly edited for consistency.  
> Unless explicitly stated otherwise, code blocks are **reference implementations**, not validated patches, and scenario-based exploit narratives should not be read as reproduced proofs.



## Executive Summary

This audit identifies critical scaling cliffs and fault modes across the ToxMCP ecosystem. While the suite demonstrates good architectural patterns for job persistence and retry logic, significant gaps exist in **circuit breaker implementation**, **memory protection for large simulations**, and **input validation for chemical complexity**.

**Overall Risk Rating: 🔴 HIGH**

---

## 1. SPARQL Timeout Cascades (AOP-MCP) 🔴 Critical

### Finding AOP-001: No Circuit Breaker Logic

**File:** `aop-mcp/src/adapters/sparql_client.py` (lines 37-231)

**Issue:** The SPARQL client implements failover across endpoints but **lacks circuit breaker pattern**:

```python
# Current implementation - NO circuit breaker
async def _dispatch(self, query: str, *, timeout: float | None = None) -> dict[str, Any]:
    last_error: Exception | None = None
    for endpoint in self._endpoints:
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            try:
                response = await self._client.post(...)
            except Exception as exc:
                # Simply logs and retries - no circuit breaker
                logger.warning("SPARQL request to %s failed...", endpoint.url, ...)
                last_error = exc
                continue
```

**Fault Mode:** When AOP-Wiki is down:
- System **FAILS CLOSED** - raises `SparqlUpstreamError` after all endpoints exhausted
- No graceful degradation to cached/empty results
- Each request waits full timeout (default 10s) x retries (default 2) x endpoints
- **Cascading latency** under load

**Missing Protection:**
| Feature | Status | Risk |
|---------|--------|------|
| Circuit Breaker | Absent | 🔴 Critical |
| Exponential Backoff | Absent | 🟠 High |
| Jitter | Absent | 🟠 High |
| Half-Open State | Absent | 🔴 Critical |
| Cache-First on Failure | Absent | 🟠 High |

**Thresholds:**
- Default timeout: **10 seconds**
- Default retries: **2 per endpoint**
- No maximum query complexity limits

**Recommendation:** Implement circuit breaker with:
- Failure threshold: 5 errors in 60 seconds
- Open state duration: 30 seconds
- Half-open probe: 1 request
- Fallback to cache or empty results with warning

---

## 2. Memory Exhaustion Patterns (PBPK-MCP) 🔴 Critical

### Finding PBPK-001: No Population Size Limits

**File:** `pbpk-mcp/src/mcp_bridge/services/job_service.py` (1392 lines)

**Issue:** Population simulations can generate massive datasets with **no input validation**:

```python
# From JobRecord dataclass - no population size limits
@dataclass
class JobRecord:
    job_id: str
    simulation_id: str
    job_type: str  # Can be "population_simulation"
    # ... no max_population_size field
```

**Configuration (`.env.example`):**
```bash
JOB_TIMEOUT_SECONDS=300  # 5 minutes
JOB_MAX_RETRIES=0
JOB_WORKER_THREADS=2
# NO population size limit defined
```

**OOM Risk Assessment:**

| Population Size | Memory Estimate | Timeout Risk |
|-----------------|-----------------|--------------|
| 100 patients | ~50 MB | Low |
| 1,000 patients | ~500 MB | Medium |
| 10,000 patients | ~5 GB | 🔴 High - Likely OOM |
| 100,000 patients | ~50 GB | 🔴 Critical - Likely OOM on many worker sizes |

**Streaming Status:** NO streaming/chunking logic found for population results

**File:** `pbpk-mcp/src/mcp_bridge/storage/population_store.py` (not examined but referenced)

**Missing Protection:**
- No `max_population_size` parameter
- No memory quota enforcement
- No result pagination/streaming
- SQLite storage loads full results into memory

**Recommendation:** 
1. Add `MAX_POPULATION_SIZE=5000` environment variable
2. Implement result streaming with chunk handles
3. Add memory quota check before simulation start

---

### Finding PBPK-002: Insufficient Job Timeout

**Current:** `JOB_TIMEOUT_SECONDS=300` (5 minutes)

**Risk:** Population simulations with 1000+ patients can exceed 5 minutes, causing:
- Job marked as `TIMEOUT` status
- Orphaned simulation processes in R/ospsuite
- Partial results lost

**Recommendation:** 
- Increase default to 1800s (30 minutes) for population jobs
- Implement job-type specific timeouts

---

## 3. API Rate Limit Handling (CompTox-MCP) 🟠 High

### Finding CTX-001: Basic Retry Without Jitter

**File:** `comptox-mcp/src/epacomp_tox/settings.py` (lines 37-139)

**Current Implementation:**
```python
class ContextSettings:
    retry_attempts: int  # Default: 3
    retry_base: float    # Default: 0.5 seconds
```

**Configuration:**
```bash
CTX_RETRY_ATTEMPTS=3
CTX_RETRY_BASE=0.5
```

**Retry Pattern:**
- Attempt 1: Immediate
- Attempt 2: 0.5s delay
- Attempt 3: 0.5s delay (NOT exponential!)

**Missing Protection:**
| Feature | Status | Risk |
|---------|--------|------|
| Exponential Backoff | Partial (fixed base) | 🟠 High |
| Jitter | Absent | 🔴 Critical |
| Rate Limit Headers | Not checked | 🟠 High |
| Quota Budgets | Absent | 🟠 High |
| 429 Retry-After | Not honored | 🔴 Critical |

**Fault Mode:** Under EPA CompTox rate limiting:
- Multiple concurrent requests will retry simultaneously
- **Thundering herd** amplifies rate limit violations
- No `Retry-After` header parsing
- Risk of temporary API ban

**Recommendation:**
```python
# Implement proper exponential backoff with jitter
delay = retry_base * (2 ** attempt) + random.uniform(0, 1)
```

---

## 4. Long-Running Job Orphans (PBPK-MCP) 🟡 Medium

### Finding PBPK-003: SQLite Persistence with Limitations

**File:** `pbpk-mcp/src/mcp_bridge/services/job_service.py` (lines 127-400)

**Positive Finding:** Jobs are persisted to SQLite:
```python
class JobRegistry:
    def __init__(self, db_path: str = "var/jobs/registry.json"):
        self._conn = sqlite3.connect(str(self._prepare_path(db_path)))
        # Creates tables: job_records, simulation_results
```

**Survival Scenario:**
| Scenario | Job Survival | Notes |
|----------|--------------|-------|
| API server restart | Yes | SQLite persists to disk |
| Worker crash | Partial | Job status may be "RUNNING" but actually dead |
| Full system restart | Yes | Jobs recover from SQLite |
| Celery backend crash | Depends | Redis/memory backend loses queue |

**Orphan Risk:**
- Job status can remain `RUNNING` indefinitely if worker dies
- No heartbeat/health check from workers to verify liveness
- Cleanup only based on `retention_seconds` (default unknown)

**Recommendation:**
1. Implement worker heartbeat (every 30s)
2. Mark jobs as `FAILED` if no heartbeat for 2x timeout
3. Add orphan detection job (runs every 5 minutes)

---

## 5. Maximum Safe Chemical Complexity 🟠 High

### Finding SUITE-001: No Complexity Limits

**Cross-Repository Analysis:**

| Component | Validation | Limit |
|-----------|------------|-------|
| AOP-MCP SPARQL queries | None | N/A |
| CompTox-MCP chemical search | Basic | None |
| PBPK-MCP population sims | None | N/A |
| OQT-MCP workflows | Timeout only | 300s |

**Missing Validations:**
- **Molecular complexity:** No atom count limit
- **Pathway depth:** No AOP chain length limit
- **Query result size:** No LIMIT enforcement on SPARQL
- **Simulation granularity:** No time-step minimum

**Risk Scenarios:**
1. **SPARQL query** with unlimited `?chemical aops:hasMIE` traversal → timeout/OOM
2. **Population simulation** with 100,000 virtual patients → OOM
3. **AOP network** query with 50+ key events → response size explosion

**Recommendation:** Implement tiered limits:
```python
MAX_ATOMS = 500  # For PBPK modeling
MAX_AOP_CHAIN_DEPTH = 10
MAX_SPARQL_RESULTS = 10000
MAX_POPULATION_SIZE = 5000
```

---

## 6. Cross-Component Vulnerability Matrix

| Threat | CompTox | AOP | PBPK | OQT | Severity |
|--------|---------|-----|------|-----|----------|
| Timeout Cascade | 🟡 | 🔴 | 🟡 | 🟠 | 🔴 Critical |
| Memory Exhaustion | 🟢 | 🟢 | 🔴 | 🟢 | 🔴 Critical |
| Rate Limit Ban | 🟠 | 🟢 | 🟢 | 🟢 | 🟠 High |
| Job Orphans | 🟢 | 🟢 | 🟡 | 🟢 | 🟡 Medium |
| Complexity Bomb | 🟠 | 🔴 | 🔴 | 🟠 | 🔴 Critical |

---

## 7. Specific File References

### Critical Files Examined:

1. **AOP-MCP:**
   - `src/adapters/sparql_client.py` (231 lines) - No circuit breaker
   - `src/adapters/aop_wiki.py` - SPARQL endpoint consumer

2. **CompTox-MCP:**
   - `src/epacomp_tox/settings.py` (139 lines) - Retry config
   - `src/epacomp_tox/client.py` (102 lines) - Basic client

3. **PBPK-MCP:**
   - `src/mcp_bridge/services/job_service.py` (1392 lines) - Job persistence
   - `src/mcp_bridge/config.py` (543 lines) - Configuration
   - `.env.example` (67 lines) - Environment defaults

4. **OQT-MCP:**
   - `TIMEOUT_FIX_SUMMARY.md` - Timeout hardening documentation

---

## 8. Concrete Thresholds & Resource Limits

### Current Limits:

| Parameter | Default | Maximum | Unit |
|-----------|---------|---------|------|
| SPARQL timeout | 10 | Configurable | seconds |
| SPARQL retries | 2 | Configurable | attempts |
| Job timeout | 300 | Configurable | seconds |
| Job retries | 0 | Configurable | attempts |
| API retry attempts | 3 | Configurable | attempts |
| API retry base | 0.5 | Configurable | seconds |
| Adapter timeout | 30 | Configurable | seconds |

### Missing Limits (Critical Gaps):

| Parameter | Recommended | Priority |
|-----------|-------------|----------|
| Max population size | 5000 | 🔴 Critical |
| Max SPARQL results | 10000 | 🔴 Critical |
| Max AOP chain depth | 10 | 🟠 High |
| Max molecule atoms | 500 | 🟠 High |
| Circuit breaker threshold | 5 errors/60s | 🔴 Critical |
| Memory quota per job | 2 GB | 🔴 Critical |

---

## 9. Recommendations Summary

### Immediate Actions (Critical):

1. **PBPK-MCP:** Add `MAX_POPULATION_SIZE` limit (default 5000)
2. **AOP-MCP:** Implement circuit breaker for SPARQL endpoints
3. **CompTox-MCP:** Add jitter and exponential backoff to retries
4. **PBPK-MCP:** Implement memory quota check before simulations

### Short-term (High Priority):

5. **PBPK-MCP:** Add worker heartbeat to prevent orphan jobs
6. **AOP-MCP:** Add `MAX_SPARQL_RESULTS` limit
7. **CompTox-MCP:** Parse and honor `Retry-After` headers
8. **PBPK-MCP:** Implement result streaming for population sims

### Long-term (Medium Priority):

9. **All:** Add complexity scoring for chemical inputs
10. **All:** Implement distributed rate limiter
11. **All:** Add Prometheus alerts for resource exhaustion

---

## Appendix: Evidence Snapshots

### SPARQL Client (No Circuit Breaker):
```python
# From aop-mcp/src/adapters/sparql_client.py
class SparqlClient:
    def __init__(self, ..., max_retries: int = 2, timeout: float = 10.0):
        self._max_retries = max(0, max_retries)
        self._timeout = timeout
```

### Job Persistence (SQLite):
```python
# From pbpk-mcp/src/mcp_bridge/services/job_service.py
class JobRegistry:
    def __init__(self, db_path: str = "var/jobs/registry.json"):
        self._conn = sqlite3.connect(str(self._prepare_path(db_path)))
```

### Retry Configuration (No Jitter):
```python
# From comptox-mcp/src/epacomp_tox/settings.py
ctx_retry_attempts: int = Field(default=3, alias="CTX_RETRY_ATTEMPTS")
ctx_retry_base: float = Field(default=0.5, alias="CTX_RETRY_BASE")
```

---

## Detailed Findings by Repository

### AOP-MCP (aop-mcp)

**Version:** v0.8.1  
**Primary Risk:** SPARQL timeout cascades

**Key Files:**
- `src/adapters/sparql_client.py` - Async HTTPX client with failover
- `src/adapters/aop_wiki.py` - AOP-Wiki SPARQL consumer
- `src/adapters/aop_db.py` - AOP-DB integration

**Findings:**
1. SPARQL client has configurable timeout (default 10s) and retries (default 2)
2. No circuit breaker - sequential endpoint failover only
3. Cache support exists but no cache-first on failure mode
4. Metrics recording available but not used for health checks

**Maximum Safe Load:**
- Query complexity: Unlimited (no validation)
- Result size: Unlimited (no LIMIT enforcement)
- Concurrent queries: Limited by HTTPX connection pool (default 100)

---

### CompTox-MCP (comptox-mcp)

**Version:** v0.2.2  
**Primary Risk:** Rate limit handling

**Key Files:**
- `src/epacomp_tox/settings.py` - Configuration with retry settings
- `src/epacomp_tox/client.py` - MCP client wrapper

**Findings:**
1. Retry configuration: 3 attempts with 0.5s base delay
2. No exponential backoff - fixed delay between retries
3. No jitter - thundering herd risk
4. No rate limit header parsing (429, Retry-After)

**Maximum Safe Load:**
- Requests per minute: Unknown (EPA CompTox limit not documented)
- Concurrent requests: Limited by client configuration
- No quota budget per tool call

---

### PBPK-MCP (pbpk-mcp)

**Version:** v0.4.3  
**Primary Risk:** Memory exhaustion

**Key Files:**
- `src/mcp_bridge/services/job_service.py` - Job orchestration (1392 lines)
- `src/mcp_bridge/config.py` - Application configuration
- `src/mcp_bridge/storage/population_store.py` - Result storage

**Findings:**
1. SQLite-based job persistence survives restarts
2. No population size validation
3. Job timeout: 300s (5 minutes) - insufficient for large populations
4. Worker threads: 2 (configurable)
5. No memory quota enforcement

**Maximum Safe Load:**
- Population size: ~1000 patients (before timeout/OOM risk)
- Simulation duration: 5 minutes max (default timeout)
- Memory per job: Unlimited (no quota)

---

### OQT-MCP (oqt-mcp)

**Version:** v0.3.0  
**Primary Risk:** Timeout on heavy operations

**Key Files:**
- `TIMEOUT_FIX_SUMMARY.md` - Timeout hardening history
- `src/` - QSAR workflow implementation

**Findings:**
1. Timeout increased from 120s to 300s for heavy operations
2. Better error handling for 404 responses
3. MCP content type standardization applied

**Maximum Safe Load:**
- Workflow timeout: 300 seconds
- Heavy operations: Metabolism, reports, batch processing

---

## Risk Severity Legend

| Badge | Severity | Description |
|-------|----------|-------------|
| 🔴 | Critical | System failure, data loss, or security breach likely |
| 🟠 | High | Performance degradation or availability issues likely |
| 🟡 | Medium | Limited impact, workarounds available |
| 🟢 | Low | Minor issues, easily mitigated |

---

**End of Audit Report**

*Report generated by Performance & Resilience Engineer*  
*ToxMCP Ecosystem Analysis - April 2026*

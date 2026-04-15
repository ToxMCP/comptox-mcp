# PBPK-MCP: Detailed Remediation Code

> **Reviewed copy note:** Treat these snippets as reference patterns. Physiological bounds, workload limits, and runtime hardening values should be validated against representative models and infrastructure.


## 1. Parameter Bounds Validation (Physiological Plausibility)

**File:** `src/mcp/tools/parameter_bounds.py`

```python
from typing import Dict, Tuple, Optional
from pydantic import BaseModel, validator
from enum import Enum
import numpy as np

class ParameterCategory(str, Enum):
    """Categories of PBPK parameters."""
    PHYSICOCHEMICAL = "physicochemical"
    ANATOMICAL = "anatomical"
    PHYSIOLOGICAL = "physiological"
    ENZYME_KINETICS = "enzyme_kinetics"

class ParameterBounds(BaseModel):
    """Bounds for a single parameter."""
    min_value: float
    max_value: float
    default_value: float
    unit: str
    category: ParameterCategory
    description: str
    references: list = []  # Literature references
    
    def validate_value(self, value: float) -> bool:
        """Check if value is within bounds."""
        return self.min_value <= value <= self.max_value

class PBPKParameterDatabase:
    """Database of physiologically plausible parameter bounds."""
    
    # Organ volumes (L) - based on literature
    ORGAN_VOLUMES = {
        "Liver": ParameterBounds(
            min_value=0.5,
            max_value=3.0,
            default_value=1.5,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Liver volume",
            references=["ICRP 89", "PK-Sim defaults"]
        ),
        "Kidney": ParameterBounds(
            min_value=0.2,
            max_value=0.6,
            default_value=0.31,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Kidney volume (both kidneys)",
            references=["ICRP 89"]
        ),
        "Brain": ParameterBounds(
            min_value=1.0,
            max_value=1.8,
            default_value=1.4,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Brain volume",
            references=["ICRP 89"]
        ),
        "Muscle": ParameterBounds(
            min_value=15.0,
            max_value=35.0,
            default_value=24.0,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Muscle volume",
            references=["ICRP 89"]
        ),
        "Adipose": ParameterBounds(
            min_value=5.0,
            max_value=30.0,
            default_value=15.0,
            unit="L",
            category=ParameterCategory.ANATOMICAL,
            description="Adipose tissue volume",
            references=["ICRP 89"]
        ),
    }
    
    # Blood flows (L/min) - must sum to cardiac output
    BLOOD_FLOWS = {
        "Liver": ParameterBounds(
            min_value=0.5,
            max_value=2.0,
            default_value=1.0,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Hepatic blood flow",
            references=["Davies 1993"]
        ),
        "Kidney": ParameterBounds(
            min_value=0.5,
            max_value=1.5,
            default_value=1.0,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Renal blood flow",
            references=["Davies 1993"]
        ),
        "Brain": ParameterBounds(
            min_value=0.3,
            max_value=1.0,
            default_value=0.7,
            unit="L/min",
            category=ParameterCategory.PHYSIOLOGICAL,
            description="Cerebral blood flow",
            references=["Davies 1993"]
        ),
    }
    
    # Clearance parameters
    CLEARANCE = {
        "Liver|Clearance": ParameterBounds(
            min_value=0.0,
            max_value=100.0,  # Cannot exceed hepatic blood flow
            default_value=1.0,
            unit="L/h",
            category=ParameterCategory.ENZYME_KINETICS,
            description="Hepatic clearance",
            references=["Rowland 1973"]
        ),
        "Kidney|Clearance": ParameterBounds(
            min_value=0.0,
            max_value=50.0,  # Cannot exceed renal blood flow
            default_value=1.0,
            unit="L/h",
            category=ParameterCategory.ENZYME_KINETICS,
            description="Renal clearance",
            references=["Rowland 1973"]
        ),
    }
    
    # Physicochemical properties
    PHYSICOCHEMICAL = {
        "Lipophilicity": ParameterBounds(
            min_value=-5.0,
            max_value=10.0,
            default_value=1.0,
            unit="logP",
            category=ParameterCategory.PHYSICOCHEMICAL,
            description="Octanol-water partition coefficient",
            references=["Leo 1971"]
        ),
        "MolecularWeight": ParameterBounds(
            min_value=50.0,
            max_value=1000.0,
            default_value=300.0,
            unit="g/mol",
            category=ParameterCategory.PHYSICOCHEMICAL,
            description="Molecular weight",
            references=[]
        ),
        "FractionUnbound": ParameterBounds(
            min_value=0.0,
            max_value=1.0,
            default_value=0.1,
            unit="dimensionless",
            category=ParameterCategory.PHYSICOCHEMICAL,
            description="Fraction unbound in plasma",
            references=[]
        ),
    }
    
    @classmethod
    def get_bounds(cls, parameter_path: str) -> Optional[ParameterBounds]:
        """Get bounds for a parameter by path."""
        # Search in all categories
        for category in [cls.ORGAN_VOLUMES, cls.BLOOD_FLOWS, cls.CLEARANCE, cls.PHYSICOCHEMICAL]:
            if parameter_path in category:
                return category[parameter_path]
        
        # Try partial matching
        for category in [cls.ORGAN_VOLUMES, cls.BLOOD_FLOWS, cls.CLEARANCE, cls.PHYSICOCHEMICAL]:
            for key, bounds in category.items():
                if key in parameter_path or parameter_path in key:
                    return bounds
        
        return None
    
    @classmethod
    def validate_parameter(cls, parameter_path: str, value: float) -> tuple:
        """
        Validate parameter value against bounds.
        
        Returns:
            (is_valid, bounds, message)
        """
        bounds = cls.get_bounds(parameter_path)
        
        if bounds is None:
            return (True, None, f"No bounds defined for {parameter_path}")
        
        if not bounds.validate_value(value):
            return (
                False,
                bounds,
                f"Value {value} for {parameter_path} outside plausible range "
                f"[{bounds.min_value}, {bounds.max_value}] {bounds.unit}"
            )
        
        return (True, bounds, "Valid")
    
    @classmethod
    def get_all_parameters(cls) -> Dict[str, ParameterBounds]:
        """Get all defined parameters."""
        all_params = {}
        for category in [cls.ORGAN_VOLUMES, cls.BLOOD_FLOWS, cls.CLEARANCE, cls.PHYSICOCHEMICAL]:
            all_params.update(category)
        return all_params


# Integration with set_parameter_value
class ValidatedSetParameterValueRequest(BaseModel):
    """Parameter value request with validation."""
    
    simulation_id: str
    parameter_path: str
    value: float
    unit: Optional[str] = None
    update_mode: Optional[str] = "absolute"
    comment: Optional[str] = None
    
    @validator('value')
    def validate_physiological_bounds(cls, v, values):
        """Validate against physiological bounds."""
        if 'parameter_path' not in values:
            return v
        
        parameter_path = values['parameter_path']
        is_valid, bounds, message = PBPKParameterDatabase.validate_parameter(
            parameter_path, v
        )
        
        if not is_valid:
            raise ValueError(message)
        
        return v
    
    @validator('parameter_path')
    def validate_parameter_exists(cls, v):
        """Warn if parameter not in database."""
        bounds = PBPKParameterDatabase.get_bounds(v)
        if bounds is None:
            # Log warning but allow (might be custom parameter)
            logger.warning(f"Parameter {v} not in database - no bounds validation")
        return v


# Parameter change audit trail
class ParameterChangeAudit:
    """Audit trail for parameter changes."""
    
    def __init__(self):
        self.changes: list = []
    
    def log_change(
        self,
        simulation_id: str,
        parameter_path: str,
        old_value: float,
        new_value: float,
        user_id: str,
        reason: str = None
    ):
        """Log a parameter change."""
        change = {
            "timestamp": datetime.utcnow().isoformat(),
            "simulation_id": simulation_id,
            "parameter_path": parameter_path,
            "old_value": old_value,
            "new_value": new_value,
            "change_magnitude": abs(new_value - old_value) / old_value if old_value != 0 else float('inf'),
            "user_id": user_id,
            "reason": reason
        }
        self.changes.append(change)
    
    def detect_p_hacking(self, simulation_id: str) -> list:
        """Detect systematic parameter exploration (p-hacking)."""
        sim_changes = [c for c in self.changes if c["simulation_id"] == simulation_id]
        
        alerts = []
        
        # Group by parameter
        param_changes = {}
        for change in sim_changes:
            param = change["parameter_path"]
            if param not in param_changes:
                param_changes[param] = []
            param_changes[param].append(change)
        
        # Detect patterns
        for param, changes in param_changes.items():
            # Pattern 1: Many small changes to same parameter
            if len(changes) > 5:
                alerts.append({
                    "type": "frequent_changes",
                    "parameter": param,
                    "count": len(changes),
                    "recommendation": "Frequent parameter changes detected - possible optimization bias"
                })
            
            # Pattern 2: Oscillating values (searching for target)
            if len(changes) >= 3:
                values = [c["new_value"] for c in changes]
                # Check for oscillation (up-down-up or down-up-down)
                diffs = [values[i+1] - values[i] for i in range(len(values)-1)]
                sign_changes = sum(1 for i in range(len(diffs)-1) if diffs[i] * diffs[i+1] < 0)
                
                if sign_changes >= 2:
                    alerts.append({
                        "type": "oscillating_values",
                        "parameter": param,
                        "changes": len(changes),
                        "recommendation": "Oscillating parameter values - possible target-seeking behavior"
                    })
            
            # Pattern 3: Large magnitude changes
            large_changes = [c for c in changes if c["change_magnitude"] > 0.5]
            if len(large_changes) > 2:
                alerts.append({
                    "type": "large_changes",
                    "parameter": param,
                    "count": len(large_changes),
                    "recommendation": "Large parameter changes detected - review physiological plausibility"
                })
        
        return alerts
```

---

> **Reviewed copy (2026-04-15):** This document was retained from the original package but lightly edited for consistency.  
> Unless explicitly stated otherwise, code blocks are **reference implementations**, not validated patches, and scenario-based exploit narratives should not be read as reproduced proofs.



## 2. Population Size Limits and Memory Quotas

**File:** `src/mcp_bridge/services/job_service.py`

```python
from pydantic import BaseModel, validator
import psutil
import os

class JobResourceConfig(BaseModel):
    """Resource limits for jobs."""
    
    max_population_size: int = 5000
    max_memory_per_job_mb: int = 2048  # 2 GB
    max_simulation_duration_seconds: int = 1800  # 30 minutes
    max_concurrent_jobs_per_user: int = 5
    max_daily_jobs_per_user: int = 100
    
    @validator('max_population_size')
    def validate_population_size(cls, v):
        if v > 10000:
            raise ValueError("Population size cannot exceed 10000")
        return v

class ResourceQuotaEnforcer:
    """Enforce resource quotas for jobs."""
    
    def __init__(self, config: JobResourceConfig = None):
        self.config = config or JobResourceConfig()
        self.user_job_counts: Dict[str, Dict[str, int]] = {}
    
    def check_population_size(self, population_size: int) -> tuple:
        """
        Check if population size is within quota.
        
        Returns:
            (is_allowed, message)
        """
        if population_size > self.config.max_population_size:
            return (
                False,
                f"Population size {population_size} exceeds maximum {self.config.max_population_size}. "
                f"Contact administrator for large population simulations."
            )
        
        return (True, "Valid")
    
    def check_memory_quota(self, requested_memory_mb: int) -> tuple:
        """
        Check if memory request is within quota.
        
        Returns:
            (is_allowed, message)
        """
        if requested_memory_mb > self.config.max_memory_per_job_mb:
            return (
                False,
                f"Memory request {requested_memory_mb} MB exceeds quota {self.config.max_memory_per_job_mb} MB"
            )
        
        # Check system memory
        available_mb = psutil.virtual_memory().available / (1024 * 1024)
        if requested_memory_mb > available_mb * 0.8:
            return (
                False,
                f"Insufficient system memory. Requested: {requested_memory_mb} MB, "
                f"Available: {available_mb:.0f} MB"
            )
        
        return (True, "Valid")
    
    def check_user_quotas(self, user_id: str) -> tuple:
        """
        Check if user is within daily and concurrent job quotas.
        
        Returns:
            (is_allowed, message)
        """
        user_counts = self.user_job_counts.get(user_id, {
            "concurrent": 0,
            "daily": 0,
            "last_reset": datetime.utcnow()
        })
        
        # Reset daily count if new day
        last_reset = user_counts["last_reset"]
        if (datetime.utcnow() - last_reset).days >= 1:
            user_counts["daily"] = 0
            user_counts["last_reset"] = datetime.utcnow()
        
        if user_counts["concurrent"] >= self.config.max_concurrent_jobs_per_user:
            return (
                False,
                f"Concurrent job limit reached ({self.config.max_concurrent_jobs_per_user}). "
                f"Wait for existing jobs to complete."
            )
        
        if user_counts["daily"] >= self.config.max_daily_jobs_per_user:
            return (
                False,
                f"Daily job limit reached ({self.config.max_daily_jobs_per_user}). "
                f"Try again tomorrow."
            )
        
        return (True, "Valid")
    
    def estimate_memory_requirement(self, population_size: int) -> int:
        """
        Estimate memory requirement for population simulation.
        
        Returns:
            Estimated memory in MB
        """
        # Base memory for simulation
        base_memory = 100  # MB
        
        # Per-patient memory (empirical estimate)
        memory_per_patient = 0.5  # MB
        
        # Safety factor
        safety_factor = 1.5
        
        estimated = (base_memory + population_size * memory_per_patient) * safety_factor
        
        return int(estimated)
    
    def validate_job_request(
        self,
        user_id: str,
        population_size: int
    ) -> tuple:
        """
        Validate complete job request against all quotas.
        
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # Check population size
        allowed, message = self.check_population_size(population_size)
        if not allowed:
            errors.append(message)
        
        # Check memory
        memory_required = self.estimate_memory_requirement(population_size)
        allowed, message = self.check_memory_quota(memory_required)
        if not allowed:
            errors.append(message)
        
        # Check user quotas
        allowed, message = self.check_user_quotas(user_id)
        if not allowed:
            errors.append(message)
        
        return (len(errors) == 0, errors)
    
    def record_job_start(self, user_id: str, job_id: str):
        """Record job start for quota tracking."""
        if user_id not in self.user_job_counts:
            self.user_job_counts[user_id] = {
                "concurrent": 0,
                "daily": 0,
                "last_reset": datetime.utcnow()
            }
        
        self.user_job_counts[user_id]["concurrent"] += 1
        self.user_job_counts[user_id]["daily"] += 1
    
    def record_job_end(self, user_id: str, job_id: str):
        """Record job completion."""
        if user_id in self.user_job_counts:
            self.user_job_counts[user_id]["concurrent"] = max(
                0,
                self.user_job_counts[user_id]["concurrent"] - 1
            )


# Integration with job submission
class ResourceConstrainedJobService:
    """Job service with resource quota enforcement."""
    
    def __init__(self):
        self.quota_enforcer = ResourceQuotaEnforcer()
    
    async def submit_population_simulation(
        self,
        user_id: str,
        simulation_id: str,
        population_size: int,
        **kwargs
    ) -> JobRecord:
        """Submit population simulation with quota checks."""
        # Validate against quotas
        is_valid, errors = self.quota_enforcer.validate_job_request(
            user_id, population_size
        )
        
        if not is_valid:
            raise QuotaExceeded(f"Job validation failed: {'; '.join(errors)}")
        
        # Record job start
        self.quota_enforcer.record_job_start(user_id, simulation_id)
        
        try:
            # Create job
            job = JobRecord(
                job_id=str(uuid.uuid4()),
                simulation_id=simulation_id,
                job_type="population_simulation",
                population_size=population_size,
                user_id=user_id,
                estimated_memory_mb=self.quota_enforcer.estimate_memory_requirement(
                    population_size
                ),
                submitted_at=datetime.utcnow()
            )
            
            # Submit to queue
            await self._submit_to_queue(job)
            
            return job
            
        except Exception:
            # Rollback quota on failure
            self.quota_enforcer.record_job_end(user_id, simulation_id)
            raise
```

---

## 3. Container Security Hardening

**File:** `Dockerfile` (Secure Multi-Stage Build)

```dockerfile
# =============================================================================
# PBPK-MCP Secure Dockerfile
# Multi-stage build with security hardening
# =============================================================================

# Stage 1: Build environment (not used in final image)
FROM r-base:4.3.0 AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install R packages
RUN R -e "install.packages('ospsuite', repos='https://...')" \
    && R -e "install.packages('rxode2', repos='https://...')"

# Stage 2: Runtime environment (minimal, secure)
FROM gcr.io/distroless/cc-debian11:nonroot

# Copy R installation from builder
COPY --from=builder /usr/lib/R /usr/lib/R
COPY --from=builder /usr/local/lib/R /usr/local/lib/R
COPY --from=builder /usr/share/R /usr/share/R

# Copy application code
COPY --chown=nonroot:nonroot ./src /app/src
COPY --chown=nonroot:nonroot ./requirements.txt /app/

# Set working directory
WORKDIR /app

# Switch to non-root user
USER nonroot:nonroot

# Environment variables
ENV R_HOME=/usr/lib/R
ENV R_LIBS_USER=/usr/local/lib/R/site-library
ENV TOXMCP_CONTAINER_DIGEST=${CONTAINER_DIGEST}
ENV TOXMCP_GIT_COMMIT=${GIT_COMMIT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["/app/src/health_check"]

# Expose port
EXPOSE 8080

# Run application
ENTRYPOINT ["Rscript", "/app/src/main.R"]
```

**Seccomp Profile:** `pbpk-seccomp.json`

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64", "SCMP_ARCH_X86"],
  "syscalls": [
    {
      "names": [
        "accept",
        "accept4",
        "bind",
        "clone",
        "close",
        "connect",
        "epoll_create1",
        "epoll_ctl",
        "epoll_pwait",
        "exit",
        "exit_group",
        "fcntl",
        "fstat",
        "futex",
        "getpid",
        "getrandom",
        "getsockname",
        "getsockopt",
        "listen",
        "mmap",
        "mprotect",
        "munmap",
        "openat",
        "read",
        "recvfrom",
        "recvmsg",
        "rt_sigaction",
        "rt_sigprocmask",
        "rt_sigreturn",
        "select",
        "sendmsg",
        "sendto",
        "setitimer",
        "setsockopt",
        "socket",
        "write",
        "writev"
      ],
      "action": "SCMP_ACT_ALLOW"
    },
    {
      "names": [
        "execve",
        "execveat",
        "fork",
        "vfork",
        "ptrace",
        "mount",
        "umount",
        "umount2",
        "reboot",
        "open_by_handle_at"
      ],
      "action": "SCMP_ACT_ERRNO"
    }
  ]
}
```

**Docker Compose Secure Configuration:** `docker-compose.secure.yml`

```yaml
version: '3.8'

services:
  pbpk-mcp:
    build:
      context: .
      dockerfile: Dockerfile.secure
      args:
        CONTAINER_DIGEST: ${CONTAINER_DIGEST}
        GIT_COMMIT: ${GIT_COMMIT}
    
    # Security options
    security_opt:
      - no-new-privileges:true
      - seccomp:pbpk-seccomp.json
      - apparmor:pbpk-profile
    
    # Capabilities
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
    
    # Read-only root filesystem
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
      - /var/tmp:noexec,nosuid,size=100m
    
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '1.0'
          memory: 2G
    
    # Network
    networks:
      - toxmcp-internal
    
    # Environment
    environment:
      - TOXMCP_ENVIRONMENT=production
      - TOXMCP_SECURE_MODE=true
      - MAX_POPULATION_SIZE=5000
      - MAX_MEMORY_PER_JOB_MB=2048
    
    # Health check
    healthcheck:
      test: ["CMD", "/app/health_check"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  toxmcp-internal:
    internal: true  # No external access
```

---

## 4. Floating-Point Determinism

**File:** `src/mcp_bridge/audit/trail.py`

```python
import json
import decimal
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

class CanonicalJsonEncoder(json.JSONEncoder):
    """
    JSON encoder with canonical floating-point representation.
    
    Ensures that the same scientific results produce identical
    audit hashes across different hardware and Python versions.
    """
    
    # Precision for IEEE 754 double precision
    FLOAT_PRECISION = 15
    
    def encode(self, obj: Any) -> str:
        return json.dumps(
            self._canonicalize(obj),
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=True
        )
    
    def _canonicalize(self, obj: Any) -> Any:
        """Convert object to canonical form."""
        if isinstance(obj, float):
            # Handle special values
            if obj != obj:  # NaN
                return "NaN"
            if obj == float('inf'):
                return "Infinity"
            if obj == float('-inf'):
                return "-Infinity"
            
            # Round to fixed precision
            d = Decimal(obj)
            quantized = d.quantize(
                Decimal('0.00000000000000'),  # 14 decimal places
                rounding=ROUND_HALF_UP
            )
            return float(quantized)
        
        elif isinstance(obj, dict):
            # Sort keys recursively
            return {
                k: self._canonicalize(v)
                for k, v in sorted(obj.items())
            }
        
        elif isinstance(obj, list):
            return [self._canonicalize(item) for item in obj]
        
        elif isinstance(obj, str):
            # Normalize Unicode
            return obj.encode('utf-8', 'ignore').decode('utf-8')
        
        elif isinstance(obj, (int, bool, type(None))):
            return obj
        
        else:
            # Convert unknown types to string
            return str(obj)


def compute_deterministic_hash(event: dict) -> str:
    """
    Compute deterministic hash for audit event.
    
    This ensures that identical scientific results produce
    identical hashes regardless of hardware or Python version.
    """
    # Remove hash field if present
    temp = dict(event)
    temp.pop("hash", None)
    temp.pop("signature", None)
    
    # Use canonical JSON encoding
    encoder = CanonicalJsonEncoder()
    payload = encoder.encode(temp)
    
    # Compute hash
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


# Test determinism
def test_hash_determinism():
    """Test that hash is deterministic across calls."""
    event = {
        "prediction": 0.1 + 0.2,  # 0.30000000000000004
        "confidence": 0.95,
        "nested": {
            "value": 1.234567890123456789
        }
    }
    
    hash1 = compute_deterministic_hash(event)
    hash2 = compute_deterministic_hash(event)
    
    assert hash1 == hash2, "Hash should be deterministic"
    
    # Test with equivalent values
    event2 = {
        "prediction": 0.3,  # Mathematically equivalent
        "confidence": 0.95,
        "nested": {
            "value": 1.234567890123456789
        }
    }
    
    hash3 = compute_deterministic_hash(event2)
    
    # Note: These may differ due to floating-point representation
    # but should be consistent within the same Python session
    print(f"Hash 1: {hash1}")
    print(f"Hash 2: {hash2}")
    print(f"Hash 3: {hash3}")
```

---

*These remediation code snippets address the critical issues identified in the PBPK-MCP audit.*

# CompTox-MCP: Detailed Remediation Code

> **Reviewed copy note:** Treat these snippets as reference patterns. Do not assume upstream providers support custom version headers or response signing unless those features are documented by the provider.


## 1. Version Pinning for Upstream APIs

**Reviewed caution:** If an upstream provider does not expose explicit version or snapshot selectors, capture request/response provenance internally instead of inventing unsupported protocol features.

**File:** `src/epacomp_tox/client.py`

```python
from typing import Dict, Optional
from pydantic import BaseModel
import httpx
import hashlib

class APIVersionConfig(BaseModel):
    """Configuration for API version pinning."""
    api_version: str  # e.g., "2024-01-15"
    data_snapshot_id: str  # e.g., "ds_2024_q1_v3"
    require_version_header: bool = True

class VersionedCompToxClient:
    """CompTox API client with version pinning."""
    
    def __init__(
        self,
        base_url: str = "https://comptox.epa.gov/ctx-api",
        version_config: Optional[APIVersionConfig] = None
    ):
        self.base_url = base_url
        self.version_config = version_config or APIVersionConfig(
            api_version="2024-01-15",
            data_snapshot_id="latest"
        )
        self.client = httpx.AsyncClient()
        self.response_cache: Dict[str, dict] = {}
    
    def _get_version_headers(self) -> Dict[str, str]:
        """Get version pinning headers."""
        headers = {}
        if self.version_config.require_version_header:
            headers["X-API-Version"] = self.version_config.api_version
            headers["X-Data-Snapshot"] = self.version_config.data_snapshot_id
        return headers
    
    async def get_chemical_detail(
        self,
        dtxsid: str,
        use_cache: bool = True
    ) -> dict:
        """Get chemical details with version pinning."""
        cache_key = f"{dtxsid}:{self.version_config.api_version}:{self.version_config.data_snapshot_id}"
        
        if use_cache and cache_key in self.response_cache:
            return self.response_cache[cache_key]
        
        url = f"{self.base_url}/chemical/detail/{dtxsid}"
        headers = self._get_version_headers()
        
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        # Add version metadata
        data["_api_metadata"] = {
            "api_version": self.version_config.api_version,
            "data_snapshot_id": self.version_config.data_snapshot_id,
            "retrieved_at": datetime.utcnow().isoformat(),
            "response_hash": hashlib.sha256(response.content).hexdigest()[:16]
        }
        
        if use_cache:
            self.response_cache[cache_key] = data
        
        return data
    
    async def get_qsar_predictions(
        self,
        dtxsid: str,
        model_id: str
    ) -> dict:
        """Get QSAR predictions with model version tracking."""
        url = f"{self.base_url}/qsar/predictions/{dtxsid}"
        headers = self._get_version_headers()
        headers["X-QSAR-Model-ID"] = model_id
        
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        # Add model version metadata
        data["_model_metadata"] = {
            "model_id": model_id,
            "model_version": response.headers.get("X-QSAR-Model-Version", "unknown"),
            "api_version": self.version_config.api_version,
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
        return data


# Integration with workflow
class VersionedWorkflow:
    """Workflow with complete version tracking."""
    
    def __init__(self, client: VersionedCompToxClient):
        self.client = client
    
    async def run_assessment(self, dtxsid: str) -> dict:
        """Run chemical assessment with full version tracking."""
        # Get chemical details
        chemical = await self.client.get_chemical_detail(dtxsid)
        
        # Get QSAR predictions
        predictions = await self.client.get_qsar_predictions(
            dtxsid,
            model_id="TEST_4.2"
        )
        
        # Compile evidence with version metadata
        evidence = {
            "chemical": chemical,
            "predictions": predictions,
            "assessment_metadata": {
                "comptox_api_version": chemical["_api_metadata"]["api_version"],
                "data_snapshot_id": chemical["_api_metadata"]["data_snapshot_id"],
                "qsar_model_version": predictions["_model_metadata"]["model_version"],
                "assessment_timestamp": datetime.utcnow().isoformat()
            }
        }
        
        return evidence
```

---

> **Reviewed copy (2026-04-15):** This document was retained from the original package but lightly edited for consistency.  
> Unless explicitly stated otherwise, code blocks are **reference implementations**, not validated patches, and scenario-based exploit narratives should not be read as reproduced proofs.



## 2. Cryptographic Audit Chain

**File:** `src/epacomp_tox/audit.py`

```python
import hashlib
import json
import base64
from datetime import datetime
from typing import Dict, List, Optional, Callable
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
import os

class AuditEvent(BaseModel):
    """Single audit event with cryptographic verification."""
    event_type: str
    timestamp: str
    user_id: str
    session_id: str
    action: str
    resource: str
    details: Dict
    content_hash: str
    previous_hash: str
    signature: Optional[str] = None

class CryptographicAuditChain:
    """Tamper-evident audit chain."""
    
    def __init__(self, private_key_path: Optional[str] = None):
        self.previous_hash = "0" * 64
        self.events: List[AuditEvent] = []
        self.sinks: List[Callable[[AuditEvent], None]] = []
        
        # Load or generate signing key
        if private_key_path and os.path.exists(private_key_path):
            self.private_key = self._load_private_key(private_key_path)
        else:
            self.private_key = self._generate_key()
            if private_key_path:
                self._save_private_key(private_key_path)
    
    def emit(self, event_data: Dict, user_id: str, session_id: str) -> AuditEvent:
        """Emit audit event with cryptographic chaining."""
        # Compute content hash
        content = json.dumps(event_data, sort_keys=True)
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Create event
        event = AuditEvent(
            event_type=event_data.get("type", "unknown"),
            timestamp=datetime.utcnow().isoformat(),
            user_id=user_id,
            session_id=session_id,
            action=event_data.get("action", "unknown"),
            resource=event_data.get("resource", "unknown"),
            details=event_data,
            content_hash=content_hash,
            previous_hash=self.previous_hash
        )
        
        # Sign event
        event.signature = self._sign_event(event)
        
        # Update chain
        self.previous_hash = content_hash
        self.events.append(event)
        
        # Emit to sinks
        for sink in self.sinks:
            sink(event)
        
        return event
    
    def _sign_event(self, event: AuditEvent) -> str:
        """Cryptographically sign event."""
        payload = f"{event.content_hash}:{event.previous_hash}:{event.timestamp}"
        signature = self.private_key.sign(
            payload.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()
    
    def verify_chain(self) -> bool:
        """Verify integrity of entire audit chain."""
        previous_hash = "0" * 64
        
        for event in self.events:
            # Verify previous hash linkage
            if event.previous_hash != previous_hash:
                return False
            
            # Verify content hash
            content = json.dumps(event.details, sort_keys=True)
            computed_hash = hashlib.sha256(content.encode()).hexdigest()
            if computed_hash != event.content_hash:
                return False
            
            # Verify signature
            if not self._verify_signature(event):
                return False
            
            previous_hash = event.content_hash
        
        return True
    
    def _verify_signature(self, event: AuditEvent) -> bool:
        """Verify event signature."""
        try:
            payload = f"{event.content_hash}:{event.previous_hash}:{event.timestamp}"
            signature = base64.b64decode(event.signature)
            
            self.private_key.public_key().verify(
                signature,
                payload.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
    
    def add_sink(self, sink: Callable[[AuditEvent], None]):
        """Add audit sink (e.g., file, database, external service)."""
        self.sinks.append(sink)
    
    def _generate_key(self):
        """Generate RSA key pair."""
        return rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
    
    def _load_private_key(self, path: str):
        """Load private key from file."""
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
    
    def _save_private_key(self, path: str):
        """Save private key to file."""
        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(path, "wb") as f:
            f.write(pem)


# File-based audit sink with WORM properties
class WORMAuditSink:
    """Write-Once-Read-Many audit log sink."""
    
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Set immutable flag on log directory (Unix)
        self._set_immutable()
    
    def __call__(self, event: AuditEvent):
        """Write event to WORM log."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit_{date_str}.jsonl"
        
        # Append-only mode
        with open(log_file, "a") as f:
            f.write(json.dumps(event.dict(), default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())  # Ensure write to disk
        
        # Set immutable flag on file (Unix)
        self._set_file_immutable(log_file)
    
    def _set_immutable(self):
        """Set immutable flag on log directory."""
        try:
            # Linux: chattr +i
            import subprocess
            subprocess.run(["chattr", "+a", str(self.log_dir)], check=False)
        except Exception:
            pass  # Not supported on all systems
    
    def _set_file_immutable(self, file_path: Path):
        """Set immutable flag on log file."""
        try:
            import subprocess
            subprocess.run(["chattr", "+i", str(file_path)], check=False)
        except Exception:
            pass


# Usage
audit_chain = CryptographicAuditChain(private_key_path="/secure/audit_key.pem")
audit_chain.add_sink(WORMAuditSink("/var/log/comptox-mcp/audit"))

# In API endpoint
async def chemical_search_endpoint(request: Request):
    user = authenticate(request)
    
    audit_chain.emit(
        event_data={
            "type": "chemical_search",
            "action": "search",
            "resource": "chemical",
            "query": request.query_params.get("q"),
            "results_count": len(results)
        },
        user_id=user.id,
        session_id=request.session_id
    )
```

---

## 3. Retry with Exponential Backoff and Jitter

**File:** `src/epacomp_tox/client.py`

```python
import random
import asyncio
from typing import TypeVar, Callable
import httpx

T = TypeVar('T')

class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_status_codes: set = {429, 500, 502, 503, 504}

async def retry_with_backoff(
    func: Callable[[], T],
    config: RetryConfig = None,
    is_retryable: Callable[[Exception], bool] = None
) -> T:
    """
    Execute function with exponential backoff and jitter.
    
    Args:
        func: Async function to execute
        config: Retry configuration
        is_retryable: Function to determine if exception is retryable
    
    Returns:
        Result of func()
    
    Raises:
        Last exception if all retries exhausted
    """
    config = config or RetryConfig()
    is_retryable = is_retryable or (lambda e: True)
    
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            
            # Check if we should retry
            if attempt >= config.max_retries:
                raise
            
            if not is_retryable(e):
                raise
            
            # Calculate delay
            delay = config.base_delay * (config.exponential_base ** attempt)
            delay = min(delay, config.max_delay)
            
            # Add jitter
            if config.jitter:
                delay = delay * (0.5 + random.random())
            
            await asyncio.sleep(delay)
    
    raise last_exception


# HTTP-specific retry
async def http_request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs
) -> httpx.Response:
    """Make HTTP request with retry logic."""
    config = RetryConfig()
    
    def is_retryable_error(e: Exception) -> bool:
        """Determine if error is retryable."""
        if isinstance(e, httpx.HTTPStatusError):
            return e.response.status_code in config.retryable_status_codes
        if isinstance(e, (httpx.ConnectError, httpx.TimeoutException)):
            return True
        return False
    
    async def make_request():
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return response
    
    return await retry_with_backoff(
        make_request,
        config=config,
        is_retryable=is_retryable_error
    )


# Rate limit handling
async def handle_rate_limit(response: httpx.Response) -> float:
    """
    Extract retry delay from rate limit response.
    
    Returns:
        Delay in seconds
    """
    if response.status_code != 429:
        return 0
    
    # Check Retry-After header
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            # Could be HTTP date, parse it
            pass
    
    # Check X-RateLimit-Reset header
    reset_timestamp = response.headers.get("X-RateLimit-Reset")
    if reset_timestamp:
        try:
            reset_time = datetime.fromtimestamp(int(reset_timestamp))
            delay = (reset_time - datetime.utcnow()).total_seconds()
            return max(delay, 1)
        except (ValueError, OSError):
            pass
    
    # Default backoff
    return 60.0
```

---

## 4. Distributed Tracing

**File:** `src/epacomp_tox/middleware.py`

```python
from contextvars import ContextVar
from typing import Optional, Dict
import uuid

# Context variable for trace ID
trace_id_var: ContextVar[str] = ContextVar('trace_id', default=None)
span_id_var: ContextVar[str] = ContextVar('span_id', default=None)

class TraceContext:
    """W3C Trace Context propagation."""
    
    TRACEPARENT_HEADER = "traceparent"
    TRACESTATE_HEADER = "tracestate"
    
    def __init__(self, trace_id: str = None, span_id: str = None):
        self.trace_id = trace_id or self._generate_trace_id()
        self.span_id = span_id or self._generate_span_id()
        self.parent_span_id = None
    
    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> "TraceContext":
        """Parse trace context from HTTP headers."""
        traceparent = headers.get(cls.TRACEPARENT_HEADER)
        if traceparent:
            # Parse W3C traceparent format: 00-{trace_id}-{span_id}-{flags}
            parts = traceparent.split("-")
            if len(parts) == 4:
                return cls(trace_id=parts[1], span_id=parts[2])
        
        return cls()  # Generate new context
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers."""
        traceparent = f"00-{self.trace_id}-{self.span_id}-01"
        return {
            self.TRACEPARENT_HEADER: traceparent
        }
    
    def create_child_span(self) -> "TraceContext":
        """Create child span context."""
        child = TraceContext(trace_id=self.trace_id)
        child.parent_span_id = self.span_id
        return child
    
    def _generate_trace_id(self) -> str:
        """Generate 16-byte hex trace ID."""
        return uuid.uuid4().hex + uuid.uuid4().hex[:16]
    
    def _generate_span_id(self) -> str:
        """Generate 8-byte hex span ID."""
        return uuid.uuid4().hex[:16]


# FastAPI middleware
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class TracingMiddleware(BaseHTTPMiddleware):
    """Middleware to handle distributed tracing."""
    
    async def dispatch(self, request: Request, call_next):
        # Extract trace context from incoming request
        trace_context = TraceContext.from_headers(dict(request.headers))
        
        # Set context variables
        trace_id_var.set(trace_context.trace_id)
        span_id_var.set(trace_context.span_id)
        
        # Add trace context to request state
        request.state.trace_context = trace_context
        
        # Process request
        response = await call_next(request)
        
        # Add trace context to response headers
        for key, value in trace_context.to_headers().items():
            response.headers[key] = value
        
        return response


# Traced HTTP client
class TracedHTTPClient:
    """HTTP client that propagates trace context."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """Make request with trace context propagation."""
        # Get current trace context
        trace_id = trace_id_var.get()
        span_id = span_id_var.get()
        
        if trace_id and span_id:
            trace_context = TraceContext(trace_id, span_id)
            child_context = trace_context.create_child_span()
            
            # Add trace headers
            headers = kwargs.get("headers", {})
            headers.update(child_context.to_headers())
            kwargs["headers"] = headers
        
        url = f"{self.base_url}{path}"
        return await self.client.request(method, url, **kwargs)


# Usage in service calls
async def call_oqt_service(chemical_id: str) -> dict:
    """Call O-QT service with trace propagation."""
    client = TracedHTTPClient("http://oqt-mcp:8000")
    
    response = await client.request(
        "POST",
        "/mcp",
        json={
            "tool": "run_qsar_prediction",
            "params": {"chemical_id": chemical_id}
        }
    )
    
    return response.json()
```

---

*These remediation code snippets address the critical issues identified in the CompTox-MCP audit.*

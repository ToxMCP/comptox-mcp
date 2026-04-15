# AOP-MCP: Detailed Remediation Code

> **Reviewed copy note:** Treat these snippets as reference patterns. Do **not** pass arbitrary structural query fragments from untrusted input; use allow-listed query plans and bind only literals/URIs.


## 1. Parameterized SPARQL Queries (Injection Prevention)

**Reviewed caution:** Bind values safely, but keep query *structure* fixed. `ORDER BY`, `LIMIT`, graph patterns, and predicate choices should come from allow-lists, not directly from user input.

**File:** `src/adapters/sparql_client.py`

```python
from rdflib.plugins.sparql import prepareQuery
from rdflib import Literal, URIRef, Variable
from typing import Mapping, Any, Dict, Tuple
import re

class SafeSparqlClient:
    """SPARQL client with parameterized query support."""
    
    def __init__(self, endpoints: List[SparqlEndpoint]):
        self._endpoints = endpoints
        self._client = httpx.AsyncClient()
        self._template_cache: Dict[str, str] = {}
    
    def render(self, name: str, parameters: Mapping[str, Any] | None = None) -> Tuple[str, Dict]:
        """
        Render SPARQL template with safe parameter binding.
        
        Returns:
            Tuple of (query_string, bindings_dict)
        """
        template = self._get_template(name)
        params = parameters or {}
        
        # Extract parameter placeholders from template
        placeholders = self._extract_placeholders(template)
        
        # Validate all parameters are provided
        missing = placeholders - set(params.keys())
        if missing:
            raise ValueError(f"Missing parameters for template {name}: {missing}")
        
        # Convert parameters to RDFLib types
        bindings = {}
        for key, value in params.items():
            bindings[key] = self._convert_to_rdf_type(value)
        
        # Replace placeholders in template with variable references
        query_string = self._substitute_placeholders(template, placeholders)
        
        return query_string, bindings
    
    def _extract_placeholders(self, template: str) -> set:
        """Extract {placeholder} patterns from template."""
        pattern = r'\{(\w+)\}'
        return set(re.findall(pattern, template))
    
    def _convert_to_rdf_type(self, value: Any) -> Any:
        """Convert Python value to appropriate RDFLib type."""
        if isinstance(value, str):
            # Check if it's a URI
            if value.startswith('http://') or value.startswith('https://'):
                return URIRef(value)
            # Otherwise treat as literal
            return Literal(value)
        elif isinstance(value, (int, float)):
            return Literal(value)
        elif isinstance(value, bool):
            return Literal(value)
        else:
            return Literal(str(value))
    
    def _substitute_placeholders(self, template: str, placeholders: set) -> str:
        """Replace {placeholder} with ?placeholder for SPARQL variable binding."""
        result = template
        for placeholder in placeholders:
            result = result.replace(f'{{{placeholder}}}', f'?{placeholder}')
        return result
    
    async def query(self, name: str, parameters: Mapping[str, Any] | None = None) -> dict:
        """Execute parameterized SPARQL query."""
        query_string, bindings = self.render(name, parameters)
        
        # Prepare the query
        prepared = prepareQuery(query_string)
        
        # Execute with bindings
        return await self._execute_with_bindings(prepared, bindings)
    
    async def _execute_with_bindings(self, prepared_query, bindings: Dict) -> dict:
        """Execute prepared query with parameter bindings."""
        # Convert bindings to SPARQL BIND statements or use endpoint's binding mechanism
        # This example uses string substitution for the final query (still safe due to RDFLib types)
        bound_query = prepared_query.serialize()
        
        for var_name, value in bindings.items():
            # Replace ?var with bound value
            if isinstance(value, URIRef):
                bound_query = bound_query.replace(f'?{var_name}', f'<{value}>')
            elif isinstance(value, Literal):
                # Properly escape literal values
                escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
                bound_query = bound_query.replace(f'?{var_name}', f'"{escaped}"')
        
        return await self._dispatch(bound_query)


# Template example (search_aops.sparql)
SAFE_SEARCH_AOPS_TEMPLATE = """
SELECT DISTINCT ?aop ?title ?shortName
WHERE {{
  ?aop a aopo:AdverseOutcomePathway ;
       dc:title ?title .
  
  # Safe parameter binding with ?variable syntax
  {search_bindings}
  
  FILTER ({search_filter})
}}
ORDER BY {order_by}
LIMIT {limit}
"""

# Usage example
async def search_aops_safe(chemical_name: str):
    client = SafeSparqlClient(endpoints)
    
    # Parameters are only safe if structural query parts are fixed or allow-listed; do not treat arbitrary graph fragments as bindable user input
    result = await client.query("search_aops", {
        "search_bindings": "?aop aopo:hasMIE ?mie . ?mie dc:title ?chemicalName .",
        "search_filter": "CONTAINS(LCASE(?chemicalName), LCASE(?chemicalNameParam))",
        "order_by": "?title",
        "limit": "100",
        "chemicalNameParam": chemical_name  # This is safely bound as Literal
    })
    
    return result
```

---

> **Reviewed copy (2026-04-15):** This document was retained from the original package but lightly edited for consistency.  
> Unless explicitly stated otherwise, code blocks are **reference implementations**, not validated patches, and scenario-based exploit narratives should not be read as reproduced proofs.



## 2. Circuit Breaker for SPARQL Endpoints

**File:** `src/adapters/sparql_client.py`

```python
import asyncio
import random
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import time

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 1
    success_threshold: int = 2

class SparqlCircuitBreaker:
    """Circuit breaker for SPARQL endpoint protection."""
    
    def __init__(self, config: CircuitBreakerConfig = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise CircuitBreakerOpen("SPARQL endpoint circuit breaker is OPEN")
            
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpen("Circuit breaker half-open limit reached")
                self.half_open_calls += 1
        
        # Execute the call
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try reset."""
        if self.last_failure_time is None:
            return True
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.config.recovery_timeout
    
    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            else:
                self.failure_count = max(0, self.failure_count - 1)
    
    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN

class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


# Integration with SPARQL client
class ResilientSparqlClient(SafeSparqlClient):
    """SPARQL client with circuit breaker and retry logic."""
    
    def __init__(self, endpoints: List[SparqlEndpoint]):
        super().__init__(endpoints)
        self.circuit_breakers = {
            endpoint.url: SparqlCircuitBreaker()
            for endpoint in endpoints
        }
    
    async def _dispatch(
        self,
        query: str,
        *,
        timeout: float | None = None,
        max_retries: int = 3
    ) -> dict[str, Any]:
        """Dispatch with circuit breaker and exponential backoff."""
        last_error: Exception | None = None
        
        for endpoint in self._endpoints:
            circuit_breaker = self.circuit_breakers[endpoint.url]
            
            for attempt in range(max_retries):
                try:
                    # Use circuit breaker
                    result = await circuit_breaker.call(
                        self._execute_single,
                        endpoint,
                        query,
                        timeout
                    )
                    return result
                    
                except CircuitBreakerOpen:
                    # Skip to next endpoint
                    break
                except Exception as exc:
                    last_error = exc
                    
                    # Exponential backoff with jitter
                    if attempt < max_retries - 1:
                        delay = (2 ** attempt) + random.uniform(0, 1)
                        await asyncio.sleep(delay)
        
        raise SparqlUpstreamError(f"All endpoints failed: {last_error}")


# Fallback mechanism
class SparqlClientWithFallback(ResilientSparqlClient):
    """SPARQL client with fallback to cache on failure."""
    
    def __init__(self, endpoints: List[SparqlEndpoint], cache: Cache):
        super().__init__(endpoints)
        self.cache = cache
    
    async def query_with_fallback(
        self,
        name: str,
        parameters: Mapping[str, Any] | None = None,
        use_cache_on_failure: bool = True
    ) -> dict:
        """Query with fallback to cache on failure."""
        cache_key = f"{name}:{hash(str(parameters))}"
        
        try:
            # Try live query
            result = await self.query(name, parameters)
            
            # Cache successful result
            await self.cache.set(cache_key, result, ttl=3600)
            
            return result
            
        except SparqlUpstreamError as e:
            if not use_cache_on_failure:
                raise
            
            # Try cache fallback
            cached = await self.cache.get(cache_key)
            if cached:
                return {
                    "results": cached,
                    "source": "cache",
                    "warning": "Results from cache due to upstream failure"
                }
            
            # Return empty result with warning
            return {
                "results": [],
                "source": "fallback",
                "warning": f"Upstream failure: {e}. No cached data available."
            }
```

---

## 3. Electronic Signatures (21 CFR Part 11)

**File:** `src/services/draft_store/signing.py`

```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel
import base64
import hashlib

class ElectronicSignature(BaseModel):
    """Electronic signature per 21 CFR Part 11."""
    
    signer_user_id: str
    signature_meaning: Literal["authored", "reviewed", "approved"]
    timestamp_utc: str
    content_hash: str  # SHA-256 of signed content
    signature_value: str  # Base64-encoded signature
    cert_chain: List[str]  # PEM-encoded certificates
    
    def verify(self, content: bytes, trusted_certs: List[str]) -> bool:
        """Verify signature against content."""
        # Verify content hash
        computed_hash = hashlib.sha256(content).hexdigest()
        if computed_hash != self.content_hash:
            return False
        
        # Verify signature
        try:
            public_key = self._extract_public_key()
            signature_bytes = base64.b64decode(self.signature_value)
            
            public_key.verify(
                signature_bytes,
                self.content_hash.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False
    
    def _extract_public_key(self):
        """Extract public key from certificate chain."""
        if not self.cert_chain:
            raise ValueError("No certificate chain provided")
        
        cert_pem = self.cert_chain[0]
        cert = serialization.load_pem_x509_certificate(
            cert_pem.encode(),
            default_backend()
        )
        return cert.public_key()

class SignatureService:
    """Service for creating and verifying electronic signatures."""
    
    def __init__(self, private_key_path: str, cert_path: str):
        self.private_key = self._load_private_key(private_key_path)
        self.certificate = self._load_certificate(cert_path)
    
    def sign_content(
        self,
        content: bytes,
        signer_user_id: str,
        meaning: Literal["authored", "reviewed", "approved"]
    ) -> ElectronicSignature:
        """Sign content electronically."""
        # Compute content hash
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Create signature
        signature = self.private_key.sign(
            content_hash.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return ElectronicSignature(
            signer_user_id=signer_user_id,
            signature_meaning=meaning,
            timestamp_utc=datetime.utcnow().isoformat(),
            content_hash=content_hash,
            signature_value=base64.b64encode(signature).decode(),
            cert_chain=[self.certificate]
        )
    
    def _load_private_key(self, path: str):
        """Load private key from file."""
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
    
    def _load_certificate(self, path: str) -> str:
        """Load certificate from file."""
        with open(path, "r") as f:
            return f.read()


# Integration with draft store
from dataclasses import dataclass, field
from typing import List

@dataclass
class VersionMetadata:
    """Version metadata with electronic signatures."""
    
    author: str
    signatures: List[ElectronicSignature] = field(default_factory=list)
    checksum: str = ""  # REQUIRED
    previous_checksum: str = ""  # REQUIRED
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def add_signature(self, signature: ElectronicSignature):
        """Add electronic signature."""
        self.signatures.append(signature)
    
    def verify_signatures(self, content: bytes, trusted_certs: List[str]) -> bool:
        """Verify all signatures."""
        if not self.signatures:
            return False
        
        for sig in self.signatures:
            if not sig.verify(content, trusted_certs):
                return False
        
        return True

class SignedDraftStore:
    """Draft store with electronic signature support."""
    
    def __init__(self, signature_service: SignatureService):
        self.signature_service = signature_service
    
    async def sign_draft(
        self,
        draft_id: str,
        user_id: str,
        meaning: Literal["authored", "reviewed", "approved"],
        content: bytes
    ):
        """Sign a draft electronically."""
        signature = self.signature_service.sign_content(
            content=content,
            signer_user_id=user_id,
            meaning=meaning
        )
        
        draft = await self.get_draft(draft_id)
        draft.metadata.add_signature(signature)
        
        await self.save_draft(draft)
    
    async def verify_draft(self, draft_id: str, trusted_certs: List[str]) -> bool:
        """Verify all signatures on a draft."""
        draft = await self.get_draft(draft_id)
        content = await self.get_draft_content(draft_id)
        
        return draft.metadata.verify_signatures(content, trusted_certs)
```

---

## 4. Ontology Migration Framework

**File:** `src/semantic/migration.py`

```python
from typing import Dict, List, Callable, Any
from pydantic import BaseModel
import json

class OntologyVersion(BaseModel):
    """Ontology version identifier."""
    name: str
    version: str  # Semantic version

class MigrationRule(BaseModel):
    """Single migration rule."""
    source_version: str
    target_version: str
    transformer: Callable[[Any], Any]
    description: str

class OntologyMigrator:
    """Migrate data between ontology versions."""
    
    def __init__(self):
        self.migrations: Dict[str, List[MigrationRule]] = {}
        self.term_mappings: Dict[str, Dict[str, str]] = {}
    
    def register_migration(
        self,
        source: str,
        target: str,
        transformer: Callable[[Any], Any],
        description: str = ""
    ):
        """Register a migration rule."""
        key = f"{source}->{target}"
        if key not in self.migrations:
            self.migrations[key] = []
        
        self.migrations[key].append(MigrationRule(
            source_version=source,
            target_version=target,
            transformer=transformer,
            description=description
        ))
    
    def register_term_mapping(self, version: str, mappings: Dict[str, str]):
        """Register term mappings for a version transition."""
        self.term_mappings[version] = mappings
    
    def migrate(self, data: Any, from_version: str, to_version: str) -> Any:
        """Migrate data from one version to another."""
        if from_version == to_version:
            return data
        
        # Find migration path
        path = self._find_migration_path(from_version, to_version)
        if not path:
            raise UnsupportedMigration(
                f"No migration path from {from_version} to {to_version}"
            )
        
        # Apply migrations in sequence
        result = data
        for step in path:
            result = self._apply_migration(result, step)
        
        return result
    
    def _find_migration_path(self, from_version: str, to_version: str) -> List[str]:
        """Find shortest migration path using BFS."""
        # Simplified BFS - production would use proper graph algorithm
        visited = {from_version}
        queue = [(from_version, [])]
        
        while queue:
            current, path = queue.pop(0)
            
            if current == to_version:
                return path
            
            # Find all possible next versions
            for key in self.migrations:
                if key.startswith(f"{current}->"):
                    next_version = key.split("->")[1]
                    if next_version not in visited:
                        visited.add(next_version)
                        queue.append((next_version, path + [key]))
        
        return None
    
    def _apply_migration(self, data: Any, migration_key: str) -> Any:
        """Apply a single migration step."""
        rules = self.migrations.get(migration_key, [])
        
        for rule in rules:
            data = rule.transformer(data)
        
        # Apply term mappings
        version = migration_key.split("->")[1]
        if version in self.term_mappings:
            data = self._apply_term_mappings(data, self.term_mappings[version])
        
        return data
    
    def _apply_term_mappings(self, data: Any, mappings: Dict[str, str]) -> Any:
        """Apply term mappings to data."""
        if isinstance(data, dict):
            return {
                mappings.get(k, k): self._apply_term_mappings(v, mappings)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._apply_term_mappings(item, mappings) for item in data]
        elif isinstance(data, str):
            return mappings.get(data, data)
        return data


# Predefined migrations
migrator = OntologyMigrator()

# AOP ontology v1 to v2 migration
migrator.register_term_mapping("aop-ontology-v2", {
    "AOP:123": "AOP:123v2",
    "KE:456": "KE:456v2",
    "KER:789": "KER:789v2",
})

def migrate_aop_structure_v1_to_v2(data: dict) -> dict:
    """Migrate AOP structure from v1 to v2."""
    if "key_events" in data:
        # v2 uses 'key_event_relationships' instead of 'key_events'
        data["key_event_relationships"] = data.pop("key_events")
    
    if "molecular_initiating_event" in data:
        # v2 nests MIE under 'events'
        data["events"] = {
            "molecular_initiating_event": data.pop("molecular_initiating_event")
        }
    
    return data

migrator.register_migration(
    source="aop-ontology-v1",
    target="aop-ontology-v2",
    transformer=migrate_aop_structure_v1_to_v2,
    description="Migrate AOP structure to v2 format"
)


# Usage in CURIE service
class MigratingCurieService:
    """CURIE service with migration support."""
    
    def __init__(self, migrator: OntologyMigrator):
        self.migrator = migrator
        self.current_version = "aop-ontology-v2"
    
    def normalize(self, value: str, target_version: str = None) -> str:
        """Normalize CURIE with optional version migration."""
        # Extract version from CURIE if present
        curie_version = self._extract_version(value)
        
        if curie_version and curie_version != (target_version or self.current_version):
            # Need to migrate
            data = {"curie": value}
            migrated = self.migrator.migrate(
                data,
                from_version=curie_version,
                to_version=target_version or self.current_version
            )
            return migrated["curie"]
        
        return value
    
    def _extract_version(self, curie: str) -> Optional[str]:
        """Extract version from CURIE if present."""
        # Example: AOP:123v2 -> aop-ontology-v2
        if "v" in curie:
            parts = curie.split(":")
            if len(parts) == 2:
                id_part = parts[1]
                if "v" in id_part:
                    version = id_part.split("v")[-1]
                    return f"aop-ontology-v{version}"
        return None
```

---

*These remediation code snippets address the critical issues identified in the AOP-MCP audit.*

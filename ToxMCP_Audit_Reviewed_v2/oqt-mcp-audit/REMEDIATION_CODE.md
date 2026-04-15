# OQT-MCP: Detailed Remediation Code

> **Reviewed copy note:** Treat these snippets as reference patterns. For LLM-facing contexts, prefer removing control characters **and** newlines from untrusted identifiers unless a well-tested structured representation is used.


## 1. Applicability Domain Index (ADI) Calculation

**File:** `src/tools/implementations/o_qt_qsar_tools.py`

```python
from pydantic import BaseModel
from typing import List, Dict, Tuple
import numpy as np
from rdkit import Chem
from rdkit.Chem import Descriptors, AllChem

class ApplicabilityDomainResult(BaseModel):
    """Quantitative applicability domain assessment."""
    adi_score: float  # 0-1, higher is better
    is_within_domain: bool  # Hard gate
    chemical_class_alerts: List[str]
    training_set_overlap: float  # Tanimoto similarity to nearest neighbor
    domain_boundaries: Dict[str, Tuple[float, float]]
    descriptor_values: Dict[str, float]
    warnings: List[str]

class ADICalculator:
    """Calculate Applicability Domain Index for QSAR predictions."""
    
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.training_set = self.load_training_set(model_id)
        self.domain_boundaries = self.calculate_domain_boundaries()
    
    def calculate_adi(self, smiles: str) -> ApplicabilityDomainResult:
        """Calculate comprehensive ADI for a chemical."""
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return ApplicabilityDomainResult(
                adi_score=0.0,
                is_within_domain=False,
                chemical_class_alerts=["Invalid SMILES"],
                training_set_overlap=0.0,
                domain_boundaries={},
                descriptor_values={},
                warnings=["Cannot parse chemical structure"]
            )
        
        # 1. Calculate molecular descriptors
        descriptors = self.calculate_descriptors(mol)
        
        # 2. Check domain boundaries
        boundary_violations = self.check_boundaries(descriptors)
        
        # 3. Calculate training set similarity
        similarity = self.calculate_training_set_similarity(mol)
        
        # 4. Check chemical class alerts
        alerts = self.check_chemical_class_alerts(mol)
        
        # 5. Calculate overall ADI
        adi_score = self.compute_adi_score(
            descriptors, boundary_violations, similarity, alerts
        )
        
        # 6. Determine if within domain (hard gate)
        is_within_domain = (
            adi_score >= 0.7 and  # Minimum ADI threshold
            similarity >= 0.5 and  # Must have some training set similarity
            len(boundary_violations) <= 2  # Limited boundary violations
        )
        
        return ApplicabilityDomainResult(
            adi_score=adi_score,
            is_within_domain=is_within_domain,
            chemical_class_alerts=alerts,
            training_set_overlap=similarity,
            domain_boundaries=self.domain_boundaries,
            descriptor_values=descriptors,
            warnings=self.generate_warnings(boundary_violations, alerts)
        )
    
    def calculate_descriptors(self, mol: Chem.Mol) -> Dict[str, float]:
        """Calculate key molecular descriptors."""
        return {
            "molecular_weight": Descriptors.MolWt(mol),
            "logp": Descriptors.MolLogP(mol),
            "hbd": Descriptors.NumHDonors(mol),
            "hba": Descriptors.NumHAcceptors(mol),
            "tpsa": Descriptors.TPSA(mol),
            "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
            "aromatic_rings": Descriptors.NumAromaticRings(mol),
            "heavy_atoms": mol.GetNumHeavyAtoms(),
        }
    
    def calculate_domain_boundaries(self) -> Dict[str, Tuple[float, float]]:
        """Calculate domain boundaries from training set."""
        if not self.training_set:
            return {}
        
        boundaries = {}
        for descriptor in ["molecular_weight", "logp", "hbd", "hba", "tpsa"]:
            values = [chem["descriptors"][descriptor] for chem in self.training_set]
            q1, q3 = np.percentile(values, [25, 75])
            iqr = q3 - q1
            # Use IQR method with 1.5x expansion
            boundaries[descriptor] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)
        
        return boundaries
    
    def check_boundaries(self, descriptors: Dict[str, float]) -> List[str]:
        """Check if descriptors are within domain boundaries."""
        violations = []
        for desc, value in descriptors.items():
            if desc in self.domain_boundaries:
                min_val, max_val = self.domain_boundaries[desc]
                if not (min_val <= value <= max_val):
                    violations.append(
                        f"{desc}: {value:.2f} outside [{min_val:.2f}, {max_val:.2f}]"
                    )
        return violations
    
    def calculate_training_set_similarity(self, mol: Chem.Mol) -> float:
        """Calculate Tanimoto similarity to nearest neighbor in training set."""
        if not self.training_set:
            return 0.0
        
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
        max_similarity = 0.0
        
        for train_chem in self.training_set:
            train_fp = train_chem["fingerprint"]
            similarity = DataStructs.TanimotoSimilarity(fp, train_fp)
            max_similarity = max(max_similarity, similarity)
        
        return max_similarity
    
    def check_chemical_class_alerts(self, mol: Chem.Mol) -> List[str]:
        """Check for chemical class-specific alerts."""
        alerts = []
        
        # Check for reactive groups
        if self.has_reactive_group(mol):
            alerts.append("Reactive functional group detected")
        
        # Check for known problematic scaffolds
        if self.has_problematic_scaffold(mol):
            alerts.append("Known problematic scaffold")
        
        # Check for model-specific alerts
        alerts.extend(self.model_specific_alerts(mol))
        
        return alerts
    
    def compute_adi_score(
        self,
        descriptors: Dict[str, float],
        boundary_violations: List[str],
        similarity: float,
        alerts: List[str]
    ) -> float:
        """Compute overall ADI score (0-1)."""
        # Base score from similarity
        score = similarity * 0.4
        
        # Penalty for boundary violations
        violation_penalty = len(boundary_violations) * 0.1
        score -= violation_penalty
        
        # Penalty for alerts
        alert_penalty = len(alerts) * 0.15
        score -= alert_penalty
        
        # Bonus for being well within boundaries
        if len(boundary_violations) == 0:
            score += 0.2
        
        return max(0.0, min(1.0, score))
    
    def generate_warnings(
        self,
        boundary_violations: List[str],
        alerts: List[str]
    ) -> List[str]:
        """Generate human-readable warnings."""
        warnings = []
        
        if boundary_violations:
            warnings.append(f"Descriptor boundary violations: {len(boundary_violations)}")
            warnings.extend(boundary_violations[:3])  # Show first 3
        
        if alerts:
            warnings.append(f"Chemical class alerts: {len(alerts)}")
            warnings.extend(alerts)
        
        return warnings


# Integration with run_qsar_prediction
async def run_qsar_prediction(smiles: str, model_id: str) -> dict:
    """Run QSAR prediction with ADI enforcement."""
    # Calculate ADI
    adi_calculator = ADICalculator(model_id)
    ad_result = adi_calculator.calculate_adi(smiles)
    
    # Hard gate: reject if outside domain
    if not ad_result.is_within_domain:
        return {
            "prediction": None,
            "status": "REJECTED",
            "reason": "Outside applicability domain",
            "ad_result": ad_result.dict(),
            "requires_human_review": True,
            "recommendation": "Consider read-across or experimental testing"
        }
    
    # Fetch prediction from QSAR Toolbox
    prediction = await fetch_prediction_from_toolbox(smiles, model_id)
    
    # Combine with ADI
    return {
        "prediction": prediction,
        "ad_result": ad_result.dict(),
        "confidence": ad_result.adi_score * prediction.get("confidence", 0.5),
        "status": "SUCCESS",
        "requires_human_review": ad_result.adi_score < 0.8  # Review if borderline
    }
```

---

> **Reviewed copy (2026-04-15):** This document was retained from the original package but lightly edited for consistency.  
> Unless explicitly stated otherwise, code blocks are **reference implementations**, not validated patches, and scenario-based exploit narratives should not be read as reproduced proofs.



## 2. Chemical Name Sanitization (Prompt Injection Prevention)

**File:** `src/schemas/workflow_record.py`

```python
import re
import unicodedata
from typing import Optional

class ChemicalNameSanitizer:
    """Sanitize chemical names to prevent prompt injection."""
    
    # Blocked patterns that could be used for prompt injection
    BLOCKED_PATTERNS = [
        r'ignore\s+(previous\s+)?instructions',
        r'override\s+(all\s+)?(safety|guidelines|constraints)',
        r'debug\s+mode',
        r'system\s+(test|prompt|instruction)',
        r'you\s+are\s+now',
        r'new\s+instruction',
        r'forget\s+(previous|everything)',
        r'disregard\s+(all|previous)',
        r'act\s+as\s+(if|though)',
        r'pretend\s+to\s+be',
        r'roleplay\s+as',
    ]
    
    # Maximum allowed length
    MAX_LENGTH = 1000
    
    @classmethod
    def sanitize(cls, name: str, context: str = "general") -> str:
        """
        Sanitize chemical name to prevent prompt injection.
        
        Args:
            name: Raw chemical name input
            context: Context where name will be used ("general", "llm_prompt", "search")
        
        Returns:
            Sanitized chemical name
        
        Raises:
            ValueError: If potentially malicious input detected
        """
        if not name:
            return name
        
        # Check length
        if len(name) > cls.MAX_LENGTH:
            raise ValueError(f"Chemical name exceeds maximum length of {cls.MAX_LENGTH}")
        
        # Normalize Unicode
        normalized = unicodedata.normalize('NFKC', name)
        
        # Remove zero-width and control characters
        sanitized = cls._remove_control_chars(normalized)
        
        # Check for blocked patterns
        cls._check_blocked_patterns(sanitized)
        
        # Context-specific sanitization
        if context == "llm_prompt":
            sanitized = sanitized.replace('\n', ' ').replace('\r', ' ')
            sanitized = cls._sanitize_for_llm(sanitized)
        
        return sanitized.strip()
    
    @classmethod
    def _remove_control_chars(cls, text: str) -> str:
        """Remove control and zero-width characters."""
        # Remove zero-width characters
        zero_width = [
            '\u200B',  # Zero Width Space
            '\u200C',  # Zero Width Non-Joiner
            '\u200D',  # Zero Width Joiner
            '\uFEFF',  # Zero Width No-Break Space
            '\u2060',  # Word Joiner
            '\u180E',  # Mongolian Vowel Separator
        ]
        
        for zw in zero_width:
            text = text.replace(zw, '')
        
        # Remove control characters; if the value is destined for an LLM context, prefer removing newlines too
        cleaned = []
        for char in text:
            cat = unicodedata.category(char)
            if cat.startswith('C') and char not in '\n\t':
                continue
            cleaned.append(char)
        
        return ''.join(cleaned)
    
    @classmethod
    def _check_blocked_patterns(cls, text: str):
        """Check for blocked instruction patterns."""
        text_lower = text.lower()
        
        for pattern in cls.BLOCKED_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                raise ValueError(
                    f"Potentially malicious chemical name detected. "
                    f"Pattern matched: {pattern}"
                )
    
    @classmethod
    def _sanitize_for_llm(cls, text: str) -> str:
        """Additional sanitization for LLM prompts."""
        # Escape special characters that could be interpreted as formatting
        text = text.replace('`', '')  # Remove backticks
        text = text.replace('$', '')  # Remove dollar signs (LaTeX)
        
        # Limit consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
    
    @classmethod
    def validate_smiles(cls, smiles: str) -> bool:
        """Validate SMILES string format."""
        from rdkit import Chem
        
        try:
            mol = Chem.MolFromSmiles(smiles)
            return mol is not None
        except:
            return False


# Usage in workflow processing
from pydantic import validator

class WorkflowInput(BaseModel):
    chemical_name: str
    
    @validator('chemical_name')
    def sanitize_chemical_name(cls, v):
        return ChemicalNameSanitizer.sanitize(v, context="llm_prompt")


class ChemicalSearchParams(BaseModel):
    query: str
    search_type: str = "name"  # Changed from "auto" to safer default
    
    @validator('query')
    def sanitize_query(cls, v):
        return ChemicalNameSanitizer.sanitize(v, context="search")
```

---

## 3. PII Scrubbing for Logs

**File:** `src/tools/registry.py`

```python
import hashlib
import json
import re
from typing import Any, Dict, List, Optional

class PrivacyScrubber:
    """Scrub PII/PSI (Proprietary Substance Information) from logs."""
    
    # Sensitive field patterns
    SENSITIVE_PATTERNS = [
        r'(?i)smiles?',  # Case-insensitive match for "smiles" or "SMILES"
        r'(?i)inchi(key)?',
        r'(?i)cas(_number)?',
        r'(?i)chemical_name',
        r'(?i)preferred_name',
        r'(?i)iupac_name',
        r'(?i)structure',
        r'(?i)molecule',
        r'(?i)compound',
        r'(?i)substance',
        r'(?i)formula',
    ]
    
    # SMILES detection pattern (simplified)
    SMILES_PATTERN = re.compile(r'^[A-Za-z0-9@+\-\[\]\\\(\)=#$:.]+$')
    
    # CAS number pattern
    CAS_PATTERN = re.compile(r'^\d{1,7}\-\d{2}\-\d$')
    
    def __init__(self, salt: Optional[str] = None):
        """
        Initialize scrubber with optional salt for hashing.
        
        Args:
            salt: Salt for hashing (should be consistent across services)
        """
        self.salt = salt or "toxmcp_default_salt"
    
    def scrub(self, data: Any, path: str = "") -> Any:
        """
        Recursively scrub sensitive data.
        
        Args:
            data: Data to scrub
            path: Current path in nested structure (for debugging)
        
        Returns:
            Scrubbed data with sensitive fields hashed
        """
        if isinstance(data, dict):
            return self._scrub_dict(data, path)
        elif isinstance(data, list):
            return [self.scrub(item, f"{path}[]") for item in data]
        elif isinstance(data, str):
            return self._scrub_string(data, path)
        else:
            return data
    
    def _scrub_dict(self, data: Dict, path: str) -> Dict:
        """Scrub dictionary values."""
        scrubbed = {}
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            
            if self._is_sensitive_key(key):
                # Hash the value
                scrubbed[key] = self._hash_value(value)
            else:
                # Recursively scrub
                scrubbed[key] = self.scrub(value, current_path)
        
        return scrubbed
    
    def _scrub_string(self, value: str, path: str) -> str:
        """Scrub string value, detecting embedded sensitive data."""
        # Check if entire string is a SMILES
        if self._is_smiles(value):
            return self._hash_value(value)
        
        # Check if entire string is a CAS number
        if self._is_cas_number(value):
            return self._hash_value(value)
        
        # Check for embedded SMILES in text (more complex)
        # This is a simplified check - production would need more sophisticated detection
        words = value.split()
        scrubbed_words = []
        for word in words:
            if self._is_smiles(word) or self._is_cas_number(word):
                scrubbed_words.append(self._hash_value(word))
            else:
                scrubbed_words.append(word)
        
        return ' '.join(scrubbed_words)
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if key name indicates sensitive data."""
        key_lower = key.lower()
        return any(re.match(pattern, key_lower) for pattern in self.SENSITIVE_PATTERNS)
    
    def _is_smiles(self, value: str) -> bool:
        """Check if value looks like a SMILES string."""
        # Basic heuristic: contains typical SMILES characters and minimum length
        if len(value) < 3:
            return False
        
        # Check for SMILES-specific characters
        smiles_chars = set('CNO[]()=@+-#$.1234567890')
        value_chars = set(value.upper())
        
        # If most characters are SMILES-specific, likely a SMILES
        if len(value_chars - smiles_chars) <= 2:
            return True
        
        return False
    
    def _is_cas_number(self, value: str) -> bool:
        """Check if value is a CAS registry number."""
        return bool(self.CAS_PATTERN.match(value))
    
    def _hash_value(self, value: Any) -> str:
        """Hash a value for logging."""
        if value is None:
            return None
        
        value_str = str(value)
        
        # Create deterministic hash with salt
        hash_input = f"{self.salt}:{value_str}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
        return f"[HASH:{hash_value}]"
    
    def create_correlation_id(self, identifier: str) -> str:
        """
        Create a correlation ID that can link events without revealing the identifier.
        
        This allows debugging across services without exposing sensitive data.
        """
        return self._hash_value(identifier)


# Integration with audit logging
class AuditLogger:
    """Audit logger with built-in PII scrubbing."""
    
    def __init__(self, scrubber: Optional[PrivacyScrubber] = None):
        self.scrubber = scrubber or PrivacyScrubber()
    
    def log_tool_execution(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: Any,
        user_id: str,
        correlation_id: str
    ):
        """Log tool execution with PII scrubbing."""
        scrubbed_params = self.scrubber.scrub(params)
        scrubbed_result = self.scrubber.scrub(result)
        
        event = {
            "type": "tool_execution",
            "tool": tool_name,
            "params": scrubbed_params,
            "result_summary": self._summarize_result(scrubbed_result),
            "user_id": user_id,
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        self._emit(event)
    
    def _summarize_result(self, result: Any) -> Dict:
        """Create a summary of result without sensitive data."""
        if isinstance(result, dict):
            return {
                "status": result.get("status"),
                "has_prediction": "prediction" in result,
                "has_warnings": "warnings" in result and len(result["warnings"]) > 0,
            }
        return {"type": type(result).__name__}


# Usage example
scrubber = PrivacyScrubber(salt="oqt_mcp_production_salt")
audit_logger = AuditLogger(scrubber)

# In tool execution
async def run_qsar_prediction(smiles: str, model_id: str) -> dict:
    correlation_id = scrubber.create_correlation_id(smiles)
    
    try:
        result = await fetch_prediction(smiles, model_id)
        
        audit_logger.log_tool_execution(
            tool_name="run_qsar_prediction",
            params={"smiles": smiles, "model_id": model_id},
            result=result,
            user_id=current_user.id,
            correlation_id=correlation_id
        )
        
        return result
    except Exception as e:
        audit_logger.log_tool_execution(
            tool_name="run_qsar_prediction",
            params={"smiles": smiles, "model_id": model_id},
            result={"error": str(e)},
            user_id=current_user.id,
            correlation_id=correlation_id
        )
        raise
```

---

## 4. Mandatory Scientific Review Mode

**File:** `src/tools/implementations/workflow_runner.py`

```python
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import asyncio

class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class ReviewCheckpoint(BaseModel):
    """A checkpoint requiring human review."""
    checkpoint_id: str
    step: str  # e.g., "chemical_id", "ad_assessment", "final_report"
    status: ReviewStatus
    data: Dict[str, Any]  # Data to review
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[str] = None
    comments: Optional[str] = None
    expires_at: Optional[str] = None

class ReviewOrchestrator:
    """Orchestrate mandatory human review checkpoints."""
    
    REVIEW_TIMEOUT = 3600  # 1 hour timeout for review
    
    def __init__(self):
        self.pending_reviews: Dict[str, ReviewCheckpoint] = {}
        self.review_callbacks: Dict[str, asyncio.Event] = {}
    
    async def create_checkpoint(
        self,
        workflow_id: str,
        step: str,
        data: Dict[str, Any],
        require_approval: bool = True
    ) -> ReviewCheckpoint:
        """Create a review checkpoint and wait for human approval."""
        checkpoint_id = f"{workflow_id}_{step}_{uuid.uuid4().hex[:8]}"
        
        checkpoint = ReviewCheckpoint(
            checkpoint_id=checkpoint_id,
            step=step,
            status=ReviewStatus.PENDING,
            data=data,
            expires_at=(datetime.utcnow() + timedelta(seconds=self.REVIEW_TIMEOUT)).isoformat()
        )
        
        self.pending_reviews[checkpoint_id] = checkpoint
        self.review_callbacks[checkpoint_id] = asyncio.Event()
        
        # Notify reviewers (e.g., via email, Slack, or UI)
        await self.notify_reviewers(checkpoint)
        
        if require_approval:
            # Wait for review with timeout
            try:
                await asyncio.wait_for(
                    self.review_callbacks[checkpoint_id].wait(),
                    timeout=self.REVIEW_TIMEOUT
                )
            except asyncio.TimeoutError:
                checkpoint.status = ReviewStatus.EXPIRED
                raise ReviewTimeout(f"Review checkpoint {checkpoint_id} timed out")
        
        return self.pending_reviews[checkpoint_id]
    
    async def submit_review(
        self,
        checkpoint_id: str,
        reviewer_id: str,
        decision: ReviewStatus,
        comments: Optional[str] = None
    ):
        """Submit a review decision."""
        if checkpoint_id not in self.pending_reviews:
            raise ValueError(f"Unknown checkpoint: {checkpoint_id}")
        
        checkpoint = self.pending_reviews[checkpoint_id]
        
        if checkpoint.status != ReviewStatus.PENDING:
            raise ValueError(f"Checkpoint already reviewed: {checkpoint.status}")
        
        checkpoint.status = decision
        checkpoint.reviewer_id = reviewer_id
        checkpoint.reviewed_at = datetime.utcnow().isoformat()
        checkpoint.comments = comments
        
        # Signal completion
        self.review_callbacks[checkpoint_id].set()
        
        # Audit log
        await self.log_review(checkpoint)
    
    async def notify_reviewers(self, checkpoint: ReviewCheckpoint):
        """Notify available reviewers."""
        # Implementation depends on notification system
        # Could be: email, Slack, WebSocket, etc.
        notification = {
            "type": "review_required",
            "checkpoint_id": checkpoint.checkpoint_id,
            "step": checkpoint.step,
            "workflow_id": checkpoint.checkpoint_id.split("_")[0],
            "data_summary": self.summarize_for_notification(checkpoint.data),
            "review_url": f"/review/{checkpoint.checkpoint_id}"
        }
        
        await send_notification(notification)
    
    def summarize_for_notification(self, data: Dict) -> str:
        """Create human-readable summary for notification."""
        if "chemical_name" in data:
            return f"Chemical: {data['chemical_name']}"
        elif "prediction" in data:
            return f"Prediction: {data['prediction']}"
        return "Review required"


# Integration with workflow runner
class WorkflowRunner:
    def __init__(self):
        self.review_orchestrator = ReviewOrchestrator()
    
    async def run_workflow(self, params: WorkflowParams) -> WorkflowResult:
        """Run workflow with mandatory review checkpoints."""
        workflow_id = str(uuid.uuid4())
        
        # Step 1: Chemical identification
        chemical = await self.identify_chemical(params.identifier)
        
        if params.require_human_review:
            checkpoint = await self.review_orchestrator.create_checkpoint(
                workflow_id=workflow_id,
                step="chemical_id",
                data={
                    "input_identifier": params.identifier,
                    "resolved_chemical": chemical.dict(),
                    "search_type_used": params.search_type
                },
                require_approval=True
            )
            
            if checkpoint.status == ReviewStatus.REJECTED:
                return WorkflowResult(
                    status="REJECTED",
                    reason=f"Chemical identification rejected: {checkpoint.comments}",
                    checkpoint=checkpoint
                )
        
        # Step 2: QSAR predictions
        predictions = await self.run_qsar_predictions(chemical, params.qsar_mode)
        
        # Check for AD warnings
        ad_warnings = [p for p in predictions if not p.ad_result.is_within_domain]
        
        if params.require_human_review and ad_warnings:
            checkpoint = await self.review_orchestrator.create_checkpoint(
                workflow_id=workflow_id,
                step="ad_assessment",
                data={
                    "chemical": chemical.dict(),
                    "ad_warnings": [w.dict() for w in ad_warnings],
                    "predictions": [p.dict() for p in predictions]
                },
                require_approval=True
            )
            
            if checkpoint.status == ReviewStatus.REJECTED:
                return WorkflowResult(
                    status="REJECTED",
                    reason=f"AD assessment rejected: {checkpoint.comments}",
                    checkpoint=checkpoint
                )
        
        # Step 3: Generate report
        report = await self.generate_report(chemical, predictions)
        
        # Final review before PDF generation
        if params.require_human_review:
            checkpoint = await self.review_orchestrator.create_checkpoint(
                workflow_id=workflow_id,
                step="final_report",
                data={
                    "report_preview": report.summary(),
                    "chemical": chemical.dict(),
                    "predictions_count": len(predictions),
                    "warnings_count": len(ad_warnings)
                },
                require_approval=True
            )
            
            if checkpoint.status == ReviewStatus.REJECTED:
                return WorkflowResult(
                    status="REJECTED",
                    reason=f"Final report rejected: {checkpoint.comments}",
                    checkpoint=checkpoint
                )
        
        # Generate final PDF
        pdf = await self.generate_pdf(report)
        
        return WorkflowResult(
            status="SUCCESS",
            workflow_id=workflow_id,
            chemical=chemical,
            predictions=predictions,
            report=report,
            pdf=pdf,
            review_checkpoints=self.review_orchestrator.get_workflow_reviews(workflow_id)
        )
```

---

## 5. Provenance Tables for PDF Generation

**File:** `src/utils/pdf_generator.py`

```python
from datetime import datetime
from typing import Dict, List, Any

class ProvenanceTableGenerator:
    """Generate provenance tables for PDF reports."""
    
    def generate_provenance_section(self, workflow_record: Dict) -> str:
        """Generate complete provenance section for PDF."""
        sections = [
            self._generate_header(),
            self._generate_data_sources_table(workflow_record),
            self._generate_models_table(workflow_record),
            self._generate_applicability_domain_section(workflow_record),
            self._generate_signatures_table(workflow_record),
            self._generate_audit_trail(workflow_record),
        ]
        
        return "\n\n".join(sections)
    
    def _generate_header(self) -> str:
        """Generate section header."""
        return """
## Provenance and Data Quality Information

This section provides complete traceability for the hazard assessment 
contained in this report, including data sources, model versions, and 
applicability domain status.

"""
    
    def _generate_data_sources_table(self, workflow_record: Dict) -> str:
        """Generate data sources table."""
        provenance = workflow_record.get("provenance", {})
        
        table = """
### Data Sources and Versions

| Component | Version | Timestamp | Source |
|-----------|---------|-----------|--------|
"""
        
        # O-QT MCP version
        table += f"| O-QT MCP | {provenance.get('oqt_version', 'N/A')} | {provenance.get('generated_at', 'N/A')} | Internal |\n"
        
        # QSAR Toolbox version
        table += f"| QSAR Toolbox | {provenance.get('toolbox_version', 'N/A')} | {provenance.get('toolbox_timestamp', 'N/A')} | OECD |\n"
        
        # Data snapshot
        table += f"| Data Snapshot | {provenance.get('data_snapshot_id', 'N/A')} | {provenance.get('snapshot_date', 'N/A')} | EPA/OECD |\n"
        
        # API versions
        for api_name, api_info in provenance.get('upstream_apis', {}).items():
            table += f"| {api_name} | {api_info.get('version', 'N/A')} | {api_info.get('called_at', 'N/A')} | External |\n"
        
        return table
    
    def _generate_models_table(self, workflow_record: Dict) -> str:
        """Generate QSAR models table."""
        predictions = workflow_record.get('predictions', [])
        
        table = """
### QSAR Models Used

| Model | Version | Prediction | Confidence | AD Status |
|-------|---------|------------|------------|-----------|
"""
        
        for pred in predictions:
            model = pred.get('model', {})
            ad_result = pred.get('ad_result', {})
            
            model_name = model.get('name', 'Unknown')
            model_version = model.get('version', 'N/A')
            prediction = pred.get('prediction', 'N/A')
            confidence = pred.get('confidence', 'N/A')
            ad_status = "✓ In Domain" if ad_result.get('is_within_domain') else "✗ Outside Domain"
            
            table += f"| {model_name} | {model_version} | {prediction} | {confidence:.2f if isinstance(confidence, float) else confidence} | {ad_status} |\n"
        
        return table
    
    def _generate_applicability_domain_section(self, workflow_record: Dict) -> str:
        """Generate applicability domain warnings section."""
        predictions = workflow_record.get('predictions', [])
        
        # Collect all AD warnings
        all_warnings = []
        for pred in predictions:
            ad_result = pred.get('ad_result', {})
            if not ad_result.get('is_within_domain'):
                warnings = ad_result.get('warnings', [])
                all_warnings.extend(warnings)
        
        if not all_warnings:
            return """
### Applicability Domain Assessment

✓ All predictions are within the applicability domain of their respective models.

"""
        
        section = """
### ⚠️ Applicability Domain Warnings

**WARNING:** The following predictions were made outside the strict applicability domain 
of the QSAR models. These predictions should be treated with caution and may require 
additional experimental validation.

**Warnings:**

"""
        for warning in set(all_warnings):  # Deduplicate
            section += f"- {warning}\n"
        
        section += """
**Recommendations:**
1. Consider read-across from structurally similar compounds with experimental data
2. Conduct in vitro testing for critical endpoints
3. Consult with a QSAR expert before using these predictions for regulatory decisions

"""
        return section
    
    def _generate_signatures_table(self, workflow_record: Dict) -> str:
        """Generate electronic signatures table."""
        signatures = workflow_record.get('signatures', [])
        
        if not signatures:
            return """
### Electronic Signatures

*No electronic signatures have been applied to this report.*

"""
        
        table = """
### Electronic Signatures

| Role | Signer | Date | Meaning | Verification |
|------|--------|------|---------|--------------|
"""
        
        for sig in signatures:
            role = sig.get('role', 'Unknown')
            signer = sig.get('signer_user_id', 'Unknown')
            date = sig.get('timestamp', 'N/A')
            meaning = sig.get('meaning', 'N/A')
            verified = "✓ Verified" if sig.get('verified') else "✗ Failed"
            
            table += f"| {role} | {signer} | {date} | {meaning} | {verified} |\n"
        
        return table
    
    def _generate_audit_trail(self, workflow_record: Dict) -> str:
        """Generate audit trail section."""
        audit_events = workflow_record.get('audit_trail', [])
        
        if not audit_events:
            return """
### Audit Trail

*No audit events recorded.*

"""
        
        section = """
### Audit Trail

| Timestamp | Event | User | Details |
|-----------|-------|------|---------|
"""
        
        for event in audit_events[-10:]:  # Show last 10 events
            timestamp = event.get('timestamp', 'N/A')
            event_type = event.get('type', 'Unknown')
            user = event.get('user_id', 'System')
            details = event.get('details', '')
            
            section += f"| {timestamp} | {event_type} | {user} | {details} |\n"
        
        if len(audit_events) > 10:
            section += f"\n*... and {len(audit_events) - 10} more events*\n"
        
        return section


# Integration with PDF generator
class PDFGenerator:
    def __init__(self):
        self.provenance_generator = ProvenanceTableGenerator()
    
    async def generate_pdf(self, workflow_record: Dict) -> bytes:
        """Generate PDF with complete provenance."""
        # Generate main content
        content = self.generate_main_content(workflow_record)
        
        # Generate provenance section
        provenance = self.provenance_generator.generate_provenance_section(workflow_record)
        
        # Combine
        full_content = f"""
{content}

---

{provenance}

---

## Disclaimer

This report was generated automatically using the O-QT MCP system. 
The predictions contained herein are based on QSAR models and should 
be reviewed by a qualified toxicologist before use in regulatory submissions.

Report ID: {workflow_record.get('workflow_id', 'N/A')}
Generated: {datetime.utcnow().isoformat()}Z
        """
        
        # Convert to PDF (using existing PDF library)
        return await self.render_to_pdf(full_content)
```

---

*These remediation code snippets address the critical issues identified in the OQT-MCP audit.*

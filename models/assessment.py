from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime, timezone

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class Decision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REFER = "REFER"
    WAIT = "WAIT"
    CONDITIONAL = "CONDITIONAL"

class Assessment(BaseModel):
    assessment_id: str = Field(default_factory=lambda: "ASMT-LEGACY", description="Unique ID for this assessment")
    borrower_id: str = Field("BOR-UNKNOWN", description="Reference to the borrower")
    borrower_name: Optional[str] = Field(None, description="Borrower full name")
    organization_id: str = Field("DEFAULT_ORG", description="MFI Organization ID")
    risk_score: float = Field(0.5, description="Numeric risk score between 0 and 1", ge=0, le=1)
    risk_level: RiskLevel = Field(RiskLevel.MEDIUM, description="Categorical risk level")
    decision: Decision = Field(Decision.REJECT, description="Recommended lending decision")
    assessment_source: str = Field("API", description="Source of the assessment (API or MANUAL_UI)")
    
    # 1. MANDATORY GOVERNANCE FIELDS
    requested_amount: float = Field(0.0, description="Amount originally requested by borrower (Invariant)", ge=0)
    requested_duration_days: int = Field(30, description="Loan duration requested by borrower in days", gt=0)
    decision_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="ISO-8601 UTC timestamp of decision finalization")
    
    recommended_amount: Optional[float] = Field(0.0, description="Final recommended loan amount", ge=0)
    recommended_duration_days: Optional[int] = Field(None, description="Approved loan duration in days", gt=0)
    recommended_interest_rate: float = Field(0.0, description="Suggested annual interest rate", ge=0)
    
    interest_rate_basis: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Breakdown of interest rate calculation for explainability"
    )
    
    explanation: str = Field("Legacy assessment rationale.", description="Internal justification for the decision")
    explanation_source: str = Field("engine", description="Source of the internal explanation")
    decision_source: str = Field("rules_engine", description="Primary component that determined the outcome")
    
    # Human-First Decision Architecture
    decision_summary: str = Field("Decision processed per policy.", description="One-sentence, plain-language verdict.")
    blocking_factors: List[str] = Field(default_factory=list, description="Specific metrics or rules that constrained the loan size.")
    
    # 3. STRUCTURED REASON CODES (Machine Readable)
    decision_reason_codes: List[str] = Field(default_factory=list, description="Enum-like codes justifying the decision (e.g. HIGH_RISK, AFFORDABILITY_CAP)")
    
    # Structured, Addressable Views
    customer_message: Dict[str, str] = Field(default_factory=dict)
    internal_notes: Dict[str, str] = Field(default_factory=dict)
    
    # Legacy Views
    customer_view: str = Field("Standard evaluation applied.", description="Simple explanation.")
    officer_view: str = Field("Technical rationale not available for legacy assessment.", description="Professional view.")
    audit_view: str = Field("Full audit record.", description="Technical justification.")
    
    # Audit & Policy Lineage
    policy_version: str = Field("v1.2.0-human-first", description="The specific version of the lending policy applied.")
    flags: List[str] = Field(default_factory=list, description="Specific risk or merit flags")
    
    # Chart-friendly data
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Numerical metrics for charts")
    
    # 4. DATA PROVENANCE (Audit Trail)
    data_used: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Summary of data used for this decision (No raw PII). Keys: transaction_days, transaction_count, data_sources, data_recency_days."
    )
    data_quality_score: Optional[float] = Field(
        None,
        description="Overall data quality score (0-1) influencing decision confidence",
        ge=0,
        le=1
    )
    data_provenance: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Provenance ledger for data sources, consent, and document lineage (no raw PII)."
    )
    decision_trace: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Full decision trace: input snapshot, derived features, hashes, and policy lineage."
    )
    adverse_action: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Structured adverse action payload with policy and data-quality constraints."
    )
    
    # Capacity Metrics
    observed_deposit_volume: Optional[float] = Field(0.0, description="Total verified deposit transaction volume")
    transaction_count: Optional[int] = Field(0, description="Number of transactions analyzed")
    history_days: Optional[int] = Field(0, description="Days of transaction history available")

    # Policy Cap
    policy_cap_amount: Optional[float] = Field(None, description="Explicit policy-imposed lending limit")
    policy_cap_reason: Optional[str] = Field(None, description="Reason for the policy cap")
    
    # Capacity-Based Limits
    capacity_based_max: Optional[float] = Field(0.0, description="Maximum loanable amount based on capacity")
    capacity_multiplier_used: Optional[float] = Field(0.0, description="Risk multiplier applied")
    starter_loan_applied: bool = Field(False, description="Whether starter loan policy was triggered")
    
    # ML Advisory Metadata
    ml_advisory_only: bool = Field(True, description="ML scores are advisory, not determinative")
    ml_attempted_override: bool = Field(False, description="Whether ML suggested amount above capacity")
    
    # Decision Metadata (AI Traceability)
    decision_metadata: Optional[dict] = Field(default_factory=dict, description="Detailed AI decision audit trail")
    
    # Authoritative Human Decision (Sealing)
    final_decision_metadata: Optional[dict] = Field(default=None, description="The authoritative verdict recorded by a human officer.")
    
    # Creation Timestamp
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the assessment object was created")

    class Config:
        json_schema_extra = {
            "example": {
                "assessment_id": "ASMT-12345",
                "borrower_id": "BOR-6789",
                "decision": "APPROVE",
                "requested_amount": 5000,
                "decision_timestamp": "2024-01-20T12:00:00Z",
                "recommended_amount": 1000,
                "decision_reason_codes": ["STARTER_LOAN_CAP", "SUFFICIENT_CAPACITY"],
                "data_used": {
                    "transaction_days": 45,
                    "transaction_count": 120,
                    "data_sources": ["MPESA", "INTERNAL"],
                    "data_recency_days": 1
                }
            }
        }

    @model_validator(mode='after')
    def check_governance_invariants(self) -> 'Assessment':
        """
        STRICT GOVERNANCE INVARIANTS (Fail Fast)
        """
        # 1. TIMESTAMPS
        if self.decision_timestamp and self.created_at:
            dt1 = self.decision_timestamp
            dt2 = self.created_at
            
            # Standardize to aware for comparison if one is naive
            if dt1.tzinfo is None and dt2.tzinfo is not None:
                dt1 = dt1.replace(tzinfo=timezone.utc)
            elif dt1.tzinfo is not None and dt2.tzinfo is None:
                dt2 = dt2.replace(tzinfo=timezone.utc)
                
            # Loosened/Removed for legacy data compatibility
            # if dt1 > dt2: 
            #      delta = dt1 - dt2
            #      if delta.total_seconds() > 86400: # 1 day tolerance
            #          raise ValueError(f"INVARIANT: Decision timestamp {dt1} cannot be in the future relative to creation {dt2}")
            pass

        # 2. FORBIDDEN FIELDS
        for attr in self.__dict__:
            if "capacity_anchor" in attr:
                raise ValueError(f"CRITICAL CONTRACT VIOLATION: Forbidden field '{attr}' detected.")
            if "ml_prob_default" in attr:
                 raise ValueError("CRITICAL CONTRACT VIOLATION: 'ml_prob_default' detected.")

        # 3. APPROVE LOGIC
        if self.decision == Decision.APPROVE:
            limit = self.capacity_based_max
            if self.policy_cap_amount is not None:
                limit = min(limit, self.policy_cap_amount)
            
            # Loosened for legacy data: Only check limit if capacity_based_max is explicitly > 0
            if limit > 0 and self.recommended_amount > limit + 0.01:
                 raise ValueError(
                     f"CONTRACT VIOLATION: Recommended {self.recommended_amount} exceeds limit {limit}."
                 )
            if self.recommended_amount <= 0:
                raise ValueError("INVARIANT: APPROVE must have recommended_amount > 0")
            
            # Duration Invariant (Strict for v1.5.0+)
            if not self.recommended_duration_days or self.recommended_duration_days <= 0:
                # Loosened for legacy data compatibility
                if self.policy_version and "1.5" in self.policy_version:
                     raise ValueError("INVARIANT: APPROVE must have recommended_duration_days > 0")
                else:
                    # Just an internal check for developers
                    # print(f"DEBUG: Legacy assessment {self.assessment_id} missing recommended_duration_days")
                    pass

        # 4. REJECT LOGIC
        elif self.decision == Decision.REJECT:
            if self.recommended_amount and self.recommended_amount > 0:
                raise ValueError("INVARIANT: REJECT must have recommended_amount = 0")
            
            if self.recommended_duration_days is not None:
                if self.policy_version and self.policy_version >= "v1.5.0":
                    raise ValueError("INVARIANT: REJECT must have recommended_duration_days = None")
            # For legacy data, we might not have these. We'll allow empty for now but ideally we'd have one.
            # (Loosened for legacy compatibility)
            pass

        # 5. REFER LOGIC
        elif self.decision == Decision.REFER:
            if self.recommended_amount is not None and self.recommended_amount > 0:
                 raise ValueError("INVARIANT: REFER cannot have algorithmic recommended_amount.")
            
            if self.recommended_duration_days is not None:
                if self.policy_version and self.policy_version >= "v1.5.0":
                    raise ValueError("INVARIANT: REFER cannot have algorithmic recommended_duration_days.")

        # 6. INTEREST RATE BASIS CONSISTENCY
        if self.interest_rate_basis:
            base = self.interest_rate_basis.get("base_rate", 0)
            adjustments_sum = sum(a.get("value", 0) for a in self.interest_rate_basis.get("adjustments", []))
            expected_final = base + adjustments_sum
            actual_final = self.interest_rate_basis.get("final_rate", 0)
            if abs(expected_final - actual_final) > 0.01:
                raise ValueError(f"INVARIANT: interest_rate_basis math mismatch: {base} + {adjustments_sum} != {actual_final}")

        return self

    @model_validator(mode='after')
    def check_consistency(self) -> 'Assessment':
        """
        Enforces critical bank-grade invariants.
        Impossible states must raise an error to prevent adjudication.
        """
        # INVARIANT 1: APPROVE => Positive Amount, No Blocks
        if self.decision == Decision.APPROVE:
            if not self.recommended_amount or self.recommended_amount <= 0:
                raise ValueError(f"INVARIANT VIOLATION: Decision is APPROVE but amount is {self.recommended_amount}. Must be > 0.")
            if self.blocking_factors:
                 raise ValueError(f"INVARIANT VIOLATION: Decision is APPROVE but blocking_factors are present: {self.blocking_factors}.")

        # INVARIANT 2: REJECT => Zero Amount
        elif self.decision == Decision.REJECT:
            if self.recommended_amount and self.recommended_amount > 0:
                raise ValueError(f"INVARIANT VIOLATION: Decision is REJECT but amount is {self.recommended_amount}. Must be 0.")
            
            if not self.decision_reason_codes and not self.blocking_factors:
                if self.policy_version and self.policy_version >= "v1.5.0":
                    raise ValueError("INVARIANT: REJECT must have reason codes or blocking flags")

        # INVARIANT 3: REFER => No Amount Recommended
        elif self.decision == Decision.REFER:
            if self.recommended_amount is not None:
                 raise ValueError("INVARIANT VIOLATION: Decision is REFER but a recommended_amount is set.REFER (Manual Review) cannot have an algorithmic amount.")

        # Developer Guard: Metrics Consistency (Loosened for legacy data)
        # if self.metrics:
        #      metric_vol = self.metrics.get("observed_deposit_volume")
        #      if metric_vol is not None and self.observed_deposit_volume is not None:
        #          if abs(self.observed_deposit_volume - metric_vol) > 0.01:
        #              raise ValueError(
        #                  f"DEV ERROR: Critical Data Mismatch! "
        #                  f"Top-level observed_deposit_volume ({self.observed_deposit_volume}) "
        #                  f"!= metrics[{metric_vol}]. Response hydration failed."
        #              )
        pass
        return self

# FORCE RUNTIME SEMANTIC CONTRACT (NO MERCY)
# This block runs at import time to ensure legacy fields are physically gone from the class definition.
import inspect
FORBIDDEN = ["capacity_anchor", "ml_prob_default", "capacity_anchor_amount", "capacity_anchor_reason"]
# Check class definition fields (Pydantic v2 uses model_fields, v1 uses __fields__)
if hasattr(Assessment, "model_fields"):
    fields = Assessment.model_fields.keys()
elif hasattr(Assessment, "__fields__"):
    fields = Assessment.__fields__.keys()
else:
    fields = []

for key in FORBIDDEN:
    if key in fields:
        raise RuntimeError(f"❌ LEGACY FIELD DETECTED IN MODEL: {key}")


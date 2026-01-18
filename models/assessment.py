from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class Decision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CONDITIONAL = "CONDITIONAL"
    WAIT = "WAIT"

class Assessment(BaseModel):
    assessment_id: str = Field(default_factory=lambda: "ASMT-LEGACY", description="Unique ID for this assessment")
    borrower_id: str = Field("BOR-UNKNOWN", description="Reference to the borrower")
    organization_id: str = Field("DEFAULT_ORG", description="MFI Organization ID")
    risk_score: float = Field(0.5, description="Numeric risk score between 0 and 1", ge=0, le=1)
    risk_level: RiskLevel = Field(RiskLevel.MEDIUM, description="Categorical risk level")
    decision: Decision = Field(Decision.REJECT, description="Recommended lending decision")
    recommended_amount: float = Field(0.0, description="Final recommended loan amount", ge=0)
    recommended_interest_rate: float = Field(0.0, description="Suggested annual interest rate", ge=0)
    requested_amount: float = Field(0.0, description="Amount originally requested by borrower", ge=0)
    explanation: str = Field("Legacy assessment rationale.", description="Internal justification for the decision")
    explanation_source: str = Field("engine", description="Source of the internal explanation")
    decision_source: str = Field("rules_engine", description="Primary component that determined the outcome")
    
    # Human-First Decision Architecture
    decision_summary: str = Field("Decision processed per policy.", description="One-sentence, plain-language verdict.")
    blocking_factors: List[str] = Field(default_factory=list, description="Specific metrics or rules that constrained the loan size.")
    
    # Structured, Addressable Views (Default to empty dict for legacy data)
    customer_message: Dict[str, str] = Field(default_factory=dict)
    internal_notes: Dict[str, str] = Field(default_factory=dict)
    
    # Legacy Views (Optional for backward compatibility)
    customer_view: str = Field("Standard evaluation applied.", description="Simple explanation.")
    officer_view: str = Field("Technical rationale not available for legacy assessment.", description="Professional view.")
    audit_view: str = Field("Full audit record starting from v1.2.", description="Technical justification.")
    
    # Audit & Policy Lineage
    policy_version: str = Field("v1.2.0-human-first", description="The specific version of the lending policy applied.")
    flags: List[str] = Field(default_factory=list, description="Specific risk or merit flags")
    
    # Chart-friendly data
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Numerical metrics for charts (e.g., DTI ratio)")
    
    # ====================================================================
    # CAPACITY DECISION METRICS (Bank-Grade Audit Trail)
    # ====================================================================
    # These fields enable regulatory compliance and explanation validation
    
    # Demonstrated Financial Activity
    observed_deposit_volume: Optional[float] = Field(0.0, description="Total verified deposit transaction volume within observation window")
    transaction_count: Optional[int] = Field(0, description="Number of transactions analyzed")
    history_days: Optional[int] = Field(0, description="Days of transaction history available")

    # Capacity Anchor (Regulatory Requirement)
    capacity_anchor_amount: Optional[float] = Field(0.0, description="The maximum loan amount permitted by policy anchors")
    capacity_anchor_reason: Optional[str] = Field("POLICY_DEFAULT", description="The specific policy justification for the anchor amount")
    
    # Capacity-Based Limits
    capacity_based_max: Optional[float] = Field(0.0, description="Maximum loanable amount based on capacity")
    capacity_multiplier_used: Optional[float] = Field(0.0, description="Risk multiplier applied (1x/2x/4x)")
    starter_loan_applied: bool = Field(False, description="Whether starter loan policy was triggered")
    
    # ML Advisory Metadata
    ml_advisory_only: bool = Field(True, description="ML scores are advisory, not determinative")
    ml_attempted_override: bool = Field(False, description="Whether ML suggested amount above capacity")
    
    # Decision Metadata (for audit trail)
    decision_metadata: Optional[dict] = Field(default_factory=dict, description="Detailed decision audit trail")
    
    # Timestamp for analytics
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When the assessment was created")

    class Config:
        json_schema_extra = {
            "example": {
                "assessment_id": "ASMT-12345",
                "borrower_id": "BOR-6789",
                "risk_score": 0.25,
                "risk_level": "LOW",
                "decision": "CONDITIONAL",
                "recommended_amount": 1000,
                "recommended_interest_rate": 18.5,
                "requested_amount": 5000,
                "decision_summary": "Approved for a starter loan with capped amount to help establish history.",
                "blocking_factors": ["LIMITED_TRANSACTION_HISTORY", "STARTER_CREDIT_CAP"],
                "customer_view": "Welcome! We've approved you for a starter loan of $1,000 to help you build your record with us.",
                "officer_view": "Conditional approval. Capped by Micro-Starter policy ($1k). High risk due to 45-day history.",
                "audit_view": "DECISION_POLICY: MICRO_STARTER; CAPACITY_ANCHOR: 1000.0; OBSERVED_DEPOSIT_VOLUME: 450.0; REASON: STARTER_LOAN_CAP.",
                "explanation": "Applicant approved for conditional entry-level credit...",
                "explanation_source": "engine",
                "observed_deposit_volume": 450.50,
                "deposit_transaction_count": 8,
                "observation_window_days": 30,
                "capacity_based_max": 1000.0,
                "capacity_anchor_amount": 1000.0,
                "capacity_anchor_reason": "MICRO_STARTER_POLICY",
                "policy_version": "v1.2.0-human-first",
                "decision_metadata": {
                    "requested_amount": 5000,
                    "capacity_based_max": 1000,
                    "adjustments_applied": [{"type": "CAPACITY_CAP", "reason": "Policy Cap"}]
                }
            }
        }

    @model_validator(mode='after')
    def check_consistency(self) -> 'Assessment':
        """
        Developer Guard: Ensures top-level fields match the metrics dictionary.
        Prevents 'silent zeroing' of critical capacity data.
        """
        if self.metrics:
             # Deposit Volume Guard
             metric_vol = self.metrics.get("observed_deposit_volume")
             if metric_vol is not None and self.observed_deposit_volume is not None:
                 if abs(self.observed_deposit_volume - metric_vol) > 0.01:
                     raise ValueError(
                         f"DEV ERROR: Critical Data Mismatch! "
                         f"Top-level observed_deposit_volume ({self.observed_deposit_volume}) "
                         f"!= metrics[{metric_vol}]. Response hydration failed."
                     )
        return self

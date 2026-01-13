from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class Decision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CONDITIONAL = "CONDITIONAL"

class Assessment(BaseModel):
    assessment_id: str = Field(..., description="Unique ID for this assessment")
    borrower_id: str = Field(..., description="Reference to the borrower")
    organization_id: str = Field("DEFAULT_ORG", description="MFI Organization ID")
    risk_score: float = Field(..., description="Numeric risk score between 0 and 1", ge=0, le=1)
    risk_level: RiskLevel = Field(..., description="Categorical risk level")
    decision: Decision = Field(..., description="Recommended lending decision")
    recommended_amount: float = Field(..., description="Final recommended loan amount", ge=0)
    recommended_interest_rate: float = Field(..., description="Suggested annual interest rate", ge=0)
    requested_amount: float = Field(..., description="Amount originally requested by borrower", ge=0)
    explanation: str = Field(..., description="Human-readable justification for the decision")
    explanation_source: str = Field("engine", description="Source of the explanation (engine or vertex_ai)")
    decision_source: str = Field("rules_engine", description="Source of the decision logic")
    flags: List[str] = Field(default_factory=list, description="Specific risk or merit flags")
    
    # Chart-friendly data
    metrics: dict = Field(default_factory=dict, description="Numerical metrics for charts (e.g., DTI ratio)")

    class Config:
        json_schema_extra = {
            "example": {
                "assessment_id": "ASMT-12345",
                "borrower_id": "BOR-6789",
                "risk_score": 0.25,
                "risk_level": "LOW",
                "decision": "APPROVE",
                "recommended_amount": 15000,
                "recommended_interest_rate": 12.5,
                "explanation": "Borrower has strong income-to-expense ratio and stable employment.",
                "flags": ["STABLE_INCOME", "LOW_DEBT"],
                "metrics": {
                    "debt_to_income": 0.1,
                    "affordability_ratio": 0.6
                }
            }
        }

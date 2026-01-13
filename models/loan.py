from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime

class LoanStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAID = "PAID"
    DEFAULTED = "DEFAULTED"

class Loan(BaseModel):
    loan_id: str = Field(..., description="Unique Identifier for the loan")
    assessment_id: str = Field(..., description="Reference to the assessment that led to this loan")
    borrower_id: str = Field(..., description="Reference to the borrower")
    organization_id: str = Field("DEFAULT_ORG", description="MFI Organization ID")
    amount: float = Field(..., description="Disbursed amount")
    interest_rate: float = Field(..., description="Annual interest rate applied")
    status: LoanStatus = Field(LoanStatus.ACTIVE, description="Current status of the loan")
    disbursed_at: datetime = Field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None

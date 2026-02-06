from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime

class LoanStatus(str, Enum):
    PENDING_DISBURSEMENT = "PENDING_DISBURSEMENT"
    DISBURSED = "DISBURSED"
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
    status: LoanStatus = Field(LoanStatus.PENDING_DISBURSEMENT, description="Current status of the loan")
    disbursed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Disbursement Details
    disbursement_method: Optional[str] = Field(None, description="e.g., BANK_TRANSFER, CASH, MOBILE_MONEY")
    disbursement_reference: Optional[str] = Field(None, description="Transaction ID or receipt number")
    disbursed_by: Optional[str] = Field(None, description="Email or ID of the officer who confirmed disbursement")
    created_at: datetime = Field(default_factory=datetime.now)

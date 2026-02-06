from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class EmploymentType(str, Enum):
    SALARIED = "salaried"
    TRADER = "trader"
    FARMER = "farmer"
    GIG = "gig"
    SELF_EMPLOYED = "self_employed"

class IDType(str, Enum):
    NRC = "NRC"
    PASSPORT = "PASSPORT"
    UNKNOWN = "UNKNOWN"

class IDReviewStatus(str, Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class Borrower(BaseModel):
    id: Optional[str] = Field(None, description="Unique identifier for the borrower")
    organization_id: str = Field("DEFAULT_ORG", description="ID of the MFI this borrower belongs to")
    name: str = Field(..., description="Full name of the borrower")
    phone: str = Field(..., description="Phone number for contact/verification")
    employment_type: EmploymentType = Field(..., description="Type of employment")
    monthly_income: float = Field(..., description="Average monthly income in local currency", ge=0)
    monthly_expenses: float = Field(..., description="Average monthly expenses", ge=0)
    existing_debt: float = Field(0.0, description="Total current outstanding debt", ge=0)
    loan_amount_requested: float = Field(..., description="Requested loan amount", gt=0)
    loan_purpose: str = Field(..., description="Reason for the loan")
    
    # ID Document Fields (Optional, Supporting Risk Signal Only)
    national_id: Optional[str] = Field(None, description="Encrypted national ID (NRC) or passport number")
    id_provided: bool = Field(False, description="Whether an ID was provided")
    id_type: IDType = Field(IDType.UNKNOWN, description="Type of ID: NRC, PASSPORT, or UNKNOWN")
    id_review_status: IDReviewStatus = Field(IDReviewStatus.NOT_REVIEWED, description="Review status of the ID")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Jane Doe",
                "phone": "+254700000000",
                "employment_type": "trader",
                "monthly_income": 50000,
                "monthly_expenses": 20000,
                "existing_debt": 5000,
                "loan_amount_requested": 15000,
                "loan_purpose": "Business stock expansion"
            }
        }

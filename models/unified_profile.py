"""
UnifiedFinancialProfile: The ONLY input allowed into the assessment engine.

This model enforces:
1. Explicit null handling (no zero-fills for missing data)
2. Clear data provenance (which document provided what)
3. Assessment readiness gating
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"           # Data extracted with high confidence
    UNVERIFIED = "UNVERIFIED"       # Data not available or low confidence
    PARTIAL = "PARTIAL"             # Some data available but incomplete


class DocumentPresence(str, Enum):
    PRESENT_COMPLETE = "PRESENT_COMPLETE"    # Document provided and fully extracted
    PRESENT_INCOMPLETE = "PRESENT_INCOMPLETE" # Document provided but extraction failed
    MISSING = "MISSING"                       # Document not provided


class IdentityProfile(BaseModel):
    """
    Identity information merged from multiple documents.
    """
    full_name: Optional[str] = Field(None, description="Name from payslip or bank statement")
    full_name_source: Optional[str] = Field(None, description="Source document for name")
    
    employer_name: Optional[str] = Field(None, description="Employer from payslip")
    
    bank_name: Optional[str] = Field(None, description="Bank from bank statement")
    account_holder_name: Optional[str] = Field(None, description="Account holder from bank statement")
    
    id_number: Optional[str] = Field(None, description="National ID number if provided")
    
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class IncomeProfile(BaseModel):
    """
    Income information from payslip.
    CRITICAL: Never zero-fill - missing income must be explicit null.
    """
    gross_pay: Optional[float] = Field(None, description="Gross pay from payslip")
    net_pay: Optional[float] = Field(None, description="Net pay from payslip")
    deductions: Optional[float] = Field(None, description="Total deductions from payslip")
    
    pay_frequency: Optional[str] = Field(None, description="MONTHLY, WEEKLY, BIWEEKLY")
    pay_period_start: Optional[str] = Field(None, description="Start of pay period")
    pay_period_end: Optional[str] = Field(None, description="End of pay period")
    
    currency: Optional[str] = Field(None, description="Currency of income")
    
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    
    @property
    def verified_monthly_income(self) -> Optional[float]:
        """
        Returns verified monthly income, or None if not verifiable.
        """
        if self.net_pay is None:
            return None
        if self.pay_frequency == "WEEKLY":
            return self.net_pay * 4.33
        if self.pay_frequency == "BIWEEKLY":
            return self.net_pay * 2.17
        return self.net_pay  # Assume monthly


class BankingBehaviorProfile(BaseModel):
    """
    Banking behavior from bank statement.
    """
    # Balance Information
    opening_balance: Optional[float] = Field(None, description="Opening balance from statement")
    closing_balance: Optional[float] = Field(None, description="Closing balance from statement")
    
    # Transaction Totals
    total_money_in: Optional[float] = Field(None, description="Total credits/deposits")
    total_money_out: Optional[float] = Field(None, description="Total debits/withdrawals")
    
    # Transaction Metrics
    transaction_count: int = Field(0, description="Number of transactions extracted")
    history_days: int = Field(0, description="Days of transaction history available")
    
    # Statement Period
    statement_period_start: Optional[str] = Field(None, description="Start of statement period")
    statement_period_end: Optional[str] = Field(None, description="End of statement period")
    
    currency: Optional[str] = Field(None, description="Currency of bank statement")
    
    # Salary Detection
    salary_detected: bool = Field(False, description="Whether salary deposits were detected")
    salary_confidence: float = Field(0.0, ge=0.0, le=1.0)
    
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class DocumentCoverage(BaseModel):
    """
    Tracks which documents are present and their extraction status.
    """
    bank_statement: DocumentPresence = DocumentPresence.MISSING
    bank_statement_confidence: float = Field(0.0, ge=0.0, le=1.0)
    
    payslip: DocumentPresence = DocumentPresence.MISSING
    payslip_confidence: float = Field(0.0, ge=0.0, le=1.0)
    
    nrc_id: DocumentPresence = DocumentPresence.MISSING
    nrc_confidence: float = Field(0.0, ge=0.0, le=1.0)
    
    @property
    def missing_required_documents(self) -> List[str]:
        """Returns list of missing required documents."""
        missing = []
        if self.bank_statement == DocumentPresence.MISSING:
            missing.append("bank_statement")
        if self.payslip == DocumentPresence.MISSING:
            missing.append("payslip")
        return missing
    
    @property
    def incomplete_documents(self) -> List[str]:
        """Returns list of documents that were provided but couldn't be fully extracted."""
        incomplete = []
        if self.bank_statement == DocumentPresence.PRESENT_INCOMPLETE:
            incomplete.append("bank_statement")
        if self.payslip == DocumentPresence.PRESENT_INCOMPLETE:
            incomplete.append("payslip")
        return incomplete


class AssessmentReadiness(str, Enum):
    READY = "READY"               # All required data available - proceed with assessment
    BLOCKED = "BLOCKED"           # Missing critical data - cannot assess
    PARTIAL = "PARTIAL"           # Some data missing but can provide limited assessment


class UnifiedFinancialProfile(BaseModel):
    """
    The ONLY input allowed into the assessment engine.
    
    This model merges data from multiple document types into a single,
    validated profile that the assessment engine can consume.
    
    INVARIANTS:
    - Missing numeric fields are None, NEVER 0
    - Assessment readiness must be checked before scoring
    - Document provenance is tracked for audit
    """
    # Core Profile Components
    identity: IdentityProfile = Field(default_factory=IdentityProfile)
    income: IncomeProfile = Field(default_factory=IncomeProfile)
    banking_behavior: BankingBehaviorProfile = Field(default_factory=BankingBehaviorProfile)
    document_coverage: DocumentCoverage = Field(default_factory=DocumentCoverage)
    
    # Assessment Gating
    assessment_readiness: AssessmentReadiness = AssessmentReadiness.BLOCKED
    blocking_reasons: List[str] = Field(default_factory=list)
    
    # Metadata
    profile_created_at: datetime = Field(default_factory=datetime.utcnow)
    source_documents: List[str] = Field(default_factory=list, description="List of document types that contributed")
    
    # Raw summaries for UI display (NOT for assessment logic)
    ui_document_summaries: List[Dict[str, Any]] = Field(default_factory=list)
    
    def is_ready_for_assessment(self) -> bool:
        """Check if this profile has sufficient data for assessment."""
        return self.assessment_readiness == AssessmentReadiness.READY
    
    def get_blocking_reasons(self) -> List[str]:
        """Get human-readable reasons why assessment is blocked."""
        return self.blocking_reasons.copy()
    
    class Config:
        json_schema_extra = {
            "example": {
                "identity": {
                    "full_name": "Jane Mwangi",
                    "employer_name": "CANET CONSULTING LTD",
                    "bank_name": "Zanaco",
                    "verification_status": "VERIFIED"
                },
                "income": {
                    "net_pay": 6230.00,
                    "gross_pay": 7450.00,
                    "currency": "ZMW",
                    "verification_status": "VERIFIED"
                },
                "banking_behavior": {
                    "closing_balance": 1623.18,
                    "transaction_count": 45,
                    "history_days": 30
                },
                "assessment_readiness": "READY"
            }
        }

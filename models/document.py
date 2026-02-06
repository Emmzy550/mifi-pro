from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class DocumentType(str, Enum):
    BANK_STATEMENT = "BANK_STATEMENT"
    PAYSLIP = "PAYSLIP"
    MOBILE_MONEY = "MOBILE_MONEY"
    GENERIC_CSV = "GENERIC_CSV"
    NRC_ID = "NRC_ID"
    UNKNOWN = "UNKNOWN"

class Transaction(BaseModel):
    """
    Standardized financial transaction event.
    """
    date: str  # YYYY-MM-DD
    description: str
    amount: float
    credit: Optional[float] = None
    debit: Optional[float] = None
    direction: str # INFLOW / OUTFLOW
    balance: Optional[float] = None
    currency: str = "USD"
    confidence: float = 1.0
    confidence_score: float = 1.0
    confidence_reasons: List[str] = []
    flags: List[str] = []
    metadata: Dict[str, Any] = {}

class NumericRole(str, Enum):
    OPENING_BALANCE = "OPENING_BALANCE"
    CLOSING_BALANCE = "CLOSING_BALANCE"
    RUNNING_BALANCE = "RUNNING_BALANCE"
    TRANSACTION_DEBIT = "TRANSACTION_DEBIT"
    TRANSACTION_CREDIT = "TRANSACTION_CREDIT"
    SUMMARY_TOTAL_IN = "SUMMARY_TOTAL_IN"
    SUMMARY_TOTAL_OUT = "SUMMARY_TOTAL_OUT"
    TIMESTAMP = "TIMESTAMP"
    NON_FINANCIAL_NUMBER = "NON_FINANCIAL_NUMBER"
    UNKNOWN = "UNKNOWN"

class NumericToken(BaseModel):
    raw_text: str
    normalized_value: Optional[float] = None
    currency: Optional[str] = None
    role: NumericRole = NumericRole.UNKNOWN
    confidence: float = 0.0
    metadata: Dict[str, Any] = {}

class SummaryProfile(str, Enum):
    BANK_STATEMENT_SUMMARY = "BANK_STATEMENT_SUMMARY"
    PAYSLIP_SUMMARY = "PAYSLIP_SUMMARY"
    COMBINED_SNAPSHOT = "COMBINED_FINANCIAL_SNAPSHOT"
    NRC_IDENTITY_SUMMARY = "NRC_IDENTITY_SUMMARY"
    UNKNOWN = "UNKNOWN"

class StatementPeriod(BaseModel):
    start: Optional[str] = None # YYYY-MM-DD
    end: Optional[str] = None   # YYYY-MM-DD

class BankStatementSummary(BaseModel):
    """
    Strict Bank Statement Schema.
    No calculated ratios. No zero-fills. explicit values only.
    """
    summary_profile: str = SummaryProfile.BANK_STATEMENT_SUMMARY.value
    currency: Optional[str] = None
    bank_name: Optional[str] = None
    statement_period: Optional[StatementPeriod] = None
    account_holder_name: Optional[str] = None
    
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_money_in: Optional[float] = None
    total_money_out: Optional[float] = None
    deposit_count: Optional[int] = None
    calculated_total_money_in: Optional[float] = None
    calculated_total_money_out: Optional[float] = None
    calculated_opening_balance: Optional[float] = None
    calculated_closing_balance: Optional[float] = None
    
    salary_detected: bool = False
    salary_deposit_detected: bool = False
    salary_frequency: Optional[str] = None
    salary_confidence: Optional[float] = None
    
    document_confidence: float = 0.0
    confidence_reasons: List[str] = []
    risk_flags: List[str] = []

    # Forbidden fields (explicitly omitted)
    # avg_monthly_income, dti_ratio, capacity_max -> MOVED TO CombinedFinancialSnapshot

class PayslipSummary(BaseModel):
    """
    Summary specific to Payslips.
    Focus on income verification and deductions.
    """
    summary_profile: str = SummaryProfile.PAYSLIP_SUMMARY.value
    employee_name: Optional[str] = None
    employer_name: Optional[str] = None
    pay_period_start: Optional[str] = None
    pay_period_end: Optional[str] = None
    pay_date: Optional[str] = None
    gross_pay: Optional[float] = None
    net_pay: Optional[float] = None
    deductions: Optional[float] = None
    currency: Optional[str] = None
    pay_frequency: Optional[str] = None
    
    is_tax_deducted: bool = False
    is_loan_deducted: bool = False
    document_confidence: float = 0.0
    confidence_reasons: List[str] = []
    risk_flags: List[str] = []

class NRCIdentitySummary(BaseModel):
    summary_profile: str = SummaryProfile.NRC_IDENTITY_SUMMARY.value
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    document_readability: Optional[str] = None
    name_confidence: Optional[float] = None
    document_confidence: float = 0.0
    confidence_reasons: List[str] = []
    risk_flags: List[str] = []

class ExtractionResult(BaseModel):
    """
    Container for extraction results.
    """
    document_type: DocumentType
    confidence: float = 0.0
    
    # Common Artifacts
    transactions: List[Transaction] = []
    numeric_tokens: List[NumericToken] = []
    
    # Type-Specific Summaries (Only one should be populated)
    bank_statement_summary: Optional[BankStatementSummary] = None
    payslip_summary: Optional[PayslipSummary] = None
    nrc_summary: Optional[NRCIdentitySummary] = None
    
    # Metadata
    warnings: List[str] = []
    raw_text_preview: Optional[str] = None
    quality_score: Optional[float] = None

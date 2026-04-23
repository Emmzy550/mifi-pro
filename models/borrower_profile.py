from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from models.borrower_communication import (
    BorrowerCommunicationRecord,
    BorrowerContactPreference,
    ReminderScheduleItem,
)
from models.borrower_note import BorrowerNote


class BorrowerStatusBadge(BaseModel):
    label: str
    tone: str = "neutral"


class BorrowerDirectoryItem(BaseModel):
    borrower_id: str
    full_name: str
    phone: Optional[str] = None
    employment_type: Optional[str] = None
    active_loans: int = 0
    past_applications: int = 0
    outstanding_balance: float = 0.0
    latest_risk_level: Optional[str] = None
    latest_tracker_state: Optional[str] = None
    needs_attention: bool = False
    last_activity_at: Optional[datetime] = None
    badges: List[BorrowerStatusBadge] = Field(default_factory=list)


class BorrowerIdentitySummary(BaseModel):
    borrower_id: str
    full_name: str
    national_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    borrower_type: Optional[str] = None
    status_badges: List[BorrowerStatusBadge] = Field(default_factory=list)
    contact_preferences: Optional[BorrowerContactPreference] = None


class BorrowerBiodata(BaseModel):
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    dependants: Optional[int] = None
    employer_or_business_name: Optional[str] = None
    occupation_or_job_title: Optional[str] = None
    monthly_income: Optional[float] = None
    employment_type: Optional[str] = None
    business_type: Optional[str] = None


class BorrowerLoanSummary(BaseModel):
    active_loans: int = 0
    closed_loans: int = 0
    past_applications: int = 0
    total_outstanding_balance: float = 0.0
    total_repaid_historically: float = 0.0
    most_recent_loan_status: Optional[str] = None
    current_arrears_amount: float = 0.0
    current_risk_state: Optional[str] = None


class BorrowerApplicationHistoryItem(BaseModel):
    assessment_id: str
    application_date: Optional[datetime] = None
    product: Optional[str] = None
    requested_amount: Optional[float] = None
    recommended_decision: Optional[str] = None
    final_decision: Optional[str] = None
    status: Optional[str] = None
    officer_name: Optional[str] = None
    risk_level: Optional[str] = None
    requested_duration_days: Optional[int] = None


class BorrowerLoanHistoryItem(BaseModel):
    loan_id: str
    assessment_id: Optional[str] = None
    status: Optional[str] = None
    disbursement_date: Optional[datetime] = None
    maturity_date: Optional[str] = None
    installment_pattern: Optional[str] = None
    repayment_progress: Optional[float] = None
    outstanding_amount: float = 0.0
    delinquency_state: Optional[str] = None
    collection_lane: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None


class BorrowerRepaymentHistoryItem(BaseModel):
    event_id: str
    loan_id: str
    payment_date: Optional[datetime] = None
    amount: float = 0.0
    method: Optional[str] = None
    status: Optional[str] = None
    event_type: Optional[str] = None
    note: Optional[str] = None
    promise_to_pay_date: Optional[str] = None


class BorrowerDocumentItem(BaseModel):
    doc_id: str
    assessment_id: str
    type: str
    file_name: Optional[str] = None
    upload_date: Optional[datetime] = None
    status: str
    provider: Optional[str] = None
    period: Optional[Any] = None
    extracted_summary: Optional[str] = None
    secure_file_url: Optional[str] = None
    confidence: Optional[float] = None


class BorrowerRiskSignal(BaseModel):
    label: str
    severity: str
    detail: Optional[str] = None
    source: Optional[str] = None


class BorrowerProfileOverview(BaseModel):
    identity: BorrowerIdentitySummary
    biodata: BorrowerBiodata
    loan_summary: BorrowerLoanSummary
    applications: List[BorrowerApplicationHistoryItem] = Field(default_factory=list)
    loans: List[BorrowerLoanHistoryItem] = Field(default_factory=list)
    repayments: List[BorrowerRepaymentHistoryItem] = Field(default_factory=list)
    documents: List[BorrowerDocumentItem] = Field(default_factory=list)
    bank_statement_summary: Dict[str, Any] = Field(default_factory=dict)
    payslip_summary: Dict[str, Any] = Field(default_factory=dict)
    risk_flags: List[BorrowerRiskSignal] = Field(default_factory=list)
    notes: List[BorrowerNote] = Field(default_factory=list)
    communications: List[BorrowerCommunicationRecord] = Field(default_factory=list)
    reminder_schedule: List[ReminderScheduleItem] = Field(default_factory=list)

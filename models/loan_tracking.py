from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class RepaymentFrequency(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    MARKET_DAY = "MARKET_DAY"
    SEASONAL = "SEASONAL"


class CollectionChannel(str, Enum):
    MOBILE_MONEY = "MOBILE_MONEY"
    USSD = "USSD"
    BANK_TRANSFER = "BANK_TRANSFER"
    CASH_AGENT = "CASH_AGENT"
    BRANCH_CASH = "BRANCH_CASH"
    PAYROLL_DEDUCTION = "PAYROLL_DEDUCTION"
    CARD = "CARD"
    OTHER = "OTHER"


class IncomeCycle(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    SEASONAL = "SEASONAL"
    MIXED = "MIXED"


class TrackingLane(str, Enum):
    MOBILE_MONEY_FASTLANE = "MOBILE_MONEY_FASTLANE"
    MARKET_DAY_SWEEP = "MARKET_DAY_SWEEP"
    PAYDAY_LOCKSTEP = "PAYDAY_LOCKSTEP"
    HARVEST_BRIDGE = "HARVEST_BRIDGE"
    FIELD_COLLECTION = "FIELD_COLLECTION"


class LoanCollectionEventType(str, Enum):
    PAYMENT = "PAYMENT"
    PROMISE_TO_PAY = "PROMISE_TO_PAY"
    FIELD_VISIT = "FIELD_VISIT"
    MISSED_CONTACT = "MISSED_CONTACT"
    RESTRUCTURE = "RESTRUCTURE"
    NOTE = "NOTE"


class InstallmentStatus(str, Enum):
    UPCOMING = "UPCOMING"
    DUE = "DUE"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    MISSED = "MISSED"


class LoanTrackingProfile(BaseModel):
    currency: str = Field("ZMW", description="Loan currency")
    term_days: int = Field(30, gt=0, description="Approved term in days")
    repayment_frequency: RepaymentFrequency = Field(
        RepaymentFrequency.MONTHLY,
        description="Expected repayment cadence"
    )
    first_due_date: str = Field(..., description="First installment due date (YYYY-MM-DD)")
    grace_period_days: int = Field(
        3,
        ge=0,
        le=60,
        description="Tolerance window before an installment is treated as missed"
    )
    income_cycle: IncomeCycle = Field(
        IncomeCycle.MONTHLY,
        description="Borrower cash-flow rhythm used to judge cadence fit"
    )
    preferred_collection_channel: CollectionChannel = Field(
        CollectionChannel.MOBILE_MONEY,
        description="Primary collection route"
    )
    tracking_lane: TrackingLane = Field(
        TrackingLane.MOBILE_MONEY_FASTLANE,
        description="Collection playbook selected for this loan"
    )
    collection_anchor_day: Optional[str] = Field(
        None,
        description="Human-readable anchor such as payday weekday or market day"
    )
    seasonal_start_month: Optional[int] = Field(None, ge=1, le=12)
    seasonal_end_month: Optional[int] = Field(None, ge=1, le=12)
    community_cycle_label: Optional[str] = Field(
        None,
        description="Optional label for a local collection rhythm or community cycle"
    )
    officer_notes: Optional[str] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Optional[str]) -> str:
        normalized = str(value or "ZMW").strip().upper()
        return normalized or "ZMW"

    @model_validator(mode="after")
    def validate_seasonal_window(self) -> "LoanTrackingProfile":
        if (self.seasonal_start_month is None) ^ (self.seasonal_end_month is None):
            raise ValueError("Seasonal tracking requires both start and end months.")
        return self


class LoanInstallment(BaseModel):
    installment_id: str
    due_date: str = Field(..., description="Installment due date (YYYY-MM-DD)")
    amount_due: float = Field(..., ge=0)
    principal_due: float = Field(..., ge=0)
    interest_due: float = Field(..., ge=0)
    amount_collected: float = Field(0.0, ge=0)
    status: InstallmentStatus = Field(InstallmentStatus.UPCOMING)
    paid_at: Optional[datetime] = None
    payment_references: List[str] = Field(default_factory=list)


class LoanCollectionEvent(BaseModel):
    event_id: str
    loan_id: str
    organization_id: str
    event_type: LoanCollectionEventType
    amount: float = Field(0.0, ge=0)
    currency: str = Field("ZMW")
    channel: Optional[CollectionChannel] = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recorded_by: str
    reference: Optional[str] = None
    note: Optional[str] = None
    promise_date: Optional[str] = Field(None, description="Promised payment date (YYYY-MM-DD)")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_event_currency(cls, value: Optional[str]) -> str:
        normalized = str(value or "ZMW").strip().upper()
        return normalized or "ZMW"


class LoanTrackingSetupRequest(BaseModel):
    currency: Optional[str] = None
    term_days: Optional[int] = Field(None, gt=0)
    repayment_frequency: Optional[RepaymentFrequency] = None
    first_due_date: Optional[str] = None
    grace_period_days: Optional[int] = Field(None, ge=0, le=60)
    income_cycle: Optional[IncomeCycle] = None
    preferred_collection_channel: Optional[CollectionChannel] = None
    collection_anchor_day: Optional[str] = None
    seasonal_start_month: Optional[int] = Field(None, ge=1, le=12)
    seasonal_end_month: Optional[int] = Field(None, ge=1, le=12)
    community_cycle_label: Optional[str] = None
    officer_notes: Optional[str] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_setup_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        return normalized or None

    @model_validator(mode="after")
    def validate_seasonal_window(self) -> "LoanTrackingSetupRequest":
        if (self.seasonal_start_month is None) ^ (self.seasonal_end_month is None):
            raise ValueError("Seasonal tracking requires both start and end months.")
        return self


class LoanTrackingEventCreate(BaseModel):
    event_type: LoanCollectionEventType
    amount: float = Field(0.0, ge=0)
    channel: Optional[CollectionChannel] = None
    occurred_at: Optional[datetime] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    promise_date: Optional[str] = Field(None, description="Promised payment date (YYYY-MM-DD)")
    metadata: Dict[str, Any] = Field(default_factory=dict)

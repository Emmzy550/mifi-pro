
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum

class PaymentGateway(str, Enum):
    LIPILA = "LIPILA"
    BANK_TRANSFER = "BANK_TRANSFER"
    STRIPE = "STRIPE"

class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PROMPT_SENT = "PROMPT_SENT"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


ACTIVE_PAYMENT_STATUSES = {
    PaymentStatus.PENDING,
    PaymentStatus.PROMPT_SENT,
    PaymentStatus.CANCELLING,
}


RESUMABLE_PAYMENT_STATUSES = {
    PaymentStatus.PENDING,
    PaymentStatus.PROMPT_SENT,
}


CANCELLABLE_PAYMENT_STATUSES = {
    PaymentStatus.PENDING,
    PaymentStatus.PROMPT_SENT,
}


TERMINAL_PAYMENT_STATUSES = {
    PaymentStatus.CANCELLED,
    PaymentStatus.SUCCESS,
    PaymentStatus.FAILED,
    PaymentStatus.EXPIRED,
}

class Payment(BaseModel):
    payment_id: str = Field(..., description="Unique Payment/Transaction ID")
    org_id: str = Field(..., description="Organization ID")
    plan: str = Field(..., description="Plan being purchased")
    amount: float = Field(..., description="Amount paid")
    currency: str = Field("USD", description="Currency (USD, ZMW, etc)")
    gateway: PaymentGateway = Field(..., description="Payment Gateway used")
    status: PaymentStatus = Field(PaymentStatus.PENDING, description="Payment lifecycle status")
    
    # Gateway specific
    transaction_id: Optional[str] = Field(None, description="External provider transaction ID")
    phone_number: Optional[str] = Field(None, description="Phone number for MoMo")
    reference_code: Optional[str] = Field(None, description="Unique reference code for Bank Transfer/Invoice")
    invoice_id: Optional[str] = Field(None, description="Invoice ID for accounting")
    invoice_pdf_path: Optional[str] = Field(None, description="Local path to generated PDF invoice")
    
    # Metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict, description="Additional gateway-specific metadata")

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value):
        if isinstance(value, PaymentStatus):
            return value
        normalized = str(value or "").strip().upper()
        aliases = {
            "PAID": PaymentStatus.SUCCESS,
            "COMPLETED": PaymentStatus.SUCCESS,
            "SUCCESS": PaymentStatus.SUCCESS,
            "PENDING": PaymentStatus.PENDING,
            "PROMPT_SENT": PaymentStatus.PROMPT_SENT,
            "CANCELLING": PaymentStatus.CANCELLING,
            "CANCELLED": PaymentStatus.CANCELLED,
            "CANCELED": PaymentStatus.CANCELLED,
            "FAILED": PaymentStatus.FAILED,
            "EXPIRED": PaymentStatus.EXPIRED,
        }
        return aliases.get(normalized, value)

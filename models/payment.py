
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class PaymentGateway(str, Enum):
    LIPILA = "LIPILA"
    BANK_TRANSFER = "BANK_TRANSFER"
    STRIPE = "STRIPE"

class PaymentStatus(str, Enum):
    UNPAID = "UNPAID"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"

class Payment(BaseModel):
    payment_id: str = Field(..., description="Unique Payment/Transaction ID")
    org_id: str = Field(..., description="Organization ID")
    plan: str = Field(..., description="Plan being purchased")
    amount: float = Field(..., description="Amount paid")
    currency: str = Field("USD", description="Currency (USD, ZMW, etc)")
    gateway: PaymentGateway = Field(..., description="Payment Gateway used")
    status: PaymentStatus = Field(PaymentStatus.PENDING, description="Payment status")
    
    # Gateway specific
    transaction_id: Optional[str] = Field(None, description="External provider transaction ID")
    phone_number: Optional[str] = Field(None, description="Phone number for MoMo")
    reference_code: Optional[str] = Field(None, description="Unique reference code for Bank Transfer/Invoice")
    invoice_id: Optional[str] = Field(None, description="Invoice ID for accounting")
    
    # Metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict, description="Additional gateway-specific metadata")

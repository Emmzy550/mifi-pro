from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum

class OrgStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"

class OrgEnvironment(str, Enum):
    SANDBOX = "SANDBOX"
    PRODUCTION = "PRODUCTION"

class BillingPlan(str, Enum):
    SANDBOX = "SANDBOX"
    STARTER = "STARTER"
    GROWTH = "GROWTH"
    ENTERPRISE = "ENTERPRISE"

class BillingStatus(str, Enum):
    FREE = "FREE"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    SUSPENDED = "SUSPENDED"

class PaymentStatus(str, Enum):
    UNPAID = "UNPAID"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"

class Organization(BaseModel):
    id: str = Field(..., description="Unique Organization ID")
    name: str = Field(..., description="Organization Name")
    environment: OrgEnvironment = Field(OrgEnvironment.SANDBOX, description="Environment type")
    status: OrgStatus = Field(OrgStatus.ACTIVE, description="Account status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    webhook_url: Optional[str] = Field(None, description="Webhook endpoint for events")
    webhook_secret: Optional[str] = Field(None, description="Secret for signing webhook payloads")
    feature_flags: dict = Field(default_factory=dict, description="Enabled optional features")
    
    # Billing fields
    plan: BillingPlan = Field(BillingPlan.SANDBOX, description="Current billing plan")
    billing_status: BillingStatus = Field(BillingStatus.FREE, description="Billing account status")
    payment_status: PaymentStatus = Field(PaymentStatus.UNPAID, description="Strict payment status for gatekeeping")
    last_payment_id: Optional[str] = Field(None, description="ID of the most recent payment attempt")
    monthly_limit: Optional[int] = Field(None, description="Custom override for monthly limit (e.g. Enterprise)")
    current_period_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Current billing period start")
    current_period_end: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30), description="Current billing period end")
    
    @field_validator('status', mode='before')
    @classmethod
    def normalize_status(cls, v):
        if isinstance(v, str):
            v_upper = v.upper()
            if v_upper == "ACTIVE": return OrgStatus.ACTIVE
            if v_upper == "SUSPENDED": return OrgStatus.SUSPENDED
        return v

    @field_validator('environment', mode='before')
    @classmethod
    def normalize_env(cls, v):
        if isinstance(v, str):
            v_upper = v.upper()
            if v_upper == "SANDBOX": return OrgEnvironment.SANDBOX
            if v_upper == "PRODUCTION": return OrgEnvironment.PRODUCTION
        return v

    @field_validator('plan', mode='before')
    @classmethod
    def normalize_plan(cls, v):
        if isinstance(v, str):
            v_upper = v.upper()
            # Map common variations
            if "SANDBOX" in v_upper: return BillingPlan.SANDBOX
            if "STARTER" in v_upper: return BillingPlan.STARTER
            if "GROWTH" in v_upper: return BillingPlan.GROWTH
            if "ENTERPRISE" in v_upper: return BillingPlan.ENTERPRISE
        return v
    
    @field_validator('billing_status', mode='before')
    @classmethod
    def normalize_billing_status(cls, v):
        if isinstance(v, str):
            v_upper = v.upper()
            if v_upper == "FREE": return BillingStatus.FREE
            if v_upper == "ACTIVE": return BillingStatus.ACTIVE
            if v_upper == "PAST_DUE": return BillingStatus.PAST_DUE
            if v_upper == "SUSPENDED": return BillingStatus.SUSPENDED
        return v

    @field_validator('payment_status', mode='before')
    @classmethod
    def normalize_payment_status(cls, v):
        if isinstance(v, str):
            v_upper = v.upper()
            if v_upper == "UNPAID": return PaymentStatus.UNPAID
            if v_upper == "PENDING": return PaymentStatus.PENDING
            if v_upper == "PAID": return PaymentStatus.PAID
            if v_upper == "FAILED": return PaymentStatus.FAILED
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "id": "ORG-123",
                "name": "Acme Microfinance",
                "environment": "PRODUCTION",
                "status": "ACTIVE",
                "plan_name": "starter",
                "monthly_limit": 5000,
                "unit_cost": 0.05,
                "usage_count": 243,
                "billing_status": "active"
            }
        }

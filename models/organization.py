from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime, timedelta, timezone

class OrgStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"

class OrgEnvironment(str, Enum):
    SANDBOX = "SANDBOX"
    PRODUCTION = "PRODUCTION"

class BillingStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"

class BillingPlan(str, Enum):
    SANDBOX = "sandbox"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

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
    plan_name: BillingPlan = Field(BillingPlan.SANDBOX, description="Current billing plan")
    monthly_limit: int = Field(10, description="Maximum assessments allowed per billing cycle")
    unit_cost: float = Field(0.00, description="Cost per assessment in USD")
    usage_count: int = Field(0, description="Number of assessments used in current billing cycle")
    billing_cycle_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Start of current billing cycle")
    billing_cycle_end: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30), description="End of current billing cycle")
    billing_status: BillingStatus = Field(BillingStatus.ACTIVE, description="Billing account status")
    
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

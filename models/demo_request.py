from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DemoRequestIntent(str, Enum):
    DEMO = "demo"
    TRIAL = "trial"
    PILOT = "pilot"
    CONTACT = "contact"


class DemoRequestStatus(str, Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    CLOSED = "CLOSED"


class DemoRequestCreate(BaseModel):
    intent: DemoRequestIntent = Field(DemoRequestIntent.DEMO, description="Lead intent from the landing page")
    name: str = Field(..., min_length=2, max_length=120, description="Full name of the person requesting contact")
    institution: str = Field(..., min_length=2, max_length=160, description="Institution name")
    phone: str = Field(..., min_length=6, max_length=40, description="WhatsApp or phone number")
    institution_type: Optional[str] = Field(None, max_length=80, description="Institution type")
    volume: Optional[str] = Field(None, max_length=60, description="Loan volume band")


class DemoRequest(BaseModel):
    request_id: str = Field(..., description="Unique request identifier")
    intent: DemoRequestIntent = Field(DemoRequestIntent.DEMO, description="Lead intent from the landing page")
    name: str = Field(..., min_length=2, max_length=120, description="Full name of the person requesting contact")
    institution: str = Field(..., min_length=2, max_length=160, description="Institution name")
    phone: str = Field(..., min_length=6, max_length=40, description="WhatsApp or phone number")
    institution_type: Optional[str] = Field(None, max_length=80, description="Institution type")
    volume: Optional[str] = Field(None, max_length=60, description="Loan volume band")
    status: DemoRequestStatus = Field(DemoRequestStatus.NEW, description="Current follow-up status")
    source: str = Field("landing_page", description="Submission source")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Submission timestamp")

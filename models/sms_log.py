from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional

class SMSLog(BaseModel):
    """
    Immutable record of an SMS sent to a borrower.
    """
    id: str = Field(..., description="Unique ID for the SMS log")
    assessment_id: str = Field(..., description="Reference assessment")
    borrower_id: str = Field(..., description="Reference borrower")
    phone_number: str = Field(..., description="Recipient phone number")
    message: str = Field(..., description="Verbatim message content")
    sent_by: str = Field(..., description="User ID of the officer who sent it")
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str = Field("Twilio", description="SMS service provider used")
    provider_id: Optional[str] = Field(None, description="External provider transaction ID")
    status: str = Field(..., description="SENT or FAILED")
    environment: str = Field("sandbox", description="sandbox or production")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "SMS-20240124-ABC",
                "assessment_id": "ASMT-123",
                "borrower_id": "BOR-456",
                "phone_number": "+254700000000",
                "message": "Your loan has been approved.",
                "sent_by": "USR-123",
                "status": "SENT",
                "environment": "sandbox"
            }
        }

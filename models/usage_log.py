from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class UsageLog(BaseModel):
    """
    Tracks billable API usage for audit and billing purposes.
    Each record represents one billable API call (assessment).
    """
    log_id: str = Field(..., description="Unique log identifier")
    org_id: str = Field(..., description="Organization ID that made the request")
    api_key_id: str = Field(..., description="API key used for the request")
    endpoint: str = Field(..., description="API endpoint called (e.g., /assessment/run)")
    units: int = Field(1, description="Billable units (always 1 for assessments)")
    cost: float = Field(..., description="Cost in currency units (units × unit_cost)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When the usage occurred")
    assessment_id: Optional[str] = Field(None, description="Link to the assessment record")
    user_email: Optional[str] = Field(None, description="Email of user who made the request (if JWT)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "log_id": "LOG-A1B2C3D4",
                "org_id": "ORG-123",
                "api_key_id": "loa_live_abc123",
                "endpoint": "/assessment/run",
                "units": 1,
                "cost": 0.05,
                "timestamp": "2026-01-12T09:30:00Z",
                "assessment_id": "ASMT-X1Y2Z3W4"
            }
        }

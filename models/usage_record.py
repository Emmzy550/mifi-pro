from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from .organization import OrgEnvironment

class UsageRecord(BaseModel):
    """
    Tracks assessment counts per organization and environment.
    """
    organization_id: str = Field(..., description="Organization ID")
    environment: OrgEnvironment = Field(..., description="SANDBOX or PRODUCTION")
    assessment_count: int = Field(0, description="Number of assessments performed")
    period_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Start of current usage period")
    period_end: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30), description="End of current usage period")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "organization_id": "ORG-123",
                "environment": "SANDBOX",
                "assessment_count": 5,
                "period_start": "2026-01-01T00:00:00Z",
                "period_end": "2026-02-01T00:00:00Z"
            }
        }

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime, timezone


class FollowUpStatus(str, Enum):
    OPEN = "OPEN"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class FollowUpTask(BaseModel):
    task_id: str = Field(..., description="Unique follow-up task ID")
    assessment_id: str = Field(..., description="Associated assessment ID")
    borrower_id: str = Field(..., description="Borrower ID")
    organization_id: str = Field(..., description="Organization ID")
    note: str = Field(..., description="Officer follow-up note")
    due_date: Optional[str] = Field(None, description="Due date (YYYY-MM-DD)")
    status: FollowUpStatus = Field(FollowUpStatus.OPEN, description="Task status")
    created_by: str = Field(..., description="Creator user id or email")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")

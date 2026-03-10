from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime, timezone


class FollowUpStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_ON_BORROWER = "WAITING_ON_BORROWER"
    WAITING_ON_INTERNAL_REVIEW = "WAITING_ON_INTERNAL_REVIEW"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class FollowUpType(str, Enum):
    DOCUMENT = "DOCUMENT"
    VERIFICATION = "VERIFICATION"
    COMMITTEE = "COMMITTEE"
    COMPLIANCE = "COMPLIANCE"
    DISBURSEMENT = "DISBURSEMENT"
    MONITORING = "MONITORING"
    OTHER = "OTHER"


class FollowUpPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class FollowUpTask(BaseModel):
    task_id: str = Field(..., description="Unique follow-up task ID")
    assessment_id: str = Field(..., description="Associated assessment ID")
    borrower_id: str = Field(..., description="Borrower ID")
    organization_id: str = Field(..., description="Organization ID")
    title: str = Field("Follow-up task", description="Short task title")
    note: str = Field(..., description="Officer follow-up note")
    task_type: FollowUpType = Field(FollowUpType.OTHER, description="Task category")
    reason_code: Optional[str] = Field(None, description="Machine-readable workflow reason code")
    priority: FollowUpPriority = Field(FollowUpPriority.MEDIUM, description="Task urgency")
    due_date: Optional[str] = Field(None, description="Due date (YYYY-MM-DD)")
    status: FollowUpStatus = Field(FollowUpStatus.OPEN, description="Task status")
    is_blocking: bool = Field(False, description="Whether task blocks progression of the case")
    created_by: str = Field(..., description="Creator user id or email")
    created_by_name: Optional[str] = Field(None, description="Creator display name")
    created_by_email: Optional[str] = Field(None, description="Creator email")
    assigned_to_user_id: Optional[str] = Field(None, description="Assigned owner user id")
    assigned_to_user_name: Optional[str] = Field(None, description="Assigned owner name")
    assigned_to_user_email: Optional[str] = Field(None, description="Assigned owner email")
    notify_assignee: bool = Field(False, description="Whether an in-app alert was requested")
    notification_sent_at: Optional[datetime] = Field(None, description="When an in-app notification was created")
    email_notification_status: Optional[str] = Field(None, description="Email delivery status, if attempted")
    email_notification_message: Optional[str] = Field(None, description="Email delivery metadata")
    resolution_note: Optional[str] = Field(None, description="Resolution comment captured on completion/cancel")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    completed_by: Optional[str] = Field(None, description="User id/email that completed the task")
    completed_by_name: Optional[str] = Field(None, description="Display name of completing user")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")

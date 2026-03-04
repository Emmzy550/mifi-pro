from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class Notification(BaseModel):
    notification_id: str = Field(..., description="Unique notification ID")
    organization_id: str = Field(..., description="Organization ID")
    recipient_user_id: str = Field(..., description="User ID that should receive this notification")
    recipient_email: Optional[str] = Field(None, description="Recipient email")
    created_by_user_id: str = Field(..., description="User ID that triggered the notification")
    type: str = Field(..., description="Notification type")
    title: str = Field(..., description="Title shown in UI")
    message: str = Field(..., description="Body shown in UI")
    assessment_id: Optional[str] = Field(None, description="Related assessment, if any")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional extra context")
    is_read: bool = Field(False, description="Read state")
    read_at: Optional[datetime] = Field(None, description="Read timestamp")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")

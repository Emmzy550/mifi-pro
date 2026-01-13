from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

class WebhookEvent(str, Enum):
    ASSESSMENT_COMPLETED = "assessment.completed"
    ASSESSMENT_FAILED = "assessment.failed"
    SYSTEM_ALERT = "system.alert"

class WebhookConfig(BaseModel):
    organization_id: str = Field(..., description="Organization ID")
    url: str = Field(..., description="Destination URL")
    secret: str = Field(..., description="Signing secret")
    events: List[WebhookEvent] = Field(..., description="Subscribed events")
    enabled: bool = Field(True, description="Is webhook active")
    updated_at: datetime = Field(default_factory=datetime.now)

class WebhookLog(BaseModel):
    id: str = Field(..., description="Log ID")
    organization_id: str = Field(..., description="Organization ID")
    event: WebhookEvent = Field(..., description="Event type")
    payload: dict = Field(..., description="Data sent")
    response_code: int = Field(..., description="HTTP status code")
    success: bool = Field(..., description="Delivery status")
    timestamp: datetime = Field(default_factory=datetime.now)

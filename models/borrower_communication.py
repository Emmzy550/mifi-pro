from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ReminderChannel(str, Enum):
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"


class ReminderType(str, Enum):
    UPCOMING_REPAYMENT = "UPCOMING_REPAYMENT"
    DUE_TODAY = "DUE_TODAY"
    MISSED_PAYMENT = "MISSED_PAYMENT"
    PROMISE_TO_PAY_FOLLOW_UP = "PROMISE_TO_PAY_FOLLOW_UP"
    MANUAL = "MANUAL"
    GENERAL_FOLLOW_UP = "GENERAL_FOLLOW_UP"


class CommunicationSenderType(str, Enum):
    SYSTEM = "SYSTEM"
    OFFICER = "OFFICER"


class CommunicationDeliveryStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    MOCKED = "MOCKED"


class CommunicationLanguage(str, Enum):
    ENGLISH = "ENGLISH"
    BEMBA = "BEMBA"
    NYANJA = "NYANJA"
    TONGA = "TONGA"
    LOZI = "LOZI"
    OTHER = "OTHER"


class ReminderScheduleStatus(str, Enum):
    UPCOMING = "UPCOMING"
    DUE = "DUE"
    OVERDUE = "OVERDUE"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class BorrowerContactPreference(BaseModel):
    borrower_id: str
    organization_id: str
    preferred_channel: Optional[ReminderChannel] = None
    preferred_number: Optional[str] = None
    best_contact_time: Optional[str] = None
    communication_language: Optional[CommunicationLanguage] = None
    consent_opt_in: Optional[bool] = None
    updated_by: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BorrowerCommunicationRecord(BaseModel):
    communication_id: str
    organization_id: str
    borrower_id: str
    borrower_name: Optional[str] = None
    assessment_id: Optional[str] = None
    loan_id: Optional[str] = None
    related_promise_date: Optional[str] = None
    reminder_type: ReminderType
    channel: ReminderChannel
    recipient_number: str
    sender_type: CommunicationSenderType = CommunicationSenderType.OFFICER
    automated: bool = False
    template_key: str
    template_version: str = "2026-03"
    message_body: str
    message_preview: str
    delivery_status: CommunicationDeliveryStatus = CommunicationDeliveryStatus.PENDING
    failure_reason: Optional[str] = None
    provider: Optional[str] = None
    provider_message_id: Optional[str] = None
    triggered_by_user_id: Optional[str] = None
    triggered_by_name: Optional[str] = None
    triggered_by_email: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: Optional[datetime] = None


class ReminderScheduleItem(BaseModel):
    schedule_id: str
    borrower_id: str
    organization_id: str
    loan_id: Optional[str] = None
    assessment_id: Optional[str] = None
    reminder_type: ReminderType
    channel: ReminderChannel
    title: str
    description: str
    scheduled_for: datetime
    template_key: str
    status: ReminderScheduleStatus = ReminderScheduleStatus.UPCOMING
    automated: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReminderPreviewRequest(BaseModel):
    reminder_type: ReminderType
    channel: ReminderChannel
    loan_id: Optional[str] = None
    assessment_id: Optional[str] = None
    promise_to_pay_date: Optional[str] = None
    recipient_number: Optional[str] = None


class ReminderSendRequest(ReminderPreviewRequest):
    custom_message: Optional[str] = None
    override_preview: bool = False


class ReminderPreviewResponse(BaseModel):
    borrower_id: str
    loan_id: Optional[str] = None
    assessment_id: Optional[str] = None
    recipient_number: str
    channel: ReminderChannel
    reminder_type: ReminderType
    template_key: str
    template_version: str
    generated_message: str
    placeholders: Dict[str, Any] = Field(default_factory=dict)
    can_edit_message: bool = True

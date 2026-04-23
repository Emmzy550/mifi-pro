from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BorrowerNoteType(str, Enum):
    GENERAL = "GENERAL"
    COLLECTION = "COLLECTION"
    RISK = "RISK"
    DOCUMENT = "DOCUMENT"
    PROMISE_TO_PAY = "PROMISE_TO_PAY"


class BorrowerNote(BaseModel):
    note_id: str
    borrower_id: str
    organization_id: str
    note_type: BorrowerNoteType = BorrowerNoteType.GENERAL
    text: str = Field(..., min_length=1)
    related_loan_id: Optional[str] = None
    related_assessment_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_by_name: Optional[str] = None
    created_by_email: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BorrowerNoteCreate(BaseModel):
    text: str = Field(..., min_length=1)
    note_type: BorrowerNoteType = BorrowerNoteType.GENERAL
    related_loan_id: Optional[str] = None
    related_assessment_id: Optional[str] = None

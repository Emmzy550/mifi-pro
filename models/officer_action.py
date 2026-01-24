from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
from datetime import datetime, timezone

class OfficerDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REFER = "REFER"

class CommChannel(str, Enum):
    NONE = "NONE"
    SMS = "SMS"
    EMAIL = "EMAIL"

class OfficerAction(BaseModel):
    assessment_id: str = Field(..., description="Indexed ID of the assessment")
    officer_id: str = Field(..., description="ID of the officer who made the decision")
    officer_name: str = Field("Unknown Officer", description="Name of the officer for display")
    officer_decision: OfficerDecision = Field(..., description="Final decision made by the officer")
    officer_notes: Optional[str] = Field(None, description="Internal notes for the institution")
    borrower_message: Optional[str] = Field(None, description="Message sent to the borrower")
    communication_channel: CommChannel = Field(CommChannel.NONE, description="Channel used for notification")
    
    # Metadata for transparency & audit
    final_amount: float = Field(..., description="The final amount approved by the officer")
    final_duration_days: int = Field(..., description="The final duration approved by the officer")
    final_interest_rate: float = Field(..., description="The final interest rate approved by the officer")
    is_override: bool = Field(False, description="Whether this decision overrode the AI recommendation")
    ai_recommendation_snapshot: Optional[dict] = Field(None, description="Snapshot of the AI recommendation at the time of decision")
    sealed_at: Optional[str] = Field(None, description="ISO timestamp for legacy frontend support")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of the decision")

    @field_validator('borrower_message')
    @classmethod
    def validate_message_safety(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        
        forbidden = ["guaranteed", "automatic approval", "system approved"]
        lower_v = v.lower()
        for phrase in forbidden:
            if phrase in lower_v:
                raise ValueError(f"Message contains non-compliant phrase: '{phrase}'")
        return v

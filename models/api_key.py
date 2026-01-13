from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime

class KeyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"

class APIKey(BaseModel):
    key_hash: str = Field(..., description="Hashed API Key for secure storage")
    key_prefix: str = Field(..., description="First 8 chars of key for display")
    organization_id: str = Field(..., description="Organization this key belongs to")
    name: str = Field(..., description="Friendly name for the key (e.g. 'Prod Backend')")
    environment: str = Field(..., description="SANDBOX or PRODUCTION")
    status: KeyStatus = Field(KeyStatus.ACTIVE, description="Key status")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")
    created_by: str = Field(..., description="User ID who created this key")


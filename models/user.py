from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime

class UserRole(str, Enum):
    ORG_ADMIN = "ORG_ADMIN"
    DEVELOPER = "DEVELOPER"
    VIEWER = "VIEWER"
    AUDITOR = "AUDITOR"
    SUPER_ADMIN = "SUPER_ADMIN"

class User(BaseModel):
    id: str = Field(..., description="Unique User ID")
    organization_id: str = Field(..., description="Organization ID")
    email: str = Field(..., description="User email (used for login)")
    password_hash: str = Field(..., description="Hashed password")
    role: UserRole = Field(UserRole.AUDITOR, description="RBAC Role")
    full_name: str = Field(..., description="Display Name")
    created_at: datetime = Field(default_factory=datetime.now)
    last_login_at: Optional[datetime] = None


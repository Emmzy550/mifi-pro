from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
from datetime import datetime

class UserRole(str, Enum):
    ORG_ADMIN = "ORG_ADMIN"
    OFFICER = "OFFICER"
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

    @field_validator('role', mode='before')
    @classmethod
    def normalize_role(cls, v):
        if isinstance(v, str):
            v_upper = v.upper()
            # Map legacy roles
            if v_upper == "ADMIN": return UserRole.ORG_ADMIN
            if v_upper == "USER": return UserRole.VIEWER
            
            # Direct match
            for role in UserRole:
                if v_upper == role.value:
                    return role
        return v

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from starlette.status import HTTP_403_FORBIDDEN, HTTP_401_UNAUTHORIZED
from passlib.context import CryptContext
from jose import jwt, JWTError

from utils.db import Database
from models.user import User, UserRole
from models.api_key import APIKey, KeyStatus
from models.organization import OrgStatus
from agents.audit_agent import AuditAgent

# Configuration for Auth
SECRET_KEY = "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

class AuthAgent:
    """
    Handles authentication for Loan Officers (API Key) and Dashboard Users (JWT).
    Refactored for V3 to use Database instead of hardcoded keys.
    """
    API_KEY_NAME = "X-API-KEY"
    api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

    @staticmethod
    def verify_password(plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password):
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def hash_key(key: str) -> str:
        """Hashes the raw API key for storage lookup."""
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    async def get_api_key(cls, received_key: str = Security(api_key_header)):
        """
        Validates the API key from the request header against the Database.
        """
        if not received_key:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="API Key is missing"
            )

        # 1. Hash the key
        key_hash = cls.hash_key(received_key)
        
        # 2. Lookup in DB
        api_key_record = Database.get_api_key(key_hash)

        if not api_key_record:
            # Fallback for Legacy Hardcoded Keys (Migration Support)
            # TODO: Remove this after full migration
            legacy_user = cls._check_legacy_keys(received_key)
            if legacy_user:
                return legacy_user
                
            AuditAgent.log_event("AUTH_FAILURE", "SYSTEM", {"reason": "Invalid Key"})
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="Invalid API Key"
            )

        # 3. Check status
        if api_key_record.status != KeyStatus.ACTIVE:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="API Key is revoked or inactive"
            )

        # 4. Resolve Organization & Check Status
        org = Database.get_organization(api_key_record.organization_id)
        if not org:
            AuditAgent.log_event("AUTH_FAILURE", "SYSTEM", {"reason": "Orphaned API Key", "key_hash": key_hash})
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="Organization not found for this key"
            )
            
        if org.status != "ACTIVE": # Enum comparison string
             raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="Organization is suspended"
            )

        # 5. Return context
        # If the key belongs to the Platform Owner organization, grant Super Admin role
        role = "OFFICER"
        if api_key_record.organization_id == "PLATFORM_OWNER":
            role = "SUPER_ADMIN"
            
        return AuthUser(
            role=role, 
            organization_id=api_key_record.organization_id
        )

    @classmethod
    async def get_current_user(cls, token: str = Depends(oauth2_scheme)) -> User:
        """
        Validates JWT token for Dashboard access.
        """
        credentials_exception = HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        
        user = Database.get_user_by_email(email)
        if user is None:
            raise credentials_exception
            
        # Check Organization Status
        org = Database.get_organization(user.organization_id)
        print(f"DEBUG AUTH: Checking Org {user.organization_id} for user {email}")
        if not org:
            print(f"DEBUG AUTH: Org {user.organization_id} NOT FOUND")
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Organization not found")
        
        print(f"DEBUG AUTH: Org Status is {org.status} (Type: {type(org.status)})")
        if org.status != OrgStatus.ACTIVE:
             print(f"DEBUG AUTH: Org Status {org.status} is NOT ACTIVE")
             raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="Organization is suspended or invalid"
             )
             
        print(f"Auth Debug: Password verified.")
        return user

    @classmethod
    async def authenticate_user(cls, email: str, password: str) -> Optional[User]:
        user = Database.get_user_by_email(email)
        if not user:
            print(f"Auth Debug: User {email} not found in DB")
            return None
        
        print(f"Auth Debug: Found user {user.id}. Verifying password (len: {len(password)})...")
        # Verify password
        if not cls.verify_password(password, user.password_hash):
            print(f"Auth Debug: Password verification failed for {email}.")
            return None
            
        print(f"Auth Debug: Password verified.")
        return user

    @classmethod
    def create_api_key(cls, organization_id: str, name: str, env: str, created_by: str) -> tuple[str, APIKey]:
        """
        Generates a new API Key and returns the raw key + the record to save.
        """
        raw_key = "sk_" + secrets.token_urlsafe(32)
        key_hash = cls.hash_key(raw_key)
        
        api_key_record = APIKey(
            key_hash=key_hash,
            key_prefix=raw_key[:8],
            organization_id=organization_id,
            name=name,
            environment=env,
            created_by=created_by,
            status=KeyStatus.ACTIVE
        )
        
        Database.save_api_key(api_key_record)
        return raw_key, api_key_record

    @staticmethod
    def _check_legacy_keys(received_key: str):
        """
        Hardcoded keys for backward compatibility during migration.
        """
        VALID_KEYS = {
            "mfi-admin-key": AuthUser(role="OFFICER", organization_id="DEFAULT_ORG"),
            "mfi-zambia-key": AuthUser(role="OFFICER", organization_id="MFI_B_ZAMBIA"),
            "super-admin-key": AuthUser(role="SUPER_ADMIN", organization_id="PLATFORM_OWNER"),
            "portal-key": AuthUser(role="CLIENT", organization_id="DEFAULT_ORG"),
            "mfi-officer-admin-key": AuthUser(role="OFFICER", organization_id="DEFAULT_ORG"),
            "mfi-b-officer-key": AuthUser(role="OFFICER", organization_id="MFI_B_ZAMBIA"),
            "platform-super-admin-key": AuthUser(role="SUPER_ADMIN", organization_id="PLATFORM_OWNER")
        }
        return VALID_KEYS.get(received_key)

# Helper class to match what main.py expects
class AuthUser:
    def __init__(self, role: str, organization_id: str, email: Optional[str] = None):
        self.role = role
        self.organization_id = organization_id
        self.email = email or f"key_user_{organization_id.lower()}"

async def get_super_admin(
    received_key: Optional[str] = Security(AuthAgent.api_key_header),
    token: Optional[str] = Depends(oauth2_scheme)
) -> User:
    """
    Dependency to enforce SUPER_ADMIN role.
    Works with both Dashboard JWT and API Keys (Legacy/Migration).
    """
    user = None
    
    # 1. Try API Key first (common for super dashboard script)
    if received_key:
        try:
            user = await AuthAgent.get_api_key(received_key)
        except Exception:
            pass
            
    # 2. Try JWT if no user found yet
    if not user and token:
        try:
            user = await AuthAgent.get_current_user(token)
        except Exception:
            pass
            
    if not user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, 
            detail="Authentication required. Please provide a valid API Key or JWT."
        )

    # 3. Enforce Role
    if user.role != "SUPER_ADMIN":
        AuditAgent.log_event("AUTH_FAILURE", getattr(user, 'email', 'KEY_USER'), {"reason": "Insufficient Privileges", "required": "SUPER_ADMIN"})
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Super Admin privileges required."
        )
        
    return user

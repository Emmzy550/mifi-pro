import secrets
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional
import logging
from contextlib import contextmanager
logger = logging.getLogger(__name__)

from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from starlette.status import HTTP_403_FORBIDDEN, HTTP_401_UNAUTHORIZED
from passlib.context import CryptContext
import firebase_admin
from firebase_admin import auth as firebase_auth
from jose import jwt, JWTError

import config
from utils.db import Database
from models.user import User, UserRole
from models.api_key import APIKey, KeyStatus
from models.organization import OrgStatus
from agents.audit_agent import AuditAgent

# Configuration for Auth
SECRET_KEY = config.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

_PROXY_ENV_KEYS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]


@contextmanager
def _without_broken_local_proxy():
    """
    Some local environments export a dead proxy like http://127.0.0.1:9,
    which breaks Firebase public-key fetches during ID token verification.
    Temporarily remove only those obviously invalid loopback proxy values.
    """
    removed = {}
    try:
        for key in _PROXY_ENV_KEYS:
            value = os.environ.get(key)
            if not value:
                continue
            normalized = value.strip().lower()
            if normalized in {
                "http://127.0.0.1:9",
                "http://localhost:9",
                "https://127.0.0.1:9",
                "https://localhost:9",
            }:
                removed[key] = value
                os.environ.pop(key, None)
        yield
    finally:
        for key, value in removed.items():
            os.environ[key] = value

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

        # 4b. Enforce Payment Status for PRODUCTION environment
        from models.organization import OrgEnvironment, PaymentStatus
        if api_key_record.environment == OrgEnvironment.PRODUCTION:
            if org.payment_status != PaymentStatus.PAID:
                raise HTTPException(
                    status_code=402, 
                    detail={
                        "error": "Payment Required",
                        "message": "You’re currently using the sandbox. Complete payment to unlock live decision processing.",
                        "payment_status": org.payment_status
                    }
                )

        # 5. Return context
        # If the key belongs to the Platform Owner organization, grant Super Admin role
        role = "OFFICER"
        if api_key_record.organization_id == "PLATFORM_OWNER":
            role = "SUPER_ADMIN"
            
        return AuthUser(
            role=role, 
            organization_id=api_key_record.organization_id,
            environment=api_key_record.environment
        )

    @classmethod
    async def get_api_key_optional(cls, received_key: str = Security(api_key_header)):
        """
        Optional version of get_api_key. Returns None if key is missing or invalid.
        """
        if not received_key:
            return None
        try:
            return await cls.get_api_key(received_key)
        except HTTPException:
            return None

    @classmethod
    async def get_current_user(cls, token: str = Depends(oauth2_scheme)) -> User:
        """
        Validates Authentication:
        1. Checks for local HS256 JWT (Internal API usage)
        2. Falls back to Firebase ID Token (Dashboard Frontend)
        """
        credentials_exception = HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        if not token:
            logger.debug("[AUTH DEBUG] No token provided")
            raise credentials_exception

        try:
            # Force DB/Firebase Initialization
            Database.get_db()
        except Exception as db_error:
            logger.error(f"[AUTH DEBUG] Database initialization failed: {db_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Database initialization failed: {str(db_error)}"
            )

        email = None
        
        # 1. ATTEMPT LOCAL JWT (HS256)
        try:
            logger.debug("[AUTH DEBUG] Attempting local HS256 JWT decoding...")
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            if email:
                logger.debug(f"[AUTH DEBUG] Valid local JWT found for: {email}")
        except JWTError:
            # This is expected for standard dashboard users who send Firebase tokens
            logger.debug("[AUTH DEBUG] Local JWT decode failed. Attempting Firebase ID token...")
        except Exception as e:
            logger.error(f"[AUTH DEBUG] Unexpected local JWT error: {e}")

        # 2. ATTEMPT FIREBASE ID TOKEN (RS256)
        if not email:
            try:
                # Decodes and verifies the token using Firebase Public Keys
                app = firebase_admin.get_app()
                with _without_broken_local_proxy():
                    decoded_token = firebase_auth.verify_id_token(token, app=app)
                email = decoded_token.get("email")
                if email:
                     logger.debug(f"[AUTH DEBUG] Valid Firebase ID token found for: {email}")
            except Exception as e:
                logger.error(f"[AUTH DEBUG] Firebase token verification failed: {e}")
                raise credentials_exception
        
        if not email:
            logger.error("[AUTH DEBUG] All auth methods failed.")
            raise credentials_exception
        
        try:
            logger.debug(f"[AUTH DEBUG] Looking up user by email: {email}")
            user = Database.get_user_by_email(email)
            if user is None:
                logger.debug(f"[AUTH DEBUG] User {email} not found in Firestore Users collection")
                raise credentials_exception
            logger.debug(f"[AUTH DEBUG] Found user: {user.id}, org={user.organization_id}")
        except HTTPException:
            raise
        except Exception as user_err:
            logger.error(f"[AUTH DEBUG] User lookup failed: {user_err}")
            raise HTTPException(
                status_code=500,
                detail=f"User lookup failed: {str(user_err)}"
            )
            
        try:
            # Check Organization Status
            logger.debug(f"[AUTH DEBUG] Looking up organization: {user.organization_id}")
            org = Database.get_organization(user.organization_id)
            if not org:
                logger.debug(f"[AUTH DEBUG] Organization {user.organization_id} not found")
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Organization not found")
            
            if org.status != OrgStatus.ACTIVE:
                # Handle cases where OrgStatus is still a string in old records or Enum
                status_val = org.status.value if hasattr(org.status, 'value') else org.status
                if status_val != "ACTIVE":
                    logger.debug(f"[AUTH DEBUG] Organization status is {status_val}, not ACTIVE")
                    raise HTTPException(
                        status_code=HTTP_403_FORBIDDEN, detail="Organization is suspended or invalid"
                    )
        except HTTPException:
            raise
        except Exception as org_err:
            logger.error(f"[AUTH DEBUG] Organization lookup failed: {org_err}")
            raise HTTPException(
                status_code=500,
                detail=f"Organization lookup failed: {str(org_err)}"
            )
                 
        logger.debug(f"[AUTH DEBUG] Authentication successful for {email}")
        return user

    @classmethod
    def create_firebase_user(cls, email: str, password: str, display_name: Optional[str] = None) -> str:
        """
        Creates a user in Firebase Authentication.
        Returns the Firebase UID.
        """
        # Ensure Firebase is initialized
        Database.get_db()
        
        try:
            user = firebase_auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )
            logger.debug(f"DEBUG AUTH: Created Firebase user {user.uid} for {email}")
            return user.uid
        except firebase_admin.exceptions.AlreadyExistsError:
            # If user already exists in Firebase, we should probably try to get their UID
            # and reuse it, or raise an error if this is unexpected.
            user = firebase_auth.get_user_by_email(email)
            logger.debug(f"DEBUG AUTH: Firebase user {email} already exists. Reusing UID {user.uid}")
            return user.uid
        except Exception as e:
            logger.error(f"DEBUG AUTH: Failed to create Firebase user: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create authentication record: {str(e)}")

    @classmethod
    def update_firebase_user_password(cls, user_id: str, new_password: str):
        """
        Updates a user's password in Firebase Authentication.
        """
        Database.get_db()
        try:
            firebase_auth.update_user(user_id, password=new_password)
        except Exception as e:
            print(f"DEBUG AUTH: Failed to update Firebase password: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update authentication record: {str(e)}")

    @classmethod
    async def authenticate_user(cls, email: str, password: str) -> Optional[User]:
        user = Database.get_user_by_email(email)
        if not user:
            logger.debug(f"Auth Debug: User {email} not found in DB")
            return None
        
        # Verify password
        if not cls.verify_password(password, user.password_hash):
            logger.error(f"Auth Debug: Password verification failed for {email}.")
            return None
            
        return user

    @classmethod
    def create_api_key(cls, organization_id: str, name: str, env: str, created_by: str) -> tuple[str, APIKey]:
        """
        Generates a new API Key and returns the raw key + the record to save.
        Enforces one active key per environment.
        """
        # 1. Resolve Organization
        org = Database.get_organization(organization_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        # 2. Check for existing active keys in the same environment
        existing_keys = Database.list_api_keys(organization_id)
        active_env_keys = [k for k in existing_keys if k.environment == env and k.status == KeyStatus.ACTIVE]
        
        if active_env_keys:
            if env == "SANDBOX":
                AuditAgent.log_event("BLOCKED_CREATE", created_by, {"reason": "SANDBOX_KEY_EXISTS", "org_id": organization_id})
                raise HTTPException(
                    status_code=409, 
                    detail={
                        "error": "SANDBOX_KEY_EXISTS",
                        "message": "Only one Sandbox API key is allowed per organization."
                    }
                )
            else:
                AuditAgent.log_event("BLOCKED_CREATE", created_by, {"reason": "PRODUCTION_KEY_EXISTS", "org_id": organization_id})
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "PRODUCTION_KEY_EXISTS",
                        "message": "Only one Production API key is allowed. Please revoke the existing key to rotate."
                    }
                )

        # 3. Enforce Production billing status
        if env == "PRODUCTION" and org.billing_status != "ACTIVE":
            AuditAgent.log_event("BLOCKED_CREATE", created_by, {"reason": "BILLING_NOT_ACTIVE", "org_id": organization_id})
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "BILLING_NOT_ACTIVE",
                    "message": "Activate billing to create a Production API key."
                }
            )

        # 4. Generate Key
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
        AuditAgent.log_event("CREATE_KEY", created_by, {"environment": env, "org_id": organization_id})
        
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
    def __init__(self, role: str, organization_id: str, environment: str = "SANDBOX", email: Optional[str] = None):
        self.role = role
        self.organization_id = organization_id.upper() if organization_id else "DEFAULT_ORG"
        self.environment = environment
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

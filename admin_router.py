
import datetime
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import List, Dict, Optional
import uuid
from models.user import User, UserRole
from models.organization import Organization, OrgStatus, BillingPlan
from models.organization import Organization, OrgStatus, BillingPlan
from models.api_key import APIKey
from agents.auth_agent import AuthAgent, get_super_admin
from utils.db import Database
from agents.audit_agent import AuditAgent
import config

from fastapi.responses import FileResponse
import os

# Create Admin Router
admin_router = APIRouter(
    prefix="/admin",
    tags=["Super Admin"],
    dependencies=[Depends(get_super_admin)]
)

@admin_router.get("/organizations", response_model=List[Organization])
async def list_organizations(current_user: User = Depends(get_super_admin)):
    """
    List all organizations.
    """
    return Database.list_organizations()

@admin_router.post("/organizations", response_model=Dict)
async def create_organization(
    org_data: Dict = Body(..., example={"name": "New MFI", "plan_name": "starter", "admin_email": "admin@newmfi.com"}),
    current_user: User = Depends(get_super_admin)
):
    """
    Create a new organization.
    If 'admin_email' is provided, also creates the first ORG_ADMIN user with a generated password.
    """
    # 1. Validate Initial User if requested
    admin_email = org_data.get("admin_email")
    if admin_email and Database.get_user_by_email(admin_email):
        raise HTTPException(status_code=400, detail=f"User with email {admin_email} already exists. Please choose a different email for the organization administrator.")

    # 2. Create Org
    import uuid
    import secrets
    org_id = f"ORG-{uuid.uuid4().hex[:8].upper()}"
    
    new_org = Organization(
        id=org_id,
        name=org_data.get("name"),
        plan_name=org_data.get("plan_name", "sandbox"),
        monthly_limit=10 if org_data.get("plan_name", "sandbox") == "sandbox" else 10,
        status=OrgStatus.ACTIVE
    )
    
    Database.save_organization(new_org)
    AuditAgent.log_event("ORG_CREATED", current_user.email, {"org_id": org_id, "name": new_org.name})
    
    response = new_org.model_dump(mode='json')
    
    # 3. Create Initial User
    if admin_email:
        generated_password = secrets.token_urlsafe(10)
        pwd_hash = AuthAgent.get_password_hash(generated_password)
        
        new_user = User(
            id=f"USR-{uuid.uuid4().hex[:8].upper()}",
            organization_id=org_id,
            email=admin_email,
            password_hash=pwd_hash,
            full_name="Admin User",
            role=UserRole.ORG_ADMIN
        )
        Database.save_user(new_user)
        AuditAgent.log_event("USER_CREATED_BY_SYSTEM", current_user.email, {"new_user_id": new_user.id, "org": org_id})
        
        response["user_created"] = True
        response["initial_credentials"] = {
            "email": admin_email,
            "password": generated_password
        }
    else:
        response["user_created"] = False

    return response

@admin_router.patch("/organizations/{org_id}", response_model=Organization)
async def update_organization(
    org_id: str,
    update_data: Dict = Body(...),
    current_user: User = Depends(get_super_admin)
):
    """
    Update organization status or limits.
    """
    org = Database.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    if "status" in update_data:
        org.status = update_data["status"]
        
    if "monthly_limit" in update_data:
        org.monthly_limit = update_data["monthly_limit"]
        
    if "plan_name" in update_data:
        org.plan_name = update_data["plan_name"]
        
    Database.save_organization(org)
    AuditAgent.log_event("ORG_UPDATED", current_user.email, {"org_id": org_id, "updates": list(update_data.keys())})
    return org

@admin_router.get("/audit-logs", response_model=List[Dict])
async def list_global_audit_logs(
    limit: int = 100,
    current_user: User = Depends(get_super_admin)
):
    """
    View global audit logs.
    """
    return AuditAgent.list_logs(limit=limit)

@admin_router.post("/users", response_model=User)
async def create_admin_user(
    user_data: Dict = Body(...),
    current_user: User = Depends(get_super_admin)
):
    """
    Create a new user (usually the first ORG_ADMIN for a new org).
    """
    # Basic validation
    if Database.get_user_by_email(user_data["email"]):
        raise HTTPException(status_code=400, detail="Email already registered")
        
    pwd_hash = AuthAgent.get_password_hash(user_data["password"])
    
    new_user = User(
        id=f"USR-{uuid.uuid4().hex[:8].upper()}",
        organization_id=user_data["organization_id"],
        email=user_data["email"],
        password_hash=pwd_hash,
        full_name=user_data["full_name"],
        role=UserRole.ORG_ADMIN # Force ORG_ADMIN for manually created users via this endpoint
    )
    
    Database.save_user(new_user)
    AuditAgent.log_event("USER_CREATED_BY_ADMIN", current_user.email, {"new_user_id": new_user.id, "org": new_user.organization_id})
    return new_user

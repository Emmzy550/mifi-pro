from utils.db import Database
from models.user import User, UserRole
from models.organization import Organization, OrgStatus, BillingPlan
from agents.auth_agent import AuthAgent
import uuid

# Initialize DB
# This forces the DB to load
Database.get_db()

email = "admin@platform.com"
password = "admin123"


# 1. Create Platform Org if missing
print("Checking for PLATFORM_OWNER organization...")
plat_org = Database.get_organization("PLATFORM_OWNER")
if not plat_org:
    print("Creating PLATFORM_OWNER organization...")
    plat_org = Organization(
        id="PLATFORM_OWNER",
        name="Loan Officer AI Platform",
        plan_name=BillingPlan.ENTERPRISE,
        monthly_limit=1000000,
        status=OrgStatus.ACTIVE
    )
    Database.save_organization(plat_org)
    print("Created PLATFORM_OWNER org.")
else:
    print("PLATFORM_OWNER org exists.")

print(f"Checking for existing user: {email}...")
existing = Database.get_user_by_email(email)

if existing:
    print(f"User {email} already exists. Resetting role to SUPER_ADMIN just in case.")
    existing.role = UserRole.SUPER_ADMIN
    Database.save_user(existing)
    print("Updated existing user.")
else:
    print(f"Creating new Super Admin: {email}")
    pwd_hash = AuthAgent.get_password_hash(password)
    user = User(
        id=f"USR-{uuid.uuid4().hex[:8].upper()}",
        organization_id="PLATFORM_OWNER",
        email=email,
        password_hash=pwd_hash,
        full_name="Platform Super Admin",
        role=UserRole.SUPER_ADMIN
    )
    Database.save_user(user)
    print("Created new user.")

print(f"\n[SUCCESS] Super Admin Ready")
print(f"Email: {email}")
print(f"Password: {password}")

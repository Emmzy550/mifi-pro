import asyncio
from models.user import User, UserRole
from models.organization import Organization, OrgStatus, OrgEnvironment
from utils.db import Database
from agents.auth_agent import AuthAgent

async def seed_data():
    print("Seeding Database with Initial Data...")
    
    # 1. Create Default Organization
    org = Organization(
        id="DEFAULT_ORG",
        name="Acme Microfinance Ltd",
        environment=OrgEnvironment.PRODUCTION,
        status=OrgStatus.ACTIVE
    )
    Database.save_organization(org)
    print(f"[OK] Organization Created: {org.name}")

    # 2. Create Admin User
    # Email: admin@acme.com
    # Pass: admin123
    
    password_hash = AuthAgent.get_password_hash("admin123")
    
    admin_user = User(
        id="USR-ADMIN-001",
        organization_id="DEFAULT_ORG",
        email="admin@acme.com",
        password_hash=password_hash,
        role=UserRole.ORG_ADMIN,
        full_name="Alice Administrator"
    )
    
    Database.save_user(admin_user)
    print(f"[OK] Users Created: {admin_user.email} (Password: admin123)")
    
    # 3. Create a Developer User
    dev_hash = AuthAgent.get_password_hash("dev123")
    dev_user = User(
         id="USR-DEV-001",
         organization_id="DEFAULT_ORG",
         email="dev@acme.com",
         password_hash=dev_hash,
         role=UserRole.DEVELOPER,
         full_name="Bob Developer"
    )
    Database.save_user(dev_user)
    print(f"[OK] Users Created: {dev_user.email} (Password: dev123)")

    print("\n[DONE] Seeding Complete! You can now login to the dashboard.")

if __name__ == "__main__":
    asyncio.run(seed_data())

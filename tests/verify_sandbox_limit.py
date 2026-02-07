import asyncio
from utils.db import Database
from admin_router import create_organization
from models.user import User, UserRole
from models.organization import BillingPlan

async def verify_limit():
    print("Verifying Sandbox Monthly Limit...")
    
    # Mock a super admin user
    super_admin = User(
        id="SUPER-ADMIN",
        organization_id="PLATFORM_OWNER",
        email="super@admin.com",
        password_hash="...",
        role=UserRole.SUPER_ADMIN,
        full_name="Super Admin"
    )
    
    # 1. Test Sandbox Creation
    import uuid
    unique_id = uuid.uuid4().hex[:4]
    sandbox_payload = {
        "name": f"Verify Sandbox Org {unique_id}",
        "plan_name": "sandbox",
        "admin_email": f"test-sandbox-{unique_id}@example.com"
    }
    
    resp = await create_organization(sandbox_payload, current_user=super_admin)
    org_id = resp["id"]
    org = Database.get_organization(org_id)
    
    print(f"Sandbox Org: {org.name}")
    print(f"Plan: {org.plan_name}")
    print(f"Monthly Limit: {org.monthly_limit}")
    
    if org.monthly_limit == 10:
        print("✅ SUCCESS: Sandbox limit is 10.")
    else:
        print(f"❌ FAILURE: Sandbox limit is {org.monthly_limit}, expected 10.")

    # 2. Test Starter Creation (should be 1000)
    starter_payload = {
        "name": f"Verify Starter Org {unique_id}",
        "plan_name": "starter",
        "admin_email": f"test-starter-{unique_id}@example.com"
    }
    
    resp_starter = await create_organization(starter_payload, current_user=super_admin)
    org_starter = Database.get_organization(resp_starter["id"])
    
    print(f"\nStarter Org: {org_starter.name}")
    print(f"Plan: {org_starter.plan_name}")
    print(f"Monthly Limit: {org_starter.monthly_limit}")
    
    if org_starter.monthly_limit == 1000:
        print("✅ SUCCESS: Starter limit is 1000.")
    else:
        print(f"❌ FAILURE: Starter limit is {org_starter.monthly_limit}, expected 1000.")

if __name__ == "__main__":
    asyncio.run(verify_limit())

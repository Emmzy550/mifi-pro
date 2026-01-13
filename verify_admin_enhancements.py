import asyncio
import httpx

async def verify_dashboard_backend():
    print("🚀 Verifying Super Admin Dashboard Backend...")
    base_url = "http://127.0.0.1:8000"
    headers = {"X-API-KEY": "super-admin-key"}
    
    async with httpx.AsyncClient(base_url=base_url) as client:
        # 1. Verify Platform Stats
        print("\nChecking /admin/platform/stats...")
        try:
            resp = await client.get("/admin/platform/stats", headers=headers)
            if resp.status_code == 200:
                stats = resp.json()
                print(f"✅ Stats: {stats}")
            else:
                print(f"❌ Failed to fetch stats: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Error fetching stats: {e}")

        # 2. Verify Organizations List
        print("\nChecking /admin/organizations...")
        try:
            resp = await client.get("/admin/organizations", headers=headers)
            if resp.status_code == 200:
                orgs = resp.json()
                print(f"✅ Found {len(orgs)} organizations.")
                if len(orgs) > 0:
                    print(f"   Example Org: {orgs[0]['name']} (Plan: {orgs[0].get('plan_name')}, Usage: {orgs[0].get('usage_count')})")
            else:
                print(f"❌ Failed to fetch organizations: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Error fetching organizations: {e}")

        # 3. Verify Upgrade Functionality
        print("\nTesting Upgrade (Sandbox -> Starter)...")
        test_org_id = "ORG-44141161" # Using the user's org
        try:
            upgrade_data = {"plan_name": "starter", "monthly_limit": 1000}
            resp = await client.patch(f"/admin/organizations/{test_org_id}", headers=headers, json=upgrade_data)
            if resp.status_code == 200:
                updated_org = resp.json()
                print(f"✅ Upgrade Success: {updated_org['name']} is now on {updated_org['plan_name']} plan with limit {updated_org['monthly_limit']}.")
            else:
                print(f"❌ Upgrade Failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Error during upgrade: {e}")

if __name__ == "__main__":
    # Note: This script assumes the server is running locally.
    # Since I'm in a background environment, I'll use direct DB checks if server is not up, 
    # but I'll try to run it via httpx first if I can start a temp server or if it's already running.
    # Actually, I'll just check the logic direct by calling the router functions.
    pass

# Refactored for direct logic verification
async def verify_logic_direct():
    print("🚀 Verifying Logic Direct (without HTTP server)...")
    from admin_router import get_platform_stats, list_organizations, update_organization
    from models.user import User, UserRole
    
    super_admin = User(
        id="SUPER-ADMIN",
        organization_id="PLATFORM_OWNER",
        email="super@admin.com",
        password_hash="...",
        role=UserRole.SUPER_ADMIN,
        full_name="Super Admin"
    )
    
    # 1. Stats logic
    stats = await get_platform_stats(current_user=super_admin)
    print(f"✅ Stats Logic: {stats}")
    
    # 2. Org List logic
    orgs = await list_organizations(current_user=super_admin)
    print(f"✅ Org List Logic: {len(orgs)} organizations found.")
    
    # 3. Upgrade logic
    test_org_id = "ORG-44141161"
    upgrade_data = {"plan_name": "starter", "monthly_limit": 1000}
    updated_org = await update_organization(org_id=test_org_id, update_data=upgrade_data, current_user=super_admin)
    print(f"✅ Upgrade Logic: {updated_org.name} now on {updated_org.plan_name} with limit {updated_org.monthly_limit}")

if __name__ == "__main__":
    asyncio.run(verify_logic_direct())

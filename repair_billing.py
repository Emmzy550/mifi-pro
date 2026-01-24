
import asyncio
from models.organization import Organization, PaymentStatus
from utils.db import Database

async def repair_priscah():
    print("--- Billing Repair Script ---")
    
    # Initialize DB
    db = Database.get_db()
    
    # 1. Find User
    user = Database.get_user_by_email("priscah@gmail.com")
    if not user:
        print("ERROR: User priscah@gmail.com not found")
        return
    
    # 2. Get Organization
    org = Database.get_organization(user.organization_id)
    if not org:
        print(f"ERROR: Organization {user.organization_id} not found")
        return
    
    print(f"Current Plan: {org.plan}")
    print(f"Current Payment Status: {org.payment_status}")
    
    # 3. Repair
    org.payment_status = PaymentStatus.PAID
    org.billing_status = "ACTIVE"
    
    Database.save_organization(org)
    print(f"\n[SUCCESS] Updated Organization {org.id} to PAID status.")
    print("Production API should now be UNLOCKED.")

if __name__ == "__main__":
    asyncio.run(repair_priscah())


import os
import firebase_admin
from firebase_admin import credentials, firestore
from models.user import User
from models.organization import Organization
from utils.db import Database

async def inspect_priscah():
    print("--- Billing Diagnostic Script ---")
    
    # Initialize DB (will use serviceAccountKey.json)
    db = Database.get_db()
    
    # 1. Find User
    user = Database.get_user_by_email("priscah@gmail.com")
    if not user:
        print("ERROR: User priscah@gmail.com not found")
        return
    
    print(f"User Found: {user.email}")
    print(f"Role: {user.role}")
    print(f"Org ID: {user.organization_id}")
    
    # 2. Get Organization
    org = Database.get_organization(user.organization_id)
    if not org:
        print(f"ERROR: Organization {user.organization_id} not found")
        return
    
    print("\n--- Organization State ---")
    print(f"Name: {org.name}")
    print(f"Plan (field.plan): {org.plan}")
    print(f"Payment Status: {org.payment_status}")
    print(f"Billing Status: {org.billing_status}")
    print(f"Environment: {org.environment}")
    
    # 3. Check for 'plan_name' extra field if any
    raw_doc = db.collection("organizations").document(org.id).get().to_dict()
    print("\n--- Raw JSON Data ---")
    import json
    print(json.dumps(raw_doc, indent=2, default=str))

if __name__ == "__main__":
    import asyncio
    asyncio.run(inspect_priscah())

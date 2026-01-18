#!/usr/bin/env python3
"""
Verify that your API key can be authenticated properly
"""
import hashlib
from utils.db import Database

# Your API key from the dashboard
api_key = "sk_lkCRNjHBGKJnNMgkHLdkTb5YcmsK8rV9igQvsDHKtK0"

print("="*60)
print("API KEY AUTHENTICATION VERIFICATION")
print("="*60)

# Check the key using the same method the API uses
print(f"\n1. Testing API key: {api_key[:20]}...")

# Hash the key (this is how it's stored)
key_hash = hashlib.sha256(api_key.encode()).hexdigest()
print(f"2. Key hash: {key_hash[:40]}...")

# Try to fetch it from database
api_key_obj = Database.get_api_key(key_hash)

if api_key_obj:
    print("\n✅ API KEY FOUND IN DATABASE!")
    print(f"   - Organization ID: {api_key_obj.organization_id}")
    print(f"   - Environment: {api_key_obj.environment}")
    print(f"   - Status: {api_key_obj.status}")
    print(f"   - Name: {api_key_obj.name}")
    
    org_id = api_key_obj.organization_id
    
    # Now check borrowers for this organization
    print("\n" + "="*60)
    print(f"BORROWERS FOR ORGANIZATION: {org_id}")
    print("="*60)
    
    borrowers = Database.list_borrowers(organization_id=org_id)
    if borrowers:
        print(f"\nFound {len(borrowers)} borrower(s):")
        for b in borrowers:
            print(f"  - ID: {b.id}")
            print(f"    Name: {b.name}")
            print(f"    Org: {b.organization_id}")
            print()
    else:
        print("\n⚠️  NO BORROWERS FOUND for this organization yet!")
        print("\nYou need to create a borrower first using /intake/start")
        print("Make sure to include the X-API-KEY header when creating the borrower")
    
    print("\n" + "="*60)
    print("POSTMAN SETUP")
    print("="*60)
    print("\nTo create a borrower that matches your API key:")
    print("\n1. Create Borrower:")
    print("   POST http://localhost:8000/intake/start")
    print("\n   Headers:")
    print(f"   X-API-KEY: {api_key}")
    print("\n   Body (JSON):")
    print("""   {
       "name": "Test Borrower",
       "phone": "+254700000000",
       "employment_type": "trader",
       "monthly_income": 50000,
       "monthly_expenses": 20000,
       "existing_debt": 5000,
       "loan_amount_requested": 15000,
       "loan_purpose": "Business"
   }""")
    print(f"\n   → The borrower will automatically get org_id: {org_id}")
    
    print("\n2. Then upload alternative data:")
    print("   POST http://localhost:8000/borrower/data/upload")
    print(f"\n   Headers:")
    print(f"   X-API-KEY: {api_key}")
    print("\n   Body:")
    print("""   {
       "borrower_id": "<borrower_id_from_step_1>",
       "data_type": "bank_statement",
       "data_source": "Manual Upload",
       "data": {...}
   }""")
    
else:
    print("\n❌ API KEY NOT FOUND IN DATABASE!")
    print("\nPossible reasons:")
    print("1. The key wasn't saved properly")
    print("2. Database connection issue")
    print("3. The key was created in a different environment")
    
    # List all API keys to help debug
    print("\n" + "="*60)
    print("ALL ORGANIZATIONS AND THEIR API KEYS")
    print("="*60)
    
    orgs = Database.list_organizations()
    for org in orgs:
        print(f"\nOrganization: {org.name} ({org.id})")
        try:
            keys = Database.list_api_keys(org.id)
            if keys:
                for key in keys:
                    print(f"  - {key.key_prefix}... (Env: {key.environment}, Status: {key.status})")
            else:
                print("  (no API keys)")
        except Exception as e:
            print(f"  Error: {e}")

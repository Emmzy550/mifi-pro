#!/usr/bin/env python3
"""
Debug script to verify API key and borrower organization matching
"""
from utils.db import Database

# Your API key
api_key = "sk_lkCRNjHBGKJnNMgkHLdkTb5YcmsK8rV9igQvsDHKtK0"

print("="*60)
print("API KEY DEBUGGING")
print("="*60)

# Find the API key in the database
key_obj = Database.get_api_key(api_key)
if key_obj:
    print(f"✓ API Key found!")
    print(f"  - Key ID: {key_obj.id}")
    print(f"  - Organization ID: {key_obj.organization_id}")
    print(f"  - Environment: {key_obj.environment}")
    print(f"  - Status: {key_obj.status}")
    print(f"  - Role: {key_obj.role}")
else:
    print("✗ API Key NOT FOUND in database")
    print("\nAvailable API keys:")
    all_keys = Database.list_api_keys()
    for key in all_keys:
        print(f"  - {key.key[:20]}... (Org: {key.organization_id}, Env: {key.environment})")

print("\n" + "="*60)
print("ORGANIZATIONS IN DATABASE")
print("="*60)

# List all organizations
orgs = Database.list_organizations()
if orgs:
    for org in orgs:
        print(f"  - ID: {org.id}")
        print(f"    Name: {org.name}")
        print(f"    Plan: {org.plan}")
        print()
        
        # List API keys for this org
        try:
            org_keys = Database.list_api_keys(org.id)
            if org_keys:
                print(f"    API Keys for {org.name}:")
                for key in org_keys:
                    print(f"      - Prefix: {key.key_prefix}... (Env: {key.environment}, Status: {key.status})")
            else:
                print(f"    No API keys found for {org.name}")
        except Exception as e:
            print(f"    Error listing keys: {e}")
        print()
else:
    print("No organizations found in database")

print("\n" + "="*60)
print("BORROWERS IN DATABASE")
print("="*60)

# List all borrowers to find the one you're trying to use
borrowers = Database.list_borrowers()
if borrowers:
    for borrower in borrowers[:10]:  # Show first 10
        print(f"  - ID: {borrower.id}")
        print(f"    Name: {borrower.name}")
        print(f"    Org ID: {borrower.organization_id}")
        print()
else:
    print("No borrowers found in database")

print("="*60)
print("SOLUTION")
print("="*60)
print("\n⚠️  Your API key is NOT in the database!")
print("\nOptions to fix:")
print("\n1. Create a new API key via the dashboard:")
print("   - Login to http://localhost:8000")
print("   - Go to Settings → API Keys")
print("   - Click 'Create API Key'")
print("\n2. Or use the existing test account credentials:")
print("   - Email: test@example.com")
print("   - Password: password123")
print("\n3. Once you have a valid API key, make sure:")
print("   - The borrower and API key belong to the SAME organization")
print("   - Use the X-API-KEY header in all requests")

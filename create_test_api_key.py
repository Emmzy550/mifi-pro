#!/usr/bin/env python3
"""
Helper script to create a test API key that you can use for testing
"""
from utils.db import Database
from models.organization import Organization, BillingPlan, BillingStatus, OrgEnvironment
from models.user import User
from models.api_key import APIKey, KeyStatus
import hashlib
from datetime import datetime, timezone

print("="*60)
print("CREATING TEST API KEY")
print("="*60)

# First, ensure we have a test organization
org_id = "TEST_ORG_001"
org = Database.get_organization(org_id)

if not org:
    print(f"\n✓ Creating test organization: {org_id}")
    org = Organization(
        id=org_id,
        name="Test Organization",
        plan=BillingPlan.SANDBOX,
        billing_status=BillingStatus.ACTIVE,
        monthly_limit=None  # Unlimited for sandbox
    )
    Database.save_organization(org)
else:
    print(f"\n✓ Test organization already exists: {org_id}")

# Create a user for this organization
user_email = "test@example.com"
user = Database.get_user_by_email(user_email)

if not user:
    print(f"✓ Creating test user: {user_email}")
    from agents.auth_agent import AuthAgent
    hashed_password = AuthAgent._hash_password("password123")
    
    user = User(
        id="USER_TEST_001",
        email=user_email,
        hashed_password=hashed_password,
        name="Test User",
        organization_id=org_id,
        role="OFFICER"
    )
    Database.save_user(user)
else:
    print(f"✓ Test user already exists: {user_email}")

# Generate a new API key
print("\n✓ Generating new API key...")

# Create a readable API key
new_api_key = "sk_test_" + hashlib.sha256(datetime.now(timezone.utc).isoformat().encode()).hexdigest()[:40]

# Hash it for storage
key_hash = hashlib.sha256(new_api_key.encode()).hexdigest()

# Create the APIKey object
api_key_obj = APIKey(
    key_hash=key_hash,
    key_prefix=new_api_key[:12],
    organization_id=org_id,
    name="Test API Key for Data Upload",
    environment=OrgEnvironment.SANDBOX.value,
    status=KeyStatus.ACTIVE,
    created_at=datetime.now(timezone.utc),
    created_by=user.id,
    role="OFFICER"  # Add role field
)

# Save to database
Database.save_api_key(api_key_obj)

print("\n" + "="*60)
print("✅ SUCCESS! API KEY CREATED")
print("="*60)
print(f"\nYour new API key: {new_api_key}")
print(f"Organization ID: {org_id}")
print(f"Environment: SANDBOX")
print(f"Status: ACTIVE")

print("\n" + "="*60)
print("HOW TO USE THIS API KEY")
print("="*60)
print("\n1. In Postman, update your Headers:")
print(f"   Key: X-API-KEY")
print(f"   Value: {new_api_key}")
print("\n2. Create a borrower:")
print(f"   POST http://localhost:8000/intake/start")
print(f"   Body (JSON):")
print(f"""   {{
       "name": "Test Borrower",
       "phone": "+254700000000",
       "employment_type": "trader",
       "monthly_income": 50000,
       "monthly_expenses": 20000,
       "existing_debt": 5000,
       "loan_amount_requested": 15000,
       "loan_purpose": "Business"
   }}""")
print("\n   The borrower will automatically get organization_id: TEST_ORG_001")
print("\n3. Upload alternative data:")
print(f"   POST http://localhost:8000/borrower/data/upload")
print(f"   Use the borrower_id from step 2")
print("\n" + "="*60)

# Show existing borrowers for this org
print("\nExisting borrowers for TEST_ORG_001:")
borrowers = Database.list_borrowers(organization_id=org_id)
if borrowers:
    for b in borrowers:
        print(f"  - {b.id}: {b.name} (Org: {b.organization_id})")
else:
    print("  (none yet)")

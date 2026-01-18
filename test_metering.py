import requests

BASE_URL = "http://localhost:8000"

print("=== Testing Usage Metering (Corrected) ===\n")

# Use legacy API key
api_key = "mfi-admin-key"
headers = {"X-API-KEY": api_key}

# 1. Create borrower with CORRECT field names
print("1. Creating test borrower...")
borrower_data = {
    "name": "Test Borrower",  # Changed from full_name
    "phone": "+260123456789",
    "employment_type": "trader",  # Changed from employment_status
    "monthly_income": 5000,
    "monthly_expenses": 2000,
    "existing_debt": 0,
    "loan_amount_requested": 2000,
    "loan_purpose": "business"
}

intake_resp = requests.post(f"{BASE_URL}/intake/start", headers=headers, json=borrower_data)
print(f"Status: {intake_resp.status_code}")

if intake_resp.status_code == 200:
    borrower_id = intake_resp.json()["borrower_id"]
    print(f"✓ Borrower ID: {borrower_id}\n")
    
    # 2. Run assessment
    print("2. Running assessment...")
    assessment_resp = requests.post(f"{BASE_URL}/assessment/run", 
                                   headers=headers,
                                   json={"borrower_id": borrower_id})
    print(f"Status: {assessment_resp.status_code}")
    
    if assessment_resp.status_code == 200:
        print("✓ Assessment completed\n")
        
        # 3. Check usage via database
        print("3. Checking usage in database...")
        import sys
        sys.path.insert(0, '.')
        from utils.db import Database
        from models.organization import OrgEnvironment
        
        # Get the DEFAULT_ORG usage
        sandbox_record = Database.get_usage_record("DEFAULT_ORG", OrgEnvironment.SANDBOX)
        print(f"Sandbox usage count: {sandbox_record.assessment_count}")
        
        if sandbox_record.assessment_count > 0:
            print("\n✓ SUCCESS: Usage is being tracked!")
        else:
            print("\n✗ FAILED: Usage not incremented")
    else:
        print(f"✗ Assessment failed: {assessment_resp.text}")
else:
    print(f"✗ Intake failed: {intake_resp.text}")

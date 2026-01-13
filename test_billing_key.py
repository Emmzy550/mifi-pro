import hashlib
import requests
import uuid
from models.api_key import APIKey, KeyStatus
from models.organization import Organization, BillingPlan, BillingStatus
from utils.db import Database
from agents.auth_agent import AuthAgent

def test_api_key_billing():
    raw_key = "sk_qU4aMmlh26vJ6J4w_6vwwXtequKCDCFYwBE8jGlUW_A"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    org_id = "USER_TEST_ORG"
    
    print(f"DEBUG: Setting up test organization: {org_id}")
    
    # 1. Ensure Organization exists with Sandbox plan (Limit 10)
    org = Organization(
        id=org_id,
        name="Billing Test MFI",
        plan_name=BillingPlan.SANDBOX,
        monthly_limit=10,
        unit_cost=0.0,
        usage_count=0,
        billing_status=BillingStatus.ACTIVE
    )
    Database.save_organization(org)
    
    # 2. Register the API Key
    api_key = APIKey(
        key_hash=key_hash,
        key_prefix=raw_key[:8],
        organization_id=org_id,
        name="Test Billing Key",
        environment="SANDBOX",
        created_by="SYSTEM_TEST",
        status=KeyStatus.ACTIVE
    )
    Database.save_api_key(api_key)
    print(f"[OK] API Key registered in DB: {raw_key[:8]}...")

    # 3. Create a test borrower for this org
    borrower_id = f"BOR-{uuid.uuid4().hex[:8].upper()}"
    print(f"INFO: Creating test borrower: {borrower_id}")
    
    # Note: We use the API to create the borrower to ensure it's linked to the org
    intake_url = "http://localhost:8000/intake/start"
    intake_data = {
        "name": "Billing Test User",
        "phone": "+260970000000",
        "employment_type": "salaried",
        "monthly_income": 5000,
        "monthly_expenses": 2000,
        "existing_debt": 1000,
        "loan_amount_requested": 2000,
        "loan_purpose": "Test Metering",
        "organization_id": org_id
    }
    
    # We don't need the key for intake (it's public in this setup, or we use header if required)
    # Actually, let's see if intake requires auth
    intake_res = requests.post(intake_url, json=intake_data)
    if intake_res.status_code != 200:
        print(f"[FAIL] Intake failed: {intake_res.text}")
        return
        
    borrower_id = intake_res.json()["borrower_id"]
    print(f"[OK] Borrower created: {borrower_id}")

    # 4. Run assessment and check metering
    assessment_url = "http://localhost:8000/assessment/run"
    headers = {"X-API-KEY": raw_key}
    
    print("\nINFO: Running first assessment (should increase usage to 1)...")
    res = requests.post(assessment_url, json={"borrower_id": borrower_id}, headers=headers)
    
    if res.status_code == 200:
        print("[OK] Assessment successful!")
        # 5. Verify usage count in DB
        updated_org = Database.get_organization(org_id)
        print(f"STATS: Usage count in DB: {updated_org.usage_count}/{updated_org.monthly_limit}")
        
        if updated_org.usage_count == 1:
            print("SUCCESS: Metering worked correctly.")
        else:
            print(f"[FAIL] ERROR: Expected usage 1, got {updated_org.usage_count}")
    else:
        print(f"[FAIL] Assessment failed: {res.status_code} - {res.text}")

if __name__ == "__main__":
    test_api_key_billing()

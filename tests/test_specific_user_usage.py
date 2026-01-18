
import requests
import sys
import os
import uuid
import time
import hashlib
import secrets

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import Database
from models.api_key import APIKey, KeyStatus
from models.organization import OrgEnvironment

BASE_URL = "http://localhost:8000"
TARGET_ORG_ID = "ORG-44141161"
TEMP_KEY_RAW = "sk_test_temp_" + secrets.token_urlsafe(16)

def setup_temp_key():
    print(f"Setting up temporary key for {TARGET_ORG_ID}...")
    key_hash = hashlib.sha256(TEMP_KEY_RAW.encode()).hexdigest()
    api_key = APIKey(
        key_hash=key_hash,
        key_prefix=TEMP_KEY_RAW[:8],
        organization_id=TARGET_ORG_ID,
        name="Temp Test Key",
        environment="SANDBOX",
        created_by="SYSTEM_TEST",
        status=KeyStatus.ACTIVE
    )
    Database.save_api_key(api_key)
    print("Temporary key saved.")

def cleanup_temp_key():
    print("Cleaning up temporary key...")
    # Ideally we would delete it, but Database might not have delete_api_key.
    # We can revoke it.
    key_hash = hashlib.sha256(TEMP_KEY_RAW.encode()).hexdigest()
    api_key = Database.get_api_key(key_hash)
    if api_key:
        api_key.status = KeyStatus.REVOKED
        Database.save_api_key(api_key)
        print("Temporary key revoked.")

def get_db_usage():
    record = Database.get_usage_record(TARGET_ORG_ID, OrgEnvironment.SANDBOX)
    return record.assessment_count

def run_test():
    try:
        setup_temp_key()
        
        print(f"Initial DB Usage Check for {TARGET_ORG_ID} (SANDBOX)...", flush=True)
        initial_usage = get_db_usage()
        print(f"Initial Usage: {initial_usage}", flush=True)

        # 1. Create Borrower (Public endpoint, but specify Org ID)
        print("\nCreating Borrower...", flush=True)
        borrower_data = {
            "name": f"Mwape Test Borrower {uuid.uuid4().hex[:4]}",
            "phone": "+254700000000",
            "email": "mwape.test@example.com",
            "employment_type": "trader",
            "monthly_income": 60000,
            "monthly_expenses": 25000,
            "existing_debt": 2000,
            "loan_amount_requested": 20000,
            "loan_purpose": "Business stock",
            "organization_id": TARGET_ORG_ID
        }
        
        response = requests.post(f"{BASE_URL}/intake/start", json=borrower_data, timeout=10)
        if response.status_code != 200:
            print(f"FAILED to create borrower: {response.text}", flush=True)
            return
        
        borrower_id = response.json().get("borrower_id")
        print(f"Borrower Created: {borrower_id}", flush=True)

        # 2. Run Assessment using the Temp Key
        print(f"\nRunning Assessment for {borrower_id}...", flush=True)
        headers = {"X-API-KEY": TEMP_KEY_RAW}
        payload = {"borrower_id": borrower_id}
        
        response = requests.post(f"{BASE_URL}/assessment/run", json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"FAILED to run assessment: {response.text}", flush=True)
            return
        
        print("Assessment Successful!", flush=True)
        decision = response.json().get('decision')
        print(f"Decision: {decision}", flush=True)

        # 3. Verify Usage
        print("\nVerifying Usage Increment...", flush=True)
        time.sleep(1)
        
        final_usage = get_db_usage()
        print(f"Final Usage: {final_usage}", flush=True)
        
        if final_usage == initial_usage + 1:
            print(f"\n✅ SUCCESS: Usage count incremented correctly for {TARGET_ORG_ID}!", flush=True)
        else:
            print(f"\n❌ FAILURE: Usage count mismatch. Expected {initial_usage + 1}, got {final_usage}", flush=True)
            
    except Exception as e:
        print(f"Test failed with exception: {e}", flush=True)
    finally:
        cleanup_temp_key()

if __name__ == "__main__":
    run_test()

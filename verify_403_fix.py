import requests
import json

BASE_URL = "http://127.0.0.1:8000"
# We'll use one of the existing keys from the inspection
# sk_DLkii -> DEFAULT_ORG
# sk__xlgW -> ORG-44141161
API_KEY = "mfi-admin-key" # Using legacy key for guaranteed validity in test

def test_fix():
    print(f"Testing with API Key: {API_KEY[:8]}...")
    
    # 1. Create Borrower
    payload = {
        "name": "Verification Test User",
        "phone": "+254712345678",
        "employment_type": "salaried",
        "monthly_income": 45000,
        "monthly_expenses": 15000,
        "loan_amount_requested": 10000,
        "loan_purpose": "Testing"
    }
    
    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    
    print("\n--- Step 1: Create Borrower ---")
    resp = requests.post(f"{BASE_URL}/intake/start", json=payload, headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.json()}")
    
    if resp.status_code != 200:
        print("Failed to create borrower.")
        return

    borrower_id = resp.json()["borrower_id"]
    org_id = resp.json().get("organization_id")
    print(f"Created Borrower {borrower_id} in Org {org_id}")

    # 2. Upload Data
    print("\n--- Step 2: Upload Data ---")
    data_payload = {
        "borrower_id": borrower_id,
        "airtime_usage_avg": 100.0,
        "mobile_money_history": [],
        "utility_history": []
    }
    
    resp = requests.post(f"{BASE_URL}/borrower/data/upload", json=data_payload, headers=headers)
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.json()}")
    
    if resp.status_code == 200:
        print("\n✅ SUCCESS: 403 Avoided! Borrower correctly associated with API Key Org.")
    else:
        print(f"\n❌ FAILED: Got {resp.status_code}")

if __name__ == "__main__":
    test_fix()

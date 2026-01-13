import requests
import json
import sys

# Default URL
BASE_URL = "http://127.0.0.1:8000"

def run_test(api_key):
    print(f"🚀 Sending assessment request to {BASE_URL}/assessment/run...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-API-KEY": api_key, # Endpoint requires this header specifically
        "Content-Type": "application/json"
    }
    
    # 1. Create Borrower via /intake/start
    print(f"\n[Step 1] Creating Borrower via {BASE_URL}/intake/start...")
    intake_payload = {
        "name": "Test Borrower",
        "phone": "+1234567890",
        "email": "test@example.com",
        "employment_type": "trader",
        "monthly_income": 10000,
        "monthly_expenses": 50,
        "loan_amount_requested": 5000,
        "loan_purpose": "Business Expansion",
        "organization_id": "DEFAULT_ORG" # Match the API Key's Org
    }
    
    try:
        resp1 = requests.post(f"{BASE_URL}/intake/start", json=intake_payload, headers=headers)
        if resp1.status_code != 200:
            print(f"[FAIL] Intake Failed: {resp1.text}")
            return
            
        print("[OK] Intake Success!")
        borrower_id = resp1.json()["borrower_id"]
        print(f"   Borrower ID: {borrower_id}")

        # 1.5 Simulate External Systems (e.g. Unifi App / Mobile Network Aggregator) pushing Data
        # This is where the real-time "Airtime" and "Transaction" data comes from.
        print(f"\n[Step 1.5] Simulating Real-time Data Push (Airtime & Mobile Money)...")
        alt_data_payload = {
            "borrower_id": borrower_id,
            "airtime_usage_avg": 500.0, # High usage = correlated with higher repayment in some models
            "mobile_money_history": [
                {"transaction_id": "TX1001", "amount": 5000, "type": "DEPOSIT", "timestamp": "2024-03-01T10:00:00"},
                {"transaction_id": "TX1002", "amount": 2000, "type": "PAYMENT", "timestamp": "2024-03-05T14:30:00"},
                {"transaction_id": "TX1003", "amount": 1500, "type": "TRANSFER", "timestamp": "2024-03-10T09:15:00"}
            ],
            "utility_history": [
                {"utility_name": "ZESCO", "amount": 500, "timestamp": "2024-03-01T00:00:00", "status": "PAID"}
            ]
        }
        
        resp_data = requests.post(f"{BASE_URL}/borrower/data/upload", json=alt_data_payload, headers=headers)
        if resp_data.status_code == 200:
            print("[OK] Data Ingestion Success! Engine now has behavioral context.")
        else:
            print(f"[WARN] Data Ingestion Failed: {resp_data.text}")
        
        # 2. Run Assessment
        print(f"\n[Step 2] Running Assessment via {BASE_URL}/assessment/run...")
        # Note: endpoint expects {"borrower_id": "..."} wrapped in body keywords if embed=True?
        # The signature is borrower_id: str = Body(..., embed=True)
        # So payload should be {"borrower_id": "..."}
        assess_payload = {"borrower_id": borrower_id}
        
        resp2 = requests.post(f"{BASE_URL}/assessment/run", json=assess_payload, headers=headers)
        
        print(f"Status Code: {resp2.status_code}")
        if resp2.status_code == 200:
            print("\n[OK] Assessment Result:")
            print(json.dumps(resp2.json(), indent=2))
        else:
            print(f"\n[FAIL] Assessment Failed: {resp2.text}")

    except Exception as e:
        print(f"\n[FAIL] Request failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_assessment.py <YOUR_API_KEY>")
        print("Example: python test_assessment.py sk_live_12345...")
        sys.exit(1)
        
    api_key = sys.argv[1]
    run_test(api_key)

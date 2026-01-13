import requests
import json
import time

API_BASE = "http://127.0.0.1:8000"
OFFICER_KEY = "mfi-officer-admin-key"

def run_self_healing_test():
    print("--- Starting Phase 6: Self-Healing AI Stress Test ---")
    headers = {"X-API-KEY": OFFICER_KEY}
    
    # 1. Create 5 Assessments and Disburse them
    loan_ids = []
    for i in range(5):
        print(f"Submitting Application {i+1}...")
        borrower_data = {
            "name": f"Loop Tester {i}",
            "phone": f"+260900000{i:03d}",
            "employment_type": "trader",
            "monthly_income": 2000.0,
            "monthly_expenses": 500.0,
            "existing_debt": 100.0,
            "loan_amount_requested": 500.0,
            "loan_purpose": "Inventory growth"
        }
        
        # Intake
        res = requests.post(f"{API_BASE}/intake/start", json=borrower_data)
        bid = res.json()["borrower_id"]
        
        # Assessment
        res = requests.post(f"{API_BASE}/assessment/run", json={"borrower_id": bid})
        aid = res.json()["assessment_id"]
        
        # Disburse
        res = requests.post(f"{API_BASE}/loan/disburse", json={"assessment_id": aid}, headers=headers)
        lid = res.json()["loan_id"]
        loan_ids.append(lid)
        print(f"  -> Disbursed Loan: {lid}")

    print("\n--- Phase 2: Simulating Outcomes to Trigger Retraining ---")
    # Mark 5 loans as PAID to hit the RETRAIN_THRESHOLD=5
    for i, lid in enumerate(loan_ids):
        status = "PAID" if i % 2 == 0 else "DEFAULTED"
        print(f"Closing Loan {lid} as {status}...")
        requests.post(f"{API_BASE}/loan/status", json={"loan_id": lid, "status": status}, headers=headers)
        time.sleep(1) # Small delay for logging

    print("\n✅ Outcomes submitted. Checking server logs for 'SELF-HEALING' trigger...")
    print("Wait 5-10 seconds for asynchronous retraining to finish.")
    
    # Wait and check Audit logs
    time.sleep(10)
    print("\n--- Verification: Checking Audit Logs for Retraining Event ---")
    # In a real test, we would hit an Audit API, for now we look at terminal output.
    print("Test finished. Please check the 'uvicorn' terminal for 'SELF-HEALING: Background retraining started' message.")

if __name__ == "__main__":
    run_self_healing_test()

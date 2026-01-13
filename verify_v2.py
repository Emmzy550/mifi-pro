import requests
import json
import time

API_BASE = "http://127.0.0.1:8000"
OFFICER_KEY = "mfi-admin-key"

def test_v2_flow():
    print("--- Starting V2 Stress Test: Thin-File Borrower ---")
    
    # 1. Intake
    borrower_data = {
        "name": "Sarah Mobile",
        "phone": "+260977123456",
        "employment_type": "trader",
        "monthly_income": 300.0, # Low income, might fail V1 rules
        "monthly_expenses": 150.0,
        "existing_debt": 0.0,
        "loan_amount_requested": 500.0,
        "loan_purpose": "Stock for market stall"
    }
    
    res = requests.post(f"{API_BASE}/intake/start", json=borrower_data)
    borrower_id = res.json()["borrower_id"]
    print(f"Intake Success: {borrower_id}")
    
    # 2. Upload Alternative Data (Next-Gen V2 Feature)
    alt_data = {
        "borrower_id": borrower_id,
        "mobile_money_history": [
            {"transaction_id": "T1", "amount": 100.0, "type": "DEPOSIT", "timestamp": "2024-01-01T10:00:00"},
            {"transaction_id": "T2", "amount": 200.0, "type": "DEPOSIT", "timestamp": "2024-01-05T10:00:00"},
            {"transaction_id": "T3", "amount": 50.0, "type": "PAYMENT", "timestamp": "2024-01-10T10:00:00"}
        ],
        "utility_history": [
            {"utility_name": "Power", "amount": 20.0, "timestamp": "2024-01-15T10:00:00", "status": "PAID"}
        ],
        "airtime_usage_avg": 45.0
    }
    
    headers = {"X-API-KEY": OFFICER_KEY}
    res = requests.post(f"{API_BASE}/borrower/data/upload", json=alt_data, headers=headers)
    print(f"Alt Data Upload: {res.json()['status']}")
    
    # 3. Run Assessment
    res = requests.post(f"{API_BASE}/assessment/run", json={"borrower_id": borrower_id})
    assessment = res.json()
    
    print("\n--- Assessment Results ---")
    print(f"Risk Level: {assessment['risk_level']}")
    print(f"Rule Score: {assessment['rule_based_score']:.2f}")
    print(f"ML Score (PD): {assessment['ml_based_score']:.2f}")
    print(f"Final Ensemble Score: {assessment['risk_score']:.2f}")
    print(f"AI Reasoning: {assessment['explanation']}")
    
    # 4. Check Audit Logs
    res = requests.get(f"{API_BASE}/borrowers", headers=headers)
    print(f"\nAudit: Borrowers in DB: {len(res.json())}")

if __name__ == "__main__":
    # Ensure server is running or wait
    try:
        test_v2_flow()
    except Exception as e:
        print(f"Test failed: {e}")

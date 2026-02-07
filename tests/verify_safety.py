import requests
import json

API_BASE = "http://127.0.0.1:8000"

def test_high_risk_rejection():
    print("--- Starting Safety Verification: High-Risk Rejection ---")
    
    # 1. Intake a borrower with extreme debt (DTI > 0.4)
    borrower_data = {
        "name": "Debt Heavy",
        "phone": "+260900000001",
        "employment_type": "trader",
        "monthly_income": 1000.0,
        "monthly_expenses": 200.0,
        "existing_debt": 900.0, # 90% DTI - Should be a CRITICAL failure
        "loan_amount_requested": 100.0,
        "loan_purpose": "Emergency"
    }
    
    res = requests.post(f"{API_BASE}/intake/start", json=borrower_data)
    borrower_id = res.json()["borrower_id"]
    print(f"Intake Success: {borrower_id}")
    
    # 2. Run Assessment
    res = requests.post(f"{API_BASE}/assessment/run", json={"borrower_id": borrower_id})
    assessment = res.json()
    
    print("\n--- Assessment Results ---")
    print(f"Risk Level: {assessment['risk_level']}")
    print(f"Decision: {assessment['decision']}")
    print(f"Flags: {assessment['flags']}")
    print(f"Explanation: {assessment['explanation']}")
    
    if assessment['decision'] == 'REJECT':
        print("\n✅ PASS: High-risk borrower correctly rejected.")
    else:
        print("\n❌ FAIL: High-risk borrower was NOT rejected.")

if __name__ == "__main__":
    test_high_risk_rejection()

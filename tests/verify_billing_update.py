
import requests
import uuid
import sys
import os

# Add root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.user import User, UserRole
from models.organization import Organization, BillingPlan, BillingStatus
from utils.db import Database
from agents.auth_agent import AuthAgent

def get_auth_token(email="billing_test@example.com", password="password123"):
    login_url = "http://localhost:8000/auth/login"
    res = requests.post(login_url, data={"username": email, "password": password})
    if res.status_code != 200:
        raise Exception(f"Login failed: {res.text}")
    return res.json()["access_token"]

def verify_billing_flow():
    try:
        token = get_auth_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 1. Get Initial Usage
        print("1. Fetching initial usage...")
        res = requests.get("http://localhost:8000/billing/usage", headers=headers)
        initial_usage = res.json()["usage_count"]
        print(f"   Initial Usage: {initial_usage}")
        
        # 2. Create Borrower (Intake)
        print("\n2. Creating test borrower...")
        borrower_data = {
            "name": "Billing Check Borrower",
            "phone": "+254711122233",
            "employment_type": "salaried",
            "monthly_income": 5000,
            "monthly_expenses": 2000,
            "existing_debt": 0,
            "loan_amount_requested": 1000,
            "loan_purpose": "Test Billing Increment",
            "organization_id": "ORG-BILLING-TEST" 
        }
        
        # Intake endpoint is public but we should link to our ORG
        res = requests.post("http://localhost:8000/intake/start", json=borrower_data)
        if res.status_code != 200:
            print(f"Intake failed: {res.text}")
            exit(1)
            
        borrower_id = res.json()["borrower_id"]
        print(f"   Borrower Created: {borrower_id}")
        
        # 3. Run Assessment
        print(f"\n3. Running Assessment for {borrower_id}...")
        res = requests.post(
            "http://localhost:8000/assessment/run", 
            json={"borrower_id": borrower_id},
            headers=headers # Pass headers if authentication is needed, though currently public but good practice
        )
        
        if res.status_code != 200:
            print(f"Assessment failed: {res.status_code} {res.text}")
            exit(1)
            
        print("   Assessment Complete!")
        
        # 4. Verify Usage Update
        print("\n4. Verifying usage update...")
        res = requests.get("http://localhost:8000/billing/usage", headers=headers)
        final_usage = res.json()["usage_count"]
        print(f"   Final Usage: {final_usage}")
        
        if final_usage == initial_usage + 1:
            print("\n[SUCCESS] usage_count incremented by 1.")
        else:
            print(f"\n[FAIL] Usage mismatch! Expected {initial_usage + 1}, got {final_usage}")
            exit(1)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        exit(1)

if __name__ == "__main__":
    verify_billing_flow()

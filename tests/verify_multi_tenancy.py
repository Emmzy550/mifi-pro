
import requests
import sys
import uuid
import time

# Helper colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

BASE_URL = "http://localhost:8001"

def log(msg, success=None):
    if success is True:
        print(f"{GREEN}[PASS]{RESET} {msg}")
    elif success is False:
        print(f"{RED}[FAIL]{RESET} {msg}")
    else:
        print(f"[INFO] {msg}")

def run_test():
    # 1. Setup Data - We need to manually create 2 orgs and keys via Python/File manipulation 
    # OR we can assume they exist. Since we don't have endpoints to create Orgs easily without Super Admin,
    # we will rely on `test_assessment.py` logic or better yet, use the `AuthAgent` creates directly?
    # Actually, we can just start the server and use the 'seed' logic or use existing keys.
    # BUT, to be rigorous, let's create new keys locally using a helper script logic.
    
    # We will assume the server is running.
    # We will try to use the legacy keys first to verify they still work, then try cross-access.
    
    # Key A: mfi-officer-admin-key (Default Org)
    KEY_A = "mfi-officer-admin-key" 
    ORG_A = "DEFAULT_ORG"
    
    # Key B: mfi-b-officer-key (MFI_B_ZAMBIA)
    KEY_B = "mfi-b-officer-key"
    ORG_B = "MFI_B_ZAMBIA"
    
    # STEP 1: Assessment Isolation
    log("Testing Assessment Isolation...")
    
    # 1.1 Create Borrower A in Org A (using Intake - currently public)
    # We need to manually inject a borrower into Org A if intake is public but we want to be sure.
    payload_a = {
        "name": "Borrower A", "phone": "+111", "email": "a@test.com", "employment_type": "salaried",
        "monthly_income": 1000, "monthly_expenses": 500, "loan_amount_requested": 100,
        "loan_purpose": "test", "organization_id": ORG_A
    }
    resp = requests.post(f"{BASE_URL}/intake/start", json=payload_a)
    if resp.status_code != 200:
        log("Failed to create Borrower A", False)
        return
    bor_a_id = resp.json()["borrower_id"]
    log(f"Created Borrower A ({bor_a_id}) in {ORG_A}", True)
    
    # 1.2 Run Assessment for Borrower A using Key A (Should work)
    headers_a = {"X-API-KEY": KEY_A}
    resp = requests.post(f"{BASE_URL}/assessment/run", json={"borrower_id": bor_a_id}, headers=headers_a)
    if resp.status_code == 200:
        log("Key A accessed Borrower A assessment", True)
        asmt_id = resp.json()["assessment_id"]
    else:
        log(f"Key A failed to assess Borrower A: {resp.text}", False)
        return

    # 1.3 Try to access Borrower A assessment using Key B (Should FAIL)
    headers_b = {"X-API-KEY": KEY_B}
    resp = requests.get(f"{BASE_URL}/assessment/result/{asmt_id}", headers=headers_b)
    if resp.status_code == 404:
         log("Key B blocked from reading Assessment A (404 Not Found)", True)
    else:
         log(f"Key B COULD read Assessment A! Status: {resp.status_code}", False)

    # 1.4 Try to Run Assessment for Borrower A using Key B (Should FAIL)
    resp = requests.post(f"{BASE_URL}/assessment/run", json={"borrower_id": bor_a_id}, headers=headers_b)
    if resp.status_code == 404:
        log("Key B blocked from running assessment on Borrower A (404 Not Found)", True)
    else:
        log(f"Key B COULD run assessment on Borrower A! Status: {resp.status_code}", False)
        
    # STEP 2: Dashboard/List Isolation
    log("\nTesting List Isolation...")
    resp = requests.get(f"{BASE_URL}/assessments", headers=headers_a)
    if resp.status_code == 200:
        items = resp.json()
        # Verify all items belong to Org A
        bad_items = [i for i in items if i["organization_id"] != ORG_A]
        if not bad_items:
            log(f"Key A saw {len(items)} assessments, all from {ORG_A}", True)
        else:
            log(f"Key A saw {len(bad_items)} assessments from OTHER orgs!", False)
            
    # STEP 3: API Key Auth Checks
    log("\nTesting Auth Checks...")
    resp = requests.get(f"{BASE_URL}/assessments", headers={"X-API-KEY": "INVALID_KEY"})
    if resp.status_code == 403:
        log("Invalid Key rejected (403)", True)
    else:
        log(f"Invalid Key accepted?! {resp.status_code}", False)

if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        log(f"Test crashed: {e}", False)

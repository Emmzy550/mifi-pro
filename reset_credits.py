
import sys
import os

# Add root directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.db import Database
from models.organization import Organization

def reset_credits():
    print("resetting credits...")
    db = Database.get_db()
    
    # We want to reset "USER_TEST_ORG" (limit 10) and potentially others
    # Since we are using MockFirestore (likely), we can iterate collections
    
    # In utils/db.py, Database has get_organization but no list_organizations?
    # Let's check if we can list them or just target the specific one.
    # The user specifically mentioned "10 credits", which matches USER_TEST_ORG from test_billing_key.py
    
    target_orgs = ["USER_TEST_ORG", "ORG-BILLING-TEST", "DEFAULT_ORG"]
    
    for org_id in target_orgs:
        org = Database.get_organization(org_id)
        if org:
            print(f"Found org: {org.id} (Current Usage: {org.usage_count}/{org.monthly_limit})")
            org.usage_count = 0
            # Ensure stats are active
            org.billing_status = "active" 
            Database.save_organization(org)
            print(f"-> Reset usage to 0 for {org.id}")
        else:
            print(f"Org {org_id} not found.")

if __name__ == "__main__":
    reset_credits()

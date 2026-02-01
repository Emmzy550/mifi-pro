import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import Database

def find_user_and_org(email):
    print(f"=== Searching for user: {email} ===")
    
    # We don't have a direct get_user_by_email in Database based on typical patterns, 
    # but let's check what's available or use Firestore directly.
    db = Database.get_db()
    users_ref = db.collection("users").where("email", "==", email).stream()
    
    user_found = False
    for user_doc in users_ref:
        user_data = user_doc.to_dict()
        user_found = True
        print(f"User Found: {user_data.get('email')}")
        print(f"Role: {user_data.get('role')}")
        org_id = user_data.get('organization_id')
        print(f"Organization ID: {org_id}")
        
        if org_id:
            org = Database.get_organization(org_id)
            if org:
                print(f"Org Name: {org.name}")
                print(f"Org Plan: {org.plan}")
                print(f"Org Payment Status: {org.payment_status}")
                print(f"Org Environment: {org.environment}")
            else:
                print("Organization record not found for ID.")
                
            # Check payments
            payments = Database.list_payments(org_id)
            print(f"\nPayments for Org ({len(payments)}):")
            for p in payments:
                print(f"- ID: {p.payment_id}, Status: {p.status}, Plan: {p.plan}, Gateway: {p.gateway}, Time: {p.timestamp}")

    if not user_found:
        print("User not found.")

if __name__ == "__main__":
    find_user_and_org("abc@gmail.com")

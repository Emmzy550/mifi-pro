import sys
import os
from utils.db import Database
from models.organization import Organization

def inspect_org(org_id):
    print(f"--- Inspecting Org: {org_id} ---")
    
    # Force DB init
    Database.get_db()
    
    org = Database.get_organization(org_id)
    if not org:
        print("Organization not found in DB.")
        return

    print(f"ID: {org.id}")
    print(f"Name: {org.name}")
    print(f"Environment: {org.environment} (Raw: {org.environment.value if hasattr(org.environment, 'value') else org.environment})")
    print(f"Plan: {org.plan} (Raw: {org.plan.value if hasattr(org.plan, 'value') else org.plan})")
    print(f"Billing Status: {org.billing_status} (Raw: {org.billing_status.value if hasattr(org.billing_status, 'value') else org.billing_status})")
    print(f"Payment Status: {org.payment_status} (Raw: {org.payment_status.value if hasattr(org.payment_status, 'value') else org.payment_status})")
    print(f"Last Payment ID: {org.last_payment_id}")
    
    if org.last_payment_id:
        print(f"\n--- Last Payment Details ({org.last_payment_id}) ---")
        payment = Database.get_payment(org.last_payment_id)
        if payment:
            print(f"ID: {payment.payment_id}")
            print(f"Status: {payment.status}")
            print(f"Gateway: {payment.gateway}")
            print(f"Transaction ID: {payment.transaction_id}")
        else:
            print("Payment record not found.")

if __name__ == "__main__":
    inspect_org("ORG-B328EF63")

import sys
import os
from utils.db import Database
from models.organization import Organization, PaymentStatus as AppPaymentStatus
from agents.payment_agent import PaymentAgent

def simulate_webhook(org_id):
    print(f"--- Simulating Successful Payment for: {org_id} ---")
    
    # Force DB init
    Database.get_db()
    
    org = Database.get_organization(org_id)
    if not org:
        print("Organization not found.")
        return

    if not org.last_payment_id:
        print("No pending payment found to confirm.")
        return

    payment = Database.get_payment(org.last_payment_id)
    if not payment:
         print(f"Payment record {org.last_payment_id} not found.")
         return

    print(f"Found Pending Payment: {payment.payment_id} ({payment.amount} {payment.currency})")
    
    # Simulate what handle_webhook does
    payment.status = AppPaymentStatus.PAID
    print("Marking Payment as PAID...")
    Database.save_payment(payment)
    
    print("Activating Organization Plan...")
    PaymentAgent._activate_org_plan(payment)
    
    # verify
    updated_org = Database.get_organization(org_id)
    print("\n--- FINAL STATE ---")
    print(f"Org Status: {updated_org.status}")
    print(f"Environment: {updated_org.environment}")
    print(f"Payment Status: {updated_org.payment_status}")
    print(f"Billing Status: {updated_org.billing_status}")
    
    if updated_org.payment_status == "PAID" and updated_org.environment == "PRODUCTION":
        print("\n✅ SUCCESS: Production Unlocked!")
    else:
        print("\n❌ FAILED: Still locked.")

if __name__ == "__main__":
    simulate_webhook("ORG-B328EF63")

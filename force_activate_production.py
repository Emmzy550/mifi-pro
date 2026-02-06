
from utils.db import Database
from models.organization import Organization, PaymentStatus
from models.payment import Payment, PaymentStatus as AppPaymentStatus
from agents.payment_agent import PaymentAgent
from datetime import datetime, timezone

def force_activate(org_id):
    print(f"--- Force Activating Production for {org_id} ---")
    db = Database.get_db()
    
    # 1. Get Org
    org = Database.get_organization(org_id)
    if not org:
        print(f"Error: Org {org_id} not found")
        return

    # 2. Find latest pending payment
    payments = db.collection('payments').where('org_id', '==', org_id).where('status', '==', 'PENDING').stream()
    latest_payment = None
    for p in payments:
        data = p.to_dict()
        if not latest_payment or data.get('timestamp') > latest_payment['timestamp']:
            latest_payment = data
            latest_payment['id'] = p.id

    if not latest_payment:
        print("No pending payment found for this org. Creating a mock successful payment...")
        # Create a mock payment for Starter plan
        import uuid
        payment_id = f"PAY-MOCK-{uuid.uuid4().hex[:6].upper()}"
        payment = Payment(
            payment_id=payment_id,
            org_id=org_id,
            plan="STARTER",
            amount=1.0,
            currency="ZMW",
            gateway="LIPILA",
            status=AppPaymentStatus.PAID,
            transaction_id=f"MOCK-TXN-{uuid.uuid4().hex[:6].upper()}"
        )
    else:
        print(f"Found pending payment: {latest_payment['id']}")
        # Load as Payment model
        payment = Database.get_payment(latest_payment['id'])
        payment.status = AppPaymentStatus.PAID
    
    # 3. Save Payment
    Database.save_payment(payment)
    
    # 4. Activate Plan (using the agent's logic for consistency)
    PaymentAgent._activate_org_plan(payment)
    
    print(f"SUCCESS: Organization {org_id} is now on {payment.plan} plan in PRODUCTION environment.")

if __name__ == "__main__":
    force_activate("ORG-6C1D2BA5")

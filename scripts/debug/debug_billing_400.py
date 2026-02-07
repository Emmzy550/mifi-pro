import sys
import os
import uuid
from typing import Dict, Optional

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import Database
from models.organization import Organization, OrgStatus, PaymentStatus as OrgPaymentStatus, OrgEnvironment
from agents.payment_agent import PaymentAgent
from models.user import User, UserRole

def test_upgrade_logic():
    print("=== Testing /billing/upgrade Logic ===")
    
    # Setup Mock Data
    org_id = "ORG-DEBUG-123"
    test_org = Organization(
        id=org_id,
        name="Debug Org",
        plan="SANDBOX",
        status=OrgStatus.ACTIVE,
        environment=OrgEnvironment.SANDBOX,
        payment_status=OrgPaymentStatus.UNPAID
    )
    Database.save_organization(test_org)
    
    plans_to_test = ["STARTER", "GROWTH", "starter", "growth"]
    gateways_to_test = ["LIPILA", "BANK", "STRIPE"]
    
    for plan in plans_to_test:
        for gateway in gateways_to_test:
            print(f"\nTesting Plan: {plan}, Gateway: {gateway}")
            try:
                # Simulate what api.py does
                # 1. Validation in api.py
                from pricing_config import PLAN_CONFIG
                if plan.upper() not in PLAN_CONFIG:
                   print(f"❌ API level validation failed: Invalid plan {plan}")
                   continue
                
                # 2. Call initiate_payment
                res = PaymentAgent.initiate_payment(
                    org=test_org,
                    plan_name=plan,
                    gateway=gateway,
                    extra_data={"phone_number": "0970000000" if gateway == "LIPILA" else None}
                )
                print(f"✅ Success: {res.get('status')} - {res.get('message')}")
            except ValueError as e:
                print(f"❌ ValueError (400): {e}")
            except Exception as e:
                print(f"❌ Unexpected Error (500): {e}")

if __name__ == "__main__":
    test_upgrade_logic()

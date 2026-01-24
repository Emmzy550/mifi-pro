
from models.organization import Organization, BillingPlan, PaymentStatus
import json

def test_serialization():
    org = Organization(id="TEST", name="Test Org", plan=BillingPlan.GROWTH)
    print(f"Org Object: {org}")
    print(f"Payment Status: {org.payment_status}")
    
    dump = org.model_dump(mode='json')
    print("\n--- Model Dump (mode='json') ---")
    print(json.dumps(dump, indent=2))
    
    if "payment_status" in dump:
        print("\nSUCCESS: payment_status is in the dump")
    else:
        print("\nFAILURE: payment_status is MISSING from the dump")

if __name__ == "__main__":
    test_serialization()

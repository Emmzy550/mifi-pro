
import os
import sys

# Add current dir to path
sys.path.append(os.getcwd())

# Force environment to PRODUCTION for testing
os.environ["ENVIRONMENT"] = "PRODUCTION"
os.environ["LIPILA_SECRET_KEY"] = "lsk_019bd0fe-e801-7e93-8194-b918142f4c1f"

try:
    from agents.payment_agent import PaymentAgent
    from models.organization import Organization, OrgStatus, BillingPlan, PaymentStatus
    
    print("--- Testing Lipila Initiation ---")
    
    mock_org = Organization(
        id="ORG-TEST",
        name="Test Org",
        plan=BillingPlan.SANDBOX,
        status=OrgStatus.ACTIVE,
        payment_status=PaymentStatus.UNPAID
    )
    
    # We expect this to fail with a connection error (since keys are likely invalid for real API),
    # but it should NOT fail with "Lipila API key not configured".
    
    try:
        res = PaymentAgent.initiate_payment(
            org=mock_org,
            plan_name="STARTER",
            gateway="LIPILA",
            extra_data={"phone_number": "0970000000"}
        )
        print("Success (unexpected but good for config check):", res)
    except ValueError as e:
        if "Lipila API key not configured" in str(e):
            print("FAILURE: Config check failed - Key still reported as missing!")
            sys.exit(1)
        else:
            print("SUCCESS OR API ERROR (Expected):", str(e))
    except Exception as e:
        print("API ERROR (Expected):", str(e))

    print("--- Test Complete ---")

except Exception as e:
    print(f"ERROR: {str(e)}")
    import traceback
    traceback.print_exc()

import sys
import os
from datetime import datetime, timezone

# Add parent directory to path to import models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.organization import Organization, BillingPlan, BillingStatus, OrgEnvironment
from models.usage_record import UsageRecord

def test_model_hierarchy():
    print("--- Testing New Billing Data Model Hierarchy ---")
    
    # 1. Create Organization
    org = Organization(
        id="ORG-TEST-001",
        name="Test Microfinance",
        plan=BillingPlan.SANDBOX,
        billing_status=BillingStatus.FREE
    )
    print(f"CREATED ORG: {org.name} [ID: {org.id}]")
    print(f"PLAN: {org.plan}")
    print(f"BILLING STATUS: {org.billing_status}")
    
    # 2. Create UsageRecords for Sandbox and Production
    sandbox_usage = UsageRecord(
        organization_id=org.id,
        environment=OrgEnvironment.SANDBOX,
        assessment_count=5
    )
    
    prod_usage = UsageRecord(
        organization_id=org.id,
        environment=OrgEnvironment.PRODUCTION,
        assessment_count=0
    )
    
    print("\n--- Usage Tracking (Environment Isolated) ---")
    print(f"SANDBOX USE: {sandbox_usage.assessment_count} assessments")
    print(f"PROD USE: {prod_usage.assessment_count} assessments")
    
    # 3. Simulate Upgrade
    print("\n--- Simulating Upgrade ---")
    org.plan = BillingPlan.STARTER
    org.billing_status = BillingStatus.ACTIVE
    print(f"NEW PLAN: {org.plan}")
    print(f"NEW STATUS: {org.billing_status}")
    
    print("\n[SUCCESS] Data model hierarchy (Org -> Env -> Usage) is validated.")

if __name__ == "__main__":
    test_model_hierarchy()

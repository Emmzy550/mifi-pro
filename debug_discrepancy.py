
import sys
import os

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import Database
from models.organization import OrgEnvironment

TARGET_ORG_ID = "ORG-44141161"

def check_discrepancy():
    print(f"Checking Logic Discrepancy for {TARGET_ORG_ID}...")

    # 1. Total Assessments
    assessments = Database.list_assessments(TARGET_ORG_ID)
    print(f"Total Assessments in DB: {len(assessments)}")
    if assessments:
        print(f"Last Assessment ID: {assessments[-1].assessment_id}")
        # Timestamp not in model

    # 2. Usage Records
    print("\nUsage Records:")
    sandbox_usage = Database.get_usage_record(TARGET_ORG_ID, OrgEnvironment.SANDBOX)
    prod_usage = Database.get_usage_record(TARGET_ORG_ID, OrgEnvironment.PRODUCTION)
    
    print(f"SANDBOX: Count={sandbox_usage.assessment_count}")
    print(f"    Period: {sandbox_usage.period_start} to {sandbox_usage.period_end}")
    print(f"    Last Updated: {sandbox_usage.last_updated}")
    
    print(f"PRODUCTION: Count={prod_usage.assessment_count}")
    print(f"    Period: {prod_usage.period_start} to {prod_usage.period_end}")

    # 3. Check for logic mismatch
    total_usage = sandbox_usage.assessment_count + prod_usage.assessment_count
    print(f"\nTotal Usage (Sandbox+Prod): {total_usage}")
    print(f"Assessment Count Discrepancy: {len(assessments) - total_usage}")

if __name__ == "__main__":
    check_discrepancy()

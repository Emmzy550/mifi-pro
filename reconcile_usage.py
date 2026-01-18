
import sys
import os
from datetime import datetime, timezone

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import Database
from models.organization import OrgEnvironment

TARGET_ORG_ID = "ORG-44141161"

def reconcile():
    print(f"Starting Reconciliation for {TARGET_ORG_ID}...")
    
    # 1. Count Assessments
    assessments = Database.list_assessments(TARGET_ORG_ID)
    actual_count = len(assessments)
    print(f"Actual Assessment Count: {actual_count}")
    
    # 2. Get Usage Record (Sandbox)
    # Assuming assessments are Sandbox for now, or we treat them as such for the fix
    record = Database.get_usage_record(TARGET_ORG_ID, OrgEnvironment.SANDBOX)
    print(f"Current Usage Record Count: {record.assessment_count}")
    
    if record.assessment_count == actual_count:
        print("✅ Counts already match. No action needed.")
        return

    # 3. Update Record
    print(f"Updating Usage Record from {record.assessment_count} to {actual_count}...")
    record.assessment_count = actual_count
    record.last_updated = datetime.now(timezone.utc)
    
    # Ensure environment is strictly "SANDBOX" (Enum value)
    record.environment = OrgEnvironment.SANDBOX
    
    Database.save_usage_record(record)
    print("✅ Usage Record Updated Successfully.")
    
    # Verify
    new_record = Database.get_usage_record(TARGET_ORG_ID, OrgEnvironment.SANDBOX)
    print(f"Verification: New Count in DB = {new_record.assessment_count}")

if __name__ == "__main__":
    reconcile()

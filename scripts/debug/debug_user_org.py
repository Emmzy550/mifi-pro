
import sys
import os

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import Database
from models.organization import OrgEnvironment

TARGET_EMAIL = "mwape@gmail.com"

def check_user_org():
    print(f"Checking details for {TARGET_EMAIL}...")
    
    # 1. Find User
    user = Database.get_user_by_email(TARGET_EMAIL)
    if not user:
        print(f"❌ User {TARGET_EMAIL} NOT FOUND in database.")
        print("Listing all users:")
        all_users = Database.list_users() # Assuming this method exists or we can mock it
        # Database.list_users() might not exist, let's check `Database.users` if it's an in-memory DB or similar
        # Based on previous file reads, Database methods are static.
        return

    print(f"✅ User Found: {user.email} (ID: {user.id})")
    print(f"   Organization ID: {user.organization_id}")
    print(f"   Role: {user.role}")
    
    # 2. Check Organization
    org = Database.get_organization(user.organization_id)
    if not org:
        print(f"❌ Organization {user.organization_id} NOT FOUND.")
    else:
        print(f"✅ Organization Found: {org.name} (Plan: {org.plan.value})")
        
    # 3. Check Usage
    print("\nUsage Records:")
    for env in [OrgEnvironment.SANDBOX, OrgEnvironment.PRODUCTION]:
        record = Database.get_usage_record(user.organization_id, env)
        print(f"   - {env.value}: {record.assessment_count} assessments (Limit: {record.period_end})")

if __name__ == "__main__":
    check_user_org()

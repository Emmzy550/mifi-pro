from utils.db import Database
from models.organization import OrgEnvironment

def debug_billing():
    print("--- Billing Diagnostics ---")
    
    # 1. Try to find the user
    user = Database.get_user_by_email("mwape@gmail.com")
    if not user:
        print("User mwape@gmail.com not found.")
        # List all users to be sure
        users = Database.list_all_users()
        print(f"Total Users in DB: {len(users)}")
        if users:
            user = users[0]
            print(f"Using first user: {user.email} (Org: {user.organization_id})")
        else:
            return

    org_id = user.organization_id
    print(f"Found User: {user.email}, Org ID: {org_id}")
    
    # 2. Check Organization
    org = Database.get_organization(org_id)
    if not org:
        print(f"Organization {org_id} not found!")
    else:
        print(f"Org Plan: {org.plan}, Status: {org.status}")
    
    # 3. List Usage Records
    records = Database.list_usage_records(org_id)
    print(f"Database.list_usage_records results ({len(records)}):")
    for r in records:
        print(f" - Record: Env={r.environment}, Usage={r.assessment_count}")
        
    # 4. Manual collection check (bypass list_usage_records)
    db = Database.get_db()
    raw_docs = db.collection("usage_records").stream()
    print("\nRaw usage_records collection:")
    for doc in raw_docs:
        print(f" - Doc ID: {doc.id}, Data: {doc.to_dict()}")

if __name__ == "__main__":
    debug_billing()

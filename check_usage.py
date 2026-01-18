from utils.db import Database
from models.organization import OrgEnvironment

def diagnose():
    print("=== Billing Diagnostics ===\n")
    
    # Get first user
    users = Database.list_all_users()
    if not users:
        print("No users found")
        return
    
    user = users[0]
    org_id = user.organization_id
    print(f"User: {user.email}")
    print(f"Org ID: {org_id}\n")
    
    # Get organization
    org = Database.get_organization(org_id)
    if org:
        print(f"Org Plan: {org.plan}")
        print(f"Org Status: {org.status}\n")
    
    # Check usage records via list
    print("--- Via list_usage_records() ---")
    records = Database.list_usage_records(org_id)
    print(f"Found {len(records)} records")
    for r in records:
        print(f"  Env: {r.environment}, Count: {r.assessment_count}")
    
    # Check usage records directly
    print("\n--- Direct Firestore Query ---")
    db = Database.get_db()
    all_docs = db.collection("usage_records").stream()
    for doc in all_docs:
        data = doc.to_dict()
        print(f"  Doc ID: {doc.id}")
        print(f"  Data: {data}")
    
    # Try get_usage_record for both environments
    print("\n--- Via get_usage_record() ---")
    sandbox_rec = Database.get_usage_record(org_id, OrgEnvironment.SANDBOX)
    print(f"Sandbox: {sandbox_rec.assessment_count}")
    
    prod_rec = Database.get_usage_record(org_id, OrgEnvironment.PRODUCTION)
    print(f"Production: {prod_rec.assessment_count}")

if __name__ == "__main__":
    diagnose()

from utils.db import Database
from models.borrower import Borrower
from models.api_key import APIKey
import json
import os

def inspect():
    results = []
    
    def log(msg):
        print(msg)
        results.append(msg)

    # 1. Check specific borrower from Postman image
    borrower_id = "BOR-D361F870"
    borrower = Database.get_borrower(borrower_id)
    
    log(f"--- Borrower Inspection ({borrower_id}) ---")
    if borrower:
        log(f"ID: {borrower.id}")
        log(f"Organization ID: {borrower.organization_id}")
    else:
        log("Borrower NOT FOUND in Database.")
        # List all borrowers to see what we have
        all_borrowers = Database.list_borrowers()
        log(f"\nTotal Borrowers: {len(all_borrowers)}")
        for b in all_borrowers:
            log(f"- {b.id} (Org: {b.organization_id})")

    # 2. Check Organizations
    orgs = Database.list_organizations()
    log(f"\n--- Organizations ({len(orgs)}) ---")
    for org in orgs:
        log(f"- {org.id}: {org.name} (Status: {org.status})")

    # 3. Check Users
    users = Database.list_all_users()
    log(f"\n--- Users ({len(users)}) ---")
    for user in users:
        log(f"- {user.email} (Org: {user.organization_id}, Role: {user.role})")

    # 4. Check API Keys
    db = Database.get_db()
    try:
        keys_col = db.collection("api_keys").stream()
        log(f"\n--- API Keys ---")
        for k_doc in keys_col:
            k = k_doc.to_dict()
            log(f"- Prefix: {k.get('key_prefix')} (Org: {k.get('organization_id')}, Status: {k.get('status')})")
    except Exception as e:
        log(f"\nCould not list API keys: {e}")

    with open("inspection_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    print(f"Results saved to inspection_results.txt")

if __name__ == "__main__":
    inspect()

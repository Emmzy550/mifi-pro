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

    # 1. Check specific borrower from NEW Postman image
    borrower_id = "BOR-DF563B0F"
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
            if b.id == borrower_id:
                 log(f"!!! FOUND BY LISTING: {b.id} (Org: {b.organization_id})")

    # 2. Check recent Audit Logs
    try:
        from agents.audit_agent import AuditAgent
        logs = AuditAgent.list_logs(limit=20)
        log(f"\n--- Recent Audit Logs ---")
        for entry in logs:
            log(f"[{entry.get('timestamp')}] {entry.get('event_type')} - {entry.get('user')} - {json.dumps(entry.get('metadata'))}")
    except Exception as e:
        log(f"Could not fetch audit logs: {e}")

    # 3. Check All API Keys and their Orgs
    db = Database.get_db()
    try:
        keys_col = db.collection("api_keys").stream()
        log(f"\n--- API Keys ---")
        for k_doc in keys_col:
            k = k_doc.to_dict()
            log(f"- Prefix: {k.get('key_prefix')} (Org: {k.get('organization_id')}, Status: {k.get('status')}, Name: {k.get('name')})")
    except Exception as e:
        log(f"\nCould not list API keys: {e}")

    with open("inspection_results_v2.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    print(f"Results saved to inspection_results_v2.txt")

if __name__ == "__main__":
    inspect()

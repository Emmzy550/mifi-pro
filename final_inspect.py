from utils.db import Database
from models.borrower import Borrower
from agents.audit_agent import AuditAgent
import json

def final_inspect():
    borrower_id = "BOR-DF563B0F"
    
    # 1. Borrower Check
    borrower = Database.get_borrower(borrower_id)
    print(f"--- Borrower Check ---")
    if borrower:
        print(f"Borrower: {borrower.id}")
        print(f"Org: {borrower.organization_id}")
    else:
        print("Borrower NOT FOUND")

    # 2. Audit Logs Check
    print(f"\n--- Audit Logs (Last 10) ---")
    logs = AuditAgent.list_logs(limit=10)
    for l in logs:
        print(f"Event: {l.get('event_type')}")
        print(f"Actor: {l.get('actor')}")
        print(f"Org: {l.get('organization_id')}")
        print(f"Details: {json.dumps(l.get('details'))}")
        print("-" * 20)

if __name__ == "__main__":
    final_inspect()

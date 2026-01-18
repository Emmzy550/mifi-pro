#!/usr/bin/env python3
"""Script to inspect database contents and find assessments."""
from utils.db import Database

def main():
    db = Database.get_db()
    
    # Get all assessments
    assessments_col = db.collection('assessments')
    docs = list(assessments_col.stream())
    
    print(f"\n=== Total Assessments in Firestore: {len(docs)} ===\n")
    
    org_counts = {}
    for doc in docs:
        data = doc.to_dict()
        org_id = data.get('organization_id', 'UNKNOWN')
        decision = data.get('decision', 'N/A')
        risk_level = data.get('risk_level', 'N/A')
        
        org_counts[org_id] = org_counts.get(org_id, 0) + 1
        print(f"  {doc.id}: org={org_id}, decision={decision}, risk={risk_level}")
    
    print(f"\n=== Assessments by Organization ===")
    for org, count in org_counts.items():
        print(f"  {org}: {count} assessments")
    
    # Also check users
    print(f"\n=== Users in Database ===")
    users_col = db.collection('users')
    user_docs = list(users_col.stream())
    for doc in user_docs:
        data = doc.to_dict()
        email = data.get('email', 'N/A')
        org_id = data.get('organization_id', 'UNKNOWN')
        print(f"  {email}: org={org_id}")

if __name__ == "__main__":
    main()

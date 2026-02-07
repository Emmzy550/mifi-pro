import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.db import Database

def debug_db():
    print("=== Database Debug Info ===")
    db = Database.get_db()
    print(f"Using DB: {type(db)}")
    
    assessments = Database.list_assessments()
    print(f"Total assessments: {len(assessments)}")
    
    if assessments:
        print("\nLast 10 assessments:")
        for a in assessments[:10]:
            print(f"  - ID: {a.assessment_id}, Org: {a.organization_id}, Created: {a.created_at}")
    
    unique_orgs = set(a.organization_id for a in assessments)
    print(f"\nUnique Orgs in assessments: {unique_orgs}")

if __name__ == "__main__":
    debug_db()

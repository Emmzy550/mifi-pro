import sys
import os
from utils.db import Database

def check_org(org_id):
    print(f"--- Checking Org: {org_id} ---")
    Database.get_db()
    
    org = Database.get_organization(org_id)
    if org:
        print(f"Org FOUND.")
        print(f"ID: {org.id}")
        print(f"Status: {org.status}")
    else:
        print("Org NOT FOUND.")
        
        # List first 5 orgs
        db = Database.get_db()
        docs = db.collection("organizations").limit(5).stream()
        print("\n--- Listing first 5 orgs ---")
        for doc in docs:
            print(f"- {doc.id}")

if __name__ == "__main__":
    check_org("DEFAULT_ORG")

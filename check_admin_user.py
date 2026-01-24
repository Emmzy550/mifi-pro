import sys
import os
from utils.db import Database

def check_user(email):
    print(f"--- Checking User: {email} ---")
    db = Database.get_db()
    
    user = Database.get_user_by_email(email)
    if user:
        print(f"User FOUND in Firestore.")
        print(f"ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"Org: {user.organization_id}")
        print(f"Role: {user.role}")
        
        # Check Org as well
        org = Database.get_organization(user.organization_id)
        if org:
            print(f"Org Status: {org.status}")
        else:
            print("Org NOT FOUND.")
    else:
        print("User NOT FOUND in Firestore.")
        
        # List first 5 users to see what's there
        print("\n--- Listing first 5 users ---")
        docs = db.collection("users").limit(5).stream()
        for doc in docs:
             u = doc.to_dict()
             print(f"- {u.get('email')}")

if __name__ == "__main__":
    check_user("admin@acme.com")

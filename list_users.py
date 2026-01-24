import sys
import os
from utils.db import Database

def list_users():
    print("--- Listing Users in Firestore ---")
    Database.get_db()
    
    users = Database.list_all_users() # Corrected method name
    if not users:
        # Fallback: stream manually
        db = Database.get_db()
        docs = db.collection("users").stream()
        users = [doc.to_dict() for doc in docs]

    if not users:
        print("No users found.")
    else:
        for u in users:
            print(f"Email: {u.email}, Role: {u.role}, Org: {u.organization_id}")

if __name__ == "__main__":
    list_users()

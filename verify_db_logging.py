
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import Database

print("Calling Database.get_db()...")
db = Database.get_db()
print("Database initialized.")

if os.path.exists("db_init_debug.txt"):
    print(f"File created: {open('db_init_debug.txt').read()}")
else:
    print("File NOT created.")

print("\nChecking Usage Record in Real Firestore:")
try:
    doc = db.collection("usage_records").document("ORG-44141161_SANDBOX").get()
    if doc.exists:
        print(f"Found Record: {doc.to_dict()}")
    else:
        print("Record NOT found.")
except Exception as e:
    print(f"Error fetching record: {e}")

